"""OneASR Unified CLI (Ollama-style command-line interface).

Usage examples:
    oneasr serve                       # Start the OneASR backend daemon
    oneasr list                        # List all models and their local status
    oneasr pull sensevoice-small       # Pull and verify a model
    oneasr rm sensevoice-small         # Remove local model files
    oneasr ps                          # Show models currently loaded in VRAM/memory
    oneasr info                        # Display hardware and storage diagnostics
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.core.manifest import BUILTIN_MODELS, get_manifest
from server.core.paths import get_models_dir, get_oneasr_home, get_settings_path
from server.core.scanner import scan_all_models


def format_bytes(bytes_val: int) -> str:
    """Format bytes into human-readable representation."""
    if not bytes_val or bytes_val <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


def cmd_list(args: argparse.Namespace) -> int:
    """List all available models, their local readiness, and disk footprint."""
    scanned = scan_all_models().values()
    print(f"{'NAME':<24} {'ID':<25} {'SIZE':<10} {'STATUS':<12} {'ENGINE':<14}")
    print("-" * 88)

    for m in scanned:
        name = m.name or m.id
        status_label = "Ready" if m.status == "ready" else "Available"
        if getattr(m, "loaded", False):
            status_label = "In VRAM"
        elif m.status == "downloading":
            status_label = "Downloading"

        size_str = format_bytes(m.size_on_disk if m.status == "ready" else m.size_expected)
        engine_str = m.driver or "Native"
        print(f"{name[:22]:<24} {m.id[:23]:<25} {size_str:<10} {status_label:<12} {engine_str:<14}")

    return 0


def cmd_ps(args: argparse.Namespace) -> int:
    """List models currently loaded in memory/VRAM."""
    # Query running daemon if available
    import urllib.request
    try:
        url = "http://127.0.0.1:8020/v1/x/models"
        req = urllib.request.Request(url, headers={"Authorization": "Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            loaded = [m for m in models if m.get("loaded", False)]
            if not loaded:
                print("No models currently loaded in memory.")
                return 0

            print(f"{'NAME':<24} {'ID':<25} {'SIZE':<10} {'VRAM STATUS':<14}")
            print("-" * 75)
            for m in loaded:
                name = m.get("name") or m.get("id")
                size = format_bytes(m.get("size_on_disk", 0))
                print(f"{name[:22]:<24} {m.get('id')[:23]:<25} {size:<10} Active in VRAM")
            return 0
    except Exception:
        print("OneASR daemon is not running (checked 127.0.0.1:8020).")
        return 0


def cmd_pull(args: argparse.Namespace) -> int:
    """Pull model weights with terminal progress."""
    model_id = args.model_id
    source = args.source

    # Check if daemon is active on 8020
    import urllib.request
    daemon_online = False
    try:
        urllib.request.urlopen("http://127.0.0.1:8020/health", timeout=0.8)
        daemon_online = True
    except Exception:
        daemon_online = False

    if daemon_online:
        print(f"Connecting to OneASR daemon to pull '{model_id}'...")
        import urllib.request
        pull_url = "http://127.0.0.1:8020/v1/x/models/pull"
        payload = json.dumps({"model_id": model_id, "hub": source}).encode()
        req = urllib.request.Request(
            pull_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
                for line in resp:
                    line_str = line.decode().strip()
                    if line_str.startswith("data: "):
                        data = json.loads(line_str[6:])
                        status = data.get("status")
                        percent = data.get("percent", 0)
                        speed = data.get("speed", "")
                        print(f"\rpulling {model_id}: {percent}% [{speed}]", end="", flush=True)
                        if status == "ready":
                            print(f"\rsuccess: model '{model_id}' is ready!               ")
                            return 0
                        elif status == "failed":
                            print(f"\nerror: {data.get('error')}")
                            return 1
            print()
            return 0
        except Exception as e:
            print(f"\nError communicating with daemon: {e}. Falling back to direct download...")

    # Direct offline pull via cli.model
    from cli.model import main as model_cli_main
    return model_cli_main(["pull", model_id, "--source", source])


def cmd_rm(args: argparse.Namespace) -> int:
    """Remove local model files."""
    model_id = args.model_id
    models_dir = get_models_dir()
    target = models_dir / model_id

    if not target.exists():
        print(f"Model '{model_id}' not found in {models_dir}")
        return 1

    shutil.rmtree(target, ignore_errors=True)
    print(f"Deleted model '{model_id}' from {target}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Display system compute diagnostics and storage paths."""
    import platform
    import psutil

    home_dir = get_oneasr_home()
    models_dir = get_models_dir()
    settings_path = get_settings_path()

    print(f"OneASR Home:    {home_dir}")
    print(f"Models Dir:     {models_dir}")
    print(f"Settings File:  {settings_path}")
    print("-" * 50)

    # Hardware detection
    accel = "CPU"
    try:
        import torch
        if torch.cuda.is_available():
            accel = f"NVIDIA CUDA ({torch.cuda.get_device_name(0)})"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            accel = f"Apple Silicon MPS ({platform.machine()})"
    except Exception:
        pass

    mem = psutil.virtual_memory()
    disk = shutil.disk_usage(home_dir)

    print(f"Accelerator:    {accel}")
    print(f"RAM Total:      {mem.total / (1024**3):.1f} GB (Used: {mem.percent}%)")
    print(f"Disk Free:      {disk.free / (1024**3):.1f} GB of {disk.total / (1024**3):.1f} GB")
    print(f"Python:         {platform.python_version()} ({platform.system()} {platform.machine()})")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the OneASR backend daemon in the foreground."""
    import socket
    import uvicorn

    host = args.host
    port = args.port

    # Pre-check if port is already listening to avoid unhandled socket bind Traceback
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        if s.connect_ex((probe_host, port)) == 0:
            print(f"[OneASR] Daemon is already active on http://{probe_host}:{port}")
            print(f"[OneASR] Interactive Swagger Docs: http://{probe_host}:{port}/docs")
            if getattr(args, "browser", False):
                import webbrowser
                webbrowser.open(f"http://{probe_host}:{port}")
            return 0

    print(f"Starting OneASR Engine daemon on {host}:{port} ...")
    if getattr(args, "browser", False):
        import threading
        import webbrowser

        def _open():
            time.sleep(1.2)
            url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"
            print(f"Opening web browser at {url} ...")
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    reload_flag = getattr(args, "reload", False)
    uvicorn.run("server.main:app", host=host, port=port, log_level="info", reload=reload_flag)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build unified oneasr command-line parser."""
    parser = argparse.ArgumentParser(
        prog="oneasr",
        description="OneASR - Unified Local Speech Recognition Model Engine",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="OneASR subcommands")

    # list / ls
    subparsers.add_parser("list", aliases=["ls"], help="List local and official models")

    # ps
    subparsers.add_parser("ps", help="List models currently loaded in memory/VRAM")

    # pull
    pull_p = subparsers.add_parser("pull", help="Pull a model from registry")
    pull_p.add_argument("model_id", help="Model identifier (e.g. 'sensevoice-small')")
    pull_p.add_argument(
        "--source",
        choices=["auto", "modelscope", "huggingface", "hf-mirror"],
        default="auto",
        help="Model download registry hub",
    )

    # rm
    rm_p = subparsers.add_parser("rm", aliases=["delete"], help="Remove local model files")
    rm_p.add_argument("model_id", help="Model identifier to delete")

    # info
    subparsers.add_parser("info", help="Display hardware accelerator and path diagnostics")

    # serve
    serve_p = subparsers.add_parser("serve", help="Start the OneASR backend daemon")
    serve_p.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    serve_p.add_argument("--port", type=int, default=8020, help="Port to listen on")
    serve_p.add_argument("--browser", "--open-browser", action="store_true", help="Automatically open web browser on startup")
    serve_p.add_argument("--reload", action="store_true", help="Enable auto-reload on code change (development)")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand in ("list", "ls"):
        return cmd_list(args)
    if args.subcommand == "ps":
        return cmd_ps(args)
    if args.subcommand == "pull":
        return cmd_pull(args)
    if args.subcommand in ("rm", "delete"):
        return cmd_rm(args)
    if args.subcommand == "info":
        return cmd_info(args)
    if args.subcommand == "serve":
        return cmd_serve(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
