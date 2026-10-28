<template>
  <header class="app-header" data-tauri-drag-region @mousedown="startDrag">
    <div class="header-left">
      <h1 class="header-title">{{ title }}</h1>
      <span class="header-subtitle">{{ subtitle }}</span>
    </div>

    <div class="header-right">
      <slot name="actions"></slot>
    </div>
  </header>
</template>

<script setup>
import { useI18n } from '../i18n';
import { getCurrentWindow } from '@tauri-apps/api/window';

defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  }
});

const { t } = useI18n();

let appWindow = null;
try {
  appWindow = getCurrentWindow();
} catch (err) {
  // Fallback if running outside Tauri
}

function startDrag(e) {
  if (appWindow && e.buttons === 1 && !e.target.closest('button, select, input, a, .icon-btn, .no-drag')) {
    appWindow.startDragging();
  }
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
  -webkit-app-region: drag;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
  pointer-events: none;
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
  -webkit-app-region: no-drag;
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
