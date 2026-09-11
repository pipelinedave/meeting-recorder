# meeting-recorder

> **100% lokaler, autarker 1-Klick Meeting-Recorder & GPU-Transkriptor mit hardwarebasierter Sprechertrennung und DOM-basiertem Multi-Speaker Alignment**

Nimmt Meetings (Microsoft Teams, Zoom, Web-Browser) ohne Cloud und ohne fremde Recording-Bots direkt über Windows WASAPI Loopback auf. Die Sprechertrennung erfolgt physisch auf zwei getrennten Tonspuren (Kanal Links = eigenes Headset-Mikrofon, Kanal Rechts = Systemsound / Gegenseite). Nach Meeting-Ende transkribiert eine lokale NVIDIA GPU via `faster-whisper` (`large-v3-turbo`) in wenigen Sekunden das Gespräch, gleicht die Gegenseite optional mit der Teams-Sprecher-Timeline ab und kopiert das fertige Markdown-Transkript direkt in die Windows-Zwischenablage.

---

## Architektur

```
Windows Host:
  [Desktop-Shortcut] -> meeting-transcribe.ps1
    -> MeetingRecorder.dll (C# / CSCore WASAPI)
         - Stream 1: Headset-Mikrofon (z.B. Poly VLegend 50) -> Kanal 1
         - Stream 2: Headset-Sound (Loopback / Teams)         -> Kanal 2
    -> Startet im Hintergrund: teams-mcp Speaker Tracker (track-speakers.js record)
    -> Speichert als 16kHz Stereo-WAV unter Music/MeetingRecordings/
    -> Schreibt beim Beenden .stop Signaldatei für sauberen JSON-Export

WSL2 Backend (NVIDIA CUDA):
  run_dual.sh -> transcribe_dual.py
    -> faster-whisper (large-v3-turbo FP16) mit VAD-Clusterung (Silero VAD)
    -> Separierte Transkription beider Kanäle ohne Silence-Merge-Drift
    -> Multi-Speaker Alignment mit *.speakers.json (Teams DOM & 1:1 Call Auto-Matching)
    -> Paragraph-Merging für natürliche, flüssige Redeblöcke
    -> iconv UTF-16LE Pipe an Windows clip.exe (saubere deutsche Umlaute)
```

## Features
- **1-Klick Bedienung:** Ein Klick auf die Desktop- oder Taskleisten-Verknüpfung startet die Aufnahme, `ENTER` beendet und transkribiert.
- **Hardware-Sprechertrennung:** `David:` vs. `Gegenseite / Kunde:` ohne rechenintensive KI-Diarisierung.
- **Multi-Speaker Alignment (Teams DOM):** Erkennt via `teams-mcp` die aktiven Sprecher im Teams-Call und ersetzt `Gegenseite` durch echte Namen (z.B. `Stefan Maciolek:`, `Robert Lábas:`, `Niklas Brunnenkant:`).
- **1:1 Call Auto-Matching:** Erkennt direkte 1:1 Anrufe automatisch und ordnet die gesamte Gegenseite-Spur dem Gesprächspartner zu.
- **Robuste VAD-Clusterung:** Verhindert das Verschmelzen von isolierten Einwürfen bei langen Pausen.
- **Super-Speed:** ~20- bis 100-fache Echtzeit-Geschwindigkeit auf NVIDIA RTX GPUs (30 Min. Meeting in ~15-20 Sek.).
- **Signalverlustfreier Shutdown:** Signaldatei `.stop` garantiert die vollständige Finalisierung der Timeline vor dem Transkriptionsstart.
- **Auto-Unmute:** Erkennt, ob das Headset-Mikrofon in Windows gemuted ist, und entstummt es automatisch.
- **Clipboard-Integration:** Fertiges Markdown-Transkript landet sofort in der Zwischenablage (`Strg + V` für OneNote, Chat oder Mail).

## Tests

```bash
# Alignment & Diarization Unit-Tests
source venv/bin/activate
python -m unittest discover -s tests
```
