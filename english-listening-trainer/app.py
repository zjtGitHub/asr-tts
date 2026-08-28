from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from faster_whisper import WhisperModel

from persistence import (
    MEDIA_DIR,
    create_project,
    delete_project,
    find_project_id_by_hash,
    get_project,
    get_project_media_path,
    init_database,
    list_projects,
    media_relative_path,
    rename_project,
    update_project_progress,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
MAX_LESSON_TITLE_LENGTH = 200

app = FastAPI(title="English Listening Trainer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model: WhisperModel | None = None
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]*$")


@app.on_event("startup")
def startup() -> None:
    init_database()


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
        )
    return _model


def build_sentence_rows(segments) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_words: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current_words
        if not current_words:
            return
        text = " ".join(item["word"] for item in current_words)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text).strip()
        rows.append(
            {
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "text": text,
                "words": current_words,
            }
        )
        current_words = []

    for segment in segments:
        words = list(segment.words or [])
        if not words:
            text = segment.text.strip()
            if text:
                flush()
                rows.append(
                    {
                        "start": round(float(segment.start), 3),
                        "end": round(float(segment.end), 3),
                        "text": text,
                        "words": [],
                    }
                )
            continue

        for word in words:
            token = word.word.strip()
            if not token:
                continue
            current_words.append(
                {
                    "start": round(float(word.start if word.start is not None else segment.start), 3),
                    "end": round(float(word.end if word.end is not None else segment.end), 3),
                    "word": token,
                }
            )
            if SENTENCE_END_RE.search(token):
                flush()

    flush()
    return rows


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def title_from_filename(filename: str) -> str:
    title = Path(filename).stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", title).strip() or "Untitled lesson"


def project_payload(project: dict[str, Any], *, reused: bool = False) -> dict[str, Any]:
    return {
        **project,
        "filename": project["original_filename"],
        "reused": reused,
        "media_url": f"/api/projects/{project['id']}/media",
    }


def validated_title(payload: dict[str, Any]) -> str:
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="Lesson title cannot be empty")
    if len(title) > MAX_LESSON_TITLE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Lesson title must be {MAX_LESSON_TITLE_LENGTH} characters or fewer",
        )
    return title


def expected_project_media_directory(project_id: str, media_path: Path) -> Path:
    expected = (MEDIA_DIR / project_id).resolve()
    actual = media_path.parent.resolve()
    if actual != expected:
        raise HTTPException(status_code=500, detail="Stored lesson media path is invalid")
    return actual


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/projects")
def projects() -> dict[str, Any]:
    return {"projects": list_projects()}


@app.get("/api/projects/{project_id}")
def project(project_id: str) -> dict[str, Any]:
    stored = get_project(project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return project_payload(stored)


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    title = validated_title(payload)
    if not rename_project(project_id, title):
        raise HTTPException(status_code=404, detail="Lesson not found")
    stored = get_project(project_id, touch=False)
    if stored is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return project_payload(stored)


@app.delete("/api/projects/{project_id}")
def remove_project(project_id: str) -> dict[str, bool]:
    media_path = get_project_media_path(project_id)
    if media_path is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    project_directory = expected_project_media_directory(project_id, media_path)
    if not delete_project(project_id):
        raise HTTPException(status_code=404, detail="Lesson not found")

    try:
        if project_directory.exists():
            shutil.rmtree(project_directory)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Lesson record was deleted, but its local media could not be removed: {exc}",
        ) from exc

    return {"ok": True}


@app.get("/api/projects/{project_id}/media")
def project_media(project_id: str) -> FileResponse:
    media_path = get_project_media_path(project_id)
    if media_path is None or not media_path.is_file():
        raise HTTPException(status_code=404, detail="Lesson media is missing")
    return FileResponse(media_path)


@app.patch("/api/projects/{project_id}/progress")
def save_progress(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, bool]:
    allowed = {
        key: payload[key]
        for key in ("playback_position", "playback_rate", "subtitles_hidden", "auto_follow")
        if key in payload
    }
    if not allowed:
        return {"ok": True}
    if not update_project_progress(project_id, **allowed):
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"ok": True}


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = Path(file.filename or "audio.mp3").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    temp_path: Path | None = None
    project_directory: Path | None = None
    project_id: str | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)

        media_sha256 = hash_file(temp_path)
        existing_project_id = find_project_id_by_hash(media_sha256)
        if existing_project_id:
            existing = get_project(existing_project_id)
            if existing is not None:
                existing_media = get_project_media_path(existing_project_id)
                if existing_media is not None and existing_media.is_file():
                    return project_payload(existing, reused=True)
                delete_project(existing_project_id)
                if existing_media is not None:
                    shutil.rmtree(existing_media.parent, ignore_errors=True)

        project_id = uuid.uuid4().hex
        transcript_id = uuid.uuid4().hex
        project_directory = MEDIA_DIR / project_id
        project_directory.mkdir(parents=True, exist_ok=False)
        stored_media = project_directory / f"original{suffix}"
        shutil.copy2(temp_path, stored_media)

        model = get_model()
        segments, info = model.transcribe(
            str(stored_media),
            language="en",
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=True,
        )
        rows = build_sentence_rows(segments)
        duration = round(float(info.duration), 3)
        language_probability = round(float(info.language_probability), 4)

        create_project(
            project_id=project_id,
            transcript_id=transcript_id,
            title=title_from_filename(filename),
            original_filename=filename,
            media_path=media_relative_path(project_id, suffix),
            media_sha256=media_sha256,
            media_size=stored_media.stat().st_size,
            media_suffix=suffix,
            duration=duration,
            engine="faster-whisper",
            model=MODEL_SIZE,
            language=info.language,
            language_probability=language_probability,
            segments=rows,
        )
        stored = get_project(project_id)
        if stored is None:
            raise RuntimeError("Persisted lesson could not be reloaded")
        return project_payload(stored)
    except HTTPException:
        raise
    except Exception as exc:
        if project_id:
            delete_project(project_id)
        if project_directory and project_directory.exists():
            shutil.rmtree(project_directory, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
