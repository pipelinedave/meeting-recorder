import os
import sys
import time
import json
from pathlib import Path

WATCH_DIR = Path("/mnt/c/Users/dhallmann/Music/meetily-recordings")
PROCESSED_FILE = Path("/home/dhallmann/projects/meeting-recorder/.processed_meetings.json")

def load_processed():
    if PROCESSED_FILE.exists():
        try:
            with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_processed(processed_set):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed_set), f, indent=2)

def check_and_transcribe():
    processed = load_processed()
    if not WATCH_DIR.exists():
        print("Watch directory does not exist:", WATCH_DIR)
        return

    # Scan meeting folders
    folders = [p for p in WATCH_DIR.iterdir() if p.is_dir() and (p / "audio.mp4").exists()]
    folders.sort(key=lambda p: p.stat().st_mtime)

    for folder in folders:
        folder_id = folder.name
        audio_path = folder / "audio.mp4"
        meta_path = folder / "metadata.json"
        
        if folder_id in processed:
            continue

        is_completed = False
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("status") == "completed":
                        is_completed = True
            except Exception:
                pass
        
        # Alternatively check if audio file stopped growing (>20 seconds)
        if not is_completed:
            age = time.time() - audio_path.stat().st_mtime
            if age > 20:
                is_completed = True

        if is_completed:
            print(f"[!] New completed recording found: {folder_id}")
            out_file = folder / "transkript_whisper_gpu.md"
            if not out_file.exists():
                print(f"[*] Starting GPU transcription for {folder_id}...")
                cmd = f'/home/dhallmann/projects/meeting-recorder/run_transcribe.sh "{audio_path}" "{folder}"'
                os.system(cmd)
            
            # Copy to Windows Clipboard via clip.exe
            if out_file.exists():
                try:
                    os.system(f'cat "{out_file}" | iconv -f UTF-8 -t UTF-16LE | /mnt/c/Windows/System32/clip.exe')
                    print(f"[+] Transkript erfolgreich in die Windows-Zwischenablage kopiert!")
                except Exception as e:
                    print(f"Clipboard copy error: {e}")

            processed.add(folder_id)
            save_processed(processed)

if __name__ == "__main__":
    check_and_transcribe()
