<template>
  <div class="drawer-overlay" :class="{ open: isOpen }" @click.self="$emit('close')">
    <div class="drawer-panel" :class="{ open: isOpen }">
      <!-- Drawer Header -->
      <div class="drawer-header">
        <div class="drawer-title-group">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span class="drawer-title">{{ t('historyTitle') }}</span>
          <span v-if="items.length > 0" class="count-pill">({{ items.length }})</span>
        </div>
        <div class="drawer-actions">
          <button v-if="items.length > 0" class="clear-btn" @click="$emit('clear')">
            {{ t('historyClear') }}
          </button>
          <button class="close-btn" @click="$emit('close')">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Drawer Content -->
      <div class="drawer-content">
        <div v-if="items.length === 0" class="empty-state">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          <p>{{ t('historyEmpty') }}</p>
        </div>

        <div v-else class="history-list">
          <div v-for="(item, index) in items" :key="item.id || index" class="history-card">
            <div class="card-meta">
              <span class="type-tag" :class="item.type">
                {{ item.type === 'dictate' ? '🎙️ 听写' : '📁 文件' }}
              </span>
              <span class="time-text">{{ item.time }}</span>
              <span v-if="item.model" class="model-tag">{{ item.model }}</span>
            </div>
            
            <p class="card-text">{{ item.text }}</p>

            <div class="card-footer">
              <span v-if="item.duration" class="meta-metric">{{ item.duration }}s</span>
              <span v-if="item.latency" class="meta-metric">{{ item.latency }}ms</span>
              <div class="card-buttons">
                <button class="copy-link" @click="copyItemText(item)">
                  {{ copiedId === item.id ? '✓ 已复制' : t('copyText') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useI18n } from '../i18n';

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  items: {
    type: Array,
    default: () => []
  }
});

defineEmits(['close', 'clear']);
const { t } = useI18n();
const copiedId = ref(null);

function copyItemText(item) {
  navigator.clipboard.writeText(item.text);
  copiedId.value = item.id;
  setTimeout(() => {
    if (copiedId.value === item.id) {
      copiedId.value = null;
    }
  }, 1800);
}
</script>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(2px);
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.drawer-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.drawer-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  background: #16171b;
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.5);
}

.drawer-panel.open {
  transform: translateX(0);
}

.drawer-header {
  height: 52px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-subtle);
}

.drawer-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 13px;
}

.count-pill {
  font-size: 11px;
  color: var(--text-muted);
}

.drawer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.clear-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
}

.clear-btn:hover {
  color: var(--accent-red);
  background: rgba(239, 68, 68, 0.1);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 4px;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.drawer-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 240px;
  color: var(--text-muted);
  gap: 12px;
  font-size: 12px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.15s ease;
}

.history-card:hover {
  border-color: rgba(255, 255, 255, 0.14);
  background: var(--bg-card-hover);
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 10px;
}

.type-tag {
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-secondary);
}

.time-text {
  color: var(--text-muted);
}

.model-tag {
  margin-left: auto;
  color: var(--accent-emerald);
  background: var(--accent-emerald-subtle);
  padding: 1px 5px;
  border-radius: 4px;
}

.card-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  margin-bottom: 8px;
  word-break: break-word;
  max-height: 84px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.meta-metric {
  font-size: 10px;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, monospace;
}

.copy-link {
  background: none;
  border: none;
  color: var(--accent-emerald);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.copy-link:hover {
  background: var(--accent-emerald-subtle);
}
</style>
