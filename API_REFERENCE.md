# OneASR API 接口参考文档 (API Reference)

本文档提供 OneASR 全部 HTTP REST 与 WebSocket 接口的完整规范、请求参数及返回格式说明。

## 认证方式

除 `/health` 健康检查外，所有 API 接口均需携带 API Key 进行认证。

### HTTP 请求
在 Header 中添加 `Authorization` 或 `X-API-Key`：
```http
Authorization: Bearer <api_key>
```
或
```http
X-API-Key: <api_key>
```

### WebSocket 连接
支持以下任一方式：
1. **Query 参数**：`ws://<host>:<port>/v1/realtime?api_key=<api_key>`
2. **请求头**：`Authorization: Bearer <api_key>`

---

## 一、文件转录（OpenAI 兼容直接识别）

### `POST /v1/audio/transcriptions`

OpenAI 兼容的语音识别接口，支持同步和 SSE 流式两种响应模式。适用于单次 ≤25MB 的文件快速识别。

#### 请求方式与参数
- **Content-Type**: `multipart/form-data`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `file` | File | 是 | - | 音视频文件（≤25MB） |
| `model` | string | 是 | - | 引擎/模型标识（如 `whisper1`、`qwen-asr`） |
| `language` | string | 否 | - | ISO-639-1 语言代码（如 `zh`、`en`、`auto`） |
| `languages` | string | 否 | - | 备选语言列表（逗号分隔） |
| `response_format` | string | 否 | `json` | 响应格式：`json` / `verbose_json` / `text` / `srt` / `vtt` / `diarized_json` |
| `prompt` | string | 否 | - | 初始提示词（部分模型支持） |
| `stream` | bool | 否 | `false` | 是否开启 SSE 流式推送 |
| `temperature` | float | 否 | `0.0` | 采样温度 (0.0 ~ 1.0) |
| `timestamp_granularities` | string | 否 | - | 时间戳粒度：`word` / `segment` / `word,segment` |
| `keywords` | string | 否 | - | 关键词/热词（逗号分隔） |

#### 响应示例

##### 1. 同步普通 JSON (`stream=false`, `response_format=json`)
```json
{
  "text": "今天天气非常晴朗，我们一起去公园散步吧。"
}
```

##### 2. 同步详细 JSON (`stream=false`, `response_format=verbose_json`)
```json
{
  "text": "今天天气非常晴朗，我们一起去公园散步吧。",
  "language": "zh",
  "duration": 4.12,
  "words": [
    {
      "word": "今天天气非常晴朗",
      "start": 0.0,
      "end": 1.8,
      "probability": 0.0
    }
  ],
  "segments": [
    {
      "id": 0,
      "seek": 0,
      "start": 0.0,
      "end": 1.8,
      "text": "今天天气非常晴朗，",
      "tokens": [],
      "temperature": 0.0,
      "avg_logprob": 0.0,
      "compression_ratio": 0.0,
      "no_speech_prob": 0.0
    },
    {
      "id": 1,
      "seek": 0,
      "start": 1.9,
      "end": 4.12,
      "text": "我们一起去公园散步吧。",
      "tokens": [],
      "temperature": 0.0,
      "avg_logprob": 0.0,
      "compression_ratio": 0.0,
      "no_speech_prob": 0.0
    }
  ]
}
```

##### 3. SSE 流式响应 (`stream=true`, `Content-Type: text/event-stream`)
```http
data: {"type": "transcript.text.delta", "delta": "今天天气非常晴朗，", "start": 0.0, "end": 1.8, "is_endpoint": true}

data: {"type": "transcript.text.delta", "delta": "我们一起去公园散步吧。", "start": 1.9, "end": 4.12, "is_endpoint": true}

data: {"type": "transcript.text.done", "text": "今天天气非常晴朗，我们一起去公园散步吧。"}
```

---

## 二、大文件上传与管理

支持大文件（最大 2GB）上传和客户端 MD5 秒传。

### 1. `POST /v1/file/upload` — 上传音视频文件

#### 请求参数（multipart/form-data）
| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `file` | File | 是 | 音视频文件（最大 2GB） |
| `file_md5` | string | 否 | 客户端计算的 MD5（传入时服务端检测是否可秒传） |
| `file_size` | int | 否 | 文件大小（字节，与实际不符则校验拒绝） |

#### 响应示例
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "meeting_recording.wav",
  "file_size": 104857600,
  "file_md5": "e10adc3949ba59abbe56e057f20f883e",
  "duplicate": false,
  "message": "File uploaded successfully"
}
```

---

### 2. `GET /v1/file/list` — 列出已上传文件

#### 响应示例
```json
{
  "files": [
    {
      "file_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "meeting_recording.wav",
      "file_size": 104857600,
      "file_md5": "e10adc3949ba59abbe56e057f20f883e",
      "content_type": "audio/wav",
      "created_at": "2026-09-19T10:30:00+00:00"
    }
  ],
  "total": 1
}
```

---

### 3. `GET /v1/file/{file_id}` — 获取单个文件信息

- **路径参数**：`file_id` (string) — 文件的 UUID
- **响应**：单个文件信息对象（格式同 `GET /v1/file/list` 中的项）。

---

### 4. `DELETE /v1/file/{file_id}` — 删除已上传文件

- **路径参数**：`file_id` (string) — 文件的 UUID
- **响应**：
```json
{
  "message": "File deleted successfully",
  "file_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 三、异步文件转录任务

适用于大文件、长时间音视频转录。支持后台异步执行、轮询状态与 SSE 流式输出。

### 1. `POST /v1/file/transcriptions` — 创建转录任务

#### 请求参数（multipart/form-data）
| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `file` | File | 否 | 直接上传音视频文件（优先级 1） |
| `file_url` | string | 否 | 音视频公网下载链接（优先级 2） |
| `file_uuid` | string | 否 | 已上传文件的 UUID（优先级 3） |
| `model` | string | 是 | 引擎名称（如 `whisper1`、`qwen-asr`） |
| `language` | string | 否 | 语言代码（如 `zh`、`en`） |
| `response_format`| string | 否 | 默认 `json` |

#### 响应示例
```json
{
  "task_id": "9f7b1e8a-6b2c-4f18-9a3d-2c8e5e9b3a10",
  "status": "pending",
  "created_at": "2026-09-19T10:30:00+00:00"
}
```

---

### 2. `GET /v1/file/transcriptions` — 分页查询任务列表

#### 查询参数
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `status` | string | 否 | - | 按状态过滤：`pending` / `processing` / `completed` / `failed` / `cancelled` |
| `limit` | int | 否 | 20 | 分页大小 (1 ~ 100) |
| `offset` | int | 否 | 0 | 偏移量 |

#### 响应示例
```json
{
  "tasks": [
    {
      "task_id": "9f7b1e8a-6b2c-4f18-9a3d-2c8e5e9b3a10",
      "status": "completed",
      "progress": 1.0,
      "filename": "meeting_recording.wav",
      "file_size": 104857600,
      "source_type": "file_uuid",
      "model": "whisper1",
      "language": "zh",
      "response_format": "json",
      "total_time": 18.35,
      "segment_count": 2,
      "text": "今天天气非常晴朗，我们一起去公园散步吧。",
      "segments": [
        {
          "id": 0,
          "start": 0.0,
          "end": 1.8,
          "text": "今天天气非常晴朗，",
          "speaker": null,
          "avg_logprob": null,
          "no_speech_prob": null
        },
        {
          "id": 1,
          "start": 1.9,
          "end": 4.12,
          "text": "我们一起去公园散步吧。",
          "speaker": null,
          "avg_logprob": null,
          "no_speech_prob": null
        }
      ],
      "error_message": null,
      "created_at": "2026-09-19T10:30:00+00:00",
      "updated_at": "2026-09-19T10:30:20+00:00",
      "completed_at": "2026-09-19T10:30:20+00:00"
    }
  ],
  "total": 1
}
```

---

### 3. `GET /v1/file/transcriptions/{task_id}` — 获取单个任务详情

- **路径参数**：`task_id` (string) — 任务 UUID
- **响应**：单个任务详情对象（包含完整的 `segments` 分段结果）。

---

### 4. `GET /v1/file/transcriptions/{task_id}/stream` — 任务结果 SSE 流式推送

- **路径参数**：`task_id` (string) — 任务 UUID
- **说明**：对进行中的任务实时推送已转录的句子；对已完成的任务快速回放输出。

#### SSE 事件流格式
```http
data: {"type": "transcript.text.delta", "delta": "今天天气非常晴朗，", "start": 0.0, "end": 1.8, "is_endpoint": true}

data: {"type": "transcript.text.delta", "delta": "我们一起去公园散步吧。", "start": 1.9, "end": 4.12, "is_endpoint": true}

data: {"type": "transcript.text.done", "text": "今天天气非常晴朗，我们一起去公园散步吧。"}
```

---

### 5. `DELETE /v1/file/transcriptions/{task_id}` — 取消转录任务

- **路径参数**：`task_id` (string) — 任务 UUID（仅处于 `pending` 或 `processing` 状态的任务可被取消）
- **响应**：
```json
{
  "message": "Task cancelled",
  "task_id": "9f7b1e8a-6b2c-4f18-9a3d-2c8e5e9b3a10"
}
```

---

## 四、模型与 Provider 接口

### 1. `GET /v1/models` — 获取可用模型（OpenAI 兼容）

#### 响应示例
```json
{
  "object": "list",
  "data": [
    {
      "id": "whisper1",
      "object": "model",
      "created": 1726700000,
      "owned_by": "local",
      "shutdown_date": null
    }
  ]
}
```

---

### 2. `GET /v1/providers` — 获取 Provider 详情及能力

#### 响应示例
```json
{
  "object": "list",
  "data": [
    {
      "id": "whisper1",
      "object": "provider",
      "created": 1726700000,
      "owned_by": "local",
      "shutdown_date": "9999-12-31T23:59:59Z",
      "functions": ["realtimeASR", "fileASR"],
      "languages": ["zh", "en", "ja", "ko", "auto"]
    },
    {
      "id": "qwen-asr",
      "object": "provider",
      "created": 1726700000,
      "owned_by": "local",
      "shutdown_date": "9999-12-31T23:59:59Z",
      "functions": ["fileASR"],
      "languages": ["zh", "en", "yue", "auto"]
    }
  ]
}
```

---

## 五、媒体解析与下载（抖音/B站/YouTube）

### 1. `POST /v1/media/parse` — 提交媒体下载任务

#### 请求参数（JSON）
```json
{
  "url": "https://www.bilibili.com/video/BV1xx411c7mD",
  "format": "audio"
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `url` | string | 是 | - | 视频或音频 URL（支持抖音、B站、YouTube等） |
| `format` | string | 否 | `audio` | 提取格式：`audio`（音频）或 `video`（视频） |

#### 响应示例
```json
{
  "task_id": "c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
  "status": "pending",
  "platform": "bilibili"
}
```

---

### 2. `GET /v1/media/parse` — 查询下载任务列表

- **查询参数**：`limit`（默认 50）、`offset`（默认 0）
- **响应示例**：
```json
{
  "tasks": [
    {
      "task_id": "c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
      "url": "https://www.bilibili.com/video/BV1xx411c7mD",
      "platform": "bilibili",
      "format": "audio",
      "status": "succeeded",
      "progress": 1.0,
      "title": "示例视频标题",
      "duration_seconds": 185,
      "uploader": "UP主昵称",
      "file_path": "./downloads/xxx.mp3",
      "file_size": 2457600,
      "error_message": null,
      "created_at": "2026-09-19T10:30:00+00:00",
      "updated_at": "2026-09-19T10:30:15+00:00",
      "completed_at": "2026-09-19T10:30:15+00:00"
    }
  ],
  "total": 1
}
```

---

### 3. `GET /v1/media/parse/{task_id}` — 获取下载任务详情
- **路径参数**：`task_id` (string)
- **响应**：单个下载任务对象。

---

### 4. `GET /v1/media/parse/{task_id}/file` — 下载提取的文件
- **路径参数**：`task_id` (string)
- **响应**：二进制文件流（`application/octet-stream`）。

---

### 5. `DELETE /v1/media/parse/{task_id}` — 删除下载任务及文件
- **路径参数**：`task_id` (string)
- **响应**：
```json
{
  "message": "任务已删除",
  "task_id": "c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f"
}
```

---

## 六、WebSocket 实时语音识别

### 1. `WS /v1/realtime` — OpenAI 标准实时长连接

- **连接 URL**：`ws://<host>:<port>/v1/realtime?api_key=<api_key>`
- **音频格式**：16kHz, 16-bit, 单声道 PCM（以 base64 编码发送）

#### 客户端发送消息

##### (1) 配置会话 (`session.update`)
```json
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "format": {
          "type": "audio/pcm",
          "rate": 16000
        },
        "transcription": {
          "model": "whisper1",
          "language": "zh"
        }
      }
    }
  }
}
```

##### (2) 持续发送音频切片 (`input_audio_buffer.append`)
```json
{
  "type": "input_audio_buffer.append",
  "audio": "<base64_encoded_pcm_data>"
}
```

##### (3) 提交当前音频块 (`input_audio_buffer.commit`)
```json
{
  "type": "input_audio_buffer.commit"
}
```

#### 服务端返回事件

##### (1) 会话配置成功 (`session.updated`)
```json
{
  "type": "session.updated",
  "session": {
    "id": "sess_12345678",
    "type": "transcription"
  }
}
```

##### (2) 实时增量识别中间结果 (`conversation.item.input_audio_transcription.delta`)
```json
{
  "type": "conversation.item.input_audio_transcription.delta",
  "item_id": "item_12345678_1",
  "delta": "今天天气"
}
```

##### (3) 确定句子/端点识别结果 (`conversation.item.input_audio_transcription.completed`)
```json
{
  "type": "conversation.item.input_audio_transcription.completed",
  "item_id": "item_12345678_1",
  "transcript": "今天天气非常晴朗。"
}
```

---

### 2. `WS /v1/realtimeext` — 扩展版实时转录

在 `/v1/realtime` 协议基础上提供心跳保活和完成信号：
- 每 5 秒推送 `{"type": "heartbeat"}`
- 音频流提交完成时推送 `{"type": "done"}` 信号

---

## 七、系统与健康检查

### `GET /health`
无需认证，用于探针检测。
```json
{
  "status": "ok"
}
```

---

## 完整路由索引表

| 序号 | Method | 路由路径 | 说明 | 模块 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `POST` | `/v1/audio/transcriptions` | 文件转录（OpenAI 兼容直接识别，≤25MB） | 音频转录 |
| 2 | `POST` | `/v1/file/upload` | 上传音视频文件（支持秒传，≤2GB） | 文件管理 |
| 3 | `GET` | `/v1/file/list` | 查询已上传文件列表 | 文件管理 |
| 4 | `GET` | `/v1/file/{file_id}` | 查询单个文件信息 | 文件管理 |
| 5 | `DELETE` | `/v1/file/{file_id}` | 删除已上传文件及存储 | 文件管理 |
| 6 | `POST` | `/v1/file/transcriptions` | 创建异步转录任务（≤2GB） | 任务中心 |
| 7 | `GET` | `/v1/file/transcriptions` | 任务列表分页查询 | 任务中心 |
| 8 | `GET` | `/v1/file/transcriptions/{task_id}` | 查询任务状态与完整分段结果 | 任务中心 |
| 9 | `GET` | `/v1/file/transcriptions/{task_id}/stream` | SSE 流式获取任务转录结果 | 任务中心 |
| 10 | `DELETE` | `/v1/file/transcriptions/{task_id}` | 取消转录任务 | 任务中心 |
| 11 | `GET` | `/v1/models` | 可用模型列表（OpenAI 兼容） | 模型与 Provider |
| 12 | `GET` | `/v1/providers` | Provider 引擎及能力详情 | 模型与 Provider |
| 13 | `POST` | `/v1/media/parse` | 提交媒体 URL 下载任务（抖音/B站等） | 媒体下载 |
| 14 | `GET` | `/v1/media/parse` | 查询媒体下载任务列表 | 媒体下载 |
| 15 | `GET` | `/v1/media/parse/{task_id}` | 查询单个媒体下载任务 | 媒体下载 |
| 16 | `GET` | `/v1/media/parse/{task_id}/file` | 下载解析完成的音视频文件 | 媒体下载 |
| 17 | `DELETE` | `/v1/media/parse/{task_id}` | 删除下载任务及文件 | 媒体下载 |
| 18 | `WS` | `/v1/realtime` | WebSocket 实时流式识别（OpenAI 标准） | 实时识别 |
| 19 | `WS` | `/v1/realtimeext` | WebSocket 实时流式识别（扩展版） | 实时识别 |
| 20 | `GET` | `/health` | 服务健康检查 | 系统 |
