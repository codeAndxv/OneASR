<script setup>
import { ref, onMounted } from 'vue'
import { setApiKey, getStoredApiKey } from '../api'

const showSettings = ref(false)
const apiKey = ref('')

onMounted(() => {
  apiKey.value = getStoredApiKey()
})

function saveApiKey() {
  setApiKey(apiKey.value)
  showSettings.value = false
  location.reload()
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">OneASR</div>
      <nav>
        <router-link to="/" class="nav-item active">
          <span class="icon"> </span>
          语音识别
        </router-link>
      </nav>
    </aside>
    <div class="main-area">
      <header class="topbar">
        <div class="spacer"></div>
        <button class="settings-btn" @click="showSettings = !showSettings">
          ⚙ 设置
        </button>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>

    <!-- API Key 弹窗 -->
    <div v-if="showSettings" class="overlay" @click.self="showSettings = false">
      <div class="modal">
        <h3>设置</h3>
        <div class="field">
          <label>API Key</label>
          <input
            v-model="apiKey"
            type="text"
            placeholder="输入 API Key"
            @keyup.enter="saveApiKey"
          />
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showSettings = false">取消</button>
          <button class="btn-save" @click="saveApiKey">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 220px;
  background: #1a1a2e;
  color: #fff;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.logo {
  padding: 24px 20px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 1px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

nav {
  flex: 1;
  padding: 12px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  font-size: 15px;
  transition: all 0.2s;
}

.nav-item:hover,
.nav-item.active {
  background: rgba(255,255,255,0.1);
  color: #fff;
}

.nav-item .icon {
  font-size: 18px;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar {
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 52px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.spacer {
  flex: 1;
}

.settings-btn {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.settings-btn:hover {
  background: #f5f5f5;
  border-color: #bbb;
}

.content {
  flex: 1;
  overflow: auto;
  background: #f5f5f5;
}

/* Modal */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 120px;
  z-index: 100;
}

.modal {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
  width: 380px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.15);
}

.modal h3 {
  margin: 0 0 20px;
  font-size: 18px;
  color: #333;
}

.field {
  margin-bottom: 20px;
}

.field label {
  display: block;
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}

.field input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.field input:focus {
  border-color: #667eea;
  outline: none;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-cancel {
  padding: 8px 18px;
  background: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  color: #555;
  cursor: pointer;
}

.btn-save {
  padding: 8px 18px;
  background: #667eea;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  color: #fff;
  cursor: pointer;
}

.btn-save:hover {
  opacity: 0.9;
}
</style>
