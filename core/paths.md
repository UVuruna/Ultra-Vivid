# Paths

**Script:** [Paths (script)](paths.py)

## Purpose
The single place that knows where things live, so identical code runs
from the repo AND as a frozen single-exe.

| | Repo (not frozen) | Frozen exe |
|--|-------------------|------------|
| Read-only data (world DB, assets, default config) | project folder | bundle (`sys._MEIPASS`) |
| Writable state (config.json, logs, shortcuts) | project folder | `%LOCALAPPDATA%\UltraVivid` |

`ensure_state()` seeds `config.json` under `%LOCALAPPDATA%` on first
frozen run (Program Files is not writable by a standard user).
`launcher_command()` / `slot_command_string()` produce the right
re-invocation (`pythonw resolver.py …` vs `UltraVivid.exe …`) for
scheduled tasks and Synapse slot files.

## Used by
- Everything with a path: [Resolver](../resolver.md), [Hotkey Daemon](../hotkey_daemon.md),
  [Tasks](tasks.md), [Settings](settings.md), [Locations](locations.md), the GUI
