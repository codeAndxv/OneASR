<template>
  <div class="app-layout">
    <!-- Left Navigation Sidebar -->
    <Sidebar
      :current-tab="currentTab"
      :is-online="isServerOnline"
      :history-count="historyItems.length"
      @select-tab="handleSelectTab"
      @open-settings="isSettingsOpen = true"
    />

    <!-- Main Content Area -->
    <main class="main-viewport">
      <Header
        :title="currentTabTitle"
        :subtitle="currentTabSubtitle"
      />

      <div class="view-container">
        <DictateView
          v-if="currentTab === 'dictate'"
          @add-history="addHistoryItem"
        />
        <FilesView
          v-else-if="currentTab === 'files'"
          @add-history="addHistoryItem"
        />
        <ModelsView
          v-else-if="currentTab === 'models'"
        />
        <HistoryView
          v-else-if="currentTab === 'history'"
          :items="historyItems"
          @delete-item="deleteHistoryItem"
          @clear-all="clearHistory"
        />
      </div>
    </main>

    <!-- Preferences / Settings Modal -->
    <SettingsModal
      :is-open="isSettingsOpen"
      @close="isSettingsOpen = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from './i18n';
import { apiClient } from './api/client';
import Sidebar from './components/Sidebar.vue';
import Header from './components/Header.vue';
import SettingsModal from './components/SettingsModal.vue';
import DictateView from './views/DictateView.vue';
import FilesView from './views/FilesView.vue';
import ModelsView from './views/ModelsView.vue';
import HistoryView from './views/HistoryView.vue';

const { t } = useI18n();

const currentTab = ref(localStorage.getItem('oneasr_current_tab') || 'models');
const isSettingsOpen = ref(false);
const isServerOnline = ref(false);
const historyItems = ref([]);

const tabMeta = {
  dictate: { titleKey: 'dictateTitle', subtitleKey: 'dictateSubtitle' },
  files: { titleKey: 'filesTitle', subtitleKey: 'filesSubtitle' },
  models: { titleKey: 'modelsTitle', subtitleKey: 'modelsSubtitle' },
  history: { titleKey: 'historyTitle', subtitleKey: 'historySubtitle' }
};

const currentTabTitle = computed(() => {
  const meta = tabMeta[currentTab.value];
  return meta ? t(meta.titleKey) : '';
});

const currentTabSubtitle = computed(() => {
  const meta = tabMeta[currentTab.value];
  return meta ? t(meta.subtitleKey) : '';
});

function handleSelectTab(tabId) {
  currentTab.value = tabId;
  localStorage.setItem('oneasr_current_tab', tabId);
}

function handleGlobalKeydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === ',') {
    e.preventDefault();
    isSettingsOpen.value = !isSettingsOpen.value;
  }
}

function addHistoryItem(item) {
  historyItems.value.unshift(item);
  if (historyItems.value.length > 50) {
    historyItems.value.pop();
  }
  saveHistoryToStorage();
}

function deleteHistoryItem(id) {
  historyItems.value = historyItems.value.filter((i) => i.id !== id);
  saveHistoryToStorage();
}

function clearHistory() {
  historyItems.value = [];
  saveHistoryToStorage();
}

function saveHistoryToStorage() {
  localStorage.setItem('oneasr_history', JSON.stringify(historyItems.value));
}

let healthInterval = null;

onMounted(async () => {
  window.addEventListener('keydown', handleGlobalKeydown);

  // Load saved history
  try {
    const saved = localStorage.getItem('oneasr_history');
    if (saved) {
      historyItems.value = JSON.parse(saved);
    }
  } catch (err) {
    console.warn('Could not load history:', err);
  }

  // Poll server health
  checkHealth();
  healthInterval = setInterval(checkHealth, 3000);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
  if (healthInterval) {
    clearInterval(healthInterval);
  }
});

async function checkHealth() {
  const info = await apiClient.checkHealth();
  isServerOnline.value = !!(info && (info.status === 'ok' || info.online));
}
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: var(--bg-base);
  position: relative;
}

.main-viewport {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background-color: var(--bg-surface);
}

.view-container {
  flex: 1;
  overflow-y: auto;
  position: relative;
}
</style>
