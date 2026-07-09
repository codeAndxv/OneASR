<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { setApiKey, getStoredApiKey } from '../api'

const router = useRouter()
const showSettings = ref(false)
const apiKey = ref('')
const language = ref(localStorage.getItem('asr_language') || 'auto')
const outputFormat = ref(localStorage.getItem('asr_format') || 'srt')

onMounted(() => {
  apiKey.value = getStoredApiKey()
})

function saveSettings() {
  setApiKey(apiKey.value)
  localStorage.setItem('asr_language', language.value)
  localStorage.setItem('asr_format', outputFormat.value)
  showSettings.value = false
  location.reload()
}

function goTo(path) {
  router.push(path)
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">
        <span class="logo-icon"> </span>
        <span class="logo-text">OneASR</span>
      </div>
      <nav>
        <button @click="goTo('/')" class="nav-item">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </span>
          <span class="nav-label">语音识别</span>
        </button>
        <button @click="goTo('/files')" class="nav-item">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </span>
          <span class="nav-label">上传管理</span>
        </button>
      </nav>
      <div class="sidebar-footer">
        <button class="settings-btn" @click="showSettings = !showSettings">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <span>设置</span>
        </button>
      </div>
    </aside>
    <div class="main-area">
      <main class="content">
        <router-view />
      </main>
    </div>

    <!-- 设置弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showSettings" class="overlay" @click.self="showSettings = false">
          <div class="modal">
            <div class="modal-header">
              <h3>设置</h3>
              <button class="modal-close" @click="showSettings = false">&times;</button>
            </div>
            <div class="modal-body">
              <div class="field">
                <label>API Key</label>
                <input
                  v-model="apiKey"
                  type="password"
                  placeholder="输入 API Key"
                  @keyup.enter="saveSettings"
                />
              </div>
              <div class="field">
                <label>识别语言</label>
                <select v-model="language" class="field-select">
                  <option value="auto">自动检测</option>
                  <option value="zh">中文</option>
                  <option value="en">英文</option>
                  <option value="ja">日文</option>
                  <option value="ko">韩文</option>
                </select>
              </div>
              <div class="field">
                <label>默认输出格式</label>
                <select v-model="outputFormat" class="field-select">
                  <option value="srt">SRT 字幕</option>
                  <option value="text">纯文本</option>
                  <option value="vtt">WebVTT</option>
                  <option value="json">JSON</option>
                </select>
              </div>
            </div>
            <div class="modal-actions">
              <button class="btn-cancel" @click="showSettings = false">取消</button>
              <button class="btn-save" @click="saveSettings">保存</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 200px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #667eea, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

nav {
  flex: 1;
  padding: 16px 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  color: rgba(255,255,255,0.6);
  text-decoration: none;
  font-size: 14px;
  border-radius: 8px;
  transition: all 0.2s;
  background: none;
  border: none;
  width: 100%;
  cursor: pointer;
  text-align: left;
}

.nav-item:hover {
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.9);
}

.nav-item.router-link-active {
  background: rgba(102, 126, 234, 0.2);
  color: #fff;
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}

.sidebar-footer {
  padding: 12px 10px;
  border-top: 1px solid rgba(255,255,255,0.08);
}

.settings-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border-radius: 8px;
  font-size: 14px;
  color: rgba(255,255,255,0.6);
  transition: all 0.2s;
}

.settings-btn:hover {
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.9);
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.content {
  flex: 1;
  overflow: auto;
  background: #f0f2f5;
  min-height: 0;
}

/* Modal */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  background: #fff;
  border-radius: 16px;
  padding: 0;
  width: 400px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 0;
}

.modal-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
}

.modal-close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  border-radius: 50%;
  font-size: 18px;
  color: #666;
  transition: all 0.2s;
}

.modal-close:hover {
  background: #e0e0e0;
}

.modal-body {
  padding: 16px 24px;
}

.field {
  margin-bottom: 16px;
}

.field:last-child {
  margin-bottom: 0;
}

.field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #6e6e73;
  margin-bottom: 8px;
}

.field input,
.field-select {
  width: 100%;
  padding: 10px 14px;
  border: 1.5px solid #d2d2d7;
  border-radius: 10px;
  font-size: 14px;
  background: #fff;
  transition: border-color 0.2s;
}

.field input:focus,
.field-select:focus {
  border-color: #667eea;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  background: #fafafa;
  border-top: 1px solid #f0f0f0;
}

.btn-cancel {
  padding: 8px 18px;
  background: #fff;
  border: 1.5px solid #e0e0e0;
  border-radius: 10px;
  font-size: 14px;
  color: #666;
  transition: all 0.2s;
}

.btn-cancel:hover {
  border-color: #ccc;
  background: #f5f5f5;
}

.btn-save {
  padding: 8px 20px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  transition: opacity 0.2s;
}

.btn-save:hover {
  opacity: 0.9;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
