# gui/

The Ultra Vivid control panel — a PySide6 editor for `config.json`.
Dark-first theme per the monorepo [DESIGN.md](../../../DESIGN.md); the
engine itself never needs the GUI (it reads the same config).

## Files

### `app.py` — Entry Point
`python -m gui.app` from the project root. Applies the theme QSS and
shows the main window.

### `main_window.py` — Window Shell
Tabs, the Save / Apply now / Install tasks action bar, and a live status
line showing what the schedule resolves to right now.

### `theme.py` — Theme
DESIGN.md tokens (surfaces, vivid-violet accent, radii, spacing) and the
application QSS. All styling values live here (Rule #4).

### `config_io.py` — Config I/O
Loads the raw config dict; saving validates through `core.settings.parse`
first — an invalid edit never reaches the file (Rule #1).

### `presets_tab.py` — Presets Tab
The base entity: named color presets. Rename cascades into every
reference; deletion is blocked while a preset is in use.

### `schedule_tab.py` — Schedule Tab
One grouping type per schedule (owner spec): hours / weekdays /
monthdays / months / daylight, each with its own editor.

### `devices_tab.py` — Devices Tab
Live device list from the OpenRGB SDK with check boxes (unchecked =
excluded), plus the optional Razer Chroma module toggles.

### `shortcuts_tab.py` — Shortcuts Tab
Shortcut sets: selector + key row + per-key preset bindings, and the
"Write slot files" action for Synapse Hypershift bindings.

## Connections

### Uses
- [Core (folder)](../core/__index.md) — validation, schedule preview, SDK device list

### Used by
- The owner. The scheduled tasks and daemon run without the GUI.
