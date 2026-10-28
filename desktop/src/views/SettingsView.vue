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
            <span class="row-desc">无请求时自动释放模型占用的显存与内存</span>
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

const apiBaseInput = ref(localStorage.getItem('oneasr_api_base') || '');
const defaultPlaceholder = computed(() => `默认: ${getDefaultApiBaseUrl()}`);
const hasCustomApiBase = computed(() => Boolean(apiBaseInput.value && apiBaseInput.value.trim()));
const isPinging = ref(false);
const pingStatus = ref(null);

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
    await apiClient.updateSystemSettings({
      host: isLanExposed.value ? '0.0.0.0' : '127.0.0.1',
      keep_alive: kaVal,
      keep_alive_timeout: kaVal,
      download_source: downloadSource.value
    });
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
</style>
