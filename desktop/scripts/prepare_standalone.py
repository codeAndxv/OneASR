#!/usr/bin/env python3
"""
OneASR Standalone Bundle Preparation Script

Assembles a fully self-contained runtime environment containing:
1. Isolated CPython 3.12 runtime (from python-build-standalone via uv).
2. Production Python dependencies (PyTorch with MPS/CUDA, FunASR, ONNX, FastAPI, etc.).
3. Static ffmpeg binary.
4. OneASR server and CLI source code.
5. Unified 'oneasr' command launcher script.

Target outputs can be packaged by Tauri (desktop/src-tauri/resources) or tarred for Linux CLI.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
import tarfile
from pathlib import Path


def log(msg: str):
    print(f"[OneASR Standalone] {msg}", flush=True)


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict | None = None):
    cmd_str = " ".join(str(c) for c in cmd)
    log(f"Running: {cmd_str}")
    proc = subprocess.run(cmd, cwd=cwd, env=env, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {proc.returncode}: {cmd_str}")


def resolve_platform():
    system = platform.system().lower()
    if system.startswith("darwin"):
        return "macos"
    elif system.startswith("win"):
        return "windows"
    else:
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


def locate_standalone_cpython(python_version: str = "3.12") -> Path:
    """
    Find or install standalone CPython distribution using uv.
    Returns the root directory of the standalone CPython installation.
    """
    uv_bin = shutil.which("uv")
    if not uv_bin:
        raise RuntimeError(
            "The 'uv' tool is required to manage standalone Python. "
            "Please install uv (https://github.com/astral-sh/uv) or install it via pip."
        )

    log(f"Locating standalone CPython {python_version} via uv...")
    # Ensure python is available
    run_cmd([uv_bin, "python", "install", python_version])

    # Find the python binary path
    out = subprocess.check_output([uv_bin, "python", "find", python_version], text=True).strip()
    py_path = Path(out).resolve()
    if not py_path.exists():
        raise FileNotFoundError(f"Could not resolve standalone Python path: {out}")

    # Root of python installation
    # On Unix: <root>/bin/python3.12 -> root is parent of bin
    # On Windows: <root>/python.exe -> root is parent of python.exe
    if py_path.parent.name.lower() in ("bin", "scripts"):
        root_dir = py_path.parent.parent
    else:
        root_dir = py_path.parent

    log(f"Standalone CPython installation root resolved at: {root_dir}")
    return root_dir


def assemble_standalone_python(src_root: Path, target_dir: Path, target_os: str) -> Path:
    """
    Copies standalone CPython tree to target_dir and returns python executable path.
    """
    log(f"Copying standalone Python tree to {target_dir}...")
    copy_clean_tree(src_root, target_dir)

    if target_os == "windows":
        py_candidates = [
            target_dir / "python.exe",
            target_dir / "Scripts" / "python.exe",
        ]
    else:
        py_candidates = [
            target_dir / "bin" / "python3",
            target_dir / "bin" / "python3.12",
            target_dir / "bin" / "python",
        ]

    for cand in py_candidates:
        if cand.exists():
            log(f"Standalone Python executable verified at: {cand}")
            return cand

    raise FileNotFoundError(f"Could not locate Python executable within {target_dir}")


def install_python_dependencies(
    py_bin: Path,
    requirements_file: Path,
    torch_backend: str,
    target_os: str,
):
    """
    Installs project dependencies into the standalone Python environment using uv pip.
    """
    uv_bin = shutil.which("uv")
    if not uv_bin:
        raise RuntimeError("'uv' executable not found in PATH.")

    log(f"Installing dependencies with torch backend '{torch_backend}' into standalone Python...")

    # PyTorch backend customization
    if torch_backend.startswith("cu") and target_os in ("windows", "linux"):
        # e.g. cu124 -> https://download.pytorch.org/whl/cu124
        whl_index = f"https://download.pytorch.org/whl/{torch_backend}"
        log(f"Installing CUDA PyTorch from {whl_index}...")
        run_cmd([
            uv_bin, "pip", "install",
            "--python", str(py_bin),
            "torch", "torchaudio",
            "--index-url", whl_index,
        ])
    elif torch_backend == "cpu" and target_os == "linux":
        whl_index = "https://download.pytorch.org/whl/cpu"
        log(f"Installing CPU-only PyTorch from {whl_index}...")
        run_cmd([
            uv_bin, "pip", "install",
            "--python", str(py_bin),
            "torch", "torchaudio",
            "--index-url", whl_index,
        ])

    # Install remaining requirements
    run_cmd([
        uv_bin, "pip", "install",
        "--python", str(py_bin),
        "-r", str(requirements_file),
    ])


def bundle_ffmpeg(target_bin_dir: Path, target_os: str):
    """
    Copies or provisions a static ffmpeg executable into target_bin_dir.
    """
    target_bin_dir.mkdir(parents=True, exist_ok=True)
    exe_name = "ffmpeg.exe" if target_os == "windows" else "ffmpeg"
    dest_path = target_bin_dir / exe_name

    # Check if host system has ffmpeg
    host_ffmpeg = shutil.which("ffmpeg")
    if host_ffmpeg:
        log(f"Found host ffmpeg at {host_ffmpeg}, copying to {dest_path}...")
        shutil.copy2(host_ffmpeg, dest_path)
        dest_path.chmod(0o755)
        return

    # If on Windows and host ffmpeg not found, download BtbN/yt-dlp static build
    if target_os == "windows":
        url = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        log(f"Host ffmpeg not found. Downloading static Windows ffmpeg from {url}...")
        zip_temp = target_bin_dir / "ffmpeg_win.zip"
        urllib.request.urlretrieve(url, zip_temp)
        with zipfile.ZipFile(zip_temp, "r") as z:
            for file_info in z.infolist():
                if file_info.filename.endswith("bin/ffmpeg.exe"):
                    with z.open(file_info) as src_f, open(dest_path, "wb") as dst_f:
                        shutil.copyfileobj(src_f, dst_f)
                    break
        if zip_temp.exists():
            zip_temp.unlink()
        log(f"Static ffmpeg extracted to {dest_path}")
    else:
        log("Warning: host ffmpeg binary not found; please ensure ffmpeg is available on PATH.")


def create_cli_launcher(target_root: Path, target_os: str):
    """
    Creates a wrapper launcher script for running 'oneasr' directly from the bundle.
    """
    bin_dir = target_root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    if target_os == "windows":
        script_path = bin_dir / "oneasr.cmd"
        content = (
            "@echo off\r\n"
            "set \"ONEASR_DIR=%~dp0..\"\r\n"
            "set \"PYTHONPATH=%ONEASR_DIR%;%PYTHONPATH%\"\r\n"
            "set \"PATH=%ONEASR_DIR%\\bin;%ONEASR_DIR%\\python;%PATH%\"\r\n"
            "\"%ONEASR_DIR%\\python\\python.exe\" -m cli.main %*\r\n"
        )
        script_path.write_text(content, encoding="utf-8")
        log(f"Created Windows CLI launcher at {script_path}")
    else:
        script_path = bin_dir / "oneasr"
        content = (
            "#!/usr/bin/env bash\n"
            "set -e\n"
            "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)\"\n"
            "export PYTHONPATH=\"$SCRIPT_DIR:$PYTHONPATH\"\n"
            "export PATH=\"$SCRIPT_DIR/bin:$SCRIPT_DIR/python/bin:$PATH\"\n"
            "exec \"$SCRIPT_DIR/python/bin/python3\" -m cli.main \"$@\"\n"
        )
        script_path.write_text(content, encoding="utf-8")
        script_path.chmod(0o755)
        log(f"Created Unix CLI launcher at {script_path}")


def prune_unneeded_files(target_dir: Path):
    """
    Prunes redundant test files, compiled cache, and documentation to trim bundle size.
    """
    log("Pruning unneeded test caches and bytecode...")
    for root, dirs, files in os.walk(target_dir, topdown=False):
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                try:
                    os.unlink(os.path.join(root, name))
                except OSError:
                    pass
        for name in dirs:
            if name == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, name))
                except OSError:
                    pass


def main():
    parser = argparse.ArgumentParser(description="Prepare standalone OneASR runtime bundle.")
    parser.add_argument("--target-os", choices=["macos", "windows", "linux"], default=resolve_platform())
    parser.add_argument("--output-dir", type=Path, default=None, help="Bundle output destination")
    parser.add_argument(
        "--torch-backend",
        choices=["mps", "cu124", "cu121", "cpu"],
        default=None,
        help="PyTorch acceleration backend (default: mps on macOS, cu124 on Windows/Linux)",
    )
    parser.add_argument("--skip-pip", action="store_true", help="Skip running uv pip install")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent
    desktop_tauri = project_root / "desktop" / "src-tauri"

    target_os = args.target_os
    if args.torch_backend is None:
        torch_backend = "mps" if target_os == "macos" else "cu124"
    else:
        torch_backend = args.torch_backend

    if args.output_dir:
        output_dir = args.output_dir.resolve()
    else:
        output_dir = (desktop_tauri / "resources").resolve()

    log(f"Starting standalone bundle preparation...")
    log(f"Project root: {project_root}")
    log(f"Target OS: {target_os}")
    log(f"Torch backend: {torch_backend}")
    log(f"Output directory: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Standalone Python
    py_target_dir = output_dir / "python"
    src_py_root = locate_standalone_cpython("3.12")
    py_bin = assemble_standalone_python(src_py_root, py_target_dir, target_os)

    # 2. Python Packages
    if not args.skip_pip:
        req_file = project_root / "requirements.txt"
        install_python_dependencies(py_bin, req_file, torch_backend, target_os)

    # 3. Static ffmpeg
    bundle_ffmpeg(output_dir / "bin", target_os)

    # 4. Copy OneASR code
    log("Copying OneASR application code...")
    copy_clean_tree(project_root / "server", output_dir / "server")
    copy_clean_tree(project_root / "cli", output_dir / "cli")

    for f in ["pyproject.toml", "config.yaml"]:
        src_f = project_root / f
        if src_f.exists():
            shutil.copy2(src_f, output_dir / f)

    # 5. CLI Launcher
    create_cli_launcher(output_dir, target_os)

    # 6. Cleanup
    prune_unneeded_files(output_dir)

    log("Standalone bundle preparation successfully completed!")


if __name__ == "__main__":
    main()
