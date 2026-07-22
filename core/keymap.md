# Keymap

**Script:** [Keymap (script)](keymap.py)

## Purpose
Single source of truth for shortcut keys — the GUI shows the labels,
the daemon maps the same labels to Win32 virtual-key codes and
`RegisterHotKey` modifier flags. Shared so the two can never drift
(Rule #5).

| Table | Contents |
|-------|----------|
| `KEY_ROWS` | key labels per row: fkeys, numrow, numpad, qwerty (12 each) |
| `VIRTUAL_KEYS` | label → Win32 VK code |
| `MODIFIER_FLAGS` | selector → RegisterHotKey flags (hypershift absent by design — Synapse territory) |

## Connections

### Used by
- [Shortcuts Tab](../gui/shortcuts_tab.py) (labels), [Hotkey Daemon](../hotkey_daemon.md) (VK codes)
