# meeting-recorder

> **100% lokaler, autarker 1-Klick Meeting-Recorder & GPU-Transkriptor mit hardwarebasierter Sprechertrennung**

Nimmt Meetings (Microsoft Teams, Zoom, Browser) ohne Cloud und ohne fremde Recording-Bots direkt über Windows WASAPI Loopback auf. Die Sprechertrennung erfolgt physisch auf zwei getrennten Tonspuren (Kanal Links = eigenes Headset-Mikrofon, Kanal Rechts = Systemsound / Gegenseite). Nach Meeting-Ende transkribiert eine lokale NVIDIA GPU via `faster-whisper` (`large-v3-turbo`) in wenigen Sekunden das Gespräch und kopiert das fertige Markdown-Transkript direkt in die Windows-Zwischenablage.

---

## Architektur

```
Windows Host:
  [Desktop-Shortcut] -> meeting-transcribe.ps1
    -> MeetingRecorder.dll (C# / CSCore WASAPI)
         - Stream 1: Headset-Mikrofon (z.B. Poly VLegend 50) -> Kanal 1
         - Stream 2: Headset-Sound (Loopback / Teams)         -> Kanal 2
    -> Speichert als 16kHz Stereo-WAV unter Music/MeetingRecordings/

WSL2 Backend (NVIDIA CUDA):
  run_dual.sh -> transcribe_dual.py
    -> faster-whisper (large-v3-turbo FP16)
    -> Separierte Transkription beider Kanäle
    -> Chronologisches Alignment & Formatierung mit Sprecher-Tags
    -> iconv UTF-16LE Pipe an Windows clip.exe (saubere deutsche Umlaute)
```

## Features
- **1-Klick Bedienung:** Ein Klick auf die Desktop- oder Taskleisten-Verknüpfung startet die Aufnahme, `ENTER` beendet und transkribiert.
- **Hardware-Sprechertrennung:** `David:` vs. `Gegenseite / Kunde:` ohne rechenintensive KI-Diarisierung.
- **Super-Speed:** ~100-fache Echtzeit-Geschwindigkeit auf NVIDIA RTX GPUs (30 Min. Meeting in ~15-20 Sek.).
- **Auto-Unmute:** Erkennt, ob das Headset-Mikrofon in Windows gemuted ist, und entstummt es automatisch.
- **Clipboard-Integration:** Fertiges Markdown-Transkript landet sofort in der Zwischenablage (`Strg + V` für OneNote, Chat oder Mail).
