# 1. Clean up old registry entries
$oldPaths = @(
    "HKCR:\SystemFileAssociations\audio\shell\YeshivaAudioFeedback",
    "HKCR:\mp3file\shell\YeshivaAudioFeedback",
    "HKCR:\WMP11.AssocFile.MP3\shell\YeshivaAudioFeedback",
    "HKCR:\.mp3\shell\YeshivaAudioFeedback",
    "HKCU:\Software\Classes\SystemFileAssociations\audio\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\SystemFileAssociations\.mp3\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\SystemFileAssociations\.wav\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\mp3file\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\WMP11.AssocFile.MP3\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\*\shell\YeshivaAudioFeedback",
    "HKCU:\Software\Classes\*\shell\YeshivaFeedback"
)

foreach ($p in $oldPaths) {
    if (Test-Path $p) {
        Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 2. Build Hebrew String safely: "השאר הערה לאחראי השמע"
$hebrewChars = [char[]]@(
    0x05D4, 0x05E9, 0x05D0, 0x05E8, 0x0020, # השאר
    0x05D4, 0x05E2, 0x05E8, 0x05D4, 0x0020, # הערה
    0x05DC, 0x05D0, 0x05D7, 0x05E8, 0x05D0, 0x05D9, 0x0020, # לאחראי
    0x05D4, 0x05E9, 0x05DE, 0x05E2 # השמע
)
$menuText = [string]::new($hebrewChars)

$commandValue = 'powershell.exe -WindowStyle Hidden -Command "Start-Process (''http://192.168.1.244:8000/student?file='' + [uri]::EscapeDataString(''%1''))"'

$newTargets = @(
    "HKCU:\Software\Classes\SystemFileAssociations\audio\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\SystemFileAssociations\.mp3\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\SystemFileAssociations\.wav\shell\YeshivaFeedback",
    "HKCU:\Software\Classes\*\shell\YeshivaFeedback"
)

foreach ($target in $newTargets) {
    New-Item -Path $target -Force | Out-Null
    Set-ItemProperty -Path $target -Name "(Default)" -Value $menuText
    Set-ItemProperty -Path $target -Name "Icon" -Value "shell32.dll,269"
    
    $cmdPath = "$target\command"
    New-Item -Path $cmdPath -Force | Out-Null
    Set-ItemProperty -Path $cmdPath -Name "(Default)" -Value $commandValue
}

Write-Host "============================================================" -ForegroundColor Green
Write-Host "Success: Context Menu installed in clean Hebrew!" -ForegroundColor Green
Write-Host "Menu Item: $menuText" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green
