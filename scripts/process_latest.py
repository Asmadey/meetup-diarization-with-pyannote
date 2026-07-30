#!/usr/bin/env python3
"""
process_latest.py — Complete Pipeline Orchestrator for Meeting Transcriber Skill.
1. Scans Meets/audio/ for unprocessed files.
2. Tracks processed files in skills/meeting-transcriber/реестр.md.
3. Transcribes & diarizes audio -> saves JSON to Meets/transcripts/.
4. Resolves speaker names via LLM (replacing SPEAKER_UNKNOWN).
5. Generates plain text follow-up -> saves TXT to Meets/followups/.
6. Updates skills/meeting-transcriber/реестр.md with clickable links to audio, transcript, and follow-up.
"""

import os
import sys
import json
import argparse
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MEETS_DIR = BASE_DIR / "Meets"
AUDIO_DIR = MEETS_DIR / "audio"
TRANSCRIPTS_DIR = MEETS_DIR / "transcripts"
FOLLOWUPS_DIR = MEETS_DIR / "followups"

REGISTRY_PATH = BASE_DIR / "skills" / "meeting-transcriber" / "реестр.md"

def ensure_directories():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    FOLLOWUPS_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_registry_file():
    if not REGISTRY_PATH.exists():
        header = """# Реестр обработанных аудиозаписей встреч

Файл автоматически обновляется навыком `meeting-transcriber`.

| Дата и время обработки | Исходный аудиофайл | Размер | Файл транскрипта (JSON) | Фоллоу-ап (TXT) | Статус |
|---|---|---|---|---|---|
"""
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            f.write(header)

def get_processed_filenames():
    if not REGISTRY_PATH.exists():
        return set()
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()
    processed = set()
    for line in lines:
        if line.startswith("|") and not line.startswith("| Дата") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                # Extract filename from markdown link [filename.mp3](...) or raw text
                audio_col = parts[1]
                if audio_col.startswith("[") and "]" in audio_col:
                    raw_name = audio_col[1:audio_col.index("]")]
                else:
                    raw_name = audio_col
                processed.add(raw_name)
    return processed

def get_latest_unprocessed_audio(specified_audio=None):
    if specified_audio:
        path = Path(specified_audio).resolve()
        if path.exists():
            return path
        else:
            print(f"Error: Specified audio file not found: {specified_audio}", file=sys.stderr)
            sys.exit(1)

    processed = get_processed_filenames()
    audio_extensions = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".webm", ".mp4"}
    
    files = []
    for item in AUDIO_DIR.iterdir():
        if item.is_file() and item.suffix.lower() in audio_extensions:
            if item.name not in processed:
                files.append(item)
                
    if not files:
        print("No new unprocessed audio files found in Meets/audio/", file=sys.stderr)
        return None

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]

def make_file_url(file_path: Path) -> str:
    path_str = str(file_path.resolve())
    return f"file://{urllib.parse.quote(path_str)}"

def record_in_registry(audio_path, transcript_path, followup_path, status="Успешно ✅"):
    init_registry_file()
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    size_mb = f"{audio_path.stat().st_size / (1024*1024):.1f} MB"
    
    audio_link = f"[{audio_path.name}]({make_file_url(audio_path)})"
    transcript_link = f"[{transcript_path.name}]({make_file_url(transcript_path)})"
    followup_link = f"[{followup_path.name}]({make_file_url(followup_path)})"
    
    row = f"| {now_str} | {audio_link} | {size_mb} | {transcript_link} | {followup_link} | {status} |\n"
    
    with open(REGISTRY_PATH, "a", encoding="utf-8") as f:
        f.write(row)
        
    print(f"Recorded execution in registry: {REGISTRY_PATH}")

def run_pipeline(audio_path, title=None):
    ensure_directories()
    
    stem = audio_path.stem
    transcript_json = TRANSCRIPTS_DIR / f"{stem}.json"
    followup_txt = FOLLOWUPS_DIR / f"{audio_path.stem}.txt"
    
    scripts_dir = Path(__file__).parent
    
    # Step 1: Transcribe & Diarize
    print(f"Step 1/3: Transcribing and diarizing {audio_path.name}...")
    cmd1 = [
        sys.executable, str(scripts_dir / "transcribe_diarize.py"),
        "--audio", str(audio_path),
        "--output", str(transcript_json)
    ]
    subprocess.run(cmd1, check=True)

    # Step 2: Resolve Speakers via LLM
    print(f"Step 2/3: Resolving speaker names in {transcript_json.name}...")
    cmd2 = [
        sys.executable, str(scripts_dir / "resolve_speakers.py"),
        "--input", str(transcript_json),
        "--output", str(transcript_json)
    ]
    subprocess.run(cmd2, check=True)

    # Step 3: Format Follow-up
    print(f"Step 3/3: Formatting follow-up to {followup_txt.name}...")
    doc_title = title or f"{stem} — {datetime.now().strftime('%d.%m.%Y')}"
    cmd3 = [
        sys.executable, str(scripts_dir / "format_followup.py"),
        "--input", str(transcript_json),
        "--title", doc_title,
        "--output", str(followup_txt)
    ]
    subprocess.run(cmd3, check=True)

    # Step 4: Record in Registry
    record_in_registry(audio_path, transcript_json, followup_txt)
    
    print("\n✅ Processing Complete!")
    print(f"📄 Transcript: {transcript_json}")
    print(f"📋 Follow-up: {followup_txt}")
    print(f"📊 Registry updated: {REGISTRY_PATH}")

def main():
    parser = argparse.ArgumentParser(description="Process latest audio file from Meets/audio/")
    parser.add_argument("--audio", help="Optional specific audio file path to process")
    parser.add_argument("--title", help="Optional title for the meeting follow-up")
    
    args = parser.parse_args()
    
    audio_file = get_latest_unprocessed_audio(args.audio)
    if not audio_file:
        sys.exit(0)
        
    run_pipeline(audio_file, args.title)

if __name__ == "__main__":
    main()
