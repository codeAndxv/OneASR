# OneASR

整合多种 ASR 引擎，对外提供统一的语音识别 API。

## 功能

- **文件识别** — 上传音视频文件或传入 URL，返回完整识别结果
- **流式文件识别** — 上传音视频文件或传入 URL，以 SSE 逐句返回识别结果
- **流式识别** — 通过 WebSocket 传输音频流，实时返回识别结果
- **Web 管理界面** — Vue.js 前端，支持文件/URL 识别、实时流式结果展示、SRT 导出

## 快速开始

### 后端

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

### 前端

```bash
cd web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在 `http://localhost:3000`，通过 Vite 代理转发 API 请求到后端。

### 一键启动（前后端分离，两个终端）

```bash
# 终端 1：启动后端
cd OneASR
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：启动前端
cd OneASR/web
npm run dev
```

启动后访问：
- 前端界面：`http://localhost:3000`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 测试接口

项目提供了一个测试脚本，可快速验证文件识别流式接口是否正常工作：

```bash
cd web
node test-stream.js <音频文件路径> [引擎名称]

# 示例
node test-stream.js ../test.mp3
node test-stream.js ../audio.wav whisper
```

脚本会通过 `X-API-Key` 请求头调用后端 SSE 流式接口，实时打印每句识别结果。

## 认证

所有 API 接口（`/health` 除外）需要通过请求头 `X-API-Key` 传递 API Key。

API Key 在 `config.yaml` 中配置：

```yaml
api_key: oneasr-key
```

```bash
# 使用 API Key 调用接口
curl -H "X-API-Key: oneasr-key" http://localhost:8000/api/v1/engines

# 上传文件识别
curl -X POST -H "X-API-Key: oneasr-key" \
  http://localhost:8000/api/v1/transcribe/file \
  -F "file=@audio.mp3" -F "format=srt" -o subtitle.srt
```

WebSocket 流式接口通过查询参数传递（浏览器 WebSocket API 不支持自定义请求头）：`ws://localhost:8000/ws/transcribe/stream?api_key=oneasr-key`

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/transcribe/file` | POST | 上传文件识别 |
| `/api/v1/transcribe/url` | POST | URL 下载识别 |
| `/api/v1/transcribe/file/stream` | POST | 上传文件，SSE 流式逐句返回 |
| `/api/v1/transcribe/url/stream` | POST | URL 下载，SSE 流式逐句返回 |
| `/api/v1/engines` | GET | 列出可用引擎 |
| `/api/v1/formats` | GET | 列出输出格式 |
| `/ws/transcribe/stream?api_key=` | WebSocket | 流式识别（基于 WhisperLiveKit） |
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
const ws = new WebSocket("ws://localhost:8000/ws/transcribe/stream?api_key=oneasr-key&language=zh");

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
curl -X POST -H "X-API-Key: oneasr-key" "http://localhost:8000/api/v1/transcribe/file" \
  -F "file=@audio.mp3" -F "format=srt" -o subtitle.srt

# URL 识别，返回 JSON
curl -X POST -H "X-API-Key: oneasr-key" "http://localhost:8000/api/v1/transcribe/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/audio.mp3", "format": "json"}'
```

## SSE 流式文件识别

上传音视频文件后，以 [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) 格式逐句返回识别结果，适合长音频的实时进度展示。

### 请求示例

```bash
# 上传文件，SSE 流式返回
curl -N -X POST "http://localhost:8000/api/v1/transcribe/file/stream?api_key=oneasr-key" \
  -F "file=@audio.mp3"

# URL 识别，SSE 流式返回
curl -N -X POST "http://localhost:8000/api/v1/transcribe/url/stream?api_key=oneasr-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/audio.mp3", "engine": "whisper"}'
```

### 响应格式

```
data: {"index": 0, "start": 0.0, "end": 2.5, "text": "你好世界"}

data: {"index": 1, "start": 2.5, "end": 5.1, "text": "这是一段测试音频"}

data: {"done": true}
```

| 字段 | 说明 |
|------|------|
| `index` | 句子序号（从 0 开始） |
| `start` | 开始时间（秒） |
| `end` | 结束时间（秒） |
| `text` | 识别文本 |
| `done` | 为 `true` 时表示识别完成 |

### JavaScript 客户端示例

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
  buffer = lines.pop(); // 保留未完成的行

  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const data = JSON.parse(line.slice(6));
      if (data.done) {
        console.log("识别完成");
      } else {
        console.log(`[${data.start.toFixed(1)}s] ${data.text}`);
      }
    }
  }
}
```

## 配置

编辑 `config.yaml` 配置 API Key 和引擎：

```yaml
# API Key（所有接口必须携带此 key）
api_key: oneasr-key

# 默认引擎
default_engine: whisper

engines:
  whisper:
    type: local
    model_name: base
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

## 项目结构

```
OneASR/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/
│   │   ├── auth.py          # API Key 验证
│   │   ├── file.py          # 文件识别接口
│   │   └── stream.py        # 流式识别接口（WhisperLiveKit）
│   ├── core/config.py       # 配置管理
│   ├── engines/
│   │   ├── base.py          # 引擎抽象基类
│   │   ├── whisper_engine.py # faster-whisper 实现
│   │   ├── firered_engine.py # FireRedASR 实现
│   │   ├── wlk_engine.py    # WhisperLiveKit 实现（流式+文件）
│   │   └── registry.py      # 引擎注册中心
│   ├── models/schemas.py    # 数据模型
│   └── utils/
│       ├── download.py      # URL 下载工具
│       └── format.py        # 输出格式转换
├── web/                     # Vue.js 前端
│   ├── src/
│   │   ├── api/index.js     # API 服务层
│   │   ├── router/index.js  # 路由配置
│   │   ├── views/
│   │   │   ├── Layout.vue   # 主布局（侧边栏+内容区）
│   │   │   └── Transcribe.vue # 语音识别页面
│   │   └── assets/main.css  # 全局样式
│   ├── index.html
│   ├── vite.config.js       # Vite 配置（含 API 代理）
│   └── package.json
├── models/                  # 模型存放目录
├── config.yaml              # API Key 和引擎配置
└── requirements.txt
```
