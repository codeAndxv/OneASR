# OneASR

整合多种 ASR 引擎，对外提供统一的语音识别 API。

## 功能

- **文件识别** — 上传音视频文件或传入 URL，返回完整识别结果
- **流式识别** — 通过 WebSocket 传输音频流，实时返回识别结果

## 快速开始

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --reload
```

服务默认运行在 `http://localhost:8000`，访问 `/docs` 查看 API 文档。

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/transcribe/file` | POST | 上传文件识别 |
| `/api/v1/transcribe/url` | POST | URL 下载识别 |
| `/api/v1/engines` | GET | 列出可用引擎 |
| `/api/v1/formats` | GET | 列出输出格式 |
| `/ws/transcribe/stream` | WebSocket | 流式识别（基于 WhisperLiveKit） |
| `/health` | GET | 健康检查 |

## 流式识别

基于 [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) 实现的实时语音识别，支持：

- **VAD/VAC** — Silero 语音活动检测，自动识别语音/静音边界
- **SimulStreaming** — 低延迟流式策略（默认），或 LocalAgreement 高准确策略
- **时间戳对齐** — 每行文本附带精确的开始/结束时间
- **说话人分离** — 可选的说话人识别（需额外模型）
- **多语言** — 自动语言检测或指定语言

### WebSocket 连接

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/transcribe/stream?language=zh");

// 接收识别结果
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "config") {
    console.log("连接配置:", data);
  } else if (data.type === "ready_to_stop") {
    console.log("识别完成");
  } else {
    // data.status: "active_transcription" | "no_audio_detected" | "error"
    // data.lines: [{speaker, text, start, end}, ...]  // 已确认的行
    // data.buffer_transcription: "部分文本..."         // 未确认的缓冲区
    console.log(data.lines);
  }
};

// 发送音频数据（PCM s16le 16kHz mono 或其他格式）
ws.send(audioChunk);

// 结束识别
ws.send(new Uint8Array(0));
```

### 响应格式

```json
{
  "status": "active_transcription",
  "lines": [
    {"speaker": 1, "text": "你好世界", "start": "0:00:01.00", "end": "0:00:03.00"}
  ],
  "buffer_transcription": "这是一段",
  "buffer_diarization": "",
  "buffer_translation": "",
  "remaining_time_transcription": 0.0,
  "remaining_time_diarization": 0.0
}
```

| 字段 | 说明 |
|------|------|
| `status` | 识别状态：`active_transcription` / `no_audio_detected` / `error` |
| `lines` | 已确认的文本行，包含说话人、时间戳 |
| `buffer_transcription` | 正在处理中但尚未确认的部分文本 |
| `remaining_time_transcription` | 转录延迟（秒） |

## 输出格式

支持以下输出格式：

| 格式 | 说明 |
|------|------|
| `text` | 纯文本（默认） |
| `srt` | SRT 字幕格式 |
| `vtt` | WebVTT 字幕格式 |
| `json` | JSON 格式（含时间轴） |
| `tsv` | TSV 格式（制表符分隔） |

**使用示例：**

```bash
# 上传文件，返回 SRT 字幕
curl -X POST http://localhost:8000/api/v1/transcribe/file \
  -F "file=@audio.mp3" -F "format=srt" -o subtitle.srt

# URL 识别，返回 JSON
curl -X POST http://localhost:8000/api/v1/transcribe/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/audio.mp3", "format": "json"}'
```

## 配置

编辑 `config.yaml` 配置引擎：

```yaml
default_engine: whisper
model_dir: ./models

engines:
  whisper:
    type: local
    model_name: base
    device: cpu
    compute_type: int8
  firered:
    type: local
    model_name: FireRedASR-AED
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
    pcm_input: false
```

## 项目结构

```
app/
├── main.py              # FastAPI 入口
├── api/
│   ├── file.py          # 文件识别接口
│   └── stream.py        # 流式识别接口（WhisperLiveKit）
├── core/config.py       # 配置管理
├── engines/
│   ├── base.py          # 引擎抽象基类
│   ├── whisper_engine.py # faster-whisper 实现
│   ├── firered_engine.py # FireRedASR 实现
│   ├── wlk_engine.py    # WhisperLiveKit 实现（流式+文件）
│   └── registry.py      # 引擎注册中心
├── models/schemas.py    # 数据模型
└── utils/
    ├── download.py      # URL 下载工具
    └── format.py        # 输出格式转换
models/                  # 模型存放目录
config.yaml              # 引擎配置文件
```
