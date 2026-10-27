#!/usr/bin/env python3
"""
OneASR Desktop One-Click Build Script

Automates the entire desktop packaging pipeline:
1. Environment pre-check (Python/uv, Node/npm, Rust/cargo, FFmpeg)
2. Standalone backend bundle assembly (intelligent incremental reuse / clean rebuild)
3. Frontend compilation (Vite -> dist)
4. Native desktop packaging (Tauri v2 -> DMG / App / Setup Exe)
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def log(step: str, msg: str, color: str = CYAN):
    print(f"{color}{BOLD}[{step}]{RESET} {msg}", flush=True)


def log_sub(msg: str):
    print(f"  {DIM}→{RESET} {msg}", flush=True)


def error_exit(msg: str):
    print(f"\n{RED}{BOLD}[ERROR]{RESET} {msg}\n", file=sys.stderr, flush=True)
    sys.exit(1)


def check_tool(tool: str, tip: str) -> str:
    path = shutil.which(tool)
    if not path:
        error_exit(f"Required tool '{tool}' not found in PATH.\n{tip}")
    return path


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict | None = None):
    cmd_str = " ".join(str(c) for c in cmd)
    log_sub(f"Running: {cmd_str}")
    proc = subprocess.run(cmd, cwd=cwd, env=env)
    if proc.returncode != 0:
        error_exit(f"Command failed with exit code {proc.returncode}:\n  {cmd_str}")


def resolve_platform() -> str:
    s = platform.system().lower()
    if s.startswith("darwin"):
        return "macos"
    elif s.startswith("win"):
        return "windows"
    return "linux"


def copy_clean_tree(src: Path, dst: Path, ignore_patterns: tuple[str, ...] = ("__pycache__", "*.pyc", "*.pyo")):
    def _ignore(directory, contents):
        ignored = set()
        for item in contents:
            for pat in ignore_patterns:
                if pat.startswith("*") and item.endswith(pat[1:]):
                    ignored.add(item)
                elif pat == item:
                    ignored.add(item)
        return ignored

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=_ignore)


def main():
    parser = argparse.ArgumentParser(description="OneASR Desktop One-Click Build Script")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Perform a clean rebuild (re-download Python runtime and reinstall PyTorch/all wheels)",
    )
    parser.add_argument(
        "--skip-backend",
        action="store_true",
        help="Skip standalone Python bundle check/assembly (build UI and Tauri only)",
    )
    parser.add_argument(
        "--torch-backend",
        choices=["mps", "cu124", "cu121", "cpu"],
        default=None,
        help="PyTorch acceleration backend (default: mps on macOS, cu124 on Windows/Linux)",
    )
    args = parser.parse_args()

    start_time = time.time()
    target_os = resolve_platform()

    if args.torch_backend is None:
        torch_backend = "mps" if target_os == "macos" else "cu124"
    else:
        torch_backend = args.torch_backend

    # Path resolution
    script_dir = Path(__file__).resolve().parent
    desktop_dir = script_dir.parent
    project_root = desktop_dir.parent
    tauri_dir = desktop_dir / "src-tauri"
    resources_dir = tauri_dir / "resources"
    python_bundle_dir = resources_dir / "python"

    print(f"\n{BOLD}{CYAN}===================================================={RESET}")
    print(f"{BOLD}{CYAN}        OneASR Desktop One-Click Builder            {RESET}")
    print(f"{BOLD}{CYAN}===================================================={RESET}")
    print(f"Platform       : {BOLD}{target_os}{RESET}")
    print(f"Torch Backend  : {BOLD}{torch_backend}{RESET}")
    print(f"Project Root   : {DIM}{project_root}{RESET}")
    print(f"Desktop Dir    : {DIM}{desktop_dir}{RESET}")
    print(f"Output Mode    : {BOLD}{'Clean Rebuild' if args.clean else 'Incremental (Fast)'}{RESET}\n")

    # Ensure common binary directories are on PATH
    home_dir = Path.home()
    extra_paths = [
        str(home_dir / ".cargo" / "bin"),
        str(home_dir / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    current_path = os.environ.get("PATH", "")
    for p in extra_paths:
        if p not in current_path:
            current_path = f"{p}:{current_path}"
    os.environ["PATH"] = current_path

    # Step 0: Pre-flight checks
    log("0/3", "Checking environment dependencies...")
    check_tool("node", "Please install Node.js (v18+ recommended): https://nodejs.org/")
    check_tool("npm", "Please ensure npm is installed alongside Node.js.")
    check_tool("cargo", "Please install Rust & Cargo: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
    if not args.skip_backend:
        check_tool("uv", "Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
    log("0/3", "Environment dependencies verified ✓", GREEN)

    # Step 1: Standalone Backend Bundle
    if args.skip_backend:
        log("1/3", "Skipping backend assembly (--skip-backend specified)", YELLOW)
    else:
        needs_full_rebuild = args.clean or not python_bundle_dir.exists()

        if needs_full_rebuild:
            log("1/3", "Building standalone Python runtime & installing dependencies (First run / Clean)...")
            prepare_script = script_dir / "prepare_standalone.py"
            py_cmd = [
                sys.executable,
                str(prepare_script),
                "--target-os", target_os,
                "--torch-backend", torch_backend,
            ]
            run_cmd(py_cmd, cwd=project_root)
            log("1/3", "Standalone Python runtime assembly complete ✓", GREEN)
        else:
            log("1/3", "Found existing standalone runtime. Incrementally syncing application code...")
            # Sync server, cli, configs
            copy_clean_tree(project_root / "server", resources_dir / "server")
            copy_clean_tree(project_root / "cli", resources_dir / "cli")
            for f in ["pyproject.toml", "config.yaml"]:
                src_f = project_root / f
                if src_f.exists():
                    shutil.copy2(src_f, resources_dir / f)
            log("1/3", "Application code incrementally synced ✓", GREEN)

    # Step 2: Frontend Compilation
    log("2/3", "Compiling frontend assets (Vite)...")
    node_modules_dir = desktop_dir / "node_modules"
    if not node_modules_dir.exists():
        log_sub("Installing npm dependencies...")
        run_cmd(["npm", "install"], cwd=desktop_dir)

    run_cmd(["npm", "run", "build"], cwd=desktop_dir)
    dist_dir = desktop_dir / "dist"
    if not dist_dir.exists():
        error_exit(f"Frontend compilation failed: expected {dist_dir} to exist.")
    log("2/3", "Frontend compiled successfully ✓", GREEN)

    # Step 3: Native Tauri Packaging
    log("3/3", "Packaging native desktop application (Tauri v2)...")
    run_cmd(["npx", "tauri", "build"], cwd=desktop_dir)
    log("3/3", "Tauri packaging completed ✓", GREEN)

    # Locate generated bundle artifacts
    target_bundle_dir = tauri_dir / "target" / "release" / "bundle"
    found_artifacts: list[Path] = []
    if target_bundle_dir.exists():
        for ext in ("*.dmg", "*.app", "*.exe", "*.msi", "*.deb", "*.AppImage"):
            found_artifacts.extend(target_bundle_dir.glob(f"**/{ext}"))

    elapsed = time.time() - start_time
    print(f"\n{BOLD}{GREEN}===================================================={RESET}")
    print(f"{BOLD}{GREEN}   OneASR Desktop Build Succeeded! ({elapsed:.1f}s)       {RESET}")
    print(f"{BOLD}{GREEN}===================================================={RESET}")

    if found_artifacts:
        print(f"\n{BOLD}Generated Packages:{RESET}")
        for art in found_artifacts:
            # Skip inner .app directory if dmg exists
            size_mb = art.stat().st_size / (1024 * 1024) if art.is_file() else 0
            size_str = f" ({size_mb:.1f} MB)" if size_mb > 0 else ""
            print(f"  {GREEN}✔{RESET} {art}{DIM}{size_str}{RESET}")
    else:
        print(f"\n{YELLOW}Note: Check {target_bundle_dir} for output artifacts.{RESET}")
    print("")


if __name__ == "__main__":
    main()
