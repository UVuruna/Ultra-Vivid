# core/

The Ultra Vivid engine: pure decision logic plus the OpenRGB SDK applier.
Everything here is GUI-free; [Resolver](../resolver.md) is the only entry
point, the future GUI is just an editor for `config.json`.

## Files

### `settings.py` — Config Loader
Loads and validates `config.json` (schema v2) into frozen dataclasses.
Every validation error names the exact field — a broken config never
half-runs (Rule #1). See [Settings](settings.md).

### `solar.py` — Sun Events
Civil dawn, sunrise, solar noon, sunset, civil dusk for one local day via
`astral` (same library and −6° convention as DOMY Watch). See [Solar](solar.md).

### `schedule.py` — Preset Resolution
Pure function `(Settings, now) -> preset name | None(OFF)` for all five
schedule types. See [Schedule](schedule.md).

### `apply.py` — SDK Applier
Connects to the OpenRGB SDK server, filters devices by the config
include/exclude list, applies colors in Direct (fallback Static) mode.
See [Apply](apply.md).

### `actions.py` — Shortcut Binding Action
Shared logic behind a shortcut press: apply a color, or switch the
active preset and apply what it resolves to. See [Actions](actions.md).

### `keymap.py` — Key Tables
Key labels + Win32 VK codes + modifier flags, shared by GUI and daemon.
See [Keymap](keymap.md).

### `chroma.py` — Razer Chroma Client
Optional keyboard coloring through the local Chroma REST endpoint,
held by the daemon. See [Chroma](chroma.md).

### `locations.py` — World Locations
The DOMY Watch 45k-city database (`data/world_locations.json`):
cascading tree + folded-name search. Picking a city fills lat/lon and
the IANA timezone — the user never types a timezone.

## Connections

### Used by
- [Resolver](../resolver.md) — CLI entry point (Task Scheduler tick, Synapse slots)
- [Hotkey Daemon](../hotkey_daemon.md) — global hotkeys + Chroma session
- [GUI (folder)](../gui/__index.md) — validation, live preview, device list

## Design Decisions
- **Compute, don't generate (root Rule #19):** no `.orp` profiles, no
  per-combination VBS files — one engine computes the color for any moment
  from rules in `config.json`.
- **Pure core:** `schedule.py`/`solar.py` do no I/O, so every schedule type
  is testable without hardware.
