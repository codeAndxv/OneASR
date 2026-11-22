<template>
  <div class="models-view">
    <!-- 1. Top Filters Row (Filters Left, Search Right) -->
    <div class="models-toolbar-row filters-row">
      <!-- Left: Dropdown Filters (Engine, Status, Mode) -->
      <div class="filters-group-left">
        <!-- Engine Dropdown -->
        <div class="filter-select-control" :class="{ 'filter-active': selectedEngine !== 'all' }">
          <svg viewBox="0 0 24 24" class="filter-select-icon" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
          <select v-model="selectedEngine" class="filter-select-dropdown" :title="t('modelsEngineFilter')">
            <option value="all">{{ t('modelsEngineFilter') }}: {{ t('modelsEngineAll') }} ({{ modelsList.length }})</option>
            <option v-for="eng in engineOptions" :key="eng.id" :value="eng.id">
              {{ eng.name }} ({{ getEngineCount(eng.id) }})
            </option>
          </select>
        </div>

        <!-- Status Dropdown Filter -->
        <div class="filter-select-control" :class="{ 'filter-active': selectedStatus !== 'all' }">
          <svg viewBox="0 0 24 24" class="filter-select-icon" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
          </svg>
          <select v-model="selectedStatus" class="filter-select-dropdown" :title="t('modelsStatusFilter')">
            <option value="all">{{ t('modelsStatusFilter') }}: {{ t('modelsStatusAll') }}</option>
            <option value="ready">{{ t('modelsStatusFilter') }}: {{ t('modelsStatusReady') }} ({{ getStatusCount('ready') }})</option>
            <option value="remote">{{ t('modelsStatusFilter') }}: {{ t('modelsStatusRemote') }} ({{ getStatusCount('remote') }})</option>
            <option value="loaded">{{ t('modelsStatusFilter') }}: {{ t('modelsStatusLoaded') }} ({{ getStatusCount('loaded') }})</option>
          </select>
        </div>

        <!-- Mode Dropdown Filter -->
        <div class="filter-select-control" :class="{ 'filter-active': selectedMode !== 'all' }">
          <svg viewBox="0 0 24 24" class="filter-select-icon" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
          </svg>
          <select v-model="selectedMode" class="filter-select-dropdown" :title="t('modelsModeFilter')">
            <option value="all">{{ t('modelsModeFilter') }}: {{ t('modelsModeAll') }}</option>
            <option value="realtime">{{ t('modelsModeFilter') }}: {{ t('modelsModeRealtime') }} ({{ getModeCount('realtime') }})</option>
            <option value="offline">{{ t('modelsModeFilter') }}: {{ t('modelsModeOffline') }} ({{ getModeCount('offline') }})</option>
          </select>
        </div>
      </div>

      <!-- Right: Search Box -->
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

    <!-- 2. Actions & Metrics Row (Summary Left, Action Buttons Right) -->
    <div class="models-toolbar-row actions-row">
      <!-- Left: Summary Metrics -->
      <div class="metric-summary-left">
        <span class="summary-text">{{ t('modelsTotalCountPrefix') }} <strong class="summary-num">{{ filteredModels.length }}</strong> {{ t('modelsTotalCountSuffix') }}</span>
        <span class="sep">•</span>
        <span class="storage-text">{{ t('modelsDiskOccupied') }}: <strong class="disk-size">{{ totalDiskSize }}</strong></span>
      </div>

      <!-- Right: Action Buttons (Solid width, never wrap/squeeze) -->
      <div class="actions-group-right">
        <button class="open-dir-btn" :title="t('modelsImportCustom')" @click="showImportModal = true">
          <svg viewBox="0 0 24 24" class="folder-svg" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <span>{{ t('modelsImportCustom') }}</span>
        </button>

        <button
          class="refresh-btn"
          :class="{ refreshing: isRefreshing }"
          :disabled="isRefreshing"
          :title="t('modelsRefreshTooltip')"
          @click="handleManualRefresh"
        >
          <svg viewBox="0 0 24 24" class="refresh-svg" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
          </svg>
          <span>{{ t('modelsRefreshBtn') }}</span>
        </button>

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

      <!-- Models List Table (5-column Compact & Informative Layout) -->
      <div v-else class="models-list-table">
        <div class="list-header-row">
          <div
            class="col col-model sortable-header"
            :class="{ active: sortKey === 'name' }"
            :title="t('modelsSortName')"
            @click="handleHeaderSort('name')"
          >
            <span class="header-label">{{ t('modelsThModel') }}</span>
            <span class="sort-indicator">
              <span class="sort-arrow arrow-up" :class="{ highlighted: sortKey === 'name' && sortOrder === 'asc' }">▲</span>
              <span class="sort-arrow arrow-down" :class="{ highlighted: sortKey === 'name' && sortOrder === 'desc' }">▼</span>
            </span>
          </div>
          <div class="col col-langs">{{ t('modelsThLangs') }}</div>
          <div class="col col-desc">{{ t('modelsThDesc') }}</div>
          <div
            class="col col-params sortable-header"
            :class="{ active: sortKey === 'params' }"
            :title="t('modelsSortParamsDesc')"
            @click="handleHeaderSort('params')"
          >
            <span class="header-label">{{ t('modelsThParams') }}</span>
            <span class="sort-indicator">
              <span class="sort-arrow arrow-up" :class="{ highlighted: sortKey === 'params' && sortOrder === 'asc' }">▲</span>
              <span class="sort-arrow arrow-down" :class="{ highlighted: sortKey === 'params' && sortOrder === 'desc' }">▼</span>
            </span>
          </div>
          <div
            class="col col-size sortable-header"
            :class="{ active: sortKey === 'size' }"
            :title="t('modelsSortSizeDesc')"
            @click="handleHeaderSort('size')"
          >
            <span class="header-label">{{ t('modelsThSize') }}</span>
            <span class="sort-indicator">
              <span class="sort-arrow arrow-up" :class="{ highlighted: sortKey === 'size' && sortOrder === 'asc' }">▲</span>
              <span class="sort-arrow arrow-down" :class="{ highlighted: sortKey === 'size' && sortOrder === 'desc' }">▼</span>
            </span>
          </div>
          <div
            class="col col-status-actions sortable-header"
            :class="{ active: sortKey === 'ready' }"
            :title="t('modelsSortReady')"
            @click="handleHeaderSort('ready')"
          >
            <span class="header-label">{{ t('modelsThStatusActions') }}</span>
            <span class="sort-indicator">
              <span class="sort-arrow arrow-up" :class="{ highlighted: sortKey === 'ready' && sortOrder === 'asc' }">▲</span>
              <span class="sort-arrow arrow-down" :class="{ highlighted: sortKey === 'ready' && sortOrder === 'desc' }">▼</span>
            </span>
          </div>
        </div>

        <div
          v-for="model in filteredModels"
          :key="model.id"
          class="list-body-row"
          :class="{ active: model.isLoaded }"
        >
          <!-- 1. Model Name, Engine & ID (3 Lines) -->
          <div class="col col-model">
            <div class="model-title-line">
              <span class="model-row-name">{{ cleanModelName(model.name) }}</span>
              <span v-if="isRealtimeModel(model)" class="stream-pill">{{ t('modelsModeRealtime') }}</span>
              <span v-if="model.isCustom" class="custom-model-badge">{{ t('modelsCustomBadge') }}</span>
            </div>
            <div class="model-engine-line">
              <span class="model-engine-label">{{ getEngineDisplayName(model.engine) }}</span>
            </div>
            <div class="model-id-line" :title="model.id">
              <span class="model-row-id">{{ model.id }}</span>
            </div>
          </div>

          <!-- 2. Supported Languages (Glanceable Slash-Joined Dropdown) -->
          <div class="col col-langs">
            <div class="lang-select-wrap">
              <select class="lang-cell-dropdown" :title="getModelLangsFullTooltip(model, locale)">
                <!-- 多语言场景 (> 1)：第一项作为合并概览，下方展开各语种详情 -->
                <template v-if="getModelLanguageOptions(model, locale).length > 1">
                  <option value="" disabled selected hidden>{{ getModelLangs(model, locale) }}</option>
                  <option
                    v-for="(langItem, idx) in getModelLanguageOptions(model, locale)"
                    :key="idx"
                    disabled
                  >
                    {{ langItem }}
                  </option>
                </template>
                <!-- 单语言场景 (<= 1)：只渲染一行独立语种，彻底避免下拉重复 -->
                <template v-else>
                  <option disabled selected>{{ getModelLanguageOptions(model, locale)[0] || getModelLangs(model, locale) }}</option>
                </template>
              </select>
            </div>
          </div>

          <!-- 3. Description (Spacious & Natural 2-line wrap) -->
          <div class="col col-desc">
            <div class="desc-text" :title="getModelDesc(model, locale)">{{ getModelDesc(model, locale) }}</div>
          </div>

          <!-- 4. Specs (Params & VRAM) -->
          <div class="col col-params">
            <div class="params-primary">
              <span v-if="model.params && model.params !== '-'" class="param-num">{{ model.params }}</span>
              <span v-else class="param-num text-muted">-</span>
            </div>
            <div class="params-secondary" v-if="model.vram && model.vram !== '-'">
              <span class="vram-text">VRAM {{ model.vram }}</span>
            </div>
          </div>

          <!-- 5. Footprint (Size on Disk / Download) -->
          <div class="col col-size">
            <span class="size-text">{{ model.size }}</span>
          </div>

          <!-- 5. Status & Actions -->
          <div class="col col-status-actions">
            <div class="status-box">
              <span v-if="model.isLoaded" class="status-indicator in-vram" :title="t('modelsStatusLoaded')">
                <span class="status-dot green pulse"></span>
                <span class="status-text">{{ t('modelsStatusLoaded') }}</span>
              </span>
              <div v-else-if="model.isDownloading" class="download-progress-wrap">
                <div class="mini-progress-bar">
                  <div class="mini-progress-fill" :style="{ width: (model.downloadPercent || 0) + '%' }"></div>
                </div>
                <span class="progress-pct">{{ model.downloadPercent || 0 }}%</span>
              </div>
              <span v-else-if="model.status === 'ready'" class="status-indicator ready" :title="t('modelsStatusReady')">
                <span class="status-dot ready"></span>
                <span class="status-text">{{ t('modelsStatusReady') }}</span>
              </span>
              <span v-else class="status-indicator remote" :title="t('modelsStatusRemote')">
                <span class="status-dot hollow"></span>
                <span class="status-text">{{ t('modelsStatusRemote') }}</span>
              </span>
            </div>

            <div class="actions-box">
              <!-- Delete or Unregister button -->
              <button
                v-if="model.status === 'ready' && !model.isLoaded"
                class="row-delete-btn"
                :class="{ 'row-unreg-btn': model.isCustom }"
                :title="model.isCustom ? t('modelsUnregisterBtn') : t('modelsDeleteBtn')"
                @click="model.isCustom ? handleUnregisterModel(model) : handleDeleteModel(model)"
              >
                {{ model.isCustom ? t('modelsUnregisterBtn') : t('modelsDeleteBtn') }}
              </button>
              <button
                v-else-if="model.isCustom && !model.isLoaded"
                class="row-delete-btn row-unreg-btn"
                :title="t('modelsUnregisterBtn')"
                @click="handleUnregisterModel(model)"
              >
                {{ t('modelsUnregisterBtn') }}
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
    </div>

    <!-- Import Custom Model Modal -->
    <div v-if="showImportModal" class="modal-backdrop" @click.self="cancelImportModal">
      <div class="network-modal-card import-modal-card">
        <div class="modal-header">
          <div class="header-icon-box">
            <svg viewBox="0 0 24 24" class="network-icon" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <div class="header-text">
            <h3 class="modal-title">{{ t('modelsImportModalTitle') }}</h3>
            <p class="modal-subtitle">显式注册本地 ASR 权重目录，无需后台盲猜扫描</p>
          </div>
        </div>

        <div class="import-form">
          <div class="form-group">
            <label class="form-label">{{ t('modelsImportIdLabel') }} <span class="required">*</span></label>
            <input
              v-model="importForm.id"
              type="text"
              class="form-input"
              :placeholder="t('modelsImportIdPlaceholder')"
              :disabled="isImporting"
            />
          </div>

          <div class="form-group">
            <label class="form-label">{{ t('modelsImportNameLabel') }}</label>
            <input
              v-model="importForm.name"
              type="text"
              class="form-input"
              :placeholder="t('modelsImportNamePlaceholder')"
              :disabled="isImporting"
            />
          </div>

          <div class="form-group">
            <label class="form-label">{{ t('modelsImportDriverLabel') }} <span class="required">*</span></label>
            <select v-model="importForm.driver" class="form-select" :disabled="isImporting">
              <option value="xasr">Sherpa-ONNX (X-ASR 流式识别 / chunk 模型)</option>
              <option value="funasr">FunASR (SenseVoice / Paraformer)</option>
              <option value="whisper">Faster-Whisper (Whisper-large / turbo)</option>
              <option value="firered">FireRedASR (端到端 ASR)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">{{ t('modelsImportPathLabel') }} <span class="required">*</span></label>
            <input
              v-model="importForm.model_path"
              type="text"
              class="form-input"
              :placeholder="t('modelsImportPathPlaceholder')"
              :disabled="isImporting"
            />
          </div>

          <div v-if="importError" class="import-error-banner">
            <svg viewBox="0 0 24 24" class="error-svg" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{{ importError }}</span>
          </div>
        </div>

        <div class="modal-footer">
          <button class="modal-btn cancel-btn" :disabled="isImporting" @click="cancelImportModal">
            {{ t('cancel') || '取消' }}
          </button>
          <button class="modal-btn confirm-btn" :disabled="isImporting" @click="handleImportSubmit">
            <span v-if="isImporting" class="btn-spinner"></span>
            <span>{{ t('modelsImportSubmit') }}</span>
          </button>
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { useI18n } from '../i18n';
import { getModelDesc, getModelLangs, getModelLangsFullTooltip, getModelLanguageOptions, WHISPER_MAJOR_LANGS } from '../i18n/models';
import { apiClient } from '../api/client';
import { isTauri } from '../utils/env';

const { locale, t } = useI18n();

const selectedEngine = ref('all');
const selectedStatus = ref('all');
const selectedMode = ref('all');
const selectedLang = ref('all');
const searchQuery = ref('');
const sortKey = ref('ready'); // 'ready' | 'name' | 'size' | 'params'
const sortOrder = ref('desc'); // 'asc' | 'desc'

function handleHeaderSort(key) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortKey.value = key;
    sortOrder.value = (key === 'size' || key === 'params' || key === 'ready') ? 'desc' : 'asc';
  }
}

const isRefreshing = ref(false);

const currentDownloadSource = ref(null);
const showNetworkModal = ref(false);
const pendingDownloadModel = ref(null);
const selectedNetworkSource = ref('modelscope');
const isSavingNetwork = ref(false);

async function handleManualRefresh() {
  if (isRefreshing.value) return;
  isRefreshing.value = true;
  try {
    await fetchBackendModels();
    await fetchDownloadSource();
  } catch (err) {
    console.warn('[ModelsView] Refresh error:', err);
  } finally {
    setTimeout(() => {
      isRefreshing.value = false;
    }, 600);
  }
}

function parseParamsToNum(paramsStr) {
  if (!paramsStr || paramsStr === '-') return 0;
  const str = String(paramsStr).trim().toUpperCase();
  const num = parseFloat(str);
  if (isNaN(num)) return 0;
  if (str.includes('B')) return num * 1e9;
  if (str.includes('M')) return num * 1e6;
  if (str.includes('K')) return num * 1e3;
  return num;
}

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

const props = defineProps({
  isOnline: {
    type: Boolean,
    default: false
  }
});

const engineOptions = [
  { id: 'whisper', name: 'Faster-Whisper' },
  { id: 'funasr', name: 'FunASR' },
  { id: 'firered', name: 'FireRed ASR' },
  { id: 'qwen', name: 'Qwen ASR' },
  { id: 'xasr', name: 'Sherpa-ONNX' }
];

const modelsList = ref([
  // 1. FunASR (3 models)
  {
    id: 'sensevoice-small',
    name: 'SenseVoice Small',
    engine: 'funasr',
    desc: '超极速端到端语音大模型，首字延迟 <150ms，原生支持中、英、日、韩、粤多语言与情感声音检测。',
    params: '50M',
    vram: '< 1GB',
    rawLanguages: ['zh', 'en', 'yue', 'ja', 'ko'],
    langs: '中 / 英 / 日 / 韩 / 粤',
    size: '480 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'paraformer-zh',
    name: 'Paraformer Large Chinese',
    engine: 'funasr',
    desc: '阿里达摩院工业级中文语音识别基座，配备专用 VAD 语音活动检测和 Punc 标点恢复模型。',
    params: '220M',
    vram: '~ 2GB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
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
    rawLanguages: ['zh', 'en', 'yue', 'ja', 'ko'],
    langs: '中 / 英 / 日 / 韩 / 粤',
    size: '1.6 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },

  // 2. Faster-Whisper (16 models)
  {
    id: 'whisper-large-v3-turbo',
    name: 'Faster-Whisper Large V3 Turbo',
    engine: 'whisper',
    desc: 'OpenAI 官方极致优化蒸馏版，CTranslate2 加速，转写准确率极高，速度较原版提升 8 倍，最适合会议长录音与播客字幕。',
    params: '809M',
    vram: '~ 3.5GB',
    rawLanguages: WHISPER_MAJOR_LANGS,
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
    rawLanguages: WHISPER_MAJOR_LANGS,
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
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '145 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-tiny',
    name: 'Faster-Whisper Tiny',
    engine: 'whisper',
    desc: '超极速入门级多语言模型 (~75MB)，低功耗设备毫秒级响应。',
    params: '39M',
    vram: '< 300MB',
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '75 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-medium',
    name: 'Faster-Whisper Medium',
    engine: 'whisper',
    desc: '高精度多语言转写基准模型 (~1.4GB)，音视频听抄与播客双语字幕精准度极佳。',
    params: '769M',
    vram: '~ 3.2GB',
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '1.4 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-large-v1',
    name: 'Faster-Whisper Large V1',
    engine: 'whisper',
    desc: 'Whisper 旗舰第一代全球多语言全量模型，工业级经典基座。',
    params: '1550M',
    vram: '~ 4.5GB',
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '3.1 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-large-v2',
    name: 'Faster-Whisper Large V2',
    engine: 'whisper',
    desc: 'Whisper 旗舰第二代全球多语言全量模型，增强多语言抗噪泛化。',
    params: '1550M',
    vram: '~ 4.5GB',
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '3.1 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-large-v3',
    name: 'Faster-Whisper Large V3',
    engine: 'whisper',
    desc: 'Whisper 旗舰第三代最高精度模型，升级 128 Mel 频带，全球语种识别率业界标杆。',
    params: '1550M',
    vram: '~ 4.5GB',
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '3.1 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-tiny-en',
    name: 'Faster-Whisper Tiny (EN)',
    engine: 'whisper',
    desc: '极速英文专用微型模型 (~75MB)，低延迟轻量英文转录。',
    params: '39M',
    vram: '< 300MB',
    rawLanguages: ['en'],
    langs: '英语 (en)',
    size: '75 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-base-en',
    name: 'Faster-Whisper Base (EN)',
    engine: 'whisper',
    desc: '轻量英文专用模型 (~145MB)，低资源占用与高吞吐。',
    params: '74M',
    vram: '< 500MB',
    rawLanguages: ['en'],
    langs: '英语 (en)',
    size: '145 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-small-en',
    name: 'Faster-Whisper Small (EN)',
    engine: 'whisper',
    desc: '高准确度英文专用模型 (~480MB)，适合日常英文会议与影音。',
    params: '244M',
    vram: '~ 1.2GB',
    rawLanguages: ['en'],
    langs: '英语 (en)',
    size: '480 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'whisper-medium-en',
    name: 'Faster-Whisper Medium (EN)',
    engine: 'whisper',
    desc: '专业生产级英文专用模型 (~1.4GB)，长音频高准确率解析。',
    params: '769M',
    vram: '~ 3.2GB',
    rawLanguages: ['en'],
    langs: '英语 (en)',
    size: '1.4 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'distil-whisper-small-en',
    name: 'Distil-Whisper Small (EN)',
    engine: 'whisper',
    desc: '蒸馏版英文专用模型 (~330MB)，推理速度提升 6 倍，极小精度损耗。',
    params: '166M',
    vram: '~ 1GB',
    rawLanguages: ['en'],
    langs: '英语 (en)',
    size: '330 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'distil-whisper-medium-en',
    name: 'Distil-Whisper Medium (EN)',
    engine: 'whisper',
    desc: '蒸馏版英文进阶模型 (~790MB)，兼顾极速吞吐与高质量英文字幕。',
    params: '394M',
    vram: '~ 1.8GB',
    rawLanguages: ['en'],
    langs: '英语 (en)',
    size: '790 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'distil-whisper-large-v2',
    name: 'Distil-Whisper Large V2',
    engine: 'whisper',
    desc: '基于 Large V2 的蒸馏多语言大模型 (~1.5GB)，高吞吐并发推理首选。',
    params: '756M',
    vram: '~ 3.2GB',
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '1.5 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'distil-whisper-large-v3',
    name: 'Distil-Whisper Large V3',
    engine: 'whisper',
    desc: '基于 Large V3 的最新蒸馏多语言旗舰模型 (~1.5GB)，极致速度与顶级准确率。',
    params: '756M',
    vram: '~ 3.2GB',
    rawLanguages: WHISPER_MAJOR_LANGS,
    langs: '99+ 全球主流语言',
    size: '1.5 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },

  // 3. FireRed ASR (3 models)
  {
    id: 'firered-asr',
    name: 'FireRed ASR Large',
    engine: 'firered',
    desc: '基于 sherpa-onnx 优化的高精度中英双语端到端 ASR 模型，低显存消耗。',
    params: '1.1B',
    vram: '~ 3GB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
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
    desc: '小红书工业级 AED 语音大模型，针对嘈杂背景、歌词、重口音特别增强。',
    params: '1.1B',
    vram: '~ 4GB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
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
    desc: '小红书旗舰级 8.3B Encoder-LLM 语音大模型，深度覆盖 20+ 种地方方言与混合夹杂。',
    params: '8.3B',
    vram: '> 16GB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
    size: '16.0 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },

  // 4. Qwen ASR (2 models)
  {
    id: 'qwen3-asr-0.6b',
    name: 'Qwen3 ASR 0.6B',
    engine: 'qwen',
    desc: '通义千问最新紧凑型 0.6B 语音模型，资源占用极小，响应敏捷。',
    params: '600M',
    vram: '~ 2GB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
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
    desc: '通义千问端到端多模态语音大模型，具备复杂的语音理解、音频问答与强制时间对齐能力。',
    params: '1.7B',
    vram: '~ 6GB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
    size: '3.4 GB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },

  // 5. Sherpa-ONNX (4 models)
  {
    id: 'xasr-zh-en-160ms',
    name: 'X-ASR 160ms (Fast)',
    engine: 'xasr',
    desc: '基于 Sherpa-ONNX 的超低延迟 160ms 双语流式识别，极低 CPU 占用与零依赖，适合实时会议字幕。',
    params: '180M',
    latency: '160ms 极速',
    vram: '< 800MB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
    size: '586 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'xasr-zh-en-480ms',
    name: 'X-ASR 480ms (Balanced)',
    engine: 'xasr',
    desc: '480ms 均衡型双语流式识别，在极佳的跟手延迟下提供更稳健的句式识别精度。',
    params: '180M',
    latency: '480ms 均衡',
    vram: '< 800MB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
    size: '586 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'xasr-zh-en-960ms',
    name: 'X-ASR 960ms (Context)',
    engine: 'xasr',
    desc: '960ms 扩展上下文流式识别，抗噪能力更强，适合嘈杂环境与多人对话转写。',
    params: '180M',
    latency: '960ms 扩展',
    vram: '< 800MB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
    size: '586 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'xasr-zh-en-1920ms',
    name: 'X-ASR 1920ms (Accurate)',
    engine: 'xasr',
    desc: '1920ms 高精度流式识别，接近非流式模型的转录准确率，首字延迟约 1.9 秒。',
    params: '180M',
    latency: '1.92s 高精',
    vram: '< 800MB',
    rawLanguages: ['zh', 'en'],
    langs: '中文 / 英语',
    size: '586 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10',
    name: 'Zipformer Multilingual',
    engine: 'xasr',
    desc: '亚欧八语全能流式 Zipformer，覆盖日、俄、越、阿、泰、印尼、英、中八种主要语言，高抗噪且极低开销。',
    params: '75M',
    latency: '流式 Zipformer',
    vram: '< 500MB',
    rawLanguages: ['ja', 'ru', 'vi', 'ar', 'th', 'id', 'en', 'zh'],
    langs: '日 / 俄 / 越 / 阿 / 泰 / 印尼 / 英 / 中',
    size: '323 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en',
    name: 'Paraformer Trilingual',
    engine: 'xasr',
    desc: '中英粤三语混说流式 Paraformer，专为大湾区粤语口语及英粤夹杂实时听写调优。',
    params: '120M',
    latency: '流式 Paraformer',
    vram: '< 600MB',
    rawLanguages: ['yue', 'zh', 'en'],
    langs: '粤语 / 中 / 英',
    size: '220 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06',
    name: 'Zipformer Kroko',
    engine: 'xasr',
    desc: '西班牙语专精流式识别，超低延迟打字机体验，内存占用极小。',
    params: '65M',
    latency: '流式 Zipformer',
    vram: '< 400MB',
    rawLanguages: ['es'],
    langs: '西班牙语 (es)',
    size: '148 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'sherpa-onnx-streaming-zipformer-fr-kroko-2025-08-06',
    name: 'Zipformer Kroko',
    engine: 'xasr',
    desc: '法语专精流式识别，轻量化低延迟架构，支持麦克风连续实时转写。',
    params: '30M',
    latency: '流式 Zipformer',
    vram: '< 300MB',
    rawLanguages: ['fr'],
    langs: '法语 (fr)',
    size: '68 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'sherpa-onnx-streaming-zipformer-de-kroko-2025-08-06',
    name: 'Zipformer Kroko',
    engine: 'xasr',
    desc: '德语专精流式识别，高复合词识别精度，极低 CPU 负载。',
    params: '30M',
    latency: '流式 Zipformer',
    vram: '< 300MB',
    rawLanguages: ['de'],
    langs: '德语 (de)',
    size: '68 MB',
    status: 'remote',
    isLoaded: false,
    isDownloading: false,
    downloadPercent: 0,
    isBusy: false
  },
  {
    id: 'sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16',
    name: 'Zipformer Vosk INT8',
    engine: 'xasr',
    desc: '俄语超轻量流式识别，量化后仅 27MB，极度节省内存与网络带宽。',
    params: '25M',
    latency: '流式 Zipformer',
    vram: '< 200MB',
    rawLanguages: ['ru'],
    langs: '俄语 (ru)',
    size: '27 MB',
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
      // 3. Mode filter (Streaming vs Non-Streaming)
      if (selectedMode.value === 'realtime' && !isRealtimeModel(m)) return false;
      if (selectedMode.value === 'offline' && !isOfflineModel(m)) return false;
      // 4. Language filter
      if (selectedLang.value !== 'all' && !matchModelLang(m, selectedLang.value)) return false;
      // 5. Search query
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
      if (sortKey.value === 'ready') {
        const score = (m) => (m.isLoaded ? 2 : (m.status === 'ready' ? 1 : 0));
        const diff = sortOrder.value === 'desc' ? score(b) - score(a) : score(a) - score(b);
        if (diff !== 0) return diff;
        return a.name.localeCompare(b.name);
      }
      if (sortKey.value === 'name') {
        const res = a.name.localeCompare(b.name);
        return sortOrder.value === 'asc' ? res : -res;
      }
      if (sortKey.value === 'params') {
        const diff = parseParamsToNum(b.params) - parseParamsToNum(a.params);
        return sortOrder.value === 'desc' ? diff : -diff;
      }
      if (sortKey.value === 'size') {
        const diff = parseSizeToBytes(b.size) - parseSizeToBytes(a.size);
        return sortOrder.value === 'desc' ? diff : -diff;
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

function isRealtimeModel(m) {
  if (Array.isArray(m.categories)) {
    return m.categories.includes('RealtimeASR');
  }
  return m.engine === 'xasr';
}

function isOfflineModel(m) {
  if (Array.isArray(m.categories)) {
    return m.categories.includes('FileASR');
  }
  return m.engine !== 'xasr';
}

function cleanModelName(name) {
  if (!name) return '';
  return name.replace(/^Streaming\s+/i, '');
}

function getModeCount(mode) {
  if (mode === 'realtime') return modelsList.value.filter(isRealtimeModel).length;
  if (mode === 'offline') return modelsList.value.filter(isOfflineModel).length;
  return modelsList.value.length;
}

function matchModelLang(m, lang) {
  if (lang === 'all') return true;
  const rawLangs = Array.isArray(m.rawLanguages) ? m.rawLanguages : (Array.isArray(m.languages) ? m.languages : []);
  const textLangs = (m.langs || '').toLowerCase();
  const idStr = (m.id || '').toLowerCase();
  if (lang === 'multilingual') {
    return rawLangs.includes('multilingual') || textLangs.includes('99+') || textLangs.includes('多语') || textLangs.includes('八语') || textLangs.includes('all');
  }
  if (lang === 'zh') {
    return rawLangs.includes('zh') || rawLangs.includes('en') || textLangs.includes('中') || textLangs.includes('英') || textLangs.includes('zh') || textLangs.includes('en');
  }
  if (lang === 'yue') {
    return rawLangs.includes('yue') || textLangs.includes('粤') || textLangs.includes('cantonese');
  }
  return rawLangs.includes(lang) || textLangs.includes(lang) || idStr.includes(`-${lang}-`) || idStr.includes(`_${lang}_`) || idStr.endsWith(`-${lang}`);
}

function getLangCount(lang) {
  return modelsList.value.filter((m) => matchModelLang(m, lang)).length;
}

watch(
  () => props.isOnline,
  (online) => {
    if (online) {
      fetchBackendModels();
      fetchDownloadSource();
    }
  }
);

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
    const list = Array.isArray(data) ? data : (data?.data || data?.models || []);
    if (list && list.length > 0) {
      // Prune custom models that were unregistered
      const backendIdSet = new Set(list.map((m) => m.id));
      modelsList.value = modelsList.value.filter((m) => !m.isCustom || backendIdSet.has(m.id));

      list.forEach((backendModel) => {
        const local = modelsList.value.find((m) => m.id === backendModel.id);
        if (local) {
          local.status = backendModel.status === 'ready' ? 'ready' : (backendModel.status === 'corrupted' ? 'corrupted' : 'remote');
          local.isLoaded = !!backendModel.loaded;
          local.isCustom = !!backendModel.is_custom;
          if (backendModel.categories) {
            local.categories = backendModel.categories;
          }
          if (Array.isArray(backendModel.languages) && backendModel.languages.length > 0) {
            local.rawLanguages = backendModel.languages;
          }
          if (backendModel.size_on_disk && backendModel.size_on_disk > 0) {
            const szMb = backendModel.size_on_disk / (1024 * 1024);
            local.size = szMb >= 1000 ? `${(szMb / 1024).toFixed(1)} GB` : `${Math.round(szMb)} MB`;
          }
        } else {
          const szMb = (backendModel.size_on_disk || backendModel.size_expected || 0) / (1024 * 1024);
          const sizeStr = szMb >= 1000 ? `${(szMb / 1024).toFixed(1)} GB` : `${Math.round(szMb)} MB`;
          let latency = null;
          if (backendModel.id.includes('160ms')) latency = '160ms 极速';
          else if (backendModel.id.includes('480ms')) latency = '480ms 均衡';
          else if (backendModel.id.includes('960ms')) latency = '960ms 扩展';
          else if (backendModel.id.includes('1920ms')) latency = '1.92s 高精';

          modelsList.value.push({
            id: backendModel.id,
            name: backendModel.name || backendModel.id,
            engine: backendModel.owned_by || 'whisper',
            desc: backendModel.description || `${backendModel.name} 语音识别模型`,
            params: backendModel.params || '-',
            latency: latency,
            vram: backendModel.vram || '-',
            langs: Array.isArray(backendModel.languages) ? backendModel.languages.join(' / ') : (backendModel.languages || '多语言'),
            rawLanguages: Array.isArray(backendModel.languages) ? backendModel.languages : [],
            categories: backendModel.categories,
            size: sizeStr,
            status: backendModel.status === 'ready' ? 'ready' : (backendModel.status === 'corrupted' ? 'corrupted' : 'remote'),
            isLoaded: !!backendModel.loaded,
            isCustom: !!backendModel.is_custom,
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
  model.downloadPercent = 5;

  try {
    await apiClient.downloadModel(model.id, source, (event) => {
      if (event && typeof event.percent === 'number') {
        model.downloadPercent = Math.min(99, Math.max(5, Math.round(event.percent)));
      }
      if (event && event.status) {
        model.status = event.status;
      }
    });
    model.downloadPercent = 100;
    model.status = 'ready';
    model.isDownloading = false;
    await fetchBackendModels();
  } catch (err) {
    console.warn('Backend download error:', err);
    model.isDownloading = false;
    await fetchBackendModels();
  }
}

async function handleDeleteModel(model) {
  const confirmMsg = t('modelsDeleteConfirm').replace('{name}', model.name);
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

async function handleUnregisterModel(model) {
  const confirmMsg = t('modelsUnregisterConfirm').replace('{name}', model.name);
  if (!confirm(confirmMsg)) {
    return;
  }
  model.isBusy = true;
  try {
    await apiClient.unregisterCustomModel(model.id);
    modelsList.value = modelsList.value.filter((m) => m.id !== model.id);
  } catch (err) {
    alert(err.message || '注销失败');
  } finally {
    model.isBusy = false;
  }
}

const showImportModal = ref(false);
const importForm = ref({
  id: '',
  name: '',
  driver: 'xasr',
  model_path: '',
});
const importError = ref('');
const isImporting = ref(false);

function resetImportForm() {
  importForm.value = {
    id: '',
    name: '',
    driver: 'xasr',
    model_path: '',
  };
  importError.value = '';
  isImporting.value = false;
}

function cancelImportModal() {
  showImportModal.value = false;
  resetImportForm();
}

async function handleImportSubmit() {
  if (isImporting.value) return;
  importError.value = '';

  const cleanId = importForm.value.id.trim();
  if (!cleanId) {
    importError.value = '请输入模型标识 (ID)';
    return;
  }
  if (!/^[a-zA-Z0-9_\-\.]+$/.test(cleanId)) {
    importError.value = '模型标识只能包含字母、数字、下划线、中划线或点号';
    return;
  }
  const cleanPath = importForm.value.model_path.trim();
  if (!cleanPath) {
    importError.value = '请输入模型文件夹路径';
    return;
  }

  isImporting.value = true;
  try {
    await apiClient.registerCustomModel({
      id: cleanId,
      name: importForm.value.name.trim() || cleanId,
      driver: importForm.value.driver,
      model_path: cleanPath,
    });
    showImportModal.value = false;
    resetImportForm();
    await handleManualRefresh();
  } catch (err) {
    importError.value = err.message || '导入模型失败，请检查路径与文件完整性';
  } finally {
    isImporting.value = false;
  }
}

async function handleOpenDir() {
  if (isTauri) {
    invoke('open_local_dir', { target: 'models' }).catch((err) => {
      console.warn('Native open_local_dir failed, falling back to server open-path:', err);
      apiClient.post('/v1/system/open-path', { path: 'models' });
    });
  } else {
    try {
      await apiClient.post('/v1/system/open-path', { path: 'models' });
    } catch {
      alert(t('modelsPathAlert'));
    }
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
/* 1. Models Toolbar Rows (2-Row Layout) */
.models-toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}

.models-toolbar-row.filters-row {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
}

.filters-group-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.models-toolbar-row.actions-row {
  padding: 0 4px;
  font-size: 11.5px;
}

.actions-group-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  width: 220px;
  flex-shrink: 0;
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
  background: var(--bg-surface);
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

.metric-summary-left {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.summary-num {
  color: var(--text-primary);
  font-weight: 600;
}

.storage-text {
  color: var(--text-secondary);
}

.disk-size {
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.filter-select-control {
  display: flex;
  align-items: center;
  gap: 5px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 4px 8px;
  transition: all 0.15s ease;
}

.filter-select-control:hover {
  border-color: var(--border-hover, rgba(255, 255, 255, 0.2));
  background: var(--bg-elevated);
}

.filter-select-control.filter-active {
  border-color: var(--accent-emerald);
  background: rgba(16, 185, 129, 0.08);
}

.filter-select-control.filter-active .filter-select-icon {
  color: var(--accent-emerald);
}

.filter-select-control.filter-active .filter-select-dropdown {
  color: var(--accent-emerald);
  font-weight: 600;
}

.filter-select-icon {
  width: 12px;
  height: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.filter-select-dropdown {
  background: transparent;
  border: none;
  font-size: 11.5px;
  color: var(--text-secondary);
  cursor: pointer;
  outline: none;
  font-family: inherit;
}

.filter-select-dropdown option {
  background: #18181b;
  color: #f4f4f5;
}

.sep {
  color: var(--border-subtle);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 5px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 11.5px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.refresh-btn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.refresh-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.refresh-svg {
  width: 12px;
  height: 12px;
  transition: transform 0.2s ease;
}

.refresh-btn.refreshing .refresh-svg {
  animation: spin-clockwise 0.7s linear infinite;
}

@keyframes spin-clockwise {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.open-dir-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 5px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 11.5px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.open-dir-btn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.folder-svg {
  width: 12px;
  height: 12px;
}

/* 3. Table Container */
.models-grid-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
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

/* 4. Models List Table (5-column Grid) */
.models-list-table {
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  min-width: 620px;
  overflow: hidden;
}

.list-header-row {
  display: grid;
  grid-template-columns: minmax(130px, 1.8fr) minmax(105px, 1fr) minmax(80px, 2.2fr) minmax(55px, 0.6fr) minmax(60px, 0.6fr) minmax(155px, auto);
  align-items: center;
  padding: 10px 16px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(0, 0, 0, 0.02);
}

.list-header-row .col {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  white-space: nowrap !important;
}

.list-header-row .col-status-actions {
  justify-content: flex-end !important;
}

.sortable-header {
  cursor: pointer;
  user-select: none;
  display: inline-flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 4px;
  white-space: nowrap;
  flex-wrap: nowrap;
  transition: color 0.15s ease;
}

.sortable-header .header-label {
  white-space: nowrap;
}

.sortable-header:hover {
  color: var(--text-primary);
}

.sortable-header.active {
  color: var(--text-primary);
  font-weight: 700;
}

.sort-indicator {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 1px;
  margin-left: 3px;
  line-height: 1;
  vertical-align: middle;
  flex-shrink: 0;
}

.sort-indicator .sort-arrow {
  font-size: 6px;
  line-height: 6px;
  color: var(--text-muted);
  opacity: 0.35;
  transition: all 0.15s ease;
}

.sortable-header:hover .sort-indicator .sort-arrow {
  opacity: 0.65;
}

.sort-indicator .sort-arrow.highlighted {
  color: var(--accent-emerald, #10b981);
  opacity: 1;
  font-weight: 800;
}

.list-body-row {
  display: grid;
  grid-template-columns: minmax(130px, 1.8fr) minmax(105px, 1fr) minmax(80px, 2.2fr) minmax(55px, 0.6fr) minmax(60px, 0.6fr) minmax(155px, auto);
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
  min-width: 0;
  padding-right: 12px;
}

.model-title-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.model-row-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-engine-line {
  display: flex;
  align-items: center;
}

.model-engine-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  line-height: 1.2;
}

.model-id-line {
  display: flex;
  align-items: center;
  min-width: 0;
}

.model-row-id {
  font-size: 10.5px;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, monospace;
  word-break: break-all;
  white-space: normal;
  line-height: 1.35;
}

.stream-pill {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  line-height: 1.2;
  color: var(--accent-emerald, #10b981);
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.22);
  flex-shrink: 0;
}

.col-langs {
  display: flex;
  align-items: center;
  min-width: 0;
  padding-right: 12px;
}

.lang-select-wrap {
  width: 100%;
  max-width: 185px;
  min-width: 0;
}

.lang-cell-dropdown {
  width: 100%;
  height: 25px;
  padding: 2px 20px 2px 8px;
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  cursor: pointer;
  outline: none;
  font-family: inherit;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  appearance: none;
  -webkit-appearance: none;
  transition: all 0.15s ease;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23888888' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 6px center;
  background-size: 9px;
}

.lang-cell-dropdown:hover {
  color: var(--text-primary);
  background-color: var(--bg-elevated);
  border-color: var(--border-hover, rgba(255, 255, 255, 0.2));
}

.lang-cell-dropdown option {
  background: #18181b;
  color: #f4f4f5;
  font-size: 12px;
  padding: 4px;
}

.lang-cell-dropdown option:first-child {
  font-weight: 600;
  color: var(--accent-emerald, #10b981);
}

.col-desc {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  padding-right: 14px;
}

.desc-text {
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.col-params {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  font-size: 11px;
  min-width: 0;
}

.params-primary {
  display: flex;
  align-items: center;
}

.param-num {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.params-secondary {
  display: flex;
  align-items: center;
}

.vram-text {
  font-size: 10.5px;
  color: var(--text-muted);
}

.col-size {
  display: flex;
  align-items: center;
  font-size: 11.5px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, monospace;
  min-width: 0;
}

.size-text {
  font-size: 11.5px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.col-status-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 155px;
  flex-shrink: 0;
}

.col-status-actions.sortable-header {
  justify-content: flex-end;
}

.col-status-actions .status-box {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.col-status-actions .actions-box {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* Status Indicators (Mac Minimalist Dot Style) */
.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.status-indicator.in-vram {
  color: var(--accent-emerald, #10b981);
}

.status-indicator.ready {
  color: var(--text-secondary);
}

.status-indicator.remote {
  color: var(--text-muted);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
  box-sizing: border-box;
}

.status-dot.green {
  background: var(--accent-emerald, #10b981);
}

.status-dot.green.pulse {
  animation: pulse-dot 1.4s infinite;
}

.status-dot.ready {
  background: var(--text-muted);
  opacity: 0.7;
}

.status-dot.hollow {
  background: transparent;
  border: 1.5px solid var(--text-muted);
  opacity: 0.5;
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

.import-modal-card {
  max-width: 500px;
}

.import-form {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.form-label {
  font-size: 12px;
  font-weight: 550;
  color: var(--text-main, #374151);
  display: flex;
  align-items: center;
  gap: 4px;
}

.required {
  color: #ef4444;
}

.form-input {
  height: 34px;
  padding: 0 10px;
  border-radius: 7px;
  border: 1px solid var(--border-color, #d1d5db);
  background: var(--bg-item, #fafafa);
  color: var(--text-main, #111827);
  font-size: 12.5px;
  outline: none;
  transition: all 0.15s ease;
}

.form-input:focus {
  border-color: var(--primary-color, #10b981);
  background: var(--bg-card, #ffffff);
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.15);
}

.form-select {
  height: 34px;
  padding: 0 10px;
  border-radius: 7px;
  border: 1px solid var(--border-color, #d1d5db);
  background: var(--bg-item, #fafafa);
  color: var(--text-main, #111827);
  font-size: 12.5px;
  outline: none;
  cursor: pointer;
  transition: all 0.15s ease;
}

.form-select:focus {
  border-color: var(--primary-color, #10b981);
  background: var(--bg-card, #ffffff);
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.15);
}

.import-error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #dc2626;
  font-size: 12px;
}

.error-svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.custom-model-badge {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted, #6b7280);
  background: var(--bg-hover, #f3f4f6);
  border: 1px solid var(--border-color, #e5e7eb);
  padding: 0 5px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  height: 17px;
  line-height: 1;
}

.row-delete-btn.row-unreg-btn:hover {
  color: var(--primary-color, #10b981);
  background: rgba(16, 185, 129, 0.08);
}
</style>
