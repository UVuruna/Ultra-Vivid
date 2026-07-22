# Install Task

**Script:** [Install Task (script)](install-task.ps1)

## Purpose
Register the single `Ultra Vivid resolver` scheduled task and remove the
legacy nine `OpenRGB *` tasks. Run once (idempotent — re-running just
re-registers).

## Task definition

| Aspect | Value |
|--------|-------|
| Action | `pythonw.exe resolver.py` (windowless), working dir = project |
| Trigger 1 | At log on |
| Trigger 2 | Resume from sleep (Power-Troubleshooter event 1) |
| Trigger 3 | Every 10 minutes (repetition duration 10 years — Task Scheduler rejects `TimeSpan.MaxValue`) |
| Settings | Start on batteries, start when available, 5-min execution cap |

The 10-minute tick is what makes minute-precision daylight boundaries work;
it is free because the resolver skips applying when the decision is
unchanged.

## Connections

### Uses
- [Resolver](resolver.md)
