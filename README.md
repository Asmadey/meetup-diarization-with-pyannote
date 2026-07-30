# Meetup Transcribe & Diarization with pyannote & Groq

Автоматизированный инструмент и AI-скилл для **расшифровки аудиозаписей рабочих встреч**, **диаризации спикеров (кто что говорил)** с помощью `pyannote.audio` и **создания фоллоу-апов созвонов** в чистом текстовом формате без разметки Markdown.

---

## 🎯 Ключевые возможности

- ⚡ **Высокоскоростная распознавание речи**: Использование Groq API (`whisper-large-v3-turbo` / `whisper-large-v3`).
- 🗣 **Диаризация спикеров**: Определение временных отрезков речи каждого участника встречи с помощью нейросети `pyannote.audio`.
- 📋 **Строго чистый текстовый отчет**: Генерация результатов в формате `txt` / `md` (без символов `#`, `**`, `*`, `_`), полностью соответствующая профессиональным протоколам встреч.
- 🤖 **Интеграция с AI-агентами**: Наличие готовой спецификации `SKILL.md` для работы в Antigravity, Claude Code и других агентских средах.

---

## 🛠 Архитектура работы

```
[Аудиозапись (.m4a/.mp3)]
       │
       ├──► 1. Groq Whisper API ────────────────► Распознанный текст с точными таймкодами
       │
       ├──► 2. pyannote.audio (Диаризация) ────► Картография спикеров (SPEAKER_00, SPEAKER_01)
       │
       ▼
 3. Сведение (Мэтчинг) ─────────────────────────► Стенограмма диалога с привязкой к спикерам
       │
       ▼
 4. Groq LLM (llama-3.3-70b-versatile) ────────► Итоговый протокол встречи (Follow-up)
```

---

## 📦 Быстрый старт

### 1. Клонирование и установка зависимостей

```bash
git clone https://github.com/Asmadey/meetup-diarization-with-pyannote.git
cd meetup-diarization-with-pyannote

# Создание и активация виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

> **Примечание:** На компьютере должен быть установлен `ffmpeg` (на macOS: `brew install ffmpeg`).

---

### 🔑 2. Настройка ключей доступа (`.env`)

Создайте файл `.env` на основе примера `.env.example`:

```bash
cp .env.example .env
```

Заполните переменные в `.env`:

```env
# API Ключ Groq (получить на https://console.groq.com)
GROQ_API_KEY=gsk_your_groq_api_key

# Access Token Hugging Face (получить на https://huggingface.co/settings/tokens)
HF_TOKEN=hf_your_huggingface_token
```

#### Как получить токен Hugging Face для pyannote.audio:
1. Зарегистрируйтесь или войдите на [huggingface.co](https://huggingface.co).
2. Подтвердите бесплатное лицензионное соглашение на страницах двух моделей:
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) (нажать *Agree and accept conditions*)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) (нажать *Agree and accept conditions*)
3. Создайте токен с правами `Read` на странице [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) и скопируйте его в `.env`.

---

## 🚀 Использование

### Шаг 1. Расшифровка аудио и диаризация спикеров

Поместите файл аудиозаписи (например, `meet.m4a`) в папку `audio/` и запустите скрипт:

```bash
python3 scripts/transcribe_diarize.py --audio audio/meet.m4a --output transcripts/meet.json
```

Параметры:
- `--audio` *(обязательно)*: Путь к файлу аудио.
- `--output`: Путь для сохранения сырого JSON результата.
- `--model`: Модель Whisper (`whisper-large-v3-turbo` по умолчанию или `whisper-large-v3`).
- `--language`: Язык аудио (по умолчанию `ru`).

### Шаг 2. Генерация фоллоу-апа встречи

Запустите форматирование в строго чистый текстовый вид:

```bash
python3 scripts/format_followup.py --input transcripts/meet.json --title "Синк по направлению Recsys — 30.07.2026" --output followups/meet.txt
```

---

## 📄 Пример получаемого отчета

Выходящий файл создается строго в чистом текстовом формате без Markdown-символов:

```
Синк по направлению Recsys — 30.07.2026

Участники:

1. Имя 1
2. Имя 2
3. Имя 3

Обсудили:

1. Архитектура и разграничение зон ответственности — зафиналены. Договорились, кто на какой стороне выполняет вычисления. Бэкенд поднимает сервис аналитики, который принимает входящие ивенты и складывает их в ClickHouse.
2. Ключевой блокер — недостающие параметры от ML-команды.
   2.1) категоризация постов происходит на шаг раньше
   2.2) согласовано с генеративными командами
```

---

## 📁 Структура проекта

```
meetup-diarization-with-pyannote/
├── SKILL.md                         # Спецификация для AI-агентов
├── README.md                        # Документация на русском языке
├── requirements.txt                 # Зависимости Python
├── .env.example                     # Пример файла переменных окружения
├── scripts/
│   ├── transcribe_diarize.py        # Скрипт транскрибации Groq + pyannote диаризация
│   └── format_followup.py           # Скрипт построения фоллоу-апа без Markdown
├── examples/
│   └── example.md                   # Шаблон эталонного формата
└── docs/
    └── groq_api.md                  # Справка по Groq API
```

---

## 📜 Лицензия

MIT License
