# generate-hotkeys.ps1 - Generate keyboard shortcut daemon and Task Scheduler task
#
# Creates rainbow/hotkeys.ps1 - a hidden PowerShell process that registers global
# hotkeys via Win32 RegisterHotKey and dispatches them to OpenRGB.
# Creates rainbow/hotkeys_runner.vbs - launches hotkeys.ps1 silently.
# Registers "OpenRGB hotkeys" Task Scheduler task (at log on).

# ------------------------------------------------------------------
# If shortcuts are disabled: clean up and exit
# ------------------------------------------------------------------

if (-not $config.shortcuts.enabled) {
    Write-Host "Shortcuts disabled - removing hotkey task if present..." -ForegroundColor DarkGray

    # Kill any running hotkeys.ps1 process
    Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*hotkeys.ps1*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    return
}

# ------------------------------------------------------------------
# Modifier flag mapping
# ------------------------------------------------------------------

$modFlags = switch ($config.shortcuts.modifier) {
    "Ctrl+Shift" { 6 }   # MOD_CONTROL | MOD_SHIFT
    "Alt+Shift"  { 5 }   # MOD_ALT | MOD_SHIFT
    default      { 4 }   # MOD_SHIFT
}

# ------------------------------------------------------------------
# Virtual key code arrays (12 keys each)
# ------------------------------------------------------------------

# F1-F12: 0x70 .. 0x7B
$vkF   = @(0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x7B)

# Number row: 1 2 3 4 5 6 7 8 9 0 - =
$vkNum = @(0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30, 0xBD, 0xBB)

$vkCodes = if ($config.shortcuts.keyRow -eq "num") { $vkNum } else { $vkF }

# ------------------------------------------------------------------
# Build registration lines for each assigned slot
# ------------------------------------------------------------------

$items = $config.shortcuts.items
$registrationLines = [System.Collections.Generic.List[string]]::new()

for ($i = 0; $i -lt $items.Count; $i++) {
    if ($i -ge $vkCodes.Count) { break }
    $prof = ($items[$i].profile -replace '"', '').Trim()
    if ([string]::IsNullOrEmpty($prof)) { continue }
    $vk = "0x{0:X2}" -f $vkCodes[$i]
    $registrationLines.Add(
        '$r.Register({0}, {1}, {2}, $exe, "{3}")' -f ($i + 1), $modFlags, $vk, $prof
    )
}

if ($registrationLines.Count -eq 0) {
    Write-Host "Shortcuts enabled but no profiles assigned - skipping hotkey task." -ForegroundColor Yellow
    return
}

# ------------------------------------------------------------------
# C# code for hidden WndProc form (static - no variable expansion)
# ------------------------------------------------------------------

$csharp = @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class HotkeyReceiver : Form {
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);
    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    private const int WM_HOTKEY = 0x0312;
    private readonly Dictionary<int, string[]> _actions = new Dictionary<int, string[]>();

    public HotkeyReceiver() {
        this.ShowInTaskbar = false;
        this.Text = "AutoOpenRGB-Hotkeys";
        // Access Handle to force Win32 window creation before Application.Run
        var _ = this.Handle;
    }

    protected override void SetVisibleCore(bool value) {
        // Never show the form window
        base.SetVisibleCore(false);
    }

    public void Register(int id, uint modifiers, uint vk, string exe, string profile) {
        if (RegisterHotKey(this.Handle, id, modifiers, vk))
            _actions[id] = new string[] { exe, profile };
    }

    protected override void WndProc(ref Message m) {
        if (m.Msg == WM_HOTKEY) {
            int id = (int)m.WParam;
            if (_actions.ContainsKey(id)) {
                var psi = new ProcessStartInfo {
                    FileName = _actions[id][0],
                    Arguments = "-p \"" + _actions[id][1] + "\"",
                    WindowStyle = ProcessWindowStyle.Hidden,
                    CreateNoWindow = true
                };
                Process.Start(psi);
            }
        }
        base.WndProc(ref m);
    }

    protected override void OnFormClosed(FormClosedEventArgs e) {
        foreach (int id in _actions.Keys)
            UnregisterHotKey(this.Handle, id);
        base.OnFormClosed(e);
    }
}
'@

# ------------------------------------------------------------------
# Assemble hotkeys.ps1 content line by line
# ------------------------------------------------------------------

$hotkeysPath   = Join-Path $rainbowPath "hotkeys.ps1"
$launcherPath  = Join-Path $rainbowPath "hotkeys_runner.vbs"

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# Auto-generated by AutoOpenRGB Setup - do not edit manually")
$lines.Add("# Edit config.json and run setup.ps1 to update")
$lines.Add("")
$lines.Add('Add-Type -TypeDefinition @"')

foreach ($cline in ($csharp -split "`n")) {
    $lines.Add($cline.TrimEnd("`r"))
}

$lines.Add('"@ -ReferencedAssemblies System.Windows.Forms, System.Drawing')
$lines.Add("")
$lines.Add('$exe = "' + $openRGBPath.Replace('"', '') + '"')
$lines.Add('$r   = New-Object HotkeyReceiver')
$lines.Add("")

foreach ($reg in $registrationLines) {
    $lines.Add($reg)
}

$lines.Add("")
$lines.Add('[System.Windows.Forms.Application]::Run($r)')

$lines | Out-File -FilePath $hotkeysPath -Encoding UTF8
Write-Host "Generated: rainbow/hotkeys.ps1 ($($registrationLines.Count) hotkeys)" -ForegroundColor Green

# ------------------------------------------------------------------
# Generate hotkeys_runner.vbs - launches hotkeys.ps1 hidden
# ------------------------------------------------------------------

$launcherContent = 'Set WshShell = CreateObject("WScript.Shell")' + "`r`n" +
    'WshShell.Run "powershell.exe -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & "' +
    $hotkeysPath.Replace('"', '') + '" & """", 0' + "`r`n" +
    'WScript.Quit'

$launcherContent | Out-File -FilePath $launcherPath -Encoding ASCII
Write-Host "Generated: rainbow/hotkeys_runner.vbs" -ForegroundColor Green

# ------------------------------------------------------------------
# Kill any running hotkeys.ps1 instance (from previous setup run)
# ------------------------------------------------------------------

Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*hotkeys.ps1*" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped old hotkeys.ps1 process (PID $($_.ProcessId))" -ForegroundColor DarkGray
    }

# ------------------------------------------------------------------
# Create Task Scheduler task "OpenRGB hotkeys" (at log on, user session)
# ------------------------------------------------------------------

Write-Host "Creating hotkeys task..." -ForegroundColor Yellow

$action    = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcherPath`""
$trigger   = New-ScheduledTaskTrigger -AtLogOn
$trigger.UserId = "$env:USERDOMAIN\$env:USERNAME"
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances Stop
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal
$task.Author = "UV"

Register-ScheduledTask -TaskName "OpenRGB hotkeys" -InputObject $task -Force | Out-Null
Write-Host "Created task: OpenRGB hotkeys (at log on)" -ForegroundColor Green

# Start immediately so shortcuts work without rebooting
Start-ScheduledTask -TaskName "OpenRGB hotkeys" -ErrorAction SilentlyContinue
Write-Host "Started hotkeys daemon." -ForegroundColor Green
