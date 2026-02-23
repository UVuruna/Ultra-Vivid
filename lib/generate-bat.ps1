# generate-bat.ps1 - Generate autoprofile.vbs (time-based profile switcher)

# Function to generate VBS content
function New-TimeVbs {
    param (
        [array]$Items,
        [string]$OpenRGBPath,
        [bool]$WithRetry = $false
    )

    $vbsContent = @"
' Auto-generated file - do not edit manually!
' Edit config.json and run setup.ps1

Set WshShell = CreateObject("WScript.Shell")

"@

    if ($WithRetry) {
        $vbsContent += @"
Set objWMI = GetObject("winmgmts:\\.\root\cimv2")

' Wait for OpenRGB server (max 60 sec)
retries = 0
Do While retries < 30
    Set colProcesses = objWMI.ExecQuery("SELECT * FROM Win32_Process WHERE Name = 'OpenRGB.exe'")
    If colProcesses.Count > 0 Then Exit Do
    WScript.Sleep 2000
    retries = retries + 1
Loop

If retries >= 30 Then WScript.Quit

"@
    }

    $vbsContent += @"
' Get current hour
currentHour = Hour(Now)

' Determine profile based on hour
Select Case True

"@

    # Generate Case conditions
    for ($i = 0; $i -lt $Items.Count; $i++) {
        $item = $Items[$i]
        $prof = $item.profile

        # Parse start hour from "HH:MM"
        $start = [int]($item.startTime -split ":")[0]

        # End = next item's start hour (wraps around for last item)
        if ($i -lt $Items.Count - 1) {
            $end = [int]($Items[$i + 1].startTime -split ":")[0]
        } else {
            $end = [int]($Items[0].startTime -split ":")[0]
        }

        if ($start -eq 0) {
            # Starts at midnight (e.g., 0-3)
            $vbsContent += "    Case currentHour < $end`r`n"
        } elseif ($end -eq 0) {
            # Ends at midnight (e.g., 21-0)
            $vbsContent += "    Case currentHour >= $start`r`n"
        } elseif ($end -lt $start) {
            # Crosses midnight (e.g., 23-2)
            $vbsContent += "    Case currentHour >= $start Or currentHour < $end`r`n"
        } else {
            # Normal range (e.g., 6-9)
            $vbsContent += "    Case currentHour >= $start And currentHour < $end`r`n"
        }
        $vbsContent += "        profile = `"$prof`"`r`n"
    }

    $vbsContent += @"
End Select

' Run OpenRGB (hidden)
WshShell.Run """$OpenRGBPath"" -p """ & profile & """", 0
WScript.Quit
"@

    return $vbsContent
}

# Generate autoprofile.vbs (with retry logic for Task Scheduler)
Write-Host "Generating autoprofile.vbs..." -ForegroundColor Yellow

$autoprofileVbsPath = Join-Path $generatedPath "autoprofile.vbs"
$autoprofileVbsContent = New-TimeVbs -Items $config.schedules.items -OpenRGBPath $openRGBPath -WithRetry $true
$autoprofileVbsContent | Out-File -FilePath $autoprofileVbsPath -Encoding ASCII
Write-Host "Created: generated/autoprofile.vbs" -ForegroundColor Green

# Clean up old generated files if they exist
foreach ($oldFile in @("autoprofile.bat", "autorainbow.bat", "autorainbow.vbs")) {
    $oldPath = Join-Path $generatedPath $oldFile
    if (Test-Path $oldPath) {
        Remove-Item $oldPath -Force
        Write-Host "Removed old: generated/$oldFile" -ForegroundColor DarkGray
    }
}
