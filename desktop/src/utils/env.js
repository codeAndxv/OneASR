// OneASR Environment Detection Utility
// Checks whether the app is running in Tauri Native Desktop or standard Web Browser

export const isTauri = typeof window !== 'undefined' && Boolean(window.__TAURI_INTERNALS__);

export function isWeb() {
  return !isTauri;
}
