<template>
  <div class="history-view">
    <!-- Top Filter & Action Bar -->
    <div class="history-toolbar">
      <div class="filter-group">
        <button
          v-for="f in filterOptions"
          :key="f.id"
          class="filter-pill"
          :class="{ active: currentFilter === f.id }"
          @click="currentFilter = f.id"
        >
          <span>{{ f.label }}</span>
          <span class="filter-count">({{ getFilterCount(f.id) }})</span>
        </button>
      </div>

      <div class="search-box">
        <svg viewBox="0 0 24 24" class="search-icon" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          :placeholder="t('historySearchPlaceholder')"
        />
        <button v-if="searchQuery" class="clear-search-btn" @click="searchQuery = ''">✕</button>
      </div>

      <div class="toolbar-actions">
        <button
          v-if="items.length > 0"
          class="clear-all-btn"
          @click="handleClearAll"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
          <span>{{ t('historyClear') }}</span>
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="filteredItems.length === 0" class="history-empty-container">
      <div class="empty-card">
        <div class="empty-icon-wrap">
          <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.6">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <h3 class="empty-title">{{ t('historyEmpty') }}</h3>
        <p class="empty-desc">{{ t('historyEmptyDesc') }}</p>
      </div>
    </div>

    <!-- Master-Detail Split Workspace -->
    <div v-else class="history-split-layout">
      <!-- Left List (Master Column) -->
      <aside class="records-sidebar">
        <div class="records-list">
          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="record-card"
            :class="{ active: selectedItem && selectedItem.id === item.id }"
            @click="selectItem(item)"
          >
            <div class="record-card-top">
              <span class="type-badge" :class="item.type">
                {{ item.type === 'dictate' ? t('historyDictateBadge') : t('historyFileBadge') }}
              </span>
              <span class="record-time">{{ item.time }}</span>
              <span v-if="item.model" class="model-badge">{{ item.model }}</span>
            </div>

            <h4 class="record-title" :title="item.filename || item.text">
              {{ item.filename || item.text.slice(0, 32) }}
            </h4>

            <p class="record-snippet">
              {{ item.text }}
            </p>

            <div class="record-card-meta">
              <span v-if="item.duration">{{ formatSeconds(item.duration) }}</span>
              <span v-if="item.latency" class="meta-dot">•</span>
              <span v-if="item.latency">{{ item.latency }}ms</span>
              <button
                class="card-delete-btn"
                :title="t('historyDelete')"
                @click.stop="handleDeleteItem(item.id)"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      </aside>

      <!-- Right Detail Workspace (Detail Column) -->
      <main class="record-detail-panel">
        <div v-if="selectedItem" class="detail-container">
          <!-- Detail Header -->
          <div class="detail-header">
            <div class="detail-title-group">
              <div class="detail-type-row">
                <span class="type-badge" :class="selectedItem.type">
                  {{ selectedItem.type === 'dictate' ? t('historyDictateLong') : t('historyFileLong') }}
                </span>
                <span class="detail-time">{{ selectedItem.time }}</span>
                <span v-if="selectedItem.model" class="model-badge">{{ selectedItem.model }}</span>
              </div>
              <h2 class="detail-heading">
                {{ selectedItem.filename || t('historyDefaultAsset') }}
              </h2>
            </div>

            <!-- Detail Action Buttons -->
            <div class="detail-actions">
              <button class="tool-btn copy-btn" @click="copyDetailText">
                {{ copied ? t('historyCopiedFull') : t('copyText') }}
              </button>
              <button
                v-if="selectedItem.segments && selectedItem.segments.length > 0"
                class="tool-btn"
                @click="exportFormat('srt')"
              >
                {{ t('historyExportSrt') }}
              </button>
              <button
                v-if="selectedItem.segments && selectedItem.segments.length > 0"
                class="tool-btn"
                @click="exportFormat('vtt')"
              >
                {{ t('historyExportVtt') }}
              </button>
              <button class="tool-btn" @click="exportFormat('txt')">
                {{ t('historyExportTxt') }}
              </button>
              <button class="tool-btn delete-btn" :title="t('historyDelete')" @click="handleDeleteItem(selectedItem.id)">
                {{ t('historyDelete') }}
              </button>
            </div>
          </div>

          <!-- Detail Telemetry Metrics Bar -->
          <div class="detail-metrics-row">
            <div class="metric-pill">
              <span class="metric-label">{{ t('historyMetricChars') }}:</span>
              <span class="metric-val">{{ selectedItem.text ? selectedItem.text.length : 0 }} {{ t('unitWords') }}</span>
            </div>
            <div v-if="selectedItem.duration" class="metric-pill">
              <span class="metric-label">{{ t('historyMetricAudioDuration') }}:</span>
              <span class="metric-val">{{ formatSeconds(selectedItem.duration) }}</span>
            </div>
            <div v-if="selectedItem.latency" class="metric-pill">
              <span class="metric-label">{{ t('historyMetricLatency') }}:</span>
              <span class="metric-val">{{ selectedItem.latency }} ms</span>
            </div>
            <div v-if="selectedItem.segments && selectedItem.segments.length > 0" class="metric-pill">
              <span class="metric-label">{{ t('historyMetricSegments') }}:</span>
              <span class="metric-val">{{ selectedItem.segments.length }} {{ t('unitSentences') }}</span>
            </div>
          </div>

          <!-- Detail Subtitle Segments / Text Canvas -->
          <div class="detail-content-box">
            <!-- Timestamp Segments List (if available) -->
            <div v-if="selectedItem.segments && selectedItem.segments.length > 0" class="segment-stream">
              <div v-for="(seg, idx) in selectedItem.segments" :key="idx" class="segment-card">
                <div class="timestamp-pill">
                  {{ formatTime(seg.start) }} → {{ formatTime(seg.end) }}
                </div>
                <div class="segment-body">{{ seg.text }}</div>
              </div>
            </div>

            <!-- Plain Article Text (Fallback or Dictate) -->
            <div v-else class="article-text-body">
              {{ selectedItem.text }}
            </div>
          </div>
        </div>

        <div v-else class="no-selection-placeholder">
          <p>{{ t('historySelectHint') }}</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from '../i18n';

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['delete-item', 'clear-all']);
const { t } = useI18n();

const currentFilter = ref('all');
const searchQuery = ref('');
const selectedItem = ref(null);
const copied = ref(false);

const filterOptions = computed(() => [
  { id: 'all', label: t('historyFilterAll') || '全部' },
  { id: 'dictate', label: t('historyFilterDictate') || '实时听写' },
  { id: 'file', label: t('historyFilterFile') || '文件转录' }
]);

function getFilterCount(filterId) {
  if (filterId === 'all') return props.items.length;
  return props.items.filter((item) => item.type === filterId).length;
}

const filteredItems = computed(() => {
  let list = props.items;
  if (currentFilter.value !== 'all') {
    list = list.filter((i) => i.type === currentFilter.value);
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase();
    list = list.filter(
      (i) =>
        (i.text && i.text.toLowerCase().includes(q)) ||
        (i.filename && i.filename.toLowerCase().includes(q)) ||
        (i.model && i.model.toLowerCase().includes(q))
    );
  }
  return list;
});

// Auto-select first item when list changes or on initial mount
watch(
  () => filteredItems.value,
  (newList) => {
    if (newList.length > 0) {
      if (!selectedItem.value || !newList.some((i) => i.id === selectedItem.value.id)) {
        selectedItem.value = newList[0];
      }
    } else {
      selectedItem.value = null;
    }
  },
  { immediate: true }
);

function selectItem(item) {
  selectedItem.value = item;
}

function handleDeleteItem(id) {
  emit('delete-item', id);
}

function handleClearAll() {
  if (confirm(t('historyClearConfirm') || '确定要清空全部历史记录吗？')) {
    emit('clear-all');
    selectedItem.value = null;
  }
}

function copyDetailText() {
  if (!selectedItem.value || !selectedItem.value.text) return;
  navigator.clipboard.writeText(selectedItem.value.text);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1800);
}

function formatSeconds(sec = 0) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

function formatTime(seconds = 0) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

function formatSrtTime(seconds = 0) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}

function exportFormat(format) {
  if (!selectedItem.value) return;
  let content = '';
  const item = selectedItem.value;
  const baseName = item.filename ? item.filename.replace(/\.[^/.]+$/, '') : `transcript_${item.id || Date.now()}`;
  const filename = `${baseName}.${format}`;

  if (format === 'srt' && item.segments && item.segments.length > 0) {
    content = item.segments
      .map((seg, i) => `${i + 1}\n${formatSrtTime(seg.start)} --> ${formatSrtTime(seg.end)}\n${seg.text}\n`)
      .join('\n');
  } else if (format === 'vtt' && item.segments && item.segments.length > 0) {
    content = 'WEBVTT\n\n' + item.segments
      .map((seg, i) => `${i + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n`)
      .join('\n');
  } else {
    content = item.text || '';
  }

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-surface);
  color: var(--text-primary);
  overflow: hidden;
}

/* Toolbar */
.history-toolbar {
  height: 52px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  flex-shrink: 0;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-pill {
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 500;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s ease;
}

.filter-pill:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.filter-pill.active {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  border-color: rgba(16, 185, 129, 0.25);
  font-weight: 600;
}

.filter-count {
  font-size: 11px;
  opacity: 0.8;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 4px 10px;
  width: 260px;
  transition: border-color 0.15s ease;
}

.search-box:focus-within {
  border-color: var(--accent-emerald);
}

.search-icon {
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 12px;
  color: var(--text-primary);
  width: 100%;
}

.clear-search-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
}

.clear-all-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  font-size: 12px;
  color: var(--text-muted);
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.clear-all-btn:hover {
  color: var(--accent-red);
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.08);
}

/* Empty State */
.history-empty-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 360px;
}

.empty-icon-wrap {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  margin-bottom: 16px;
  border: 1px solid var(--border-subtle);
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.5;
}

/* Master-Detail Layout */
.history-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Left Master Column */
.records-sidebar {
  width: 310px;
  border-right: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow-y: auto;
}

.records-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.record-card {
  padding: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.record-card:hover {
  background: var(--bg-card-hover);
  border-color: rgba(16, 185, 129, 0.3);
}

.record-card.active {
  background: var(--bg-card-hover);
  border-color: var(--accent-emerald);
  box-shadow: 0 0 0 1px var(--accent-emerald);
}

.record-card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.type-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}

.record-time {
  font-size: 10.5px;
  color: var(--text-muted);
}

.model-badge {
  margin-left: auto;
  font-size: 10px;
  color: var(--accent-emerald);
  background: var(--accent-emerald-subtle);
  padding: 1px 5px;
  border-radius: 4px;
}

.record-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.record-snippet {
  font-size: 11.5px;
  color: var(--text-secondary);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 8px;
}

.record-card-meta {
  display: flex;
  align-items: center;
  font-size: 10.5px;
  color: var(--text-muted);
  gap: 6px;
}

.meta-dot {
  opacity: 0.5;
}

.card-delete-btn {
  margin-left: auto;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.card-delete-btn:hover {
  color: var(--accent-red);
  background: rgba(239, 68, 68, 0.1);
}

/* Right Detail Column */
.record-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  overflow-y: auto;
}

.detail-container {
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 900px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 16px;
}

.detail-title-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-type-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-time {
  font-size: 11.5px;
  color: var(--text-muted);
}

.detail-heading {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tool-btn {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 6px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.tool-btn:hover {
  border-color: rgba(16, 185, 129, 0.4);
  background: var(--bg-card-hover);
}

.copy-btn {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  border-color: rgba(16, 185, 129, 0.3);
  font-weight: 600;
}

.delete-btn {
  color: var(--text-muted);
}

.delete-btn:hover {
  color: var(--accent-red);
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
}

/* Detail Metrics Bar */
.detail-metrics-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.metric-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 11.5px;
}

.metric-label {
  color: var(--text-muted);
}

.metric-val {
  color: var(--text-primary);
  font-weight: 600;
}

/* Detail Content Body */
.detail-content-box {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px;
  min-height: 200px;
}

.article-text-body {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  user-select: text;
  -webkit-user-select: text;
}

.segment-stream {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.segment-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
}

.timestamp-pill {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10.5px;
  color: var(--accent-emerald);
  background: var(--accent-emerald-subtle);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid rgba(16, 185, 129, 0.2);
  white-space: nowrap;
  flex-shrink: 0;
}

.segment-body {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  user-select: text;
  -webkit-user-select: text;
}

.no-selection-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
