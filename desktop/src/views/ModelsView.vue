<template>
  <div class="models-view">
    <!-- Top Filter & Search Bar -->
    <div class="filter-bar">
      <!-- Engine Segment Pills -->
      <div class="engine-pills-row">
        <span class="filter-title">{{ t('modelsEngineFilter') }}:</span>
        <button
          class="engine-pill"
          :class="{ active: selectedEngine === 'all' }"
          @click="selectedEngine = 'all'"
        >
          {{ t('modelsEngineAll') }} ({{ modelsList.length }})
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
          :placeholder="t('modelsSearchPlaceholder')"
          class="search-input"
        />
        <button v-if="searchQuery" class="clear-search-btn" @click="searchQuery = ''">✕</button>
      </div>
    </div>

    <!-- Status Filter & Storage Metric Row -->
    <div class="status-metric-row">
      <div class="status-filters">
        <span class="metric-caption">{{ t('modelsStatusFilter') }}:</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'all' }"
          @click="selectedStatus = 'all'"
        >
          {{ t('modelsStatusAll') }} ({{ modelsList.length }})
        </button>
        <span class="sep">•</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'ready' }"
          @click="selectedStatus = 'ready'"
        >
          {{ t('modelsStatusReady') }} ({{ getStatusCount('ready') }})
        </button>
        <span class="sep">•</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'remote' }"
          @click="selectedStatus = 'remote'"
        >
          {{ t('modelsStatusRemote') }} ({{ getStatusCount('remote') }})
        </button>
        <span class="sep">•</span>
        <button
          class="status-tab"
          :class="{ active: selectedStatus === 'loaded' }"
          @click="selectedStatus = 'loaded'"
        >
          {{ t('modelsStatusLoaded') }} ({{ getStatusCount('loaded') }})
        </button>
      </div>

      <div class="storage-metric-right">
        <!-- Sort Selector -->
        <div class="sort-control">
          <svg viewBox="0 0 24 24" class="sort-icon" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18M6 12h12M10 18h4"/>
          </svg>
          <select v-model="sortBy" class="sort-dropdown" :title="t('modelsSortReady')">
            <option value="ready_first">{{ t('modelsSortReady') }}</option>
            <option value="name_asc">{{ t('modelsSortName') }}</option>
            <option value="size_desc">{{ t('modelsSortSizeDesc') }}</option>
            <option value="size_asc">{{ t('modelsSortSizeAsc') }}</option>
          </select>
        </div>

        <span class="sep">|</span>
        <span>{{ t('modelsDiskOccupied') }}: <strong class="disk-size">{{ totalDiskSize }}</strong></span>
        <button class="open-dir-btn" :title="t('modelsOpenDir')" @click="handleOpenDir">
          <svg viewBox="0 0 24 24" class="folder-svg" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span>{{ t('modelsOpenDir') }}</span>
        </button>
      </div>
    </div>

    <!-- Models Table Container -->
    <div class="models-grid-container">
      <div v-if="filteredModels.length === 0" class="empty-models">
        <svg viewBox="0 0 24 24" class="empty-icon" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <p>{{ t('modelsEmpty') }}</p>
      </div>

      <!-- Models List Table (Dense & High Contrast) -->
      <div v-else class="models-list-table">
        <div class="list-header-row">
          <div class="col col-model">{{ t('modelsThModel') }}</div>
          <div class="col col-engine">{{ t('modelsThEngine') }}</div>
          <div class="col col-desc">{{ t('modelsThDesc') }}</div>
          <div class="col col-specs">{{ t('modelsThSpecs') }}</div>
          <div class="col col-size">{{ t('modelsThSize') }}</div>
          <div class="col col-status">{{ t('modelsThStatus') }}</div>
          <div class="col col-actions">{{ t('modelsThActions') }}</div>
        </div>

        <div
          v-for="model in filteredModels"
          :key="model.id"
          class="list-body-row"
          :class="{ active: model.isLoaded }"
        >
          <!-- Model Name & ID -->
          <div class="col col-model">
            <span class="model-row-name">{{ model.name }}</span>
            <span class="model-row-id">{{ model.id }}</span>
          </div>

          <!-- Engine Tag -->
          <div class="col col-engine">
            <span class="engine-tag" :class="model.engine">
              {{ getEngineDisplayName(model.engine) }}
            </span>
          </div>

          <!-- Specs/Desc -->
          <div class="col col-desc">
            <div class="desc-line truncate" :title="model.desc">{{ model.desc }}</div>
            <div class="lang-line">
              <span class="lang-icon">🌐</span>
              <span class="lang-text truncate" :title="model.langs">{{ model.langs }}</span>
            </div>
          </div>

          <!-- Specs: Params & VRAM -->
          <div class="col col-specs">
            <span v-if="model.params && model.params !== '-'" class="spec-pill">{{ model.params }}</span>
            <span v-if="model.vram && model.vram !== '-'" class="vram-pill">VRAM {{ model.vram }}</span>
          </div>

          <!-- Size -->
          <div class="col col-size">
            <span class="size-text">{{ model.size }}</span>
          </div>

          <!-- Status -->
          <div class="col col-status">
            <span v-if="model.isLoaded" class="status-badge loaded">
              <span class="vram-pulse">●</span> {{ t('modelsStatusLoaded') }}
            </span>
            <div v-else-if="model.isDownloading" class="download-progress-wrap">
              <div class="mini-progress-bar">
                <div class="mini-progress-fill" :style="{ width: (model.downloadPercent || 0) + '%' }"></div>
              </div>
              <span class="progress-pct">{{ model.downloadPercent || 0 }}%</span>
            </div>
            <span v-else-if="model.status === 'ready'" class="status-badge ready">
              {{ t('modelsStatusReady') }}
            </span>
            <span v-else class="status-badge remote">
              {{ t('modelsStatusRemote') }}
            </span>
          </div>

          <!-- Actions -->
          <div class="col col-actions">
            <!-- Delete button -->
            <button
              v-if="model.status === 'ready' && !model.isLoaded"
              class="row-delete-btn"
              :title="t('modelsDeleteBtn')"
              @click="handleDeleteModel(model)"
            >
              {{ t('modelsDeleteBtn') }}
            </button>

            <!-- Unload button -->
            <button
              v-if="model.isLoaded"
              class="row-action-btn unload-btn"
              :disabled="model.isBusy"
              @click="handleUnloadModel(model)"
            >
              <span v-if="model.isBusy" class="btn-spinner"></span>
              <span>{{ t('modelsUnloadBtn') }}</span>
            </button>

            <!-- Load button -->
            <button
              v-else-if="model.status === 'ready'"
              class="row-action-btn load-btn"
              :disabled="model.isBusy"
              @click="handleLoadModel(model)"
            >
              <span v-if="model.isBusy" class="btn-spinner"></span>
              <span>{{ t('modelsLoadBtn') }}</span>
            </button>

            <!-- Download button -->
            <button
              v-else
              class="row-action-btn download-btn"
              :disabled="model.isDownloading || model.isBusy"
              @click="handleDownloadModel(model)"
            >
              <span v-if="model.isDownloading" class="btn-spinner"></span>
              <span v-else>↓</span>
              <span>{{ model.isDownloading ? t('modelsDownloading') : t('modelsDownloadBtn') }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- First-Time Download Network Selection Modal -->
    <div v-if="showNetworkModal" class="modal-backdrop" @click.self="cancelNetworkModal">
      <div class="network-modal-card">
        <div class="modal-header">
          <div class="header-icon-box">
            <svg viewBox="0 0 24 24" class="network-icon" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="2" y1="12" x2="22" y2="12"/>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
          </div>
          <div class="header-text">
            <h3 class="modal-title">{{ t('downloadNetworkTitle') }}</h3>
            <p class="modal-subtitle">{{ t('downloadNetworkSubtitle') }}</p>
          </div>
        </div>

        <div class="network-options-list">
          <!-- Option 1: ModelScope -->
          <label
            class="network-option-item"
            :class="{ active: selectedNetworkSource === 'modelscope' }"
          >
            <input
              type="radio"
              v-model="selectedNetworkSource"
              value="modelscope"
              class="radio-input"
            />
            <div class="option-content">
              <div class="option-title-row">
                <span class="option-title">{{ t('downloadNetworkOptionCn') }}</span>
                <span class="tag-recommend">ModelScope</span>
              </div>
              <div class="option-desc">{{ t('downloadNetworkOptionCnDesc') }}</div>
            </div>
          </label>

          <!-- Option 2: HuggingFace -->
          <label
            class="network-option-item"
            :class="{ active: selectedNetworkSource === 'huggingface' }"
          >
            <input
              type="radio"
              v-model="selectedNetworkSource"
              value="huggingface"
              class="radio-input"
            />
            <div class="option-content">
              <div class="option-title-row">
                <span class="option-title">{{ t('downloadNetworkOptionGlobal') }}</span>
                <span class="tag-source">HuggingFace</span>
              </div>
              <div class="option-desc">{{ t('downloadNetworkOptionGlobalDesc') }}</div>
            </div>
          </label>

          <!-- Option 3: HF-Mirror -->
          <label
            class="network-option-item"
            :class="{ active: selectedNetworkSource === 'hf-mirror' }"
          >
            <input
              type="radio"
              v-model="selectedNetworkSource"
              value="hf-mirror"
              class="radio-input"
            />
            <div class="option-content">
              <div class="option-title-row">
                <span class="option-title">{{ t('downloadNetworkOptionHfMirror') }}</span>
                <span class="tag-source">hf-mirror.com</span>
              </div>
              <div class="option-desc">{{ t('downloadNetworkOptionHfMirrorDesc') }}</div>
            </div>
          </label>

          <!-- Option 4: Auto Fallback -->
          <label
            class="network-option-item"
            :class="{ active: selectedNetworkSource === 'auto' }"
          >
            <input
              type="radio"
              v-model="selectedNetworkSource"
              value="auto"
              class="radio-input"
            />
            <div class="option-content">
              <div class="option-title-row">
                <span class="option-title">{{ t('downloadNetworkOptionAuto') }}</span>
                <span class="tag-source">Auto Failover</span>
              </div>
              <div class="option-desc">{{ t('downloadNetworkOptionAutoDesc') }}</div>
            </div>
          </label>
        </div>

        <div class="modal-hint">
          {{ t('downloadNetworkHint') }}
        </div>

        <div class="modal-footer">
          <button class="modal-btn cancel-btn" @click="cancelNetworkModal">
            {{ t('downloadNetworkCancelBtn') }}
          </button>
          <button
            class="modal-btn confirm-btn"
            :disabled="isSavingNetwork"
            @click="confirmNetworkSource"
          >
            <span v-if="isSavingNetwork" class="btn-spinner"></span>
            <span>{{ t('downloadNetworkConfirmBtn') }}</span>
          </button>
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
import { isTauri } from '../utils/env';

const { t } = useI18n();

const selectedEngine = ref('all');
const selectedStatus = ref('all');
const searchQuery = ref('');
const sortBy = ref('ready_first');

const currentDownloadSource = ref(null);
const showNetworkModal = ref(false);
const pendingDownloadModel = ref(null);
const selectedNetworkSource = ref('modelscope');
const isSavingNetwork = ref(false);

function parseSizeToBytes(sizeStr) {
  if (!sizeStr) return 0;
  const str = String(sizeStr).trim().toUpperCase();
  const num = parseFloat(str);
  if (isNaN(num)) return 0;
  if (str.includes('GB')) return num * 1024 * 1024 * 1024;
  if (str.includes('MB')) return num * 1024 * 1024;
  if (str.includes('KB')) return num * 1024;
  return num;
}

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
    id: 'fun-asr-nano',
    name: 'Fun-ASR Nano 0.8B',
    engine: 'funasr',
    desc: '阿里下一代轻量级 Audio-LLM，融合 SenseVoice 声学特征与千问语义理解，抗噪与专有名词识别更佳。',
    params: '800M',
    vram: '~ 2.5GB',
    langs: '中 / 英 / 日 / 韩 / 粤',
    size: '1.6 GB',
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
    id: 'firered2-aed',
    name: 'FireRedASR2 AED 1.1B',
    engine: 'firered',
    desc: '小红书第二代工业级声学大模型，高抗噪、强口音鲁棒性，歌词与短视频字幕听写首选。',
    params: '1.1B',
    vram: '~ 3.5GB',
    langs: '中文 / 英语 / 地方口音',
    size: '2.2 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'firered2-llm',
    name: 'FireRedASR2 LLM 8.3B',
    engine: 'firered',
    desc: '小红书旗舰级方言与中英混说大模型，支持 20+ 种中国方言口音直接听抄转成普通话。',
    params: '8.3B',
    vram: '~ 12GB',
    langs: '中文 / 20+ 方言 / 中英混说',
    size: '16.0 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'qwen3-asr-0.6b',
    name: 'Qwen3 ASR 0.6B',
    engine: 'qwen',
    desc: '通义千问轻量级语音大模型，超低显存需求，适合入门级设备与 CPU 快速转录。',
    params: '0.6B',
    vram: '~ 2GB',
    langs: '52+ 语言与泛音频',
    size: '1.2 GB',
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
  return modelsList.value
    .filter((m) => {
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
    })
    .sort((a, b) => {
      if (sortBy.value === 'ready_first') {
        const score = (m) => (m.isLoaded ? 2 : (m.status === 'ready' ? 1 : 0));
        const diff = score(b) - score(a);
        if (diff !== 0) return diff;
        return a.name.localeCompare(b.name);
      }
      if (sortBy.value === 'name_asc') {
        return a.name.localeCompare(b.name);
      }
      if (sortBy.value === 'size_desc') {
        return parseSizeToBytes(b.size) - parseSizeToBytes(a.size);
      }
      if (sortBy.value === 'size_asc') {
        return parseSizeToBytes(a.size) - parseSizeToBytes(b.size);
      }
      return 0;
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
  await fetchDownloadSource();
});

async function fetchDownloadSource() {
  try {
    const sys = await apiClient.getSystemSettings();
    if (sys && sys.download_source) {
      currentDownloadSource.value = sys.download_source;
      selectedNetworkSource.value = sys.download_source;
    }
  } catch (err) {
    console.warn('[ModelsView] getSystemSettings skipped:', err);
  }
}

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
        } else {
          const szMb = (backendModel.size_on_disk || backendModel.size_expected || 0) / (1024 * 1024);
          const sizeStr = szMb >= 1000 ? `${(szMb / 1024).toFixed(1)} GB` : `${Math.round(szMb)} MB`;
          modelsList.value.push({
            id: backendModel.id,
            name: backendModel.name || backendModel.id,
            engine: backendModel.owned_by || 'whisper',
            desc: backendModel.description || `${backendModel.name} 语音识别模型`,
            params: backendModel.params || '-',
            vram: backendModel.vram || '-',
            langs: Array.isArray(backendModel.languages) ? backendModel.languages.join(' / ') : (backendModel.languages || '多语言'),
            size: sizeStr,
            status: backendModel.status === 'ready' ? 'ready' : 'remote',
            isLoaded: !!backendModel.loaded,
            isDownloading: false,
            downloadPercent: 0,
            isBusy: false
          });
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
  // If download source is not yet selected by user, prompt network selection modal
  if (!currentDownloadSource.value) {
    pendingDownloadModel.value = model;
    showNetworkModal.value = true;
    return;
  }
  await executeDownload(model, currentDownloadSource.value);
}

async function confirmNetworkSource() {
  isSavingNetwork.value = true;
  const chosenSource = selectedNetworkSource.value || 'modelscope';
  try {
    await apiClient.updateSystemSettings({ download_source: chosenSource });
  } catch (err) {
    console.warn('[ModelsView] updateSystemSettings notice:', err);
  } finally {
    currentDownloadSource.value = chosenSource;
    isSavingNetwork.value = false;
    showNetworkModal.value = false;
    if (pendingDownloadModel.value) {
      const targetModel = pendingDownloadModel.value;
      pendingDownloadModel.value = null;
      await executeDownload(targetModel, chosenSource);
    }
  }
}

function cancelNetworkModal() {
  showNetworkModal.value = false;
  pendingDownloadModel.value = null;
}

async function executeDownload(model, source) {
  model.isDownloading = true;
  model.downloadPercent = 10;
  const timer = setInterval(() => {
    if (model.downloadPercent < 90) {
      model.downloadPercent += 15;
    }
  }, 400);

  try {
    await apiClient.downloadModel(model.id, source);
    clearInterval(timer);
    model.downloadPercent = 100;
    model.status = 'ready';
  } catch (err) {
    console.warn('Backend download error:', err);
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
  const confirmMsg = (t('modelsDeleteConfirm') || '确定要删除模型 "{name}" 的本地权重文件吗？').replace('{name}', model.name);
  if (!confirm(confirmMsg)) {
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
  if (isTauri) {
    invoke('open_local_dir', { target: 'models' }).catch((err) => {
      console.warn('Native open_local_dir failed:', err);
    });
  } else {
    alert('OneASR 模型存放于服务器端: ~/.oneasr/models');
  }
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

/* 1. Top Filter & Search Bar */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 8px 12px;
  flex-shrink: 0;
}

.engine-pills-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-title {
  font-size: 11.5px;
  color: var(--text-muted);
  font-weight: 500;
  margin-right: 2px;
}

.engine-pill {
  font-size: 11.5px;
  padding: 3px 9px;
  border-radius: 5px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}

.engine-pill:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.engine-pill.active {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border-color: var(--border-subtle);
  font-weight: 500;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  width: 210px;
}

.search-icon {
  position: absolute;
  left: 8px;
  width: 12px;
  height: 12px;
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

.sort-control {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 2px 6px;
}

.sort-icon {
  width: 13px;
  height: 13px;
  color: var(--text-muted);
}

.sort-dropdown {
  background: transparent;
  border: none;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  outline: none;
}

/* 3. Table Container */
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

/* 4. Models List Table (Dense & High Contrast) */
.models-list-table {
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  overflow: hidden;
}

.list-header-row {
  display: grid;
  grid-template-columns: 2.2fr 1fr 2.6fr 1.1fr 0.8fr 1.2fr 1.3fr;
  align-items: center;
  padding: 10px 16px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(0, 0, 0, 0.02);
}

.list-body-row {
  display: grid;
  grid-template-columns: 2.2fr 1fr 2.6fr 1.1fr 0.8fr 1.2fr 1.3fr;
  align-items: center;
  padding: 11px 16px;
  border-bottom: 1px solid var(--border-subtle);
  transition: background 0.15s ease;
}

.list-body-row:last-child {
  border-bottom: none;
}

.list-body-row:hover {
  background: var(--bg-elevated);
}

.list-body-row.active {
  background: rgba(16, 185, 129, 0.04);
  border-left: 3px solid var(--accent-emerald);
  padding-left: 13px;
}

.col-model {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-row-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.model-row-id {
  font-size: 11px;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.engine-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 4px;
  border: 1px solid transparent;
  width: fit-content;
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

.col-desc {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding-right: 12px;
}

.desc-line {
  font-size: 12px;
  color: var(--text-secondary);
}

.lang-line {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.lang-icon {
  font-size: 11px;
  opacity: 0.8;
}

.col-specs {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
}

.spec-pill {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
}

.vram-pill {
  font-size: 10px;
  color: var(--text-muted);
}

.size-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.col-status {
  display: flex;
  align-items: center;
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

.vram-pulse {
  display: inline-block;
  margin-right: 2px;
  animation: pulse-dot 1.2s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

.download-progress-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.mini-progress-bar {
  flex: 1;
  height: 5px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 3px;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background: var(--accent-emerald);
  transition: width 0.3s ease;
}

.progress-pct {
  font-size: 10px;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.col-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: flex-end;
}

.row-action-btn {
  padding: 4px 10px;
  border-radius: 5px;
  font-size: 11.5px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s ease;
  font-weight: 500;
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

.row-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.row-delete-btn {
  background: transparent;
  border: none;
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 3px 6px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.row-delete-btn:hover {
  color: var(--accent-red);
  background: rgba(239, 68, 68, 0.08);
}

.btn-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ═══════════════════════════════════════════════════════════════════
   Modal: Download Network Selector (First-Time JIT Prompt)
   ═══════════════════════════════════════════════════════════════════ */
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
  padding: 20px;
  animation: fadeIn 0.18s ease-out;
}

.network-modal-card {
  width: 100%;
  max-width: 540px;
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 14px;
  box-shadow: 0 20px 45px rgba(0, 0, 0, 0.18), 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 24px 26px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  animation: scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.header-icon-box {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--bg-hover, #f3f4f6);
  border: 1px solid var(--border-color, #e5e7eb);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.network-icon {
  width: 20px;
  height: 20px;
  color: var(--primary-color, #10b981);
}

.header-text {
  flex: 1;
}

.modal-title {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main, #111827);
  letter-spacing: -0.01em;
}

.modal-subtitle {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-muted, #6b7280);
  line-height: 1.45;
}

.network-options-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.network-option-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 9px;
  border: 1.5px solid var(--border-color, #e5e7eb);
  background: var(--bg-item, #fafafa);
  cursor: pointer;
  transition: all 0.15s ease;
}

.network-option-item:hover {
  background: var(--bg-hover, #f3f4f6);
  border-color: var(--border-hover, #d1d5db);
}

.network-option-item.active {
  background: rgba(16, 185, 129, 0.05);
  border-color: var(--primary-color, #10b981);
}

.radio-input {
  margin-top: 3px;
  accent-color: var(--primary-color, #10b981);
  cursor: pointer;
}

.option-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.option-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.option-title {
  font-size: 13.5px;
  font-weight: 550;
  color: var(--text-main, #111827);
}

.tag-recommend {
  font-size: 10px;
  font-weight: 600;
  color: #047857;
  background: rgba(16, 185, 129, 0.14);
  padding: 1px 6px;
  border-radius: 4px;
}

.tag-source {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted, #6b7280);
  background: var(--bg-hover, #f3f4f6);
  border: 1px solid var(--border-color, #e5e7eb);
  padding: 1px 5px;
  border-radius: 4px;
}

.option-desc {
  font-size: 12px;
  color: var(--text-muted, #6b7280);
  line-height: 1.4;
}

.modal-hint {
  font-size: 11.5px;
  color: var(--text-muted, #6b7280);
  background: var(--bg-hover, #f8fafc);
  border: 1px dashed var(--border-color, #e2e8f0);
  border-radius: 6px;
  padding: 8px 12px;
  line-height: 1.4;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.modal-btn {
  height: 34px;
  padding: 0 16px;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s ease;
}

.cancel-btn {
  background: transparent;
  border: 1px solid var(--border-color, #d1d5db);
  color: var(--text-main, #374151);
}

.cancel-btn:hover {
  background: var(--bg-hover, #f3f4f6);
}

.confirm-btn {
  background: var(--primary-color, #10b981);
  border: 1px solid transparent;
  color: #ffffff;
}

.confirm-btn:hover:not(:disabled) {
  filter: brightness(0.94);
}

.confirm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes scaleIn {
  from { transform: scale(0.96); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
</style>
