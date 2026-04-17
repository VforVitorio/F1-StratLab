"""SSE connector for the multi-agent strategy simulator.

Runs `/api/v1/strategy/simulate` in a background thread, parses the
Server-Sent-Events stream, and mutates a shared `StrategyState` so
`F1ArcadeView.on_draw` can pick up the latest `LapDecision` without
blocking. Kept free of backend-package imports so the Arcade tool can be
installed as a standalone surface.

Event wire format (what `src/telemetry/.../simulator.py` emits):
    event: start
    data: {"gp": "Australia", ...}

    event: decision
    data: {"lap_number": 1, ...}

    event: error | summary
    data: {...}
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from src.arcade.config import (
    ACCENT,
    BACKEND_URL,
    DANGER,
    INFO,
    SSE_BACKOFF_AFTER_FAILURES_S,
    SSE_MAX_CONSECUTIVE_FAILURES,
    SSE_RECONNECT_DELAY_S,
    STRATEGY_ENDPOINT,
    SUCCESS,
    TEXT_SECONDARY,
    WARNING,
)

logger = logging.getLogger(__name__)


# --- DTOs -----------------------------------------------------------------


@dataclass(frozen=True)
class SimulateRequestDTO:
    """Payload for the simulate endpoint. Mirrors `SimulateRequest` Pydantic
    in `src/telemetry/backend/api/v1/endpoints/strategy.py` without importing
    from the backend package."""
    year: int
    gp: str
    driver: str
    team: str
    driver2: str | None = None
    lap_range: tuple[int, int] | None = None
    risk_tolerance: float = 0.5
    no_llm: bool = False
    provider: str = "lmstudio"
    interval_s: float = 0.0


@dataclass(frozen=True)
class StartEventDTO:
    gp: str = ""
    year: int = 0
    driver: str = ""
    driver2: str | None = None
    team: str = ""
    lap_start: int = 1
    lap_end: int = 0
    total_laps: int = 0
    no_llm: bool = False
    provider: str = ""


@dataclass(frozen=True)
class LapDecisionDTO:
    lap_number: int = 0
    compound: str = ""
    tyre_life: int = 0
    position: int = 0
    lap_time_s: float | None = None
    gap_ahead_s: float = 0.0
    action: str = "STAY_OUT"
    confidence: float = 0.0
    reasoning: str = ""
    scenario_scores: dict[str, float] = field(default_factory=dict)
    # Optional tactical fields (LLM mode only):
    pace_mode: str | None = None
    risk_posture: str | None = None
    pit_lap_target: int | None = None
    compound_next: str | None = None
    undercut_target: str | None = None
    agent_alerts: list[str] = field(default_factory=list)
    guardrail_reason: str | None = None


# --- Shared state ---------------------------------------------------------


@dataclass
class StrategyState:
    """Mutable handoff between connector thread and render thread.

    Access is guarded by `_lock`; the render side takes the lock only for a
    fraction of a frame to snapshot `latest` + `error`."""
    start: StartEventDTO | None = None
    latest: LapDecisionDTO | None = None
    history: list[LapDecisionDTO] = field(default_factory=list)
    error: str | None = None
    finished: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> tuple[LapDecisionDTO | None, str | None, bool]:
        with self._lock:
            return self.latest, self.error, self.finished

    def snapshot_dict(self, history_tail: int = 30) -> dict:
        """JSON-serialisable view consumed by the dashboard over the TCP stream.

        Returns the StartEvent + latest LapDecision + the last `history_tail`
        decisions (so the dashboard's charts can redraw on reconnect without
        replaying from lap 1) + the current error + finished flag."""
        with self._lock:
            return {
                "start": asdict(self.start) if self.start is not None else None,
                "latest": asdict(self.latest) if self.latest is not None else None,
                "history_tail": [asdict(d) for d in self.history[-history_tail:]],
                "error": self.error,
                "finished": self.finished,
            }


# --- Connector ------------------------------------------------------------


class SimConnector(threading.Thread):
    """Consumes the strategy SSE stream into a StrategyState.

    Reconnects up to `SSE_MAX_CONSECUTIVE_FAILURES` times on transport
    errors; on prolonged failure sets `state.error = "Backend offline"` and
    sleeps `SSE_BACKOFF_AFTER_FAILURES_S` before retrying, keeping the UI
    alive without spamming the backend."""

    daemon = True

    def __init__(
        self,
        request: SimulateRequestDTO,
        state: StrategyState,
        backend_url: str = BACKEND_URL,
    ) -> None:
        super().__init__(name="SimConnector")
        self._request = request
        self._state = state
        self._backend_url = backend_url.rstrip("/")
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        """Consume the SSE stream; give up after N failed connects.

        The stream is a one-shot: once the backend emits RunSummary the
        loop exits. On transport errors we retry `SSE_MAX_CONSECUTIVE_FAILURES`
        times with `SSE_RECONNECT_DELAY_S` between attempts, then stop the
        thread and let the panel show "Backend offline" until the user
        restarts the replay. Silent retry-forever loops produced noisy
        logs when the backend wasn't running."""
        failures = 0
        while not self._stop_event.is_set():
            try:
                self._consume_once()
                return  # clean end-of-stream
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as exc:
                failures += 1
                logger.warning("SSE transport error (%d/%d): %s",
                               failures, SSE_MAX_CONSECUTIVE_FAILURES, exc)
                if failures >= SSE_MAX_CONSECUTIVE_FAILURES:
                    with self._state._lock:
                        self._state.error = "Backend offline"
                    logger.info("SSE giving up after %d failed connects", failures)
                    return
                self._stop_event.wait(SSE_RECONNECT_DELAY_S)
            except Exception as exc:
                logger.exception("SSE stream crashed: %s", exc)
                with self._state._lock:
                    self._state.error = f"stream error: {exc}"
                return

    def _consume_once(self) -> None:
        url = f"{self._backend_url}{STRATEGY_ENDPOINT}"
        payload = {k: v for k, v in asdict(self._request).items() if v is not None}
        timeout = httpx.Timeout(None, connect=5.0)
        headers = {"Accept": "text/event-stream"}
        logger.info("SSE connecting to %s", url)
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                self._dispatch_stream(resp)

    def _dispatch_stream(self, resp: httpx.Response) -> None:
        event_name: str | None = None
        data_chunks: list[str] = []
        for line in resp.iter_lines():
            if self._stop_event.is_set():
                return
            if line == "":
                if event_name is not None and data_chunks:
                    self._handle_event(event_name, "\n".join(data_chunks))
                event_name = None
                data_chunks = []
                continue
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_chunks.append(line[len("data:"):].strip())

    def _handle_event(self, event: str, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("SSE bad JSON on event=%s: %s", event, exc)
            return
        if event == "start":
            self._on_start(payload)
        elif event == "decision":
            self._on_decision(payload)
        elif event == "error":
            self._on_error(payload)
        elif event == "summary":
            self._on_summary(payload)
        else:
            logger.debug("SSE unknown event: %s", event)

    def _on_start(self, payload: dict[str, Any]) -> None:
        with self._state._lock:
            self._state.start = StartEventDTO(
                gp=payload.get("gp", ""),
                year=int(payload.get("year", 0)),
                driver=payload.get("driver", ""),
                driver2=payload.get("driver2"),
                team=payload.get("team", ""),
                lap_start=int(payload.get("lap_start", 1)),
                lap_end=int(payload.get("lap_end", 0)),
                total_laps=int(payload.get("total_laps", 0)),
                no_llm=bool(payload.get("no_llm", False)),
                provider=payload.get("provider", ""),
            )
            self._state.error = None
        logger.info("SSE start: %s %d %s",
                    payload.get("gp"), payload.get("year"),
                    payload.get("driver"))

    def _on_decision(self, payload: dict[str, Any]) -> None:
        decision = LapDecisionDTO(
            lap_number=int(payload.get("lap_number", 0)),
            compound=str(payload.get("compound", "")),
            tyre_life=int(payload.get("tyre_life", 0) or 0),
            position=int(payload.get("position", 0) or 0),
            lap_time_s=_as_opt_float(payload.get("lap_time_s")),
            gap_ahead_s=float(payload.get("gap_ahead_s") or 0.0),
            action=str(payload.get("action", "STAY_OUT")),
            confidence=float(payload.get("confidence") or 0.0),
            reasoning=str(payload.get("reasoning", "")),
            scenario_scores=_normalize_scores(payload.get("scenario_scores", {})),
            pace_mode=payload.get("pace_mode"),
            risk_posture=payload.get("risk_posture"),
            pit_lap_target=_as_opt_int(payload.get("pit_lap_target")),
            compound_next=payload.get("compound_next"),
            undercut_target=payload.get("undercut_target"),
            agent_alerts=list(payload.get("agent_alerts") or []),
            guardrail_reason=payload.get("guardrail_reason"),
        )
        with self._state._lock:
            self._state.latest = decision
            self._state.history.append(decision)
            self._state.error = None

    def _on_error(self, payload: dict[str, Any]) -> None:
        lap = payload.get("lap")
        msg = payload.get("message", "unknown error")
        with self._state._lock:
            self._state.error = f"lap {lap}: {msg}" if lap else msg

    def _on_summary(self, payload: dict[str, Any]) -> None:
        with self._state._lock:
            self._state.finished = True


# --- Helpers exposed to the panel ----------------------------------------


_ACTION_STYLE: dict[str, tuple[tuple[int, int, int], str]] = {
    "STAY_OUT":  (SUCCESS, "STAY OUT"),
    "PIT_NOW":   (DANGER,  "PIT NOW"),
    "UNDERCUT":  (WARNING, "UNDERCUT"),
    "OVERCUT":   (WARNING, "OVERCUT"),
    "ALERT":     (INFO,    "ALERT"),
    "DNF":       (TEXT_SECONDARY, "DNF"),
    "ERROR":     (DANGER,  "ERROR"),
}


def classify_action(action: str) -> tuple[tuple[int, int, int], str]:
    """Map a raw action string to (colour, display-label) for the badge."""
    return _ACTION_STYLE.get(action.upper(), (ACCENT, action.upper() or "--"))


_ALERT_SEVERITY: dict[str, int] = {
    "SAFETY_CAR": 3, "RED_FLAG": 3,
    "VIRTUAL_SAFETY_CAR": 2, "VSC": 2, "YELLOW_FLAG": 2,
    "PROBLEM": 1, "WARNING": 1,
}


def classify_alerts(
    tags: list[str],
) -> tuple[str, tuple[int, int, int]] | None:
    """Collapse `agent_alerts` tags into one banner line. None when empty."""
    if not tags:
        return None
    severity = max((_ALERT_SEVERITY.get(t.upper(), 0) for t in tags), default=0)
    colour = {3: DANGER, 2: WARNING, 1: INFO}.get(severity, TEXT_SECONDARY)
    text = " · ".join(t.upper() for t in tags[:4])
    return text, colour


# --- Private helpers -----------------------------------------------------


def _as_opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_scores(raw: Any) -> dict[str, float]:
    """Flatten `{"stay_out": {"score": 0.7}, ...}` or `{"STAY_OUT": 0.7}`.

    Simulator emits both shapes depending on LLM mode; we render the same
    four keys in the panel regardless."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        key = str(k).upper()
        if isinstance(v, dict):
            v = v.get("score", 0.0)
        try:
            out[key] = float(v)
        except (TypeError, ValueError):
            out[key] = 0.0
    return out
