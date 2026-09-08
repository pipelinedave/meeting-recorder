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
    "CMIS, REST API, JSON, SQLite, Docker, Windows, David, Mathis, Pierre, Ticket, DL-Beleg."
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

def process_meeting(audio_file_path, output_dir=None):
    audio_path = Path(audio_file_path)
    if not audio_path.exists():
        print(f"File not found: {audio_path}", file=sys.stderr)
        return

    if output_dir is None:
        output_dir = audio_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

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
    lines.append(f"- **Sprechertrennung:** {'Aktiv (David vs. Gegenseite via Hardware-Tracks)' if is_stereo else 'Mono'}")
    lines.append("\n---\n")

    current_speaker = None
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
        json.dump({"duration": total_duration, "segments": all_segments}, f, ensure_ascii=False, indent=2)

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
        print("Usage: python transcribe_dual.py <path_to_audio_wav> [output_dir]")
        sys.exit(1)
    
    audio = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    process_meeting(audio, out)
