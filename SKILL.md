---
name: meeting-transcriber
description: Transcribe meeting audio recordings using Groq Whisper API and pyannote.audio diarization to produce structured plain-text meeting follow-ups (no markdown formatting).
---

# Meeting Transcriber Skill (Groq Whisper + pyannote.audio Diarization)

Данный навык позволяет автоматически расшифровывать записи рабочих встреч (`.m4a`, `.mp3`, `.wav`), проводить диаризацию (определение того, кто какую фразу сказал) и генерировать итоговый структурированный текстовый фоллоу-ап строго в формате `example.md` (без символов Markdown-разметки типа `#`, `**`, `*`).

---

## 🚀 Быстрый запуск

### 1. Настройка окружения и переменных

Убедитесь, что в окружении или файле `.env` задан ключ API Groq:
```env
GROQ_API_KEY=gsk_...
```
Если используется диаризация через `pyannote.audio`, также требуется токен HuggingFace (после принятия пользовательского соглашения на странице `pyannote/speaker-diarization-3.1`):
```env
HF_TOKEN=hf_...
```

### 2. Команда расшифровки и сборки фоллоу-апа

Запустите обработку файла аудиозаписи:
```bash
python3 skills/meeting-transcriber/scripts/transcribe_diarize.py --audio /path/to/audio.m4a --output /path/to/meeting_raw.json
```

А затем сгенерируйте итоговый `.txt` документ отчета:
```bash
python3 skills/meeting-transcriber/scripts/format_followup.py --input /path/to/meeting_raw.json --title "Синк по направлению ..." --output /path/to/followup.txt
```

---

## 📋 Формат выходящего документа

Выходящий документ **ОБЯЗАН** быть в строго чистом текстовом формате (plain text `.txt` или `.md` без элементов разметки Markdown):

```
Синк по направлению Recsys — 29.07.2026

Участники:

1. Бахридин (JGGL)
2. Иван (JGGL)
...

Обсудили:

1. Тема первой договоренности — детали темы.
2. Тема второй договоренности — детали темы.
   2.1) подпункт
   2.2) подпункт
...
```

### Правила форматирования:
- Никаких `#`, `##`, `###` заголовков Markdown.
- Никакой жирности `**текст**` или курсива `*текст*`.
- Точное следование пустой строке между разделами.
- Структурированные пронумерованные списки с подпунктами (1., 2., 2.1), 2.2)).
