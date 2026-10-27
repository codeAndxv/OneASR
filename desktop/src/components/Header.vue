<template>
  <header class="app-header" data-tauri-drag-region>
    <div class="header-left">
      <h1 class="header-title">{{ title }}</h1>
      <span class="header-subtitle">{{ subtitle }}</span>
    </div>

    <div class="header-right">
      <!-- Language Quick Switcher -->
      <button class="icon-btn" :title="locale === 'zh-CN' ? 'Switch to English' : '切换为简体中文'" @click="toggleLocale">
        <span class="lang-text">{{ locale === 'zh-CN' ? '中' : 'EN' }}</span>
      </button>

      <!-- History Drawer Toggle -->
      <button class="icon-btn history-btn" :class="{ active: isHistoryOpen }" :title="t('historyTitle')" @click="$emit('toggle-history')">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        <span v-if="historyCount > 0" class="history-badge">{{ historyCount }}</span>
      </button>
    </div>
  </header>
</template>

<script setup>
import { useI18n } from '../i18n';

defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  isHistoryOpen: {
    type: Boolean,
    default: false
  },
  historyCount: {
    type: Number,
    default: 0
  }
});

defineEmits(['toggle-history']);

const { locale, setLocale, t } = useI18n();

function toggleLocale() {
  setLocale(locale.value === 'zh-CN' ? 'en-US' : 'zh-CN');
}
</script>

<style scoped>
.app-header {
  height: 52px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-subtle);
  background-color: var(--bg-app);
  user-select: none;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.header-subtitle {
  font-size: 12px;
  color: var(--text-muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  cursor: pointer;
  position: relative;
  transition: all 0.15s ease;
}

.icon-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.15);
}

.icon-btn.active {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  border-color: rgba(16, 185, 129, 0.3);
}

.lang-text {
  font-size: 11px;
  font-weight: 600;
}

.history-badge {
  position: absolute;
  top: -3px;
  right: -3px;
  background: var(--accent-emerald);
  color: #000;
  font-size: 9px;
  font-weight: 700;
  border-radius: 6px;
  padding: 1px 4px;
  min-width: 14px;
  text-align: center;
}
</style>
