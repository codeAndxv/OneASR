<template>
  <div class="settings-view">
    <div class="settings-container">
      <!-- Section 1: Storage & Paths -->
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

      <!-- Section 2: Network & Host -->
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

      <!-- Section 3: Lifecycle Strategy -->
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

      <!-- Section 4: Hardware & Diagnosis -->
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

      <!-- Section 5: Language -->
      <div class="settings-group">
        <h3 class="group-title">{{ t('sectionLanguage') }}</h3>
        
        <div class="setting-row">
          <div class="row-info">
            <span class="row-label">{{ t('languageLabel') }}</span>
          </div>
          <div class="row-control">
            <select :value="locale" class="custom-select" @change="e => setLocale(e.target.value)">
              <option value="zh-CN">简体中文 (Simplified Chinese)</option>
              <option value="en-US">English (US)</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from '../i18n';
import { apiClient } from '../api/client';

const { locale, setLocale, t } = useI18n();

const isLanExposed = ref(false);
const keepAliveTimeout = ref('300');

onMounted(async () => {
  try {
    const sys = await apiClient.getSystemSettings();
    if (sys) {
      isLanExposed.value = sys.host === '0.0.0.0';
      if (sys.keep_alive_timeout !== undefined) {
        keepAliveTimeout.value = String(sys.keep_alive_timeout);
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
    await apiClient.updateSystemSettings({
      host: isLanExposed.value ? '0.0.0.0' : '127.0.0.1',
      keep_alive_timeout: parseInt(keepAliveTimeout.value, 10)
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
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
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 6px;
  outline: none;
}

.secondary-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.secondary-btn:hover {
  background: rgba(255, 255, 255, 0.09);
  color: var(--text-primary);
}

.mono-badge {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.04);
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
  background: rgba(255, 255, 255, 0.1);
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
</style>
