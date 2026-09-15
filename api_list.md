# OneASR API 列表

## 认证

所有 HTTP 端点需在请求头携带 API Key：

```
Authorization: Bearer <api_key>
```

WebSocket 端点支持两种方式：
- 查询参数：`?api_key=<key>`
- 请求头：`Authorization: Bearer <key>`

---

## 一、文件转录（OpenAI 兼容）

### `POST /v1/audio/transcriptions`

OpenAI 兼容的语音识别接口，支持同步和 SSE 流式两种模式。文件上限 25MB。

**请求参数**（multipart/form-data）：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 音视频文件（≤25MB） |
| `model` | string | 是 | 引擎标识（如 `whisper1`） |
| `language` | string | 否 | ISO-639-1 语言代码（如 `zh`、`en`） |
| `languages` | string | 否 | 可能的语言列表（逗号分隔） |
| `response_format` | string | 否 | `json` / `verbose_json` / `text` / `srt` / `vtt` / `diarized_json`，默认 `json` |
| `prompt` | string | 否 | 提示词，引导模型风格 |
| `stream` | bool | 否 | 是否 SSE 流式，默认 `false` |
| `temperature` | float | 否 | 采样温度 0-1 |
| `timestamp_granularities` | string | 否 | `word` / `segment` / `word,segment` |
| `include` | string | 否 | 额外信息（逗号分隔，如 `logprobs`） |
| `keywords` | string | 否 | 关键词提示（逗号分隔） |

**响应**（`stream=false`，`response_format=json`）：
```json
{
  "text": "完整转录文本"
}
```

**响应**（`stream=true`，SSE `text/event-stream`）：
```
data: {"type": "transcript.text.delta", "delta": "识别文本"}
data: {"type": "transcript.text.done", "text": "完整文本"}
```

---

## 二、文件管理

### `POST /v1/file/upload`

上传音视频文件，支持 MD5 秒传。文件上限 2GB。

**请求参数**（multipart/form-data）：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 音视频文件 |
| `file_md5` | string | 否 | 客户端计算的 MD5（用于秒传检测） |
| `file_size` | int | 否 | 文件字节数（与实际不符则拒绝） |

**响应**：
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "speech.mp3",
  "file_size": 1234567,
  "file_md5": "abc123...",
  "duplicate": false,
  "message": "File uploaded successfully"
}
```

---

### `GET /v1/file/list`

列出所有已上传的文件。

**响应**：
```json
{
  "files": [
    {
      "file_id": "550e8400-...",
      "filename": "speech.mp3",
      "file_size": 1234567,
      "file_md5": "abc123...",
      "content_type": "audio/mpeg",
      "created_at": "2026-01-15T10:30:00"
    }
  ],
  "total": 1
}
```

---

### `GET /v1/file/{file_id}`

获取指定文件的信息。

**路径参数**：`file_id` — 文件 UUID

**响应**：同 `GET /v1/file/list` 中的单个文件对象。

---

### `DELETE /v1/file/{file_id}`

删除指定文件（数据库记录 + 磁盘文件）。

**路径参数**：`file_id` — 文件 UUID

**响应**：
```json
{
  "message": "File deleted successfully",
  "file_id": "550e8400-..."
}
```

---

## 三、异步转录任务

### `POST /v1/file/transcriptions`

创建异步转录任务。支持直接上传文件、URL、或已上传文件的 UUID。文件上限 2GB。

**请求参数**（multipart/form-data，三选一）：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 否 | 直接上传音频文件（优先级最高） |
| `file_url` | string | 否 | 音频文件 URL |
| `file_uuid` | string | 否 | 已上传文件的 UUID |
| `model` | string | 是 | 引擎标识 |
| `language` | string | 否 | ISO-639-1 语言代码 |
| `response_format` | string | 否 | 输出格式，默认 `json` |

**响应**：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2026-01-15T10:30:00+00:00"
}
```

---

### `GET /v1/file/transcriptions`

列出转录任务，支持状态过滤和分页。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 过滤：`pending` / `processing` / `completed` / `failed` / `cancelled` |
| `limit` | int | 否 | 每页数量，1-100，默认 20 |
| `offset` | int | 否 | 偏移量，默认 0 |

**响应**：
```json
{
  "tasks": [
    {
      "task_id": "550e8400-...",
      "status": "completed",
      "progress": 1.0,
      "filename": "speech.mp3",
      "file_size": 1234567,
      "source_type": "file_uuid",
      "model": "whisper1",
      "language": "zh",
      "response_format": "json",
      "total_time": 45.2,
      "segment_count": 12,
      "text": "完整转录文本...",
      "segments": [{"id": 0, "start": 0.0, "end": 3.5, "text": "..."}],
      "error_message": null,
      "created_at": "2026-01-15T10:30:00+00:00",
      "updated_at": "2026-01-15T10:30:45+00:00",
      "completed_at": "2026-01-15T10:30:45+00:00"
    }
  ],
  "total": 1
}
```

---

### `GET /v1/file/transcriptions/{task_id}`

查询单个转录任务状态，包含所有已识别的分段结果。

**路径参数**：`task_id` — 任务 UUID

**响应**：同 `GET /v1/file/transcriptions` 中的单个任务对象。

---

### `GET /v1/file/transcriptions/{task_id}/stream`

SSE 流式获取转录结果。已完成的任务一次性推送所有结果，进行中的任务实时轮询推送。

**路径参数**：`task_id` — 任务 UUID

**响应**（SSE `text/event-stream`）：
```
data: {"type": "transcript.text.delta", "delta": "识别文本"}
data: {"type": "transcript.text.done", "text": "完整文本"}
data: {"type": "heartbeat"}
```

---

### `DELETE /v1/file/transcriptions/{task_id}`

取消转录任务（仅 `pending` / `processing` 状态可取消）。

**路径参数**：`task_id` — 任务 UUID

**响应**：
```json
{
  "message": "Task cancelled",
  "task_id": "550e8400-..."
}
```

---

## 四、模型与 Provider

### `GET /v1/models`

返回可用模型列表（兼容 OpenAI `/v1/models`）。

**响应**：
```json
{
  "object": "list",
  "data": [
    {
      "id": "whisper1",
      "object": "model",
      "created": 0,
      "owned_by": "local"
    }
  ]
}
```

---

### `GET /v1/providers`

返回已加载 Provider 的详细信息。

**响应**：
```json
{
  "object": "list",
  "default": "whisper1",
  "data": [
    {
      "id": "whisper1",
      "engine": "faster-whisper",
      "model": "base",
      "device": "cpu",
      "compute_type": "int8",
      "type": "local",
      "streaming": false,
      "loaded": true,
      "inputTypes": ["audioStream", "audioFile"],
      "outputTypes": ["text"]
    }
  ]
}
```

---

## 五、媒体 URL 下载

### `POST /v1/media/parse`

提交媒体 URL（抖音/TikTok/B站/YouTube）异步下载任务，立即返回 `task_id`。

**请求参数**（JSON）：
```json
{
  "url": "https://www.bilibili.com/video/BV1xx411c7mD",
  "format": "audio"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 视频/音频 URL |
| `format` | string | 否 | `audio`（默认）或 `video` |

**响应**：
```json
{
  "task_id": "550e8400-...",
  "status": "pending",
  "platform": "bilibili"
}
```

---

### `GET /v1/media/parse`

列出所有下载任务。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `limit` | int | 否 | 每页数量，1-200，默认 50 |
| `offset` | int | 否 | 偏移量，默认 0 |

**响应**：
```json
{
  "tasks": [
    {
      "task_id": "550e8400-...",
      "url": "https://...",
      "platform": "bilibili",
      "format": "audio",
      "status": "succeeded",
      "progress": 1.0,
      "title": "视频标题",
      "duration_seconds": 120,
      "uploader": "UP主",
      "file_path": "./downloads/xxx.mp3",
      "file_size": 1234567,
      "error_message": null,
      "created_at": "2026-01-15T10:30:00",
      "updated_at": "2026-01-15T10:30:30",
      "completed_at": "2026-01-15T10:30:30"
    }
  ],
  "total": 1
}
```

---

### `GET /v1/media/parse/{task_id}`

查询单个下载任务状态。

**路径参数**：`task_id` — 任务 UUID

**响应**：同 `GET /v1/media/parse` 中的单个任务对象。

---

### `DELETE /v1/media/parse/{task_id}`

删除下载任务（数据库记录 + 磁盘文件）。

**路径参数**：`task_id` — 任务 UUID

**响应**：
```json
{
  "message": "任务已删除",
  "task_id": "550e8400-..."
}
```

---

### `GET /v1/media/parse/{task_id}/file`

下载已完成的文件。仅 `succeeded` 状态可下载。

**路径参数**：`task_id` — 任务 UUID

**响应**：二进制文件流（`application/octet-stream`），`Content-Disposition` 附带文件名。

---

## 六、实时语音识别

### `WS /v1/realtime`

OpenAI Realtime Transcription 标准协议的 WebSocket 接口。

**连接**：`ws://<host>/v1/realtime?api_key=<key>`

**客户端 → 服务端**：

| 事件类型 | 说明 |
|---------|------|
| `session.update` | 配置会话（model、language、format 等） |
| `input_audio_buffer.append` | 发送 base64 编码的 PCM 音频数据 |
| `input_audio_buffer.commit` | 提交当前音频 turn |

**服务端 → 客户端**：

| 事件类型 | 说明 |
|---------|------|
| `session.updated` | 会话配置确认 |
| `conversation.item.input_audio_transcription.delta` | 增量转录文本 |
| `conversation.item.input_audio_transcription.completed` | 转录完成（最终文本） |

---

### `WS /v1/realtimeext`

扩展版 WebSocket 实时转录接口。在 OpenAI 标准基础上增加：

| 扩展特性 | 说明 |
|---------|------|
| `language` 字段 | 支持单语言字符串（而非 `languages` 数组） |
| `heartbeat` 事件 | 每 5 秒心跳，客户端可判断连接存活 |
| `buffer delta` | 未 commit 的中间文本推送 |
| `done` 事件 | commit 完成后通知客户端可关闭 |

**连接**：`ws://<host>/v1/realtimeext?api_key=<key>`

**协议与 `/v1/realtime` 相同**，额外支持上述扩展事件。

---

## 七、系统

### `GET /health`

健康检查，无需认证。

**响应**：
```json
{
  "status": "ok"
}
```

---

## 接口汇总

| Method | Path | 说明 |
|--------|------|------|
| POST | `/v1/audio/transcriptions` | 文件转录（OpenAI 兼容，≤25MB） |
| POST | `/v1/file/upload` | 上传文件（MD5 秒传，≤2GB） |
| GET | `/v1/file/list` | 列出已上传文件 |
| GET | `/v1/file/{file_id}` | 查询文件信息 |
| DELETE | `/v1/file/{file_id}` | 删除文件 |
| POST | `/v1/file/transcriptions` | 创建异步转录任务（≤2GB） |
| GET | `/v1/file/transcriptions` | 列出转录任务 |
| GET | `/v1/file/transcriptions/{task_id}` | 查询任务状态 |
| GET | `/v1/file/transcriptions/{task_id}/stream` | SSE 流式获取转录结果 |
| DELETE | `/v1/file/transcriptions/{task_id}` | 取消转录任务 |
| GET | `/v1/models` | 模型列表（OpenAI 兼容） |
| GET | `/v1/providers` | Provider 详情 |
| POST | `/v1/media/parse` | 提交媒体 URL 下载 |
| GET | `/v1/media/parse` | 列出下载任务 |
| GET | `/v1/media/parse/{task_id}` | 查询下载任务 |
| DELETE | `/v1/media/parse/{task_id}` | 删除下载任务 |
| GET | `/v1/media/parse/{task_id}/file` | 下载已完成文件 |
| WS | `/v1/realtime` | 实时转录（OpenAI 标准） |
| WS | `/v1/realtimeext` | 实时转录（扩展版） |
| GET | `/health` | 健康检查 |
