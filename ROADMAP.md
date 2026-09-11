# Roadmap: Meeting-Recorder Multi-Speaker Alignment

## Hintergrund (Ideenaustausch Yannick Bülter & David Hallmann, 10.09.2026)

Das aktuelle Setup trennt Stereo-Hardwarekanäle:
- Kanal 1 = David
- Kanal 2 = Gegenseite (gesamter Loopback)

## Ziel: Echte Sprechernamen für die Gegenseite ohne Cloud-Diarisierung

In Kombination mit `teams-mcp`:
1. **Meeting-Metadaten & Sprecher-Timeline:**
   `teams-mcp` liefert optional eine `*.speakers.json` (Start- und Endzeitpunkte, an denen bestimmte Personen im Teams-Browserclient gesprochen haben, ermittelt über die grünen Sprecherrahmen im DOM).
2. **Post-Processing in `transcribe_dual.py`:**
   - Wenn `*.speakers.json` für die Aufnahme vorliegt, mappt `transcribe_dual.py` die Segmente von Kanal 2 auf die Zeitbereiche der aktiven Sprecher.
   - Resultat: Statt generischem `**Gegenseite / Kunde:**` steht im Markdown-Transkript automatisch z.B. `**Yannick Bülter:**`, `**Pierre:**`, `**Kunde X:**`.
   - Bei Überschneidungen oder fehlendem DOM-Match greift der bewährte Fallback `Gegenseite` / Diarisierung.
