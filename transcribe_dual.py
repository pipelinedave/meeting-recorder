import os
import sys
import json
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

# Ensure NVIDIA CUDA libraries in venv are visible to CTranslate2
try:
    import nvidia
    nv_base = nvidia.__path__[0]
    extra_libs = [os.path.join(root, "lib") for root, dirs, files in os.walk(nv_base) if "lib" in dirs]
    os.environ["LD_LIBRARY_PATH"] = ":".join(extra_libs) + ":" + os.environ.get("LD_LIBRARY_PATH", "")
except Exception as e:
    pass

INITIAL_PROMPT = (
    "Transkript eines deutschsprachigen IT-, Beratungs- und Consulting-Meetings. "
    "Begriffe: d.velop, d.3, d.3one, d.ecs, IDP, ONAVO, FIT-Connect, LeiKa, BPMN, "
    "CMIS, REST API, JSON, SQLite, Docker, Windows, David, Mathis, Pierre, Yannick, Ticket, DL-Beleg."
)

def format_timestamp(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def transcribe_channel(model, audio_data, sample_rate, speaker_label):
    print(f"[*] Transkribiere Spur: {speaker_label}...")
    segments, info = model.transcribe(
        audio_data,
        language="de",
        initial_prompt=INITIAL_PROMPT,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
        beam_size=5,
        repetition_penalty=1.2,
        no_speech_threshold=0.6
    )
    
    results = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        seg_duration = seg.end - seg.start
        if seg_duration > 15 and text in ["Vielen Dank.", "Untertitelung aufgrund der Amara.org-Community", "Danke fürs Zuschauen!"]:
            continue

        results.append({
            "speaker": speaker_label,
            "start": seg.start,
            "end": seg.end,
            "text": text
        })
    return results

def load_speaker_timeline(speakers_path):
    """
    Loads and parses *.speakers.json exported by teams-mcp.
    """
    if not speakers_path:
        return None
    p = Path(speakers_path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"[!] Warnung: Konnte Sprecher-Timeline nicht laden: {e}", file=sys.stderr)
        return None

def align_segments_with_timeline(others_segments, timeline_data, min_overlap_ratio=0.35):
    """
    Matches transcribed Channel 2 segments against the Teams DOM active speaker intervals.
    Replaces generic 'Gegenseite' with real speaker names when there is significant overlap.
    """
    if not timeline_data or not timeline_data.get("intervals"):
        return others_segments

    intervals = timeline_data["intervals"]
    aligned = []

    for seg in others_segments:
        seg_start = seg["start"]
        seg_end = seg["end"]
        seg_duration = max(0.1, seg_end - seg_start)

        # Calculate overlap duration with each speaker
        speaker_overlaps = {}
        for item in intervals:
            spk = item.get("speaker", "").strip()
            if not spk:
                continue
            int_start = float(item.get("start_offset_sec", 0.0))
            int_end = float(item.get("end_offset_sec", 0.0))

            overlap = max(0.0, min(seg_end, int_end) - max(seg_start, int_start))
            if overlap > 0:
                speaker_overlaps[spk] = speaker_overlaps.get(spk, 0.0) + overlap

        if not speaker_overlaps:
            aligned.append(seg)
            continue

        # Sort speakers by overlap descending
        sorted_speakers = sorted(speaker_overlaps.items(), key=lambda x: x[1], reverse=True)
        top_speaker, top_overlap = sorted_speakers[0]
        top_ratio = top_overlap / seg_duration

        if top_ratio >= min_overlap_ratio:
            if len(sorted_speakers) > 1:
                sec_speaker, sec_overlap = sorted_speakers[1]
                if (sec_overlap / seg_duration) >= 0.30 and sec_speaker != top_speaker:
                    chosen_speaker = f"{top_speaker} & {sec_speaker}"
                else:
                    chosen_speaker = top_speaker
            else:
                chosen_speaker = top_speaker

            new_seg = dict(seg)
            new_seg["speaker"] = chosen_speaker
            new_seg["confidence"] = "teams_dom_aligned"
            aligned.append(new_seg)
        else:
            aligned.append(seg)

    return aligned

def process_meeting(audio_file_path, output_dir=None, speakers_file_path=None):
    audio_path = Path(audio_file_path)
    if not audio_path.exists():
        print(f"File not found: {audio_path}", file=sys.stderr)
        return None

    if output_dir is None:
        output_dir = audio_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Search for associated *.speakers.json if not explicitly provided
    if speakers_file_path is None:
        candidate = audio_path.with_suffix(".speakers.json")
        if candidate.exists():
            speakers_file_path = candidate
        else:
            candidate2 = audio_path.parent / f"{audio_path.stem}.speakers.json"
            if candidate2.exists():
                speakers_file_path = candidate2

    timeline = load_speaker_timeline(speakers_file_path)
    if timeline:
        spk_list = timeline.get("speakers", [])
        int_count = len(timeline.get("intervals", []))
        print(f"[✓] Teams Sprecher-Timeline gefunden ({int_count} Intervalle, Sprecher: {', '.join(spk_list) if spk_list else 'keine'})")

    print(f"[*] Lese Audio: {audio_path.name}...")
    audio, sr = sf.read(str(audio_path), dtype="float32")

    is_stereo = (audio.ndim == 2 and audio.shape[1] >= 2)
    
    print(f"[*] Initialisiere Faster-Whisper (large-v3-turbo) auf GPU...")
    t0 = time.time()
    model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
    print(f"[*] GPU Modell geladen in {time.time() - t0:.2f}s")

    all_segments = []
    total_duration = audio.shape[0] / sr

    if is_stereo:
        print("[✓] Stereo-Signal erkannt: Trenne Kanal 1 (David) und Kanal 2 (Gegenseite/Teams)...")
        # Left channel = David (Mic)
        david_audio = audio[:, 0]
        # Right channel = Others (Loopback)
        others_audio = audio[:, 1]

        t_trans = time.time()
        segs_david = transcribe_channel(model, david_audio, sr, "David")
        segs_others = transcribe_channel(model, others_audio, sr, "Gegenseite")
        
        # Align others with Teams DOM timeline if available
        if timeline:
            print("[*] Gleiche Gegenseite-Segmente mit Teams Sprecher-Timeline ab...")
            segs_others = align_segments_with_timeline(segs_others, timeline)
            matched_count = sum(1 for s in segs_others if s.get("confidence") == "teams_dom_aligned")
            print(f"[✓] {matched_count} von {len(segs_others)} Gegenseite-Segmenten erfolgreich konkreten Sprechern zugeordnet.")

        all_segments = segs_david + segs_others
        # Sort chronologically by start time
        all_segments.sort(key=lambda x: x["start"])
        trans_duration = time.time() - t_trans
    else:
        print("[!] Mono-Signal erkannt (keine getrennte Spur)...")
        mono_audio = audio[:, 0] if audio.ndim == 2 else audio
        t_trans = time.time()
        all_segments = transcribe_channel(model, mono_audio, sr, "Sprecher")
        trans_duration = time.time() - t_trans

    speedup = total_duration / max(0.1, trans_duration)
    print(f"[*] Transkription abgeschlossen in {trans_duration:.2f}s (Speedup: {speedup:.1f}x)")

    # Build Markdown Output
    meeting_title = audio_path.stem
    lines = []
    lines.append(f"# Meeting Transkript: {meeting_title}")
    lines.append(f"- **Dauer:** {int(total_duration // 60)}m {int(total_duration % 60)}s ({total_duration:.1f}s)")

    unique_speakers = []
    seen = set()
    for s in all_segments:
        spk = s["speaker"]
        if spk not in seen:
            seen.add(spk)
            unique_speakers.append(spk)

    if timeline and len(unique_speakers) > 1:
        lines.append(f"- **Erkannte Sprecher:** {', '.join(unique_speakers)}")
    else:
        lines.append(f"- **Sprechertrennung:** {'Aktiv (David vs. Gegenseite via Hardware-Tracks)' if is_stereo else 'Mono'}")
    lines.append("\n---\n")

    for seg in all_segments:
        time_tag = f"[{format_timestamp(seg['start'])} - {format_timestamp(seg['end'])}]"
        speaker = seg['speaker']
        text = seg['text']

        if speaker == "David":
            speaker_badge = "**David:**"
        elif speaker == "Gegenseite":
            speaker_badge = "**Gegenseite / Kunde:**"
        else:
            speaker_badge = f"**{speaker}:**"

        lines.append(f"{time_tag} {speaker_badge} {text}\n")

    md_file = output_dir / f"{meeting_title}_transkript.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    json_file = output_dir / f"{meeting_title}_transkript.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "duration": total_duration,
            "speakers": unique_speakers,
            "segments": all_segments
        }, f, ensure_ascii=False, indent=2)

    print(f"[✓] Transkript gespeichert: {md_file}")
    
    # Copy to Windows Clipboard (UTF-16LE required for Windows clip.exe to handle umlauts correctly)
    try:
        os.system(f'cat "{md_file}" | iconv -f UTF-8 -t UTF-16LE | /mnt/c/Windows/System32/clip.exe')
        print(f"[✓] Transkript automatisch in die Windows-Zwischenablage kopiert!")
    except Exception as e:
        print(f"Clipboard copy error: {e}")

    return md_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe_dual.py <path_to_audio_wav> [output_dir] [speakers_json]")
        sys.exit(1)
    
    audio = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    spk = sys.argv[3] if len(sys.argv) > 3 else None
    process_meeting(audio, out, spk)
