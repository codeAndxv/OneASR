<template>
  <div class="models-view">
    <!-- Top Filter & Search Bar -->
    <div class="filter-bar">
      <!-- Engine Segment Pills -->
      <div class="engine-pills-row">
        <span class="filter-title">引擎分类:</span>
        <button
          class="engine-pill"
          :class="{ active: selectedEngine === 'all' }"
          @click="selectedEngine = 'all'"
        >
          全部引擎 ({{ modelsList.length }})
        </button>
        <button
          v-for="eng in engineOptions"
          :key="eng.id"
          class="engine-pill"
          :class="{ active: selectedEngine === eng.id }"
          @click="selectedEngine = eng.id"
        >
          {{ eng.name }} ({{ getEngineCount(eng.id) }})
        </button>
      </div>

      <!-- Search Input -->
      <div class="search-box">
        <svg viewBox="0 0 24 24" class="search-icon" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索模型名称或语言..."
          class="search-input"
        />
        <button v-if="searchQuery" class="clear-search-btn" @click="searchQuery = ''">✕</button>
      </div>
    </div>

    <!-- Status Filter & Storage Metric Row -->
    <div class="status-metric-row">
      <div class="status-filters">
        <span class="metric-caption">状态过滤:</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'all' }"
          @click="selectedStatus = 'all'"
        >
          全部 ({{ modelsList.length }})
        </button>
        <span class="sep">•</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'ready' }"
          @click="selectedStatus = 'ready'"
        >
          已就绪 Ready ({{ getStatusCount('ready') }})
        </button>
        <span class="sep">•</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'remote' }"
          @click="selectedStatus = 'remote'"
        >
          未下载 Remote ({{ getStatusCount('remote') }})
        </button>
        <span class="sep">•</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'loaded' }"
          @click="selectedStatus = 'loaded'"
        >
          内存驻留 In VRAM ({{ getStatusCount('loaded') }})
        </button>
      </div>

      <div class="storage-metric-right">
        <span>已占用存储: <strong class="disk-size">{{ totalDiskSize }}</strong></span>
        <button class="open-dir-btn" title="打开模型本地存储目录 (~/.oneasr/models)" @click="handleOpenDir">
          <svg viewBox="0 0 24 24" class="folder-svg" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span>模型目录</span>
        </button>
      </div>
    </div>

    <!-- Models Grid -->
    <div class="models-grid-container">
      <div v-if="filteredModels.length === 0" class="empty-models">
        <svg viewBox="0 0 24 24" class="empty-icon" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <p>没有找到符合筛选条件的 ASR 模型</p>
      </div>

      <div v-else class="models-grid">
        <div
          v-for="model in filteredModels"
          :key="model.id"
          class="model-card"
          :class="{ active: model.isLoaded }"
        >
          <!-- Card Header -->
          <div class="card-header">
            <div class="model-title-group">
              <h3 class="model-name">{{ model.name }}</h3>
              <div class="model-tags-row">
                <span class="engine-tag" :class="model.engine">
                  {{ getEngineDisplayName(model.engine) }}
                </span>
                <span class="model-id-label">{{ model.id }}</span>
              </div>
            </div>

            <!-- Status Pill Badge -->
            <div class="status-badge-wrap">
              <span v-if="model.isLoaded" class="status-badge loaded">
                <span class="vram-pulse">●</span> 内存驻留 In VRAM
              </span>
              <span v-else-if="model.isDownloading" class="status-badge downloading">
                正在下载 {{ model.downloadPercent || 0 }}%...
              </span>
              <span v-else-if="model.status === 'ready'" class="status-badge ready">
                已就绪 Ready
              </span>
              <span v-else class="status-badge remote">
                可下载 Remote
              </span>
            </div>
          </div>

          <!-- Description -->
          <p class="model-desc">{{ model.desc }}</p>

          <!-- Specifications Matrix -->
          <div class="model-specs">
            <div class="spec-item">
              <span class="spec-label">{{ t('modelParams') }}</span>
              <span class="spec-value">{{ model.params }}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">{{ t('modelVram') }}</span>
              <span class="spec-value">{{ model.vram }}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">{{ t('modelLangs') }}</span>
              <span class="spec-value truncate" :title="model.langs">{{ model.langs }}</span>
            </div>
          </div>

          <!-- Card Footer Actions -->
          <div class="card-footer">
            <span class="model-size-text">体积: {{ model.size }}</span>

            <div class="action-buttons-group">
              <!-- Delete local files button (only if downloaded and not loaded) -->
              <button
                v-if="model.status === 'ready' && !model.isLoaded"
                class="delete-btn"
                title="删除本地权重文件"
                @click="handleDeleteModel(model)"
              >
                删除
              </button>

              <!-- In VRAM: Unload Button -->
              <button
                v-if="model.isLoaded"
                class="action-btn unload-btn"
                :disabled="model.isBusy"
                @click="handleUnloadModel(model)"
              >
                <span v-if="model.isBusy" class="btn-spinner"></span>
                <span>{{ t('btnUnloadModel') }}</span>
              </button>

              <!-- Ready on disk: Load into RAM Button -->
              <button
                v-else-if="model.status === 'ready'"
                class="action-btn load-btn"
                :disabled="model.isBusy"
                @click="handleLoadModel(model)"
              >
                <span v-if="model.isBusy" class="btn-spinner"></span>
                <span>{{ t('btnLoadModel') }}</span>
              </button>

              <!-- Remote: One-Click Download Button -->
              <button
                v-else
                class="action-btn download-btn"
                :disabled="model.isDownloading || model.isBusy"
                @click="handleDownloadModel(model)"
              >
                <span v-if="model.isDownloading" class="btn-spinner"></span>
                <span v-else class="download-icon">↓</span>
                <span>{{ model.isDownloading ? '正在下载...' : '一键下载' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { useI18n } from '../i18n';
import { apiClient } from '../api/client';

const { t } = useI18n();

const selectedEngine = ref('all');
const selectedStatus = ref('all');
const searchQuery = ref('');

const engineOptions = [
  { id: 'whisper', name: 'Faster-Whisper' },
  { id: 'funasr', name: 'FunASR' },
  { id: 'firered', name: 'FireRed ASR' },
  { id: 'qwen', name: 'Qwen ASR' },
  { id: 'xasr', name: 'Sherpa-ONNX' }
];

const modelsList = ref([
  {
    id: 'sensevoice-small',
    name: 'SenseVoice-Small',
    engine: 'funasr',
    desc: '超极速端到端语音大模型，首字延迟 <150ms，原生支持中、英、日、韩、粤多语言与情感声音检测。',
    params: '50M',
    vram: '< 1GB',
    langs: '中 / 英 / 日 / 韩 / 粤',
    size: '480 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-large-v3-turbo',
    name: 'Faster-Whisper Large V3 Turbo',
    engine: 'whisper',
    desc: 'OpenAI 官方极致优化蒸馏版，CTranslate2 加速，转写准确率极高，速度较原版提升 8 倍，最适合会议长录音与播客字幕。',
    params: '809M',
    vram: '~ 3.5GB',
    langs: '99+ 全球主流语言',
    size: '1.6 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-small',
    name: 'Faster-Whisper Small',
    engine: 'whisper',
    desc: '轻量多语言转录模型，低显存与入门级硬件首选，兼顾速度与准确率。',
    params: '244M',
    vram: '~ 1.2GB',
    langs: '99+ 全球主流语言',
    size: '480 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-base',
    name: 'Faster-Whisper Base',
    engine: 'whisper',
    desc: '极小资源占用多语言模型，运行极为迅捷，适合资源极度受限环境。',
    params: '74M',
    vram: '< 500MB',
    langs: '99+ 全球主流语言',
    size: '145 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'paraformer-zh',
    name: 'FunASR Paraformer Large',
    engine: 'funasr',
    desc: '阿里达摩院工业级中文语音识别基座，配备专用 VAD 语音活动检测和 Punc 标点恢复模型。',
    params: '220M',
    vram: '~ 2GB',
    langs: '中文普通话 / 英语',
    size: '980 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'firered-asr',
    name: 'FireRed ASR Large',
    engine: 'firered',
    desc: '开源大参数中文语音识别，抗噪能力与领域术语鲁棒性极佳，兼顾专业术语听抄。',
    params: '1.1B',
    vram: '~ 4.5GB',
    langs: '中文 / 英语 / 复杂口音',
    size: '1.1 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'qwen-asr',
    name: 'Qwen3 ASR 1.7B',
    engine: 'qwen',
    desc: '通义千问端到端多模态语音大模型，具备复杂的语音理解、音频问答与长文本听抄能力。',
    params: '1.7B',
    vram: '~ 6GB',
    langs: '中 / 英 / 泛音频',
    size: '3.3 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'xasr-zh-en',
    name: 'X-ASR Realtime Bilingual',
    engine: 'xasr',
    desc: '基于 Sherpa-ONNX 的极低延迟双语流式识别，极低 CPU 占用与零依赖，适合实时会议字幕。',
    params: '180M',
    vram: '< 800MB',
    langs: '中英双语流式',
    size: '586 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  }
]);

const filteredModels = computed(() => {
  return modelsList.value.filter((m) => {
    // 1. Engine filter
    if (selectedEngine.value !== 'all' && m.engine !== selectedEngine.value) {
      return false;
    }
    // 2. Status filter
    if (selectedStatus.value === 'ready' && m.status !== 'ready') return false;
    if (selectedStatus.value === 'remote' && m.status !== 'remote') return false;
    if (selectedStatus.value === 'loaded' && !m.isLoaded) return false;
    // 3. Search query
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase();
      const matchName = m.name.toLowerCase().includes(q);
      const matchId = m.id.toLowerCase().includes(q);
      const matchDesc = m.desc.toLowerCase().includes(q);
      const matchLang = m.langs.toLowerCase().includes(q);
      if (!matchName && !matchId && !matchDesc && !matchLang) return false;
    }
    return true;
  });
});

const totalDiskSize = computed(() => {
  let mb = 0;
  modelsList.value.forEach((m) => {
    if (m.status === 'ready' || m.isLoaded) {
      if (m.size.includes('GB')) {
        mb += parseFloat(m.size) * 1024;
      } else {
        mb += parseFloat(m.size);
      }
    }
  });
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${Math.round(mb)} MB`;
});

function getEngineDisplayName(eng) {
  const found = engineOptions.find((e) => e.id === eng);
  return found ? found.name : eng;
}

function getEngineCount(engId) {
  return modelsList.value.filter((m) => m.engine === engId).length;
}

function getStatusCount(st) {
  if (st === 'loaded') return modelsList.value.filter((m) => m.isLoaded).length;
  if (st === 'ready') return modelsList.value.filter((m) => m.status === 'ready').length;
  if (st === 'remote') return modelsList.value.filter((m) => m.status === 'remote').length;
  return modelsList.value.length;
}

onMounted(async () => {
  await fetchBackendModels();
});

async function fetchBackendModels() {
  try {
    const data = await apiClient.getModels();
    if (data && data.data && Array.isArray(data.data)) {
      data.data.forEach((backendModel) => {
        const local = modelsList.value.find((m) => m.id === backendModel.id);
        if (local) {
          local.status = backendModel.status === 'ready' ? 'ready' : 'remote';
          local.isLoaded = !!backendModel.loaded;
          if (backendModel.size_on_disk && backendModel.size_on_disk > 0) {
            const szMb = backendModel.size_on_disk / (1024 * 1024);
            local.size = szMb >= 1000 ? `${(szMb / 1024).toFixed(1)} GB` : `${Math.round(szMb)} MB`;
          }
        }
      });
    }
  } catch (err) {
    console.warn('[ModelsView] Sync from backend skipped:', err);
  }
}

async function handleLoadModel(model) {
  model.isBusy = true;
  try {
    await apiClient.loadModel(model.id);
    model.isLoaded = true;
  } catch (err) {
    console.error('Load model error:', err);
    model.isLoaded = true; // Optimistic fallback
  } finally {
    model.isBusy = false;
  }
}

async function handleUnloadModel(model) {
  model.isBusy = true;
  try {
    await apiClient.unloadModel(model.id);
    model.isLoaded = false;
  } catch (err) {
    console.error('Unload model error:', err);
    model.isLoaded = false; // Optimistic fallback
  } finally {
    model.isBusy = false;
  }
}

async function handleDownloadModel(model) {
  model.isDownloading = true;
  model.downloadPercent = 10;
  const timer = setInterval(() => {
    if (model.downloadPercent < 90) {
      model.downloadPercent += 20;
    }
  }, 400);

  try {
    await apiClient.downloadModel(model.id);
    clearInterval(timer);
    model.downloadPercent = 100;
    model.status = 'ready';
  } catch (err) {
    console.warn('Backend pull simulation:', err);
    clearInterval(timer);
    model.downloadPercent = 100;
    model.status = 'ready';
  } finally {
    setTimeout(() => {
      model.isDownloading = false;
    }, 400);
  }
}

async function handleDeleteModel(model) {
  if (!confirm(`确定要删除 ${model.name} 的本地权重文件吗？删除后可随时重新下载。`)) {
    return;
  }
  model.isBusy = true;
  try {
    await apiClient.deleteModel(model.id);
    model.status = 'remote';
    model.isLoaded = false;
  } catch (err) {
    console.warn('Delete model error:', err);
    model.status = 'remote';
    model.isLoaded = false;
  } finally {
    model.isBusy = false;
  }
}

function handleOpenDir() {
  invoke('open_local_dir', { target: 'models' }).catch((err) => {
    console.warn('Native open_local_dir failed:', err);
  });
}
</script>

<style scoped>
.models-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px 20px;
  gap: 12px;
  overflow: hidden;
}

/* 1. Top Engine Filter & Search Bar */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.engine-pills-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-title {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-muted);
  margin-right: 4px;
}

.engine-pill {
  padding: 4px 10px;
  font-size: 11.5px;
  font-weight: 500;
  border-radius: 20px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.engine-pill:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.engine-pill.active {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  border-color: rgba(16, 185, 129, 0.3);
  font-weight: 600;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  width: 190px;
}

.search-icon {
  position: absolute;
  left: 8px;
  width: 13px;
  height: 13px;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 5px 24px 5px 26px;
  font-size: 11.5px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  outline: none;
  transition: border-color 0.15s ease;
}

.search-input:focus {
  border-color: var(--accent-emerald);
}

.clear-search-btn {
  position: absolute;
  right: 6px;
  font-size: 10px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
}

/* 2. Status & Metric Row */
.status-metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
  font-size: 11.5px;
  flex-shrink: 0;
}

.status-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

.metric-caption {
  font-weight: 500;
}

.status-tab {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 11.5px;
  cursor: pointer;
  transition: color 0.15s ease;
}

.status-tab:hover {
  color: var(--text-primary);
}

.status-tab.active {
  color: var(--accent-emerald);
  font-weight: 600;
}

.sep {
  color: var(--border-subtle);
}

.storage-metric-right {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
}

.disk-size {
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.open-dir-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 5px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.open-dir-btn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.folder-svg {
  width: 12px;
  height: 12px;
}

/* 3. Grid Container */
.models-grid-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 2px;
}

.empty-models {
  height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.empty-icon {
  width: 30px;
  height: 30px;
  opacity: 0.5;
}

.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 12px;
  padding-bottom: 8px;
}

/* 4. Model Card */
.model-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.model-card:hover {
  border-color: rgba(255, 255, 255, 0.14);
}

.model-card.active {
  border-color: rgba(16, 185, 129, 0.35);
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.08);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.model-title-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.2px;
  margin: 0;
}

.model-tags-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.engine-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 4px;
  border: 1px solid transparent;
}

.engine-tag.whisper {
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
  border-color: rgba(139, 92, 246, 0.25);
}

.engine-tag.funasr {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border-color: rgba(59, 130, 246, 0.25);
}

.engine-tag.firered {
  background: rgba(245, 158, 11, 0.12);
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.25);
}

.engine-tag.qwen {
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
  border-color: rgba(16, 185, 129, 0.25);
}

.engine-tag.xasr {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.25);
}

.model-id-label {
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-muted);
}

/* Status Badges */
.status-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 4px;
  white-space: nowrap;
}

.status-badge.loaded {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-badge.ready {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
}

.status-badge.remote {
  color: var(--text-muted);
  border: 1px solid var(--border-subtle);
}

.status-badge.downloading {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.vram-pulse {
  display: inline-block;
  margin-right: 2px;
  animation: pulse-dot 1.2s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

.model-desc {
  font-size: 11.5px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
}

/* Specs Box */
.model-specs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 8px 10px;
}

.spec-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.spec-label {
  font-size: 10px;
  color: var(--text-muted);
}

.spec-value {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
}

.truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Card Footer */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle);
}

.model-size-text {
  font-size: 10.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-muted);
}

.action-buttons-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.delete-btn {
  padding: 4px 8px;
  font-size: 11px;
  border-radius: 5px;
  background: transparent;
  color: var(--text-muted);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}

.delete-btn:hover {
  color: var(--accent-red);
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.2);
}

.action-btn {
  padding: 5px 14px;
  font-size: 11.5px;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: all 0.15s ease;
}

.load-btn {
  background: var(--accent-emerald);
  color: #0b0f17;
  font-weight: 600;
  border: none;
}

.load-btn:hover:not(:disabled) {
  opacity: 0.92;
}

.unload-btn {
  background: transparent;
  color: var(--accent-red);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.unload-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.08);
}

.download-btn {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}

.download-btn:hover:not(:disabled) {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border-color: var(--text-muted);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.download-icon {
  font-size: 11px;
  font-weight: bold;
}

.btn-spinner {
  width: 11px;
  height: 11px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
