# generate-vbs.ps1 - Generate all VBS files

# OpenRGB-Server.vbs in startup folder
Write-Host "Creating OpenRGB-Server.vbs in Startup folder..." -ForegroundColor Yellow

$startupPath = [Environment]::GetFolderPath('Startup')
$script:serverVbsPath = Join-Path $startupPath "OpenRGB-Server.vbs"

$serverVbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """$openRGBPath"" --server --startminimized", 0
WScript.Quit
"@

$serverVbsContent | Out-File -FilePath $serverVbsPath -Encoding ASCII
Write-Host "Created: $serverVbsPath" -ForegroundColor Green

# VBS files for cycle profiles
Write-Host "Generating VBS files in cycle folder..." -ForegroundColor Yellow

foreach ($s in $config.schedules.items) {
    $vbsName = $s.vbsName + ".vbs"
    $vbsPath = Join-Path $cyclePath $vbsName
    $prof = $s.profile

    $vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """$openRGBPath"" -p ""$prof""", 0
WScript.Quit
"@

    $vbsContent | Out-File -FilePath $vbsPath -Encoding ASCII
    Write-Host "Created: cycle\$vbsName -> $prof" -ForegroundColor Green
}

foreach ($e in $config.extras) {
    $vbsName = $e.vbsName + ".vbs"
    $vbsPath = Join-Path $cyclePath $vbsName
    $prof = $e.profile

    $vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """$openRGBPath"" -p ""$prof""", 0
WScript.Quit
"@

    $vbsContent | Out-File -FilePath $vbsPath -Encoding ASCII
    Write-Host "Created: cycle\$vbsName -> $prof" -ForegroundColor Green
}

# VBS files for shortcut profiles (one per key assignment)
Write-Host "Generating VBS files in rainbow folder..." -ForegroundColor Yellow

foreach ($e in $config.shortcuts.items) {
    $vbsName = $e.vbsName + ".vbs"
    $vbsPath = Join-Path $rainbowPath $vbsName
    $prof = $e.profile

    $vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """$openRGBPath"" -p ""$prof""", 0
WScript.Quit
"@

    $vbsContent | Out-File -FilePath $vbsPath -Encoding ASCII
    Write-Host "Created: rainbow\$vbsName -> $prof" -ForegroundColor Green
}
