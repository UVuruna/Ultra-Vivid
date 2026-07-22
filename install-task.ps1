# install-task.ps1 - Register the single "Ultra Vivid resolver" scheduled task
#
# Replaces the legacy nine "OpenRGB *" tasks: the resolver computes the
# active color itself on every tick, so one task covers the whole schedule.
# Triggers: at log on, on resume from sleep, and every 10 minutes
# (the tick is a no-op when the computed preset has not changed).
#
# Run:  .\install-task.ps1        (elevation only needed to delete legacy
#                                  tasks that were created as admin)

$ErrorActionPreference = "Stop"

$taskName   = "Ultra Vivid resolver"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$resolver   = Join-Path $projectDir "resolver.py"

$pythonw = Join-Path (Split-Path (Get-Command python).Source) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Host "ERROR: pythonw.exe not found next to python.exe" -ForegroundColor Red
    exit 1
}

# -- Action: run the resolver windowless from the project folder ----------
$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$resolver`"" -WorkingDirectory $projectDir

# -- Trigger 1: at log on -------------------------------------------------
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn
$logonTrigger.UserId = "$env:USERDOMAIN\$env:USERNAME"

# -- Trigger 2: resume from sleep (Power-Troubleshooter event 1) ----------
$eventClass = Get-CimClass -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler
$resumeTrigger = New-CimInstance -CimClass $eventClass -ClientOnly
$resumeTrigger.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Power-Troubleshooter''] and EventID=1]]</Select></Query></QueryList>'
$resumeTrigger.Enabled = $true

# -- Trigger 3: every 10 minutes, forever ---------------------------------
# Task Scheduler XML rejects TimeSpan.MaxValue — 10 years is effectively forever
$tickTrigger = New-ScheduledTaskTrigger -Once -At ([datetime]::Today) `
    -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$task = New-ScheduledTask -Action $action -Trigger @($logonTrigger, $resumeTrigger, $tickTrigger) -Settings $settings
$task.Author = "UV"

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host "Registered task: $taskName (log on + resume + 10-min tick)" -ForegroundColor Green

# -- Remove the legacy nine tasks -----------------------------------------
$legacy = @("OpenRGB autoprofile", "OpenRGB zora", "OpenRGB jutro", "OpenRGB podne",
            "OpenRGB popodne", "OpenRGB vece", "OpenRGB sumrak", "OpenRGB ponoc", "OpenRGB noc")
foreach ($name in $legacy) {
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing) {
        try {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
            Write-Host "Removed legacy task: $name" -ForegroundColor DarkGray
        } catch {
            Write-Host "Could not remove '$name' (run elevated to clean up): $_" -ForegroundColor Yellow
        }
    }
}

Write-Host "Done. Test with: python resolver.py --dry-run" -ForegroundColor Cyan
