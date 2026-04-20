"""Audit DRS zones per GP — sanity check against the FIA 2025 circuit docs.

Uses the same ``_extract_reference_lap`` pattern the arcade's
``SessionLoader`` relies on: fastest qualifying lap telemetry, ``DRS``
column, ``add_distance()`` for the distance axis.

For each DRS activation zone the script reports:

- Start / end distance in metres from the start-finish line
- Zone length in metres
- Start / end (X, Y) coordinates in FastF1 position units (1/10 mm)
- Approximate speed at the detection point (km/h)

The FIA publishes a per-GP "Event Notes / DRS activation zones" PDF
that lists zones as "from Turn X to Turn Y" plus the exact detection
and activation distances. Cross-reference the ``zone_start_m`` values
below with those figures — they should match within ~30 m (sampling
resolution of FastF1 telemetry).

Usage:
    python scripts/verify_drs_zones.py --year 2025
    python scripts/verify_drs_zones.py --year 2025 --round 3
    python scripts/verify_drs_zones.py --year 2025 --json drs_audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import fastf1  # noqa: E402


def extract_zones(tel) -> list[dict]:
    """Walk the telemetry row-by-row, emit one dict per DRS-ON run.

    FastF1 publishes ``DRS`` as a status byte; values ``>= 10`` mean the
    flap is open. A "zone" is any maximal run of open samples. The
    emitter collects boundary coordinates (X, Y) and boundary speeds
    so a human verifier can line the numbers up against the FIA
    document or the arcade replay overlay."""
    drs = tel["DRS"].to_numpy().astype(float)
    dist = tel["Distance"].to_numpy().astype(float)
    x = tel["X"].to_numpy().astype(float)
    y = tel["Y"].to_numpy().astype(float)
    speed = tel["Speed"].to_numpy().astype(float)

    zones: list[dict] = []
    active = drs >= 10
    n = active.size
    i = 0
    while i < n:
        if not active[i]:
            i += 1
            continue
        j = i
        while j < n and active[j]:
            j += 1
        # [i, j) is the run
        zones.append({
            "zone_start_m":  round(float(dist[i]), 1),
            "zone_end_m":    round(float(dist[j - 1]), 1),
            "length_m":      round(float(dist[j - 1] - dist[i]), 1),
            "start_xy":      (int(x[i]),     int(y[i])),
            "end_xy":        (int(x[j - 1]), int(y[j - 1])),
            "start_speed_kph": round(float(speed[i]), 1),
            "end_speed_kph":   round(float(speed[j - 1]), 1),
            "samples":       int(j - i),
        })
        i = j
    return zones


def audit_one(year: int, round_: int) -> dict:
    """Load quali, fastest lap, telemetry + add_distance — then
    extract zones. Exceptions become error dicts so a single bad
    session does not halt the batch."""
    try:
        session = fastf1.get_session(year, round_, "Q")
        session.load(telemetry=True, laps=True, weather=False, messages=False)
        lap = session.laps.pick_fastest()
        if lap is None or lap.empty:
            return {"round": round_, "error": "no fastest lap in quali"}
        tel = lap.get_telemetry().add_distance()
        if "DRS" not in tel.columns:
            return {
                "round": round_,
                "gp":    session.event.get("Location", "?"),
                "error": "DRS column missing",
            }
        zones = extract_zones(tel)
        lap_length_m = round(float(tel["Distance"].iloc[-1]), 1)
        return {
            "round":        round_,
            "gp":           session.event.get("Location", "?"),
            "lap_length_m": lap_length_m,
            "n_zones":      len(zones),
            "zones":        zones,
        }
    except Exception as exc:
        return {"round": round_, "error": f"{type(exc).__name__}: {exc}"}


def _classify(row: dict) -> str:
    if "error" in row:
        return "ERROR"
    n = row.get("n_zones", 0)
    if n == 0:
        return "BROKEN"
    if 1 <= n <= 4:
        return "OK"
    return "SUSPICIOUS"


def _format_row(row: dict) -> str:
    """Human-readable per-GP block for cross-checking against FIA docs."""
    header = f"R{row['round']:02d}  "
    if "error" in row:
        return header + f"ERROR: {row['error']}"
    body = (
        f"{row['gp']:<22s}  lap={row['lap_length_m']}m  "
        f"zones={row['n_zones']}"
    )
    lines = [header + body]
    for i, z in enumerate(row["zones"], 1):
        lines.append(
            f"    Zone {i}: {z['zone_start_m']:>6.1f}m → {z['zone_end_m']:>6.1f}m  "
            f"({z['length_m']:>5.1f}m)  "
            f"xy[{z['start_xy'][0]:>7d}, {z['start_xy'][1]:>7d}] → "
            f"[{z['end_xy'][0]:>7d}, {z['end_xy'][1]:>7d}]  "
            f"spd {z['start_speed_kph']:>5.1f} → {z['end_speed_kph']:>5.1f} kph"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DRS zones per GP.")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--round", type=int, default=0,
        help="Single round to audit (default: all rounds in the year).",
    )
    parser.add_argument(
        "--json", type=str, default="",
        help="If set, dump the full audit as JSON to this path.",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Skip the per-GP detail block and print only the summary table.",
    )
    args = parser.parse_args()

    fastf1.Cache.enable_cache(_REPO_ROOT / "data" / "cache" / "fastf1")

    rounds = [args.round] if args.round else list(range(1, 25))
    rows: list[dict] = []
    for r in rounds:
        row = audit_one(args.year, r)
        rows.append(row)
        if not args.summary:
            print(_format_row(row))
            print()

    print("=== Summary ===")
    for row in rows:
        status = _classify(row)
        tag = f"[{status:10s}]"
        if "error" in row:
            print(f"  R{row['round']:02d} {tag} — {row['error']}")
        else:
            print(
                f"  R{row['round']:02d} {tag}  "
                f"{row['gp']:<22s} zones={row['n_zones']}"
            )
    broken = [r for r in rows if _classify(r) in ("BROKEN", "ERROR")]
    sus = [r for r in rows if _classify(r) == "SUSPICIOUS"]
    print(
        f"\n{len(rows)} rounds audited · "
        f"{len(broken)} broken/error · {len(sus)} suspicious"
    )

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nJSON dump written to {out_path}")

    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
