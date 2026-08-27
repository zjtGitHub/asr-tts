# English Listening Trainer

A local-first English listening practice app. The current v0.2 work keeps the existing FastAPI + `faster-whisper` implementation and adds a Tauri macOS desktop shell without changing the core listening workflow.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the product and architecture roadmap.

## Current features

- Upload MP3 / WAV / M4A / AAC / FLAC / OGG audio
- Transcribe English speech locally with `faster-whisper`
- Generate sentence-level timestamped transcript rows
- Preserve word timestamps in the API response
- Click any transcript line to jump playback to that sentence
- Highlight and auto-follow the currently playing sentence
- One-click locate-current-sentence control
- Hide / reveal subtitles for listening practice
- Run in a Tauri macOS desktop window during development

## macOS desktop development (v0.2)

### 1. System prerequisites

Install Xcode Command Line Tools if they are not already installed:

```bash
xcode-select --install
```

Install Rust with `rustup` if needed:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```

Install a current Node.js LTS release. Verify the required tools:

```bash
node --version
npm --version
rustc --version
cargo --version
python3 --version
```

Python 3.11 or 3.12 is recommended for the current `faster-whisper` stack.

### 2. Install Python dependencies

From this directory:

```bash
cd english-listening-trainer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The Tauri development launcher prefers `english-listening-trainer/.venv/bin/python` automatically when that virtual environment exists.

### 3. Install Tauri CLI dependencies

```bash
npm install
```

### 4. Start the macOS desktop app

Do not manually start `python app.py` first. Run:

```bash
npm run tauri dev
```

Tauri's `beforeDevCommand` starts the FastAPI backend on `127.0.0.1:8000`, waits for the local frontend URL, and opens it inside the desktop WebView.

Expected development flow:

```text
npm run tauri dev
        ↓
Python/FastAPI starts locally
        ↓
Tauri opens a macOS desktop window
        ↓
Upload audio
        ↓
faster-whisper transcribes locally
        ↓
Existing transcript/player interactions continue to work
```

On the first transcription, the selected Whisper model may need to be downloaded.

### Current v0.2 limitation

This first desktop step is intentionally development-only. The Python backend is started from the local project virtual environment and is **not yet bundled as a production sidecar inside a distributable `.app` / `.dmg`**. Packaging the Python runtime/sidecar is a later v0.2 step.

SQLite persistence, video support, URL import, and React/Vue migration are intentionally not part of this step.

## Browser-only development

The previous development mode still works:

```bash
cd english-listening-trainer
source .venv/bin/activate
python app.py
```

Open:

```text
http://localhost:8000
```

## Default Whisper model

The default configuration is optimized for CPU use:

```text
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

Override these environment variables when needed, for example:

```bash
WHISPER_MODEL=medium npm run tauri dev
```

For NVIDIA GPU development on a supported machine:

```bash
WHISPER_MODEL=large-v3 \
WHISPER_DEVICE=cuda \
WHISPER_COMPUTE_TYPE=float16 \
npm run tauri dev
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

## Next architecture steps

Follow `docs/ARCHITECTURE.md`. The immediate next steps after this Tauri development shell are:

1. make the Python inference backend a packaged sidecar that users do not need to configure manually;
2. add SQLite-backed project/lesson persistence;
3. save transcripts and resume playback without re-running Whisper;
4. then add intensive-listening controls and media expansion such as video.
