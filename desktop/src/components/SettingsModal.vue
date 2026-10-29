<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="isOpen" class="modal-backdrop" @click="handleBackdropClick">
        <div class="modal-card" @click.stop>
          <!-- Modal Header -->
          <div class="modal-header">
            <div class="modal-title-area">
              <h2 class="modal-title">{{ t('navSettings') }}</h2>
              <span class="modal-subtitle">{{ t('settingsSubtitle') }}</span>
            </div>
            <button class="modal-close-btn" :title="t('close') + ' (Esc)'" @click="$emit('close')">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <!-- Segmented Tab Nav -->
          <div class="modal-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              class="tab-btn"
              :class="{ active: activeTab === tab.id }"
              @click="activeTab = tab.id"
            >
              <span class="tab-icon" v-html="tab.icon"></span>
              <span class="tab-label">{{ t(tab.labelKey) }}</span>
            </button>
          </div>

          <!-- Modal Body (Active Tab Content) -->
          <div class="modal-body">
            <!-- Tab 1: General -->
            <div v-if="activeTab === 'general'" class="tab-pane">
              <div class="settings-group">
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

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('downloadNetworkSettingsLabel') }}</span>
                    <span class="row-desc">{{ t('downloadNetworkSettingsDesc') }}</span>
                  </div>
                  <div class="row-control">
                    <select v-model="downloadSource" class="custom-select" @change="saveSettings">
                      <option value="auto">{{ t('downloadNetworkOptionAuto') }}</option>
                      <option value="modelscope">{{ t('downloadNetworkOptionCn') }}</option>
                      <option value="hf-mirror">{{ t('downloadNetworkOptionHfMirror') }}</option>
                      <option value="huggingface">{{ t('downloadNetworkOptionGlobal') }}</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <!-- Tab 2: Storage -->
            <div v-else-if="activeTab === 'storage'" class="tab-pane">
              <div class="settings-group">
                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('storageUserModels') }}</span>
                    <span class="row-desc mono-path">{{ modelsDirPath || '~/.oneasr/models' }}</span>
                  </div>
                  <div class="row-control">
                    <button class="secondary-btn" @click="openFolder">
                      {{ t('btnOpenDir') }}
                    </button>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('storageLogs') }}</span>
                    <span class="row-desc mono-path">~/.oneasr/logs</span>
                  </div>
                  <div class="row-control">
                    <button class="secondary-btn" @click="openLogs">
                      {{ t('btnOpenDir') }}
                    </button>
                  </div>
                </div>

                <div v-if="diskFreeGb !== null" class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('storageDiskSpace') }}</span>
                    <span class="row-desc">主存储卷总计 {{ diskTotalGb }} GB</span>
                  </div>
                  <div class="row-control">
                    <span class="disk-free-pill">{{ diskFreeGb }} GB 可用</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Tab 3: Service -->
            <div v-else-if="activeTab === 'service'" class="tab-pane">
              <div class="settings-group">
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
                    <span class="row-desc">HTTP & WebSocket 统一监听端口</span>
                  </div>
                  <div class="row-control">
                    <span class="mono-badge">8020</span>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('apiKeyLabel') }}</span>
                    <span class="row-desc">{{ t('apiKeyDesc') }}</span>
                  </div>
                  <div class="row-control api-key-control-wrap">
                    <div class="api-key-input-group">
                      <div class="api-key-input-wrapper">
                        <input
                          v-model="apiKeyInput"
                          :type="showApiKey ? 'text' : 'password'"
                          class="api-key-input"
                          :placeholder="t('apiKeyPlaceholder')"
                          @change="handleApiKeyChange"
                        />
                        <button
                          type="button"
                          class="eye-toggle-btn"
                          :title="showApiKey ? t('btnHideKey') : t('btnShowKey')"
                          @click="showApiKey = !showApiKey"
                        >
                          <svg v-if="showApiKey" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                            <line x1="1" y1="1" x2="23" y2="23"/>
                          </svg>
                          <svg v-else viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                          </svg>
                        </button>
                      </div>
                      <button
                        class="secondary-btn"
                        :disabled="!apiKeyInput"
                        @click="copyApiKey"
                      >
                        {{ apiKeyCopied ? t('btnCopied') : t('btnCopy') }}
                      </button>
                      <button
                        class="secondary-btn"
                        @click="regenerateApiKey"
                      >
                        {{ t('btnRegenerateKey') }}
                      </button>
                    </div>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('keepAliveLabel') }}</span>
                    <span class="row-desc">{{ locale === 'zh-CN' ? '无请求时自动释放模型占用的显存与内存' : 'Auto-release idle model GPU/CPU memory' }}</span>
                  </div>
                  <div class="row-control">
                    <select v-model="keepAliveTimeout" class="custom-select" @change="saveSettings">
                      <option value="0">{{ t('keepAliveImmediate') }}</option>
                      <option value="60">{{ t('keepAlive1Min') }}</option>
                      <option value="300">{{ t('keepAlive5Min') }}</option>
                      <option value="900">{{ t('keepAlive15Min') }}</option>
                      <option value="1800">{{ t('keepAlive30Min') }}</option>
                      <option value="-1">{{ t('keepAliveNever') }}</option>
                    </select>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('maxLoadedModelsLabel') }}</span>
                    <span class="row-desc">{{ t('maxLoadedModelsDesc') }}</span>
                  </div>
                  <div class="row-control">
                    <select v-model.number="maxLoadedModels" class="custom-select" @change="saveSettings">
                      <option :value="1">1</option>
                      <option :value="2">2 {{ locale === 'zh-CN' ? '(推荐)' : '(Default)' }}</option>
                      <option :value="3">3</option>
                      <option :value="4">4</option>
                      <option :value="5">5</option>
                    </select>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('swaggerDocs') }}</span>
                    <span class="row-desc">{{ t('apiDocsDesc') }}</span>
                  </div>
                  <div class="row-control">
                    <button class="secondary-btn" @click="openDocs">
                      {{ t('apiDocsBtn') }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- Advanced Toolkit & VAD (Collapsible) -->
              <div class="settings-group advanced-group">
                <details class="advanced-details">
                  <summary class="advanced-summary">
                    <div class="summary-left">
                      <span class="group-title">{{ t('sectionAdvancedToolkit') }}</span>
                      <span class="summary-desc">{{ t('sectionAdvancedToolkitDesc') }}</span>
                    </div>
                    <span class="summary-chevron">▾</span>
                  </summary>
                  
                  <div class="advanced-content">
                    <div class="setting-row">
                      <div class="row-info">
                        <span class="row-label">{{ t('vadThresholdLabel') }}</span>
                        <span class="row-desc">{{ t('vadThresholdDesc') }}</span>
                      </div>
                      <div class="row-control slider-control">
                        <input
                          v-model.number="vadThreshold"
                          type="range"
                          min="0.10"
                          max="0.90"
                          step="0.05"
                          class="range-slider"
                          @change="saveSettings"
                        />
                        <span class="mono-badge slider-badge">{{ vadThreshold.toFixed(2) }}</span>
                      </div>
                    </div>

                    <div class="setting-row">
                      <div class="row-info">
                        <span class="row-label">{{ t('targetChunkLabel') }}</span>
                        <span class="row-desc">{{ t('targetChunkDesc') }}</span>
                      </div>
                      <div class="row-control slider-control">
                        <input
                          v-model.number="targetChunkDuration"
                          type="range"
                          min="3.0"
                          max="15.0"
                          step="0.5"
                          class="range-slider"
                          @change="saveSettings"
                        />
                        <span class="mono-badge slider-badge">{{ targetChunkDuration.toFixed(1) }}s</span>
                      </div>
                    </div>

                    <div class="advanced-actions">
                      <button class="secondary-btn" @click="resetAdvancedDefaults">
                        {{ t('btnResetDefaults') }}
                      </button>
                    </div>
                  </div>
                </details>
              </div>
            </div>

            <!-- Tab 4: About -->
            <div v-else-if="activeTab === 'about'" class="tab-pane">
              <div class="about-hero">
                <div class="about-logo-wrapper">
                  <img :src="appLogo" alt="OneASR" class="about-app-icon" />
                </div>
                <div class="about-identity">
                  <div class="identity-top">
                    <span class="about-name">OneASR</span>
                    <span class="about-version-tag">v1.0.0</span>
                  </div>
                  <span class="about-tagline">{{ t('aboutTagline') }}</span>
                </div>
              </div>

              <div class="settings-group">
                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('aboutArch') }}</span>
                    <span class="row-desc">{{ t('aboutArchDesc') }}</span>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('aboutAcceleration') }}</span>
                    <span class="row-desc">{{ deviceDesc || 'Apple Silicon Metal (MPS)' }}</span>
                  </div>
                  <div class="row-control">
                    <span class="status-pill active">{{ hardwareAccel === 'mps' ? 'Apple MPS 开启' : (hardwareAccel === 'cuda' ? 'NVIDIA CUDA 开启' : 'CPU AVX2') }}</span>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="row-info">
                    <span class="row-label">{{ t('aboutGithub') }}</span>
                    <span class="row-desc">https://github.com/codeAndxv/OneASR</span>
                  </div>
                  <div class="row-control">
                    <button class="secondary-btn" @click="openGithub">
                      访问 GitHub
                    </button>
                  </div>
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
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { useI18n } from '../i18n';
import { apiClient } from '../api/client';
import { currentTheme, setTheme } from '../utils/theme';
import appLogo from '../assets/logo.svg';

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['close']);
const { locale, setLocale, t } = useI18n();

const activeTab = ref('general');

const tabs = [
  {
    id: 'general',
    labelKey: 'tabGeneral',
    icon: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
  },
  {
    id: 'storage',
    labelKey: 'tabStorage',
    icon: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
  },
  {
    id: 'service',
    labelKey: 'tabService',
    icon: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>'
  },
  {
    id: 'about',
    labelKey: 'tabAbout',
    icon: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  }
];

const selectedTheme = ref(currentTheme.value);
const isLanExposed = ref(false);
const keepAliveTimeout = ref('300');
const downloadSource = ref('auto');
const modelsDirPath = ref('');
const hardwareAccel = ref('mps');
const deviceDesc = ref('');
const diskFreeGb = ref(null);
const diskTotalGb = ref(null);

const apiKeyInput = ref(localStorage.getItem('oneasr_api_key') || '');
const apiKeyCopied = ref(false);
const showApiKey = ref(false);
const maxLoadedModels = ref(2);
const vadThreshold = ref(0.50);
const targetChunkDuration = ref(6.0);

function generateRandomKey() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = 'sk-oneasr-v1-';
  const array = new Uint8Array(24);
  if (typeof window !== 'undefined' && window.crypto && window.crypto.getRandomValues) {
    window.crypto.getRandomValues(array);
    for (let i = 0; i < array.length; i++) {
      result += chars[array[i] % chars.length];
    }
  } else {
    for (let i = 0; i < 24; i++) {
      result += chars[Math.floor(Math.random() * chars.length)];
    }
  }
  return result;
}

async function regenerateApiKey() {
  const newKey = generateRandomKey();
  apiKeyInput.value = newKey;
  localStorage.setItem('oneasr_api_key', newKey);
  await saveSettings();
}

async function handleApiKeyChange() {
  const val = apiKeyInput.value.trim();
  apiKeyInput.value = val;
  if (val) {
    localStorage.setItem('oneasr_api_key', val);
  } else {
    localStorage.removeItem('oneasr_api_key');
  }
  await saveSettings();
}

async function copyApiKey() {
  if (!apiKeyInput.value) return;
  try {
    await navigator.clipboard.writeText(apiKeyInput.value);
    apiKeyCopied.value = true;
    setTimeout(() => {
      apiKeyCopied.value = false;
    }, 2000);
  } catch (err) {
    console.warn('Copy failed:', err);
  }
}

async function resetAdvancedDefaults() {
  vadThreshold.value = 0.50;
  targetChunkDuration.value = 6.0;
  maxLoadedModels.value = 2;
  await saveSettings();
}

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

watch(() => props.isOpen, (open) => {
  if (open) {
    fetchSettings();
  }
});

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
      if (data.hardware) {
        hardwareAccel.value = data.hardware.accelerator || 'mps';
        deviceDesc.value = data.hardware.device_name || '';
      }
      if (data.storage) {
        modelsDirPath.value = data.storage.models_dir || '';
        diskFreeGb.value = data.storage.disk_free_gb;
        diskTotalGb.value = data.storage.disk_total_gb;
      }
    }
  } catch (err) {
    // Engine not online yet, keep defaults
  }

  try {
    const cfg = await apiClient.get('/v1/x/system/settings');
    if (cfg) {
      if (cfg.host === '0.0.0.0') isLanExposed.value = true;
      const ka = cfg.keep_alive ?? cfg.default_keep_alive ?? cfg.keep_alive_timeout;
      if (ka !== undefined && ka !== null) keepAliveTimeout.value = String(ka);
      if (cfg.download_source) downloadSource.value = cfg.download_source;
      if (cfg.models_dir) modelsDirPath.value = cfg.models_dir;
      if (cfg.api_key !== undefined && cfg.api_key !== null) {
        apiKeyInput.value = cfg.api_key;
        if (cfg.api_key) {
          localStorage.setItem('oneasr_api_key', cfg.api_key);
        } else {
          localStorage.removeItem('oneasr_api_key');
        }
      }
      if (cfg.max_loaded_models !== undefined && cfg.max_loaded_models !== null) {
        maxLoadedModels.value = Number(cfg.max_loaded_models);
      }
      if (cfg.vad_threshold !== undefined && cfg.vad_threshold !== null) {
        vadThreshold.value = Number(cfg.vad_threshold);
      }
      if (cfg.target_chunk_duration !== undefined && cfg.target_chunk_duration !== null) {
        targetChunkDuration.value = Number(cfg.target_chunk_duration);
      }
    }
  } catch (err) {
    // Keep defaults
  }
}

async function saveSettings() {
  try {
    const kaVal = parseInt(keepAliveTimeout.value, 10);
    const keyVal = apiKeyInput.value.trim() || null;
    await apiClient.post('/v1/x/system/settings', {
      keep_alive: kaVal,
      keep_alive_timeout: kaVal,
      host: isLanExposed.value ? '0.0.0.0' : '127.0.0.1',
      download_source: downloadSource.value,
      api_key: keyVal,
      max_loaded_models: Number(maxLoadedModels.value),
      vad_threshold: Number(vadThreshold.value),
      target_chunk_duration: Number(targetChunkDuration.value)
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
    console.warn('Native open_local_dir (models) failed, falling back to REST API:', err);
    apiClient.post('/v1/x/system/open-path', { path: modelsDirPath.value || '~/.oneasr/models' });
  });
}

function openLogs() {
  invoke('open_local_dir', { target: 'logs' }).catch((err) => {
    console.warn('Native open_local_dir (logs) failed, falling back to REST API:', err);
    apiClient.post('/v1/x/system/open-path', { path: '~/.oneasr/logs' });
  });
}

function openDocs() {
  window.open('http://127.0.0.1:8020/docs', '_blank');
}

function openGithub() {
  window.open('https://github.com/codeAndxv/OneASR', '_blank');
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal-card {
  width: 100%;
  max-width: 580px;
  min-height: 440px;
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

/* Tabs Bar */
.modal-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.tab-btn.active {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--border-subtle);
}

.tab-icon {
  display: flex;
  align-items: center;
}

.tab-label {
  line-height: 1;
}

/* Body */
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background-color: var(--bg-surface);
}

.tab-pane {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.settings-group {
  background-color: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 10px 16px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
}

.setting-row:last-child {
  border-bottom: none;
  padding-bottom: 2px;
}

.setting-row:first-of-type {
  padding-top: 2px;
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-width: 70%;
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

.mono-path {
  font-family: monospace;
  font-size: 11.5px;
  color: var(--text-muted);
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

.api-key-control-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 1;
}

.api-key-input-group {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  justify-content: flex-end;
}

.api-key-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.api-key-input {
  width: 175px;
  background: var(--bg-card, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  padding: 4px 26px 4px 8px;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.15s ease;
}

.api-key-input:focus {
  border-color: var(--accent-emerald);
}

.eye-toggle-btn {
  position: absolute;
  right: 6px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  border-radius: 4px;
  transition: color 0.15s ease;
}

.eye-toggle-btn:hover {
  color: var(--text-primary);
}

.advanced-group {
  margin-top: 10px;
}

.advanced-details summary {
  list-style: none;
  cursor: pointer;
}

.advanced-details summary::-webkit-details-marker {
  display: none;
}

.advanced-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}

.summary-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-title {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.summary-chevron {
  font-size: 12px;
  color: var(--text-muted);
  transition: transform 0.2s ease;
}

.advanced-details[open] .summary-chevron {
  transform: rotate(180deg);
}

.advanced-content {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.slider-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.range-slider {
  width: 120px;
  accent-color: var(--text-primary);
  cursor: pointer;
}

.slider-badge {
  min-width: 44px;
  text-align: center;
}

.advanced-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}

.disk-free-pill {
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
}

.info-callout {
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-callout-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
}

.callout-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.callout-desc {
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text-muted);
  margin: 0;
}

/* About Tab Styling */
.about-hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
}

.about-logo-wrapper {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.about-app-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  object-fit: contain;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.about-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.identity-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.about-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--text-primary);
}

.about-version-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
  background: rgba(16, 185, 129, 0.12);
  color: var(--accent-emerald);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.about-tagline {
  font-size: 12px;
  color: var(--text-secondary);
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
