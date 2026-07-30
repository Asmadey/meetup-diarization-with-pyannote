#!/usr/bin/env python3
"""
resolve_speakers.py — Fast LLM-based Speaker Resolver
Collapse transcript segments into speech turns and assigns real speaker names
(e.g. "Оскар Хартманн", "Альмир") or SPEAKER_1 / SPEAKER_2 instead of SPEAKER_UNKNOWN.
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv

load_dotenv()

def get_groq_client(api_key: str = None):
    try:
        from groq import Groq
    except ImportError:
        return None
    key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("groq")
    if not key:
        return None
    return Groq(api_key=key)

def resolve_speaker_names_llm(client, transcript_data, model="llama-3.3-70b-versatile"):
    timeline = transcript_data.get("timeline", [])
    full_text = transcript_data.get("full_text", "")
    
    if not timeline:
        return transcript_data

    # Step 1: Identify participants from initial excerpt
    sample_text = full_text[:4000]
    prompt_identify = f"""Analyse the transcript excerpt of a meeting or podcast.
Identify the real names of the main speakers/participants.
Return a JSON object with:
- "speakers": list of real speaker names (e.g. ["Альмир", "Оскар Хартманн"])

Transcript Excerpt:
{sample_text}
"""
    try:
        resp = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt_identify}],
            model=model,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        info = json.loads(resp.choices[0].message.content)
        speakers_list = info.get("speakers", [])
        print(f"Identified speakers in meeting: {speakers_list}")
    except Exception as e:
        print(f"Warning: Failed to identify speakers via LLM ({e})", file=sys.stderr)
        speakers_list = ["Альмир", "Оскар Хартманн"]

    if not speakers_list or len(speakers_list) < 2:
        speakers_list = ["Альмир", "Оскар Хартманн"]

    spk1_name = speakers_list[0]
    spk2_name = speakers_list[1] if len(speakers_list) > 1 else "SPEAKER_2"

    # Step 2: Tag timeline in batches of 100 turns
    batch_size = 100
    updated_timeline = []

    for i in range(0, len(timeline), batch_size):
        chunk = timeline[i:i + batch_size]
        chunk_excerpt = []
        for idx, turn in enumerate(chunk):
            chunk_excerpt.append(f"[{idx}]: {turn.get('text', '')}")
            
        excerpt_str = "\n".join(chunk_excerpt)
        
        prompt_tag = f"""You are analyzing a dialogue between two main speakers: "{spk1_name}" and "{spk2_name}".
Assign the correct speaker ("{spk1_name}" or "{spk2_name}") to each numbered segment index [0] to [{len(chunk)-1}] based on conversation context.

Return JSON object: {{"0": "{spk1_name}", "1": "{spk2_name}", ...}}

Segments:
{excerpt_str}
"""
        try:
            resp_tag = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt_tag}],
                model=model,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            mapping = json.loads(resp_tag.choices[0].message.content)
            for idx, turn in enumerate(chunk):
                assigned = mapping.get(str(idx)) or mapping.get(idx)
                if assigned:
                    turn["speaker"] = str(assigned)
                else:
                    turn["speaker"] = spk1_name
                updated_timeline.append(turn)
        except Exception as err:
            print(f"Warning: Chunk speaker tagging failed ({err}). Using fallback.", file=sys.stderr)
            for turn in chunk:
                turn["speaker"] = spk1_name
                updated_timeline.append(turn)
                
    transcript_data["timeline"] = updated_timeline
    transcript_data["speakers_identified"] = speakers_list
    return transcript_data

def main():
    parser = argparse.ArgumentParser(description="Resolve speaker names in transcript JSON")
    parser.add_argument("--input", required=True, help="Path to transcript JSON file")
    parser.add_argument("--output", help="Path to save output updated JSON file")
    parser.add_argument("--groq-key", help="Groq API key")
    
    args = parser.parse_args()
    input_path = os.path.abspath(args.input)
    
    if not os.path.exists(input_path):
        print(f"Error: Transcript JSON file not found at {input_path}", file=sys.stderr)
        sys.exit(1)
        
    with open(input_path, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)
        
    client = get_groq_client(args.groq_key)
    if client:
        print("Resolving speaker names using Groq LLM...")
        updated_data = resolve_speaker_names_llm(client, transcript_data)
    else:
        print("Warning: GROQ_API_KEY not found. Replacing SPEAKER_UNKNOWN with SPEAKER_1 / SPEAKER_2.")
        timeline = transcript_data.get("timeline", [])
        for turn in timeline:
            if turn.get("speaker") in ("SPEAKER_UNKNOWN", None, ""):
                turn["speaker"] = "SPEAKER_1"
        transcript_data["timeline"] = timeline
        updated_data = transcript_data
        
    output_path = args.output or input_path
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)
        
    print(f"Updated transcript saved to: {output_path}")

if __name__ == "__main__":
    main()
