# English Listening Trainer

A local-first English listening practice app. v0.2 keeps the existing FastAPI + `faster-whisper` transcription engine and wraps it in a Tauri macOS desktop application.

See:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the product/architecture roadmap;
- [`docs/V0.2_PACKAGING.md`](docs/V0.2_PACKAGING.md) for the Apple Silicon sidecar and `.app` / `.dmg` build workflow.

## Current features

- Upload MP3 / WAV / M4A / AAC / FLAC / OGG audio
- Transcribe English speech locally with `faster-whisper`
- Generate sentence-level timestamped transcript rows
- Preserve word timestamps in the API response
- Click any transcript line to jump playback to that sentence
- Highlight and auto-follow the currently playing sentence
- One-click locate-current-sentence control
- Hide / reveal subtitles for listening practice
- Run in a Tauri macOS desktop window
- Build the Python/FastAPI/Whisper backend as an Apple Silicon standalone sidecar for packaged release builds

## Development mode

Verify the local toolchain:

```bash
node --version
npm --version
rustc --version
cargo --version
python3 --version
```

Python 3.11 or 3.12 is recommended for the current packaging stack.

Create/install the project Python environment:

```bash
cd english-listening-trainer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
npm install
```

Run the development app:

```bash
npm run tauri dev
```

Development mode still uses `scripts/dev_backend.py` and the project `.venv` for fast iteration.

## Packaged release mode

Release builds use a bundled backend executable instead of the user's Python installation:

```text
English Listening Trainer.app
        ↓
Tauri starts bundled sidecar
        ↓
english-listening-backend
(PyInstaller executable with Python runtime)
        ↓
FastAPI + faster-whisper on 127.0.0.1:8000
        ↓
Bundled Web UI calls the local backend
```

Current packaging target:

```text
macOS Apple Silicon arm64
Rust target: aarch64-apple-darwin
```

Install packaging dependencies:

```bash
source .venv/bin/activate
pip install -r requirements-build.txt
```

Build only the backend sidecar:

```bash
npm run backend:build
```

Expected generated binary:

```text
src-tauri/binaries/english-listening-backend-aarch64-apple-darwin
```

Build the complete `.app` / `.dmg`:

```bash
npm run desktop:build
```

This prepares bundle icons, builds the sidecar, then runs the Tauri release build with `src-tauri/tauri.release.conf.json`.

See [`docs/V0.2_PACKAGING.md`](docs/V0.2_PACKAGING.md) for smoke tests and full verification steps.

## Default Whisper model

```text
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

The Whisper model itself is intentionally not embedded in the `.app`. The first transcription may download it and cache it locally for reuse.

## Browser-only development

```bash
source .venv/bin/activate
python app.py
```

Then open:

```text
http://localhost:8000
```

## API

### `GET /health`

```json
{"status":"ok"}
```

### `POST /api/transcribe`

Multipart field:

```text
file=<audio file>
```

The response contains sentence-level segments and word timestamps.

## v0.2 boundary

The sidecar packaging code is implemented, but the actual Apple Silicon `.app` / `.dmg` build still needs to be run and verified on a real Mac before this stage is considered complete.

Not part of this packaging stage:

- SQLite / project persistence
- video import
- URL import
- Podcast import
- React/Vue migration
- new learning features
- Intel Mac / Windows packaging
- production Developer ID signing / notarization
