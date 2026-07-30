---
name: meeting-transcriber
description: Transcribe meeting audio recordings using Groq Whisper API, pyannote.audio diarization, and LLM speaker resolution to produce structured plain-text meeting follow-ups and maintain an execution registry.
---

# Meeting Transcriber Skill (Groq Whisper + pyannote.audio + LLM Speaker Resolver)

Данный навык автоматически находит новые аудиозаписи встреч в папке `Meets/audio/`, выполняет расшифровку, определяет реальные имена участников (например, "Оскар Хартманн", "Альмир"), сопоставляет реплики, ведает реестр в `реестр.md` и сохраняет итоговые протоколы в `Meets/followups/` строго по образцу `example.md` (без символов разметки Markdown).

---

## 🚀 Автоматический запуск

### 1. Единый запуск обработки последнего аудиофайла

Запустите автоматическую обработку самого свежего непереработанного аудиофайла из `Meets/audio/`:

```bash
python3 skills/meeting-transcriber/scripts/process_latest.py
```

Или укажите конкретный файл вручную:

```bash
python3 skills/meeting-transcriber/scripts/process_latest.py --audio Meets/audio/meeting.m4a --title "Синк по продукту — 30.07.2026"
```

---

## 📁 Карта каталогов и файлов

- **Входящие аудиофайлы**: [Meets/audio/](file:///Users/asmadey/AntiGravity/JGGL/Meets/audio)
- **Сырые транскрипты с именами спикеров**: [Meets/transcripts/](file:///Users/asmadey/AntiGravity/JGGL/Meets/transcripts)
- **Итоговые чистые текстовые фоллоу-апы**: [Meets/followups/](file:///Users/asmadey/AntiGravity/JGGL/Meets/followups) (по шаблону [example.md](file:///Users/asmadey/AntiGravity/JGGL/Meets/followups/example.md))
- **Реестр обработанных файлов**: [skills/meeting-transcriber/реестр.md](file:///Users/asmadey/AntiGravity/JGGL/skills/meeting-transcriber/реестр.md)

---

## 👥 Определение спикеров (LLM Speaker Resolution)

1. Скрипт `transcribe_diarize.py` разбивает аудио на фрагменты и транскрибирует через Groq Whisper.
2. Скрипт `resolve_speakers.py` с помощью Groq LLM (`llama-3.3-70b-versatile`):
   - Определяет реальные имена участников встречи (например, *Альмир*, *Оскар Хартманн*).
   - Заменяет все `SPEAKER_UNKNOWN` на реальные имена спикеров в поле `"speaker"` внутри JSON-файла транскрипта.
   - При отсутствии точных имен использует последовательную нумерацию `SPEAKER_1`, `SPEAKER_2` и т.д.

---

## 📊 Реестр обработанных файлов (`реестр.md`)

Реестр хранится в [skills/meeting-transcriber/реестр.md](file:///Users/asmadey/AntiGravity/JGGL/skills/meeting-transcriber/реестр.md) и автоматически пополняется после каждого успешного прогона:

| Дата и время обработки | Имя файла аудио | Длительность / Размер | Файл транскрипта (JSON) | Фоллоу-ап (TXT) | Статус |
|---|---|---|---|---|---|
