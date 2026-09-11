# Roadmap & Status: Meeting-Recorder Multi-Speaker Alignment

## Hintergrund (Ideenaustausch Yannick Bülter & David Hallmann, 10.09.2026)

Das Basissystem trennt Stereo-Hardwarekanäle:
- Kanal 1 = David (Mikrofon)
- Kanal 2 = Gegenseite (gesamter Loopback)

## Status: Umgesetzt (11.09.2026) ✅

In Kombination mit `teams-mcp`:
1. **Meeting-Metadaten & Sprecher-Timeline:**
   `teams-mcp` liefert eine `*.speakers.json` (Start- und Endzeitpunkte aktiver Sprecher über DOM-Polling sowie Spontan-Call 1:1 Matching).
2. **Post-Processing & Alignment in `transcribe_dual.py`:**
   - Robuste VAD-Clusterung via Silero VAD (verhindert das Verschmelzen von isolierten Einwürfen).
   - Segmente von Kanal 2 werden mit der DOM-Timeline abgeglichen (`align_segments_with_timeline`).
   - 1:1 Anrufe werden automatisch zu 100% dem Gesprächspartner zugeordnet.
   - Aufeinanderfolgende Segmente desselben Sprechers werden zu zusammenhängenden Absätzen gebündelt.
   - Resultat: Konkrete Sprechernamen (`**Stefan Maciolek:**`, `**Robert Lábas:**`, `**Niklas Brunnenkant:**`, `**Theys Schiller:**`).
3. **Signal-Datei (.stop) Shutdown:**
   PowerShell und Node-Hintergrundprozess kommunizieren über `$speakersFile.stop`, womit die Timeline vor dem Transkriptionsstart vollständig finalisiert wird.
