# Scheduled Tasks

**Script:** [Tasks (script)](tasks.py)

## Purpose
Register the two Ultra Vivid scheduled tasks, from the repo OR the frozen
exe — the task actions point at whatever is running (`python resolver.py`
in the repo, `UltraVivid.exe --tick` when packaged), so the same code
sets up both.

| Task | Trigger | Action |
|------|---------|--------|
| `Ultra Vivid resolver` | log on + resume-from-sleep + every 10 min | resolver tick |
| `Ultra Vivid daemon` | log on (resident) | hotkeys + optional Chroma |

Also writes `OpenRGB-Server.vbs` to the Startup folder and removes the
legacy nine `OpenRGB *` tasks. Registration runs elevated once (UAC).

## Invoked by
- `python main.py --install-tasks` (repo) — or the GUI **Install tasks…** button
- the NSIS installer's "Run at startup" section (`UltraVivid.exe --install-tasks --elevated`)

## Connections
### Uses
- [Paths](paths.md) — repo-vs-frozen action commands
