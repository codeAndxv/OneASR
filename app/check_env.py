"""环境检查脚本：验证 config.yaml 配置及模型/服务可用性。

用法:
    python -m app.check_env              # 检查所有已配置的 Provider
    python -m app.check_env whisper1     # 只检查指定 Provider（可多个）
    python -m app.check_env --list       # 列出所有已配置的 Provider
"""

import argparse
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_whisper(config: dict) -> bool:
    """检查 faster-whisper 模型是否可用，不可用则下载。"""
    model_name = config.get("model_name", "base")
    device = config.get("device", "cpu")
    compute_type = config.get("compute_type", "int8")
    print(f"  模型: {model_name}, 设备: {device}, 计算类型: {compute_type}")

    try:
        from faster_whisper import WhisperModel

        print("  正在加载模型（首次可能需要下载）...")
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        print("  [OK] faster-whisper 模型加载成功")
        del model
        return True
    except Exception as e:
        print(f"  [FAIL] faster-whisper 模型加载失败: {e}")
        return False


def check_firered(config: dict) -> bool:
    """检查 FireRedASR 模型是否可用，不可用则下载。"""
    model_name = config.get("model_name", "aed")
    asr_type = model_name.lower()
    if asr_type not in ("aed", "llm"):
        asr_type = "aed"
    print(f"  模型类型: {asr_type}")

    try:
        import argparse
        import torch
        torch.serialization.add_safe_globals([argparse.Namespace])

        from fireredasr.models.fireredasr import FireRedAsr

        print("  正在加载模型（首次可能需要下载）...")
        model = FireRedAsr.from_pretrained(asr_type)
        print("  [OK] FireRedASR 模型加载成功")
        del model
        return True
    except Exception as e:
        print(f"  [FAIL] FireRedASR 模型加载失败: {e}")
        return False


def check_whisperlivekit(config: dict) -> bool:
    """检查 WhisperLiveKit 模型是否可用。"""
    model_name = config.get("model_name", "base")
    device = config.get("device", "cpu")
    compute_type = config.get("compute_type", "int8")
    print(f"  模型: {model_name}, 设备: {device}")

    try:
        from whisperlivekit import TranscriptionEngine
        from whisperlivekit.config import WhisperLiveKitConfig

        wl_config = WhisperLiveKitConfig.from_kwargs(
            model_size=model_name,
            device=device,
            compute_type=compute_type,
            backend=config.get("backend", "auto"),
            backend_policy=config.get("backend_policy", "simulstreaming"),
            lan=config.get("language", "auto"),
            vac=config.get("vac", True),
            pcm_input=config.get("pcm_input", False),
            diarization=config.get("diarization", False),
            transcription=True,
        )
        print("  正在初始化 TranscriptionEngine（首次可能需要下载模型）...")
        engine = TranscriptionEngine(config=wl_config)
        print("  [OK] WhisperLiveKit 引擎初始化成功")
        del engine
        return True
    except Exception as e:
        print(f"  [FAIL] WhisperLiveKit 引擎初始化失败: {e}")
        return False


def check_cloud_api(name: str, config: dict) -> bool:
    """检查云端 API（OpenAI 兼容接口）是否可用。"""
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "")
    model_name = config.get("model_name", "")
    print(f"  模型: {model_name}, URL: {base_url}")

    if not api_key or not base_url:
        print(f"  [SKIP] 未配置 api_key 或 base_url，跳过")
        return True  # 未配置不算失败

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
        print("  正在测试 API 连接...")
        client.models.list()
        print(f"  [OK] {name} API 连接正常")
        return True
    except Exception as e:
        print(f"  [FAIL] {name} API 连接失败: {e}")
        return False


# 引擎类型名 → (标签, 检查函数)
CHECKERS = {
    "faster-whisper": ("faster-whisper", check_whisper),
    "firered": ("FireRedASR", check_firered),
    "whisperlivekit": ("WhisperLiveKit", check_whisperlivekit),
    "openai": ("OpenAI API", check_cloud_api),
    "mimo": ("MiMo API", check_cloud_api),
}


def check_provider(provider_name: str, prov_conf: dict) -> bool:
    """检查单个 Provider。"""
    engine_type = prov_conf.get("engine", "")
    if engine_type not in CHECKERS:
        print(f"\n[{provider_name}] 跳过：未知引擎类型 '{engine_type}'")
        return True

    label, checker = CHECKERS[engine_type]
    prov_type = prov_conf.get("type", "local")
    print(f"\n[{provider_name}] {label} (engine={engine_type}, type={prov_type})")

    return checker(provider_name, prov_conf) if checker is check_cloud_api else checker(prov_conf)


def main():
    parser = argparse.ArgumentParser(description="OneASR 环境检查")
    parser.add_argument("providers", nargs="*", help="要检查的 Provider 名称（默认检查所有已配置的 Provider）")
    parser.add_argument("--list", action="store_true", help="列出所有已配置的 Provider")
    args = parser.parse_args()

    config = load_config()
    providers_conf = config.get("providers", {})
    default_provider = config.get("default_provider", "")

    if args.list:
        for name, conf in providers_conf.items():
            engine_type = conf.get("engine", "?")
            marker = " <-- default" if name == default_provider else ""
            print(f"  {name} (engine={engine_type}, type={conf.get('type', 'local')}){marker}")
        return

    print("=" * 50)
    print("OneASR 环境检查")
    print("=" * 50)

    if not providers_conf:
        print("\n[WARN] config.yaml 中未配置任何 Provider")
        return

    targets = args.providers if args.providers else list(providers_conf.keys())

    results = {}
    for name in targets:
        if name not in providers_conf:
            print(f"\n[{name}] 配置中不存在，跳过")
            continue
        results[name] = check_provider(name, providers_conf[name])

    print("\n" + "=" * 50)
    print("检查结果汇总")
    print("=" * 50)
    all_ok = True
    for name, ok in results.items():
        tag = "OK" if ok else "FAIL"
        marker = " <-- default" if name == default_provider else ""
        print(f"  [{tag}] {name}{marker}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n所有 Provider 检查通过")
    else:
        print("\n部分 Provider 检查失败，请根据上方提示修复")
        sys.exit(1)


if __name__ == "__main__":
    main()
