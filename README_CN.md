# OneASR

整合多种 ASR 引擎，对外提供统一的语音识别 API。

## 功能

- **文件识别** — 上传音视频文件或传入 URL，返回完整识别结果
- **流式文件识别** — 上传音视频文件或传入 URL，以 SSE 逐句返回识别结果
- **流式识别** — 通过 WebSocket 传输音频流，实时返回识别结果
- **文件上传与秒传** — 上传文件时携带 MD5 指纹，相同文件自动秒传
- **Web 管理界面** — Vue.js 前端，支持文件/URL 识别、实时流式结果展示、SRT 导出

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- FFmpeg（音频处理必需）

### 后端启动

```bash
# 1. 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 或：.venv\Scripts\activate  # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8020
```

服务运行在 `http://localhost:8020`，访问 `http://localhost:8020/docs` 查看交互式 API 文档。

### 前端启动

```bash
# 1. 进入 web 目录
cd web

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```

前端运行在 `http://localhost:3020`，自动代理 API 请求到后端。

### 一键启动（两个终端）

**终端 1 - 后端：**
```bash
cd OneASR
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8020
```

**终端 2 - 前端：**
```bash
cd OneASR/web
npm run dev
```

### 验证安装

```bash
# 检查后端健康状态
curl http://localhost:8020/health

# 列出可用引擎
curl -H "X-API-Key: oneasr-key" http://localhost:8020/api/v1/engines
```

启动后访问：
- 前端界面：`http://localhost:3020`
- API 文档：`http://localhost:8020/docs`
- 健康检查：`http://localhost:8020/health`

### 媒体截取工具

项目提供了媒体截取工具，用于将长视频分割成短片段：

```bash
# 截取指定时长（默认 2 分钟）
python cli/clip.py input_video.mp4 120

# 自动将整个视频截取成 2 分钟片段
python cli/clip.py input_video.mp4
```

Python API 使用：
```python
from cli.clip import MediaClipper

clipper = MediaClipper("video.mp4")
clipper.clip(start=0, duration=120, output="clip.mp4")
clips = clipper.auto_clip(clip_duration=120, output_dir="clips/")
```

## 认证

所有 API 接口（`/health` 除外）需要通过请求头 `X-API-Key` 传递 API Key。

API Key 在 `config.yaml` 中配置：

```yaml
api_key: oneasr-key
```

```bash
# 使用 API Key 调用接口
curl -H "X-API-Key: oneasr-key" http://localhost:8020/api/v1/engines

# 上传文件识别
curl -X POST -H "X-API-Key: oneasr-key" \
  http://localhost:8020/api/v1/transcribe/file \
  -F "file=@audio.mp3" -F "format=srt" -o subtitle.srt
```

WebSocket 流式接口通过查询参数传递（浏览器 WebSocket API 不支持自定义请求头）：`ws://localhost:8020/ws/transcribe/stream?api_key=oneasr-key`

## API 接口

### 统一 API（兼容 OpenAI 格式）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/audio/transcriptions` | POST | 创建转录（文件上传或 file_uuid） |
| `/api/v1/audio/transcriptions/stream` | POST | 创建流式转录（SSE） |
| `/api/v1/audio/models` | GET | 列出可用模型 |
| `/api/v1/files/upload` | POST | 上传文件（支持 MD5 秒传） |
| `/api/v1/files/list` | GET | 列出所有已上传文件 |
| `/api/v1/files/{file_id}` | GET | 获取文件信息 |
| `/api/v1/files/{file_id}` | DELETE | 删除已上传文件 |
| `/health` | GET | 健康检查 |

### WebSocket 流式

| 接口 | 方法 | 说明 |
|------|------|------|
| `/ws/transcribe/stream?api_key=` | WebSocket | 流式识别（基于 WhisperLiveKit） |

## 文件上传与秒传（MD5 去重）

上传文件时可携带 MD5 指纹，实现重复文件秒传：

```bash
# 首次上传：文件保存并写入数据库
curl -X POST -H "X-API-Key: oneasr-key" \
  "http://localhost:8020/api/v1/files/upload?file_md5=abc123&file_size=1024000" \
  -F "file=@audio.mp3"
# 响应: {"duplicate": false, "file_id": "uuid-1", ...}

# 重复文件秒传：直接返回已有 file_id（不重新上传）
curl -X POST -H "X-API-Key: oneasr-key" \
  "http://localhost:8020/api/v1/files/upload?file_md5=abc123&file_size=1024000" \
  -F "file=@audio_copy.mp3"
# 响应: {"duplicate": true, "file_id": "uuid-1", ...}
```

## 流式识别

基于 [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) 实现的实时语音识别，支持：

- **VAD/VAC** — Silero 语音活动检测，自动识别语音/静音边界
- **SimulStreaming** — 低延迟流式策略（默认），或 LocalAgreement 高准确策略
- **时间戳对齐** — 每行文本附带精确的开始/结束时间
- **说话人分离** — 可选的说话人识别（需额外模型）
- **多语言** — 自动语言检测或指定语言

### WebSocket 连接

```javascript
const ws = new WebSocket("ws://localhost:8020/ws/transcribe/stream?api_key=oneasr-key&language=zh");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "config") {
    console.log("连接配置:", data);
  } else if (data.type === "ready_to_stop") {
    console.log("识别完成");
  } else {
    console.log(data.lines);
  }
};

ws.send(audioChunk);
ws.send(new Uint8Array(0));
```

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 只运行 API 接口测试（快速，无外部依赖）
python -m pytest tests/api/ -v

# 只运行通用/单元测试
python -m pytest tests/general/ -v

# 运行单个测试文件
python -m pytest tests/api/test_file_upload.py -v

# 跳过集成测试（需要真实音频文件和运行中的服务）
python -m pytest tests/ -m "not integration" -v

# 简短错误输出
python -m pytest tests/api/ -v --tb=short
```

### 测试目录结构

```
tests/
├── conftest.py                  # 共享 fixtures（client、数据库清理）
├── api/                         # API 接口测试（使用 TestClient）
│   ├── test_audio.py            # 音频转录 API
│   ├── test_file_upload.py      # 文件上传、MD5 秒传、CRUD
│   ├── test_models.py           # 模型列表、格式参数
│   └── test_streaming.py        # SSE 流式转录
└── general/                     # 单元测试 & 集成测试
    ├── test_format.py           # 输出格式转换（SRT/VTT/JSON/TSV）
    ├── test_engines.py          # 引擎加载与转录
    ├── test_mimo.py             # MiMo 音频理解引擎
    ├── test_stream_websocket.py # WebSocket 流式集成测试
    └── test_stream_whisperlivekit.py  # WhisperLiveKit 引擎测试
```

## 配置

编辑 `config.yaml` 配置 API Key 和引擎：

```yaml
# API Key（所有接口必须携带此 key）
api_key: oneasr-key

# 默认 Provider
default_provider: whisper1

# 模型根目录（取消注释并指定路径可强制使用本地模型）
# model_dir: ./models

# Provider 配置
providers:
  whisper1:
    engine: faster-whisper
    type: local
    model_name: medium
    device: cpu
    compute_type: int8
    max_duration: null

  mimo:
    engine: mimo
    type: cloud
    model_name: mimo-audio
    api_key:   # 小米 MiMo API Key
    base_url:

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

## 项目结构

```
OneASR/
├── app/                          # 后端应用
│   ├── main.py                   # FastAPI 入口
│   ├── api/
│   │   ├── auth.py               # API Key 验证
│   │   ├── audio.py              # 兼容 OpenAI 格式的音频 API
│   │   ├── models.py             # 引擎/模型信息 API
│   │   ├── upload.py             # 文件上传与管理（MD5 秒传）
│   │   └── stream.py             # WebSocket 流式识别（WhisperLiveKit）
│   ├── core/
│   │   ├── config.py             # YAML 配置管理
│   │   └── file_storage.py       # 文件存储工具
│   ├── db/
│   │   ├── base.py               # SQLAlchemy 声明基类
│   │   └── session.py            # 数据库引擎、会话工厂、初始化
│   ├── engines/
│   │   ├── base.py               # 引擎抽象基类
│   │   ├── whisper_engine.py     # faster-whisper 实现
│   │   ├── firered_engine.py     # FireRedASR 实现
│   │   ├── whisperlivekit_engine.py  # WhisperLiveKit（流式+文件）
│   │   ├── openai_engine.py      # OpenAI Whisper API
│   │   ├── mimo_engine.py        # 小米 MiMo API
│   │   └── registry.py           # 引擎注册中心（单例模式）
│   ├── models/
│   │   ├── schemas.py            # Pydantic 数据模型
│   │   └── orm_models.py         # SQLAlchemy ORM 模型
│   └── utils/
│       ├── audio.py              # 音频格式转换
│       ├── download.py           # URL 下载工具
│       ├── format.py             # 输出格式转换（SRT/VTT/JSON/TSV）
│       ├── stream.py             # PCM 流式工具
│       └── vad.py                # VAD 音频切分
├── cli/                          # 命令行工具
│   ├── clip.py                   # 媒体截取工具
│   ├── converter.py              # 音频转换器
│   └── whisperlivekit_client.py     # WhisperLiveKit WebSocket 客户端
├── web/                          # Vue.js 前端
│   ├── src/
│   │   ├── api/index.js          # API 服务层（SSE 流式）
│   │   ├── router/index.js       # Vue Router 配置
│   │   ├── views/
│   │   │   ├── Layout.vue        # 主布局（侧边栏+设置）
│   │   │   └── Transcribe.vue    # 语音识别页面
│   │   └── assets/main.css       # 全局样式
│   ├── index.html
│   ├── vite.config.js            # Vite 配置（含 API 代理）
│   └── package.json
├── tests/                        # 测试套件
│   ├── conftest.py               # 共享 fixtures
│   ├── api/                      # API 接口测试
│   └── general/                  # 单元测试 & 集成测试
├── models/                       # 模型存放目录
├── data/                         # SQLite 数据库（自动创建）
├── uploads/                      # 上传文件存储
├── config.yaml                   # API Key 和引擎配置
└── requirements.txt
```
