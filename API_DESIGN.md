# 文件转录接口设计

## 概述

为 OneASR 设计两套文件转录流程，覆盖不同使用场景：

| | 方案一：OpenAI 兼容 | 方案二：异步任务流式 |
|---|---|---|
| **风格** | 单请求同步/流式 | 上传 → 提交 → 流式订阅 / 最终结果 |
| **文件上限** | 25 MB | 2 GB |
| **适用场景** | 小文件快速转录、兼容 OpenAI 生态 | 大文件、长时间转录、需要边转边看 |
| **核心路由** | `POST /v1/audio/transcriptions` | `POST /v1/files/upload` + `POST /v1/tasks/transcriptions` + 两个消费端点 |

---

## 方案一：OpenAI 兼容标准

### 现有实现

已实现在 `app/api/audio.py`，路由 `POST /v1/audio/transcriptions`。

通过 `stream` 表单参数区分两种模式：

```
stream=false  →  同步返回完整结果 (JSON / text / srt / vtt / tsv)
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

// 可选：带时间戳（timestamp_granularities=segment）
data: {"type": "transcript.text.delta", "delta": "识别文本", "start": 0.0, "end": 2.5}

// 完成
data: {"type": "transcript.text.done", "text": "完整文本"}

// 错误
data: {"type": "error", "error": "错误信息"}
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 音视频文件（≤25MB） |
| `model` | string | 是 | 引擎标识（如 `whisper1`） |
| `language` | string | 否 | ISO-639-1 语言代码 |
| `response_format` | string | 否 | `json` / `verbose_json` / `text` / `srt` / `vtt` / `tsv`，默认 `json` |
| `prompt` | string | 否 | 提示词，引导模型风格 |
| `stream` | bool | 否 | 是否 SSE 流式，默认 `false` |
| `temperature` | float | 否 | 采样温度 0-1 |
| `timestamp_granularities` | string | 否 | `word` / `segment` / `word,segment` |

### 同步响应格式

**JSON** (`response_format=json`)：
```json
{"text": "完整转录文本"}
```

**verbose_json** (`response_format=verbose_json`)：
```json
{
  "object": "transcription",
  "text": "完整转录文本",
  "language": "zh",
  "duration": 120.5,
  "segments": [
    {"id": 0, "seek": 0, "start": 0.0, "end": 5.2, "text": "...", "tokens": [], "temperature": 0.0, "avg_logprob": 0.0, "compression_ratio": 0.0, "no_speech_prob": 0.0}
  ]
}
```

**text / srt / vtt / tsv**：返回 `text/plain`，Content-Disposition 附带文件名。

---

## 方案二：异步任务 + 流式消费

### 流程总览

```
客户端                              服务端
  │                                   │
  │  ① POST /v1/files/upload          │
  │  ───────────────────────────────► │  上传文件（支持 MD5 秒传）
  │  ◄── file_id ───────────────────  │
  │                                   │
  │  ② POST /v1/tasks/transcriptions  │
  │  file_uuid: <file_id>             │
  │  stream: true                     │
  │  ───────────────────────────────► │  创建后台转录任务
  │  ◄── task_id + status: pending ─  │
  │                                   │
  │  ③a GET /v1/tasks/transcriptions/{task_id}/stream  (流式)
  │  ───────────────────────────────► │  SSE 订阅，实时接收转录片段
  │  ◄── SSE: delta events ────────  │
  │  ◄── SSE: progress events ─────  │
  │  ◄── SSE: done event ──────────  │
  │                                   │
  │  ③b GET /v1/tasks/transcriptions/{task_id}/result   (最终)
  │  ───────────────────────────────► │  获取完整结果（需等待 completed）
  │  ◄── JSON result ──────────────  │
```

### ① 文件上传（已有）

`POST /v1/files/upload` — 已实现，支持 MD5 秒传。

### ② 创建转录任务

#### 现有接口（改造）

`POST /v1/tasks/transcriptions` — 在现有基础上新增 `stream` 参数。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 否 | 直接上传（三选一） |
| `file_url` | string | 否 | 音频 URL（三选一） |
| `file_uuid` | string | 否 | 已上传文件 ID（三选一） |
| `model` | string | 是 | 引擎标识 |
| `language` | string | 否 | ISO-639-1 语言代码 |
| `response_format` | string | 否 | 输出格式，默认 `json` |
| **`stream`** | **bool** | **否** | **是否启用流式结果推送，默认 `false`** |

**响应**：
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "stream": true,
  "created_at": "2026-01-15T10:30:00+00:00"
}
```

#### 后台处理逻辑（改造）

当 `stream=true` 时，后台 worker 调用 `transcribe_file_stream()` 而非 `transcribe_file()`，并通过内存事件总线推送中间结果：

```
_run_transcription(task_id, stream=true):
    segments = []
    async for seg in engine.transcribe_file_stream(data):
        segments.append(seg)
        event_bus.publish(task_id, {
            type: "transcript.text.delta",
            delta: seg.text,
            start: seg.start,
            end: seg.end,
            index: len(segments)
        })

    # 汇总结果，写入 DB
    full_text = "".join(s.text for s in segments)
    persist_result(task_id, full_text, segments)

    event_bus.publish(task_id, {
        type: "transcript.text.done",
        text: full_text,
        segment_count: len(segments)
    })
    event_bus.close(task_id)
```

### ③a 流式获取结果（新增）

`GET /v1/tasks/transcriptions/{task_id}/stream`

SSE 端点，订阅任务的实时输出。

#### SSE 事件格式

```jsonc
// 任务状态变更
data: {"type": "task.status", "status": "processing", "progress": 0.1}

// 转录增量
data: {"type": "transcript.text.delta", "delta": "识别文本", "start": 0.0, "end": 2.5, "index": 1}

// 转录完成
data: {"type": "transcript.text.done", "text": "完整文本", "segment_count": 42, "duration": 120.5}

// 任务失败
data: {"type": "task.failed", "error": "错误信息"}

// 心跳（每 30s，防止连接超时）
data: {"type": "heartbeat"}
```

#### 实现方案：内存事件总线

```python
import asyncio
from collections import defaultdict

class TaskEventBus:
    """内存 pub/sub，为每个 task 维护一个事件队列池。"""

    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues[task_id].append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue):
        self._queues[task_id] = [x for x in self._queues[task_id] if x is not q]

    def publish(self, task_id: str, event: dict):
        for q in self._queues.get(task_id, []):
            q.put_nowait(event)

    def close(self, task_id: str):
        for q in self._queues.get(task_id, []):
            q.put_nowait(None)  # sentinel
        self._queues.pop(task_id, None)

event_bus = TaskEventBus()
```

#### SSE 端点伪代码

```python
@router.get("/transcriptions/{task_id}/stream")
async def stream_transcription_result(task_id: str):
    # 校验任务存在
    task = await get_task(task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")

    if task.status == "completed":
        # 已完成：直接推送最终结果
        return _emit_final_result(task)

    if task.status == "failed":
        raise HTTPException(500, f"任务失败: {task.error_message}")

    queue = event_bus.subscribe(task_id)

    async def _generate():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=60)
                if event is None:  # task 结束
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            event_bus.unsubscribe(task_id, queue)

    return StreamingResponse(_generate(), media_type="text/event-stream")
```

### ③b 获取最终结果（已有，微调）

`GET /v1/tasks/transcriptions/{task_id}/result`

现有实现基本满足需求。唯一改动：任务 `processing` 状态时返回 202 + 进度信息。

```json
// 202 — 仍在处理
{
  "status": "processing",
  "progress": 0.35,
  "detail": "任务仍在处理中"
}

// 200 — 完成
{
  "text": "完整转录文本",
  "segments": [...],
  "language": "zh",
  "duration": 120.5,
  "segment_count": 42,
  "total_time": 15.3
}
```

---

## 两套方案的接口汇总

```
方案一 (OpenAI 兼容):
  POST   /v1/audio/transcriptions          文件转录 (stream 参数区分同步/流式)

方案二 (异步任务流式):
  POST   /v1/files/upload                  上传文件 (MD5 秒传)
  POST   /v1/tasks/transcriptions           提交转录任务 (新增 stream 参数)
  GET    /v1/tasks/transcriptions/{id}      查询任务状态
  GET    /v1/tasks/transcriptions/{id}/stream  流式获取结果 [新增]
  GET    /v1/tasks/transcriptions/{id}/result  获取最终结果
  DELETE /v1/tasks/transcriptions/{id}      取消任务
  GET    /v1/tasks/transcriptions           列出任务
```

---

## 遗漏分析与改进建议

### 已识别的遗漏

| # | 问题 | 说明 | 建议 |
|---|------|------|------|
| 0a | **方案一 `temperature` 参数未透传** | `audio.py:81` 接收了 `temperature` 参数但未传递给引擎调用，参数被静默忽略 | 在调用 `transcribe_file` / `transcribe_file_stream` 时透传 temperature；引擎不支持时忽略或 warn |
| 0b | **方案一 `word` 级别时间戳未实现** | `timestamp_granularities` 仅支持 `segment` 粒度（`audio.py:141`），`word` 粒度未实现 | 引擎层需开启 `word_timestamps=True`（faster-whisper 支持），在 Segment 中增加 word 级别对齐数据；OpenAI 云端 API 原生支持 |
| 1 | **方案二缺少流式消费端点** | 现有 `tasks.py` 只有 `/result`，无法实时获取中间结果 | 新增 `/stream` SSE 端点（见方案二 ③a） |
| 2 | **后台 worker 未使用流式引擎** | `_run_transcription` 调用 `transcribe_file()` 而非 `transcribe_file_stream()`，无法产生中间事件 | 根据 `stream` 参数选择调用 `transcribe_file()` 或 `transcribe_file_stream()` |
| 3 | **任务与流式订阅的解耦** | 当前无事件总线机制，后台任务产生的中间结果无法推送到 SSE 端点 | 引入内存 `TaskEventBus`（见方案二实现） |
| 4 | **文件清理策略缺失** | 任务完成后，上传的文件和临时 WAV 未自动清理 | 增加 TTL 清理：任务完成/失败后 N 小时自动删除关联文件 |
| 5 | **重复订阅保护** | 同一 task_id 多次调用 `/stream` 会产生多个订阅者，行为未定义 | 服务端应返回 409 Conflict，或允许多订阅者（广播模式）并明确文档化 |
| 6 | **流式中断恢复** | 客户端断线重连后无法从断点续传 | 可选：返回 `Last-Event-ID` header，服务端缓存最近 N 条事件用于重放 |

### 架构层面的改进空间

#### A. 统一任务引擎（推荐）

当前 `audio.py` 和 `tasks.py` 各自独立实现文件加载、格式转换、转录调用，存在重复。建议抽取公共的 `TranscriptionService`：

```python
class TranscriptionService:
    """统一的转录调度层，供 audio.py 和 tasks.py 共用。"""

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
POST /v1/tasks/transcriptions
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
| **P0** | 方案二新增 `/stream` SSE 端点 | 中 — 需要 TaskEventBus + SSE generator |
| **P0** | 改造 `_run_transcription` 支持流式引擎调用 | 小 — 根据 stream 标志选择 transcribe 方法 |
| **P1** | 抽取 `TranscriptionService` 统一转录逻辑 | 中 — 消除 audio.py / tasks.py 重复 |
| **P1** | 任务文件自动清理（TTL） | 小 — 后台定时任务 |
| **P2** | 流式断线重连（Last-Event-ID） | 中 — 需要事件缓存 |
| **P2** | Webhook 回调 | 小 — 新增 callback_url 参数 + HTTP 回调 |
| **P3** | WebSocket 替代 SSE | 大 — 协议重新设计 |
