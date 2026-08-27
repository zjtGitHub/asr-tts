from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DIR_NAME = "EnglishListeningTrainer"
DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
DATA_DIR = Path(os.getenv("ELT_DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser().resolve()
DB_PATH = DATA_DIR / "app.sqlite"
MEDIA_DIR = DATA_DIR / "media"
CACHE_DIR = DATA_DIR / "cache"
MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = DATA_DIR / "logs"
TMP_DIR = CACHE_DIR / "tmp"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_app_directories() -> None:
    for directory in (DATA_DIR, MEDIA_DIR, CACHE_DIR, MODELS_DIR, LOGS_DIR, TMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database() -> None:
    ensure_app_directories()
    with connect() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                media_path TEXT NOT NULL,
                media_sha256 TEXT NOT NULL UNIQUE,
                media_size INTEGER NOT NULL,
                media_suffix TEXT NOT NULL,
                duration REAL NOT NULL DEFAULT 0,
                playback_position REAL NOT NULL DEFAULT 0,
                playback_rate REAL NOT NULL DEFAULT 1,
                subtitles_hidden INTEGER NOT NULL DEFAULT 0,
                auto_follow INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_opened_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_projects_last_opened
            ON projects(last_opened_at DESC);

            CREATE TABLE IF NOT EXISTS transcripts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL UNIQUE,
                engine TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                language_probability REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transcript_id TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                start REAL NOT NULL,
                end REAL NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
                UNIQUE(transcript_id, sentence_index)
            );

            CREATE INDEX IF NOT EXISTS idx_sentences_transcript
            ON sentences(transcript_id, sentence_index);

            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sentence_id INTEGER NOT NULL,
                word_index INTEGER NOT NULL,
                start REAL NOT NULL,
                end REAL NOT NULL,
                word TEXT NOT NULL,
                FOREIGN KEY(sentence_id) REFERENCES sentences(id) ON DELETE CASCADE,
                UNIQUE(sentence_id, word_index)
            );

            CREATE INDEX IF NOT EXISTS idx_words_sentence
            ON words(sentence_id, word_index);
            """
        )


def media_relative_path(project_id: str, suffix: str) -> str:
    return str(Path("media") / project_id / f"original{suffix}")


def absolute_media_path(relative_path: str) -> Path:
    path = (DATA_DIR / relative_path).resolve()
    try:
        path.relative_to(DATA_DIR)
    except ValueError as exc:
        raise ValueError("Stored media path escapes the application data directory") from exc
    return path


def find_project_id_by_hash(media_sha256: str) -> str | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id FROM projects WHERE media_sha256 = ?",
            (media_sha256,),
        ).fetchone()
    return str(row["id"]) if row else None


def delete_project(project_id: str) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def create_project(
    *,
    project_id: str,
    transcript_id: str,
    title: str,
    original_filename: str,
    media_path: str,
    media_sha256: str,
    media_size: int,
    media_suffix: str,
    duration: float,
    engine: str,
    model: str,
    language: str,
    language_probability: float,
    segments: list[dict[str, Any]],
) -> None:
    timestamp = utc_now()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO projects (
                id, title, original_filename, media_path, media_sha256, media_size,
                media_suffix, duration, created_at, updated_at, last_opened_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                title,
                original_filename,
                media_path,
                media_sha256,
                media_size,
                media_suffix,
                duration,
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO transcripts (
                id, project_id, engine, model, language, language_probability, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transcript_id,
                project_id,
                engine,
                model,
                language,
                language_probability,
                timestamp,
            ),
        )

        for sentence_index, segment in enumerate(segments):
            cursor = connection.execute(
                """
                INSERT INTO sentences (
                    transcript_id, sentence_index, start, end, text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    transcript_id,
                    sentence_index,
                    float(segment["start"]),
                    float(segment["end"]),
                    str(segment["text"]),
                ),
            )
            sentence_id = int(cursor.lastrowid)
            for word_index, word in enumerate(segment.get("words", [])):
                connection.execute(
                    """
                    INSERT INTO words (
                        sentence_id, word_index, start, end, word
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        sentence_id,
                        word_index,
                        float(word["start"]),
                        float(word["end"]),
                        str(word["word"]),
                    ),
                )


def _project_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "original_filename": row["original_filename"],
        "media_sha256": row["media_sha256"],
        "media_size": int(row["media_size"]),
        "media_suffix": row["media_suffix"],
        "duration": float(row["duration"]),
        "playback_position": float(row["playback_position"]),
        "playback_rate": float(row["playback_rate"]),
        "subtitles_hidden": bool(row["subtitles_hidden"]),
        "auto_follow": bool(row["auto_follow"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_opened_at": row["last_opened_at"],
        "engine": row["engine"],
        "model": row["model"],
        "language": row["language"],
        "language_probability": float(row["language_probability"]),
        "sentence_count": int(row["sentence_count"]),
    }


def list_projects(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                p.*,
                t.engine,
                t.model,
                t.language,
                t.language_probability,
                COUNT(s.id) AS sentence_count
            FROM projects p
            JOIN transcripts t ON t.project_id = p.id
            LEFT JOIN sentences s ON s.transcript_id = t.id
            GROUP BY p.id, t.id
            ORDER BY p.last_opened_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()
    return [_project_row_to_dict(row) for row in rows]


def get_project(project_id: str, *, touch: bool = True) -> dict[str, Any] | None:
    with connect() as connection:
        if touch:
            timestamp = utc_now()
            connection.execute(
                "UPDATE projects SET last_opened_at = ?, updated_at = ? WHERE id = ?",
                (timestamp, timestamp, project_id),
            )

        row = connection.execute(
            """
            SELECT
                p.*,
                t.id AS transcript_id,
                t.engine,
                t.model,
                t.language,
                t.language_probability,
                (SELECT COUNT(*) FROM sentences s WHERE s.transcript_id = t.id) AS sentence_count
            FROM projects p
            JOIN transcripts t ON t.project_id = p.id
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
        if not row:
            return None

        project = _project_row_to_dict(row)
        transcript_id = row["transcript_id"]
        sentence_rows = connection.execute(
            """
            SELECT id, sentence_index, start, end, text
            FROM sentences
            WHERE transcript_id = ?
            ORDER BY sentence_index ASC
            """,
            (transcript_id,),
        ).fetchall()

        sentence_ids = [int(sentence["id"]) for sentence in sentence_rows]
        words_by_sentence: dict[int, list[dict[str, Any]]] = {sid: [] for sid in sentence_ids}
        if sentence_ids:
            placeholders = ",".join("?" for _ in sentence_ids)
            word_rows = connection.execute(
                f"""
                SELECT sentence_id, start, end, word
                FROM words
                WHERE sentence_id IN ({placeholders})
                ORDER BY sentence_id ASC, word_index ASC
                """,
                sentence_ids,
            ).fetchall()
            for word in word_rows:
                words_by_sentence[int(word["sentence_id"])].append(
                    {
                        "start": float(word["start"]),
                        "end": float(word["end"]),
                        "word": word["word"],
                    }
                )

        project["segments"] = [
            {
                "start": float(sentence["start"]),
                "end": float(sentence["end"]),
                "text": sentence["text"],
                "words": words_by_sentence[int(sentence["id"])],
            }
            for sentence in sentence_rows
        ]
        return project


def get_project_media_path(project_id: str) -> Path | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT media_path FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    if not row:
        return None
    return absolute_media_path(str(row["media_path"]))


def update_project_progress(
    project_id: str,
    *,
    playback_position: float | None = None,
    playback_rate: float | None = None,
    subtitles_hidden: bool | None = None,
    auto_follow: bool | None = None,
) -> bool:
    assignments: list[str] = []
    values: list[Any] = []

    if playback_position is not None:
        assignments.append("playback_position = ?")
        values.append(max(0.0, float(playback_position)))
    if playback_rate is not None:
        assignments.append("playback_rate = ?")
        values.append(max(0.25, min(float(playback_rate), 4.0)))
    if subtitles_hidden is not None:
        assignments.append("subtitles_hidden = ?")
        values.append(1 if subtitles_hidden else 0)
    if auto_follow is not None:
        assignments.append("auto_follow = ?")
        values.append(1 if auto_follow else 0)

    timestamp = utc_now()
    assignments.extend(["updated_at = ?", "last_opened_at = ?"])
    values.extend([timestamp, timestamp, project_id])

    with connect() as connection:
        cursor = connection.execute(
            f"UPDATE projects SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
    return cursor.rowcount > 0


def debug_database_summary() -> dict[str, Any]:
    with connect() as connection:
        project_count = int(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
        sentence_count = int(connection.execute("SELECT COUNT(*) FROM sentences").fetchone()[0])
    return {
        "database": str(DB_PATH),
        "project_count": project_count,
        "sentence_count": sentence_count,
    }
