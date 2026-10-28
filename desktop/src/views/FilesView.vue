<template>
  <div class="files-view">
    <!-- Top Configuration Bar (Always visible, matching DictateView design language) -->
    <div class="config-bar">
      <!-- Model Selector (Dynamic: Only displays on-disk ready models) -->
      <div class="config-item">
        <label class="config-label">{{ t('selectModel') }}</label>
        <select v-model="selectedModel" class="custom-select" :disabled="isTranscribing">
          <option v-if="readyModels.length === 0" value="" disabled>暂无可用模型 (请先前往模型管理下载)</option>
          <option
            v-for="m in readyModels"
            :key="m.id"
            :value="m.id"
          >
            {{ m.name }}{{ m.isLoaded ? ' (● 内存驻留)' : '' }} · {{ getEngineDisplayName(m.engine) }}
          </option>
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
          v-if="isTranscribing"
          class="cancel-btn"
          @click="cancelCurrentTask"
        >
          取消转写
        </button>
        <button
          v-else
          class="primary-action-btn"
          @click="startTranscribe"
        >
          <svg viewBox="0 0 24 24" class="play-icon" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
          <span>{{ t('btnStartTranscribe') }}</span>
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

    <!-- Error Banner -->
    <div v-if="errorMessage" class="error-banner">
      <div class="error-banner-content">
        <svg viewBox="0 0 24 24" class="error-icon" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="error-msg">{{ errorMessage }}</span>
      </div>
      <button class="close-error-btn" @click="errorMessage = ''" aria-label="关闭">✕</button>
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
import { ref, onMounted, onUnmounted } from 'vue';
import { useI18n } from '../i18n';
import { apiClient } from '../api/client';

const emit = defineEmits(['add-history']);
const { t } = useI18n();

const fileInput = ref(null);
const selectedFile = ref(null);
const selectedFilePath = ref('');
const importedFileUuid = ref('');
const activeTaskId = ref('');
let pollTimer = null;
let unlistenDragDrop = null;

const selectedModel = ref('sensevoice-small');
const readyModels = ref([]);
const selectedLanguage = ref('auto');
const isDragging = ref(false);
const isTranscribing = ref(false);
const progressPercent = ref(0);
const currentStageText = ref('');
const fullText = ref('');
const segments = ref([]);
const copied = ref(false);
const errorMessage = ref('');

function getEngineDisplayName(eng) {
  const map = {
    funasr: 'FunASR',
    whisper: 'Faster-Whisper',
    firered: 'FireRed ASR',
    qwen: 'Qwen ASR',
    xasr: 'Sherpa-ONNX'
  };
  return map[eng] || eng || 'ASR';
}

async function loadAvailableModels() {
  try {
    const data = await apiClient.getModels();
    const allModels = data.data || data.models || [];
    if (Array.isArray(allModels)) {
      // 严格仅加载支持 FileASR（文件转录）能力的就绪模型，排除流式专有模型与辅助模型
      readyModels.value = allModels
        .filter((m) => m.status === 'ready' && Array.isArray(m.categories) && m.categories.includes('FileASR'))
        .map((m) => ({
          id: m.id,
          name: m.name || m.id,
          engine: m.owned_by || 'whisper',
          isLoaded: !!m.loaded,
          size_bytes: m.size_on_disk || 0
        }));

      // Set default selected model
      if (readyModels.value.length > 0) {
        const loadedModel = readyModels.value.find((m) => m.isLoaded);
        const senseVoice = readyModels.value.find((m) => m.id === 'sensevoice-small');
        const turbo = readyModels.value.find((m) => m.id === 'whisper-large-v3-turbo');
        if (loadedModel) {
          selectedModel.value = loadedModel.id;
        } else if (senseVoice) {
          selectedModel.value = senseVoice.id;
        } else if (turbo) {
          selectedModel.value = turbo.id;
        } else if (!readyModels.value.some((m) => m.id === selectedModel.value)) {
          selectedModel.value = readyModels.value[0].id;
        }
      }
    }
  } catch (err) {
    console.warn('[FilesView] Failed to load ready models:', err);
  }
}

onMounted(async () => {
  await loadAvailableModels();

  // 监听 Tauri 原生 macOS Finder 拖拽事件
  try {
    const { getCurrentWebview } = await import('@tauri-apps/api/webview');
    unlistenDragDrop = await getCurrentWebview().onDragDropEvent(async (event) => {
      if (event.payload.type === 'enter' || event.payload.type === 'over') {
        isDragging.value = true;
      } else if (event.payload.type === 'drop') {
        isDragging.value = false;
        const paths = event.payload.paths;
        if (paths && paths.length > 0) {
          await handleNativeFilePath(paths[0]);
        }
      } else {
        isDragging.value = false;
      }
    });
  } catch (err) {
    console.debug('[FilesView] Webview drag-drop fallback mode', err);
  }
});

onUnmounted(() => {
  if (unlistenDragDrop) {
    unlistenDragDrop();
  }
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
});

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

async function handleNativeFilePath(pathStr) {
  if (!pathStr) return;
  const fileName = pathStr.split(/[/\\]/).pop() || 'media_file';
  selectedFilePath.value = pathStr;
  selectedFile.value = {
    name: fileName,
    size: 0,
    path: pathStr
  };
  segments.value = [];
  fullText.value = '';
  errorMessage.value = '';
  progressPercent.value = 0;
  importedFileUuid.value = '';

  try {
    const res = await apiClient.importLocalFile(pathStr);
    if (res && res.file_id) {
      importedFileUuid.value = res.file_id;
      if (res.file_size) {
        selectedFile.value.size = res.file_size;
      }
    }
  } catch (err) {
    console.warn('[FilesView] Local file fast import failed:', err);
  }
}

function loadFile(file) {
  selectedFile.value = file;
  selectedFilePath.value = '';
  importedFileUuid.value = '';
  segments.value = [];
  fullText.value = '';
  errorMessage.value = '';
  progressPercent.value = 0;
}

function formatFileSize(bytes = 0) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

async function cancelCurrentTask() {
  if (!activeTaskId.value) {
    isTranscribing.value = false;
    return;
  }
  try {
    await apiClient.cancelTranscriptionTask(activeTaskId.value);
  } catch (err) {
    console.warn('[FilesView] Cancel task error:', err);
  } finally {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    isTranscribing.value = false;
    errorMessage.value = '已取消当前转写任务';
  }
}

async function startTranscribe() {
  if (!selectedFile.value || isTranscribing.value) return;

  errorMessage.value = '';
  isTranscribing.value = true;
  progressPercent.value = 5;
  currentStageText.value = '准备音视频资源与特征校验...';
  const startTime = performance.now();

  try {
    let fileUuid = importedFileUuid.value;

    // 1. 如果尚未通过本地路径秒传导入，则上传至 /v1/x/files
    if (!fileUuid) {
      currentStageText.value = '上传音频文件与特征哈希...';
      const uploadRes = await apiClient.uploadFile(selectedFile.value);
      fileUuid = uploadRes.file_id;
      importedFileUuid.value = fileUuid;
    }

    // 2. 创建异步转写任务 (OneASR Extended /v1/x/audio/transcriptions)
    progressPercent.value = 10;
    currentStageText.value = '初始化转写引擎与音频解码...';
    const taskRes = await apiClient.createTranscriptionTask(
      fileUuid,
      selectedModel.value,
      selectedLanguage.value
    );
    const taskId = taskRes.task_id;
    activeTaskId.value = taskId;

    // 3. 实时轮询真实推理进度与分段流
    pollTimer = setInterval(async () => {
      try {
        const task = await apiClient.getTranscriptionTask(taskId);
        if (task.progress !== undefined && task.progress !== null) {
          const p = Math.round(task.progress * 100);
          progressPercent.value = Math.max(progressPercent.value, Math.min(99, p));
        }

        if (task.status === 'processing') {
          currentStageText.value = `神经网络转录中 (${progressPercent.value}%)...`;
          if (task.segments && task.segments.length > 0) {
            segments.value = task.segments;
          }
        } else if (task.status === 'completed') {
          clearInterval(pollTimer);
          pollTimer = null;
          progressPercent.value = 100;
          currentStageText.value = '转写完成';

          fullText.value = task.text || '';
          if (task.segments && task.segments.length > 0) {
            segments.value = task.segments;
          } else {
            segments.value = [{ start: 0, end: task.total_time || 0, text: task.text || '' }];
          }

          const elapsedMs = Math.round(performance.now() - startTime);
          emit('add-history', {
            id: Date.now().toString(),
            type: 'file',
            text: task.text,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            model: selectedModel.value,
            duration: Math.round(task.total_time || 0),
            latency: elapsedMs,
            filename: selectedFile.value?.name || '',
            segments: segments.value || []
          });

          setTimeout(() => {
            isTranscribing.value = false;
          }, 300);
        } else if (task.status === 'failed') {
          clearInterval(pollTimer);
          pollTimer = null;
          console.error('[FilesView] Task failed:', task.error_message);
          errorMessage.value = task.error_message || '转录处理失败，请重试';
          isTranscribing.value = false;
        } else if (task.status === 'cancelled') {
          clearInterval(pollTimer);
          pollTimer = null;
          errorMessage.value = '转写任务已取消';
          isTranscribing.value = false;
        }
      } catch (pollErr) {
        console.warn('[FilesView] Polling task status:', pollErr);
      }
    }, 350);

  } catch (err) {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    console.error('File transcribe failed:', err);
    errorMessage.value = err.message || '转写处理遇到异常，请检查音频格式或重试';
    isTranscribing.value = false;
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

.cancel-btn {
  padding: 6px 14px;
  font-size: 12.5px;
  font-weight: 500;
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s ease;
}

.cancel-btn:hover {
  background: rgba(239, 68, 68, 0.22);
  border-color: rgba(239, 68, 68, 0.5);
  color: #fca5a5;
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

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 8px;
  padding: 10px 14px;
  margin-top: 12px;
  font-size: 12.5px;
  color: #f87171;
}

.error-banner-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.error-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  stroke: #ef4444;
}

.close-error-btn {
  background: transparent;
  border: none;
  color: #999;
  cursor: pointer;
  padding: 2px 6px;
  font-size: 13px;
  border-radius: 4px;
  transition: all 0.15s;
}

.close-error-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}
</style>
