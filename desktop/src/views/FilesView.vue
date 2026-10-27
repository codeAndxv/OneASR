<template>
  <div class="files-view">
    <!-- Top Configuration & Dropzone -->
    <div class="drop-section" :class="{ dragging: isDragging }" @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="handleDrop" @click="triggerFileInput">
      <input ref="fileInput" type="file" accept="audio/*,video/*,.mp3,.wav,.m4a,.mp4,.mkv,.flac,.ogg,.webm,.aac" style="display: none" @change="handleFileSelect" />

      <div class="dropzone-content">
        <svg viewBox="0 0 24 24" class="upload-icon" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <div class="drop-text-primary">{{ selectedFile ? selectedFile.name : t('dropzoneTitle') }}</div>
        <div class="drop-text-secondary">{{ selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB` : t('dropzoneHint') }}</div>
      </div>
    </div>

    <!-- Active File Action Bar -->
    <div v-if="selectedFile" class="action-bar">
      <div class="model-select-group">
        <span class="bar-label">{{ t('selectModel') }}:</span>
        <select v-model="selectedModel" class="custom-select" :disabled="isTranscribing">
          <option value="sensevoice-small">SenseVoice-Small (极速)</option>
          <option value="whisper-large-v3-turbo">Whisper-Large-v3-Turbo (高精度)</option>
          <option value="funasr-paraformer">FunASR Paraformer</option>
        </select>
      </div>

      <button class="transcribe-btn" :class="{ loading: isTranscribing }" :disabled="isTranscribing" @click="startTranscribe">
        <span v-if="isTranscribing" class="btn-spinner"></span>
        <span>{{ isTranscribing ? currentStageText : t('btnStartTranscribe') }}</span>
      </button>
    </div>

    <!-- Subtitle Segment Viewer & Export Bar -->
    <div class="result-section">
      <div class="result-toolbar">
        <span class="toolbar-title">字幕与分段预览 ({{ segments.length }} 句)</span>
        <div class="export-buttons">
          <button class="tool-btn" :disabled="!fullText" @click="copyAllText">
            {{ copied ? '✓ 已复制' : '复制全文' }}
          </button>
          <button class="tool-btn" :disabled="segments.length === 0" @click="exportFile('srt')">
            {{ t('exportSrt') }}
          </button>
          <button class="tool-btn" :disabled="segments.length === 0" @click="exportFile('vtt')">
            {{ t('exportVtt') }}
          </button>
          <button class="tool-btn" :disabled="!fullText" @click="exportFile('txt')">
            {{ t('exportTxt') }}
          </button>
        </div>
      </div>

      <div class="segments-list">
        <div v-if="segments.length === 0" class="empty-segments">
          <p>{{ t('subtitleEmpty') }}</p>
        </div>

        <div v-else class="segment-items">
          <div v-for="(seg, idx) in segments" :key="idx" class="segment-row">
            <span class="timestamp-badge">
              {{ formatTime(seg.start) }} → {{ formatTime(seg.end) }}
            </span>
            <span class="segment-text">{{ seg.text }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useI18n } from '../i18n';
import { apiClient } from '../api/client';

const emit = defineEmits(['add-history']);
const { t } = useI18n();

const fileInput = ref(null);
const selectedFile = ref(null);
const selectedModel = ref('whisper-large-v3-turbo');
const isDragging = ref(false);
const isTranscribing = ref(false);
const currentStageText = ref('');
const fullText = ref('');
const segments = ref([]);
const copied = ref(false);

function triggerFileInput() {
  if (fileInput.value) {
    fileInput.value.click();
  }
}

function handleFileSelect(e) {
  const file = e.target.files?.[0];
  if (file) {
    selectedFile.value = file;
    segments.value = [];
    fullText.value = '';
  }
}

function handleDrop(e) {
  isDragging.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) {
    selectedFile.value = file;
    segments.value = [];
    fullText.value = '';
  }
}

async function startTranscribe() {
  if (!selectedFile.value || isTranscribing.value) return;

  isTranscribing.value = true;
  currentStageText.value = t('stageAudioDecode');

  try {
    setTimeout(() => {
      if (isTranscribing.value) currentStageText.value = t('stageInference');
    }, 800);

    const res = await apiClient.transcribeAudio(selectedFile.value, selectedModel.value);
    fullText.value = res.text;
    
    // Normalize segments
    if (res.segments && res.segments.length > 0) {
      segments.value = res.segments;
    } else {
      segments.value = [{ start: 0, end: res.duration || 5, text: res.text }];
    }

    emit('add-history', {
      id: Date.now().toString(),
      type: 'file',
      text: res.text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      model: selectedModel.value,
      duration: Math.round(res.duration || 0),
      latency: res.latencyMs
    });
  } catch (err) {
    console.error('File transcribe failed:', err);
    alert(`转写失败: ${err.message}`);
  } finally {
    isTranscribing.value = false;
  }
}

function formatTime(seconds = 0) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

function copyAllText() {
  navigator.clipboard.writeText(fullText.value);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1800);
}

function exportFile(format) {
  let content = '';
  let filename = `${selectedFile.value?.name || 'transcript'}.${format}`;

  if (format === 'srt') {
    content = segments.value
      .map((seg, i) => `${i + 1}\n${formatSrtTime(seg.start)} --> ${formatSrtTime(seg.end)}\n${seg.text}\n`)
      .join('\n');
  } else if (format === 'vtt') {
    content = 'WEBVTT\n\n' + segments.value
      .map((seg, i) => `${i + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n`)
      .join('\n');
  } else {
    content = fullText.value;
  }

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function formatSrtTime(seconds = 0) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}
</script>

<style scoped>
.files-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px 20px;
  gap: 12px;
  overflow: hidden;
}

.drop-section {
  border: 1.5px dashed var(--border-subtle);
  border-radius: 10px;
  padding: 18px 20px;
  background: rgba(255, 255, 255, 0.015);
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drop-section:hover, .drop-section.dragging {
  border-color: var(--accent-emerald);
  background: var(--accent-emerald-subtle);
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.upload-icon {
  width: 28px;
  height: 28px;
  color: var(--text-muted);
}

.drop-text-primary {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.drop-text-secondary {
  font-size: 11px;
  color: var(--text-muted);
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  padding: 8px 12px;
  border-radius: 8px;
}

.model-select-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  font-size: 11px;
  color: var(--text-muted);
}

.custom-select {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 6px;
  outline: none;
}

.transcribe-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-emerald);
  color: #000;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.transcribe-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(0, 0, 0, 0.2);
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.result-section {
  flex: 1;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.result-toolbar {
  height: 38px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.toolbar-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}

.export-buttons {
  display: flex;
  gap: 6px;
}

.tool-btn {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.tool-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.segments-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
}

.empty-segments {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 12px;
}

.segment-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.segment-row {
  display: flex;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 6px;
  transition: background 0.1s ease;
}

.segment-row:hover {
  background: rgba(255, 255, 255, 0.03);
}

.timestamp-badge {
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  color: var(--accent-emerald);
  background: var(--accent-emerald-subtle);
  padding: 2px 6px;
  border-radius: 4px;
  height: fit-content;
  white-space: nowrap;
}

.segment-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  word-break: break-word;
  user-select: text;
  -webkit-user-select: text;
}
</style>
