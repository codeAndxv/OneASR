"""环境检查脚本：验证 config.yaml 配置及本地模型/云端服务可用性。

用法:
    uv run python -m server.check_env              # 检查所有已配置的 Provider
    uv run python -m server.check_env faster-whisper  # 只检查指定 Provider（可多个）
    uv run python -m server.check_env --list       # 列出所有已配置的 Provider
"""

import argparse
import sys

from cli.model import CLOUD_ENGINES, resolve_provider_specs, verify_model_dir
from server.core.config import AppConfig, EngineConfig


def check_local_provider(cfg: EngineConfig) -> bool:
    """检查本地 Provider 的模型目录完整性（基于 cli.model 规则，零内存开销）。"""
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


def check_cloud_provider(cfg: EngineConfig) -> bool:
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


def check_provider(cfg: EngineConfig) -> bool:
    """检查单个 Provider。"""
    eng = (cfg.engine_name or cfg.name).lower()
    is_cloud = cfg.type == "cloud" or eng in CLOUD_ENGINES
    prov_type = "cloud" if is_cloud else "local"
    status_str = "enabled" if cfg.enable else "disabled"
    print(f"\n[{cfg.name}] engine={cfg.engine_name}, type={prov_type}, status={status_str}")

    if is_cloud:
        return check_cloud_provider(cfg)
    return check_local_provider(cfg)


def main():
    parser = argparse.ArgumentParser(description="OneASR 环境检查")
    parser.add_argument("providers", nargs="*", help="要检查的 Provider 名称（默认检查所有已配置的 Provider）")
    parser.add_argument("--list", action="store_true", help="列出所有已配置的 Provider")
    args = parser.parse_args()

    app_cfg = AppConfig()
    providers = app_cfg.providers

    if args.list:
        for name, cfg in providers.items():
            print(f"  {name:<18} (engine={cfg.engine_name}, enable={cfg.enable}, model={cfg.model_name})")
        return

    print("=" * 60)
    print("OneASR 环境检查")
    print("=" * 60)

    if not providers:
        print("\n[WARN] config.yaml 中未配置任何 Provider")
        return

    targets = args.providers if args.providers else list(providers.keys())

    results = {}
    for name in targets:
        if name not in providers:
            print(f"\n[{name}] 配置中不存在，跳过")
            continue
        results[name] = check_provider(providers[name])

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
