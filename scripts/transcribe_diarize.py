#!/usr/bin/env python3
"""
transcribe_diarize.py — Audio Transcription & Diarization Script
Uses Groq Whisper API (whisper-large-v3 / whisper-large-v3-turbo) for speech recognition
and pyannote.audio for speaker diarization.
Supports automatic audio chunking via ffmpeg for files > 24 MB.
"""

import os
import sys
import json
import shutil
import tempfile
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

MAX_FILE_SIZE_BYTES = 24 * 1024 * 1024  # 24 MB limit for Groq API

def get_groq_client(api_key: str = None):
    try:
        from groq import Groq
    except ImportError:
        print("Error: 'groq' package not installed. Run: pip install groq", file=sys.stderr)
        sys.exit(1)
        
    key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("groq")
    if not key:
        print("Error: GROQ_API_KEY is missing. Pass --groq-key or set GROQ_API_KEY / groq in environment/.env", file=sys.stderr)
        sys.exit(1)
        
    return Groq(api_key=key)

def split_audio_ffmpeg(audio_path: str, chunk_duration_sec: int = 600):
    temp_dir = tempfile.mkdtemp(prefix="groq_chunks_")
    output_pattern = os.path.join(temp_dir, "chunk_%03d.mp3")
    
    cmd = [
        "ffmpeg", "-y", "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(chunk_duration_sec),
        "-c", "copy",
        output_pattern
    ]
    
    print(f"Splitting audio ({os.path.getsize(audio_path)/(1024*1024):.1f} MB) into chunks with ffmpeg...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if res.returncode != 0:
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-f", "segment",
            "-segment_time", str(chunk_duration_sec),
            "-ar", "16000", "-ac", "1", "-b:a", "64k",
            output_pattern
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(f"Error splitting audio with ffmpeg: {res.stderr}", file=sys.stderr)
            sys.exit(1)

    chunk_files = sorted([os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith("chunk_") and f.endswith(".mp3")])
    
    chunks_with_offsets = []
    for i, c_path in enumerate(chunk_files):
        offset = i * chunk_duration_sec
        chunks_with_offsets.append((c_path, float(offset)))
        
    print(f"Split audio into {len(chunks_with_offsets)} chunks.")
    return chunks_with_offsets, temp_dir

def transcribe_single_chunk(client, chunk_path: str, model: str, language: str, time_offset: float = 0.0):
    with open(chunk_path, "rb") as file:
        kwargs = {
            "file": (os.path.basename(chunk_path), file.read()),
            "model": model,
            "temperature": 0,
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language

        transcription = client.audio.transcriptions.create(**kwargs)
    
    result_dict = transcription.model_dump() if hasattr(transcription, "model_dump") else dict(transcription)
    
    segments = result_dict.get("segments", [])
    for seg in segments:
        seg["start"] += time_offset
        seg["end"] += time_offset
        
    return segments, result_dict.get("text", "")

def transcribe_audio_groq(client, audio_path: str, model: str = "whisper-large-v3-turbo", language: str = "ru"):
    file_size = os.path.getsize(audio_path)
    
    if file_size <= MAX_FILE_SIZE_BYTES:
        print(f"Transcribing audio ({file_size/(1024*1024):.1f} MB) with Groq model '{model}'...")
        segments, full_text = transcribe_single_chunk(client, audio_path, model, language, 0.0)
        return {"segments": segments, "text": full_text}
    else:
        print(f"Audio file is larger than 24MB limit ({file_size/(1024*1024):.1f} MB). Processing in chunks...")
        chunks, temp_dir = split_audio_ffmpeg(audio_path, chunk_duration_sec=600)
        all_segments = []
        full_text_parts = []
        
        try:
            for i, (chunk_path, offset_sec) in enumerate(chunks, 1):
                print(f"Transcribing chunk {i}/{len(chunks)} (offset: {offset_sec:.1f}s, size: {os.path.getsize(chunk_path)/(1024*1024):.1f} MB)...")
                seg, text = transcribe_single_chunk(client, chunk_path, model, language, offset_sec)
                all_segments.extend(seg)
                full_text_parts.append(text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        return {"segments": all_segments, "text": " ".join(full_text_parts)}

def diarize_audio_pyannote(audio_path: str, hf_token: str = None):
    token = hf_token or os.getenv("HF_TOKEN") or os.getenv("HuggingFace")
    if not token:
        print("Warning: HF_TOKEN / HuggingFace key not found. Skipping pyannote.audio diarization.", file=sys.stderr)
        return None

    try:
        from pyannote.audio import Pipeline
        import torch
    except ImportError as e:
        print(f"Warning: pyannote.audio or torch not installed properly ({e}). Skipping diarization.", file=sys.stderr)
        return None

    try:
        print("Running speaker diarization with pyannote.audio...")
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=token
            )
        except TypeError:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=token
            )
        
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
        elif torch.backends.mps.is_available():
            pipeline.to(torch.device("mps"))

        diarization = pipeline(audio_path)
        
        speaker_turns = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_turns.append({
                "start": round(turn.start, 2),
                "end": round(turn.end, 2),
                "speaker": speaker
            })
        return speaker_turns
    except Exception as err:
        print(f"Warning: Failed to run pyannote diarization: {err}", file=sys.stderr)
        return None

def merge_transcription_and_diarization(segments, speaker_turns):
    if not speaker_turns:
        return [{
            "speaker": "SPEAKER_UNKNOWN",
            "start": round(seg.get("start", 0.0), 2),
            "end": round(seg.get("end", 0.0), 2),
            "text": seg.get("text", "").strip()
        } for seg in segments]

    merged = []
    for seg in segments:
        s_start = seg.get("start", 0.0)
        s_end = seg.get("end", 0.0)
        text = seg.get("text", "").strip()
        if not text:
            continue

        best_speaker = "SPEAKER_UNKNOWN"
        max_overlap = 0.0

        for turn in speaker_turns:
            t_start = turn["start"]
            t_end = turn["end"]
            
            overlap_start = max(s_start, t_start)
            overlap_end = min(s_end, t_end)
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = turn["speaker"]

        merged.append({
            "speaker": best_speaker,
            "start": round(s_start, 2),
            "end": round(s_end, 2),
            "text": text
        })

    return merged

def main():
    parser = argparse.ArgumentParser(description="Transcribe and diarize meeting audio")
    parser.add_argument("--audio", required=True, help="Path to input audio file (.m4a, .mp3, .wav)")
    parser.add_argument("--output", help="Path to save output raw transcript JSON")
    parser.add_argument("--model", default="whisper-large-v3-turbo", choices=["whisper-large-v3", "whisper-large-v3-turbo"], help="Groq Whisper model")
    parser.add_argument("--language", default="ru", help="Audio language ISO code (default: ru)")
    parser.add_argument("--groq-key", help="Groq API key")
    parser.add_argument("--hf-token", help="HuggingFace token for pyannote.audio")
    
    args = parser.parse_args()

    audio_path = os.path.abspath(args.audio)
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found at {audio_path}", file=sys.stderr)
        sys.exit(1)

    client = get_groq_client(args.groq_key)
    groq_resp = transcribe_audio_groq(client, audio_path, args.model, args.language)

    segments = groq_resp.get("segments", [])
    full_text = groq_resp.get("text", "")

    speaker_turns = diarize_audio_pyannote(audio_path, args.hf_token)
    timeline = merge_transcription_and_diarization(segments, speaker_turns)

    result_data = {
        "audio_file": audio_path,
        "model": args.model,
        "full_text": full_text,
        "timeline": timeline
    }

    output_path = args.output
    if not output_path:
        output_path = str(Path(audio_path).with_suffix(".json"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"Done! Raw transcription and diarization saved to: {output_path}")

if __name__ == "__main__":
    main()
