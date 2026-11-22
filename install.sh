#!/usr/bin/env bash
# ==============================================================================
# OneASR One-Line Installer (Ollama-style unified CLI installation)
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/codeAndxv/OneASR/main/install.sh | sh
# ==============================================================================

set -eo pipefail

# ANSI Colors
BOLD="\033[1m"
GREEN="\033[92m"
CYAN="\033[96m"
YELLOW="\033[93m"
RED="\033[91m"
DIM="\033[2m"
RESET="\033[0m"

log_info() {
    echo -e "${CYAN}${BOLD}[OneASR]${RESET} $1"
}

log_success() {
    echo -e "${GREEN}${BOLD}[OneASR] ✓${RESET} $1"
}

log_warn() {
    echo -e "${YELLOW}${BOLD}[OneASR] !${RESET} $1"
}

log_error() {
    echo -e "${RED}${BOLD}[OneASR] ✗${RESET} $1" >&2
}

# 1. Platform & Architecture Verification
OS="$(uname -s)"
ARCH="$(uname -m)"

REPO="codeAndxv/OneASR"
TAG="${ONEASR_VERSION:-latest}"

BASE_URL="https://github.com/${REPO}/releases/latest/download"
if [ "${TAG}" != "latest" ]; then
    BASE_URL="https://github.com/${REPO}/releases/download/${TAG}"
fi

TARBALL_NAME=""
PLATFORM_DESC=""

if [ "${OS}" = "Darwin" ]; then
    if [ "${ARCH}" != "arm64" ]; then
        log_error "OneASR macOS standalone prebuilts require Apple Silicon (M1/M2/M3/M4, arm64)."
        log_error "Your machine architecture is '${ARCH}'. For Intel Mac, please install via source with: 'uv pip install -e .'"
        exit 1
    fi
    TARBALL_NAME="oneasr-darwin-arm64.tar.gz"
    PLATFORM_DESC="macOS (Apple Silicon arm64)"

elif [ "${OS}" = "Linux" ]; then
    if [ "${ARCH}" = "x86_64" ] || [ "${ARCH}" = "amd64" ]; then
        # Detect NVIDIA GPU availability
        HAS_NVIDIA=0
        if command -v nvidia-smi >/dev/null 2>&1; then
            if nvidia-smi >/dev/null 2>&1; then
                HAS_NVIDIA=1
            fi
        fi

        if [ "${ONEASR_FORCE_CPU:-0}" = "1" ]; then
            TARBALL_NAME="oneasr-linux-x86_64-cpu.tar.gz"
            PLATFORM_DESC="Linux (x86_64, CPU-only build)"
        elif [ "${HAS_NVIDIA}" = "1" ]; then
            TARBALL_NAME="oneasr-linux-x86_64.tar.gz"
            PLATFORM_DESC="Linux (x86_64, NVIDIA GPU / CUDA acceleration enabled)"
        else
            # Default to CPU-optimized lightweight package if no GPU detected, fallback to full x86_64 package
            TARBALL_NAME="oneasr-linux-x86_64-cpu.tar.gz"
            PLATFORM_DESC="Linux (x86_64, CPU-optimized)"
        fi
    elif [ "${ARCH}" = "aarch64" ] || [ "${ARCH}" = "arm64" ]; then
        log_error "Linux ARM64 standalone prebuilts are in testing. For ARM64 Linux, please install via source:"
        log_error "  git clone https://github.com/${REPO}.git && cd OneASR && uv pip install -e ."
        exit 1
    else
        log_error "Unsupported Linux architecture: '${ARCH}'."
        exit 1
    fi
else
    log_error "Unsupported operating system: '${OS}'."
    log_error "OneASR currently supports macOS (arm64) and Linux (x86_64)."
    exit 1
fi

DOWNLOAD_URL="${BASE_URL}/${TARBALL_NAME}"
INSTALL_ROOT="${HOME}/.oneasr"
CORE_DIR="${INSTALL_ROOT}/core"
BIN_DIR="${CORE_DIR}/bin"

echo ""
echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "${BOLD}${CYAN}          OneASR Unified CLI Installer              ${RESET}"
echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "Platform     : ${BOLD}${PLATFORM_DESC}${RESET}"
echo -e "Target Dir   : ${DIM}${CORE_DIR}${RESET}"
echo -e "Package      : ${DIM}${TARBALL_NAME}${RESET}"
echo ""

# 2. Check for curl or wget
DOWNLOADER=""
if command -v curl >/dev/null 2>&1; then
    DOWNLOADER="curl"
elif command -v wget >/dev/null 2>&1; then
    DOWNLOADER="wget"
else
    log_error "Neither 'curl' nor 'wget' was found in PATH. Please install either to continue."
    exit 1
fi

# 3. Create Temporary Working Directory
TMP_DIR="$(mktemp -d)"
cleanup() {
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

TARBALL="${TMP_DIR}/${TARBALL_NAME}"

log_info "Downloading standalone core archive from GitHub Releases..."
DOWNLOAD_SUCCESS=0

download_asset() {
    local url="$1"
    local dest="$2"
    if [ "${DOWNLOADER}" = "curl" ]; then
        curl -fL --progress-bar "${url}" -o "${dest}"
    else
        wget -q --show-progress "${url}" -O "${dest}"
    fi
}

if download_asset "${DOWNLOAD_URL}" "${TARBALL}"; then
    DOWNLOAD_SUCCESS=1
else
    # If the -cpu package is not found on older releases, fallback to full oneasr-linux-x86_64.tar.gz
    if [[ "${TARBALL_NAME}" == *"-cpu.tar.gz" ]]; then
        FALLBACK_NAME="oneasr-linux-x86_64.tar.gz"
        FALLBACK_URL="${BASE_URL}/${FALLBACK_NAME}"
        log_warn "CPU-specific package not found, falling back to universal package: ${FALLBACK_NAME}"
        TARBALL="${TMP_DIR}/${FALLBACK_NAME}"
        if download_asset "${FALLBACK_URL}" "${TARBALL}"; then
            DOWNLOAD_SUCCESS=1
        fi
    fi
fi

if [ "${DOWNLOAD_SUCCESS}" -eq 0 ]; then
    log_error "Download failed. Please check your network connection or verify release asset existence."
    log_error "URL: ${DOWNLOAD_URL}"
    exit 1
fi

log_success "Download complete."

# 4. Extract into ~/.oneasr/core
log_info "Extracting standalone runtime into ${CORE_DIR}..."
mkdir -p "${INSTALL_ROOT}"

# Remove existing core if present to ensure clean upgrade
if [ -d "${CORE_DIR}" ]; then
    rm -rf "${CORE_DIR}"
fi
mkdir -p "${CORE_DIR}"

tar -xzf "${TARBALL}" -C "${CORE_DIR}"
log_success "Core runtime unpacked."

# 5. Ensure Executable Permissions
if [ -f "${BIN_DIR}/oneasr" ]; then
    chmod 0755 "${BIN_DIR}/oneasr"
else
    log_error "Extraction verification failed: '${BIN_DIR}/oneasr' not found."
    exit 1
fi

if [ -d "${CORE_DIR}/python/bin" ]; then
    chmod 0755 "${CORE_DIR}/python/bin/"* 2>/dev/null || true
fi

# 6. Global CLI Symlink Registration
TARGET_SYMLINK="/usr/local/bin/oneasr"
FALLBACK_SYMLINK="${HOME}/.local/bin/oneasr"
SYMLINK_SUCCESS=0

log_info "Registering 'oneasr' in system PATH..."

# Try /usr/local/bin first
if [ -w "/usr/local/bin" ]; then
    ln -sf "${BIN_DIR}/oneasr" "${TARGET_SYMLINK}"
    SYMLINK_SUCCESS=1
    INSTALLED_BIN="${TARGET_SYMLINK}"
elif command -v sudo >/dev/null 2>&1 && [ -t 0 ]; then
    log_info "Requesting sudo permission to link into /usr/local/bin..."
    if sudo ln -sf "${BIN_DIR}/oneasr" "${TARGET_SYMLINK}"; then
        SYMLINK_SUCCESS=1
        INSTALLED_BIN="${TARGET_SYMLINK}"
    fi
fi

# Fallback to ~/.local/bin if /usr/local/bin was unavailable or sudo rejected
if [ "${SYMLINK_SUCCESS}" -eq 0 ]; then
    mkdir -p "${HOME}/.local/bin"
    ln -sf "${BIN_DIR}/oneasr" "${FALLBACK_SYMLINK}"
    INSTALLED_BIN="${FALLBACK_SYMLINK}"
    
    # Check if ~/.local/bin is already in PATH
    case ":${PATH}:" in
        *":${HOME}/.local/bin:"*) ;;
        *)
            log_warn "'~/.local/bin' is not in your current PATH."
            echo -e "  Please add the following line to your shell profile (~/.bashrc, ~/.zshrc):"
            echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
            ;;
    esac
fi

log_success "Registered CLI executable at: ${INSTALLED_BIN}"

# 7. Linux systemd service unit setup (Optional user service)
SYSTEMD_SERVICE_HINT=""
if [ "${OS}" = "Linux" ]; then
    SYSTEMD_DIR="${HOME}/.config/systemd/user"
    mkdir -p "${SYSTEMD_DIR}"
    SERVICE_FILE="${SYSTEMD_DIR}/oneasr.service"

    cat <<EOF > "${SERVICE_FILE}"
[Unit]
Description=OneASR Speech Recognition Daemon
After=network.target

[Service]
Type=simple
ExecStart=${INSTALLED_BIN} serve
Restart=always
RestartSec=3
Environment="PATH=/usr/local/bin:/usr/bin:/bin:${HOME}/.local/bin"

[Install]
WantedBy=default.target
EOF

    SYSTEMD_SERVICE_HINT="  • Run in background via systemd (Auto-start on boot):\n     ${BOLD}${CYAN}systemctl --user enable --now oneasr${RESET}\n     ${BOLD}${CYAN}systemctl --user status oneasr${RESET}\n"
    log_success "Generated systemd user service: ${SERVICE_FILE}"
fi

# 8. Verification & Next Steps Banner
echo ""
echo -e "${BOLD}${GREEN}====================================================${RESET}"
echo -e "${BOLD}${GREEN}        OneASR CLI Installed Successfully!          ${RESET}"
echo -e "${BOLD}${GREEN}====================================================${RESET}"
echo ""
echo -e "Quickstart Guide:"
echo -e "  1. Start the service daemon:"
echo -e "     ${BOLD}${CYAN}oneasr serve${RESET}"
if [ -n "${SYSTEMD_SERVICE_HINT}" ]; then
    echo -e "${SYSTEMD_SERVICE_HINT}"
fi
echo -e "  2. List or pull recognition models:"
echo -e "     ${BOLD}${CYAN}oneasr list${RESET}"
echo -e "     ${BOLD}${CYAN}oneasr pull sensevoice-small${RESET}"
echo ""
echo -e "  3. Transcribe via standard API or Web UI (http://127.0.0.1:8020):"
echo -e "     ${BOLD}${CYAN}curl http://127.0.0.1:8020/v1/audio/transcriptions -F file=@audio.mp3 -F model=sensevoice-small${RESET}"
echo ""
