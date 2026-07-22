# gui/

The Ultra Vivid control panel — a PySide6 editor for `config.json`.
Dark-first theme per the monorepo [DESIGN.md](../../../DESIGN.md); opens
portrait (W:H = 1:2, min width 900, clamped to the screen). The engine
itself never needs the GUI (it reads the same config).

## Files

### `app.py` — Entry Point
`python -m gui.app` from the project root.

### `main_window.py` — Window Shell
Tabs, the Save / Apply now / Install tasks action bar, and a live status
line: active preset + what it resolves to right now.

### `theme.py` — Theme
DESIGN.md tokens (surfaces, vivid-violet accent, radii, spacing) and the
application QSS, including visible check indicators (assets/check.svg).

### `widgets.py` — Shared Widgets
Color combos with swatches, emoji tool buttons (➕ 🗑 ⬆ ⬇), and the
ordered color sequence editor with reordering.

### `config_io.py` — Config I/O
Loads the raw config dict; saving validates through `core.settings.parse`
first — an invalid edit never reaches the file (Rule #1).

### `colors_tab.py` — Colors Tab
The DEFINED COLORS (owner terminology): default palette + fully custom
colors. Rename cascades into every reference; deletion is blocked while
a color is in use.

### `presets_tab.py` — Presets Tab
A PRESET is a RULE: a trigger grouping (hours / weekdays / monthdays /
months / daylight) whose slots reference colors. Several presets, one
⭐ active. The daylight editor has separate morning/evening twilight
colors and the city picker.

### `location_picker.py` — City Picker
DOMY Watch's 45k-city system: live search + cascading combos; picking a
city fills lat/lon/timezone automatically (timezone is never typed).

### `devices_tab.py` — Devices Tab
Live device list from the OpenRGB SDK with check boxes (unchecked =
excluded), plus the optional Razer Chroma module toggles.

### `shortcuts_tab.py` — Shortcuts Tab
The owner's flow: named set → selector (hypershift offered only when a
Razer keyboard is detected) → ANY keys → color per key → "Create
shortcut files" (normal: daemon auto-registers; hypershift: folder +
Synapse + linking guide open).

## Connections

### Uses
- [Core (folder)](../core/__index.md) — validation, schedule preview, SDK device list, locations

### Used by
- The owner. The scheduled tasks and daemon run without the GUI.
