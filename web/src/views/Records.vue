<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getUploadRecords, getFileTranscriptionRecords, getStreamingRecords } from '../api'

const { t } = useI18n()

const activeTab = ref('uploads')
const loading = ref(false)
const loadError = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalPages = ref(0)
const sortBy = ref('created_at')
const sortOrder = ref('desc')

// ── Tab 配置 ─────────────────────────────────────────────────

const tabs = computed(() => [
  { key: 'uploads', label: t('records.tabUploads') },
  { key: 'fileTranscriptions', label: t('records.tabFileTrans') },
  { key: 'streaming', label: t('records.tabStreaming') },
])

const uploadColumns = computed(() => [
  { key: 'filename', label: t('records.colFileName'), sortable: true },
  { key: 'file_size', label: t('records.colFileSize'), sortable: true },
  { key: 'file_md5', label: t('records.colMd5') },
  { key: 'content_type', label: t('records.colContentType') },
  { key: 'created_at', label: t('records.colUploadTime'), sortable: true },
])

const fileTransColumns = computed(() => [
  { key: 'filename', label: t('records.colFileName'), sortable: true },
  { key: 'engine_name', label: t('records.colEngine'), sortable: true },
  { key: 'model_name', label: t('records.colModel') },
  { key: 'segment_count', label: t('records.colSegments') },
  { key: 'total_time', label: t('records.colTime'), sortable: true },
  { key: 'is_completed', label: t('records.colStatus'), sortable: true },
  { key: 'error_message', label: t('records.colError') },
  { key: 'completed_at', label: t('records.colCompleteTime'), sortable: true },
])

const streamingColumns = computed(() => [
  { key: 'engine_name', label: t('records.colEngine'), sortable: true },
  { key: 'model_name', label: t('records.colModel') },
  { key: 'language', label: t('records.colLanguage') },
  { key: 'line_count', label: t('records.colLines') },
  { key: 'total_time', label: t('records.colTime'), sortable: true },
  { key: 'is_completed', label: t('records.colStatus'), sortable: true },
  { key: 'error_message', label: t('records.colError') },
  { key: 'completed_at', label: t('records.colCompleteTime'), sortable: true },
])

const currentColumns = computed(() => {
  if (activeTab.value === 'uploads') return uploadColumns.value
  if (activeTab.value === 'fileTranscriptions') return fileTransColumns.value
  return streamingColumns.value
})

// ── 数据加载 ─────────────────────────────────────────────────

async function loadData() {
  loading.value = true
  loadError.value = ''
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    }
    let data
    if (activeTab.value === 'uploads') {
      data = await getUploadRecords(params)
    } else if (activeTab.value === 'fileTranscriptions') {
      data = await getFileTranscriptionRecords(params)
    } else {
      data = await getStreamingRecords(params)
    }
    items.value = data.items || []
    total.value = data.total || 0
    totalPages.value = data.total_pages || 0
  } catch (e) {
    console.error('[Records] loadData error:', e)
    loadError.value = e.message || 'Request failed'
    items.value = []
    total.value = 0
    totalPages.value = 0
  } finally {
    loading.value = false
  }
}

function switchTab(tab) {
  activeTab.value = tab
  page.value = 1
  sortBy.value = 'created_at'
  sortOrder.value = 'desc'
  loadError.value = ''
  loadData()
}

function toggleSort(col) {
  if (!col.sortable) return
  if (sortBy.value === col.key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = col.key
    sortOrder.value = 'desc'
  }
  page.value = 1
  loadData()
}

function goToPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  loadData()
}

function formatSize(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(seconds) {
  if (seconds == null) return '-'
  if (seconds < 60) return seconds.toFixed(1) + 's'
  const m = Math.floor(seconds / 60)
  const s = (seconds % 60).toFixed(0)
  return `${m}m ${s}s`
}

function formatDateTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function getCellValue(item, key) {
  if (key === 'file_size') return formatSize(item[key])
  if (key === 'total_time') return formatTime(item[key])
  if (key === 'completed_at' || key === 'created_at') return formatDateTime(item[key])
  if (key === 'is_completed') return item[key] ? t('records.statusDone') : t('records.statusFail')
  return item[key] ?? '-'
}

function getCellClass(item, key) {
  if (key === 'is_completed') return item[key] ? 'status-ok' : 'status-fail'
  if (key === 'error_message' && item[key]) return 'error-text'
  return ''
}

// 初始加载
loadData()
</script>

<template>
  <div class="records-page">
    <div class="page-header">
      <h1>{{ t('records.title') }}</h1>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Table -->
    <div class="table-wrap">
      <div v-if="loading" class="loading-state">{{ t('records.loading') }}</div>
      <div v-else-if="loadError" class="error-state">⚠ {{ loadError }}</div>
      <div v-else-if="items.length === 0" class="empty-state">{{ t('records.empty') }}</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th
              v-for="col in currentColumns"
              :key="col.key"
              :class="{ sortable: col.sortable, sorted: sortBy === col.key }"
              @click="toggleSort(col)"
            >
              {{ col.label }}
              <span v-if="col.sortable && sortBy === col.key" class="sort-icon">
                {{ sortOrder === 'asc' ? '↑' : '↓' }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in items" :key="item.record_id || item.file_id || idx">
            <td
              v-for="col in currentColumns"
              :key="col.key"
              :class="getCellClass(item, col.key)"
            >
              {{ getCellValue(item, col.key) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="goToPage(1)" class="page-btn">{{ t('records.first') }}</button>
      <button :disabled="page <= 1" @click="goToPage(page - 1)" class="page-btn">{{ t('records.prev') }}</button>
      <span class="page-info">{{ t('records.pageInfo', { page, totalPages, total }) }}</span>
      <button :disabled="page >= totalPages" @click="goToPage(page + 1)" class="page-btn">{{ t('records.next') }}</button>
      <button :disabled="page >= totalPages" @click="goToPage(totalPages)" class="page-btn">{{ t('records.last') }}</button>
    </div>
    <div v-else-if="total > 0" class="pagination">
      <span class="page-info">{{ t('records.totalOnly', { total }) }}</span>
    </div>
  </div>
</template>

<style scoped>
.records-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  max-height: 100vh;
  overflow-y: auto;
}

.page-header h1 {
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0 0 20px;
}

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: #f0f0f0;
  border-radius: 10px;
  padding: 4px;
  width: fit-content;
}

.tab-btn {
  padding: 8px 20px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: #333;
}

.tab-btn.active {
  background: #fff;
  color: #1d1d1f;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.table-wrap {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  text-align: left;
  padding: 12px 14px;
  background: #fafafa;
  font-weight: 600;
  color: #6e6e73;
  border-bottom: 1px solid #f0f0f0;
  white-space: nowrap;
  user-select: none;
}

.data-table th.sortable {
  cursor: pointer;
}

.data-table th.sortable:hover {
  color: #333;
}

.data-table th.sorted {
  color: #667eea;
}

.sort-icon {
  margin-left: 4px;
  font-size: 12px;
}

.data-table td {
  padding: 10px 14px;
  border-bottom: 1px solid #f5f5f5;
  color: #333;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-table tbody tr:hover {
  background: #f8f9ff;
}

.status-ok {
  color: #34c759;
  font-weight: 500;
}

.status-fail {
  color: #ff3b30;
  font-weight: 500;
}

.error-text {
  color: #ff3b30;
  max-width: 200px;
}

.loading-state,
.empty-state {
  padding: 40px;
  text-align: center;
  color: #999;
  font-size: 14px;
}

.error-state {
  padding: 40px;
  text-align: center;
  color: #ff3b30;
  font-size: 14px;
  background: #fff0f0;
  border-radius: 12px;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
}

.page-btn {
  padding: 6px 14px;
  border: 1.5px solid #d2d2d7;
  background: #fff;
  border-radius: 8px;
  font-size: 13px;
  color: #333;
  cursor: pointer;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  border-color: #667eea;
  color: #667eea;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  font-size: 13px;
  color: #666;
  margin: 0 8px;
}
</style>
