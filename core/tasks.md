# Scheduled Tasks

**Script:** [Tasks (script)](tasks.py)

## Purpose
Register the three Ultra Vivid scheduled tasks, from the repo OR the frozen
exe — the task actions point at whatever is running (`python resolver.py`
in the repo, `UltraVivid.exe --tick` when packaged), so the same code
sets up both.

| Task | Trigger | Level | Action |
|------|---------|-------|--------|
| `OpenRGB server` | log on | **Highest (elevated)** | `OpenRGB.exe --server --startminimized` |
| `Ultra Vivid resolver` | log on + resume-from-sleep + every 10 min | normal | resolver tick |
| `Ultra Vivid daemon` | log on (resident) | normal | hotkeys + optional Chroma |

**Why OpenRGB runs as an elevated task (not the old Startup VBS):** the RAM
SMBus needs administrator rights. A non-elevated instance can enumerate the
RAM but not write to it, and TWO instances fight over the bus — the exact
"everything colors except the RAM" boot bug. The registration therefore also:

- **removes a conflicting auto-start `OpenRGB` *service*** — a second,
  non-`--server` instance that starts as SYSTEM, owns the SMBus, and blocks
  our server's RAM writes (this is a *service*, so earlier legacy-*task*
  cleanups never caught it);
- **deletes the old non-elevated `OpenRGB-Server.vbs`** from Startup;
- removes the legacy nine `OpenRGB *` tasks;
- ensures exactly one live instance (kills any OpenRGB, then starts the task).

Registration runs elevated once (UAC). Only the OpenRGB server needs
elevation — the resolver/daemon are plain SDK clients (localhost), so they
stay non-elevated.

## Invoked by
- `python main.py --install-tasks` (repo) — or the GUI **Install tasks…** button
- the NSIS installer's "Run at startup" section (`UltraVivid.exe --install-tasks --elevated`)

## Connections
### Uses
- [Paths](paths.md) — repo-vs-frozen action commands
