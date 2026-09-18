"""OneASR 模型预下载/预加载脚本。

读取 config.yaml，依次预加载所有已配置的本地模型，触发自动下载与权重加载，
加载完成后立即释放显存/内存，防止内存堆积。

用法:
    python preload_models.py              # 预加载所有 enable: true 的本地模型
    python preload_models.py --all        # 预加载 config.yaml 中的所有本地模型（包含 enable: false）
    python preload_models.py qwen fast-whisper # 仅预加载指定的 provider
    python preload_models.py --list       # 列出所有可预加载的 provider
"""

import argparse
import gc
import logging
import sys
import time
from pathlib import Path

from app.core.config import AppConfig, EngineConfig, PROJECT_ROOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("PreloadModels")


def clean_memory():
    """强制垃圾回收并清理 PyTorch 显存/MPS 缓存。"""
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
            torch.mps.empty_cache()
    except ImportError:
        pass


def preload_whisper(engine_cfg: EngineConfig) -> bool:
    """预加载 faster-whisper 模型（优先本地，缺失自动下载至 model_dir）。"""
    model_path = engine_cfg.resolve_model_path(engine_cfg.model_name)
    download_root = str(engine_cfg.model_dir) if engine_cfg.model_dir else None

    logger.info("[%s] 预加载 faster-whisper: %s (device=%s, compute_type=%s)", engine_cfg.name, model_path, engine_cfg.device, engine_cfg.compute_type)
    try:
        from faster_whisper import WhisperModel

        t0 = time.time()
        model = WhisperModel(
            model_path,
            device=engine_cfg.device,
            compute_type=engine_cfg.compute_type,
            download_root=download_root,
        )
        elapsed = time.time() - t0
        logger.info("[%s] [OK] faster-whisper 模型加载成功 (耗时 %.2fs)", engine_cfg.name, elapsed)
        del model
        clean_memory()
        return True
    except Exception as e:
        logger.error("[%s] [FAIL] faster-whisper 加载失败: %s", engine_cfg.name, e)
        clean_memory()
        return False


def preload_qwen(engine_cfg: EngineConfig) -> bool:
    """预加载 Qwen3-ASR 及 ForcedAligner 模型（优先本地，缺失自动下载）。"""
    model_path = engine_cfg.resolve_model_path(engine_cfg.model_name)
    forced_aligner = engine_cfg.forced_aligner
    config_device = engine_cfg.device
    config_dtype = engine_cfg.dtype

    logger.info("[%s] 预加载 Qwen3-ASR: %s (device=%s, dtype=%s)", engine_cfg.name, model_path, config_device, config_dtype)
    try:
        import torch
        from qwen_asr import Qwen3ASRModel

        device = config_device
        if device.startswith("cuda") and not torch.cuda.is_available():
            device = "mps" if (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()) else "cpu"
            logger.warning("[%s] 当前系统无可用 CUDA，自动切换至: %s", engine_cfg.name, device)

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        dtype = dtype_map.get(config_dtype, torch.bfloat16)
        if device == "cpu" and dtype == torch.float16:
            dtype = torch.float32

        kwargs = {
            "dtype": dtype,
            "device_map": device,
            "max_inference_batch_size": int(engine_cfg.max_inference_batch_size or 32),
            "max_new_tokens": int(engine_cfg.max_new_tokens or 256),
        }

        if engine_cfg.model_dir:
            kwargs["cache_dir"] = str(engine_cfg.model_dir)

        if forced_aligner:
            aligner_path = engine_cfg.resolve_model_path(forced_aligner)
            kwargs["forced_aligner"] = aligner_path
            kwargs["forced_aligner_kwargs"] = {
                "dtype": dtype,
                "device_map": device,
            }
            logger.info("[%s] 包含时间戳对齐模型: %s", engine_cfg.name, aligner_path)

        t0 = time.time()
        model = Qwen3ASRModel.from_pretrained(model_path, **kwargs)
        elapsed = time.time() - t0
        logger.info("[%s] [OK] Qwen3-ASR 模型加载成功 (耗时 %.2fs)", engine_cfg.name, elapsed)
        del model
        clean_memory()
        return True
    except Exception as e:
        logger.error("[%s] [FAIL] Qwen3-ASR 加载失败: %s", engine_cfg.name, e)
        clean_memory()
        return False


def preload_firered(engine_cfg: EngineConfig) -> bool:
    """预加载 FireRedASR 模型（自动下载）。"""
    model_name = engine_cfg.model_name.lower()
    if model_name not in ("aed", "llm"):
        model_name = "aed"

    logger.info("[%s] 预加载 FireRedASR: %s", engine_cfg.name, model_name)
    try:
        import argparse
        import torch
        torch.serialization.add_safe_globals([argparse.Namespace])

        from fireredasr.models.fireredasr import FireRedAsr

        t0 = time.time()
        model = FireRedAsr.from_pretrained(model_name)
        elapsed = time.time() - t0
        logger.info("[%s] [OK] FireRedASR 模型加载成功 (耗时 %.2fs)", engine_cfg.name, elapsed)
        del model
        clean_memory()
        return True
    except Exception as e:
        logger.error("[%s] [FAIL] FireRedASR 加载失败: %s", engine_cfg.name, e)
        clean_memory()
        return False


def preload_xasr(engine_cfg: EngineConfig) -> bool:
    """预加载 X-ASR (sherpa-onnx) 模型。"""
    tokens_path = engine_cfg.resolve_model_path(engine_cfg.tokens)
    encoder_path = engine_cfg.resolve_model_path(engine_cfg.encoder)
    decoder_path = engine_cfg.resolve_model_path(engine_cfg.decoder)
    joiner_path = engine_cfg.resolve_model_path(engine_cfg.joiner)

    # 若未直接指定，尝试从 model_name 所在目录探测
    model_dir_path = Path(engine_cfg.resolve_model_path(engine_cfg.model_name))
    if model_dir_path.is_dir():
        for f in model_dir_path.iterdir():
            if f.name == "tokens.txt" and not (tokens_path and Path(tokens_path).exists()):
                tokens_path = str(f)
            elif "encoder" in f.name and f.suffix == ".onnx" and not (encoder_path and Path(encoder_path).exists()):
                encoder_path = str(f)
            elif "decoder" in f.name and f.suffix == ".onnx" and not (decoder_path and Path(decoder_path).exists()):
                decoder_path = str(f)
            elif "joiner" in f.name and f.suffix == ".onnx" and not (joiner_path and Path(joiner_path).exists()):
                joiner_path = str(f)

    logger.info("[%s] 预加载 X-ASR (sherpa-onnx): encoder=%s, tokens=%s", engine_cfg.name, encoder_path, tokens_path)
    try:
        import sherpa_onnx

        t0 = time.time()
        recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=tokens_path,
            encoder=encoder_path,
            decoder=decoder_path,
            joiner=joiner_path,
            num_threads=int(engine_cfg.num_threads or 1),
            sample_rate=int(engine_cfg.sample_rate or 16000),
            feature_dim=int(getattr(engine_cfg, "feature_dim", 80) or 80),
            decoding_method=engine_cfg.decoding_method or "greedy_search",
            provider=engine_cfg.provider or "cpu",
        )
        elapsed = time.time() - t0
        logger.info("[%s] [OK] X-ASR 模型加载成功 (耗时 %.2fs)", engine_cfg.name, elapsed)
        del recognizer
        clean_memory()
        return True
    except Exception as e:
        logger.error("[%s] [FAIL] X-ASR 模型加载失败: %s", engine_cfg.name, e)
        clean_memory()
        return False


def preload_silero_vad() -> bool:
    """预加载 Silero VAD 模型（自动下载）。"""
    logger.info("[VAD] 预加载 Silero-VAD...")
    try:
        from silero_vad import load_silero_vad
        t0 = time.time()
        model = load_silero_vad()
        elapsed = time.time() - t0
        logger.info("[VAD] [OK] Silero-VAD 模型加载成功 (耗时 %.2fs)", elapsed)
        del model
        clean_memory()
        return True
    except Exception as e:
        logger.warning("[VAD] [SKIP] Silero-VAD 加载失败: %s", e)
        clean_memory()
        return False


# 引擎分发字典
HANDLERS = {
    "faster-whisper": preload_whisper,
    "qwen": preload_qwen,
    "firered": preload_firered,
    "xasr": preload_xasr,
}


def main():
    parser = argparse.ArgumentParser(description="OneASR 模型预下载/预加载工具")
    parser.add_argument("providers", nargs="*", help="指定要预加载的 Provider 名称（默认按配置处理）")
    parser.add_argument("--all", action="store_true", help="预加载所有本地模型（包含 enable: false）")
    parser.add_argument("--list", action="store_true", help="列出配置中的所有 Provider")
    parser.add_argument("--no-vad", action="store_true", help="跳过 Silero-VAD 预加载")
    args = parser.parse_args()

    app_config = AppConfig()
    providers: dict[str, EngineConfig] = app_config.providers

    if args.list:
        print("\n已配置的 ASR Providers:")
        print("-" * 60)
        for name, p_conf in providers.items():
            engine = p_conf.engine_name
            enabled = p_conf.enable
            p_type = p_conf.type
            status = "已启用" if enabled else "已禁用"
            print(f"  • {name:<12} (引擎: {engine:<15} 类型: {p_type:<6} 状态: {status})")
        print("-" * 60)
        return

    # 确定要处理的 providers
    targets: list[EngineConfig] = []
    for name, p_conf in providers.items():
        if p_conf.type != "local":
            continue  # 跳过云端 API

        if args.providers:
            if name in args.providers:
                targets.append(p_conf)
        elif args.all:
            targets.append(p_conf)
        else:
            if p_conf.enable:
                targets.append(p_conf)

    if not targets:
        if args.providers:
            logger.warning("未找到匹配的本地 Provider: %s", args.providers)
        else:
            logger.info("未发现需要预加载的本地 Provider（均已禁用或无本地模型）。如需预加载全部，请加 --all 参数。")
        return

    print("=" * 65)
    print(f"开始预加载本地 ASR 模型 (共 {len(targets)} 个 Provider)...")
    if app_config.model_dir:
        print(f"统一模型根目录 (model_dir): {app_config.model_dir}")
    print("=" * 65)

    results = {}
    for p_conf in targets:
        engine = p_conf.engine_name
        handler = HANDLERS.get(engine)
        if not handler:
            logger.warning("[%s] 未知的引擎类型 '%s'，跳过", p_conf.name, engine)
            results[p_conf.name] = "未知引擎"
            continue

        print(f"\n>>> 正在加载 Provider: {p_conf.name} (engine: {engine})")
        success = handler(p_conf)
        results[p_conf.name] = "成功" if success else "失败"

    if not args.no_vad:
        print("\n>>> 正在加载辅助组件: Silero-VAD")
        preload_silero_vad()

    print("\n" + "=" * 65)
    print("预加载执行总结:")
    print("-" * 65)
    for name, res in results.items():
        mark = "✓" if res == "成功" else "✗"
        print(f"  [{mark}] {name:<15} : {res}")
    print("=" * 65)


if __name__ == "__main__":
    main()
