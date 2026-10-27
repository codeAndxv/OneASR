# OneASR

<p align="center">
  <img src="./docs/assets/OneASR.svg" width="128" alt="OneASR Logo">
</p>

整合多种本地与云端 ASR 引擎、具备智能模型生命周期管理的统一语音识别 API 网关。

[English Documentation](README.md)

## 核心特性

- **Ollama 风格零界面常驻架构** — 原生系统托盘常驻伴侣（内存占用低于 5MB），配合终端命令行（`oneasr`）与标准化 REST/WebSocket API
- **开箱即用独立打包** — 针对 macOS、Windows、Linux 平台提供全量自包含安装包，内置隔离 Python 3.12 运行时、硬件加速环境（MPS/CUDA）与 FFmpeg，无需手动配置 Python 或 PyTorch
- **统一 OpenAI 兼容音频接口** — 支持上传音视频文件、指定 `file_uuid` 或远程 `url`，输出格式涵盖 `json`、`verbose_json`、`text`、`srt`、`vtt`、`tsv`
- **SSE 流式文件识别** — 基于 Silero VAD 智能切片，以 Server-Sent Events (`stream=true`) 逐句实时推送长音频识别结果
- **WebSocket 实时流式听写** — 基于 `xasr` (`sherpa-onnx` Zipformer2 transducer) 提供毫秒级低延迟实时语音流识别（兼容 `/v1/realtime` 与扩展协议 `/v1/realtime_ext`）
- **Ollama 风格模型生命周期管理** — 支持启动预热 (`preload`)、按需懒加载、空闲超时自动卸载 (`keep_alive`)、最大常驻模型数 LRU 淘汰 (`max_loaded_models`)、活跃任务引用计数保护，以及手动 `/load` 与 `/unload` 接口
- **统一模型管理 CLI (`oneasr`)** — 一键查看模型状态、从 ModelScope / HuggingFace 下载并自动存放至 `~/.oneasr/models`
- **文件秒传与大文件异步任务** — 支持 MD5 指纹秒传去重、音视频 URL 解析下载（`yt-dlp`）及大文件后台异步转录队列

---

## 下载与安装

使用 OneASR 最简捷的方式是直接从 **[GitHub Releases](https://github.com/codeAndxv/OneASR/releases)** 下载对应平台的自包含独立安装包：

| 平台 | 安装包 | 架构 | 算力加速支持 |
| :--- | :--- | :--- | :--- |
| **macOS** | `OneASR-macos-arm64.dmg` | Apple Silicon (M1/M2/M3/M4) | Metal Performance Shaders (MPS) 原生加速 |
| **Windows** | `OneASR-windows-x64-setup.exe` | x86_64 | NVIDIA CUDA 12 独显加速 / CPU 自动回退 |
| **Linux** | `oneasr-linux-amd64.tar.gz` | x86_64 | NVIDIA CUDA 12 独显加速 / CPU 自动回退 |

*所有独立安装包均内置隔离 Python 3.12 运行时、算力加速版 PyTorch 以及静态 FFmpeg 可执行文件，用户电脑无需预装任何 Python、pip 或 CUDA 环境。*

---

## 快速开始（开发者源码运行）

### 环境要求

- Python 3.12+（推荐使用 [uv](https://docs.astral.sh/uv/) 管理）
- Node.js 18+
- FFmpeg（音视频解码与重采样必需）

### 后端启动

```bash
# 1. 创建虚拟环境
uv venv --python 3.12

# 2. 安装依赖
uv pip install -r requirements.txt
# 或安装含开发/测试依赖：
uv pip install -e ".[dev]"

# 3. 一键下载 config.yaml 中已启用的本地模型（自动优选 ModelScope / HF-Mirror）
uv run python -m cli.model pull

# 4. 启动服务
uv run uvicorn server.main:app --host 0.0.0.0 --port 8020
```

服务运行在 `http://localhost:8020`，访问 `http://localhost:8020/docs` 查看交互式 API 文档。

### 终端命令行工具 (`oneasr` CLI)

OneASR 提供了类似 Ollama 的极客终端命令行工具，支持模型管理、状态监控与快捷转录测试：

```bash
# 查看所有可用模型、本地就绪状态与磁盘占用
oneasr list

# 一键拉取模型（带实时网速与进度条）
oneasr pull sensevoice-small
oneasr pull whisper-large-v3-turbo

# 查看当前驻留在显存/内存中的活跃模型
oneasr ps

# 查看硬件加速驱动 (MPS/CUDA/CPU) 与存储路径信息
oneasr info

# 在终端直接测试转录音频文件
oneasr run sensevoice-small /path/to/sample.wav

# 删除本地权重以释放磁盘空间
oneasr rm whisper-large-v3-turbo

# 在前台启动守护服务进程
oneasr serve --host 127.0.0.1 --port 8020
```

### 原生桌面伴侣应用 (`OneASR.app`)

完全对标 Ollama，OneASR 提供了纯原生、零界面的系统托盘伴侣。它安安静静常驻在 macOS 顶部菜单栏，自动守护管理后端进程，常驻内存仅占约 3~5MB：

```bash
cd desktop
npm run build
```

打包产物 `OneASR.app` 与 `OneASR_<版本>_<架构>.dmg` 位于 `desktop/src-tauri/target/debug/bundle/`。

### 客户端接入 (DuRT 与 OpenAI SDK)

OneASR 默认在本地 `http://127.0.0.1:8020` 运行。任何兼容 OpenAI 协议的客户端（包括 DuRT 客户端、Python 脚本或自动化工具）均可无缝对接：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8020/v1",
    api_key="sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u"
)

with open("audio.wav", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="sensevoice-small",
        file=f
    )
print(transcript.text)
```

### 验证安装

```bash
# 检查后端健康状态
curl http://localhost:8020/health

# 列出已启用模型（标准 OpenAI 格式）
curl -H "Authorization: Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u" \
  http://localhost:8020/v1/models

# 列出模型完整能力矩阵与运行时内存状态（OneASR 扩展原生接口）
curl -H "Authorization: Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u" \
  http://localhost:8020/v1/x/models
```

---

## 模型下载与管理指南

OneASR 默认将所有本地模型统一存放在 `data/models/` 目录下。推荐使用内置的 `cli.model` 工具进行管理。

### 1. 推荐方式：使用内置 CLI 工具 (`cli.model`)

`cli.model` 会自动读取 `config.yaml` 中的模型配置与路径，支持 **ModelScope -> HF-Mirror -> HuggingFace** 自动降级、断点续传、子目录自动提取（如 `xasr`）以及权重分片完整性校验：

```bash
# 1. 查看所有本地模型的状态（Ready / Incomplete / Missing）、启用状态与磁盘占用
uv run python -m cli.model list

# 2. 一键下载 config.yaml 中所有已启用 (enable: true) 且缺失的模型
uv run python -m cli.model pull

# 3. 按名称下载指定模型（即使 enable: false 也可提前下载）
uv run python -m cli.model pull xasr faster-whisper
uv run python -m cli.model pull qwen --include-aligner

# 4. 下载全部配置的本地模型，或指定下载源 / 强制重下
uv run python -m cli.model pull --all --source modelscope
uv run python -m cli.model pull faster-whisper --source hf-mirror --force

# 5. 离线校验已启用模型的文件完整性（可用于 Docker / CI 启动前检查）
uv run python -m cli.model check
```

### 2. 手动使用 Hugging Face / ModelScope CLI 下载（可选）

如果希望手动执行下载命令，请在 `OneASR/` 根目录下运行：

- **① X-ASR（`sherpa-onnx` 流式实时模型）**：
  ```bash
  modelscope download --model Gilgamesh-J/X-ASR-zh-en \
    --include "deployment/models/chunk-160ms-model/*" \
    --local_dir data/models
  mv data/models/deployment/models/chunk-160ms-model data/models/chunk-160ms-model
  rm -rf data/models/deployment
  ```
- **② Faster-Whisper（`medium` / `large-v3`）**：
  ```bash
  modelscope download --model Systran/faster-whisper-medium --local_dir data/models/faster-whisper-medium
  # 或使用 hf:
  hf download Systran/faster-whisper-medium --local-dir data/models/faster-whisper-medium
  ```
- **③ Qwen3-ASR（主模型与 `ForcedAligner` 时间戳对齐模型）**：
  ```bash
  modelscope download --model Qwen/Qwen3-ASR-1.7B --local_dir data/models/Qwen3-ASR-1.7B
  modelscope download --model Qwen/Qwen3-ForcedAligner-0.6B --local_dir data/models/Qwen3-ForcedAligner-0.6B
  ```
- **④ FunASR（`iic/SenseVoiceSmall` + `fsmn-vad`）**：
  ```bash
  modelscope download --model iic/SenseVoiceSmall --local_dir data/models/SenseVoiceSmall
  modelscope download --model iic/speech_fsmn_vad_zh-cn-16k-common-pytorch --local_dir data/models/speech_fsmn_vad_zh-cn-16k-common-pytorch
  ```

---

## 配置与模型生命周期管理 (`config.yaml`)

OneASR 根据 `model_name`（`Org/Repo-Name`）自动推导 `data/models/<Repo-Name>` 本地路径，并内置了 Ollama 风格的模型生命周期管理器（`model_manager`），避免多个大模型同时常驻撑爆内存：

- **流式小模型（如 `xasr`）**：默认 `preload: true`、`keep_alive: -1`（启动即预热并常驻内存，确保实时语音 0 冷启动延迟）。
- **离线大模型（如 `faster-whisper`、`qwen`、`funasr`）**：默认 `preload: false`、`keep_alive: 600`（启动时仅零内存校验路径，首次请求时按需加载，空闲 10 分钟后自动卸载释放 RAM/VRAM；当同时加载模型数达到 `max_loaded_models` 上限时，自动按 LRU 淘汰最久未使用的空闲模型）。

```yaml
# API Key（所有接口必须携带此 key）
api_key: sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u

# 模型生命周期与内存管理配置
model_manager:
  default_keep_alive: 600        # 默认空闲存活时长（秒，支持 "10m" / 600 / -1 常驻 / 0 用完即焚）
  max_loaded_models: 2           # 最大同时驻留内存的非常驻本地模型数（超出自动按 LRU 释放）
  cleanup_interval: 30           # 后台空闲模型回收巡检间隔（秒）

# ASR Toolkit 全局切片与 VAD 配置
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

# 本地模型配置 (local-models)
local-models:
  xasr-zh-en:
    enable: true
    driver: xasr
    preload: true                # 启动即预热
    keep_alive: -1               # -1 永驻内存
    load:
      model_name: Gilgamesh-J/X-ASR-zh-en
      provider: cpu
      sample_rate: 16000

  whisper-medium:
    enable: true
    driver: whisper
    preload: false               # 按需懒加载
    keep_alive: 600              # 空闲 10 分钟自动卸载
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

## API 接口一览

所有 API 接口（`/health` 除外）均需通过请求头 `Authorization: Bearer <api_key>` 或 `X-API-Key: <api_key>` 进行认证。

### 1. OpenAI 标准接口 (`/v1/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/models` | GET | 列出已启用模型（标准 OpenAI 格式） |
| `/v1/models/{model_id}` | GET | 查询指定模型详情（标准 OpenAI 格式） |
| `/v1/audio/transcriptions` | POST | 音视频同步转录（支持上传 `file`、传 `file_uuid` 或 `url`；传 `stream=true` 开启 SSE 流式返回） |
| `/v1/realtime?api_key=` | WebSocket | 实时语音流转录（兼容 OpenAI Realtime Transcription 协议） |
| `/health` | GET | 服务健康检查 |

```bash
# 上传本地音频/视频文件识别并输出 SRT 字幕
curl -X POST http://localhost:8020/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u" \
  -F "file=@tests/fixtures/media/en_speech_15s.wav" \
  -F "model=faster-whisper" \
  -F "language=en" \
  -F "response_format=srt"
```

### 2. OneASR 扩展原生接口 (`/v1/x/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/x/models` | GET | 列出所有模型完整能力矩阵、支持语言及 RAM/VRAM 运行时状态 |
| `/v1/x/models/{model_id}/load` | POST | 手动预热/加载指定模型进内存 |
| `/v1/x/models/{model_id}/unload` | POST | 手动卸载指定模型释放内存（支持 `?force=true`） |
| `/v1/x/files` | POST / GET | 上传音视频（支持 MD5 秒传去重）或分页查询文件列表 |
| `/v1/x/files/{file_id}` | GET / DELETE | 查询文件资产详情或删除文件 |
| `/v1/x/audio/transcriptions` | POST / GET | 创建或查询大文件后台异步转录任务（支持最大 2GB 音视频） |
| `/v1/x/audio/transcriptions/{task_id}` | GET / DELETE | 查询异步任务状态/结果，或取消任务 |
| `/v1/x/audio/transcriptions/{task_id}/stream` | GET | 通过 SSE 订阅异步任务的实时分段识别流与进度 |
| `/v1/x/media` | POST / GET | 提交媒体 URL 解析与后台下载任务（yt-dlp），或查询任务列表 |
| `/v1/x/media/{task_id}` | GET / DELETE | 查询下载任务状态，或删除任务与本地文件 |
| `/v1/x/media/{task_id}/file` | GET | 下载解析完成的本地音视频文件 |
| `/v1/x/realtime?api_key=` | WebSocket | 扩展实时语音流识别（支持多句精确起止时间戳、心跳与端点控制） |
| `/v1/x/info` | GET | 查询系统配置、引擎状态与全局环境信息 |

---

## CLI 命令行工具

- **模型管理 (`cli/model.py`)**：
  ```bash
  uv run python -m cli.model list
  uv run python -m cli.model pull
  uv run python -m cli.model check
  ```
- **音视频截取 (`cli/clip.py`)**：
  ```bash
  uv run python cli/clip.py input_video.mp4 120
  ```
- **实时流式客户端模拟器 (`cli/stream_simulation_client.py`)**：
  ```bash
  uv run python -m cli.stream_simulation_client tests/fixtures/media/en_speech_15s.wav --model xasr
  ```

---

## 运行测试

OneASR 采用三层测试金字塔架构（`unit`、`api`、`integration`），测试环境自动隔离使用独立的 `oneasr_test.db`，并在 `tests/fixtures/media/` 内置了 **100% Public Domain（公有领域无版权限制）** 的标准英文音频与 MP4 视频样本，**完全离线可运行**。

```bash
# 1. 运行全部快速测试（单元测试 + API 契约测试，约 1.6 秒完成，无需加载真实大模型）
uv run pytest -m "not integration" -v

# 2. 仅运行单元测试
uv run pytest tests/unit/ -v

# 3. 仅运行 API 与 WebSocket 契约测试
uv run pytest tests/api/ -v

# 4. 运行真实模型与端到端集成测试（真实加载 xasr、faster-whisper、Qwen3-ASR 进行音视频转录）
uv run pytest tests/integration/ -v -s
```

### 测试目录结构

```text
tests/
├── conftest.py                  # 全局测试配置（ONEASR_TESTING=1、共享轻量 fixtures）
├── fixtures/
│   └── media/                   # 仓库内置 100% Public Domain 无版权测试音频与视频
│       ├── en_speech_15s.wav    # 15 秒 16kHz 单声道 WAV 英文演讲样本
│       ├── en_speech_120s.mp3   # 120 秒（2 分钟）长语音 MP3（用于 VAD 切片与长字幕测试）
│       ├── en_video_60s.mp4     # 60 秒（1 分钟）H.264+AAC MP4 视频样本
│       └── README.md            # Public Domain 版权说明与原文对照 (Ground Truth)
├── helpers/
│   ├── audio_factory.py         # 内存 WAV/PCM 合成器与本地测试媒体加载器
│   └── mock_engines.py          # 标准化模拟引擎与流式会话工厂
├── unit/                        # 第一层：快速隔离单元测试
│   ├── engines/                 # 引擎适配器与 VAD Toolkit 单元测试
│   ├── utils/                   # 音频格式转换、字幕分段、字幕生成器与 URL 解析测试
│   └── cli/                     # 模型 CLI 下载器与分片校验测试
├── api/                         # 第二层：FastAPI 路由与 WebSocket 协议契约测试
│   ├── standard/                # OpenAI 标准兼容接口测试 (/v1/*)
│   │   ├── test_audio.py        # /v1/audio/transcriptions (同步与 SSE 流式测试)
│   │   ├── test_models.py       # /v1/models 接口契约测试
│   │   └── test_realtime.py     # /v1/realtime WebSocket 契约测试
│   ├── x/                       # OneASR 扩展原生接口测试 (/v1/x/*)
│   │   ├── test_audio.py        # /v1/x/audio/transcriptions 及 SSE 流式识别测试
│   │   ├── test_files.py        # /v1/x/files 上传、秒传与 CRUD 契约测试
│   │   ├── test_info.py         # /v1/x/info 协议版本与服务信息测试
│   │   ├── test_media.py        # /v1/x/media 媒体 URL 解析与下载任务测试
│   │   ├── test_models.py       # /v1/x/models 能力查询与模型生命周期测试
│   │   └── test_realtime.py     # /v1/x/realtime 扩展 WebSocket 实时协议测试
│   └── test_error_format.py     # 统一 OpenAI 兼容错误响应格式测试
└── integration/                 # 第三层：真实模型加载与全链路端到端集成测试
    ├── conftest.py              # Session 级真实音频/视频 fixtures
    ├── test_local_engines.py    # 真实 xasr、faster-whisper、Qwen3-ASR 加载与推理基准测试
    ├── test_e2e_api.py          # 无 Mock 的 REST + WebSocket 端到端集成测试
    └── test_cloud_engines.py    # 云端 ASR 引擎集成测试 (OpenAI)
```

---

## 项目结构

```text
OneASR/
├── server/                       # FastAPI 后端核心应用
│   ├── main.py                   # 应用入口、Lifespan 预热与后台空闲模型回收器
│   ├── api/                      # 双层 REST 与 WebSocket 路由控制器
│   │   ├── auth.py               # Bearer / X-API-Key 鉴权依赖
│   │   ├── standard/             # OpenAI 标准兼容层 (/v1/*)
│   │   │   ├── audio.py          # POST /v1/audio/transcriptions
│   │   │   ├── models.py         # GET  /v1/models, GET /v1/models/{id}
│   │   │   └── realtime.py       # WS   /v1/realtime (OpenAI Realtime 协议)
│   │   └── x/                    # OneASR 扩展原生层 (/v1/x/*)
│   │       ├── audio.py          # POST /v1/x/audio/transcriptions & SSE 流
│   │       ├── files.py          # POST /v1/x/files RESTful 上传、秒传与文件资产 CRUD
│   │       ├── info.py           # GET  /v1/x/info 协议版本与服务状态
│   │       ├── media.py          # POST /v1/x/media 媒体 URL 解析与 yt-dlp 下载
│   │       ├── models.py         # GET  /v1/x/models 能力矩阵与生命周期 load/unload
│   │       └── realtime.py       # WS   /v1/x/realtime 扩展实时听写 (sentence 事件与时间戳)
│   ├── core/                     # 配置解析、统一异常与文件存储管理
│   ├── db/                       # 异步 SQLAlchemy 会话与 SQLite 数据库初始化
│   │   ├── session.py            # Session 工厂与 WAL 初始化
│   │   ├── base.py               # DeclarativeBase 声明基类
│   │   └── orm_models.py         # SQLAlchemy ORM 数据库实体模型
│   ├── engines/                  # ASR 引擎适配器与模型生命周期注册中心
│   │   ├── base.py               # ASREngine 抽象基类 (validate_config, load, unload)
│   │   ├── registry.py           # ModelManager (keep_alive, LRU, acquire_engine)
│   │   ├── xasr_engine.py        # sherpa-onnx 实时流式引擎
│   │   ├── whisper_engine.py     # faster-whisper 引擎
│   │   ├── qwen_engine.py        # Qwen3-ASR 引擎
│   │   ├── funasr_engine.py      # FunASR / Paraformer 引擎
│   │   ├── firered_engine.py     # FireRedASR 引擎
│   │   └── openai_engine.py      # OpenAI 云端兼容引擎
│   ├── schemas/                  # Pydantic 请求/响应 Schema (DTO)
│   ├── services/                 # 业务逻辑服务层
│   │   ├── transcription_service.py # 异步转录任务编排、后台调度与 SSE 流生成
│   │   ├── file_service.py       # 文件资产读取与去重
│   │   ├── media_service.py      # 媒体 URL 解析与后台下载服务
│   │   └── record_service.py     # 历史记录持久化服务
│   └── utils/                    # ASRToolkit (内存 VAD、长音频切片、智能字幕分段、格式转换)
├── cli/                          # 命令行工具集
│   ├── model.py                  # 模型状态查询、多源下载与完整性校验工具
│   ├── clip.py                   # 音视频截取工具
│   ├── converter.py              # 音频格式转换器
│   └── stream_simulation_client.py # WebSocket 实时流式模拟客户端
├── data/                         # 运行时数据目录（models、uploads、downloads、database）
│   └── models/                   # 本地 ASR 模型权重统一存放目录
├── tests/                        # 三层自动化测试套件与内置 Public Domain 测试媒体
├── web/                          # Vue 3 前端管理界面
├── docs/                         # 架构设计与 API 参考文档中心
├── config.yaml                   # 核心服务、模型生命周期与引擎配置文件
├── pyproject.toml                # 项目元数据、CLI 入口与 pytest 配置
└── requirements.txt              # Python 依赖清单
```

## 开源协议

本项目采用 [Apache 2.0](LICENSE) 开源协议。
