# OneASR API 接口设计

## 概述

OneASR 覆盖三大场景：文件转录（同步/异步）和实时语音识别。

### 文件转录

| | 方案一：OpenAI 兼容 | 方案二：异步任务流式 |
|---|---|---|
| **风格** | 单请求同步/流式 | 上传 → 提交 → 流式订阅 / 最终结果 |
| **文件上限** | 25 MB | 2 GB |
| **适用场景** | 小文件快速转录、兼容 OpenAI 生态 | 大文件、长时间转录、需要边转边看 |
| **核心路由** | `POST /v1/audio/transcriptions` | `POST /v1/file/upload` + `POST /v1/file/transcriptions` + 两个消费端点 |

### 实时语音识别

| | 方案一：OpenAI 标准协议 | 方案二：扩展 OpenAI 协议 |
|---|---|---|
| **风格** | 严格遵循 OpenAI Realtime Transcription | 兼容 OpenAI 格式 + OneASR 扩展 |
| **连接方式** | WebSocket | WebSocket |
| **核心路由** | `WS /v1/realtime` | `WS /v1/realtimeext` |
| **适用场景** | 对接 OpenAI 生态客户端 | 自部署场景，需要更多控制参数 |
| **引擎要求** | OpenAI Realtime API (gpt-live-transcribe) | faster-whisper (本地引擎) |

---

## 方案一：OpenAI 兼容标准

### 现有实现

已实现在 `app/api/audio.py`，路由 `POST /v1/audio/transcriptions`。

通过 `stream` 表单参数区分两种模式：

```
stream=false  →  同步返回完整结果 (JSON / text / srt / vtt)
stream=true   →  SSE 流式返回 (text/event-stream)
```

### 流程

```
客户端                        服务端
  │                             │
  │  POST /v1/audio/transcriptions
  │  multipart: file + model + stream
  │  ─────────────────────────► │
  │                             │  1. 读取文件 (≤25MB)
  │                             │  2. 格式转换 → WAV
  │                             │  3. 获取引擎
  │                             │
  │         stream=false        │
  │  ◄── JSON/text/srt/vtt ──  │  4a. transcribe_file() → 一次性返回
  │                             │
  │         stream=true         │
  │  ◄── SSE: delta events ──  │  4b. transcribe_file_stream() → 逐段推送
  │  ◄── SSE: done event ────  │
```

### SSE 事件格式（stream=true）

```jsonc
// 逐段增量
data: {"type": "transcript.text.delta", "delta": "识别文本"}

// 完成（gpt-transcribe 会包含 languages）
data: {"type": "transcript.text.done", "text": "完整文本", "languages": [{"code": "zh"}]}

// 错误（自扩展，OpenAI 官方未定义此事件类型）
data: {"type": "error", "error": "错误信息"}
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 音视频文件（≤25MB），支持 flac/mp3/mp4/mpeg/mpga/m4a/ogg/wav/webm |
| `model` | string | 是 | 引擎标识（如 `whisper1`） |
| `language` | string | 否 | ISO-639-1 语言代码（如 `en`），提升准确率和延迟 |
| `languages` | array | 否 | 可能的语言列表（ISO-639-1），多语言场景使用 |
| `response_format` | string | 否 | `json` / `verbose_json` / `text` / `srt` / `vtt` / `diarized_json`，默认 `json` |
| `prompt` | string | 否 | 提示词，引导模型风格或延续上下文 |
| `stream` | bool | 否 | 是否 SSE 流式，默认 `false`（whisper-1 不支持流式） |
| `temperature` | float | 否 | 采样温度 0-1，0 为自动调节 |
| `timestamp_granularities` | array | 否 | `["word"]` / `["segment"]` / `["word","segment"]`，需 `response_format=verbose_json`，仅 whisper-1 |
| `chunking_strategy` | string/object | 否 | `"auto"` 或 VAD 配置对象，用于长音频分块 |
| `include` | array | 否 | 额外信息，如 `["logprobs"]`（仅 json 格式，gpt-4o-transcribe 系列） |
| `keywords` | array | 否 | 关键词提示，辅助识别专有名词（gpt-transcribe） |

### 同步响应格式

**JSON** (`response_format=json`)：
```json
{
  "text": "完整转录文本",
  "languages": [{"code": "zh"}]
}
```

**verbose_json** (`response_format=verbose_json`)：
```json
{
  "duration": 120.5,
  "language": "zh",
  "text": "完整转录文本",
  "words": [
    {"word": "你好", "start": 0.0, "end": 0.5, "probability": 0.95}
  ],
  "segments": [
    {"id": 0, "seek": 0, "start": 0.0, "end": 5.2, "text": "...", "tokens": [], "temperature": 0.0, "avg_logprob": 0.0, "compression_ratio": 0.0, "no_speech_prob": 0.0}
  ]
}
```

**diarized_json** (`response_format=diarized_json`)：
```json
{
  "duration": 120.5,
  "language": "zh",
  "text": "完整转录文本",
  "segments": [
    {"id": 0, "start": 0.0, "end": 5.2, "text": "...", "speaker": "agent"}
  ]
}
```

**text / srt / vtt**：返回 `text/plain`，Content-Disposition 附带文件名。

---

## 方案二：异步任务 + 流式消费

### 流程总览

```
客户端                              服务端
  │                                   │
  │  ① POST /v1/file/upload           │
  │  ───────────────────────────────► │  上传文件（支持 MD5 秒传）
  │  ◄── file_id ───────────────────  │
  │                                   │
  │  ② POST /v1/file/transcriptions   │
  │  file_uuid: <file_id>             │
  │  ───────────────────────────────► │  创建后台转录任务
  │  ◄── task_id + status: pending ─  │
  │                                   │
  │  ③ GET /v1/file/transcriptions/{task_id}/stream     │
  │  ───────────────────────────────► │  SSE 订阅，实时接收转录片段
  │  ◄── SSE: delta events ────────  │
  │  ◄── SSE: progress events ─────  │
  │  ◄── SSE: done event ──────────  │
```

### ① 文件上传（已有）

`POST /v1/file/upload` — 已实现，支持 MD5 秒传。

### ② 创建转录任务

`POST /v1/file/transcriptions` — 创建后台转录任务。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 否 | 直接上传（三选一） |
| `file_url` | string | 否 | 音频 URL（三选一） |
| `file_uuid` | string | 否 | 已上传文件 ID（三选一） |
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

#### 后台处理逻辑

后台 worker 调用 `transcribe_file_stream()`，每产生一个 segment 立即写入数据库：

```python
async def _run_transcription(task_id: str):
    update_task_status(task_id, "processing")

    full_text = ""
    async for seg in engine.transcribe_file_stream(data):
        full_text += seg.text
        # 逐条写入 segment 表
        insert_segment(task_id, text=seg.text, start=seg.start, end=seg.end)
        # 更新 task 进度
        progress = seg.end / total_duration if total_duration else 0
        update_task_progress(task_id, progress)

    # 最终结果写入 task 表
    update_task_status(task_id, "completed", full_text=full_text)
```

### ③ 流式获取结果

`GET /v1/file/transcriptions/{task_id}/stream`

SSE 端点，通过轮询数据库获取新数据并推送。

#### 实现方案：数据库轮询

转录结果实时写入数据库，SSE 端点通过轮询新行实现流式推送：

```python
@router.get("/transcriptions/{task_id}/stream")
async def stream_transcription_result(task_id: str):
    task = await get_task(task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")

    if task.status == "completed":
        # 已完成：一次性推送所有结果
        return _emit_final_result(task)

    if task.status == "failed":
        raise HTTPException(500, f"任务失败: {task.error_message}")

    last_segment_id = 0  # 记录已推送的最大 segment_id

    async def _generate():
        nonlocal last_segment_id
        heartbeat_interval = 30  # seconds
        last_heartbeat = time.time()

        while True:
            # 查询新 segment（id > last_segment_id）
            new_segments = get_segments_after(task_id, last_segment_id)

            for seg in new_segments:
                event = {"type": "transcript.text.delta", "delta": seg.text}
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                last_segment_id = seg.id

            # 检查任务状态
            task = get_task(task_id)
            if task.status == "completed":
                done_event = {"type": "transcript.text.done", "text": task.full_text}
                yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
                break
            elif task.status == "failed":
                error_event = {"type": "task.failed", "error": task.error_message}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                break

            # 心跳
            if time.time() - last_heartbeat > heartbeat_interval:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                last_heartbeat = time.time()

            # 轮询间隔
            await asyncio.sleep(0.1)  # 100ms

    return StreamingResponse(_generate(), media_type="text/event-stream")
```

### ④ 查询任务状态（轮询消费）

`GET /v1/file/transcriptions/{task_id}`

同步查询转录任务的当前状态，返回所有已识别的分段结果。适用于不需要实时流式推送的场景（如轮询等待完成）。

#### 请求

```
GET /v1/file/transcriptions/{task_id}
Authorization: Bearer <api_key>
```

#### 响应（TaskStatusResponse）

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 1.0,
  "filename": "speech.mp3",
  "file_size": 42822746,
  "source_type": "file_uuid",
  "model": "whisper1",
  "language": "zh",
  "response_format": "json",
  "total_time": 45.2,
  "segment_count": 12,
  "text": "完整转录文本...",
  "segments": [
    {"id": 0, "start": 0.0, "end": 3.5, "text": "第一段文本"},
    {"id": 1, "start": 3.5, "end": 7.2, "text": "第二段文本"}
  ],
  "error_message": null,
  "created_at": "2026-01-15T10:30:00+00:00",
  "updated_at": "2026-01-15T10:30:45+00:00",
  "completed_at": "2026-01-15T10:30:45+00:00"
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 UUID |
| `status` | string | `pending` / `processing` / `completed` / `failed` / `cancelled` |
| `progress` | float | 进度 0.0 ~ 1.0 |
| `filename` | string | 原始文件名 |
| `file_size` | int? | 文件大小（字节） |
| `source_type` | string | `file` / `file_url` / `file_uuid` |
| `model` | string | 引擎标识 |
| `language` | string? | 语言代码 |
| `response_format` | string? | 输出格式 |
| `total_time` | float? | 总耗时（秒） |
| `segment_count` | int? | 分段数 |
| `text` | string? | 完整转录文本（completed 时有值） |
| `segments` | array | 已识别的分段列表 |
| `error_message` | string? | 失败原因（failed 时有值） |
| `created_at` | string | 创建时间（ISO 8601） |
| `updated_at` | string | 最后更新时间 |
| `completed_at` | string? | 完成时间 |

#### 轮询示例

客户端可定时轮询此接口，根据 `status` 字段判断任务状态：

```python
import time, requests

task_id = "550e8400-..."
while True:
    resp = requests.get(f"{base_url}/v1/file/transcriptions/{task_id}",
                        headers={"Authorization": f"Bearer {api_key}"})
    data = resp.json()
    print(f"status={data['status']}, progress={data['progress']:.0%}")

    if data["status"] == "completed":
        print(data["text"])
        break
    elif data["status"] in ("failed", "cancelled"):
        print(f"Error: {data.get('error_message')}")
        break

    time.sleep(1)  # 1 秒轮询间隔
```

---

## 实时语音识别

### 概述

| | 方案一：OpenAI 标准协议 | 方案二：扩展 OpenAI 协议 |
|---|---|---|
| **风格** | 严格遵循 OpenAI Realtime Transcription | 兼容 OpenAI 格式 + OneASR 扩展 |
| **连接方式** | WebSocket | WebSocket |
| **核心路由** | `WS /v1/realtime` | `WS /v1/realtimeext` |
| **适用场景** | 对接 OpenAI 生态客户端 | 自部署场景，需要更多控制参数 |
| **引擎要求** | OpenAI Realtime API (gpt-live-transcribe) | faster-whisper (本地引擎) |

---

### 方案一：OpenAI 标准协议

严格遵循 OpenAI Realtime Transcription API 协议。客户端可无缝切换到 OpenAI 云端服务。

#### 连接

```
ws://<host>/v1/realtime?api_key=<key>
```

或通过 Header：
```
Authorization: Bearer <api_key>
```

#### 会话配置

发送 `session.update` 创建转录会话：

```jsonc
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "format": {
          "type": "audio/pcm",
          "rate": 24000
        },
        "transcription": {
          "model": "gpt-live-transcribe"  // 或 OneASR provider 名称
        },
        "turn_detection": null  // 禁用自动 VAD，手动 commit
      }
    }
  }
}
```

**响应**：
```jsonc
{
  "type": "session.updated",
  "session": {
    "id": "session_abc123",
    "type": "transcription",
    "audio": {
      "input": {
        "format": { "type": "audio/pcm", "rate": 24000 },
        "transcription": {
          "model": "gpt-live-transcribe"
        }
      }
    }
  }
}
```

#### 流式传输音频

发送 PCM 音频数据（base64 编码）：

```jsonc
{
  "type": "input_audio_buffer.append",
  "audio": "<base64-encoded-pcm16-audio>"
}
```

手动提交音频 turn：

```jsonc
{
  "type": "input_audio_buffer.commit"
}
```

#### 接收转录结果

**增量 delta 事件**（实时部分文本）：
```jsonc
{
  "type": "conversation.item.input_audio_transcription.delta",
  "item_id": "item_001",
  "content_index": 0,
  "delta": "你好，"
}
```

**完成事件**（最终转录文本）：
```jsonc
{
  "type": "conversation.item.input_audio_transcription.completed",
  "item_id": "item_001",
  "content_index": 0,
  "transcript": "你好，请问有什么可以帮您？"
}
```

#### 会话中更新配置

可在会话期间发送新的 `session.update` 更改配置（如添加上下文）：

```jsonc
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "format": { "type": "audio/pcm", "rate": 24000 },
        "transcription": {
          "model": "gpt-live-transcribe",
          "prompt": "客服通话，关于高级套餐和账户 AC-42",
          "keywords": ["premium plan", "AC-42", "billing"],
          "languages": ["en", "zh"],
          "delay": "low"
        }
      },
      "turn_detection": null
    }
  }
}
```

#### 支持的语言格式

- ISO 639-1：`en`、`es`、`zh`
- ISO 639-3：`eng`、`spa`、`yue`、`cmn`
- 中文区域码：`zh-cn`、`zh-tw`、`zh-hk`

#### 延迟调节

通过 `delay` 参数控制延迟与准确率的平衡：

| delay | 说明 |
|-------|------|
| `minimal` | 最低延迟，适合实时交互 |
| `low` | 低延迟，适合实时字幕 |
| `medium` | 延迟与准确率平衡 |
| `high` | 准确率优先 |
| `xhigh` | 最高准确率，最大延迟 |

---

### 方案二：扩展 OpenAI 协议

在 OpenAI 标准协议基础上，增加 OneASR 特有的扩展字段和行为。完全兼容标准客户端，同时支持更多控制能力。

#### 与 OpenAI 标准的差异

| 维度 | OpenAI 标准 | OneASR 扩展 |
|------|-----------|------------|
| `language` | 使用 `languages`（数组） | 额外支持 `language`（单个字符串） |
| `heartbeat` | 无 | 每 5 秒发送心跳事件 |
| `delay` | OpenAI 原生支持 | 透传到本地引擎 |
| `buffer delta` | 无 | 发送未确认的缓冲文本变化 |
| `done` 事件 | 无（commit 后直接 close） | commit 完成后发送 `{"type": "done"}` 再关闭 |
| 引擎限制 | 仅 OpenAI 云端 | 仅 faster-whisper（本地引擎） |

#### 扩展事件：心跳

服务端每 5 秒发送心跳，客户端可据此判断连接存活：

```jsonc
{
  "type": "heartbeat"
}
```

#### 扩展事件：缓冲文本 delta

未 commit 的音频产生的中间文本，通过 delta 事件推送：

```jsonc
{
  "type": "conversation.item.input_audio_transcription.delta",
  "item_id": "item_buffer_001",
  "content_index": 0,
  "delta": "正在识别中..."
}
```

与标准 delta 的区别：缓冲文本可能被后续音频修正，commit 后的 delta 是最终结果。

#### 扩展会话配置示例

```jsonc
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": {
      "input": {
        "format": { "type": "audio/pcm", "rate": 16000 },
        "transcription": {
          "model": "whisper1",       // faster-whisper provider 名称
          "language": "zh",          // 扩展：单语言字段
          "delay": "low"             // 扩展：延迟调节
        }
      }
    }
  }
}
```

#### 扩展 commit 流程

```
客户端                         服务端
  │  input_audio_buffer.commit  │
  │  ────────────────────────►  │
  │                             │  处理剩余音频
  │  ◄── delta events ───────  │  推送最终转录片段
  │  ◄── completed events ───  │  推送完成事件
  │  ◄── {"type": "done"} ───  │  扩展：通知客户端可关闭
  │                             │  关闭 WebSocket
```

#### 完整交互示例

```
客户端                              服务端
  │                                   │
  │  WS /v1/realtimeext?api_key=xxx     │
  │  ───────────────────────────────► │  建立连接
  │                                   │
  │  session.update                   │
  │  { type: "transcription",         │
  │    model: "whisper1",             │
  │    language: "zh" }               │
  │  ───────────────────────────────► │  配置会话
  │  ◄── session.updated ───────────  │
  │                                   │
  │  input_audio_buffer.append        │
  │  { audio: "<pcm16-base64>" }      │
  │  ───────────────────────────────► │  发送音频流
  │  ... (持续发送) ...               │
  │                                   │
  │  ◄── delta: "你好" ────────────  │  实时转录
  │  ◄── delta: "你好请问" ────────  │  文本修正
  │  ◄── completed: "你好请问" ────  │  行完成
  │  ◄── heartbeat ────────────────  │  心跳保活
  │                                   │
  │  input_audio_buffer.commit        │
  │  ───────────────────────────────► │  提交 turn
  │  ◄── delta: "有什么可以帮您" ─  │  最终转录
  │  ◄── completed: "有什么..." ───  │  行完成
  │  ◄── {"type": "done"} ────────  │  扩展：结束通知
  │                                   │  关闭连接
```

---

## 三套场景的接口汇总

```
文件转录 — 方案一 (OpenAI 兼容):
  POST   /v1/audio/transcriptions              文件转录 (stream 参数区分同步/流式)

文件转录 — 方案二 (异步任务流式):
  POST   /v1/file/upload                       上传文件 (MD5 秒传)
  POST   /v1/file/transcriptions               提交转录任务
  GET    /v1/file/transcriptions/{id}          查询任务状态
  GET    /v1/file/transcriptions/{id}/stream   流式获取结果
  DELETE /v1/file/transcriptions/{id}          取消任务
  GET    /v1/file/transcriptions               列出任务
  GET    /v1/file/list                         列出已上传文件
  GET    /v1/file/{file_id}                    查询文件信息
  DELETE /v1/file/{file_id}                    删除文件

实时语音识别 — 方案一 (OpenAI 标准):
  WS     /v1/realtime                          WebSocket 实时转录 (OpenAI 协议)

实时语音识别 — 方案二 (扩展 OpenAI):
  WS     /v1/realtimeext                     WebSocket 实时转录 (扩展协议)
```

---

## 遗漏分析与改进建议

### 已识别的遗漏

| # | 问题 | 说明 | 建议 |
|---|------|------|------|
| 0a | **方案一 `temperature` 参数未透传** | `audio.py:81` 接收了 `temperature` 参数但未传递给引擎调用，参数被静默忽略 | 在调用 `transcribe_file` / `transcribe_file_stream` 时透传 temperature；引擎不支持时忽略或 warn |
| 0b | **方案一 `word` 级别时间戳未实现** | `timestamp_granularities` 仅支持 `segment` 粒度（`audio.py:141`），`word` 粒度未实现 | 引擎层需开启 `word_timestamps=True`（faster-whisper 支持），在 Segment 中增加 word 级别对齐数据；OpenAI 云端 API 原生支持 |
| 1 | **方案二缺少流式消费端点** | 现有 `file_transcription.py` 只有同步接口，无法实时获取中间结果 | 新增 `/stream` SSE 端点，通过数据库轮询获取新 segment（见方案二 ③） |
| 2 | **后台 worker 未使用流式引擎** | `_run_transcription` 调用 `transcribe_file()` 而非 `transcribe_file_stream()`，无法产生中间事件 | 改为始终调用 `transcribe_file_stream()`，逐条写入数据库 |
| 3 | **任务与流式订阅的解耦** | 当前无机制将后台任务产生的中间结果推送到 SSE 端点 | 后台逐条写入 segment 表，SSE 端点轮询新行（见方案二 ③） |
| 4 | **文件清理策略缺失** | 任务完成后，上传的文件和临时 WAV 未自动清理 | 增加 TTL 清理：任务完成/失败后 N 小时自动删除关联文件 |
| 5 | **重复订阅保护** | 同一 task_id 多次调用 `/stream` 会产生多个订阅者，行为未定义 | 数据库方案天然支持多消费者，各连接独立追踪 last_segment_id |
| 6 | **流式中断恢复** | 客户端断线重连后无法从断点续传 | 数据库方案天然支持：重连时传入 last_segment_id，从该位置继续查询 |

### 架构层面的改进空间

#### A. 统一任务引擎（推荐）

当前 `audio.py` 和 `file_transcription.py` 各自独立实现文件加载、格式转换、转录调用，存在重复。建议抽取公共的 `TranscriptionService`：

```python
class TranscriptionService:
    """统一的转录调度层，供 audio.py 和 file_transcription.py 共用。"""

    async def run(
        self,
        audio_data: bytes,
        engine_name: str,
        stream: bool = False,
        on_segment: Callable | None = None,  # 流式回调
    ) -> TranscriptionResult:
        data = self._ensure_wav(audio_data)
        engine = get_engine(engine_name)

        if stream:
            segments = []
            async for seg in engine.transcribe_file_stream(data):
                segments.append(seg)
                if on_segment:
                    await on_segment(seg)
            text = "".join(s.text for s in segments)
        else:
            text, segments = await engine.transcribe_file(data)

        return TranscriptionResult(text=text, segments=segments, ...)
```

好处：消除重复、保证两种流程行为一致、方便测试。

#### B. WebSocket 流式替代 SSE

SSE 是单向的（服务端 → 客户端），对于方案二的流式消费已经够用。但如果未来需要：
- 客户端中途发送控制指令（暂停/取消/调整参数）
- 双向交互式转录

可以考虑将 `/stream` 改为 WebSocket 端点，协议设计：

```jsonc
// 服务端 → 客户端
{"type": "delta", "text": "...", "start": 0.0, "end": 2.5}
{"type": "done", "text": "...", "segment_count": 42}
{"type": "progress", "percent": 0.6}

// 客户端 → 服务端
{"type": "cancel"}
```

#### C. Webhook 回调（可选）

对于服务端主动推送场景（如 CI/CD 流水线、后台批处理），可在创建任务时指定回调 URL：

```
POST /v1/file/transcriptions
callback_url: https://example.com/webhook

→ 任务完成时 POST callback_url:
{
  "task_id": "...",
  "status": "completed",
  "result": { "text": "...", "segments": [...] }
}
```

这可以避免客户端长时间维持 SSE 连接，适合服务端到服务端的调用场景。

#### D. 方案一文件大小限制

OpenAI 原生限制 25MB 是因为其 API 设计为同步阻塞。OneASR 作为自部署服务可以更灵活：
- 方案一保持 25MB 限制（兼容性）
- 方案二支持 2GB（异步 + 流式天然适合大文件）
- 如果需要，方案一也可以增加 `stream=true` 时的文件上限（流式响应不需要等全部处理完）

---

## 状态机

两套方案共享相同的状态定义：

```
pending → processing → completed
                     → failed
         pending / processing → cancelled
```

方案一没有显式状态（请求-响应模型），状态仅存在于方案二的 `TranscriptionTask` 表中。

---

## 实施优先级建议

| 优先级 | 任务 | 工作量 |
|--------|------|--------|
| **P0** | 方案二新增 `/stream` SSE 端点（数据库轮询） | 中 — 需要 segment 表 + 轮询逻辑 |
| **P0** | 改造 `_run_transcription` 始终使用流式引擎 + 逐条写入 DB | 小 — 移除 stream 标志判断，每条 segment 写入数据库 |
| **P1** | 抽取 `TranscriptionService` 统一转录逻辑 | 中 — 消除 audio.py / file_transcription.py 重复 |
| **P1** | 任务文件自动清理（TTL） | 小 — 后台定时任务 |
| **P2** | 流式断线重连（客户端传入 last_segment_id） | 小 — 数据库方案天然支持，只需前端传参 |
| **P2** | Webhook 回调 | 小 — 新增 callback_url 参数 + HTTP 回调 |
| **P3** | WebSocket 替代 SSE | 大 — 协议重新设计 |
