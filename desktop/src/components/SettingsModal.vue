<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="isOpen" class="modal-backdrop">
        <div class="modal-card">
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

          <!-- Two-column Body: Left Sidebar + Right Content -->
          <div class="modal-layout">
            <!-- Left Sidebar Navigation -->
            <aside class="modal-sidebar">
              <button
                v-for="tab in tabs"
                :key="tab.id"
                class="sidebar-tab-btn"
                :class="{ active: activeTab === tab.id }"
                @click="activeTab = tab.id"
              >
                <span class="tab-icon" v-html="tab.icon"></span>
                <span class="tab-label">{{ t(tab.labelKey) }}</span>
              </button>
            </aside>

            <!-- Right Content Area -->
            <main class="modal-content">
              <!-- Tab 1: General (常规设置) -->
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

              <!-- Tab 2: Service & API (网络与服务) -->
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
                      <span class="row-desc">{{ t('portDesc') }}</span>
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
              </div>

              <!-- Tab 3: Engine & Compute (引擎与计算) -->
              <div v-else-if="activeTab === 'engine'" class="tab-pane">
                <div class="settings-group">
                  <div class="setting-row">
                    <div class="row-info">
                      <span class="row-label">{{ t('aboutAcceleration') }}</span>
                      <span class="row-desc">{{ deviceDesc || 'Apple Silicon Metal (MPS)' }}</span>
                    </div>
                    <div class="row-control">
                      <span class="status-pill active">{{ hardwareAccel === 'mps' ? t('accelAppleMps') : (hardwareAccel === 'cuda' ? t('accelNvidiaCuda') : t('accelCpu')) }}</span>
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
                        <option :value="2">2 {{ t('recommendedDefault') }}</option>
                        <option :value="3">3</option>
                        <option :value="4">4</option>
                        <option :value="5">5</option>
                      </select>
                    </div>
                  </div>

                  <div class="setting-row">
                    <div class="row-info">
                      <span class="row-label">{{ t('keepAliveLabel') }}</span>
                      <span class="row-desc">{{ t('keepAliveDesc') }}</span>
                    </div>
                    <div class="row-control">
                      <select v-model="keepAliveTimeout" class="custom-select" @change="saveSettings">
                        <option value="0">{{ t('keepAliveImmediate') }}</option>
                        <option value="60">{{ t('keepAlive1Min') }}</option>
                        <option value="300">{{ t('keepAlive5Min') }}</option>
                        <option value="600">{{ t('keepAlive10Min') }}</option>
                        <option value="900">{{ t('keepAlive15Min') }}</option>
                        <option value="1800">{{ t('keepAlive30Min') }}</option>
                        <option value="-1">{{ t('keepAliveNever') }}</option>
                      </select>
                    </div>
                  </div>
                </div>

                <!-- Advanced Audio Chunking & VAD (Collapsible) -->
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

              <!-- Tab 4: Storage (存储管理) -->
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
                      <span class="row-desc">{{ t('storageVolumeTotal') }}: {{ diskTotalGb }} GB</span>
                    </div>
                    <div class="row-control">
                      <span class="disk-free-pill">{{ diskFreeGb }} {{ t('unitGbAvailable') }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Tab 5: About (关于) -->
              <div v-else-if="activeTab === 'about'" class="tab-pane">
                <div class="about-hero">
                  <div class="about-logo-wrapper">
                    <img :src="appLogo" alt="OneASR" class="about-app-icon" />
                  </div>
                  <div class="about-identity">
                    <div class="identity-top">
                      <span class="about-name">OneASR</span>
                      <span class="about-version-tag">v0.1.0</span>
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
                      <span class="row-label">{{ t('aboutGithub') }}</span>
                      <span class="row-desc">https://github.com/codeAndxv/OneASR</span>
                    </div>
                    <div class="row-control">
                      <button class="secondary-btn" @click="openGithub">
                        {{ t('visitGithub') }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </main>
          </div>

          <!-- Modal Footer -->
          <div class="modal-footer">
            <span class="footer-hint">{{ t('settingsEscHint') }}</span>
            <button class="primary-btn" @click="$emit('close')">
              {{ t('btnConfirm') }}
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
    icon: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
  },
  {
    id: 'service',
    labelKey: 'tabService',
    icon: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
  },
  {
    id: 'engine',
    labelKey: 'tabEngine',
    icon: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="15" x2="23" y2="15"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="15" x2="4" y2="15"/></svg>'
  },
  {
    id: 'storage',
    labelKey: 'tabStorage',
    icon: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
  },
  {
    id: 'about',
    labelKey: 'tabAbout',
    icon: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  }
];

const selectedTheme = ref(currentTheme.value);
const isLanExposed = ref(false);
const keepAliveTimeout = ref('600');
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
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
  }
  return result;
}

function regenerateApiKey() {
  const newKey = generateRandomKey();
  apiKeyInput.value = newKey;
  handleApiKeyChange();
}

async function copyApiKey() {
  if (!apiKeyInput.value) return;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(apiKeyInput.value);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = apiKeyInput.value;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
    apiKeyCopied.value = true;
    setTimeout(() => {
      apiKeyCopied.value = false;
    }, 2000);
  } catch (err) {
    console.error('Failed to copy API key:', err);
  }
}

async function handleApiKeyChange() {
  const keyToSave = apiKeyInput.value.trim();
  localStorage.setItem('oneasr_api_key', keyToSave);
  await saveSettings();
}

async function toggleLan() {
  isLanExposed.value = !isLanExposed.value;
  await saveSettings();
}

async function resetAdvancedDefaults() {
  vadThreshold.value = 0.50;
  targetChunkDuration.value = 6.0;
  await saveSettings();
}

async function saveSettings() {
  try {
    await apiClient.put('/v1/x/system/settings', {
      host: isLanExposed.value ? '0.0.0.0' : '127.0.0.1',
      keep_alive: parseInt(keepAliveTimeout.value, 10),
      download_source: downloadSource.value,
      api_key: apiKeyInput.value.trim(),
      max_loaded_models: maxLoadedModels.value,
      vad_threshold: vadThreshold.value,
      target_chunk_duration: targetChunkDuration.value
    });
  } catch (e) {
    console.warn('Failed to persist settings to server:', e);
  }
}

function handleThemeChange() {
  setTheme(selectedTheme.value);
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
      if (data.system) {
        hardwareAccel.value = data.system.device || 'mps';
        deviceDesc.value = data.system.device_name || '';
      }
      if (data.storage) {
        modelsDirPath.value = data.storage.models_dir || '';
        if (data.storage.disk_free_gb !== undefined) {
          diskFreeGb.value = data.storage.disk_free_gb;
        }
        if (data.storage.disk_total_gb !== undefined) {
          diskTotalGb.value = data.storage.disk_total_gb;
        }
      }
    }
  } catch (e) {
    console.warn('Could not fetch system info:', e);
  }

  try {
    const settings = await apiClient.get('/v1/x/system/settings');
    if (settings) {
      if (settings.host !== undefined) {
        isLanExposed.value = settings.host === '0.0.0.0';
      }
      if (settings.keep_alive !== undefined) {
        const valStr = String(settings.keep_alive);
        keepAliveTimeout.value = ['0', '60', '300', '600', '900', '1800', '-1'].includes(valStr) ? valStr : '600';
      }
      if (settings.download_source) {
        downloadSource.value = settings.download_source;
      }
      if (settings.api_key !== undefined) {
        apiKeyInput.value = settings.api_key || '';
        localStorage.setItem('oneasr_api_key', apiKeyInput.value);
      }
      if (settings.max_loaded_models !== undefined) {
        maxLoadedModels.value = settings.max_loaded_models;
      }
      if (settings.vad_threshold !== undefined) {
        vadThreshold.value = settings.vad_threshold;
      }
      if (settings.target_chunk_duration !== undefined) {
        targetChunkDuration.value = settings.target_chunk_duration;
      }
    }
  } catch (e) {
    console.warn('Could not fetch server settings:', e);
  }
}

async function openFolder() {
  try {
    await invoke('open_local_dir', { target: 'models' });
  } catch (err) {
    console.warn('Tauri open_local_dir failed, fallback to server:', err);
    try {
      await apiClient.post('/v1/x/system/open-folder', { target: 'models' });
    } catch (e) {
      console.error('Failed to open models folder:', e);
    }
  }
}

async function openLogs() {
  try {
    await invoke('open_local_dir', { target: 'logs' });
  } catch (err) {
    console.warn('Tauri open_local_dir failed, fallback to server:', err);
    try {
      await apiClient.post('/v1/x/system/open-folder', { target: 'logs' });
    } catch (e) {
      console.error('Failed to open logs folder:', e);
    }
  }
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
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal-card {
  width: 760px;
  max-width: 92vw;
  height: 540px;
  max-height: 86vh;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  box-shadow: 0 24px 56px rgba(0, 0, 0, 0.45), 0 0 0 1px var(--border-subtle);
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

/* Two-column Layout */
.modal-layout {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* Left Sidebar Navigation */
.modal-sidebar {
  width: 185px;
  flex-shrink: 0;
  background: var(--bg-canvas, rgba(255, 255, 255, 0.02));
  border-right: 1px solid var(--border-subtle);
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.sidebar-tab-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  width: 100%;
  text-align: left;
}

.sidebar-tab-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.sidebar-tab-btn.active {
  color: var(--accent-emerald, #10B981);
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.25);
  font-weight: 600;
}

[data-theme="light"] .sidebar-tab-btn:hover {
  background: rgba(0, 0, 0, 0.05);
}

[data-theme="light"] .sidebar-tab-btn.active {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.25);
}

.tab-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.tab-label {
  line-height: 1.2;
}

/* Right Content Area */
.modal-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 20px 24px;
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
  padding: 11px 0;
  border-bottom: 1px solid var(--border-subtle);
}

.setting-row:last-child {
  border-bottom: none;
  padding-bottom: 2px;
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-width: 62%;
}

.row-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.row-desc {
  font-size: 11.5px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.mono-path {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: var(--text-muted);
}

.row-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.custom-select {
  padding: 5px 10px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 12px;
  font-family: inherit;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s ease;
  min-width: 140px;
}

.custom-select:focus {
  border-color: var(--accent-emerald, #10B981);
}

.toggle-btn {
  width: 40px;
  height: 22px;
  background-color: rgba(255, 255, 255, 0.12);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 2px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  display: inline-block;
}

.toggle-btn.active {
  background-color: var(--accent-emerald, #10B981);
  border-color: var(--accent-emerald, #10B981);
}

.toggle-slider {
  width: 16px;
  height: 16px;
  background-color: #fff;
  border-radius: 50%;
  display: block;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.toggle-btn.active .toggle-slider {
  transform: translateX(18px);
}

.mono-badge {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  padding: 3px 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
}

/* API Key Input */
.api-key-control-wrap {
  width: 100%;
  max-width: 320px;
}

.api-key-input-group {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.api-key-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
}

.api-key-input {
  width: 100%;
  padding: 5px 28px 5px 10px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 12px;
  font-family: var(--font-mono, monospace);
  outline: none;
  transition: border-color 0.15s ease;
}

.api-key-input:focus {
  border-color: var(--accent-emerald, #10B981);
}

.eye-toggle-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 4px;
}

.eye-toggle-btn:hover {
  color: var(--text-primary);
}

.secondary-btn {
  padding: 5px 12px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.secondary-btn:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.08);
  border-color: var(--border-hover);
}

.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.status-pill {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}

.status-pill.active {
  background: rgba(16, 185, 129, 0.12);
  color: var(--accent-emerald, #10B981);
  border-color: rgba(16, 185, 129, 0.3);
}

.disk-free-pill {
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(16, 185, 129, 0.12);
  color: var(--accent-emerald, #10B981);
}

/* Advanced Collapsible Section */
.advanced-group {
  padding: 0;
}

.advanced-details {
  border-radius: 8px;
}

.advanced-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  list-style: none;
}

.advanced-summary::-webkit-details-marker {
  display: none;
}

.summary-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.summary-left .group-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.summary-desc {
  font-size: 11.5px;
  color: var(--text-secondary);
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
  padding: 0 16px 12px 16px;
  border-top: 1px solid var(--border-subtle);
}

.slider-control {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 170px;
}

.range-slider {
  flex: 1;
  accent-color: var(--accent-emerald, #10B981);
  cursor: pointer;
}

.slider-badge {
  min-width: 44px;
  text-align: center;
}

.advanced-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

/* About Section Hero */
.about-hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
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
  gap: 3px;
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
  color: var(--accent-emerald, #10B981);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.about-tagline {
  font-size: 12px;
  color: var(--text-secondary);
}

/* Modal Footer */
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
  font-size: 11.5px;
  color: var(--text-muted);
}

.primary-btn {
  padding: 6px 16px;
  background-color: var(--accent-emerald, #10B981);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.primary-btn:hover {
  opacity: 0.9;
}

/* Transitions */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.18s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@keyframes modal-pop {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
