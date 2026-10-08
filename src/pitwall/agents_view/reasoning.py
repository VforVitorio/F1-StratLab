"""The six reasoning bodies used by the cross-surface content guards.

The orchestrator body includes DecisionMemory only when the call changes.
Each agent body contains its reasoning followed by its metric dump. Bodies
travel as one neutral segment because the AGENTS UI does not render their
styling, while the guards still compare their text against WHY and tooltips.
"""

from __future__ import annotations

from typing import Any

from src.arcade.palette import TEXT_PRIMARY, hex_str
from src.pitwall.reasoning_lines import agent_body, clean

DEFAULT_COLOUR = hex_str(TEXT_PRIMARY)

TABS: tuple[tuple[str, str], ...] = (
    ("orchestrator", "Orchestrator"),
    ("pace", "Pace"),
    ("tire", "Tire"),
    ("situation", "Situation"),
    ("radio", "Radio"),
    ("pit", "Pit"),
)


def orchestrator_body(latest: dict[str, Any]) -> str:
    """The decision's reasoning, plus the memory block on a changed lap only.

    DecisionMemory leaves no trace in `reasoning` even when it drives the
    call, so the block is rendered here rather than trusting the model to
    narrate its own continuity. Hidden on every other lap: the action
    changes on a small minority of them, and unconditional display was
    measured as wallpaper.
    """
    text = clean(latest.get("reasoning")) or "— no reasoning —"
    memory_block = latest.get("memory_block")
    if latest.get("plan_changed") and memory_block:
        text += "\n\n--- why this call changed ---\n" + str(memory_block)
    return text


def build_reasoning(latest: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return six tabs with one neutral segment per body, or empty tabs without a decision."""
    if not latest:
        return [{"key": key, "label": label, "segments": []} for key, label in TABS]

    per = latest.get("per_agent") or {}
    tabs: list[dict[str, Any]] = []
    for key, label in TABS:
        if key == "orchestrator":
            body = orchestrator_body(latest)
        else:
            body = agent_body(key, per.get(key))
        segments = [{"text": body, "colour": DEFAULT_COLOUR, "bold": False}]
        tabs.append({"key": key, "label": label, "segments": segments})
    return tabs
