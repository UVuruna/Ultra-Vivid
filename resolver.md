# Resolver

**Script:** [Resolver (script)](resolver.py)

## Purpose
The single entry point that puts color on the RGB. Wired to three callers:
the **Task Scheduler** task (tick), **Synapse slot files** (`--shortcut`),
and — in Phase 2 — the hotkey daemon.

## Invocations

| Call | Effect |
|------|--------|
| *(no args)* | Tick: resolve schedule → apply; skips when unchanged |
| `--dry-run` | Print the decision, touch nothing |
| `--preset NAME` | Apply a named color preset now |
| `--shortcut "SetName:key"` | Apply the preset that set binds to that key (stale slot = quiet no-op) |
| `--off` | All selected devices off |
| `--force` | Apply even when unchanged |
| `--list-devices` | Show devices as the SDK server reports them |
| `--write-slots` | Regenerate `shortcuts/slot-*.vbs` |

## Design
- **Change detection:** the tick stores its last decision in
  `logs/state.json`; a 10-minute tick therefore costs nothing while the
  preset is unchanged.
- **Logging:** rotating `logs/resolver.log`; top-level failures are logged
  and re-raised — never swallowed (Rule #1).

## Connections

### Uses
- [Core (folder)](core/__index.md) — settings, schedule, apply

### Used by
- Task Scheduler task `Ultra Vivid resolver` — see [Tasks](core/tasks.md)
- [Shortcuts (folder)](shortcuts/__index.md) — Synapse slot files
