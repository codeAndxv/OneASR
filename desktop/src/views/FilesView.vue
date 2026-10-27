<template>
  <div class="files-view">
    <!-- Top Configuration Bar (Always visible, matching DictateView design language) -->
    <div class="config-bar">
      <!-- Model Selector -->
      <div class="config-item">
        <label class="config-label">{{ t('selectModel') }}</label>
        <select v-model="selectedModel" class="custom-select" :disabled="isTranscribing">
          <option value="whisper-large-v3-turbo">Whisper-Large-v3-Turbo (高精度 · 多语言推荐)</option>
          <option value="sensevoice-small">SenseVoice-Small (极速轻量 · 中英粤日韩)</option>
          <option value="paraformer-zh">Paraformer-zh (会议长语音)</option>
          <option value="firered-asr">FireRed-ASR (大参数高鲁棒)</option>
        </select>
      </div>

      <!-- Language Detection -->
      <div class="config-item">
        <label class="config-label">语言识别与断句</label>
        <select v-model="selectedLanguage" class="custom-select" :disabled="isTranscribing">
          <option value="auto">自动识别语言 (Auto Detect)</option>
          <option value="zh">中文普通话 (Mandarin)</option>
          <option value="en">英语 (English)</option>
          <option value="bilingual">中英双语混合识别</option>
        </select>
      </div>
    </div>

    <!-- Hidden native file input -->
    <input
      ref="fileInput"
      type="file"
      accept="audio/*,video/*,.mp3,.wav,.m4a,.mp4,.mkv,.flac,.ogg,.webm,.aac"
      style="display: none"
      @change="handleFileSelect"
    />

    <!-- File Input Section: Dropzone (when empty) vs Active File Card (when selected) -->
    <div
      v-if="!selectedFile"
      class="drop-section"
      :class="{ dragging: isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <div class="dropzone-content">
        <svg viewBox="0 0 24 24" class="upload-icon" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <div class="drop-text-primary">{{ t('dropzoneTitle') }}</div>
        <div class="drop-text-secondary">{{ t('dropzoneHint') }}</div>
      </div>
    </div>

    <!-- Active File Ready Card -->
    <div v-else class="file-card">
      <div class="file-info-group">
        <div class="file-icon-box">
          <svg viewBox="0 0 24 24" class="audio-svg" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 18V5l12-2v13"/>
            <circle cx="6" cy="18" r="3"/>
            <circle cx="18" cy="16" r="3"/>
          </svg>
        </div>
        <div class="file-meta">
          <div class="file-name-row">
            <span class="file-name" :title="selectedFile.name">{{ selectedFile.name }}</span>
            <span class="file-badge">音视频</span>
          </div>
          <div class="file-subtext">
            <span>{{ formatFileSize(selectedFile.size) }}</span>
            <span class="dot-sep">•</span>
            <span>已准备就绪</span>
          </div>
        </div>
      </div>

      <div class="file-actions">
        <button class="secondary-btn" :disabled="isTranscribing" @click="triggerFileInput">
          更换文件
        </button>
        <button
          class="primary-action-btn"
          :class="{ loading: isTranscribing }"
          :disabled="isTranscribing"
          @click="startTranscribe"
        >
          <span v-if="isTranscribing" class="btn-spinner"></span>
          <svg v-else viewBox="0 0 24 24" class="play-icon" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
          <span>{{ isTranscribing ? currentStageText : t('btnStartTranscribe') }}</span>
        </button>
      </div>
    </div>

    <!-- Live Transcription Progress Bar -->
    <div v-if="isTranscribing" class="transcribe-progress-box">
      <div class="progress-info-row">
        <span class="stage-label">{{ currentStageText }}</span>
        <span class="progress-percent">{{ progressPercent }}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar-fill" :style="{ width: `${progressPercent}%` }"></div>
      </div>
    </div>

    <!-- Result / Subtitle Viewer Section -->
    <div class="result-section">
      <div class="result-toolbar">
        <div class="toolbar-left">
          <span class="toolbar-title">字幕与分段预览</span>
          <span class="count-badge">{{ segments.length }} 句</span>
        </div>

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

      <!-- Segment list container -->
      <div class="segments-list">
        <div v-if="segments.length === 0" class="empty-segments">
          <svg viewBox="0 0 24 24" class="empty-icon" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          <p>{{ t('subtitleEmpty') }}</p>
        </div>

        <div v-else class="segment-items">
          <div v-for="(seg, idx) in segments" :key="idx" class="segment-row">
            <div class="timestamp-badge">
              {{ formatTime(seg.start) }} → {{ formatTime(seg.end) }}
            </div>
            <div class="segment-text">{{ seg.text }}</div>
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
const selectedLanguage = ref('auto');
const isDragging = ref(false);
const isTranscribing = ref(false);
const progressPercent = ref(0);
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
    loadFile(file);
  }
}

function handleDrop(e) {
  isDragging.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) {
    loadFile(file);
  }
}

function loadFile(file) {
  selectedFile.value = file;
  segments.value = [];
  fullText.value = '';
  progressPercent.value = 0;
}

function formatFileSize(bytes = 0) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

async function startTranscribe() {
  if (!selectedFile.value || isTranscribing.value) return;

  isTranscribing.value = true;
  progressPercent.value = 15;
  currentStageText.value = t('stageAudioDecode') || '音频流解码与重采样...';

  // Progress animation ticker
  const timer = setInterval(() => {
    if (progressPercent.value < 85) {
      progressPercent.value += 12;
      if (progressPercent.value > 45) {
        currentStageText.value = t('stageInference') || '神经网络分块推理中...';
      }
    }
  }, 400);

  try {
    const res = await apiClient.transcribeAudio(selectedFile.value, selectedModel.value);
    clearInterval(timer);
    progressPercent.value = 100;
    currentStageText.value = t('stageTimestamps') || '对齐精确时间戳...';

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
    clearInterval(timer);
    console.error('File transcribe failed:', err);
    alert(`转写失败: ${err.message}`);
  } finally {
    setTimeout(() => {
      isTranscribing.value = false;
    }, 450);
  }
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

function copyAllText() {
  if (!fullText.value) return;
  navigator.clipboard.writeText(fullText.value);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1800);
}

function exportFile(format) {
  let content = '';
  const baseName = selectedFile.value?.name ? selectedFile.value.name.replace(/\.[^/.]+$/, '') : 'transcript';
  const filename = `${baseName}.${format}`;

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

/* 1. Top Configuration Bar */
.config-bar {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-shrink: 0;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.config-label {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-secondary);
}

.custom-select {
  padding: 8px 12px;
  font-size: 12.5px;
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.custom-select:focus {
  border-color: var(--accent-emerald);
}

/* 2. Dropzone (Empty State) */
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
  flex-shrink: 0;
}

.drop-section:hover,
.drop-section.dragging {
  border-color: var(--accent-emerald);
  background: var(--accent-emerald-subtle);
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.upload-icon {
  width: 24px;
  height: 24px;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.drop-text-primary {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.drop-text-secondary {
  font-size: 11px;
  color: var(--text-muted);
}

/* 3. Active File Ready Card */
.file-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  flex-shrink: 0;
  gap: 12px;
}

.file-info-group {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.file-icon-box {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.audio-svg {
  width: 18px;
  height: 18px;
}

.file-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.file-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

.file-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}

.file-subtext {
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot-sep {
  color: var(--text-muted);
}

.file-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.secondary-btn {
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.secondary-btn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.primary-action-btn {
  padding: 6px 16px;
  font-size: 12.5px;
  font-weight: 600;
  background: var(--accent-emerald);
  color: #0b0f17;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: opacity 0.15s ease;
}

.primary-action-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.primary-action-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.play-icon {
  width: 12px;
  height: 12px;
}

.btn-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid rgba(11, 15, 23, 0.25);
  border-top-color: #0b0f17;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 4. Transcribe Progress Box */
.transcribe-progress-box {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.progress-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11.5px;
}

.stage-label {
  color: var(--accent-emerald);
  font-weight: 500;
}

.progress-percent {
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.progress-track {
  width: 100%;
  height: 4px;
  background: var(--bg-elevated);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--accent-emerald);
  transition: width 0.3s ease;
}

/* 5. Subtitle & Result Section */
.result-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  overflow: hidden;
  min-height: 200px;
}

.result-toolbar {
  height: 42px;
  padding: 0 14px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background: var(--bg-surface);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.count-badge {
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}

.export-buttons {
  display: flex;
  gap: 6px;
}

.tool-btn {
  padding: 4px 10px;
  font-size: 11.5px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
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
  padding: 12px 14px;
}

.empty-segments {
  height: 100%;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.empty-icon {
  width: 28px;
  height: 28px;
  opacity: 0.5;
}

.segment-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.segment-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  transition: background 0.15s ease;
}

.segment-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.timestamp-badge {
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

.segment-text {
  font-size: 12.5px;
  color: var(--text-primary);
  line-height: 1.5;
  user-select: text;
  -webkit-user-select: text;
}
</style>
