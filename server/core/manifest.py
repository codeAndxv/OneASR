"""Built-in ASR model manifest and specification catalog.

Predefines official model profiles (drivers, repositories, capabilities,
required files for integrity checks, and default resource policies)
eliminating the need for manual configuration files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelManifest:
    """Specification of an ASR model supported natively by OneASR."""

    id: str
    name: str
    driver: str  # "funasr", "whisper", "xasr", "firered", "qwen", "openai"
    repo: str
    description: str = ""
    categories: list[str] = field(default_factory=lambda: ["FileASR"])
    languages: list[str] = field(default_factory=lambda: ["zh", "en"])
    size_bytes: int = 0
    required_files: list[str] = field(default_factory=list)
    preload: bool = False
    keep_alive: int = 600  # Default 10m; -1 indicates permanent residency
    features: list[str] = field(default_factory=lambda: ["asrAutoLanguageDetect"])
    # Additional driver-specific parameters
    extra: dict[str, Any] = field(default_factory=dict)


# Built-in official model catalog
BUILTIN_MODELS: dict[str, ModelManifest] = {
    # 1. Recommended all-in-one multilingual model
    "sensevoice-small": ModelManifest(
        id="sensevoice-small",
        name="SenseVoice Small",
        driver="funasr",
        repo="iic/SenseVoiceSmall",
        description="Fast multilingual speech recognition with rich audio event detection (zh, en, yue, ja, ko)",
        categories=["RealtimeASR", "FileASR"],
        languages=["zh", "en", "yue", "ja", "ko"],
        size_bytes=480 * 1024 * 1024,
        required_files=["model.pt", "config.yaml"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrEmotionDetect", "asrAudioEventDetect"],
        extra={
            "vad_repo": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        },
    ),
    # 2. Flagship global multilingual model
    "whisper-large-v3-turbo": ModelManifest(
        id="whisper-large-v3-turbo",
        name="Faster-Whisper Large V3 Turbo",
        driver="whisper",
        repo="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        description="High accuracy 99+ languages Whisper model optimized with CTranslate2 for ultra-fast offline transcription",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=1600 * 1024 * 1024,
        required_files=["model.bin", "config.json", "tokenizer.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 3. Standard Faster-Whisper Small
    "whisper-small": ModelManifest(
        id="whisper-small",
        name="Faster-Whisper Small",
        driver="whisper",
        repo="Systran/faster-whisper-small",
        description="Lightweight multilingual transcription model for entry-level machines",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=480 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 4. Standard Faster-Whisper Base
    "whisper-base": ModelManifest(
        id="whisper-base",
        name="Faster-Whisper Base",
        driver="whisper",
        repo="Systran/faster-whisper-base",
        description="Ultra-light multilingual model with low resource footprint",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=145 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 5. Low-latency real-time streaming model
    "xasr-zh-en": ModelManifest(
        id="xasr-zh-en",
        name="X-ASR Realtime Bilingual",
        driver="xasr",
        repo="Gilgamesh-J/X-ASR-zh-en",
        description="Ultra-low latency 160ms streaming speech dictation for Chinese and English",
        categories=["RealtimeASR"],
        languages=["zh", "en"],
        size_bytes=220 * 1024 * 1024,
        required_files=[
            "encoder-160ms.onnx",
            "decoder-160ms.onnx",
            "joiner-160ms.onnx",
            "tokens.txt",
        ],
        preload=True,
        keep_alive=-1,  # Keep resident for immediate mic response
        features=["realtimeStreaming"],
    ),
    # 6. Industrial Chinese offline model
    "paraformer-zh": ModelManifest(
        id="paraformer-zh",
        name="Paraformer Large Chinese",
        driver="funasr",
        repo="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        description="Industrial grade non-autoregressive Chinese speech recognition with integrated VAD & Punctuation",
        categories=["FileASR"],
        languages=["zh"],
        size_bytes=980 * 1024 * 1024,
        required_files=["model.pt", "config.yaml"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 7. FireRed ASR large model
    "firered-asr": ModelManifest(
        id="firered-asr",
        name="FireRed ASR Large",
        driver="firered",
        repo="sherpa-onnx-fire-red-asr-large-zh_en-2025-02-16",
        description="High-precision bilingual Chinese/English end-to-end model based on sherpa-onnx",
        categories=["FileASR"],
        languages=["zh", "en"],
        size_bytes=1100 * 1024 * 1024,
        required_files=["model.onnx", "tokens.txt"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect"],
    ),
    # 8. Qwen ASR model
    "qwen-asr": ModelManifest(
        id="qwen-asr",
        name="Qwen3 ASR 1.7B",
        driver="qwen",
        repo="Qwen/Qwen3-ASR-1.7B",
        description="Qwen speech recognition model with forced alignment support",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=3400 * 1024 * 1024,
        required_files=["model.safetensors", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
        extra={"forced_aligner_name": "Qwen/Qwen3-ForcedAligner-0.6B"},
    ),
}

# Alias resolution mapping (e.g. "whisper-large-v3" -> "whisper-large-v3-turbo")
MODEL_ALIASES: dict[str, str] = {
    "turbo": "whisper-large-v3-turbo",
    "large-v3-turbo": "whisper-large-v3-turbo",
    "faster-whisper-turbo": "whisper-large-v3-turbo",
    "whisper": "whisper-large-v3-turbo",
    "faster-whisper": "whisper-large-v3-turbo",
    "sensevoice": "sensevoice-small",
    "funasr": "sensevoice-small",
    "xasr": "xasr-zh-en",
    "paraformer": "paraformer-zh",
    "qwen": "qwen-asr",
}


def get_manifest(model_id: str) -> ModelManifest | None:
    """Retrieve the manifest for a given model identifier, resolving aliases."""
    normalized_id = model_id.strip().lower()
    target_id = MODEL_ALIASES.get(normalized_id, normalized_id)
    return BUILTIN_MODELS.get(target_id)
