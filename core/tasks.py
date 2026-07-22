"""Register the Ultra Vivid scheduled tasks — from the repo OR the exe.

Two tasks (same as before, now pointing at whatever is running us):
  - "Ultra Vivid resolver"  log on + resume + 10-min tick
  - "Ultra Vivid daemon"    log on, resident (hotkeys + optional Chroma)
plus the OpenRGB SDK-server VBS in the Startup folder, and removal of the
legacy nine "OpenRGB *" tasks.

The registration itself is PowerShell (New-ScheduledTask*, the CIM event
trigger for resume-from-sleep) run elevated once — the proven approach.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from core import paths

RESOLVER_TASK = "Ultra Vivid resolver"
DAEMON_TASK = "Ultra Vivid daemon"
LEGACY_TASKS = ["OpenRGB autoprofile", "OpenRGB zora", "OpenRGB jutro",
                "OpenRGB podne", "OpenRGB popodne", "OpenRGB vece",
                "OpenRGB sumrak", "OpenRGB ponoc", "OpenRGB noc"]


def _action(*args: str) -> tuple[str, str]:
    """(Execute, Arguments) for a scheduled-task action that re-invokes
    this program with the given flags — windowless in both modes."""
    if paths.IS_FROZEN:
        return sys.executable, " ".join(args)
    pythonw = str(Path(sys.executable).parent / "pythonw.exe")
    script = "resolver.py" if args and args[0] != "--daemon" else "hotkey_daemon.py"
    inner = [str(paths.BUNDLE_DIR / script), *[a for a in args if a != "--daemon" and a != "--tick"]]
    return pythonw, " ".join(f'"{part}"' if " " in part else part for part in inner)


def _write_server_vbs() -> Path:
    """Write OpenRGB-Server.vbs to the Startup folder from Python — kept
    out of the PowerShell here-string to avoid nested-quote hell."""
    try:
        openrgb_path = json.loads(
            paths.CONFIG_PATH.read_text(encoding="utf-8"))["openrgb"]["path"]
    except (OSError, KeyError, json.JSONDecodeError):
        openrgb_path = r"C:\Program Files\OpenRGB\OpenRGB.exe"

    startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" \
        / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    server_vbs = startup / "OpenRGB-Server.vbs"
    quote = '"' * 3   # VBS needs the path wrapped in doubled quotes
    server_vbs.write_text(
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.Run {quote}{openrgb_path}"" --server --startminimized", 0\n'
        "WScript.Quit\n",
        encoding="ascii",
    )
    return server_vbs


def _build_script() -> str:
    resolver_exe, resolver_args = _action("--tick")
    daemon_exe, daemon_args = _action("--daemon")
    legacy_list = ", ".join(f'"{name}"' for name in LEGACY_TASKS)

    return f"""
$ErrorActionPreference = "Stop"

$resolverAction = New-ScheduledTaskAction -Execute '{resolver_exe}' -Argument '{resolver_args}'
$logon = New-ScheduledTaskTrigger -AtLogOn
$logon.UserId = "$env:USERDOMAIN\\$env:USERNAME"

$eventClass = Get-CimClass -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler
$resume = New-CimInstance -CimClass $eventClass -ClientOnly
$resume.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Power-Troubleshooter''] and EventID=1]]</Select></Query></QueryList>'
$resume.Enabled = $true

$tick = New-ScheduledTaskTrigger -Once -At ([datetime]::Today) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)

$rSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$rTask = New-ScheduledTask -Action $resolverAction -Trigger @($logon, $resume, $tick) -Settings $rSettings
$rTask.Author = "UV"
Register-ScheduledTask -TaskName "{RESOLVER_TASK}" -InputObject $rTask -Force | Out-Null
Write-Host "Registered: {RESOLVER_TASK}"

$daemonAction = New-ScheduledTaskAction -Execute '{daemon_exe}' -Argument '{daemon_args}'
$dLogon = New-ScheduledTaskTrigger -AtLogOn
$dLogon.UserId = "$env:USERDOMAIN\\$env:USERNAME"
$dSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$dTask = New-ScheduledTask -Action $daemonAction -Trigger $dLogon -Settings $dSettings
$dTask.Author = "UV"
Register-ScheduledTask -TaskName "{DAEMON_TASK}" -InputObject $dTask -Force | Out-Null
Write-Host "Registered: {DAEMON_TASK}"

foreach ($name in @({legacy_list})) {{
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($t) {{ Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue; Write-Host "Removed legacy: $name" }}
}}
"""


def install(elevated: bool = False) -> None:
    """Register the tasks. When not already elevated, relaunch this same
    step under UAC and wait for it."""
    paths.ensure_state()
    _write_server_vbs()
    script = _build_script()
    script_file = Path(tempfile.gettempdir()) / "ultravivid_install_tasks.ps1"
    script_file.write_text(script, encoding="utf-8")

    if elevated:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(script_file)], check=False)
    else:
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            f'Start-Process powershell -ArgumentList '
            f'"-NoProfile -ExecutionPolicy Bypass -File `"{script_file}`"" '
            f'-Verb RunAs -Wait'
        ], check=False)
