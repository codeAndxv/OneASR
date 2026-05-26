# OneASR

整合多种 ASR 引擎，对外提供统一的语音识别 API。

## 核心能力

1. **文件识别** — 接收音视频文件或音视频 URL，返回完整识别结果
2. **流式识别** — 接收音频流，实时返回识别结果流（WebSocket）
3. **Web 管理界面** — Vue.js 前端，支持文件/URL 识别、实时流式结果展示、SRT 导出

## 技术栈

- **后端**: Python 3.11+、FastAPI
- **前端**: Vue 3、Vite、Vue Router
- **ASR 引擎**: faster-whisper、FireRedASR、WhisperLiveKit
- **依赖管理**: requirements.txt（后端）、npm（前端）
- **虚拟环境**: `.venv`

## 项目结构

```
OneASR/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/
│   │   ├── auth.py          # API Key 验证
│   │   ├── file.py          # 文件识别接口（上传/URL → 完整结果）
│   │   └── stream.py        # 流式识别接口（WhisperLiveKit WebSocket）
│   ├── core/config.py       # 配置管理
│   ├── engines/
│   │   ├── base.py          # 引擎抽象基类
│   │   ├── whisper_engine.py # faster-whisper 实现
│   │   ├── firered_engine.py # FireRedASR 实现
│   │   ├── wlk_engine.py    # WhisperLiveKit 实现（流式+文件）
│   │   └── registry.py      # 引擎注册中心
│   ├── models/schemas.py    # 数据模型
│   └── utils/download.py    # URL 下载工具
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
│   ├── whisper/
│   └── firered/
├── config.yaml              # API Key 和引擎配置
├── tests/
├── requirements.txt
├── README.md
└── CLAUDE.md
```

## 引擎配置

编辑 `config.yaml` 配置 API Key 和引擎：

```yaml
# API Key（所有接口必须携带此 key）
api_key: oneasr-key

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

模型路径规则：`{model_dir}/{engine_name}/`

## 开发规范

- 抽取统一抽象层调用不同的 ASR 实现，引擎切换对上层透明
- 代码简洁易读，函数职责单一
- 每次功能变更后同步更新 README.md
- 使用类型注解（type hints）
- 错误处理：区分用户输入校验（4xx）和服务内部错误（5xx）
- 在修改api后， 在tests下同步写测试代码