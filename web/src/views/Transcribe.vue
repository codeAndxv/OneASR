<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { getEngines, transcribeFileStream, transcribeUrlStream, getStoredApiKey } from '../api'

const engines = ref([])
const selectedEngine = ref('')
const inputMode = ref('file')
const url = ref('')
const file = ref(null)
const fileName = ref('')
const isTranscribing = ref(false)
const segments = ref([])
const resultText = ref('')
const error = ref('')
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

function onFileChange(e) {
  const f = e.target.files[0]
  if (f) {
    file.value = f
    fileName.value = f.name
  }
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')},${String(ms).padStart(3,'0')}`
}

function buildSrt(segList) {
  return segList.map((seg, i) => {
    return `${i + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n`
  }).join('\n')
}

function onSegment(seg) {
  segments.value.push(seg)
  resultText.value = buildSrt(segments.value)
  nextTick(() => {
    const el = document.querySelector('.result-area')
    if (el) el.scrollTop = el.scrollHeight
  })
}

function onDone() {
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
    error.value = '请先在右上角设置中配置 API Key'
    return
  }
  error.value = ''
  segments.value = []
  resultText.value = ''
  isTranscribing.value = true

  if (inputMode.value === 'file') {
    if (!file.value) {
      error.value = '请选择文件'
      isTranscribing.value = false
      return
    }
    xhr = transcribeFileStream(file.value, selectedEngine.value, onSegment, onDone, onError)
  } else {
    if (!url.value.trim()) {
      error.value = '请输入 URL'
      isTranscribing.value = false
      return
    }
    xhr = transcribeUrlStream(url.value.trim(), selectedEngine.value, onSegment, onDone, onError)
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
</script>

<template>
  <div class="transcribe-page">
    <div class="panel">
      <div class="input-section">
        <div class="mode-tabs">
          <button :class="{ active: inputMode === 'file' }" @click="inputMode = 'file'">本地文件</button>
          <button :class="{ active: inputMode === 'url' }" @click="inputMode = 'url'">URL 输入</button>
        </div>

        <div v-if="inputMode === 'file'" class="file-input">
          <label class="file-label">
            <input type="file" accept="audio/*,video/*" @change="onFileChange" hidden />
            <span class="file-btn">选择文件</span>
            <span class="file-name">{{ fileName || '未选择文件' }}</span>
          </label>
        </div>

        <div v-else class="url-input">
          <input v-model="url" type="text" placeholder="输入音视频 URL" />
        </div>

        <div class="controls">
          <div class="engine-select">
            <label>引擎:</label>
            <select v-model="selectedEngine">
              <option v-for="eng in engines" :key="eng.name" :value="eng.name">
                {{ eng.name }} ({{ eng.model_name }})
              </option>
            </select>
          </div>
          <div class="actions">
            <button v-if="!isTranscribing" class="btn-primary" @click="startTranscribe">开始识别</button>
            <button v-else class="btn-danger" @click="cancelTranscribe">停止</button>
            <button class="btn-secondary" :disabled="!resultText" @click="saveResult">保存 SRT</button>
          </div>
        </div>

        <p v-if="error" class="error">{{ error }}</p>
      </div>
    </div>

    <div class="panel result-panel">
      <div class="result-header">
        <h3>识别结果</h3>
        <span v-if="isTranscribing" class="badge">识别中...</span>
        <span v-else-if="segments.length" class="badge done">完成 ({{ segments.length }} 句)</span>
      </div>
      <div class="result-area">
        <pre v-if="resultText">{{ resultText }}</pre>
        <p v-else class="placeholder">识别结果将在此处显示</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.transcribe-page {
  padding: 24px;
  max-width: 960px;
}

.panel {
  background: #fff;
  border-radius: 10px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.mode-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
}

.mode-tabs button {
  padding: 8px 20px;
  font-size: 14px;
  background: #f0f0f0;
  color: #666;
  border: 1px solid #ddd;
  transition: all 0.2s;
}

.mode-tabs button:first-child {
  border-radius: 6px 0 0 6px;
}

.mode-tabs button:last-child {
  border-radius: 0 6px 6px 0;
  border-left: none;
}

.mode-tabs button.active {
  background: #667eea;
  color: #fff;
  border-color: #667eea;
}

.file-label {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  margin-bottom: 16px;
}

.file-btn {
  padding: 8px 16px;
  background: #667eea;
  color: #fff;
  border-radius: 6px;
  font-size: 14px;
  white-space: nowrap;
}

.file-name {
  color: #999;
  font-size: 14px;
}

.url-input input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  margin-bottom: 16px;
}

.url-input input:focus {
  border-color: #667eea;
}

.controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.engine-select {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #666;
}

.engine-select select {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  background: #fff;
}

.actions {
  display: flex;
  gap: 10px;
}

.btn-primary {
  padding: 8px 20px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-danger {
  padding: 8px 20px;
  background: #e74c3c;
  color: #fff;
  border-radius: 6px;
  font-size: 14px;
}

.btn-secondary {
  padding: 8px 20px;
  background: #f0f0f0;
  color: #333;
  border-radius: 6px;
  font-size: 14px;
  border: 1px solid #ddd;
}

.btn-secondary:hover:not(:disabled) {
  background: #e0e0e0;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error {
  color: #e74c3c;
  font-size: 13px;
  margin-top: 12px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.result-header h3 {
  font-size: 16px;
  color: #333;
}

.badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  background: #fff3cd;
  color: #856404;
}

.badge.done {
  background: #d4edda;
  color: #155724;
}

.result-area {
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 8px;
  padding: 16px;
  min-height: 300px;
  max-height: 500px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
}

.result-area pre {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.6;
}

.placeholder {
  color: #666;
  font-size: 14px;
  text-align: center;
  padding-top: 40px;
}
</style>
