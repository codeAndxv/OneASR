# OneASR

整合多种 ASR 引擎，对外提供统一的语音识别 API。

## 核心能力

1. **文件识别** — 接收音视频文件或音视频 URL，返回完整识别结果
2. **流式识别** — 接收音频流，实时返回识别结果流（WebSocket）

## 技术栈

- **语言**: Python 3.11+
- **框架**: FastAPI
- **ASR 引擎**: faster-whisper（默认）
- **依赖管理**: requirements.txt
- **虚拟环境**: `.venv`

## 项目结构

```
OneASR/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/
│   │   ├── file.py          # 文件识别接口（上传/URL → 完整结果）
│   │   └── stream.py        # 流式识别接口（WebSocket 音频流 → 结果流）
│   ├── core/                # 配置、依赖注入、公共工具
│   ├── engines/             # ASR 引擎适配层（统一接口，不同实现）
│   ├── models/              # Pydantic 请求/响应模型
│   └── utils/               # 通用工具函数
├── tests/
├── requirements.txt
├── README.md
└── CLAUDE.md
```

## 引擎配置

通过环境变量配置 Whisper 引擎：

- `ONEASR_WHISPER_MODEL_SIZE` — 模型大小（base/small/medium/large-v3）
- `ONEASR_WHISPER_DEVICE` — 设备（cpu/cuda/auto）
- `ONEASR_WHISPER_COMPUTE_TYPE` — 计算类型（int8/float16/float32）

## 开发规范

- 抽取统一抽象层调用不同的 ASR 实现，引擎切换对上层透明
- 代码简洁易读，函数职责单一
- 每次功能变更后同步更新 README.md
- 使用类型注解（type hints）
- 错误处理：区分用户输入校验（4xx）和服务内部错误（5xx）