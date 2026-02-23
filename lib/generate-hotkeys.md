# generate-hotkeys.ps1

**Script:** [generate-hotkeys.ps1](generate-hotkeys.ps1)

## Purpose

Generates the keyboard shortcut daemon and registers it as a Task Scheduler task.

When enabled, creates:
- `rainbow/hotkeys.ps1` — a hidden PowerShell process that registers global hotkeys via the Win32 `RegisterHotKey` API and dispatches them to OpenRGB
- `rainbow/hotkeys_runner.vbs` — silent VBScript launcher for `hotkeys.ps1`
- Task Scheduler task `OpenRGB hotkeys` (runs at log on)

When shortcuts are disabled: removes existing task, kills any running daemon process.

## Dependencies

- Called by `setup.ps1` (step 5)
- Requires variables from `init.ps1`: `$config`, `$openRGBPath`, `$rainbowPath`
- No external tools required — uses pure .NET/Win32 via `Add-Type`

## How the Hotkey Daemon Works

`hotkeys.ps1` uses `Add-Type` to compile a small C# class (`HotkeyReceiver`) at runtime:

1. Creates a hidden Windows Form (never shown, handle created for message routing)
2. Calls `RegisterHotKey(hWnd, id, modifiers, vk)` for each assigned profile
3. Overrides `WndProc` to intercept `WM_HOTKEY` (0x0312) messages
4. On hotkey press: launches `OpenRGB.exe -p "ProfileName"` hidden
5. On form close: unregisters all hotkeys

No console window, no taskbar entry, no external dependencies.

## Modifier Flags

| Config value | Win32 flags | Decimal |
|---|---|---|
| `Shift` | `MOD_SHIFT` | 4 |
| `Ctrl+Shift` | `MOD_CONTROL \| MOD_SHIFT` | 6 |
| `Alt+Shift` | `MOD_ALT \| MOD_SHIFT` | 5 |

## Key Row VK Codes

**F1-F12:** `0x70` through `0x7B`

**Number row:** `0x31-0x39` (1-9), `0x30` (0), `0xBD` (-), `0xBB` (=)
