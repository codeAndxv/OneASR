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
| `/ws/transcribe/stream` | WebSocket | 流式识别 |
| `/health` | GET | 健康检查 |

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
│   ├── firered_engine.py # FireRedASR 实现
│   └── registry.py      # 引擎注册中心
├── models/schemas.py    # 数据模型
└── utils/
    ├── download.py      # URL 下载工具
    └── format.py        # 输出格式转换
models/                  # 模型存放目录
config.yaml              # 引擎配置文件
```
