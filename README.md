# OneASR

A unified speech recognition API that integrates multiple ASR engines.

[中文文档](README_CN.md)

## Features

- **File Recognition** — Upload audio/video files or provide a URL, get complete transcription results
- **Streaming File Recognition** — Upload files or provide a URL, receive sentence-by-sentence results via SSE
- **Real-time Streaming** — Send audio streams via WebSocket, get real-time transcription results
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server runs at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

### Frontend Setup

```bash
# 1. Navigate to web directory
cd web

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```

The frontend runs at `http://localhost:3000` and automatically proxies API requests to the backend.

### Quick Launch (Two Terminals)

**Terminal 1 - Backend:**
```bash
cd OneASR
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd OneASR/web
npm run dev
```

### Verify Installation

```bash
# Check backend health
curl http://localhost:8000/health

# List available engines
curl -H "X-API-Key: oneasr-key" http://localhost:8000/api/v1/engines
```

After startup:
- Frontend UI: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Media Clipping Tool

The project includes a media clipping tool for splitting long videos into shorter segments:

```bash
# Clip a specific duration (default 2 minutes)
python utils/clip.py input_video.mp4 120

# Auto-clip entire video into 2-minute segments
python utils/clip.py input_video.mp4
```

Python API usage:
```python
from utils.clip import MediaClipper

clipper = MediaClipper("video.mp4")
clipper.clip(start=0, duration=120, output="clip.mp4")
clips = clipper.auto_clip(clip_duration=120, output_dir="clips/")
```

### Test Script

A test script is provided to quickly verify the streaming file recognition endpoint:

```bash
cd web
node test-stream.js <audio_file_path> [engine_name]

# Examples
node test-stream.js ../test.mp3
node test-stream.js ../audio.wav faster-whisper
```

The script calls the backend SSE streaming endpoint with `X-API-Key` header and prints each recognized sentence in real-time.

## Authentication

All API endpoints (except `/health`) require an API Key via the `X-API-Key` request header.

Configure the API Key in `config.yaml`:

```yaml
api_key: oneasr-key
```

```bash
# Call API with API Key
curl -H "X-API-Key: oneasr-key" http://localhost:8000/api/v1/engines

# Upload file for recognition
curl -X POST -H "X-API-Key: oneasr-key" \
  http://localhost:8000/api/v1/transcribe/file \
  -F "file=@audio.mp3" -F "format=srt" -o subtitle.srt
```

WebSocket streaming uses query parameters (browser WebSocket API doesn't support custom headers): `ws://localhost:8000/ws/transcribe/stream?api_key=oneasr-key`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/transcribe/file` | POST | Upload file for recognition |
| `/api/v1/transcribe/url` | POST | Download from URL for recognition |
| `/api/v1/transcribe/file/stream` | POST | Upload file, SSE streaming sentence-by-sentence |
| `/api/v1/transcribe/url/stream` | POST | URL download, SSE streaming sentence-by-sentence |
| `/api/v1/engines` | GET | List available engines |
| `/api/v1/formats` | GET | List output formats |
| `/ws/transcribe/stream?api_key=` | WebSocket | Real-time streaming (WhisperLiveKit) |
| `/health` | GET | Health check |

## Streaming Recognition

Real-time speech recognition powered by [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit):

- **VAD/VAC** — Silero Voice Activity Detection, automatic speech/silence boundary detection
- **SimulStreaming** — Low-latency streaming strategy (default), or LocalAgreement high-accuracy strategy
- **Timestamp Alignment** — Each line has precise start/end timestamps
- **Speaker Diarization** — Optional speaker identification (requires additional models)
- **Multi-language** — Automatic language detection or manual specification

### WebSocket Connection

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/transcribe/stream?api_key=oneasr-key&language=zh");

// Receive transcription results
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "config") {
    console.log("Connection config:", data);
  } else if (data.type === "ready_to_stop") {
    console.log("Recognition complete");
  } else {
    // data.status: "active_transcription" | "no_audio_detected" | "error"
    // data.lines: [{speaker, text, start, end}, ...]  // Confirmed lines
    // data.buffer_transcription: "partial text..."     // Unconfirmed buffer
    console.log(data.lines);
  }
};

// Send audio data (PCM s16le 16kHz mono or other formats)
ws.send(audioChunk);

// End recognition
ws.send(new Uint8Array(0));
```

### Response Format

```json
{
  "status": "active_transcription",
  "lines": [
    {"speaker": 1, "text": "Hello world", "start": "0:00:01.00", "end": "0:00:03.00"}
  ],
  "buffer_transcription": "This is a",
  "buffer_diarization": "",
  "buffer_translation": "",
  "remaining_time_transcription": 0.0,
  "remaining_time_diarization": 0.0
}
```

| Field | Description |
|-------|-------------|
| `status` | Recognition status: `active_transcription` / `no_audio_detected` / `error` |
| `lines` | Confirmed text lines with speaker and timestamp info |
| `buffer_transcription` | Partial text being processed but not yet confirmed |
| `remaining_time_transcription` | Transcription latency in seconds |

## Output Formats

Supported output formats:

| Format | Description |
|--------|-------------|
| `text` | Plain text (default) |
| `srt` | SRT subtitle format |
| `vtt` | WebVTT format |
| `json` | JSON format (with timeline) |
| `tsv` | TSV format (tab-separated) |

**Usage Examples:**

```bash
# Upload file, return SRT subtitles
curl -X POST -H "X-API-Key: oneasr-key" "http://localhost:8000/api/v1/transcribe/file" \
  -F "file=@audio.mp3" -F "format=srt" -o subtitle.srt

# URL recognition, return JSON
curl -X POST -H "X-API-Key: oneasr-key" "http://localhost:8000/api/v1/transcribe/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/audio.mp3", "format": "json"}'
```

## SSE Streaming File Recognition

Upload audio/video files and receive sentence-by-sentence results in [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) format, ideal for real-time progress display with long audio.

### Request Examples

```bash
# Upload file, SSE streaming response
curl -N -X POST "http://localhost:8000/api/v1/transcribe/file/stream?api_key=oneasr-key" \
  -F "file=@audio.mp3"

# URL recognition, SSE streaming response
curl -N -X POST "http://localhost:8000/api/v1/transcribe/url/stream?api_key=oneasr-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/audio.mp3", "engine": "faster-whisper"}'
```

### Response Format

```
data: {"index": 0, "start": 0.0, "end": 2.5, "text": "Hello world"}

data: {"index": 1, "start": 2.5, "end": 5.1, "text": "This is a test audio"}

data: {"done": true}
```

| Field | Description |
|-------|-------------|
| `index` | Sentence index (starting from 0) |
| `start` | Start time in seconds |
| `end` | End time in seconds |
| `text` | Recognized text |
| `done` | `true` when recognition is complete |

### JavaScript Client Example

```javascript
const form = new FormData();
form.append("file", fileInput.files[0]);

const resp = await fetch("/api/v1/transcribe/file/stream", {
  method: "POST",
  headers: { "X-API-Key": "oneasr-key" },
  body: form,
});
const reader = resp.body.getReader();
const decoder = new TextDecoder();

let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });

  const lines = buffer.split("\n");
  buffer = lines.pop(); // Keep incomplete line

  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const data = JSON.parse(line.slice(6));
      if (data.done) {
        console.log("Recognition complete");
      } else {
        console.log(`[${data.start.toFixed(1)}s] ${data.text}`);
      }
    }
  }
}
```

## Configuration

Edit `config.yaml` to configure API Key and engines:

```yaml
# API Key (required for all endpoints)
api_key: oneasr-key

# Default engine
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
  wlk:
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
│   │   ├── file.py               # File/URL recognition endpoints
│   │   └── stream.py             # WebSocket streaming (WhisperLiveKit)
│   ├── core/
│   │   └── config.py             # YAML configuration management
│   ├── engines/
│   │   ├── base.py               # Engine abstract base class
│   │   ├── whisper_engine.py     # faster-whisper implementation
│   │   ├── firered_engine.py     # FireRedASR implementation
│   │   ├── wlk_engine.py         # WhisperLiveKit (streaming + file)
│   │   ├── openai_engine.py      # OpenAI Whisper API
│   │   ├── mimo_engine.py        # Xiaomi MiMo API
│   │   └── registry.py           # Engine registry (singleton)
│   ├── models/
│   │   └── schemas.py            # Pydantic data models
│   └── utils/
│       ├── download.py           # URL download utility
│       ├── format.py             # Output format conversion (SRT/VTT/JSON/TSV)
│       ├── audio.py              # Audio format conversion
│       └── vad.py                # VAD-based audio segmentation
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
├── utils/                        # Standalone utilities
│   └── clip.py                   # Media clipping tool (split videos)
├── tests/                        # Test files
├── models/                       # Model storage directory
├── config.yaml                   # API Key and engine configuration
└── requirements.txt
```

## License

MIT
