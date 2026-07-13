# OneASR

A unified speech recognition API that integrates multiple ASR engines.

[中文文档](README_CN.md)

## Features

- **File Recognition** — Upload audio/video files or provide a URL, get complete transcription results
- **Streaming File Recognition** — Upload files or provide a URL, receive sentence-by-sentence results via SSE
- **Real-time Streaming** — Send audio streams via WebSocket, get real-time transcription results
- **File Upload & Dedup** — Upload files with MD5 fingerprint, instant upload for duplicate files
- **Web Interface** — Vue.js frontend with file/URL recognition, real-time streaming display, and SRT export

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- FFmpeg (required for audio processing)

### Backend Setup

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8020
```

The server runs at `http://localhost:8020`. Visit `http://localhost:8020/docs` for interactive API documentation.

### Frontend Setup

```bash
# 1. Navigate to web directory
cd web

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```

The frontend runs at `http://localhost:3020` and automatically proxies API requests to the backend.

### Quick Launch (Two Terminals)

**Terminal 1 - Backend:**
```bash
cd OneASR
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8020
```

**Terminal 2 - Frontend:**
```bash
cd OneASR/web
npm run dev
```

### Verify Installation

```bash
# Check backend health
curl http://localhost:8020/health

# List available engines
curl -H "X-API-Key: oneasr-key" http://localhost:8020/api/v1/engines
```

After startup:
- Frontend UI: `http://localhost:3020`
- API Docs: `http://localhost:8020/docs`
- Health Check: `http://localhost:8020/health`

### Media Clipping Tool

The project includes a media clipping tool for splitting long videos into shorter segments:

```bash
# Clip a specific duration (default 2 minutes)
python cli/clip.py input_video.mp4 120

# Auto-clip entire video into 2-minute segments
python cli/clip.py input_video.mp4
```

Python API usage:
```python
from cli.clip import MediaClipper

clipper = MediaClipper("video.mp4")
clipper.clip(start=0, duration=120, output="clip.mp4")
clips = clipper.auto_clip(clip_duration=120, output_dir="clips/")
```

## Authentication

All API endpoints (except `/health`) require an API Key via the `X-API-Key` request header.

Configure the API Key in `config.yaml`:

```yaml
api_key: oneasr-key
```

```bash
# Call API with API Key
curl -H "X-API-Key: oneasr-key" http://localhost:8020/api/v1/engines

# Upload file for recognition
curl -X POST -H "X-API-Key: oneasr-key" \
  http://localhost:8020/api/v1/transcribe/file \
  -F "file=@audio.mp3" -F "format=srt" -o subtitle.srt
```

WebSocket streaming uses query parameters (browser WebSocket API doesn't support custom headers): `ws://localhost:8020/ws/transcribe/stream?api_key=oneasr-key`

## API Endpoints

### Unified API (OpenAI-compatible)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/audio/transcriptions` | POST | Create transcription (file upload or file_uuid) |
| `/api/v1/audio/transcriptions/stream` | POST | Create streaming transcription (SSE) |
| `/api/v1/audio/models` | GET | List available models |
| `/api/v1/files/upload` | POST | Upload file (supports MD5 instant upload) |
| `/api/v1/files/list` | GET | List all uploaded files |
| `/api/v1/files/{file_id}` | GET | Get file info |
| `/api/v1/files/{file_id}` | DELETE | Delete uploaded file |
| `/health` | GET | Health check |

### WebSocket Streaming

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws/transcribe/stream?api_key=` | WebSocket | Real-time streaming (WhisperLiveKit) |

## File Upload & Instant Upload (MD5 Dedup)

Upload files with optional MD5 fingerprint for instant upload of duplicate files:

```bash
# First upload: file is saved and metadata stored in DB
curl -X POST -H "X-API-Key: oneasr-key" \
  "http://localhost:8020/api/v1/files/upload?file_md5=abc123&file_size=1024000" \
  -F "file=@audio.mp3"
# Response: {"duplicate": false, "file_id": "uuid-1", ...}

# Second upload with same file: instant return (no re-upload)
curl -X POST -H "X-API-Key: oneasr-key" \
  "http://localhost:8020/api/v1/files/upload?file_md5=abc123&file_size=1024000" \
  -F "file=@audio_copy.mp3"
# Response: {"duplicate": true, "file_id": "uuid-1", ...}
```

## Streaming Recognition

Real-time speech recognition powered by [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit):

- **VAD/VAC** — Silero Voice Activity Detection, automatic speech/silence boundary detection
- **SimulStreaming** — Low-latency streaming strategy (default), or LocalAgreement high-accuracy strategy
- **Timestamp Alignment** — Each line has precise start/end timestamps
- **Speaker Diarization** — Optional speaker identification (requires additional models)
- **Multi-language** — Automatic language detection or manual specification

### WebSocket Connection

```javascript
const ws = new WebSocket("ws://localhost:8020/ws/transcribe/stream?api_key=oneasr-key&language=zh");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "config") {
    console.log("Connection config:", data);
  } else if (data.type === "ready_to_stop") {
    console.log("Recognition complete");
  } else {
    console.log(data.lines);
  }
};

ws.send(audioChunk);
ws.send(new Uint8Array(0)); // End recognition
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run API tests only (fast, no external dependencies)
python -m pytest tests/api/ -v

# Run general/unit tests only
python -m pytest tests/general/ -v

# Run a specific test file
python -m pytest tests/api/test_file_upload.py -v

# Skip integration tests (need real audio files and running services)
python -m pytest tests/ -m "not integration" -v

# Run with short traceback
python -m pytest tests/api/ -v --tb=short
```

### Test Structure

```
tests/
├── conftest.py                  # Shared fixtures (client, DB cleanup)
├── api/                         # API endpoint tests (TestClient)
│   ├── test_audio.py            # Audio transcription API
│   ├── test_file_upload.py      # File upload, MD5 dedup, CRUD
│   ├── test_models.py           # Models listing, format params
│   └── test_streaming.py        # SSE streaming transcription
└── general/                     # Unit tests & integration tests
    ├── test_format.py           # Output format conversion (SRT/VTT/JSON/TSV)
    ├── test_engines.py          # Engine loading and transcription
    ├── test_mimo.py             # MiMo audio understanding engine
    ├── test_stream_websocket.py # WebSocket streaming integration
    └── test_stream_whisperlivekit.py   # WhisperLiveKit engine tests
```

## Configuration

Edit `config.yaml` to configure API Key and engines:

```yaml
api_key: oneasr-key

default_engine: faster-whisper

engines:
  faster-whisper:
    type: local
    model_name: medium
    device: cpu
    compute_type: int8
  firered:
    type: local
    model_name: aed
    device: cpu
  whisperlivekit:
    type: local
    model_name: base
    device: cpu
    compute_type: int8
    backend: auto
    backend_policy: simulstreaming
    language: auto
    vac: true
    diarization: false
    pcm_input: true
```

## Project Structure

```
OneASR/
├── app/                          # Backend application
│   ├── main.py                   # FastAPI entry point
│   ├── api/
│   │   ├── auth.py               # API Key authentication
│   │   ├── audio.py              # OpenAI-compatible audio API
│   │   ├── models.py             # Engine/model info API
│   │   ├── upload.py             # File upload & management (MD5 dedup)
│   │   └── stream.py             # WebSocket streaming (WhisperLiveKit)
│   ├── core/
│   │   ├── config.py             # YAML configuration management
│   │   └── file_storage.py       # File storage utilities
│   ├── db/
│   │   ├── base.py               # SQLAlchemy declarative base
│   │   └── session.py            # DB engine, session factory, init
│   ├── engines/
│   │   ├── base.py               # Engine abstract base class
│   │   ├── whisper_engine.py     # faster-whisper implementation
│   │   ├── firered_engine.py     # FireRedASR implementation
│   │   ├── whisperlivekit_engine.py  # WhisperLiveKit (streaming + file)
│   │   ├── openai_engine.py      # OpenAI Whisper API
│   │   ├── mimo_engine.py        # Xiaomi MiMo API
│   │   └── registry.py           # Engine registry (singleton)
│   ├── models/
│   │   ├── schemas.py            # Pydantic data models
│   │   └── orm_models.py         # SQLAlchemy ORM models
│   └── utils/
│       ├── audio.py              # Audio format conversion
│       ├── download.py           # URL download utility
│       ├── format.py             # Output format conversion (SRT/VTT/JSON/TSV)
│       ├── stream.py             # PCM streaming utilities
│       └── vad.py                # VAD-based audio segmentation
├── cli/                          # CLI tools
│   ├── clip.py                   # Media clipping tool
│   ├── converter.py              # Audio converter
│   └── wlk_client.py             # WhisperLiveKit WebSocket client
├── web/                          # Vue.js frontend
│   ├── src/
│   │   ├── api/index.js          # API service layer (SSE streaming)
│   │   ├── router/index.js       # Vue Router configuration
│   │   ├── views/
│   │   │   ├── Layout.vue        # Main layout (sidebar + settings)
│   │   │   └── Transcribe.vue    # Speech recognition page
│   │   └── assets/main.css       # Global styles
│   ├── index.html
│   ├── vite.config.js            # Vite config (with API proxy)
│   └── package.json
├── tests/                        # Test suite
│   ├── conftest.py               # Shared fixtures
│   ├── api/                      # API endpoint tests
│   └── general/                  # Unit & integration tests
├── models/                       # Model storage directory
├── data/                         # SQLite database (auto-created)
├── uploads/                      # Uploaded files storage
├── config.yaml                   # API Key and engine configuration
└── requirements.txt
```

## License

MIT
