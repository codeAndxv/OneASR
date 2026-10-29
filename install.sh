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

if [ "${OS}" != "Darwin" ]; then
    log_error "The standalone CLI currently supports macOS (Apple Silicon)."
    log_error "Linux and Windows prebuilts are coming soon. On Linux, please use: 'uv pip install -e .'"
    exit 1
fi

if [ "${ARCH}" != "arm64" ]; then
    log_error "OneASR macOS standalone prebuilts require Apple Silicon (M1/M2/M3/M4, arm64)."
    log_error "Your machine architecture is '${ARCH}'. For Intel Mac, please install via source with uv/python."
    exit 1
fi

REPO="codeAndxv/OneASR"
TAG="${ONEASR_VERSION:-latest}"

if [ "${TAG}" = "latest" ]; then
    DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/oneasr-darwin-arm64.tar.gz"
else
    DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${TAG}/oneasr-darwin-arm64.tar.gz"
fi

INSTALL_ROOT="${HOME}/.oneasr"
CORE_DIR="${INSTALL_ROOT}/core"
BIN_DIR="${CORE_DIR}/bin"

echo ""
echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "${BOLD}${CYAN}          OneASR Unified CLI Installer              ${RESET}"
echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "Platform     : ${BOLD}macOS (Apple Silicon arm64)${RESET}"
echo -e "Target Dir   : ${DIM}${CORE_DIR}${RESET}"
echo -e "Source       : ${DIM}${DOWNLOAD_URL}${RESET}"
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

TARBALL="${TMP_DIR}/oneasr-darwin-arm64.tar.gz"

log_info "Downloading standalone core archive..."
if [ "${DOWNLOADER}" = "curl" ]; then
    if ! curl -fL --progress-bar "${DOWNLOAD_URL}" -o "${TARBALL}"; then
        log_error "Download failed. Please check your network connection or verify the release asset exists."
        log_error "URL: ${DOWNLOAD_URL}"
        exit 1
    fi
else
    if ! wget -q --show-progress "${DOWNLOAD_URL}" -O "${TARBALL}"; then
        log_error "Download failed. Please check your network connection or verify the release asset exists."
        log_error "URL: ${DOWNLOAD_URL}"
        exit 1
    fi
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
    chmod +x "${BIN_DIR}/oneasr"
else
    log_error "Extraction verification failed: '${BIN_DIR}/oneasr' not found."
    exit 1
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
            echo -e "  Please add the following line to your ${BOLD}~/.zshrc${RESET} or ${BOLD}~/.bashrc${RESET}:"
            echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
            ;;
    esac
fi

log_success "Registered CLI tool at: ${INSTALLED_BIN}"

# 7. Verification & Next Steps
echo ""
echo -e "${BOLD}${GREEN}====================================================${RESET}"
echo -e "${BOLD}${GREEN}        OneASR CLI Installed Successfully!          ${RESET}"
echo -e "${BOLD}${GREEN}====================================================${RESET}"
echo ""
echo -e "Quickstart Guide:"
echo -e "  1. Start the backend service daemon:"
echo -e "     ${BOLD}${CYAN}oneasr serve${RESET}"
echo ""
echo -e "  2. List or pull recognition models:"
echo -e "     ${BOLD}${CYAN}oneasr list${RESET}"
echo -e "     ${BOLD}${CYAN}oneasr pull sensevoice-small${RESET}"
echo ""
echo -e "  3. Transcribe via standard API or Web UI (http://127.0.0.1:8020):"
echo -e "     ${BOLD}${CYAN}curl http://127.0.0.1:8020/v1/audio/transcriptions -F file=@audio.mp3 -F model=sensevoice-small${RESET}"
echo ""
