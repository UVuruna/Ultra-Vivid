# Paths

**Script:** [Paths (script)](paths.py)

## Purpose
The single place that knows where things live, so identical code runs
from the repo AND as a frozen single-exe.

**One config, always.** Writable state lives under `%LOCALAPPDATA%\UltraVivid`
in EVERY mode — so a repo run and the installed exe read/write the SAME
`config.json`, and a GUI edit is always the edit the daemon and the
Synapse slots see. (An earlier repo-vs-LOCALAPPDATA split let you edit
one config while the running pieces read the other — edits looked like
they "didn't apply".)

| | Location |
|--|----------|
| Writable state (config.json, logs, state.json) | `%LOCALAPPDATA%\UltraVivid` (always) |
| Read-only data (world DB, assets, default-config seed) | repo folder (dev) or bundle `sys._MEIPASS` (frozen) |
| Slot files | repo `shortcuts/` (dev) or LOCALAPPDATA (frozen) — kept with the generating code so existing Synapse links stay valid |

`ensure_state()` seeds `config.json` under `%LOCALAPPDATA%` on first run
from the shipped default. The repo's tracked `config.json` is that
default seed, not the live config.
`launcher_command()` / `slot_command_string()` produce the right
re-invocation (`pythonw resolver.py …` vs `UltraVivid.exe …`) for
scheduled tasks and Synapse slot files.

## Used by
- Everything with a path: [Resolver](../resolver.md), [Hotkey Daemon](../hotkey_daemon.md),
  [Tasks](tasks.md), [Settings](settings.md), [Locations](locations.md), the GUI
