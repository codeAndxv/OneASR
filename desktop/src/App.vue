<template>
  <div class="app-layout">
    <!-- Left Navigation Sidebar -->
    <Sidebar
      :current-tab="currentTab"
      :is-online="isServerOnline"
      @select-tab="handleSelectTab"
    />

    <!-- Main Content Area -->
    <main class="main-viewport">
      <Header
        :title="currentTabTitle"
        :subtitle="currentTabSubtitle"
        :is-history-open="isHistoryOpen"
        :history-count="historyItems.length"
        @toggle-history="isHistoryOpen = !isHistoryOpen"
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
        <SettingsView
          v-else-if="currentTab === 'settings'"
        />
      </div>
    </main>

    <!-- History Drawer (Slide-out) -->
    <HistoryDrawer
      :is-open="isHistoryOpen"
      :items="historyItems"
      @close="isHistoryOpen = false"
      @clear="clearHistory"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from './i18n';
import { apiClient } from './api/client';
import Sidebar from './components/Sidebar.vue';
import Header from './components/Header.vue';
import HistoryDrawer from './components/HistoryDrawer.vue';
import DictateView from './views/DictateView.vue';
import FilesView from './views/FilesView.vue';
import ModelsView from './views/ModelsView.vue';
import SettingsView from './views/SettingsView.vue';

const { t } = useI18n();

const currentTab = ref('dictate');
const isHistoryOpen = ref(false);
const isServerOnline = ref(false);
const historyItems = ref([]);

const tabMeta = {
  dictate: { titleKey: 'dictateTitle', subtitleKey: 'dictateSubtitle' },
  files: { titleKey: 'filesTitle', subtitleKey: 'filesSubtitle' },
  models: { titleKey: 'modelsTitle', subtitleKey: 'modelsSubtitle' },
  settings: { titleKey: 'settingsTitle', subtitleKey: 'settingsSubtitle' }
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
}

function addHistoryItem(item) {
  historyItems.value.unshift(item);
  if (historyItems.value.length > 50) {
    historyItems.value.pop();
  }
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
  if (healthInterval) {
    clearInterval(healthInterval);
  }
});

async function checkHealth() {
  const info = await apiClient.checkHealth();
  isServerOnline.value = !!info;
}
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  background-color: var(--bg-app);
  overflow: hidden;
}

.main-viewport {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.view-container {
  flex: 1;
  overflow: hidden;
  position: relative;
}
</style>
