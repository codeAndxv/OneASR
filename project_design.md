# OneASR 项目架构与引擎设计文档

本文档记录 OneASR 的整体架构设计理念，以及各 ASR 引擎（如 X-ASR、Faster-Whisper、Qwen3-ASR 等）的技术选型、工作机制与对比分析。

---

## 目录

- [一、引擎特性对比：X-ASR vs Whisper](#一引擎特性对比x-asr-vs-whisper)
  - [1. 核心结论](#1-核心结论)
  - [2. 详细技术对比表](#2-详细技术对比表)
  - [3. 自动语种检测 (Auto Detect) 原理解析](#3-自动语种检测-auto-detect-原理解析)
  - [4. 中英混合 (Code-Switching) 场景表现](#4-中英混合-code-switching-场景表现)
  - [5. 选型与应用场景建议](#5-选型与应用场景建议)
  - [6. X-ASR 的 LanguageCode 调用链分析（代码级追踪）](#6-x-asr-的-languagecode-调用链分析代码级追踪)
- [二、OneASR 引擎架构概览](#二oneasr-引擎架构概览)
  - [1. 流式实时识别 (Realtime ASR)](#1-流式实时识别-realtime-asr)
  - [2. 异步文件转录 (File ASR)](#2-异步文件转录-file-asr)

---

## 一、引擎特性对比：X-ASR vs Whisper

在 OneASR 中，主要集成了以 **X-ASR (基于 sherpa-onnx Zipformer)** 为代表的流式 Transducer 引擎，以及以 **Faster-Whisper** 为代表的自回归 Seq2Seq 引擎。两者在语种选择与自动检测（Auto Detect）机制上有本质区别。

### 1. 核心结论

- **Whisper (Faster-Whisper)**：支持 **显式的“语言识别（Language Identification / LID）与自动检测（Auto Detect）”**。Whisper 是自回归 Encoder-Decoder 架构，解码前会先预测一个特殊的语种 Token（如 `<|zh|>`, `<|en|>`），从而切换到该语言的解码空间。
- **X-ASR (Zipformer Transducer)**：**不需要、也不存在显式的 Auto-Detect 步骤**。它是**天然“端到端多语种/混合语种直出”**的流式模型。

---

### 2. 详细技术对比表

| 特性维度 | Whisper / Faster-Whisper | X-ASR (sherpa-onnx Zipformer) |
| :--- | :--- | :--- |
| **模型基础架构** | **Encoder-Decoder (自回归 Seq2Seq)** | **RNN-T / Transducer (流式端到端)** |
| **实时/流式延迟** | 块级切片 (VAD + 伪流式 / chunk-based)，延迟通常在 0.5s ~ 2.0s | **原生帧级低延迟 (160ms chunk / 逐帧流式)**，延迟约 100ms ~ 300ms |
| **语言选择方式** | 需指定 `language="zh"` 或 `language=None`（触发自动检测） | **底层无语言参数**（`sherpa_onnx.OnlineRecognizer` 无语种入参） |
| **多语言工作机制** | 解码前先做 30s 音频的 LID 预测，选定目标语种 Token 后按该语种解码 | 模型的 `tokens.txt` 词表中同时包含中文字符与英文子词，**直接逐帧预测汉字或英文** |
| **中英混合 (Code-Switching)** | 一句话若中英夹杂，模型可能偏向主导语言或出现幻觉/翻译现象 | **天然支持中英混合识别**，中文输出汉字、英文输出单词，自由切换 |
| **支持的语种范围** | 涵盖 99+ 种常见自然语言 | **严格受限于加载的模型权重与词表**（如当前配置的 `xasr-zh-en` 仅支持中英文） |
| **适用核心场景** | 离线长音频转录、会议记录、多语种字幕生成、高精度文件转写 | 直播实时字幕、实时同传前置识别、会议实时上屏、语音输入法 |

---

### 3. 自动语种检测 (Auto Detect) 原理解析

#### Whisper 的 Auto Detect 机制
1. Whisper 的词表前缀中内置了 99+ 种语言的标记符（如 `<|zh|>`, `<|en|>`, `<|ja|>` 等）。
2. 当输入音频送入 Encoder 后，Decoder 在预测首个文本 Token 之前，首先计算所有语言 Token 的概率分布。
3. 概率最高的语种即被判定为该段语音的所属语言（例如判定为中文 `<|zh|>`）。
4. 随后 Decoder 将强制以该语言模式生成后续文本。若音频前半段与后半法语种不一致，可能导致后半段被强行以第一种语言解码。

#### X-ASR (Zipformer Transducer) 的直接解码机制
1. Transducer 由 Audio Encoder、Prediction Network 和 Joiner 三部分构成。
2. 模型训练时，中英文语料被混合标注。词表（`tokens.txt`）里同时包含数千个常用汉字和英文 BPE 子词单元。
3. 当接收到音频流时，Joiner 结合声学特征与历史已输出 Token，直接逐帧输出汉字或英文字符的概率。
4. **系统不需要（也无法）在解码前设置语言**，模型根据发音特征直接命中对应的文字表项。

---

### 4. 中英混合 (Code-Switching) 场景表现

- **典型案例**：“*这个 PR 我们需要先跑一下 benchmark 测试*”
  - **Whisper**：如果设置了 `language="zh"`，通常能正常输出，但有时英文部分会被拼音化或漏词；如果未指定语言且英文词占比较多，可能误判全句为英文并尝试翻译。
  - **X-ASR**：由于中英文字符在同一个解码图中共存，模型在听到中文时预测中文汉字，在听到“PR”、“benchmark”等标准英文发音时无缝输出英文单词，中英夹杂识别非常流畅自然。

---

### 5. 选型与应用场景建议

1. **选择 X-ASR 的场景**：
   - 极度关注**低延迟、即时上屏**的流式场景（如桌面实时字幕、语音输入）。
   - 主要语种为**中文、英文及中英混合**环境。
   - 设备资源有限（CPU 占用低，ONNX 运行时轻量）。

2. **选择 Faster-Whisper 的场景**：
   - **离线音频/视频文件转录**（批量音视频转字幕）。
   - 需要覆盖日、韩、法、德、西等多语种或**语种完全未知**需自动识别的环境。
   - 对单句断句准确度、标点及文字修饰有更高要求的离线归档场景。

---

### 6. X-ASR 的 LanguageCode 调用链分析（代码级追踪）

在实际全链路调用中（如 DuRT $\rightarrow$ OneASR），客户端传入的 `languageCode` 对 X-ASR 引擎的处理流程如下：

#### 1. 客户端发送 (DuRT: `OneASRExecutor.swift`)
客户端将用户选择的 `language`（如 `"zh"`、`"en"`）打包进 `session.update` 配置包发送给 OneASR 服务端。

#### 2. 服务端协议层接收 (OneASR: `app/api/realtime_ext.py`)
服务端解析并保存了该字段：
```python
session.language = transcription_cfg.get("language")
logger.info("[realtimeext-xasr] 启动 X-ASR 原生流式会话: language=%s", session.language)
```
> **说明**：在 X-ASR 路径下，此字段仅用于**日志记录**以及向客户端原样回传 `session.updated` 握手确认事件，并不参与实际音频解码。

#### 3. 底层引擎解码 (OneASR: `app/engines/xasr_engine.py`)
在引擎流式会话创建时：
```python
def create_stream_session(self, input_sample_rate: int | None = None) -> XASRStreamingSession:
    self._ensure_recognizer()
    return XASRStreamingSession(self._recognizer, self.sample_rate, input_sample_rate=input_sample_rate)
```
- `XASREngine` 与 `XASRStreamingSession` 的所有方法中**完全没有接收或使用 `language` 参数**。
- 底层 `sherpa_onnx.OnlineRecognizer.from_transducer(...)` 和 `recognizer.create_stream()` 属于 C++ 封装的 Zipformer 模型，其底层 API 本身**没有提供语种入参**。
- 模型在收到 PCM 音频时，直接通过声学特征在自带中英词表中逐帧计算概率输出汉字或英文。

---

## 二、OneASR 引擎架构概览

### 1. 流式实时识别 (Realtime ASR)
- 提供标准 OpenAI Realtime WebSocket 协议（`/v1/realtime`）与 OneASR 扩展协议（`/v1/realtimeext`）。
- 扩展协议支持 `sentence.delta`（词级增量）与 `sentence.committed`（带时间戳的定稿句子），为上层客户端（如 DuRT）提供双流渲染支持。

### 2. 异步文件转录 (File ASR)
- 采用标准三步接口：`POST /v1/files`（上传） $\rightarrow$ `POST /v1/transcriptions/tasks`（创建任务） $\rightarrow$ `GET /v1/transcriptions/tasks/{id}` 或 SSE 流式接收结果。
- 内置 ASR-Toolkit VAD 智能切片与标点规范化管线。
