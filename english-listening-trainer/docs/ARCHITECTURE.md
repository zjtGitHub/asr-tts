# English Listening Trainer — Architecture & Product Roadmap

## 1. Product direction

English Listening Trainer should evolve from a temporary local web demo into a **local-first macOS desktop application for intensive English listening practice**.

The core product promise is not simply "transcribe audio". It is:

> Turn any English audio or video into a reusable listening lesson, then help the learner move from recognizing isolated words to understanding complete natural sentences.

The first commercial target is intentionally small: build a useful macOS product that a few hundred users would be willing to buy. The architecture should therefore optimize for:

- low operating cost;
- local processing and privacy;
- fast iteration by a solo developer;
- reusable learning assets instead of one-off transcriptions;
- a clear migration path from prototype to distributable Mac app.

---

## 2. Architecture decision

### Decision

Do **not** continue investing heavily in the current browser-only architecture, and do **not** rewrite the product in SwiftUI from scratch at this stage.

The preferred path is:

```text
Current web MVP
      ↓
Tauri macOS desktop app
      ↓
Reuse the existing web UI
      ↓
Local persistence + media library
      ↓
Python/faster-whisper sidecar initially
      ↓
Later replace the Python inference layer with whisper.cpp / MLX if needed
```

### Why Tauri

Tauri gives the project a real desktop application shell while preserving the existing web development speed.

It provides a practical path to:

- `.app` / `.dmg` distribution;
- native windows and Dock integration;
- local file-system access;
- drag-and-drop import;
- application data directories;
- SQLite persistence;
- keyboard shortcuts;
- local FFmpeg integration;
- auto-update support later;
- keeping the UI in HTML/React/Vue instead of immediately rewriting everything in Swift.

### Why not SwiftUI now

SwiftUI may be considered later for deeply native Mac experiences, but a full rewrite now would spend too much development time reproducing UI and state-management functionality that already exists in the web prototype.

The product still needs validation. Development effort should go into the listening experience and content workflow rather than framework migration.

---

## 3. Target system architecture

### Near-term architecture

```text
┌──────────────────────────────────────┐
│            Tauri macOS App           │
│                                      │
│  Web UI                              │
│  HTML → later React/Vue + TypeScript │
│           │                          │
│           ▼                          │
│  Tauri commands / local API          │
│           │                          │
│   ┌───────┼────────┐                 │
│   ▼       ▼        ▼                 │
│ SQLite  Files     FFmpeg             │
│                    │                 │
│                    ▼                 │
│          Python sidecar              │
│          faster-whisper              │
│                    │                 │
│                    ▼                 │
│          Transcript / timestamps     │
└──────────────────────────────────────┘
```

### Long-term architecture

```text
Tauri
  ↓
React/Vue + TypeScript
  ↓
Rust/native commands
  ↓
SQLite + local files + FFmpeg
  ↓
whisper.cpp / MLX / native inference
```

The long-term goal is to make Python optional or remove it entirely from the packaged application once the product is validated and native inference becomes worth the migration cost.

---

## 4. Local-first principle

Heavy workloads should run on the user's machine whenever practical.

Local processing should handle:

- media import;
- media download when legally permitted and technically supported;
- FFmpeg audio extraction;
- Whisper transcription;
- timestamp alignment;
- project/media storage;
- playback;
- learning history;
- difficult-sentence review.

A future cloud backend, if introduced, should remain lightweight and optional, primarily for:

- license / activation;
- user account;
- payment verification;
- settings sync;
- optional cloud transcription credits;
- optional AI explanation service.

Raw media should not be uploaded to a server by default.

This keeps marginal infrastructure cost close to zero and also provides a privacy benefit that can become part of the product positioning.

---

## 5. Persistence: from transcription session to learning project

The current implementation is session-based: refresh the browser and the transcription state disappears.

This must change before adding many more learning features.

The central domain object should become a **Project / Lesson**.

A project represents one reusable learning asset.

```text
Project
├── metadata
├── media source
├── local media asset
├── transcript
├── word timestamps
├── playback state
├── learning state
├── difficult sentences
└── review history
```

### Suggested application data layout

```text
~/Library/Application Support/EnglishListeningTrainer/
├── app.sqlite
├── media/
│   ├── <project-id>/
│   │   └── original.<ext>
│   └── ...
├── cache/
├── models/
└── logs/
```

Exact paths should be obtained through Tauri's application-data APIs rather than hard-coded.

---

## 6. SQLite data model

SQLite is sufficient for the desktop product and should be the default local database.

### `projects`

Suggested fields:

```text
id
title
source_type
source_url
media_path
media_hash
duration
created_at
updated_at
last_opened_at
playback_position
playback_speed
subtitle_hidden
auto_follow
```

### `transcripts`

```text
id
project_id
engine
model
language
created_at
```

This is deliberately separate from `projects` so the same media can later be re-transcribed using another model without destroying previous results.

### `sentences`

```text
id
transcript_id
sequence
start
end
text
is_favorite
```

### `words`

```text
id
sentence_id
sequence
start
end
text
```

### Future `study_records`

```text
id
sentence_id
status
review_count
last_reviewed_at
next_review_at
```

---

## 7. Media deduplication and caching

Whisper transcription is expensive relative to normal UI operations, so previously processed content should never be re-transcribed unnecessarily.

For imported local files:

```text
Import file
   ↓
Calculate file fingerprint / SHA-256
   ↓
Check local database
   ↓
Existing transcript?
   ├── Yes → reuse immediately
   └── No  → transcribe and persist
```

Each transcript must record its inference engine and model, for example:

```text
engine = faster-whisper
model = small
language = en
```

This allows a future action such as:

> Re-transcribe with Medium / Large for higher accuracy.

---

## 8. Media source abstraction

The application should eventually treat all imported content as a common `MediaSource` instead of implementing unrelated pipelines for MP3, video, podcast and URLs.

Possible source types:

```text
LocalFile
DirectURL
PodcastEpisode
YouTube
Bilibili
OtherResolver
```

All source types should resolve into a common local `MediaAsset` before transcription.

Recommended pipeline:

```text
MediaSource
    ↓
Resolve
    ↓
Acquire / open
    ↓
MediaAsset
    ↓
ffprobe metadata
    ↓
Extract / normalize audio
    ↓
Fingerprint
    ↓
Reuse existing transcript or run Whisper
    ↓
Transcript
    ↓
Learning Project
```

This abstraction should be introduced before many URL-specific integrations are added.

---

## 9. Video support

Video should be supported after persistence is stable.

The application should preserve the original video for playback but extract a normalized audio stream for transcription.

```text
MP4 / MOV / MKV / WebM
        ↓
      FFmpeg
        ↓
16 kHz mono audio for ASR
        ↓
      Whisper
        ↓
Sentence + word timestamps
```

The UI then synchronizes the transcript with the original video player.

Do not upload multi-gigabyte videos to a cloud server by default.

---

## 10. URL and podcast import

URL import should be implemented only after the local project/media pipeline is stable.

### Direct media URLs

Direct MP3/MP4-like URLs can be downloaded locally and treated as normal media assets.

### Podcast

Podcast support is strategically important because it directly matches the target listening use case.

Potential flow:

```text
Podcast RSS
   ↓
Episode list
   ↓
Select episode
   ↓
Download audio locally
   ↓
Transcribe
   ↓
Create lesson
```

A future subscription model may notify the user when new episodes are available, but automatic cloud transcription is not required.

### YouTube / Bilibili / other pages

A resolver layer such as `yt-dlp` may be evaluated for supported sources.

Commercial distribution must respect platform terms, copyright, DRM restrictions and content ownership. The product should not be positioned primarily as a tool for bypassing platform restrictions.

---

## 11. Learning UX priorities

The product should optimize for listening practice rather than transcription productivity.

### Core controls

Recommended keyboard-first workflow:

```text
Space    Play / pause
←        Previous sentence
→        Next sentence
R        Replay current sentence
L        Locate current sentence
H        Hide / show subtitles
1        0.8× speed
2        1.0× speed
```

### High-priority learning features

After persistence and desktop packaging:

1. sentence loop;
2. previous / next sentence;
3. playback speed controls;
4. word-level synchronized highlighting;
5. dictation mode;
6. difficult-sentence favorites;
7. spaced review;
8. "Why couldn't I hear this?" explanation;
9. shadowing / recording comparison;
10. optional pronunciation feedback.

### Three-stage listening workflow

A future lesson mode should encourage:

```text
1. Listen without subtitles
2. Reveal English transcript and replay difficult phrases
3. Reveal translation / explanations only when needed
```

The product should avoid making the learner read bilingual subtitles from the beginning, because that turns listening practice into reading practice.

---

## 12. AI explanation principle

The feature "Why couldn't I hear this?" has strong product potential, but the first version must avoid pretending that a text-only LLM has acoustically analyzed the actual waveform.

Early versions should phrase explanations as:

> Common or likely connected-speech phenomena in this sentence include ...

Later versions may combine word/phoneme alignment and actual audio analysis for stronger claims.

Possible explanations include:

- reductions;
- weak forms;
- linking;
- contractions;
- phrase meaning;
- stress and rhythm;
- common spoken alternatives.

---

## 13. Front-end evolution

### Current

Single HTML page is acceptable while validating the core product.

### When to migrate to React/Vue

Move to a structured front-end framework once the app gains multiple real product screens, for example:

```text
Home / recent lessons
Lesson player
Difficult sentences
Review
Settings
Model manager
```

Do not migrate merely for code cleanliness. Migrate when application state and screen complexity justify it.

---

## 14. Inference evolution

### Phase 1 — keep current implementation

```text
Python
FastAPI / sidecar
faster-whisper
CPU int8
```

The current implementation is already validated on Apple Silicon and is the fastest route to a working desktop alpha.

### Phase 2 — optimize after validation

Evaluate:

- `whisper.cpp` + Metal;
- MLX-based Whisper on Apple Silicon;
- direct Rust/native integration where appropriate.

Migration criteria should include:

- package size;
- install complexity;
- startup time;
- transcription speed;
- memory use;
- distribution / code-signing complexity;
- actual user demand.

Do not rewrite the inference layer solely for technical elegance.

---

## 15. Product roadmap

### v0.1 — current web MVP

Goal: validate the listening interaction.

Already demonstrated:

- audio upload;
- local faster-whisper transcription;
- sentence timestamps;
- click-to-seek;
- current-sentence highlighting;
- transcript auto-follow;
- locate-current control;
- hide / show subtitles.

### v0.2 — desktop foundation

Goal: stop being a browser demo.

- package as Tauri macOS app;
- keep current web UI initially;
- integrate the existing Python/faster-whisper process as a local sidecar;
- define application data directories;
- basic drag-and-drop import;
- produce a distributable development `.app` / `.dmg`.

### v0.3 — persistent learning library

Goal: make every transcription reusable.

- SQLite;
- project/lesson model;
- save transcript and word timestamps;
- media fingerprinting and deduplication;
- recent lessons screen;
- restore playback position;
- persist playback speed and subtitle settings;
- never re-run Whisper unnecessarily.

### v0.4 — intensive-listening controls

- sentence loop;
- previous / next sentence;
- keyboard shortcuts;
- configurable lead-in / tail padding;
- word-level synchronized highlighting;
- editable transcript corrections.

### v0.5 — video

- MP4/MOV/MKV/WebM import;
- ffprobe metadata;
- FFmpeg audio extraction;
- video playback synchronized to transcript.

### v0.6 — flexible content import

- direct media URL;
- podcast RSS / episode import;
- evaluate supported URL resolvers such as yt-dlp;
- unified `MediaSource` pipeline.

### v0.7 — learning system

- dictation mode;
- difficult-sentence favorites;
- review history;
- spaced repetition;
- progress statistics.

### v0.8 — AI-assisted listening

- Chinese translation on demand;
- phrase explanation;
- "Why couldn't I hear this?";
- optional user-provided API key;
- optional built-in paid AI quota later.

### v0.9+ — productization

- model manager;
- better Apple Silicon inference;
- app signing and notarization;
- automatic updates;
- license / payment system if commercialized;
- optional lightweight account sync;
- investigate Mac App Store vs direct distribution.

---

## 16. Commercial architecture principle

The intended business model should not require the developer to pay GPU cost for every minute a user studies.

Preferred model:

```text
Local transcription: unlimited / near-zero marginal cost
Optional cloud transcription: usage-based credits
Optional AI explanation: quota or user's own API key
Desktop Pro license: one-time purchase initially
```

The application should remain useful even without an account or cloud connection.

---

## 17. Non-goals for the early product

Do not prioritize these before the core workflow is proven:

- social features;
- large content library;
- online courses;
- complex account systems;
- cloud-first media storage;
- GPU infrastructure;
- multi-platform Windows support;
- rewriting everything in SwiftUI;
- premature anti-piracy engineering;
- complex backend admin systems.

The initial target remains **macOS / Apple Silicon first**.

---

## 18. Guiding principle

When choosing between two implementation paths, prefer the one that improves this loop:

```text
Find interesting English content
        ↓
Import it with minimal friction
        ↓
Transcribe once
        ↓
Keep it permanently
        ↓
Listen sentence by sentence
        ↓
Identify exactly what was not understood
        ↓
Replay / study / review
        ↓
Come back tomorrow and continue immediately
```

Anything that does not materially improve this loop should be lower priority.
