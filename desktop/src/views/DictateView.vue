<template>
  <div class="dictate-view">
    <!-- Top Configuration Bar (Symmetric with FilesView) -->
    <div class="config-bar">
      <!-- Model Selector -->
      <div class="config-item">
        <label class="config-label">{{ t('selectModel') }}</label>
        <select v-model="selectedModel" class="custom-select" :disabled="isRecording || isTranscribing">
          <option v-for="m in modelOptions" :key="m.id" :value="m.id">
            {{ m.name }}
          </option>
        </select>
      </div>

      <!-- Language Selector -->
      <div class="config-item">
        <label class="config-label">语言识别</label>
        <select v-model="selectedLanguage" class="custom-select" :disabled="isRecording || isTranscribing">
          <option value="auto">自动识别语言 (Auto Detect)</option>
          <option value="zh">中文普通话 (Chinese)</option>
          <option value="en">英语 (English)</option>
          <option value="yue">粤语 (Cantonese)</option>
          <option value="ja">日语 (Japanese)</option>
          <option value="ko">韩语 (Korean)</option>
        </select>
      </div>

      <!-- Microphone Selector -->
      <div class="config-item">
        <label class="config-label">{{ t('selectMicrophone') }}</label>
        <select v-model="selectedMicId" class="custom-select" :disabled="isRecording || isTranscribing">
          <option value="">{{ t('micDefault') }}</option>
          <option v-for="mic in microphones" :key="mic.deviceId" :value="mic.deviceId">
            {{ mic.label }}
          </option>
        </select>
      </div>

      <!-- Telemetry Metrics Pill -->
      <div class="telemetry-box">
        <div class="telemetry-item">
          <span class="telemetry-label">{{ t('latencyMetric') }}:</span>
          <span class="telemetry-val">{{ latencyMs }} ms</span>
        </div>
        <span class="telemetry-divider">|</span>
        <div class="telemetry-item">
          <span class="telemetry-label">{{ t('rtfMetric') }}:</span>
          <span class="telemetry-val">{{ rtf }}x</span>
        </div>
      </div>
    </div>

    <!-- Hero Immersive Text Canvas -->
    <div class="text-canvas-card">
      <!-- Canvas Status & Action Header -->
      <div class="canvas-header">
        <div class="status-left">
          <span
            class="status-dot"
            :class="{
              recording: isRecording,
              transcribing: isTranscribing,
              error: !!errorMessage,
              has_text: !isRecording && !isTranscribing && transcribedText
            }"
          ></span>
          <span class="status-text" :class="{ 'text-error': !!errorMessage }">{{ currentStatusText }}</span>
          <span v-if="charCount > 0" class="char-badge">({{ charCount }} 字)</span>
        </div>

        <div class="canvas-actions">
          <button
            class="action-btn"
            :disabled="!transcribedText && finalizedSentences.length === 0"
            :title="t('copyText')"
            @click="copyResult"
          >
            {{ copied ? '✓ 已复制' : t('copyText') }}
          </button>
          <button
            class="action-btn"
            :disabled="finalizedSentences.length === 0"
            :title="t('exportSrt')"
            @click="exportFile('srt')"
          >
            {{ t('exportSrt') }}
          </button>
          <button
            class="action-btn"
            :disabled="finalizedSentences.length === 0"
            :title="t('exportVtt')"
            @click="exportFile('vtt')"
          >
            {{ t('exportVtt') }}
          </button>
          <button
            class="action-btn"
            :disabled="!transcribedText && finalizedSentences.length === 0"
            :title="t('clearText')"
            @click="clearText"
          >
            {{ t('clearText') }}
          </button>
        </div>
      </div>

      <!-- Scrollable Text Body -->
      <div class="canvas-body" ref="canvasBody">
        <div v-if="!transcribedText && finalizedSentences.length === 0 && !isRecording && !isTranscribing" class="placeholder-box">
          <svg viewBox="0 0 24 24" class="placeholder-icon" :class="{ 'error-icon': !!errorMessage }" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="22"/>
          </svg>
          <p v-if="errorMessage" class="placeholder-error">{{ errorMessage }}</p>
          <template v-else>
            <p class="placeholder-main">点击下方麦克风或按空格键开始实时听写</p>
            <p class="placeholder-sub">毫秒级流式文本与延迟检测 · 端侧神经推理不经云端</p>
          </template>
        </div>

        <div v-else class="dictate-stream">
          <!-- Segmented Sentences with Timestamps -->
          <div
            v-for="(seg, idx) in finalizedSentences"
            :key="seg.id || idx"
            class="dictate-row"
          >
            <div class="timestamp-badge">
              {{ formatTime(seg.start) }} → {{ formatTime(seg.end) }}
            </div>
            <div class="dictate-text">{{ seg.text }}</div>
          </div>

          <!-- Active Live Streaming Sentence -->
          <div
            v-if="liveSentencePreview || (isRecording && finalizedSentences.length === 0)"
            class="dictate-row live-row"
          >
            <div class="timestamp-badge live-badge">
              <span class="live-pulse-dot"></span>
              {{ formatTime(currentLiveStart) }} → {{ formatTime(durationSec) }}
            </div>
            <div class="dictate-text live-text">
              {{ liveSentencePreview }}
              <span v-if="isRecording || isTranscribing" class="typing-cursor"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Floating Bottom Audio Dock -->
      <div class="floating-dock">
        <!-- Left: Waveform animation & Timer -->
        <div class="dock-left">
          <div class="wave-visualizer">
            <span
              v-for="(h, idx) in waveBars"
              :key="idx"
              class="wave-bar"
              :class="{ active: isRecording }"
              :style="{ height: `${isRecording ? h : 4}px` }"
            ></span>
          </div>
          <span class="duration-timer">{{ formattedDuration }}</span>
        </div>

        <!-- Center: Capsule Record Button -->
        <div class="dock-center">
          <button
            class="dock-record-btn"
            :class="{ recording: isRecording, loading: isTranscribing }"
            :disabled="isTranscribing"
            @click="toggleRecording"
          >
            <span v-if="isTranscribing" class="btn-spinner"></span>
            <svg v-else-if="!isRecording" viewBox="0 0 24 24" class="btn-mic-icon" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="22"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" class="btn-stop-icon" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
            <span class="btn-caption">
              {{ isTranscribing ? t('transcribingStatus') : isRecording ? t('btnStopRecord') : t('btnStartRecord') }}
            </span>
          </button>
        </div>

        <!-- Right: Spacebar Shortcut Hint -->
        <div class="dock-right">
          <span class="shortcut-tip">
            按 <kbd class="kbd-badge">Space</kbd> 切换录音
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from '../i18n';
import { AudioEngine } from '../utils/audio';
import { apiClient } from '../api/client';

const emit = defineEmits(['add-history']);
const { t } = useI18n();

const selectedModel = ref('sensevoice-small');
const selectedLanguage = ref('auto');
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
const errorMessage = ref('');
const canvasBody = ref(null);

const waveBars = ref([4, 4, 4, 4, 4, 4, 4, 4]);

const modelOptions = ref([
  { id: 'sensevoice-small', name: 'SenseVoice-Small (极速轻量 · 推荐)' }
]);

let realtimeWs = null;
const finalizedSentences = ref([]);
const liveSentencePreview = ref('');

function connectRealtimeWebSocket() {
  return new Promise((resolve) => {
    try {
      const apiKey = localStorage.getItem('oneasr_api_key') || 'sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u';
      // 动态自适应 WebSocket 地址（支持本地与远程配置）
      const wsUrl = `${apiClient.getWsBaseUrl()}/v1/x/realtime`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        const updateMsg = {
          type: 'session.update',
          session: {
            api_key: apiKey, // 首帧在 JSON 消息体中传递 api_key
            audio: {
              input: {
                format: { type: 'audio/pcm', rate: 16000 },
                transcription: {
                  model: selectedModel.value,
                  language: selectedLanguage.value !== 'auto' ? selectedLanguage.value : null
                }
              }
            }
          }
        };
        ws.send(JSON.stringify(updateMsg));
        resolve(ws);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'conversation.item.input_audio_transcription.delta') {
            const preview = (msg.text || msg.delta || '').trim();
            liveSentencePreview.value = preview;
            const finalizedText = finalizedSentences.value.map((s) => s.text).join(' ');
            transcribedText.value = (finalizedText + (preview ? (finalizedText ? ' ' : '') + preview : '')).trim();
            scrollToBottom();
          } else if (
            msg.type === 'conversation.item.input_audio_transcription.sentence' ||
            msg.type === 'conversation.item.input_audio_transcription.completed'
          ) {
            const text = (msg.text || msg.transcript || '').trim();
            if (text) {
              const itemId = msg.item_id || `item_${finalizedSentences.value.length}`;
              const prevEnd = finalizedSentences.value.length > 0 ? finalizedSentences.value[finalizedSentences.value.length - 1].end : 0;
              const start = typeof msg.start === 'number' ? msg.start : prevEnd;
              const end = typeof msg.end === 'number' ? msg.end : (durationSec.value || start);

              const existingIdx = finalizedSentences.value.findIndex((s) => s.id === itemId);
              if (existingIdx >= 0) {
                // Update in-place to prevent duplicate push when both sentence and completed are received
                finalizedSentences.value[existingIdx] = {
                  id: itemId,
                  start: finalizedSentences.value[existingIdx].start,
                  end: Math.max(finalizedSentences.value[existingIdx].end, end),
                  text: text || finalizedSentences.value[existingIdx].text
                };
              } else {
                finalizedSentences.value.push({ id: itemId, start, end, text });
              }

              liveSentencePreview.value = '';
              transcribedText.value = finalizedSentences.value.map((s) => s.text).join(' ');
              scrollToBottom();
            }
          } else if (msg.type === 'error') {
            console.warn('[Dictate WS] Server error:', msg.error);
          }
        } catch (e) {
          console.debug('[Dictate WS] parse error:', e);
        }
      };

      ws.onerror = (err) => {
        console.warn('[Dictate WS] Connection notice (will use standard fallback if needed):', err);
        resolve(null);
      };

      ws.onclose = () => {
        realtimeWs = null;
      };
    } catch (e) {
      console.warn('[Dictate WS] Init error:', e);
      resolve(null);
    }
  });
}

async function loadAvailableModels() {
  try {
    const data = await apiClient.getModels();
    const allModels = data.data || data.models || [];
    if (Array.isArray(allModels)) {
      // Realtime dictation only accepts models with RealtimeASR capability (e.g. SenseVoice, X-ASR)
      const ready = allModels.filter(
        (m) => m.status === 'ready' && Array.isArray(m.categories) && m.categories.includes('RealtimeASR')
      );
      if (ready.length > 0) {
        modelOptions.value = ready.map((m) => ({
          id: m.id,
          name: `${m.name || m.id}${m.loaded ? ' (● 内存驻留)' : ''}`,
          isLoaded: !!m.loaded
        }));
        const loadedModel = modelOptions.value.find((m) => m.isLoaded);
        const senseVoice = modelOptions.value.find((m) => m.id === 'sensevoice-small');
        if (loadedModel) {
          selectedModel.value = loadedModel.id;
        } else if (senseVoice) {
          selectedModel.value = senseVoice.id;
        } else if (!modelOptions.value.some((m) => m.id === selectedModel.value)) {
          selectedModel.value = modelOptions.value[0].id;
        }
      }
    }
  } catch (err) {
    console.warn('[DictateView] Failed to load ready models:', err);
  }
}

let audioEngine = null;
let timerInterval = null;
let waveTicker = null;

const charCount = computed(() => (transcribedText.value ? transcribedText.value.length : 0));

const formattedDuration = computed(() => {
  const m = String(Math.floor(durationSec.value / 60)).padStart(2, '0');
  const s = String(durationSec.value % 60).padStart(2, '0');
  return `${m}:${s}`;
});

const currentStatusText = computed(() => {
  if (errorMessage.value) {
    return errorMessage.value;
  }
  if (isRecording.value) {
    return '正在收音中 · 实时感知麦克风信号...';
  }
  if (isTranscribing.value) {
    return '正在神经网络分块推理中...';
  }
  if (transcribedText.value) {
    return '转录就绪 · 已同步保存至历史记录';
  }
  return '准备就绪 · 点击下方麦克风或按空格开始';
});

onMounted(async () => {
  audioEngine = new AudioEngine();
  await refreshMicrophones();
  await loadAvailableModels();

  if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
    navigator.mediaDevices.addEventListener('devicechange', refreshMicrophones);
  }

  window.addEventListener('keydown', handleGlobalKeydown);
});

onUnmounted(() => {
  if (realtimeWs) {
    try { realtimeWs.close(); } catch (e) {}
    realtimeWs = null;
  }
  if (isRecording.value) {
    audioEngine.stopRecording();
  }
  if (timerInterval) clearInterval(timerInterval);
  if (waveTicker) clearInterval(waveTicker);
  window.removeEventListener('keydown', handleGlobalKeydown);

  if (navigator.mediaDevices && navigator.mediaDevices.removeEventListener) {
    navigator.mediaDevices.removeEventListener('devicechange', refreshMicrophones);
  }
});

function handleGlobalKeydown(e) {
  if (e.code === 'Space' && !e.target.closest('input, textarea, select')) {
    e.preventDefault();
    toggleRecording();
  }
}

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
    errorMessage.value = '';
    transcribedText.value = '';
    durationSec.value = 0;
    latencyMs.value = 0;
    rtf.value = '0.00';
    finalizedSentences.value = [];
    liveSentencePreview.value = '';

    // 1. 尝试连接真流式 WebSocket (/v1/x/realtime)
    realtimeWs = await connectRealtimeWebSocket();

    // 2. 启动麦克风录音，并流式投递 Float32 PCM16 切片
    await audioEngine.startRecording(
      selectedMicId.value,
      (vol) => {
        volume.value = vol;
      },
      (float32Chunk) => {
        if (realtimeWs && realtimeWs.readyState === WebSocket.OPEN) {
          const b64 = audioEngine.float32ToPcm16Base64(float32Chunk);
          if (b64) {
            realtimeWs.send(
              JSON.stringify({
                type: 'input_audio_buffer.append',
                audio: b64
              })
            );
          }
        }
      }
    );

    isRecording.value = true;
    timerInterval = setInterval(() => {
      durationSec.value += 1;
    }, 1000);

    // Waveform simulation responding to live volume
    waveTicker = setInterval(() => {
      const v = volume.value;
      waveBars.value = [
        Math.max(4, Math.min(18, Math.round(v * 0.5 + Math.random() * 4))),
        Math.max(4, Math.min(22, Math.round(v * 0.7 + Math.random() * 5))),
        Math.max(4, Math.min(26, Math.round(v * 0.9 + Math.random() * 6))),
        Math.max(4, Math.min(28, Math.round(v * 1.1 + Math.random() * 6))),
        Math.max(4, Math.min(26, Math.round(v * 1.0 + Math.random() * 5))),
        Math.max(4, Math.min(22, Math.round(v * 0.8 + Math.random() * 5))),
        Math.max(4, Math.min(18, Math.round(v * 0.6 + Math.random() * 4))),
        Math.max(4, Math.min(14, Math.round(v * 0.4 + Math.random() * 3)))
      ];
    }, 90);
  } catch (err) {
    console.error('Failed to start recording:', err);
    errorMessage.value = `麦克风无法启动: ${err.name || ''} ${err.message || '请检查系统偏好设置中 OneASR 的麦克风权限'}`;
  }
}

async function stopAndTranscribe() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  if (waveTicker) {
    clearInterval(waveTicker);
    waveTicker = null;
    waveBars.value = [4, 4, 4, 4, 4, 4, 4, 4];
  }

  isRecording.value = false;
  isTranscribing.value = true;

  // 1. 若 WebSocket 处于开启状态，发送 commit 最终定稿
  if (realtimeWs && realtimeWs.readyState === WebSocket.OPEN) {
    try {
      realtimeWs.send(JSON.stringify({ type: 'input_audio_buffer.commit' }));
    } catch (e) {}
    setTimeout(() => {
      if (realtimeWs) {
        try { realtimeWs.close(); } catch (e) {}
        realtimeWs = null;
      }
    }, 400);
  }

  try {
    const wavBlob = await audioEngine.stopRecording();
    const lang = selectedLanguage.value !== 'auto' ? selectedLanguage.value : '';

    // 2. 若 WS 模式未产出文本（如离线模型、WS 降级），则走标准文件转写接口兜底
    if (wavBlob && !transcribedText.value) {
      const result = await apiClient.transcribeAudio(wavBlob, selectedModel.value, lang);
      transcribedText.value = result.text || '';
      latencyMs.value = result.latencyMs || 0;
      rtf.value = result.rtf || '0.00';
      if (result.segments && result.segments.length > 0) {
        finalizedSentences.value = result.segments.map((seg, i) => ({
          id: `seg_${i}`,
          start: typeof seg.start === 'number' ? seg.start : 0,
          end: typeof seg.end === 'number' ? seg.end : 0,
          text: seg.text || ''
        }));
      } else if (result.text) {
        finalizedSentences.value = [
          {
            id: 'seg_0',
            start: 0,
            end: durationSec.value || 0,
            text: result.text
          }
        ];
      }
    }

    if (transcribedText.value) {
      emit('add-history', {
        id: Date.now().toString(),
        type: 'dictate',
        text: transcribedText.value,
        segments: [...finalizedSentences.value],
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        model: selectedModel.value,
        duration: durationSec.value,
        latency: latencyMs.value
      });
    }
  } catch (err) {
    console.error('Transcription error:', err);
    errorMessage.value = `[转录失败: ${err.message}]`;
  } finally {
    isTranscribing.value = false;
    volume.value = 0;
  }
}

const currentLiveStart = computed(() => {
  if (finalizedSentences.value.length > 0) {
    return finalizedSentences.value[finalizedSentences.value.length - 1].end;
  }
  return 0;
});

function formatTime(seconds = 0) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

function scrollToBottom() {
  if (canvasBody.value) {
    canvasBody.value.scrollTop = canvasBody.value.scrollHeight;
  }
}

function exportFile(format = 'srt') {
  if (finalizedSentences.value.length === 0) return;
  let content = '';
  if (format === 'srt') {
    content = finalizedSentences.value
      .map((seg, i) => `${i + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n`)
      .join('\n');
  } else if (format === 'vtt') {
    content =
      'WEBVTT\n\n' +
      finalizedSentences.value
        .map((seg, i) => `${i + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n`)
        .join('\n');
  }
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `dictate_${Date.now()}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

function copyResult() {
  if (!transcribedText.value) return;
  navigator.clipboard.writeText(transcribedText.value);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 1800);
}

function clearText() {
  transcribedText.value = '';
  finalizedSentences.value = [];
  liveSentencePreview.value = '';
}
</script>

<style scoped>
.dictate-view {
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

.telemetry-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  align-self: flex-end;
  height: 38px;
}

.telemetry-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.telemetry-label {
  color: var(--text-muted);
}

.telemetry-val {
  color: var(--accent-emerald);
  font-weight: 600;
}

.telemetry-divider {
  color: var(--border-subtle);
  font-size: 10px;
}

/* 2. Hero Immersive Text Canvas */
.text-canvas-card {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  min-height: 280px;
}

.canvas-header {
  height: 42px;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background: var(--bg-surface);
}

.status-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: all 0.2s ease;
}

.status-dot.recording {
  background: var(--accent-red);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
  animation: pulse-dot 1.2s infinite;
}

.status-dot.transcribing {
  background: #f59e0b;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.5);
}

.status-dot.has_text {
  background: var(--accent-emerald);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}

.status-dot.error {
  background: var(--accent-red);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
}

.status-text.text-error {
  color: var(--accent-red);
  font-weight: 500;
}

.placeholder-error {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--accent-red);
  text-align: center;
  max-width: 480px;
  line-height: 1.5;
}

.placeholder-icon.error-icon {
  color: var(--accent-red);
  opacity: 0.8;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

.status-text {
  color: var(--text-secondary);
}

.char-badge {
  font-size: 11px;
  color: var(--text-muted);
}

.canvas-actions {
  display: flex;
  gap: 6px;
}

.action-btn {
  padding: 4px 10px;
  font-size: 11.5px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Canvas Body */
.canvas-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px 80px 24px; /* Bottom padding so text is not occluded by floating dock */
  position: relative;
}

.placeholder-box {
  height: 100%;
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-muted);
  user-select: none;
}

.placeholder-icon {
  width: 32px;
  height: 32px;
  color: var(--text-muted);
  opacity: 0.5;
  margin-bottom: 2px;
}

.placeholder-main {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-secondary);
}

.placeholder-sub {
  font-size: 11.5px;
  color: var(--text-muted);
}

.dictate-stream {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dictate-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  transition: background 0.15s ease, border-color 0.15s ease;
}

.dictate-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.dictate-row.live-row {
  border-color: rgba(16, 185, 129, 0.25);
  background: rgba(16, 185, 129, 0.03);
}

.timestamp-badge {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 5px;
  border: 1px solid var(--border-subtle);
  white-space: nowrap;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  user-select: none;
}

.timestamp-badge.live-badge {
  color: var(--accent-emerald);
  background: var(--accent-emerald-subtle);
  border-color: rgba(16, 185, 129, 0.3);
}

.live-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--accent-emerald);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
  animation: pulse-dot 1.2s infinite;
}

.dictate-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
  user-select: text;
  -webkit-user-select: text;
  flex: 1;
}

.dictate-text.live-text {
  color: var(--text-primary);
}

.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background-color: var(--accent-emerald);
  margin-left: 3px;
  vertical-align: middle;
  animation: cursor-blink 0.9s step-start infinite;
}

@keyframes cursor-blink {
  50% { opacity: 0; }
}

/* 3. Floating Bottom Audio Dock */
.floating-dock {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 64px;
  padding: 0 24px;
  background: var(--bg-surface);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 10;
}

.dock-left {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 140px;
}

.wave-visualizer {
  display: flex;
  align-items: center;
  gap: 2.5px;
  height: 24px;
}

.wave-bar {
  width: 3px;
  border-radius: 2px;
  background-color: var(--text-muted);
  transition: height 0.08s ease, background-color 0.2s ease;
}

.wave-bar.active {
  background-color: var(--accent-emerald);
}

.duration-timer {
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-secondary);
}

.dock-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

.dock-record-btn {
  padding: 9px 24px;
  border-radius: 30px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  cursor: pointer;
  background: var(--accent-emerald);
  color: #0b0f17;
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.25);
  transition: all 0.16s ease;
}

.dock-record-btn:hover:not(:disabled) {
  opacity: 0.92;
  transform: translateY(-1px);
}

.dock-record-btn:active:not(:disabled) {
  transform: translateY(0);
}

.dock-record-btn.recording {
  background: var(--accent-red);
  color: #ffffff;
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35);
  animation: record-glow 1.8s infinite;
}

@keyframes record-glow {
  0%, 100% { box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35); }
  50% { box-shadow: 0 4px 22px rgba(239, 68, 68, 0.65); }
}

.btn-mic-icon,
.btn-stop-icon {
  width: 16px;
  height: 16px;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(11, 15, 23, 0.25);
  border-top-color: #0b0f17;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.dock-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  width: 140px;
}

.shortcut-tip {
  font-size: 11px;
  color: var(--text-muted);
}

.kbd-badge {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: inherit;
  color: var(--text-secondary);
}
</style>
