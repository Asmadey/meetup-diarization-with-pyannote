#!/usr/bin/env python3
"""
format_followup.py — Formatter for meeting transcripts into strict plain-text follow-ups.
Uses Groq LLM (e.g. llama-3.3-70b-versatile) to produce high-quality executive summaries
strictly matching the structure of example.md (no Markdown syntax).
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are an executive assistant creating meeting follow-ups for a software engineering and product team.
Your task is to take a meeting transcript (with timeline and speaker information) and write a detailed, highly accurate, professional Follow-Up document.

CRITICAL FORMATTING RULES (STRICT PLAIN TEXT ONLY):
1. ABSOLUTELY NO MARKDOWN FORMATTING ALLOWED!
   - DO NOT use '#' headers.
   - DO NOT use '**bold**' or '*italic*'.
   - DO NOT use markdown list symbols like '*' or '-'.
   - Use simple blank lines and plain text numbering: '1.', '2.', '4.1)', '4.2)'.
2. Output language MUST be Russian (except technical terms like ClickHouse, RunPod, AWS, Recsys, Devops, API, Python which stay in English).

EXACT TEMPLATE TO FOLLOW:

[Название встречи] — [Дата]

Участники:

1. Имя1 (Организация/Команда)
2. Имя2 (Организация/Команда)

Обсудили:

1. [Тема 1] — [Подробная суть решения, кто за что отвечает, блокеры и договоренности].
2. [Тема 2] — [Подробности].
   2.1) [подпункт]
   2.2) [подпункт]
3. [Тема 3] — [Подробности].

Do not wrap your response in markdown code blocks like ```txt or ```markdown. Output raw plain text only.
"""

def get_groq_client(api_key: str = None):
    try:
        from groq import Groq
    except ImportError:
        return None
    
    key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("groq")
    if not key:
        return None
    return Groq(api_key=key)

def generate_followup_llm(client, transcript_data, title="Синк по встрече", model="llama-3.3-70b-versatile"):
    timeline = transcript_data.get("timeline", [])
    full_text = transcript_data.get("full_text", "")
    
    timeline_str = "\n".join([
        f"[{turn.get('speaker', 'SPEAKER')}] ({turn.get('start')}s - {turn.get('end')}s): {turn.get('text')}"
        for turn in timeline
    ])
    
    user_content = f"Meeting Title: {title}\n\nTranscript Timeline:\n{timeline_str}\n\nFull Text:\n{full_text}"
    
    print(f"Generating summary using Groq LLM model '{model}'...")
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        model=model,
        temperature=0.2,
    )
    
    output_text = response.choices[0].message.content
    if output_text.startswith("```"):
        output_text = "\n".join([line for line in output_text.splitlines() if not line.startswith("```")])
    return output_text.strip()

def generate_followup_fallback(transcript_data, title="Синк по встрече"):
    timeline = transcript_data.get("timeline", [])
    speakers = list(dict.fromkeys([turn["speaker"] for turn in timeline if turn.get("speaker")]))
    
    lines = []
    lines.append("")
    lines.append(f"{title}")
    lines.append("")
    lines.append("Участники:")
    lines.append("")
    
    for i, spk in enumerate(speakers, 1):
        lines.append(f"{i}. {spk}")
        
    lines.append("")
    lines.append("Обсудили:")
    lines.append("")
    
    current_text_block = []
    point_num = 1
    
    for turn in timeline:
        spk = turn.get("speaker", "SPEAKER")
        text = turn.get("text", "")
        current_text_block.append(f"{spk}: {text}")
        if len(" ".join(current_text_block)) > 400:
            lines.append(f"{point_num}. Обсуждение блока от {spk} — {' '.join(current_text_block)[:300]}...")
            point_num += 1
            current_text_block = []
            
    if current_text_block:
        lines.append(f"{point_num}. Завершающие вопросы встречи — {' '.join(current_text_block)[:300]}...")

    lines.append("")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Format raw transcript JSON into plain text meeting follow-up")
    parser.add_argument("--input", required=True, help="Path to input raw transcript JSON")
    parser.add_argument("--output", help="Path to save output follow-up text file")
    parser.add_argument("--title", default="Синк по встрече", help="Meeting title and date")
    parser.add_argument("--model", default="llama-3.3-70b-versatile", help="Groq LLM model")
    parser.add_argument("--groq-key", help="Groq API key")
    
    args = parser.parse_args()
    
    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"Error: Input JSON file not found at {input_path}", file=sys.stderr)
        sys.exit(1)
        
    with open(input_path, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)
        
    client = get_groq_client(args.groq_key)
    if client:
        try:
            followup_text = generate_followup_llm(client, transcript_data, args.title, args.model)
        except Exception as e:
            print(f"Warning: Groq LLM summary generation failed ({e}). Falling back to template generation.", file=sys.stderr)
            followup_text = generate_followup_fallback(transcript_data, args.title)
    else:
        print("Note: GROQ_API_KEY not found for LLM summarization. Using fallback template generation.", file=sys.stderr)
        followup_text = generate_followup_fallback(transcript_data, args.title)
    
    output_path = args.output
    if not output_path:
        output_path = str(Path(input_path).with_suffix(".txt"))
        
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(followup_text)
        
    print(f"Follow-up saved to: {output_path}")

if __name__ == "__main__":
    main()
