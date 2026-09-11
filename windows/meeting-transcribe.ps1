param(
    [string]$OutputDir = "$([Environment]::GetFolderPath('MyMusic'))\MeetingRecordings"
)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       1-KLICK MEETING RECORDER & WHISPER GPU           " -ForegroundColor Yellow
Write-Host "             (100% Autark, ohne Meetily)                " -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$wavFile = Join-Path $OutputDir "Meeting_$timestamp.wav"
$speakersFile = Join-Path $OutputDir "Meeting_$timestamp.speakers.json"

$cscoreDll = "C:\Users\dhallmann\scripts\CSCore.dll"
$recorderDll = "C:\Users\dhallmann\scripts\MeetingRecorder.dll"

if (-not (Test-Path $cscoreDll) -or -not (Test-Path $recorderDll)) {
    Write-Host "[!] Fehler: CSCore.dll oder MeetingRecorder.dll fehlt in C:\Users\dhallmann\scripts" -ForegroundColor Red
    Exit 1
}

Add-Type -Path $cscoreDll
Add-Type -Path $recorderDll

$recorder = New-Object MeetingAudioRecorder

Write-Host "`n[*] Starte Dual-Track Audio-Aufnahme..." -ForegroundColor Cyan
# 'VLegend' selektiert dein Headset-Mikrofon (Poly VLegend 50) und schliesst die Webcam (Poly Studio P5) aus!
$recorder.Start($wavFile, "VLegend", "VLegend")

# Optionales Teams Active Speaker Tracking im Hintergrund starten
$wslSpeakers = $speakersFile.Replace('\', '/').Replace('C:', '/mnt/c')
$trackerJob = Start-Job -ScriptBlock {
    param($out)
    wsl -e bash -ilc "node ~/projects/teams-mcp/bin/track-speakers.js record --out '$out'"
} -ArgumentList $wslSpeakers

Write-Host "`n--------------------------------------------------------" -ForegroundColor Yellow
Write-Host " [AUFNAHME LAEUFT] " -ForegroundColor Red -NoNewline
Write-Host "Teams-Ton und Mikrofon werden aufgezeichnet." -ForegroundColor White
Write-Host " Druecke [ENTER], sobald das Meeting beendet ist!" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------`n" -ForegroundColor Yellow

$null = Read-Host

Write-Host "`n[*] Stoppe Aufnahme und finalisiere Audio-Datei..." -ForegroundColor Cyan
$recorder.Stop()

# Teams Speaker Tracking beenden
if ($trackerJob) {
    Stop-Job $trackerJob -ErrorAction SilentlyContinue | Out-Null
    Remove-Job $trackerJob -ErrorAction SilentlyContinue | Out-Null
    wsl -e bash -ilc "node ~/projects/teams-mcp/bin/track-speakers.js stop" 2>$null | Out-Null
}

Write-Host "`n[*] Starte Whisper GPU Transkription und Sprechertrennung..." -ForegroundColor Cyan

$wslWav = $wavFile.Replace('\', '/').Replace('C:', '/mnt/c')
$wslOut = $OutputDir.Replace('\', '/').Replace('C:', '/mnt/c')

$cmd = "~/projects/meeting-recorder/run_dual.sh '" + $wslWav + "' '" + $wslOut + "'"
wsl -e bash -ilc $cmd

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "[OK] FERTIG! Transkript liegt in deiner Windows-Zwischenablage." -ForegroundColor Green
Write-Host "     Einfach mit [Strg + V] in OneNote oder Teams einfuegen." -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
Write-Host "Fenster schliesst in 5 Sekunden..." -ForegroundColor Gray
Start-Sleep -Seconds 5
