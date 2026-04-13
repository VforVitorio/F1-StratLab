# Frontend CSS Fixes

## Scroll Fix on Plotly Charts (stElementContainer)

### Problem

Streamlit wraps Plotly charts in `div.stElementContainer` elements that can develop unwanted horizontal scrollbars. This happens because the Plotly SVG layout occasionally renders a few pixels wider than the container, triggering overflow.

### Solution

Located in `src/telemetry/frontend/components/common/chart_styles.py`, the `apply_telemetry_chart_styles()` function injects CSS that hides the scrollbar on the parent wrapper without clipping chart content:

```css
/* Hide scrollbar on the parent wrapper */
div.stElementContainer:has(div[data-testid="stPlotlyChart"]) {
    scrollbar-width: none !important;          /* Firefox */
    -ms-overflow-style: none !important;       /* IE/Edge */
}
div.stElementContainer:has(div[data-testid="stPlotlyChart"])::-webkit-scrollbar {
    display: none !important;                  /* Chrome/Safari */
}
```

The selector uses `:has()` to target only containers that wrap Plotly charts, avoiding side effects on other Streamlit elements.

### Chart Styling

The same function also applies a consistent visual treatment to all Plotly charts:

```css
div[data-testid="stPlotlyChart"] {
    outline: 2px solid #a78bfa !important;     /* Purple border */
    outline-offset: -2px !important;           /* Inset so no extra pixels */
    border-radius: 12px !important;
    background-color: #181633 !important;      /* Dark background */
    box-shadow: 0 4px 12px rgba(167, 139, 250, 0.2) !important;
}
```

`outline` is used instead of `border` because outlines do not affect the box model and cannot cause layout shifts or trigger scrollbars.

### Usage

Call `apply_telemetry_chart_styles()` once at the top of any page that renders Plotly charts:

```python
from components.common.chart_styles import apply_telemetry_chart_styles
st.markdown(apply_telemetry_chart_styles(), unsafe_allow_html=True)
```

## Loading Spinner Removal

### Location

`src/telemetry/frontend/components/common/loading.py`

### What It Does

`render_loading_spinner()` renders an animated CSS spinner inside a purple-bordered container that matches Plotly chart dimensions (400px height). It shows "Waiting for telemetry data..." text with five vertical bars that animate in sequence.

### Why It Should Be Removed From Empty States

The spinner was designed to display while telemetry data is actively loading. However, it was also used as a placeholder in empty states (before the user selects a session/driver), where no loading is actually happening. This confuses users because:

1. The "Waiting for telemetry data..." text implies the system is fetching data when it is not.
2. The animation suggests an ongoing operation, but nothing will complete until the user makes a selection.
3. Multiple spinners on a page (one per chart placeholder) create visual noise.

The correct pattern for empty states is a static placeholder or no content at all -- spinners should only appear during actual asynchronous operations.

### Current Status

The spinner is still present in several telemetry graph components under `components/telemetry/` and `components/comparison/`. Removal is tracked as a pending task.

### Files Using the Spinner

- `components/telemetry/speed_graph.py`
- `components/telemetry/brake_graph.py`
- `components/telemetry/throttle_graph.py`
- `components/telemetry/gear_graph.py`
- `components/telemetry/rpm_graph.py`
- `components/telemetry/drs_graph.py`
- `components/telemetry/delta_graph.py`
- `components/telemetry/circuit_domination.py`
- `components/comparison/synchronized_comparison_animation.py`
- `components/comparison/legacy/*.py` (5 files)
