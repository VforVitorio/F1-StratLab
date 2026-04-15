# Driver Colors -- Year-Aware System

## Location

`src/telemetry/frontend/components/common/driver_colors.py`

Also used by the backend: `src/telemetry/backend/core/driver_colors.py`.

## Purpose

F1 driver lineups change every season. A driver may switch teams between years, so the color associated with a driver abbreviation must be season-specific. This module provides a year-aware color palette covering 2023--2025 seasons.

## Design

### Team Base Colors

Each team has two hex constants -- one for the primary driver, one for the secondary. For example:

```python
_RED_BULL   = '#3671C6'   # Primary (e.g., VER)
_RED_BULL_2 = '#1B3D8E'   # Secondary (e.g., LAW in 2025, PER in 2024)
```

All ten teams follow this pattern: Ferrari, Mercedes, McLaren, Aston Martin, Alpine, Williams, Racing Bulls (RB), Sauber, Haas.

### Per-Year Mapping

`DRIVER_COLORS_BY_YEAR` is a dict keyed by year (2023, 2024, 2025), each containing a driver-code-to-hex mapping. Mid-season replacements are included (e.g., COL and LAW in 2024).

Notable changes across seasons:
- **Alpine** switched from pink (`#FF87BC`) in 2023--2024 to blue (`#0093CC`) in 2025.
- **HAM** moved from Mercedes (teal) to Ferrari (red) in 2025.
- **SAI** moved from Ferrari to Williams in 2025.

### Flat Fallback

`DRIVER_COLORS = DRIVER_COLORS_BY_YEAR[2025]` provides backward compatibility for code that does not pass a year.

## Public API

### `get_driver_color(driver_code, default='#A259F7', year=None) -> str`

Returns the hex color for a driver in a given season. Falls back to the 2025 flat dict when `year` is None. Returns `default` if the driver code is not found.

### `get_driver_colors_for_list(driver_codes, year=None) -> list`

Batch version -- returns a list of hex colors matching the input list of driver codes.

## Usage

```python
from components.common.driver_colors import get_driver_color

# Year-aware lookup
color = get_driver_color("HAM", year=2024)  # '#27F4D2' (Mercedes teal)
color = get_driver_color("HAM", year=2025)  # '#A30000' (Ferrari dark red)

# Fallback (uses 2025)
color = get_driver_color("VER")  # '#3671C6'
```

## Where It Is Used

- `pages/race_analysis.py` -- tire and gap chart color assignment
- `components/race_analysis/tire_charts.py` -- per-driver tire degradation plots
- `components/race_analysis/gap_charts.py` -- gap evolution charts
- `utils/race_viz.py` -- general race visualization helpers
- `components/dashboard/data_selectors.py` -- dashboard driver selector
- `backend/core/driver_colors.py` -- server-side comparison endpoint color assignment
- `backend/services/telemetry_service.py` -- telemetry data color tagging
