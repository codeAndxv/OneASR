<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="isOpen" class="modal-backdrop" @click="handleBackdropClick">
        <div class="modal-card" @click.stop>
          <!-- Modal Header -->
          <div class="modal-header">
            <div class="modal-title-area">
              <h2 class="modal-title">{{ t('navSettings') }}</h2>
              <span class="modal-subtitle">偏好设置与系统运行环境</span>
            </div>
            <button class="modal-close-btn" :title="t('close') + ' (Esc)'" @click="$emit('close')">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <!-- Modal Body (Scrollable Settings Content) -->
          <div class="modal-body">
            <!-- Section 1: General (Theme & Language) -->
            <div class="settings-group">
              <h3 class="group-title">{{ t('sectionGeneral') }}</h3>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('generalTheme') }}</span>
                  <span class="row-desc">{{ t('generalThemeDesc') }}</span>
                </div>
                <div class="row-control">
                  <select v-model="selectedTheme" class="custom-select" @change="handleThemeChange">
                    <option value="auto">{{ t('themeAuto') }}</option>
                    <option value="dark">{{ t('themeDark') }}</option>
                    <option value="light">{{ t('themeLight') }}</option>
                  </select>
                </div>
              </div>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('generalLanguage') }}</span>
                  <span class="row-desc">{{ t('generalLanguageDesc') }}</span>
                </div>
                <div class="row-control">
                  <select :value="locale" class="custom-select" @change="e => setLocale(e.target.value)">
                    <option value="zh-CN">简体中文 (Simplified Chinese)</option>
                    <option value="en-US">English (US)</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Section 2: Storage & Paths -->
            <div class="settings-group">
              <h3 class="group-title">{{ t('sectionStorage') }}</h3>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('modelDirLabel') }}</span>
                  <span class="row-desc">~/.oneasr/models</span>
                </div>
                <div class="row-control">
                  <button class="secondary-btn" @click="openFolder">
                    {{ t('btnOpenDir') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Section 3: Network & Host -->
            <div class="settings-group">
              <h3 class="group-title">{{ t('sectionNetwork') }}</h3>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('lanAccessLabel') }}</span>
                  <span class="row-desc">{{ isLanExposed ? t('lanExposed') : t('lanLocalOnly') }}</span>
                </div>
                <div class="row-control">
                  <button class="toggle-btn" :class="{ active: isLanExposed }" @click="toggleLan">
                    <span class="toggle-slider"></span>
                  </button>
                </div>
              </div>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('portLabel') }}</span>
                  <span class="row-desc">HTTP & WebSocket Port</span>
                </div>
                <div class="row-control">
                  <span class="mono-badge">8020</span>
                </div>
              </div>
            </div>

            <!-- Section 4: Lifecycle Strategy -->
            <div class="settings-group">
              <h3 class="group-title">{{ t('sectionStrategy') }}</h3>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('keepAliveLabel') }}</span>
                  <span class="row-desc">无请求时自动释放模型占用的显存与内存</span>
                </div>
                <div class="row-control">
                  <select v-model="keepAliveTimeout" class="custom-select" @change="saveSettings">
                    <option value="60">{{ t('keepAlive1Min') }}</option>
                    <option value="300">{{ t('keepAlive5Min') }}</option>
                    <option value="900">{{ t('keepAlive15Min') }}</option>
                    <option value="1800">{{ t('keepAlive30Min') }}</option>
                    <option value="0">{{ t('keepAliveNever') }}</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Section 5: Hardware & Diagnostics -->
            <div class="settings-group">
              <h3 class="group-title">{{ t('sectionDiagnostics') }}</h3>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('hardwareChip') }}</span>
                  <span class="row-desc">Metal Performance Shaders (Apple Silicon)</span>
                </div>
                <div class="row-control">
                  <span class="status-pill active">Apple MPS 开启</span>
                </div>
              </div>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('swaggerDocs') }}</span>
                  <span class="row-desc">http://127.0.0.1:8020/docs</span>
                </div>
                <div class="row-control">
                  <button class="secondary-btn" @click="openDocs">
                    浏览 API
                  </button>
                </div>
              </div>

              <div class="setting-row">
                <div class="row-info">
                  <span class="row-label">{{ t('btnViewLogs') }}</span>
                  <span class="row-desc">~/.oneasr/logs/oneasr.log</span>
                </div>
                <div class="row-control">
                  <button class="secondary-btn" @click="openLogs">
                    {{ t('btnOpenDir') }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Modal Footer -->
          <div class="modal-footer">
            <span class="footer-hint">提示：按 <kbd>Esc</kbd> 快速关闭偏好设置</span>
            <button class="primary-btn" @click="$emit('close')">
              {{ t('btnConfirm') || '完成' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { useI18n } from '../i18n';
import { apiClient } from '../api/client';
import { currentTheme, setTheme } from '../utils/theme';

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['close']);
const { locale, setLocale, t } = useI18n();

const selectedTheme = ref(currentTheme.value);
const isLanExposed = ref(false);
const keepAliveTimeout = ref('300');

function handleThemeChange() {
  setTheme(selectedTheme.value);
}

function handleBackdropClick(e) {
  if (e.target === e.currentTarget) {
    emit('close');
  }
}

function onKeydown(e) {
  if (props.isOpen && e.key === 'Escape') {
    emit('close');
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown);
  fetchSettings();
});

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown);
});

async function fetchSettings() {
  try {
    const data = await apiClient.get('/v1/x/system/info');
    if (data) {
      if (data.host === '0.0.0.0') isLanExposed.value = true;
      if (data.keep_alive !== undefined) keepAliveTimeout.value = String(data.keep_alive);
    }
  } catch (err) {
    // Engine not online yet, keep defaults
  }
}

async function saveSettings() {
  try {
    await apiClient.post('/v1/x/system/settings', {
      keep_alive: parseInt(keepAliveTimeout.value, 10),
      host: isLanExposed.value ? '0.0.0.0' : '127.0.0.1'
    });
  } catch (err) {
    console.error('Failed to save settings:', err);
  }
}

function toggleLan() {
  isLanExposed.value = !isLanExposed.value;
  saveSettings();
}

function openFolder() {
  invoke('open_local_dir', { target: 'models' }).catch((err) => {
    console.warn('Native open_local_dir (models) failed:', err);
  });
}

function openLogs() {
  invoke('open_local_dir', { target: 'logs' }).catch((err) => {
    console.warn('Native open_local_dir (logs) failed:', err);
  });
}

function openDocs() {
  window.open('http://127.0.0.1:8020/docs', '_blank');
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal-card {
  width: 100%;
  max-width: 560px;
  max-height: 82vh;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--border-subtle);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modal-pop 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-header {
  height: 52px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
  background-color: var(--bg-surface);
}

.modal-title-area {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.modal-subtitle {
  font-size: 11.5px;
  color: var(--text-muted);
}

.modal-close-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.modal-close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background-color: var(--bg-surface);
}

.settings-group {
  background-color: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px 16px;
}

.group-title {
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin: 0 0 10px 0;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-subtle);
}

.setting-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.setting-row:first-of-type {
  padding-top: 0;
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.row-desc {
  font-size: 11.5px;
  color: var(--text-secondary);
}

.row-control {
  flex-shrink: 0;
}

.custom-select {
  padding: 5px 10px;
  font-size: 12.5px;
  background-color: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  outline: none;
  cursor: pointer;
}

.custom-select:focus {
  border-color: var(--accent-emerald);
}

.secondary-btn {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.secondary-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--text-secondary);
}

.primary-btn {
  padding: 6px 18px;
  font-size: 12.5px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.primary-btn:hover {
  background: rgba(255, 255, 255, 0.18);
  border-color: var(--text-muted);
}

.toggle-btn {
  width: 40px;
  height: 22px;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid var(--border-subtle);
  position: relative;
  cursor: pointer;
  transition: background 0.2s ease;
}

.toggle-btn.active {
  background: var(--accent-emerald);
  border-color: var(--accent-emerald);
}

.toggle-slider {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ffffff;
  position: absolute;
  top: 2px;
  left: 2px;
  transition: transform 0.2s ease;
}

.toggle-btn.active .toggle-slider {
  transform: translateX(18px);
  background: #0b0f17;
}

.mono-badge {
  font-family: monospace;
  font-size: 12px;
  padding: 3px 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: var(--text-secondary);
}

.status-pill {
  font-size: 11.5px;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 12px;
  background: rgba(16, 185, 129, 0.12);
  color: var(--accent-emerald);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.modal-footer {
  height: 50px;
  padding: 0 20px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--bg-surface);
  flex-shrink: 0;
}

.footer-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.footer-hint kbd {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid var(--border-subtle);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: inherit;
  color: var(--text-secondary);
}

/* Transitions */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.16s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@keyframes modal-pop {
  from {
    transform: scale(0.97);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
