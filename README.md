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
| `/ws/transcribe/stream` | WebSocket | 流式识别 |
| `/health` | GET | 健康检查 |

## 配置

通过环境变量配置：

```bash
# ASR 引擎
ONEASR_DEFAULT_ENGINE=whisper       # 默认引擎

# Whisper 配置
ONEASR_WHISPER_MODEL_SIZE=base      # base/small/medium/large-v3
ONEASR_WHISPER_DEVICE=cpu           # cpu/cuda/auto
ONEASR_WHISPER_COMPUTE_TYPE=int8    # int8/float16/float32

# 其他
ONEASR_DEBUG=false
ONEASR_MAX_FILE_SIZE_MB=500
```

## 项目结构

```
app/
├── main.py              # FastAPI 入口
├── api/
│   ├── file.py          # 文件识别接口
│   └── stream.py        # 流式识别接口
├── core/config.py       # 配置管理
├── engines/
│   ├── base.py          # 引擎抽象基类
│   ├── whisper_engine.py # faster-whisper 实现
│   └── registry.py      # 引擎注册中心
├── models/schemas.py    # 数据模型
└── utils/download.py    # URL 下载工具
```
