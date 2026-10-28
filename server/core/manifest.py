"""Built-in ASR model manifest and specification catalog.

Predefines official model profiles (drivers, ModelScope and HuggingFace repositories,
capabilities, required files for integrity checks, and default resource policies)
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
    ms_repo: str  # ModelScope 官方模型仓库唯一标识
    hf_repo: str  # HuggingFace 官方模型仓库唯一标识
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
        ms_repo="iic/SenseVoiceSmall",
        hf_repo="FunAudioLLM/SenseVoiceSmall",
        description="Fast multilingual speech recognition with rich audio event detection (zh, en, yue, ja, ko)",
        categories=["RealtimeASR", "FileASR"],
        languages=["zh", "en", "yue", "ja", "ko"],
        size_bytes=480 * 1024 * 1024,
        required_files=["model.pt", "config.yaml"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrEmotionDetect", "asrAudioEventDetect"],
        extra={
            "vad_ms_repo": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
            "vad_hf_repo": "funasr/fsmn-vad",
        },
    ),
    # 2. Flagship global multilingual model
    "whisper-large-v3-turbo": ModelManifest(
        id="whisper-large-v3-turbo",
        name="Faster-Whisper Large V3 Turbo",
        driver="whisper",
        ms_repo="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        hf_repo="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
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
        ms_repo="Systran/faster-whisper-small",
        hf_repo="Systran/faster-whisper-small",
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
        ms_repo="Systran/faster-whisper-base",
        hf_repo="Systran/faster-whisper-base",
        description="Ultra-light multilingual model with low resource footprint",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=145 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 5. Bundled starter Faster-Whisper Tiny (ultra-fast starter model)
    "whisper-tiny": ModelManifest(
        id="whisper-tiny",
        name="Faster-Whisper Tiny",
        driver="whisper",
        ms_repo="Systran/faster-whisper-tiny",
        hf_repo="Systran/faster-whisper-tiny",
        description="Ultra-fast starter multilingual model (~75MB), bundled for zero-configuration out-of-the-box dictation",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=75 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 6. Faster-Whisper Medium
    "whisper-medium": ModelManifest(
        id="whisper-medium",
        name="Faster-Whisper Medium",
        driver="whisper",
        ms_repo="Systran/faster-whisper-medium",
        hf_repo="Systran/faster-whisper-medium",
        description="High-precision multilingual model (~1.4GB), excellent accuracy for long-form audio and podcasts",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=1420 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 7. Faster-Whisper Large V1
    "whisper-large-v1": ModelManifest(
        id="whisper-large-v1",
        name="Faster-Whisper Large V1",
        driver="whisper",
        ms_repo="Systran/faster-whisper-large-v1",
        hf_repo="Systran/faster-whisper-large-v1",
        description="Full-scale Whisper first generation multilingual model",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=3090 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 8. Faster-Whisper Large V2
    "whisper-large-v2": ModelManifest(
        id="whisper-large-v2",
        name="Faster-Whisper Large V2",
        driver="whisper",
        ms_repo="Systran/faster-whisper-large-v2",
        hf_repo="Systran/faster-whisper-large-v2",
        description="Full-scale Whisper second generation flagship model with proven multilingual robustness",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=3090 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 9. Faster-Whisper Large V3
    "whisper-large-v3": ModelManifest(
        id="whisper-large-v3",
        name="Faster-Whisper Large V3",
        driver="whisper",
        ms_repo="Systran/faster-whisper-large-v3",
        hf_repo="Systran/faster-whisper-large-v3",
        description="Full-scale Whisper flagship model with 128 Mel-frequency bins for highest accuracy",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=3090 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 10. Faster-Whisper Tiny (English-only)
    "whisper-tiny-en": ModelManifest(
        id="whisper-tiny-en",
        name="Faster-Whisper Tiny (EN)",
        driver="whisper",
        ms_repo="Systran/faster-whisper-tiny.en",
        hf_repo="Systran/faster-whisper-tiny.en",
        description="Ultra-fast English-specialized model (~75MB)",
        categories=["FileASR"],
        languages=["en"],
        size_bytes=75 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 11. Faster-Whisper Base (English-only)
    "whisper-base-en": ModelManifest(
        id="whisper-base-en",
        name="Faster-Whisper Base (EN)",
        driver="whisper",
        ms_repo="Systran/faster-whisper-base.en",
        hf_repo="Systran/faster-whisper-base.en",
        description="Lightweight English-specialized transcription model",
        categories=["FileASR"],
        languages=["en"],
        size_bytes=145 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 12. Faster-Whisper Small (English-only)
    "whisper-small-en": ModelManifest(
        id="whisper-small-en",
        name="Faster-Whisper Small (EN)",
        driver="whisper",
        ms_repo="Systran/faster-whisper-small.en",
        hf_repo="Systran/faster-whisper-small.en",
        description="High-accuracy English-specialized model",
        categories=["FileASR"],
        languages=["en"],
        size_bytes=480 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 13. Faster-Whisper Medium (English-only)
    "whisper-medium-en": ModelManifest(
        id="whisper-medium-en",
        name="Faster-Whisper Medium (EN)",
        driver="whisper",
        ms_repo="Systran/faster-whisper-medium.en",
        hf_repo="Systran/faster-whisper-medium.en",
        description="Production grade English transcription model",
        categories=["FileASR"],
        languages=["en"],
        size_bytes=1420 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 14. Distil-Whisper Small (English-only)
    "distil-whisper-small-en": ModelManifest(
        id="distil-whisper-small-en",
        name="Distil-Whisper Small (EN)",
        driver="whisper",
        ms_repo="Systran/faster-distil-whisper-small.en",
        hf_repo="Systran/faster-distil-whisper-small.en",
        description="Distilled English model (~330MB), 6x faster inference with minimal accuracy loss",
        categories=["FileASR"],
        languages=["en"],
        size_bytes=330 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 15. Distil-Whisper Medium (English-only)
    "distil-whisper-medium-en": ModelManifest(
        id="distil-whisper-medium-en",
        name="Distil-Whisper Medium (EN)",
        driver="whisper",
        ms_repo="Systran/faster-distil-whisper-medium.en",
        hf_repo="Systran/faster-distil-whisper-medium.en",
        description="Distilled English model (~790MB), excellent speedup for long-form podcasts",
        categories=["FileASR"],
        languages=["en"],
        size_bytes=790 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 16. Distil-Whisper Large V2
    "distil-whisper-large-v2": ModelManifest(
        id="distil-whisper-large-v2",
        name="Distil-Whisper Large V2",
        driver="whisper",
        ms_repo="Systran/faster-distil-whisper-large-v2",
        hf_repo="Systran/faster-distil-whisper-large-v2",
        description="Distilled multilingual large model (~1.5GB) with high inference throughput",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=1510 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 17. Distil-Whisper Large V3
    "distil-whisper-large-v3": ModelManifest(
        id="distil-whisper-large-v3",
        name="Distil-Whisper Large V3",
        driver="whisper",
        ms_repo="Systran/faster-distil-whisper-large-v3",
        hf_repo="Systran/faster-distil-whisper-large-v3",
        description="State-of-the-art distilled multilingual model (~1.5GB) based on Large V3",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=1510 * 1024 * 1024,
        required_files=["model.bin", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 18. Low-latency real-time streaming model
    "xasr-zh-en": ModelManifest(
        id="xasr-zh-en",
        name="X-ASR Realtime Bilingual",
        driver="xasr",
        ms_repo="Gilgamesh-J/X-ASR-zh-en",
        hf_repo="Gilgamesh-J/X-ASR-zh-en",
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
        preload=False,
        keep_alive=600,
        features=["realtimeStreaming"],
    ),
    # 19. Industrial Chinese offline model
    "paraformer-zh": ModelManifest(
        id="paraformer-zh",
        name="Paraformer Large Chinese",
        driver="funasr",
        ms_repo="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        hf_repo="funasr/paraformer-zh",
        description="Industrial grade non-autoregressive Chinese speech recognition with integrated VAD & Punctuation",
        categories=["FileASR"],
        languages=["zh"],
        size_bytes=980 * 1024 * 1024,
        required_files=["model.pt", "config.yaml"],
        preload=False,
        keep_alive=600,
        features=["asrWordTimestamp"],
    ),
    # 20. Fun-ASR Nano next-generation Audio-LLM
    "fun-asr-nano": ModelManifest(
        id="fun-asr-nano",
        name="Fun-ASR Nano 0.8B",
        driver="funasr",
        ms_repo="FunAudioLLM/Fun-ASR-Nano-2512",
        hf_repo="FunAudioLLM/Fun-ASR-Nano-2512",
        description="Next-generation lightweight Audio-LLM base (SenseVoice + Qwen3) for accurate context understanding",
        categories=["FileASR"],
        languages=["zh", "en", "yue", "ja", "ko"],
        size_bytes=1600 * 1024 * 1024,
        required_files=["model.pt", "config.yaml"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
    ),
    # 21. FireRed ASR large model
    "firered-asr": ModelManifest(
        id="firered-asr",
        name="FireRed ASR Large",
        driver="firered",
        ms_repo="csukuangfj/sherpa-onnx-fire-red-asr-large-zh_en-2025-02-16",
        hf_repo="csukuangfj/sherpa-onnx-fire-red-asr-large-zh_en-2025-02-16",
        description="High-precision bilingual Chinese/English end-to-end model based on sherpa-onnx",
        categories=["FileASR"],
        languages=["zh", "en"],
        size_bytes=1100 * 1024 * 1024,
        required_files=["model.onnx", "tokens.txt"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect"],
    ),
    # 22. FireRedASR2 AED 1.1B
    "firered2-aed": ModelManifest(
        id="firered2-aed",
        name="FireRedASR2 AED 1.1B",
        driver="firered",
        ms_repo="FireRedTeam/FireRedASR2-AED",
        hf_repo="FireRedTeam/FireRedASR2-AED",
        description="Industrial AED speech model by Xiaohongshu, optimized for lyrics, noise robustness, and accents",
        categories=["FileASR"],
        languages=["zh", "en"],
        size_bytes=2200 * 1024 * 1024,
        required_files=["model.pt", "config.yaml"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect"],
    ),
    # 23. FireRedASR2 LLM 8.3B
    "firered2-llm": ModelManifest(
        id="firered2-llm",
        name="FireRedASR2 LLM 8.3B",
        driver="firered",
        ms_repo="FireRedTeam/FireRedASR2-LLM",
        hf_repo="FireRedTeam/FireRedASR2-LLM",
        description="Flagship 8.3B Encoder-LLM model by Xiaohongshu with 20+ Chinese dialect and code-switching support",
        categories=["FileASR"],
        languages=["zh", "en", "dialects"],
        size_bytes=16000 * 1024 * 1024,
        required_files=["model.safetensors", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect"],
    ),
    # 24. Qwen ASR model
    "qwen-asr": ModelManifest(
        id="qwen-asr",
        name="Qwen3 ASR 1.7B",
        driver="qwen",
        ms_repo="Qwen/Qwen3-ASR-1.7B",
        hf_repo="Qwen/Qwen3-ASR-1.7B",
        description="Qwen speech recognition model with forced alignment support",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=3400 * 1024 * 1024,
        required_files=["model.safetensors", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
        extra={
            "forced_aligner_ms_repo": "Qwen/Qwen3-ForcedAligner-0.6B",
            "forced_aligner_hf_repo": "Qwen/Qwen3-ForcedAligner-0.6B",
        },
    ),
    # 25. Qwen3 ASR 0.6B compact model
    "qwen3-asr-0.6b": ModelManifest(
        id="qwen3-asr-0.6b",
        name="Qwen3 ASR 0.6B",
        driver="qwen",
        ms_repo="Qwen/Qwen3-ASR-0.6B",
        hf_repo="Qwen/Qwen3-ASR-0.6B",
        description="Compact 0.6B Qwen speech model for low-resource environments and fast transcription",
        categories=["FileASR"],
        languages=["multilingual"],
        size_bytes=1200 * 1024 * 1024,
        required_files=["model.safetensors", "config.json"],
        preload=False,
        keep_alive=600,
        features=["asrAutoLanguageDetect", "asrWordTimestamp"],
        extra={
            "forced_aligner_ms_repo": "Qwen/Qwen3-ForcedAligner-0.6B",
            "forced_aligner_hf_repo": "Qwen/Qwen3-ForcedAligner-0.6B",
        },
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
    "qwen-0.6b": "qwen3-asr-0.6b",
    "qwen-1.7b": "qwen-asr",
    "qwen3-asr": "qwen-asr",
    "firered": "firered-asr",
    "firered2": "firered2-aed",
    "firered-aed": "firered2-aed",
    "firered-llm": "firered2-llm",
    "funasr-nano": "fun-asr-nano",
    "fun-asr": "fun-asr-nano",
}


def get_manifest(model_id: str) -> ModelManifest | None:
    """Retrieve the manifest for a given model identifier, resolving aliases."""
    normalized_id = model_id.strip().lower()
    target_id = MODEL_ALIASES.get(normalized_id, normalized_id)
    return BUILTIN_MODELS.get(target_id)
