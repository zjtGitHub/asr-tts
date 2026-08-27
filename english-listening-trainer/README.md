# English Listening Trainer

A small local web app for English listening practice.

## Features

- Upload MP3 / WAV / M4A / AAC / FLAC / OGG audio
- Transcribe English speech locally with `faster-whisper`
- Generate timestamped transcript segments
- Click any transcript line to jump the audio player to that moment
- Highlight the currently playing transcript segment
- Word timestamps are included in the API response for future extensions

## Run locally

```bash
cd english-listening-trainer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://localhost:8000
```

The first transcription may take longer because the Whisper model needs to be downloaded.

## Default model

The default configuration is optimized for CPU use:

```text
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

You can override these environment variables, for example:

```bash
WHISPER_MODEL=medium python app.py
```

For NVIDIA GPU:

```bash
WHISPER_MODEL=large-v3 \
WHISPER_DEVICE=cuda \
WHISPER_COMPUTE_TYPE=float16 \
python app.py
```

## API

### `POST /api/transcribe`

Multipart form field:

```text
file=<audio file>
```

Response shape:

```json
{
  "filename": "example.mp3",
  "language": "en",
  "language_probability": 0.99,
  "duration": 120.4,
  "segments": [
    {
      "start": 3.42,
      "end": 7.81,
      "text": "What have you been up to lately?",
      "words": [
        {"start": 3.42, "end": 3.62, "word": "What"}
      ]
    }
  ]
}
```

## Next ideas

- Split long Whisper segments into sentence-level transcript rows
- Hide / reveal transcript for listening drills
- Repeat current sentence
- Playback speed shortcuts
- Chinese translation and phrase explanations
- Save listening history and difficult sentences
- Speaker diarization for interviews
