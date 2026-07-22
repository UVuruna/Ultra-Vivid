# Hotkey Daemon

**Script:** [Hotkey Daemon (script)](hotkey_daemon.py)

## Purpose
Resident process (Task Scheduler: `Ultra Vivid daemon`, at log on,
windowless) serving the two features that need a resident process:

1. **Global hotkeys** — one `RegisterHotKey` per binding in every
   non-hypershift shortcut set; a press applies the bound color preset.
   Hypershift is Synapse's job via the stable slot files.
2. **Chroma keyboard** (optional) — holds the Razer Chroma session
   (sessions die without heartbeat) and colors the keyboard: following
   the schedule and/or on hotkey presses. See [Chroma](core/chroma.md).

## Behavior (pseudocode)

```
IF another instance runs (named mutex) -> exit
REGISTER hotkeys from config (skip hypershift sets)
START chroma thread (heartbeat every 5 s; follow schedule each minute)
START 5 s timer; LOOP on Windows messages:
    WM_TIMER  -> config.json changed? -> reload + re-register hotkeys
    WM_HOTKEY -> apply the bound preset (worker thread)
```

The daemon stays resident even with nothing registered — the GUI may
add a set at any moment and it activates within 5 s, no restart. All
(un)registration happens on the message-loop thread (Win32 requirement).

Failures are logged to `logs/daemon.log` and never crash the loop; a
hotkey another app already owns is logged as a warning (Rule #1).

## Connections

### Uses
- [Core (folder)](core/__index.md) — settings, keymap, apply, schedule, chroma

### Used by
- Task Scheduler task `Ultra Vivid daemon` — see [Install Task](install-task.md)
