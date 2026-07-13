<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { getEngines, transcribeFileStream, transcribeUrlStream, transcribeFile, transcribeUrl, getStoredApiKey } from '../api'

const { t } = useI18n()

const engines = ref([])
const selectedEngine = ref('')
const inputMode = ref('file')
const streamingEnabled = ref(true)
const url = ref('')
const file = ref(null)
const fileName = ref('')
const fileSize = ref('')
const isTranscribing = ref(false)
const isDragging = ref(false)
const segments = ref([])
const resultText = ref('')
const error = ref('')
const activeTab = ref('srt')
const resultRef = ref(null)
let xhr = null

onMounted(() => {
  loadEngines()
})

async function loadEngines() {
  try {
    error.value = ''
    const data = await getEngines()
    engines.value = data.engines
    selectedEngine.value = data.default
  } catch (e) {
    error.value = e.message
    engines.value = []
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function onFileChange(e) {
  const f = e.target.files[0]
  if (f) {
    file.value = f
    fileName.value = f.name
    fileSize.value = formatFileSize(f.size)
  }
}

function onDrop(e) {
  e.preventDefault()
  isDragging.value = false
  const f = e.dataTransfer.files[0]
  if (f) {
    file.value = f
    fileName.value = f.name
    fileSize.value = formatFileSize(f.size)
  }
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')},${String(ms).padStart(3,'0')}`
}

function formatSrtSingle(seg) {
  if (!seg) return ''
  return `1\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n`
}

function buildSrt(segList) {
  if (segList.length === 0) return ''
  return segList.map((seg, i) => {
    return `${i + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n`
  }).join('\n')
}

function buildText(segList) {
  if (segList.length === 0) return ''
  return segList.map(seg => seg.text).join('\n')
}

let accumulatedText = ''

function onSegment(seg) {
  // 流式接口返回识别结果
  // faster-whisper: 每句独立 segment
  // wlk: 累积更新的文本
  if (seg.index !== undefined) {
    // 有 index 说明是独立 segment（faster-whisper）
    segments.value.push(seg)
    resultText.value = buildSrt(segments.value)
  } else {
    // 无 index 说明是累积文本（wlk）
    accumulatedText = seg.text
    resultText.value = seg.text
  }
  nextTick(() => {
    if (resultRef.value) resultRef.value.scrollTop = resultRef.value.scrollHeight
  })
}

function onDone() {
  // 识别完成后，确保最终结果正确
  if (accumulatedText && segments.value.length === 0) {
    // wlk 引擎：累积文本模式
    segments.value = [{ text: accumulatedText, start: 0, end: 0 }]
    resultText.value = buildSrt(segments.value)
  } else if (segments.value.length > 0) {
    // faster-whisper 引擎：独立 segment 模式
    resultText.value = buildSrt(segments.value)
  }
  accumulatedText = ''
  isTranscribing.value = false
  xhr = null
}

function onError(e) {
  error.value = e.message
  isTranscribing.value = false
  xhr = null
}

function startTranscribe() {
  if (!getStoredApiKey()) {
    error.value = t('transcribe.errorApiKey')
    return
  }
  error.value = ''
  segments.value = []
  resultText.value = ''
  accumulatedText = ''
  isTranscribing.value = true

  if (streamingEnabled.value) {
    // 流式模式：调用 SSE 流式接口
    if (inputMode.value === 'file') {
      if (!file.value) {
        error.value = t('transcribe.errorNoFile')
        isTranscribing.value = false
        return
      }
      xhr = transcribeFileStream(file.value, selectedEngine.value, onSegment, onDone, onError)
    } else {
      if (!url.value.trim()) {
        error.value = t('transcribe.errorNoUrl')
        isTranscribing.value = false
        return
      }
      xhr = transcribeUrlStream(url.value.trim(), selectedEngine.value, onSegment, onDone, onError)
    }
  } else {
    // 非流式模式：调用普通接口，等待完整结果
    transcribeFileOrUrl()
  }
}

async function transcribeFileOrUrl() {
  try {
    let result
    if (inputMode.value === 'file') {
      if (!file.value) {
        error.value = t('transcribe.errorNoFile')
        isTranscribing.value = false
        return
      }
      result = await transcribeFile(file.value, selectedEngine.value, 'json')
    } else {
      if (!url.value.trim()) {
        error.value = t('transcribe.errorNoUrl')
        isTranscribing.value = false
        return
      }
      result = await transcribeUrl(url.value.trim(), selectedEngine.value, 'json')
    }

    // 处理返回结果
    if (result && result.segments) {
      segments.value = result.segments
      resultText.value = buildSrt(segments.value)
    } else if (result && result.text) {
      segments.value = [{ text: result.text, start: 0, end: 0 }]
      resultText.value = result.text
    }
  } catch (e) {
    error.value = e.message
  } finally {
    isTranscribing.value = false
  }
}

function cancelTranscribe() {
  if (xhr) {
    xhr.abort()
    xhr = null
  }
  isTranscribing.value = false
}

function saveResult() {
  if (!resultText.value) return
  const blob = new Blob([resultText.value], { type: 'text/plain;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  const baseName = inputMode.value === 'file' && fileName.value
    ? fileName.value.replace(/\.[^.]+$/, '')
    : 'transcript'
  a.download = `${baseName}.srt`
  a.click()
  URL.revokeObjectURL(a.href)
}

function copyResult() {
  const text = activeTab.value === 'srt' ? resultText.value : buildText(segments.value)
  navigator.clipboard.writeText(text)
}
</script>

<template>
  <div class="transcribe-page">
    <!-- 左侧：输入控制 -->
    <div class="left-col">
      <div class="card input-card">
        <div class="card-header">
          <h2>{{ t('transcribe.title') }}</h2>
          <p class="subtitle">{{ t('transcribe.subtitle') }}</p>
        </div>

        <div class="mode-tabs">
          <button :class="{ active: inputMode === 'file' }" @click="inputMode = 'file'">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>
            </svg>
            {{ t('transcribe.localFile') }}
          </button>
          <button :class="{ active: inputMode === 'url' }" @click="inputMode = 'url'">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
            {{ t('transcribe.urlInput') }}
          </button>
        </div>

        <div v-if="inputMode === 'file'" class="file-area">
          <div
            class="drop-zone"
            :class="{ dragging: isDragging, 'has-file': fileName }"
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop="onDrop"
          >
            <label class="drop-label">
              <input type="file" accept="audio/*,video/*" @change="onFileChange" hidden />
              <template v-if="!fileName">
                <div class="drop-icon">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <span class="drop-text">{{ t('transcribe.dropHint') }}</span>
                <span class="drop-hint">{{ t('transcribe.dropFormats') }}</span>
              </template>
              <template v-else>
                <div class="file-info">
                  <div class="file-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>
                    </svg>
                  </div>
                  <div class="file-meta">
                    <span class="file-name">{{ fileName }}</span>
                    <span class="file-size">{{ fileSize }}</span>
                  </div>
                  <button class="file-remove" @click.stop="file = null; fileName = ''; fileSize = ''">&times;</button>
                </div>
              </template>
            </label>
          </div>
        </div>

        <div v-else class="url-area">
          <input v-model="url" type="text" :placeholder="t('transcribe.urlPlaceholder')" class="url-input" />
        </div>

        <div class="engine-row">
          <label class="engine-label">{{ t('transcribe.engine') }}</label>
          <select v-model="selectedEngine" class="engine-select">
            <option v-for="eng in engines" :key="eng.name" :value="eng.name">
              {{ eng.name }} — {{ eng.model_name }}
            </option>
          </select>
        </div>

        <div class="streaming-row">
          <label class="streaming-label">
            <input type="checkbox" v-model="streamingEnabled" class="streaming-checkbox" />
            <span>{{ t('transcribe.streaming') }}</span>
          </label>
          <span class="streaming-hint">{{ streamingEnabled ? t('transcribe.streamingHintRealtime') : t('transcribe.streamingHintWait') }}</span>
        </div>

        <p v-if="error" class="error-msg">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          {{ error }}
        </p>

        <div class="action-row">
          <button v-if="!isTranscribing" class="btn-start" @click="startTranscribe">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            {{ t('transcribe.start') }}
          </button>
          <button v-else class="btn-stop" @click="cancelTranscribe">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
            {{ t('transcribe.stop') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 右侧：识别结果 -->
    <div class="right-col">
      <div class="card result-card">
        <div class="result-toolbar">
          <div class="result-tabs">
            <button :class="{ active: activeTab === 'srt' }" @click="activeTab = 'srt'">{{ t('transcribe.srtTab') }}</button>
            <button :class="{ active: activeTab === 'text' }" @click="activeTab = 'text'">{{ t('transcribe.textTab') }}</button>
          </div>
          <div class="result-actions">
            <span v-if="isTranscribing" class="status-badge running">
              <span class="pulse"></span> {{ t('transcribe.recognizing') }}
            </span>
            <span v-else-if="segments.length" class="status-badge done">
              {{ resultText ? t('transcribe.completed') : t('transcribe.ready') }}
            </span>
            <button v-if="resultText" class="icon-btn" :title="t('transcribe.copy')" @click="copyResult">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
            <button v-if="resultText" class="icon-btn" :title="t('transcribe.saveSrt')" @click="saveResult">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="result-content" ref="resultRef">
          <pre v-if="resultText">{{ activeTab === 'srt' ? resultText : buildText(segments) }}</pre>
          <div v-else class="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
            <p>{{ t('transcribe.emptyTitle') }}</p>
            <span>{{ t('transcribe.emptyHint') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.transcribe-page {
  display: flex;
  gap: 20px;
  padding: 24px;
  height: 100vh;
  min-height: 0;
  overflow: hidden;
}

.left-col {
  width: 360px;
  flex-shrink: 0;
}

.right-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.card {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04);
}

/* 输入卡片 */
.input-card {
  padding: 24px;
  height: fit-content;
}

.card-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 4px;
}

.subtitle {
  font-size: 13px;
  color: #86868b;
  margin-bottom: 20px;
}

.mode-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 18px;
}

.mode-tabs button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  background: #f5f5f7;
  color: #6e6e73;
  border-radius: 8px;
  transition: all 0.2s;
}

.mode-tabs button:hover {
  background: #e8e8ed;
}

.mode-tabs button.active {
  background: #1d1d1f;
  color: #fff;
}

/* 文件拖拽区 */
.drop-zone {
  border: 2px dashed #d2d2d7;
  border-radius: 12px;
  transition: all 0.2s;
  margin-bottom: 18px;
}

.drop-zone:hover,
.drop-zone.dragging {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.04);
}

.drop-zone.has-file {
  border-style: solid;
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.04);
}

.drop-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 20px;
  cursor: pointer;
}

.drop-icon {
  color: #86868b;
  margin-bottom: 10px;
}

.drop-text {
  font-size: 14px;
  font-weight: 500;
  color: #1d1d1f;
  margin-bottom: 4px;
}

.drop-hint {
  font-size: 12px;
  color: #86868b;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.file-icon {
  color: #667eea;
  flex-shrink: 0;
}

.file-meta {
  flex: 1;
  min-width: 0;
}

.file-meta .file-name {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #1d1d1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta .file-size {
  font-size: 12px;
  color: #86868b;
}

.file-remove {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f7;
  border-radius: 50%;
  font-size: 16px;
  color: #6e6e73;
  flex-shrink: 0;
  transition: all 0.2s;
}

.file-remove:hover {
  background: #e8e8ed;
  color: #1d1d1f;
}

/* URL 输入 */
.url-input {
  width: 100%;
  padding: 11px 14px;
  border: 1.5px solid #d2d2d7;
  border-radius: 10px;
  font-size: 14px;
  transition: border-color 0.2s;
  margin-bottom: 18px;
}

.url-input:focus {
  border-color: #667eea;
}

/* 引擎选择 */
.engine-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.engine-label {
  font-size: 13px;
  font-weight: 500;
  color: #6e6e73;
  white-space: nowrap;
}

.engine-select {
  flex: 1;
  padding: 9px 12px;
  border: 1.5px solid #d2d2d7;
  border-radius: 10px;
  font-size: 14px;
  background: #fff;
  color: #1d1d1f;
  transition: border-color 0.2s;
}

.engine-select:focus {
  border-color: #667eea;
}

/* 流式开关 */
.streaming-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.streaming-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #6e6e73;
  cursor: pointer;
}

.streaming-checkbox {
  width: 16px;
  height: 16px;
  accent-color: #667eea;
  cursor: pointer;
}

.streaming-hint {
  font-size: 12px;
  color: #86868b;
}

/* 错误 */
.error-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #ff3b30;
  margin-bottom: 16px;
  padding: 10px 12px;
  background: rgba(255, 59, 48, 0.06);
  border-radius: 8px;
}

/* 操作按钮 */
.action-row {
  display: flex;
  gap: 10px;
}

.btn-start {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 500;
  transition: opacity 0.2s, transform 0.1s;
}

.btn-start:hover {
  opacity: 0.92;
}

.btn-start:active {
  transform: scale(0.98);
}

.btn-stop {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  background: #ff3b30;
  color: #fff;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 500;
  transition: opacity 0.2s;
}

.btn-stop:hover {
  opacity: 0.9;
}

/* 结果卡片 */
.result-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.result-tabs {
  display: flex;
  gap: 4px;
  background: #f5f5f7;
  border-radius: 8px;
  padding: 3px;
}

.result-tabs button {
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #6e6e73;
  border-radius: 6px;
  transition: all 0.2s;
}

.result-tabs button.active {
  background: #fff;
  color: #1d1d1f;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 20px;
}

.status-badge.running {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.status-badge.done {
  background: rgba(52, 199, 89, 0.1);
  color: #34c759;
}

.pulse {
  width: 6px;
  height: 6px;
  background: #667eea;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f7;
  border-radius: 8px;
  color: #6e6e73;
  transition: all 0.2s;
}

.icon-btn:hover {
  background: #e8e8ed;
  color: #1d1d1f;
}

.result-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  min-height: 0;
  scroll-behavior: smooth;
}

.result-content pre {
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #1d1d1f;
  white-space: pre-wrap;
  word-break: break-all;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 300px;
  color: #86868b;
}

.empty-state svg {
  margin-bottom: 16px;
  color: #d2d2d7;
}

.empty-state p {
  font-size: 15px;
  font-weight: 500;
  color: #6e6e73;
  margin-bottom: 4px;
}

.empty-state span {
  font-size: 13px;
  color: #aeaeb2;
}
</style>
