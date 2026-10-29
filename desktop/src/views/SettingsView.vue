<template>
  <div class="settings-view">
    <div class="settings-container">
      <!-- Section 1: General (Theme & Language) -->
      <div class="settings-group">
        <h3 class="group-title">{{ t('sectionGeneral') }}</h3>
        
        <div class="setting-row">
          <div class="row-info">
            <span class="row-label">{{ t('generalTheme') }}</span>
            <span class="row-desc">{{ t('generalThemeDesc') || '浅色、深色或随系统自动切换' }}</span>
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
            <span class="row-desc">{{ t('generalLanguageDesc') || '系统界面多语言支持' }}</span>
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
            <span class="row-label">{{ t('apiBaseLabel') }}</span>
            <span class="row-desc">{{ t('apiBaseDesc') }}</span>
          </div>
          <div class="row-control url-control-wrap">
            <div class="url-input-group">
              <input
                v-model="apiBaseInput"
                type="text"
                class="url-input"
                :placeholder="defaultPlaceholder"
                @change="handleApiBaseChange"
              />
              <button
                class="secondary-btn ping-btn"
                :disabled="isPinging"
                @click="testApiConnection"
              >
                <span v-if="isPinging" class="btn-spinner"></span>
                <span v-else>{{ t('apiTestPing') }}</span>
              </button>
              <button
                v-if="hasCustomApiBase"
                class="secondary-btn reset-btn"
                @click="resetApiBase"
              >
                {{ t('apiResetDefault') }}
              </button>
            </div>
            <span v-if="pingStatus" class="ping-badge" :class="pingStatus.ok ? 'success' : 'error'">
              {{ pingStatus.message }}
            </span>
          </div>
        </div>

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
            <span class="row-label">{{ t('downloadNetworkSettingsLabel') }}</span>
            <span class="row-desc">{{ t('downloadNetworkSettingsDesc') }}</span>
          </div>
          <div class="row-control">
            <select v-model="downloadSource" class="custom-select" @change="saveSettings">
              <option value="modelscope">{{ t('downloadNetworkOptionCn') }}</option>
              <option value="huggingface">{{ t('downloadNetworkOptionGlobal') }}</option>
              <option value="hf-mirror">{{ t('downloadNetworkOptionHfMirror') }}</option>
              <option value="auto">{{ t('downloadNetworkOptionAuto') }}</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Section 4: Lifecycle Strategy -->
      <div class="settings-group">
        <h3 class="group-title">{{ t('sectionStrategy') }}</h3>
        
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
      </div>

      <!-- Section 5: Hardware & Diagnosis -->
      <div class="settings-group">
        <h3 class="group-title">{{ t('sectionDiagnostics') }}</h3>
        
        <div class="setting-row">
          <div class="row-info">
            <span class="row-label">{{ t('hardwareChip') }}</span>
            <span class="row-desc">Metal Performance Shaders (Apple Silicon)</span>
          </div>
          <div class="row-control">
            <span class="status-pill active">Apple MPS</span>
          </div>
        </div>

        <div class="setting-row">
          <div class="row-info">
            <span class="row-label">{{ t('swaggerDocs') }}</span>
            <span class="row-desc">http://127.0.0.1:8020/docs</span>
          </div>
          <div class="row-control">
            <button class="secondary-btn" @click="openDocs">
              {{ t('apiDocsBtn') }}
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

      <!-- Section 6: Advanced Toolkit & VAD (Collapsible) -->
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from '../i18n';
import {
  apiClient,
  getApiBaseUrl,
  getDefaultApiBaseUrl,
  setApiBaseUrl,
  resetApiBaseUrl
} from '../api/client';
import { currentTheme, setTheme } from '../utils/theme';

const { locale, setLocale, t } = useI18n();

const selectedTheme = ref(currentTheme.value);
const isLanExposed = ref(false);
const keepAliveTimeout = ref('300');
const downloadSource = ref('modelscope');
const maxLoadedModels = ref(2);
const vadThreshold = ref(0.50);
const targetChunkDuration = ref(6.0);

const apiKeyInput = ref(localStorage.getItem('oneasr_api_key') || '');
const apiKeyCopied = ref(false);
const showApiKey = ref(false);

const apiBaseInput = ref(localStorage.getItem('oneasr_api_base') || '');
const defaultPlaceholder = computed(() => `默认: ${getDefaultApiBaseUrl()}`);
const hasCustomApiBase = computed(() => Boolean(apiBaseInput.value && apiBaseInput.value.trim()));
const isPinging = ref(false);
const pingStatus = ref(null);

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

function handleApiBaseChange() {
  if (apiBaseInput.value && apiBaseInput.value.trim()) {
    setApiBaseUrl(apiBaseInput.value.trim());
  } else {
    resetApiBaseUrl();
  }
  pingStatus.value = null;
}

function resetApiBase() {
  apiBaseInput.value = '';
  resetApiBaseUrl();
  pingStatus.value = null;
}

async function testApiConnection() {
  isPinging.value = true;
  pingStatus.value = null;
  const target = (apiBaseInput.value && apiBaseInput.value.trim()) || getDefaultApiBaseUrl();
  const res = await apiClient.testConnection(target);
  isPinging.value = false;
  if (res.ok) {
    const chip = res.data?.system?.chip ? ` · ${res.data.system.chip}` : '';
    pingStatus.value = { ok: true, message: `${t('apiPingSuccess')}${chip}` };
  } else {
    pingStatus.value = { ok: false, message: `${t('apiPingFailed')}: ${res.error || res.status}` };
  }
}

function handleThemeChange() {
  setTheme(selectedTheme.value);
}

onMounted(async () => {
  try {
    const sys = await apiClient.getSystemSettings();
    if (sys) {
      isLanExposed.value = sys.host === '0.0.0.0';
      const val = sys.keep_alive ?? sys.default_keep_alive ?? sys.keep_alive_timeout;
      if (val !== undefined && val !== null) {
        keepAliveTimeout.value = String(val);
      }
      if (sys.download_source) {
        downloadSource.value = sys.download_source;
      }
      if (sys.api_key !== undefined && sys.api_key !== null) {
        apiKeyInput.value = sys.api_key;
        if (sys.api_key) {
          localStorage.setItem('oneasr_api_key', sys.api_key);
        } else {
          localStorage.removeItem('oneasr_api_key');
        }
      }
      if (sys.max_loaded_models !== undefined && sys.max_loaded_models !== null) {
        maxLoadedModels.value = Number(sys.max_loaded_models);
      }
      if (sys.vad_threshold !== undefined && sys.vad_threshold !== null) {
        vadThreshold.value = Number(sys.vad_threshold);
      }
      if (sys.target_chunk_duration !== undefined && sys.target_chunk_duration !== null) {
        targetChunkDuration.value = Number(sys.target_chunk_duration);
      }
    }
  } catch (err) {
    console.warn('Could not load system settings:', err);
  }
});

async function toggleLan() {
  isLanExposed.value = !isLanExposed.value;
  await saveSettings();
}

async function saveSettings() {
  try {
    const kaVal = parseInt(keepAliveTimeout.value, 10);
    const keyVal = apiKeyInput.value.trim() || null;
    await apiClient.updateSystemSettings({
      host: isLanExposed.value ? '0.0.0.0' : '127.0.0.1',
      keep_alive: kaVal,
      keep_alive_timeout: kaVal,
      download_source: downloadSource.value,
      api_key: keyVal,
      max_loaded_models: Number(maxLoadedModels.value),
      vad_threshold: Number(vadThreshold.value),
      target_chunk_duration: Number(targetChunkDuration.value)
    });
  } catch (err) {
    console.error('Save settings error:', err);
  }
}
  } catch (err) {
    console.error('Save settings error:', err);
  }
}

function openFolder() {
  window.open('file:///Users/dudu/.oneasr/models', '_blank');
}

function openDocs() {
  window.open('http://127.0.0.1:8020/docs', '_blank');
}

function openLogs() {
  window.open('file:///Users/dudu/.oneasr/logs', '_blank');
}
</script>

<style scoped>
.settings-view {
  padding: 16px 20px;
  overflow-y: auto;
  height: 100%;
}

.settings-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 620px;
  margin: 0 auto;
}

.settings-group {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-subtle);
}

.setting-row:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.row-desc {
  font-size: 11px;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.custom-select {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 11px;
  padding: 5px 8px;
  border-radius: 6px;
  outline: none;
  cursor: pointer;
}

.custom-select option {
  background: var(--bg-card);
  color: var(--text-primary);
}

.secondary-btn {
  background: var(--bg-app);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.secondary-btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-focus);
}

.mono-badge {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 11px;
  background: var(--bg-app);
  border: 1px solid var(--border-subtle);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--text-secondary);
}

.status-pill {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-pill.active {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
}

.toggle-btn {
  width: 36px;
  height: 20px;
  background: var(--border-subtle);
  border-radius: 10px;
  border: none;
  cursor: pointer;
  position: relative;
  transition: background 0.2s ease;
}

.toggle-btn.active {
  background: var(--accent-emerald);
}

.toggle-slider {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s ease;
}

.toggle-btn.active .toggle-slider {
  transform: translateX(16px);
}

.url-control-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex: 1;
}

.url-input-group {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  justify-content: flex-end;
}

.url-input {
  width: 220px;
  background: var(--bg-app);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 11.5px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  padding: 4px 8px;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.15s ease;
}

.url-input:focus {
  border-color: var(--border-focus);
}

.ping-btn, .reset-btn {
  white-space: nowrap;
  padding: 4px 8px;
}

.ping-badge {
  font-size: 10.5px;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1.2;
}

.ping-badge.success {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
}

.ping-badge.error {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.btn-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 1.5px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
  width: 210px;
  background: var(--bg-app);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  padding: 4px 26px 4px 8px;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.15s ease;
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

.api-key-input:focus {
  border-color: var(--border-focus);
}

.slider-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.range-slider {
  width: 130px;
  accent-color: var(--text-primary);
  cursor: pointer;
}

.slider-badge {
  min-width: 44px;
  text-align: center;
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
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.advanced-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}
</style>
