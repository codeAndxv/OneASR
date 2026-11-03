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
import concurrent.futures
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


def find_signing_identity() -> str | None:
    """Detect available Apple Developer ID Application signing identity on macOS."""
    env_id = os.environ.get("APPLE_SIGNING_IDENTITY")
    if env_id and env_id.strip():
        return env_id.strip()

    try:
        out = subprocess.check_output(
            ["security", "find-identity", "-p", "codesigning", "-v"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if "Developer ID Application:" in line:
                start = line.find('"Developer ID Application:')
                end = line.rfind('"')
                if start != -1 and end != -1:
                    return line[start + 1 : end]
    except Exception:
        pass
    return None


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


def sign_app_bundle_deep(app_bundle: Path, identity: str, entitlements: Path | None):
    """
    Recursively and concurrently signs all nested Mach-O binaries (.dylib, .so, executables)
    with Developer ID, Hardened Runtime (--options runtime), and secure timestamps.
    Then signs the main bundle from the inside out to satisfy Apple Notary requirements.
    """
    log("3/4", f"Analyzing Mach-O binaries in {app_bundle.name} for Apple Notarization...")
    MACH_O_MAGICS = {
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
        b"\xca\xfe\xba\xbe",
        b"\xbe\xba\xfe\xca",
    }

    def is_macho(p: Path) -> bool:
        if not p.is_file() or p.is_symlink():
            return False
        try:
            with open(p, "rb") as f:
                return f.read(4) in MACH_O_MAGICS
        except Exception:
            return False

    binaries: list[Path] = []
    # Only scan Contents/Resources and Contents/Frameworks for nested Mach-O binaries.
    # Contents/MacOS/<CFBundleExecutable> is automatically signed when signing the outer bundle.
    for sub in ("Resources", "Frameworks"):
        subdir = app_bundle / "Contents" / sub
        if not subdir.exists():
            continue
        for root, _, files in os.walk(subdir):
            for f in files:
                p = Path(root) / f
                if is_macho(p):
                    binaries.append(p)

    # Sort from deepest to shallowest path (crucial for nested dependency signing)
    binaries.sort(key=lambda p: len(p.parts), reverse=True)

    log_sub(f"Found {len(binaries)} nested Mach-O binaries. Parallel signing with Hardened Runtime & Timestamps...")

    failed_files: list[str] = []

    def _sign_single(p: Path):
        cmd = [
            "codesign",
            "--force",
            "--options", "runtime",
            "--timestamp",
            "-s", identity,
        ]
        if entitlements and entitlements.exists():
            cmd.extend(["--entitlements", str(entitlements)])
        cmd.append(str(p))

        # Retry up to 3 times to handle transient Apple timestamp server throttling
        for attempt in range(3):
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                return
            time.sleep(1.0 * (attempt + 1))

        failed_files.append(f"{p.name}: {res.stderr.strip()}")

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_sign_single, binaries))

    if failed_files:
        error_exit(f"Failed to sign {len(failed_files)} binaries:\n  " + "\n  ".join(failed_files[:5]))

    log_sub(f"Signed {len(binaries)} binaries in {time.time() - t0:.1f}s ✓")

    # Sign the top-level bundle
    log_sub(f"Signing outer application bundle {app_bundle.name}...")
    outer_cmd = [
        "codesign",
        "--force",
        "--options", "runtime",
        "--timestamp",
        "-s", identity,
    ]
    if entitlements and entitlements.exists():
        outer_cmd.extend(["--entitlements", str(entitlements)])
    outer_cmd.append(str(app_bundle))
    run_cmd(outer_cmd)

    log_sub(f"Validating bundle signature with codesign...")
    run_cmd(["codesign", "--verify", "--deep", "--strict", "--verbose=1", str(app_bundle)])
    log("3/4", f"OneASR.app successfully signed and verified with Developer ID ✓", GREEN)


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
    parser.add_argument(
        "--sign",
        action="store_true",
        help="Enable Apple Developer ID code signing (default: False for fast daily debugging)",
    )
    parser.add_argument(
        "--notarize",
        action="store_true",
        help="Submit DMG to Apple Cloud Notarization and staple ticket (requires --sign)",
    )
    parser.add_argument(
        "--notary-profile",
        default="OneASR",
        help="Keychain profile name stored via notarytool store-credentials (default: OneASR)",
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
        log("1/3", "Skipping backend dependency install; incrementally syncing application code...", YELLOW)
        copy_clean_tree(project_root / "server", resources_dir / "server")
        copy_clean_tree(project_root / "cli", resources_dir / "cli")
        for f in ["pyproject.toml"]:
            src_f = project_root / f
            if src_f.exists():
                shutil.copy2(src_f, resources_dir / f)
        log("1/3", "Application code incrementally synced ✓", GREEN)
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
            for f in ["pyproject.toml"]:
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
    log("3/4", "Packaging native desktop application (Tauri v2)...")
    signing_identity = None
    build_env = os.environ.copy()
    if target_os == "macos":
        if args.sign:
            signing_identity = find_signing_identity()
            if signing_identity:
                log_sub(f"Detected Developer ID: {signing_identity}")
                build_env["APPLE_SIGNING_IDENTITY"] = signing_identity
            else:
                log_sub("No Developer ID certificate found; using ad-hoc signing", YELLOW)
        else:
            log_sub("Fast dev mode: skipping Developer ID signing (pass --sign to enable)")

    if target_os == "macos":
        run_cmd(["npx", "tauri", "build", "--bundles", "app"], cwd=desktop_dir, env=build_env)
        app_bundle = tauri_dir / "target" / "release" / "bundle" / "macos" / "OneASR.app"
        if not app_bundle.exists():
            error_exit(f"Expected .app bundle at {app_bundle} but not found.")

        # Inside-out deep signing with Hardened Runtime and Entitlements
        entitlements_file = tauri_dir / "Entitlements.plist"
        if signing_identity:
            sign_app_bundle_deep(app_bundle, signing_identity, entitlements_file)

        # Step 4: Robust DMG Creation (immune to EBUSY / Resource busy)
        log("4/4", "Creating distribution DMG installer...")
        dmg_dir = tauri_dir / "target" / "release" / "bundle" / "dmg"
        dmg_dir.mkdir(parents=True, exist_ok=True)
        dmg_path = dmg_dir / "OneASR.dmg"
        if dmg_path.exists():
            dmg_path.unlink()

        staging_dir = tauri_dir / "target" / "release" / "bundle" / "dmg_staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        copy_clean_tree(app_bundle, staging_dir / "OneASR.app")
        os.symlink("/Applications", staging_dir / "Applications")

        run_cmd([
            "hdiutil",
            "create",
            "-volname",
            "OneASR",
            "-srcfolder",
            str(staging_dir),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ])
        shutil.rmtree(staging_dir, ignore_errors=True)

        if signing_identity:
            log("4/4", f"Signing DMG container with {signing_identity}...")
            run_cmd(["codesign", "--force", "-s", signing_identity, "--timestamp", str(dmg_path)])

        # Step 5: Apple Cloud Notarization & Stapling
        notary_profile = getattr(args, "notary_profile", "OneASR")
        if args.notarize:
            if not signing_identity:
                error_exit("Apple Notarization requires Developer ID signing. Please pass --sign together with --notarize.")
            log("4/4", f"Submitting {dmg_path.name} to Apple for Notarization (profile: {notary_profile})...")
            submit_cmd = [
                "xcrun",
                "notarytool",
                "submit",
                str(dmg_path),
                "--keychain-profile",
                notary_profile,
                "--wait",
            ]
            log_sub(f"Running: {' '.join(submit_cmd)}")
            proc = subprocess.Popen(
                submit_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            submission_id = None
            is_accepted = False
            if proc.stdout:
                for line in proc.stdout:
                    sys.stdout.write(f"  {line}")
                    sys.stdout.flush()
                    if "id:" in line and not submission_id:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            submission_id = parts[1]
                    if "status: Accepted" in line:
                        is_accepted = True

            proc.wait()

            if not is_accepted:
                error_exit(
                    f"Apple Notarization rejected! Submission ID: {submission_id or 'unknown'}.\n"
                    f"To view detailed validation errors from Apple, run:\n"
                    f"  xcrun notarytool log {submission_id} --keychain-profile {notary_profile}"
                )

            log("4/4", "Apple Notarization Accepted! Stapling ticket to DMG...", GREEN)
            run_cmd(["xcrun", "stapler", "staple", str(dmg_path)])
            log("4/4", "Validating Gatekeeper acceptance...", GREEN)
            run_cmd(["spctl", "-a", "-t", "open", "--context", "context:primary-signature", "-v", str(dmg_path)])
            log("4/4", "OneASR.dmg is 100% Notarized and Stapled! Ready for any Mac ✓", GREEN)
        else:
            log("4/4", "Fast dev mode: skipping Apple Notarization (pass --notarize to submit) ✓", GREEN)
    else:
        run_cmd(["npx", "tauri", "build"], cwd=desktop_dir, env=build_env)

    log("✓", "All desktop packaging and certification completed ✓", GREEN)

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
