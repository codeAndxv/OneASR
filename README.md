# OneASR

<p align="center">
  <img src="./docs/assets/OneASR.svg" width="128" alt="OneASR Logo">
</p>

A unified speech recognition API gateway that integrates multiple local and cloud ASR engines with intelligent model lifecycle management.

[中文文档](README_CN.md)

## Features

- **Unified OpenAI-Compatible Audio API** — Upload audio/video files or specify `file_uuid` / `url`, get transcription in `json`, `verbose_json`, `text`, `srt`, `vtt`, or `tsv`
- **SSE Streaming File Recognition** — Receive sentence-by-sentence transcription segments in real time via Server-Sent Events (`stream=true`)
- **Real-time WebSocket Streaming** — Low-latency streaming speech recognition (`/v1/realtime` & `/v1/realtime_ext`) powered by `xasr` (`sherpa-onnx` Zipformer2 transducer)
- **Ollama-Style Model Lifecycle Manager** — On-demand loading, configurable `keep_alive` TTL auto-unloading, `max_loaded_models` LRU eviction, active task reference counting, and manual `/load` & `/unload` APIs
- **One-Command Model CLI (`cli.model`)** — Inspect, verify, and download local models into `data/models/` with automatic ModelScope / HuggingFace Mirror fallback
- **File Upload & MD5 Instant Dedup** — Upload files with MD5 fingerprint for instant deduplication, plus async long-audio task management
- **Web Interface** — Vue 3 frontend with file/URL recognition, real-time streaming display, and SRT/VTT export

## Quick Start

### Prerequisites

- Python 3.12+ (managed by [uv](https://docs.astral.sh/uv/))
- Node.js 18+
- FFmpeg (required for audio/video decoding and resampling)

### Backend Setup

```bash
# 1. Create virtual environment
uv venv --python 3.12

# 2. Install dependencies
uv pip install -r requirements.txt
# or install with dev/test dependencies:
uv pip install -e ".[dev]"

# 3. Download enabled local models (auto-selects ModelScope / HF-Mirror / HuggingFace)
uv run python -m cli.model pull

# 4. Start the server
uv run uvicorn server.main:app --host 0.0.0.0 --port 8020
```

The server runs at `http://localhost:8020`. Visit `http://localhost:8020/docs` for interactive Swagger API documentation.

### Frontend Setup

```bash
cd web
npm install
npm run dev
```

The frontend runs at `http://localhost:3020` and automatically proxies API requests to the backend.

### Verify Installation

```bash
# Check backend health
curl http://localhost:8020/health

# List available models (standard OpenAI format)
curl -H "Authorization: Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u" \
  http://localhost:8020/v1/models

# List models with extended capability matrix & runtime status
curl -H "Authorization: Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u" \
  http://localhost:8020/v1/x/models
```

---

## Model Management & Download Guide

Local ASR models are stored in `data/models/` by default. OneASR provides a built-in CLI tool (`cli.model`) that reads `config.yaml` and automatically downloads, extracts, and verifies model weights.

### 1. Recommended: Built-in Model CLI (`cli.model`)

```bash
# 1. List all configured local models, status (Ready / Incomplete / Missing), and disk size
uv run python -m cli.model list

# 2. Pull all enabled (enable: true) models configured in config.yaml
uv run python -m cli.model pull

# 3. Pull specific provider models (even if enable: false in config.yaml)
uv run python -m cli.model pull xasr faster-whisper
uv run python -m cli.model pull qwen --include-aligner

# 4. Pull all configured local models using a specific hub source
uv run python -m cli.model pull --all --source modelscope
uv run python -m cli.model pull faster-whisper --source hf-mirror --force

# 5. Offline integrity verification (checks required .onnx / model.bin / .safetensors shards)
uv run python -m cli.model check
```

### 2. Manual CLI Download (Optional)

If you prefer using `hf` or `modelscope` CLI directly, run from the `OneASR/` root directory:

- **X-ASR (`sherpa-onnx` streaming model)**:
  ```bash
  modelscope download --model Gilgamesh-J/X-ASR-zh-en \
    --include "deployment/models/chunk-160ms-model/*" \
    --local_dir data/models
  mv data/models/deployment/models/chunk-160ms-model data/models/chunk-160ms-model
  rm -rf data/models/deployment
  ```
- **Faster-Whisper (`medium` / `large-v3`)**:
  ```bash
  hf download Systran/faster-whisper-medium --local-dir data/models/faster-whisper-medium
  # or via ModelScope:
  modelscope download --model Systran/faster-whisper-medium --local_dir data/models/faster-whisper-medium
  ```
- **Qwen3-ASR (`Qwen/Qwen3-ASR-1.7B` & `ForcedAligner`)**:
  ```bash
  modelscope download --model Qwen/Qwen3-ASR-1.7B --local_dir data/models/Qwen3-ASR-1.7B
  modelscope download --model Qwen/Qwen3-ForcedAligner-0.6B --local_dir data/models/Qwen3-ForcedAligner-0.6B
  ```
- **FunASR (`iic/SenseVoiceSmall` + `fsmn-vad`)**:
  ```bash
  modelscope download --model iic/SenseVoiceSmall --local_dir data/models/SenseVoiceSmall
  modelscope download --model iic/speech_fsmn_vad_zh-cn-16k-common-pytorch --local_dir data/models/speech_fsmn_vad_zh-cn-16k-common-pytorch
  ```

---

## Configuration & Model Lifecycle (`config.yaml`)

OneASR automatically maps `model_name` (`Org/Repo-Name`) to `data/models/<Repo-Name>` and features an Ollama-inspired model lifecycle manager that prevents out-of-memory issues when configuring multiple large local ASR models:

- **`preload: true` & `keep_alive: -1`**: Ideal for lightweight real-time streaming models (`xasr`), keeping them permanently resident in memory with zero cold-start latency.
- **`preload: false` & `keep_alive: 600`**: Ideal for heavy offline transcription models (`faster-whisper`, `qwen`, `funasr`). Validated at startup with zero RAM usage, loaded on first request, and automatically unloaded after 10 minutes of inactivity or when `max_loaded_models` capacity is reached.

```yaml
api_key: sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u

# Ollama-style model lifecycle & memory management
model_manager:
  default_keep_alive: 600        # Default idle TTL in seconds (supports "10m", 600, -1 forever, 0 immediate unload)
  max_loaded_models: 2           # Max concurrent non-pinned local models in RAM (LRU eviction)
  cleanup_interval: 30           # Background idle reaper interval in seconds

ASR-Toolkit:
  vad:
    model: "silero_vad"
    threshold: 0.5
    min_speech_duration_ms: 250
    min_silence_duration_ms: 300
    padding_ms: 100
  chunking:
    target_chunk_duration: 6.0
    max_chunk_duration: 8.0
    min_pause_duration: 0.4
    min_sentence_duration: 2.0

ASR-Providers:
  xasr:
    enable: true
    engine: xasr
    preload: true                # Preload at startup
    keep_alive: -1               # Pin in memory forever
    load:
      model_name: Gilgamesh-J/X-ASR-zh-en
      provider: cpu
      sample_rate: 16000

  faster-whisper:
    enable: true
    engine: faster-whisper
    preload: false               # Lazy load on demand
    keep_alive: 600              # Auto-unload after 10m idle
    load:
      model_name: Systran/faster-whisper-medium
      device: cpu
      compute_type: int8

  qwen:
    enable: false
    engine: qwen
    load:
      model_name: Qwen/Qwen3-ASR-1.7B
      device: cpu
      dtype: float32
      # forced_aligner_name: Qwen/Qwen3-ForcedAligner-0.6B

  funasr:
    enable: false
    engine: funasr
    load:
      model_name: iic/SenseVoiceSmall
      vad_model: iic/speech_fsmn_vad_zh-cn-16k-common-pytorch
      punc_model: null
      device: cpu
```

---

## API Endpoints

All API endpoints (except `/health`) require authentication via `Authorization: Bearer <api_key>` or `X-API-Key: <api_key>`.

### 1. OpenAI Standard API (`/v1/*`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/models` | GET | List available models (standard OpenAI format) |
| `/v1/models/{model_id}` | GET | Get model details (standard OpenAI format) |
| `/v1/audio/transcriptions` | POST | Transcribe audio/video (`file`, `file_uuid`, or `url`; supports `stream=true` SSE) |
| `/v1/realtime?api_key=` | WebSocket | Real-time streaming (OpenAI Realtime Transcription protocol) |
| `/health` | GET | Service health check |

```bash
# Synchronous transcription (verbose_json / srt / vtt / text / json)
curl -X POST http://localhost:8020/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u" \
  -F "file=@tests/fixtures/media/en_speech_15s.wav" \
  -F "model=faster-whisper" \
  -F "language=en" \
  -F "response_format=srt"
```

### 2. OneASR Extended Native API (`/v1/x/*`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/x/models` | GET | List models with full capability matrix, languages, and RAM/VRAM runtime status |
| `/v1/x/models/{model_id}/load` | POST | Manually warm up / load a model into memory |
| `/v1/x/models/{model_id}/unload` | POST | Manually unload a model to free RAM/VRAM (`?force=true` supported) |
| `/v1/x/files` | POST / GET | Upload audio/video (supports MD5 instant dedup) or list files |
| `/v1/x/files/{file_id}` | GET / DELETE | Get or delete an uploaded file asset |
| `/v1/x/audio/transcriptions` | POST / GET | Create or list async long-audio transcription tasks (supports up to 2GB) |
| `/v1/x/audio/transcriptions/{task_id}` | GET / DELETE | Query async task status/result or cancel a task |
| `/v1/x/audio/transcriptions/{task_id}/stream` | GET | Subscribe to SSE progress & segment stream of an async task |
| `/v1/x/media` | POST / GET | Submit URL parsing & background download task (yt-dlp) or list tasks |
| `/v1/x/media/{task_id}` | GET / DELETE | Query media download task status or delete task & files |
| `/v1/x/media/{task_id}/file` | GET | Download parsed media file asset |
| `/v1/x/realtime?api_key=` | WebSocket | Extended real-time streaming with sentence-level events & timestamps |
| `/v1/x/info` | GET | Query server configuration & system status |

```javascript
const ws = new WebSocket("ws://localhost:8020/v1/realtime?api_key=sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u");

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "session.update",
    session: {
      type: "transcription",
      audio: {
        input: {
          format: { type: "audio/pcm", rate: 16000 },
          transcription: { model: "xasr", language: "en" },
        },
      },
    },
  }));
};
```

---

## CLI Utilities

- **Model Management (`cli/model.py`)**:
  ```bash
  uv run python -m cli.model list
  uv run python -m cli.model pull
  uv run python -m cli.model check
  ```
- **Media Clipping (`cli/clip.py`)**:
  ```bash
  uv run python cli/clip.py input_video.mp4 120
  ```
- **Realtime Stream Simulator (`cli/stream_simulation_client.py`)**:
  ```bash
  uv run python -m cli.stream_simulation_client tests/fixtures/media/en_speech_15s.wav --model xasr
  ```

---

## Running Tests

OneASR uses a 3-tier test pyramid (`unit`, `api`, `integration`) with isolated test SQLite database (`oneasr_test.db`) and built-in **100% Public Domain** English audio/video fixtures in `tests/fixtures/media/`.

```bash
# 1. Run fast unit + API contract tests (~1.6s, no real model weights required)
uv run pytest -m "not integration" -v

# 2. Run unit tests only
uv run pytest tests/unit/ -v

# 3. Run API & WebSocket contract tests only
uv run pytest tests/api/ -v

# 4. Run real-model & end-to-end integration tests (loads real xasr, faster-whisper, qwen)
uv run pytest tests/integration/ -v -s
```

### Test Directory Structure

```text
tests/
├── conftest.py                  # Global test setup (ONEASR_TESTING=1, shared fixtures)
├── fixtures/
│   └── media/                   # Built-in 100% Public Domain speech & video fixtures
│       ├── en_speech_15s.wav    # 15s 16kHz PCM WAV speech sample
│       ├── en_speech_120s.mp3   # 120s long speech MP3 for VAD chunking
│       ├── en_video_60s.mp4     # 60s H.264+AAC MP4 video sample
│       └── README.md            # Public Domain license & Ground Truth transcript
├── helpers/
│   ├── audio_factory.py         # In-memory WAV/PCM synthesizer & fixture loader
│   └── mock_engines.py          # Standardized mock ASR engines & stream sessions
├── unit/                        # Tier 1: Fast isolated unit tests
│   ├── engines/                 # Engine & VAD toolkit unit tests
│   ├── utils/                   # Audio converter, formatting, subtitles, URL parsers
│   └── cli/                     # Model CLI downloader & shard verification tests
├── api/                         # Tier 2: FastAPI & WebSocket contract tests
│   ├── standard/                # OpenAI standard contract tests (/v1/*)
│   │   ├── test_audio.py        # /v1/audio/transcriptions (sync + SSE stream)
│   │   ├── test_models.py       # /v1/models contract tests
│   │   └── test_realtime.py     # /v1/realtime WebSocket contract tests
│   ├── x/                       # OneASR extended contract tests (/v1/x/*)
│   │   ├── test_audio.py        # /v1/x/audio/transcriptions & SSE stream tests
│   │   ├── test_files.py        # /v1/x/files upload, dedup & CRUD tests
│   │   ├── test_info.py         # /v1/x/info version & health tests
│   │   ├── test_media.py        # /v1/x/media parse & download tests
│   │   ├── test_models.py       # /v1/x/models load/unload & capabilities tests
│   │   └── test_realtime.py     # /v1/x/realtime extended WebSocket tests
│   └── test_error_format.py     # Unified OpenAI-compatible error schema tests
└── integration/                 # Tier 3: Real-model & E2E integration tests
    ├── conftest.py              # Session-scoped real media fixtures
    ├── test_local_engines.py    # Real xasr, faster-whisper & Qwen3-ASR inference benchmarks
    ├── test_e2e_api.py          # Unmocked REST + WebSocket end-to-end tests
    └── test_cloud_engines.py    # Cloud ASR provider tests (OpenAI / MiMo)
```

---

## Project Structure

```text
OneASR/
├── server/                       # Core FastAPI backend application
│   ├── main.py                   # FastAPI entry point, lifespan & idle model reaper
│   ├── api/                      # Dual-layer REST & WebSocket route controllers
│   │   ├── auth.py               # Bearer / X-API-Key authentication
│   │   ├── standard/             # OpenAI standard layer (/v1/*)
│   │   │   ├── audio.py          # POST /v1/audio/transcriptions
│   │   │   ├── models.py         # GET /v1/models, GET /v1/models/{model_id}
│   │   │   └── realtime.py       # WS /v1/realtime (OpenAI Realtime protocol)
│   │   └── x/                    # OneASR extended native layer (/v1/x/*)
│   │       ├── audio.py          # POST /v1/x/audio/transcriptions & SSE stream
│   │       ├── files.py          # POST /v1/x/files RESTful upload, dedup & CRUD
│   │       ├── info.py           # GET /v1/x/info version & status
│   │       ├── media.py          # POST /v1/x/media yt-dlp parsing & download
│   │       ├── models.py         # GET /v1/x/models & lifecycle load/unload
│   │       └── realtime.py       # WS /v1/x/realtime (sentence events & timestamps)
│   ├── core/                     # Configuration, exceptions & file storage
│   ├── db/                       # Async SQLAlchemy session & SQLite management
│   │   ├── session.py            # Session factory & WAL initialization
│   │   ├── base.py               # DeclarativeBase
│   │   └── orm_models.py         # SQLAlchemy database models
│   ├── engines/                  # ASR engine adapters & lifecycle registry
│   │   ├── base.py               # ASREngine ABC (validate_config, load, unload)
│   │   ├── registry.py           # ModelManager (keep_alive, LRU, acquire_engine)
│   │   ├── xasr_engine.py        # sherpa-onnx streaming engine
│   │   ├── whisper_engine.py     # faster-whisper engine
│   │   ├── qwen_engine.py        # Qwen3-ASR engine
│   │   ├── funasr_engine.py      # FunASR / Paraformer engine
│   │   ├── firered_engine.py     # FireRedASR engine
│   │   ├── openai_engine.py      # OpenAI cloud ASR engine
│   │   └── mimo_engine.py        # Xiaomi MiMo cloud ASR engine
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Business logic services
│   │   ├── transcription_service.py # Async task orchestrator, workers & SSE
│   │   ├── file_service.py       # Uploaded file reader & dedup
│   │   ├── media_service.py      # yt-dlp download & background workers
│   │   └── record_service.py     # Transcription records persistence
│   └── utils/                    # High-performance audio & subtitle utilities
├── cli/                          # Command-line utilities
│   ├── model.py                  # Model download, status & integrity check CLI
│   ├── clip.py                   # Media clipping utility
│   ├── converter.py              # Audio format converter
│   └── stream_simulation_client.py # WebSocket streaming test client
├── data/                         # Runtime data directory (models, uploads, downloads, DB)
│   └── models/                   # Local ASR model weights directory
├── tests/                        # 3-tier automated test suite
├── web/                          # Vue 3 frontend application
├── docs/                         # Architecture & API design documentation
├── config.yaml                   # Server, model lifecycle & provider configuration
├── pyproject.toml                # Project metadata, scripts & pytest config
└── requirements.txt              # Python dependencies
```

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
