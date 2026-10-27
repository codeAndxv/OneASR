<template>
  <div class="dictate-view">
    <!-- Top Configuration Bar -->
    <div class="config-bar">
      <!-- Model Selector -->
      <div class="config-item">
        <label class="config-label">{{ t('selectModel') }}</label>
        <select v-model="selectedModel" class="custom-select">
          <option v-for="m in modelOptions" :key="m.id" :value="m.id">
            {{ m.name }}
          </option>
        </select>
      </div>

      <!-- Microphone Selector (Scheme A: Web Audio API) -->
      <div class="config-item mic-item">
        <label class="config-label">{{ t('selectMicrophone') }}</label>
        <select v-model="selectedMicId" class="custom-select" :disabled="isRecording">
          <option value="">{{ t('micDefault') }}</option>
          <option v-for="mic in microphones" :key="mic.deviceId" :value="mic.deviceId">
            {{ mic.label }}
          </option>
        </select>
      </div>
    </div>

    <!-- Center Stage: Mascot, Sound Wave Ring & Big Mic Button -->
    <div class="center-stage">
      <div class="mascot-visual-container">
        <!-- Audio Pulse Ring -->
        <div
          class="pulse-ring"
          :class="{ active: isRecording }"
          :style="{ transform: `scale(${1 + (volume / 100) * 0.35})`, opacity: isRecording ? 0.3 + (volume / 100) * 0.7 : 0 }"
        ></div>

        <!-- Cat Mascot Face (Option 1 Line-Art) -->
        <div class="mascot-circle" :class="{ recording: isRecording }">
          <svg viewBox="0 0 24 24" class="cat-svg" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M12 21a7 7 0 0 1-7-7c0-2.3 1.1-4.3 2.8-5.6l-1.3-4.4 4.5 1.8c.3-.1.7-.2 1-.2s.7.1 1 .2l4.5-1.8-1.3 4.4c1.7 1.3 2.8 3.3 2.8 5.6a7 7 0 0 1-7 7z" />
            <!-- Round Chin & Headphones -->
            <path d="M4 14a2 2 0 0 1 2-2h1v4H6a2 2 0 0 1-2-2zm16 0a2 2 0 0 0-2-2h-1v4h1a2 2 0 0 0 2-2z" />
            <path d="M7 12V9a5 5 0 0 1 10 0v3" />
            <!-- Eyes & Smile -->
            <path d="M9 14.5c.5.5 1 .5 1.5 0" />
            <path d="M13.5 14.5c.5.5 1 .5 1.5 0" />
            <path d="M12 16.5v1" />
          </svg>
        </div>
      </div>

      <!-- Big Record Button -->
      <button
        class="record-btn"
        :class="{ recording: isRecording, loading: isTranscribing }"
        :disabled="isTranscribing"
        @click="toggleRecording"
      >
        <span v-if="isTranscribing" class="btn-spinner"></span>
        <svg v-else-if="!isRecording" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="22"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
        <span class="btn-text">
          {{ isTranscribing ? t('transcribingStatus') : isRecording ? `${t('btnStopRecord')} (${durationSec}s)` : t('btnStartRecord') }}
        </span>
      </button>

      <p class="status-tip">
        {{ isRecording ? t('recordingStatus') : t('idleStatus') }}
      </p>
    </div>

    <!-- Bottom Result & Telemetry Box -->
    <div class="result-box">
      <div class="result-header">
        <div class="metrics-row">
          <span class="metric-pill">
            <span class="metric-label">{{ t('latencyMetric') }}:</span>
            <span class="metric-value">{{ latencyMs }} ms</span>
          </span>
          <span class="metric-pill">
            <span class="metric-label">{{ t('rtfMetric') }}:</span>
            <span class="metric-value">{{ rtf }}x</span>
          </span>
        </div>
        <div class="result-actions">
          <button v-if="transcribedText" class="action-btn" @click="copyResult">
            {{ copied ? '✓ 已复制' : t('copyText') }}
          </button>
          <button v-if="transcribedText" class="action-btn" @click="transcribedText = ''">
            {{ t('clearText') }}
          </button>
        </div>
      </div>

      <div class="text-content" :class="{ placeholder: !transcribedText }">
        {{ transcribedText || t('previewPlaceholder') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useI18n } from '../i18n';
import { AudioEngine } from '../utils/audio';
import { apiClient } from '../api/client';

const emit = defineEmits(['add-history']);
const { t } = useI18n();

const selectedModel = ref('sensevoice-small');
const selectedMicId = ref('');
const microphones = ref([]);
const isRecording = ref(false);
const isTranscribing = ref(false);
const volume = ref(0);
const durationSec = ref(0);
const transcribedText = ref('');
const latencyMs = ref(0);
const rtf = ref('0.00');
const copied = ref(false);

const modelOptions = [
  { id: 'sensevoice-small', name: 'SenseVoice-Small (极速轻量 · 推荐)' },
  { id: 'whisper-large-v3-turbo', name: 'Whisper-Large-v3-Turbo (高精度)' },
  { id: 'funasr-paraformer', name: 'FunASR Paraformer (中文工业级)' },
  { id: 'qwen2-audio-7b', name: 'Qwen2-Audio (语音大模型)' }
];

let audioEngine = null;
let timerInterval = null;

onMounted(async () => {
  audioEngine = new AudioEngine();
  await refreshMicrophones();

  // Listen to device hotplug events
  if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
    navigator.mediaDevices.addEventListener('devicechange', refreshMicrophones);
  }
});

onUnmounted(() => {
  if (isRecording.value) {
    audioEngine.stopRecording();
  }
  if (timerInterval) {
    clearInterval(timerInterval);
  }
  if (navigator.mediaDevices && navigator.mediaDevices.removeEventListener) {
    navigator.mediaDevices.removeEventListener('devicechange', refreshMicrophones);
  }
});

async function refreshMicrophones() {
  microphones.value = await AudioEngine.getMicrophones();
}

async function toggleRecording() {
  if (isRecording.value) {
    await stopAndTranscribe();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    transcribedText.value = '';
    durationSec.value = 0;
    
    await audioEngine.startRecording(
      selectedMicId.value,
      (vol) => {
        volume.value = vol;
      }
    );

    isRecording.value = true;
    timerInterval = setInterval(() => {
      durationSec.value += 1;
    }, 1000);
  } catch (err) {
    console.error('Failed to start recording:', err);
    alert(t('micPermissionDenied'));
  }
}

async function stopAndTranscribe() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  isRecording.value = false;
  isTranscribing.value = true;

  try {
    const wavBlob = await audioEngine.stopRecording();
    if (wavBlob) {
      const result = await apiClient.transcribeAudio(wavBlob, selectedModel.value);
      transcribedText.value = result.text;
      latencyMs.value = result.latencyMs;
      rtf.value = result.rtf;

      // Add to history
      emit('add-history', {
        id: Date.now().toString(),
        type: 'dictate',
        text: result.text,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        model: selectedModel.value,
        duration: durationSec.value,
        latency: result.latencyMs
      });
    }
  } catch (err) {
    console.error('Transcription error:', err);
    transcribedText.value = `[转录失败: ${err.message}]`;
  } finally {
    isTranscribing.value = false;
    volume.value = 0;
  }
}

function copyResult() {
  navigator.clipboard.writeText(transcribedText.value);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 1800);
}
</script>

<style scoped>
.dictate-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px 20px;
  gap: 16px;
  overflow: hidden;
}

.config-bar {
  display: flex;
  gap: 14px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.config-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.custom-select {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  outline: none;
  cursor: pointer;
}

.custom-select:focus {
  border-color: var(--border-focus);
}

.center-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  min-height: 180px;
}

.mascot-visual-container {
  position: relative;
  width: 90px;
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.pulse-ring {
  position: absolute;
  inset: -12px;
  border-radius: 50%;
  border: 2px solid var(--accent-emerald);
  pointer-events: none;
  transition: transform 0.08s ease, opacity 0.08s ease;
}

.mascot-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.mascot-circle.recording {
  color: var(--accent-emerald);
  border-color: rgba(16, 185, 129, 0.4);
  background: var(--accent-emerald-subtle);
}

.cat-svg {
  width: 44px;
  height: 44px;
}

.record-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 30px;
  padding: 10px 24px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.record-btn:hover {
  background: var(--bg-card-hover);
  border-color: rgba(255, 255, 255, 0.15);
}

.record-btn.recording {
  background: rgba(239, 68, 68, 0.15);
  color: var(--accent-red);
  border-color: rgba(239, 68, 68, 0.4);
}

.record-btn.loading {
  opacity: 0.8;
  cursor: not-allowed;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--accent-emerald);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-tip {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 10px;
}

.result-box {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  height: 150px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.result-header {
  height: 38px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.metrics-row {
  display: flex;
  gap: 8px;
}

.metric-pill {
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  background: rgba(255, 255, 255, 0.04);
  padding: 2px 6px;
  border-radius: 4px;
}

.metric-label {
  color: var(--text-muted);
  margin-right: 4px;
}

.metric-value {
  color: var(--accent-emerald);
  font-weight: 600;
}

.result-actions {
  display: flex;
  gap: 6px;
}

.action-btn {
  background: none;
  border: none;
  font-size: 11px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 3px 6px;
  border-radius: 4px;
}

.action-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
}

.text-content {
  flex: 1;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  overflow-y: auto;
  user-select: text;
  -webkit-user-select: text;
}

.text-content.placeholder {
  color: var(--text-muted);
  font-style: italic;
  font-size: 12px;
}
</style>
