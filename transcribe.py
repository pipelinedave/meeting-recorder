import os
import sys
import glob
import json
import time
from pathlib import Path
from faster_whisper import WhisperModel

# Ensure NVIDIA CUDA libraries in venv are visible to CTranslate2
try:
    import nvidia
    nv_base = nvidia.__path__[0]
    extra_libs = [os.path.join(root, "lib") for root, dirs, files in os.walk(nv_base) if "lib" in dirs]
    os.environ["LD_LIBRARY_PATH"] = ":".join(extra_libs) + ":" + os.environ.get("LD_LIBRARY_PATH", "")
except Exception as e:
    pass

# Initial prompt gives Whisper domain context so it recognizes abbreviations and jargon
INITIAL_PROMPT = (
    "Transkript eines deutschsprachigen IT-, Beratungs- und Consulting-Meetings. "
    "Begriffe: d.velop, d.3, d.3one, d.ecs, IDP, ONAVO, FIT-Connect, LeiKa, BPMN, "
    "CMIS, REST API, JSON, SQLite, Docker, Windows, David, Mathis, Pierre, Ticket, DL-Beleg."
)

def transcribe_audio(audio_path, output_dir=None, language="de"):
    audio_path = Path(audio_path)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}", file=sys.stderr)
        return None

    if output_dir is None:
        output_dir = audio_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Initializing Faster-Whisper (large-v3-turbo) on GPU...")
    t0 = time.time()
    model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
    init_time = time.time() - t0
    print(f"[*] Model loaded in {init_time:.2f}s")

    print(f"[*] Transcribing: {audio_path.name}...")
    t1 = time.time()
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        initial_prompt=INITIAL_PROMPT,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        beam_size=5,
        repetition_penalty=1.2,
        no_speech_threshold=0.6
    )

    results = []
    formatted_lines = []
    meeting_title = audio_path.parent.name if audio_path.name.startswith("audio") else audio_path.stem
    formatted_lines.append(f"# Transkript: {meeting_title}")
    formatted_lines.append(f"- **Sprache:** {info.language} (Erkennung: {info.language_probability * 100:.1f}%)")
    formatted_lines.append(f"- **Audiodauer:** {int(info.duration // 60)}m {int(info.duration % 60)}s ({info.duration:.1f}s)")
    formatted_lines.append("\n---\n")

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        
        seg_duration = seg.end - seg.start
        # Filter hallucinated ending phrases like "Vielen Dank." on silence
        if seg_duration > 15 and text in ["Vielen Dank.", "Untertitelung aufgrund der Amara.org-Community", "Untertitel im Auftrag des ZDF", "Danke fürs Zuschauen!"]:
            continue

        m_start = int(seg.start // 60)
        s_start = int(seg.start % 60)
        m_end = int(seg.end // 60)
        s_end = int(seg.end % 60)
        time_str = f"[{m_start:02d}:{s_start:02d} - {m_end:02d}:{s_end:02d}]"
        
        results.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": text
        })
        formatted_lines.append(f"**{time_str}**: {text}\n")

    trans_time = time.time() - t1
    speedup = info.duration / max(0.1, trans_time)
    print(f"[*] Transcription completed in {trans_time:.2f}s (Speedup: {speedup:.1f}x real-time)")

    # Output Markdown
    md_file = output_dir / f"transkript_whisper_gpu.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(formatted_lines))

    # Output JSON
    json_file = output_dir / f"transkript_whisper_gpu.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"info": {"language": info.language, "duration": info.duration}, "segments": results}, f, ensure_ascii=False, indent=2)

    print(f"[+] Markdown gespeichert: {md_file}")
    print(f"[+] JSON gespeichert: {json_file}")
    return md_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <path_to_audio_file> [output_dir]")
        sys.exit(1)
    
    audio = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    transcribe_audio(audio, out)
