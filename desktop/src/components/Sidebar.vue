<template>
  <aside class="sidebar" data-tauri-drag-region @mousedown="handleSidebarMouseDown">
    <!-- Top Window Drag Bar (Safe area for macOS traffic lights & window drag header) -->
    <div class="sidebar-top-bar" data-tauri-drag-region @mousedown="handleSidebarMouseDown"></div>

    <!-- Brand / Mascot Header -->
    <div class="brand" data-tauri-drag-region @mousedown="handleSidebarMouseDown">
      <div class="mascot-badge">
        <svg viewBox="0 0 24 24" class="mascot-icon" fill="none" stroke="currentColor" stroke-width="2">
          <!-- Cat Mascot Outline -->
          <path d="M12 21a7 7 0 0 1-7-7c0-2.3 1.1-4.3 2.8-5.6l-1.3-4.4 4.5 1.8c.3-.1.7-.2 1-.2s.7.1 1 .2l4.5-1.8-1.3 4.4c1.7 1.3 2.8 3.3 2.8 5.6a7 7 0 0 1-7 7z" />
          <!-- Headphones -->
          <path d="M4 14a2 2 0 0 1 2-2h1v4H6a2 2 0 0 1-2-2zm16 0a2 2 0 0 0-2-2h-1v4h1a2 2 0 0 0 2-2z" />
          <path d="M7 12V9a5 5 0 0 1 10 0v3" />
        </svg>
      </div>
      <div class="brand-text">
        <div class="brand-title">OneASR</div>
        <div class="brand-version">v0.1.0 • Core</div>
      </div>
    </div>

    <!-- Navigation List (4 Core Tabs) -->
    <nav class="nav-list no-drag">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="nav-item no-drag"
        :class="{ active: currentTab === item.id }"
        @click="$emit('select-tab', item.id)"
      >
        <span class="nav-icon" v-html="item.icon"></span>
        <span class="nav-label">{{ t(item.labelKey) }}</span>
        <span v-if="item.id === 'history' && historyCount > 0" class="nav-badge">{{ historyCount }}</span>
      </button>
    </nav>

    <!-- Sidebar Footer: Status on top, Settings at the very bottom -->
    <div class="sidebar-footer no-drag">
      <!-- Engine Status Card (above settings) -->
      <div class="server-status no-drag" :class="{ online: isOnline, starting: isStarting }">
        <div class="status-indicator" :class="{ pulse: isStarting }"></div>
        <div class="status-text">
          <div class="status-title">
            {{ isOnline ? t('statusOnline') : (isStarting ? t('statusStarting') : t('statusOffline')) }}
          </div>
          <div class="status-host">127.0.0.1:8020</div>
        </div>
        <!-- Manual Start Ghost Button: shown when initial check fails or offline -->
        <button
          v-if="!isOnline && hasChecked"
          class="status-action-btn no-drag"
          :disabled="isStarting"
          :title="isStarting ? t('statusStarting') : t('statusStart')"
          @click.stop="$emit('start-service')"
        >
          <svg v-if="isStarting" class="spin-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
          <span v-else>{{ t('statusStart') }}</span>
        </button>
      </div>

      <!-- Preferences / Settings Button (Triggers Preferences Modal) -->
      <button
        class="nav-item settings-item no-drag"
        :title="t('navSettings') + ' (⌘,)'"
        @click="$emit('open-settings')"
      >
        <span class="nav-icon">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </span>
        <span class="nav-label">{{ t('navSettings') }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { useI18n } from '../i18n';
import { getCurrentWindow } from '@tauri-apps/api/window';

const props = defineProps({
  currentTab: {
    type: String,
    required: true
  },
  isOnline: {
    type: Boolean,
    default: false
  },
  isStarting: {
    type: Boolean,
    default: false
  },
  hasChecked: {
    type: Boolean,
    default: false
  },
  historyCount: {
    type: Number,
    default: 0
  }
});

defineEmits(['select-tab', 'open-settings', 'start-service']);
const { t } = useI18n();

let appWindow = null;
try {
  appWindow = getCurrentWindow();
} catch (err) {
  // Fallback
}

function handleSidebarMouseDown(e) {
  if (appWindow && e.buttons === 1 && !e.target.closest('button, select, input, a, .nav-item, .settings-item, .server-status, .no-drag')) {
    appWindow.startDragging();
  }
}

const navItems = [
  {
    id: 'dictate',
    labelKey: 'navDictate',
    icon: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>`
  },
  {
    id: 'files',
    labelKey: 'navFiles',
    icon: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>`
  },
  {
    id: 'models',
    labelKey: 'navModels',
    icon: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`
  },
  {
    id: 'history',
    labelKey: 'navHistory',
    icon: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`
  }
];
</script>

<style scoped>
.sidebar {
  width: 210px;
  background-color: var(--bg-sidebar);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  padding: 0 12px 14px 12px;
  height: 100%;
  user-select: none;
  -webkit-app-region: drag;
  cursor: default;
}

.sidebar-top-bar {
  height: 34px;
  width: 100%;
  margin: 0 -12px;
  padding: 0 12px;
  flex-shrink: 0;
  -webkit-app-region: drag;
  cursor: default;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 16px 8px;
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 14px;
  user-select: none;
  -webkit-app-region: drag;
}

.mascot-badge {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-emerald);
  pointer-events: none;
}

.mascot-icon {
  width: 20px;
  height: 20px;
}

.brand-text {
  pointer-events: none;
}

.brand-title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.2px;
  color: var(--text-primary);
}

.brand-version {
  font-size: 11px;
  color: var(--text-muted);
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.no-drag {
  -webkit-app-region: no-drag;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  font-weight: 600;
}

.nav-badge {
  margin-left: auto;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}

.nav-item.active .nav-badge {
  background: var(--accent-emerald-subtle);
  color: var(--accent-emerald);
  border-color: rgba(16, 185, 129, 0.25);
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border-subtle);
  margin-top: auto;
}

.settings-item {
  width: 100%;
}

.server-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-subtle);
}

.status-indicator {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: var(--accent-red);
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
}

.status-indicator.pulse {
  background-color: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.server-status.online .status-indicator {
  background-color: var(--accent-emerald);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}

.status-text {
  flex: 1;
  min-width: 0;
}

.status-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-host {
  font-size: 10px;
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.status-action-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.status-action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.2);
}

.status-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
