# OpenRGB Task Scheduler Auto-Setup
# Author: UV
# Run as Administrator

$libPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "lib"

# 1. Initialization - load config, create folders, delete old tasks
. (Join-Path $libPath "init.ps1")

# 2. Generate autoprofile.vbs (time-based profile switcher)
. (Join-Path $libPath "generate-bat.ps1")

# 3. Generate VBS files (server, cycle/schedule, shortcuts/rainbow)
. (Join-Path $libPath "generate-vbs.ps1")

# 4. Create Task Scheduler tasks (schedule, if enabled)
. (Join-Path $libPath "create-tasks.ps1")

# 5. Generate keyboard hotkey daemon + task (if enabled)
. (Join-Path $libPath "generate-hotkeys.ps1")

# Final message
$schedEnabled  = $config.schedules.enabled
$shortEnabled  = $config.shortcuts.enabled
$schedCount    = if ($schedEnabled) { $config.schedules.items.Count } else { 0 }
$shortCount    = if ($shortEnabled) { $config.shortcuts.items.Count } else { 0 }

Write-Host "`n=== COMPLETED ===" -ForegroundColor Cyan
Write-Host "Schedule:  $(if ($schedEnabled) { 'enabled - ' + ($schedCount + 1) + ' tasks' } else { 'disabled' })" -ForegroundColor Cyan
Write-Host "Shortcuts: $(if ($shortEnabled) { 'enabled - ' + $shortCount + ' hotkeys' } else { 'disabled' })" -ForegroundColor Cyan
Write-Host "Cycle VBS: $($config.schedules.items.Count + $config.extras.Count) files" -ForegroundColor Cyan
Write-Host "OpenRGB Server: $serverVbsPath" -ForegroundColor Cyan
Write-Host "`nNOTE: Restart or log out/in for Task Scheduler tasks to start automatically." -ForegroundColor Yellow
