#!/usr/bin/env python3
"""
transcribe_diarize.py — Audio Transcription & Diarization Script
Uses Groq Whisper API (whisper-large-v3 / whisper-large-v3-turbo) for speech recognition
and pyannote.audio for speaker diarization.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

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

def transcribe_audio_groq(client, audio_path: str, model: str = "whisper-large-v3-turbo", language: str = "ru"):
    print(f"Transcribing audio with Groq model '{model}'...")
    with open(audio_path, "rb") as file:
        kwargs = {
            "file": (os.path.basename(audio_path), file.read()),
            "model": model,
            "temperature": 0,
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language

        transcription = client.audio.transcriptions.create(**kwargs)
    
    result_dict = transcription.model_dump() if hasattr(transcription, "model_dump") else dict(transcription)
    return result_dict

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
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=token
        )
        
        # Use Apple Silicon MPS or CUDA if available
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
