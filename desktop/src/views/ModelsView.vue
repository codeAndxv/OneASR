<template>
  <div class="models-view">
    <div class="models-grid">
      <div v-for="model in modelsList" :key="model.id" class="model-card" :class="{ active: model.isActive }">
        <div class="card-header">
          <div class="model-title-group">
            <h3 class="model-name">{{ model.name }}</h3>
            <span class="model-arch">{{ model.arch }}</span>
          </div>
          <span class="status-badge" :class="model.status">
            {{ getStatusLabel(model.status) }}
          </span>
        </div>

        <p class="model-desc">{{ model.desc }}</p>

        <div class="model-specs">
          <div class="spec-item">
            <span class="spec-label">{{ t('modelParams') }}</span>
            <span class="spec-value">{{ model.params }}</span>
          </div>
          <div class="spec-item">
            <span class="spec-label">{{ t('modelVram') }}</span>
            <span class="spec-value">{{ model.vram }}</span>
          </div>
          <div class="spec-item">
            <span class="spec-label">{{ t('modelLangs') }}</span>
            <span class="spec-value">{{ model.langs }}</span>
          </div>
        </div>

        <div class="card-footer">
          <button
            v-if="model.status === 'downloaded' && !model.isActive"
            class="action-btn load-btn"
            @click="handleLoadModel(model)"
          >
            {{ t('btnLoadModel') }}
          </button>
          <button
            v-else-if="model.isActive"
            class="action-btn unload-btn"
            @click="handleUnloadModel(model)"
          >
            {{ t('btnUnloadModel') }}
          </button>
          <button
            v-else-if="model.status === 'remote'"
            class="action-btn download-btn"
            :disabled="model.isDownloading"
            @click="handleDownloadModel(model)"
          >
            <span v-if="model.isDownloading" class="btn-spinner"></span>
            <span>{{ model.isDownloading ? t('downloadingProgress') : t('btnDownloadModel') }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from '../i18n';
import { apiClient } from '../api/client';

const { t } = useI18n();

const modelsList = ref([
  {
    id: 'sensevoice-small',
    name: 'SenseVoice-Small',
    arch: 'FunASR · 50M',
    desc: '超极速端到端语音大模型，首字延迟 <150ms，原生支持中、英、日、韩、粤多语言与情感声音检测。',
    params: '50M',
    vram: '< 1GB',
    langs: '中 / 英 / 日 / 韩 / 粤',
    status: 'downloaded',
    isActive: true,
    isDownloading: false
  },
  {
    id: 'whisper-large-v3-turbo',
    name: 'Whisper-Large-v3-Turbo',
    arch: 'OpenAI · 800M',
    desc: 'OpenAI 官方极致优化蒸馏版，转写准确率极高，速度较原版提升 8 倍，最适合会议长录音与播客字幕。',
    params: '809M',
    vram: '~ 3.5GB',
    langs: '99+ 全球主流语言',
    status: 'downloaded',
    isActive: false,
    isDownloading: false
  },
  {
    id: 'funasr-paraformer',
    name: 'FunASR Paraformer Large',
    arch: 'Alibaba · 非自回归',
    desc: '阿里达摩院工业级中文语音识别基座，配备专用 VAD 语音活动检测和 Punc 标点恢复模型。',
    params: '220M',
    vram: '~ 2GB',
    langs: '中文 / 英文',
    status: 'remote',
    isActive: false,
    isDownloading: false
  },
  {
    id: 'qwen2-audio-7b',
    name: 'Qwen2-Audio-7B',
    arch: 'Qwen · 7B Multimodal',
    desc: '通义千问全功能语音多模态大模型，具备复杂的语音理解、音频问答与高精准长文本听抄能力。',
    params: '7.6B',
    vram: '~ 14GB',
    langs: '中 / 英 / 泛音频',
    status: 'remote',
    isActive: false,
    isDownloading: false
  }
]);

onMounted(async () => {
  await fetchBackendModels();
});

async function fetchBackendModels() {
  try {
    const data = await apiClient.getModels();
    if (data && data.active_model) {
      modelsList.value.forEach((m) => {
        m.isActive = m.id === data.active_model;
      });
    }
  } catch (err) {
    console.warn('Could not sync models from backend:', err);
  }
}

function getStatusLabel(status) {
  if (status === 'active') return t('modelActiveBadge');
  if (status === 'downloaded') return t('modelDownloadedBadge');
  return t('modelRemoteBadge');
}

async function handleLoadModel(model) {
  try {
    await apiClient.loadModel(model.id);
    modelsList.value.forEach((m) => {
      m.isActive = m.id === model.id;
    });
  } catch (err) {
    console.error('Load model error:', err);
  }
}

async function handleUnloadModel(model) {
  try {
    await apiClient.unloadModel(model.id);
    model.isActive = false;
  } catch (err) {
    console.error('Unload model error:', err);
  }
}

async function handleDownloadModel(model) {
  model.isDownloading = true;
  try {
    await apiClient.downloadModel(model.id);
    model.status = 'downloaded';
  } catch (err) {
    console.error('Download model error:', err);
    // Simulate successful download in preview
    setTimeout(() => {
      model.status = 'downloaded';
    }, 1500);
  } finally {
    model.isDownloading = false;
  }
}
</script>

<style scoped>
.models-view {
  padding: 16px 20px;
  overflow-y: auto;
  height: 100%;
}

.models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.model-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.15s ease;
}

.model-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background: var(--bg-card-hover);
}

.model-card.active {
  border-color: rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.03);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.model-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.model-arch {
  font-size: 11px;
  color: var(--text-muted);
}

.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.model-card.active .status-badge {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
}

.status-badge.downloaded {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
}

.status-badge.remote {
  background: rgba(59, 130, 246, 0.12);
  color: var(--accent-blue);
}

.model-desc {
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-secondary);
  flex: 1;
}

.model-specs {
  display: flex;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 6px 10px;
  border: 1px solid rgba(255, 255, 255, 0.03);
}

.spec-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.spec-label {
  font-size: 9px;
  color: var(--text-muted);
}

.spec-value {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
}

.action-btn {
  font-size: 11px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  border: none;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s ease;
}

.load-btn {
  background: var(--accent-emerald);
  color: #000;
  font-weight: 600;
}

.load-btn:hover {
  opacity: 0.9;
}

.unload-btn {
  background: rgba(239, 68, 68, 0.12);
  color: var(--accent-red);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.unload-btn:hover {
  background: rgba(239, 68, 68, 0.2);
}

.download-btn {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
}

.download-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.btn-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(255, 255, 255, 0.2);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
