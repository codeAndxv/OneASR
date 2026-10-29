"""环境检查脚本：验证本地模型及服务可用性。

用法:
    uv run python -m server.check_env              # 检查所有模型
    uv run python -m server.check_env sensevoice-small  # 只检查指定模型（可多个）
    uv run python -m server.check_env --list       # 列出所有模型
"""

import argparse
import sys

from cli.model import CLOUD_ENGINES, resolve_provider_specs, verify_model_dir
from server.core.config import AppConfig, EngineConfig


def check_local_model(cfg: EngineConfig) -> bool:
    """检查本地模型的目录完整性（基于 cli.model 规则，零内存开销）。"""
    specs = resolve_provider_specs(cfg, include_aligner=False)
    if not specs:
        print(f"  [WARN] 未能解析本地模型规格: {cfg.name}")
        return False

    all_ok = True
    for spec in specs:
        ok, reasons = verify_model_dir(spec.engine_name, spec.local_dir, spec.required_files)
        if ok:
            print(f"  [OK] {spec.display_name} -> {spec.relative_local_dir} (repo: {spec.ms_repo_id})")
        else:
            all_ok = False
            print(f"  [FAIL] {spec.display_name} -> {spec.relative_local_dir} ({'; '.join(reasons)})")
            print(f"         请运行: uv run python -m cli.model pull {cfg.name}")
    return all_ok


def check_cloud_model(cfg: EngineConfig) -> bool:
    """检查云端 API（OpenAI 兼容接口）是否可用。"""
    print(f"  模型: {cfg.model_name}, URL: {cfg.base_url}")

    if not cfg.api_key or not cfg.base_url:
        print("  [SKIP] 未配置 api_key 或 base_url，跳过")
        return True

    try:
        from openai import OpenAI

        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url.rstrip("/"))
        print("  正在测试 API 连接...")
        client.models.list()
        print(f"  [OK] {cfg.name} API 连接正常")
        return True
    except Exception as e:
        print(f"  [FAIL] {cfg.name} API 连接失败: {e}")
        return False


def check_model(cfg: EngineConfig) -> bool:
    """检查单个模型。"""
    eng = (cfg.engine_name or cfg.name).lower()
    is_cloud = cfg.type == "cloud" or eng in CLOUD_ENGINES
    prov_type = "cloud" if is_cloud else "local"
    status_str = "enabled" if cfg.enable else "disabled"
    print(f"\n[{cfg.name}] engine={cfg.engine_name}, type={prov_type}, status={status_str}")

    if is_cloud:
        return check_cloud_model(cfg)
    return check_local_model(cfg)


check_provider = check_model


def main():
    parser = argparse.ArgumentParser(description="OneASR 环境检查")
    parser.add_argument("models", nargs="*", help="要检查的模型 ID（默认检查所有已配置的模型）")
    parser.add_argument("--list", action="store_true", help="列出所有模型")
    args = parser.parse_args()

    app_cfg = AppConfig()
    models = app_cfg.models

    if args.list:
        for name, cfg in models.items():
            print(f"  {name:<18} (engine={cfg.engine_name}, enable={cfg.enable}, model={cfg.model_name})")
        return

    print("=" * 60)
    print("OneASR 环境与模型检查")
    print("=" * 60)

    if not models:
        print("\n[WARN] 未扫描到任何可用模型")
        return

    targets = args.models if args.models else list(models.keys())

    results = {}
    for name in targets:
        if name not in models:
            print(f"\n[{name}] 模型不存在，跳过")
            continue
        results[name] = check_model(models[name])

    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)
    all_ok = True
    for name, ok in results.items():
        tag = "OK" if ok else "FAIL"
        print(f"  [{tag}] {name}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n所有目标 Provider 检查通过")
    else:
        print("\n部分 Provider 检查失败，请运行 `uv run python -m cli.model pull` 下载缺失模型")
        sys.exit(1)


if __name__ == "__main__":
    main()
