"""Pure formatters that turn per-agent output dicts into the tuple the
``AgentCard`` widget renders.

One function per sub-agent (Pace N25, Tire N26, Situation N27, Radio N29,
Pit N28, RAG N30). The logic mirrors the CLI's six-row inference panel
(``c:/tmp/arcade_analysis/06_cli_inference_panel.md`` §1.1–§1.6) so the
dashboard reads as a visual extension of the CLI without divergent
thresholds.

Return shape: ``(headline_text, headline_color, body_lines, status)``
where ``body_lines`` is ``list[tuple[str, color]]`` (one line per
pair) and ``status`` is ``"OK" | "WATCH" | "ALERT" | "IDLE"``. The card
widget maps ``status`` to the glyph + colour.

No agent package imports — formatters accept plain dicts already
serialised by ``src/arcade/strategy.py::_dump_dataclass``.
"""

from __future__ import annotations

from typing import Any

from src.arcade.dashboard.theme import (
    DANGER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    WARNING,
    compound_pill_html,
    flag_chip_html,
)

# Status tokens consumed by AgentCard.set_status
STATUS_OK:    str = "OK"
STATUS_WATCH: str = "WATCH"
STATUS_ALERT: str = "ALERT"
STATUS_IDLE:  str = "IDLE"

# Type alias for readability only.
Line = tuple[str, tuple[int, int, int]]
Formatted = tuple[str, tuple[int, int, int], list[Line], str]


def _signed(x: float, decimals: int = 3) -> str:
    """Return a +/- signed string so ``+0.123`` vs ``-0.123`` pops visually."""
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.{decimals}f}"


# --- N25 Pace -----------------------------------------------------------


def format_pace(p: dict[str, Any] | None) -> Formatted:
    """CLI §1.1 — headline Δnext, context pred / median / CI."""
    if not p:
        return (
            "no prediction — stub",
            TEXT_TERTIARY,
            [],
            STATUS_IDLE,
        )
    delta_prev = float(p.get("delta_vs_prev", 0.0) or 0.0)
    delta_med = float(p.get("delta_vs_median", 0.0) or 0.0)
    pred = float(p.get("lap_time_pred", 0.0) or 0.0)
    ci_p10 = float(p.get("ci_p10", 0.0) or 0.0)
    ci_p90 = float(p.get("ci_p90", 0.0) or 0.0)
    ci_half = (ci_p90 - ci_p10) / 2 if ci_p90 and ci_p10 else 0.0

    if delta_prev <= 0:
        status = STATUS_OK
    elif delta_prev <= 0.25:
        status = STATUS_WATCH
    else:
        status = STATUS_ALERT

    headline = f"Δnext {_signed(delta_prev, 3)}s"
    body: list[Line] = [
        (f"pred {pred:.2f}s", TEXT_SECONDARY),
        (f"vs median {_signed(delta_med, 2)}s", TEXT_SECONDARY),
        (f"±{ci_half:.2f}s (CI)", TEXT_TERTIARY),
    ]
    return headline, TEXT_PRIMARY, body, status


# --- N26 Tire -----------------------------------------------------------


_TIRE_CLIFF_MAX_SANE: float = 100.0  # laps — anything above this is early-stint TCN noise


def format_tire(t: dict[str, Any] | None) -> Formatted:
    """CLI §1.2 — cliff p50, range p10-p90, deg rate, warning_level.

    Early-stint outputs (lap 1-3) can produce absurd cliff projections
    (tens of thousands of laps) because the TCN's MC Dropout samples
    lack enough history to converge. We clamp the display to a plausible
    range: values above ``_TIRE_CLIFF_MAX_SANE`` collapse to a "stabilising"
    message and drop the range line rather than render useless numbers.
    """
    if not t:
        return (
            "no prediction — stub",
            TEXT_TERTIARY,
            [],
            STATUS_IDLE,
        )
    p10 = float(t.get("laps_to_cliff_p10", 0.0) or 0.0)
    p50 = float(t.get("laps_to_cliff_p50", 0.0) or 0.0)
    p90 = float(t.get("laps_to_cliff_p90", 0.0) or 0.0)
    deg = float(t.get("deg_rate", 0.0) or 0.0)
    warning = str(t.get("warning_level") or "OK").upper()
    compound = str(t.get("compound") or "--")

    status_map = {"PIT_SOON": STATUS_ALERT, "MONITOR": STATUS_WATCH, "OK": STATUS_OK}
    status = status_map.get(warning, STATUS_OK)

    # Degradation rate may arrive as 0 while the agent is still warming up;
    # render an em-dash so the user sees "no reading yet" not "0 s/lap".
    deg_text = f"{deg:.3f}s/lap" if deg > 0.0 else "— s/lap"
    compound_label = compound if compound != "0" else "—"

    cliff_unreliable = p50 > _TIRE_CLIFF_MAX_SANE or p50 <= 0
    if cliff_unreliable:
        headline = "cliff stabilising…"
        pill = compound_pill_html(compound_label)
        body: list[Line] = [
            (f"deg {deg_text} · {pill}", TEXT_SECONDARY),
            (warning, _status_colour(status)),
        ]
        return headline, TEXT_TERTIARY, body, STATUS_WATCH if status == STATUS_OK else status

    headline = f"Cliff ~{int(p50)} laps"
    pill = compound_pill_html(compound_label)
    body = [
        (f"range {int(p10)}–{int(p90)} laps", TEXT_SECONDARY),
        (f"deg {deg_text} · {pill}", TEXT_SECONDARY),
        (warning, _status_colour(status)),
    ]
    return headline, TEXT_PRIMARY, body, status


# --- N27 Situation ------------------------------------------------------


def format_situation(s: dict[str, Any] | None) -> Formatted:
    """CLI §1.3 — threat level, overtake/SC probabilities, SC gold if >15%."""
    if not s:
        return (
            "no prediction — stub",
            TEXT_TERTIARY,
            [],
            STATUS_IDLE,
        )
    ot = float(s.get("overtake_prob", 0.0) or 0.0)
    sc = float(s.get("sc_prob_3lap", 0.0) or 0.0)
    gap = float(s.get("gap_ahead_s", 0.0) or 0.0)
    threat = str(s.get("threat_level") or "LOW").upper()

    status_map = {"HIGH": STATUS_ALERT, "MEDIUM": STATUS_WATCH, "LOW": STATUS_OK}
    status = status_map.get(threat, STATUS_OK)
    headline_color = _status_colour(status)

    sc_color = WARNING if sc > 0.15 else TEXT_SECONDARY
    body: list[Line] = [
        (f"overtake {ot * 100:.0f}%", TEXT_SECONDARY),
        (f"safety car {sc * 100:.0f}%", sc_color),
        (f"gap ahead {gap:.1f}s", TEXT_TERTIARY),
    ]
    return f"Threat {threat}", headline_color, body, status


# --- N29 Radio ----------------------------------------------------------


def format_radio(r: dict[str, Any] | None) -> Formatted:
    """CLI §1.4 — alert intents if any, else "quiet" / "no alerts"."""
    if r is None:
        return (
            "no radio/rcm pipeline output",
            TEXT_TERTIARY,
            [],
            STATUS_IDLE,
        )
    radio_events = r.get("radio_events") or []
    rcm_events = r.get("rcm_events") or []
    alerts = r.get("alerts") or []
    n_radios = len(radio_events)
    n_rcms = len(rcm_events)

    if alerts:
        chips: list[str] = []
        for a in alerts[:3]:
            if isinstance(a, dict):
                intent = a.get("intent") or a.get("event_type") or "ALERT"
            else:
                intent = str(a)
            chips.append(flag_chip_html(intent))
        headline = " ".join(chips)
        headline_color = WARNING
        status = STATUS_ALERT
    elif n_radios or n_rcms:
        headline = "no alerts"
        headline_color = TEXT_PRIMARY
        status = STATUS_OK
    else:
        headline = "quiet"
        headline_color = TEXT_PRIMARY
        status = STATUS_OK

    body: list[Line] = [
        (f"{n_radios} radios · {n_rcms} rcm", TEXT_SECONDARY),
    ]
    return headline, headline_color, body, status


# --- N28 Pit (conditional) ---------------------------------------------


def format_pit(p: dict[str, Any] | None, active: bool) -> Formatted:
    """CLI §1.5 — active shows pit p50 → compound; idle shows trigger hint."""
    if not active or not p:
        return (
            "triggers on cliff pressure, compound change, or problem radio",
            TEXT_TERTIARY,
            [],
            STATUS_IDLE,
        )
    p05 = float(p.get("stop_duration_p05", 0.0) or 0.0)
    p50 = float(p.get("stop_duration_p50", 0.0) or 0.0)
    p95 = float(p.get("stop_duration_p95", 0.0) or 0.0)
    compound = str(p.get("compound_recommendation") or "--")
    up = p.get("undercut_prob")
    target = p.get("undercut_target")

    headline = f"pit {p50:.2f}s → {compound}"
    lines: list[Line] = [(f"range {p05:.2f}–{p95:.2f}s", TEXT_SECONDARY)]
    if up is not None and target:
        lines.append(
            (f"UCUT {float(up) * 100:.0f}% → {target}", WARNING)
        )
    else:
        lines.append(("no undercut target", TEXT_TERTIARY))
    return headline, WARNING, lines, STATUS_WATCH


# --- N30 RAG (conditional) ---------------------------------------------


def format_rag(regulation_context: str | None, active: bool) -> Formatted:
    """CLI §1.6 — active shows "regulation loaded" + first 60 chars; idle shows hint."""
    if not active:
        return (
            "triggers on compound change, SC >30%, or FIA warning/penalty",
            TEXT_TERTIARY,
            [],
            STATUS_IDLE,
        )
    text = (regulation_context or "").strip()
    if not text:
        return (
            "regulation loaded",
            TEXT_PRIMARY,
            [("(empty context)", TEXT_TERTIARY)],
            STATUS_OK,
        )
    snippet = text[:120].replace("\n", " ")
    body: list[Line] = [(snippet + ("…" if len(text) > 120 else ""), TEXT_SECONDARY)]
    return "regulation loaded", TEXT_PRIMARY, body, STATUS_OK


# --- Shared helpers -----------------------------------------------------


def _status_colour(status: str) -> tuple[int, int, int]:
    return {
        STATUS_OK:    SUCCESS,
        STATUS_WATCH: WARNING,
        STATUS_ALERT: DANGER,
        STATUS_IDLE:  TEXT_TERTIARY,
    }.get(status, TEXT_TERTIARY)
