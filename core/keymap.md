# Keymap

**Script:** [Keymap (script)](keymap.py)

## Purpose
Single source of truth for shortcut keys — the GUI shows the labels,
the daemon maps the same labels to Win32 virtual-key codes and
`RegisterHotKey` modifier flags. Shared so the two can never drift
(Rule #5).

| Table | Contents |
|-------|----------|
| `VIRTUAL_KEYS` | every supported key label → Win32 VK code (F-keys, digits, numpad, letters, punctuation) — a set may mix ANY of them |
| `KEY_GROUPS` | display grouping for the GUI key-picker menu |
| `MODIFIER_FLAGS` | selector → RegisterHotKey flags (hypershift absent by design — Synapse territory) |

## Connections

### Used by
- [Shortcuts Tab](../gui/shortcuts_tab.py) (labels), [Hotkey Daemon](../hotkey_daemon.md) (VK codes)
