<template>
  <div class="file-upload-page">
    <h2>上传管理</h2>
    
    <!-- 上传区域 -->
    <div class="upload-section">
      <div 
        class="upload-dropzone"
        :class="{ 'drag-over': isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="handleDrop"
        @click="triggerFileInput"
      >
        <input 
          ref="fileInput" 
          type="file" 
          accept="audio/*,video/*" 
          multiple
          style="display: none" 
          @change="handleFileSelect"
        />
        <div class="upload-icon">⬆️</div>
        <p>拖拽文件到此处，或点击选择文件</p>
        <p class="upload-hint">支持格式：mp3, wav, m4a, flac, mp4, mov, avi, mkv 等</p>
      </div>
      
      <!-- 上传进度 -->
      <div v-if="uploadingFiles.length > 0" class="upload-progress">
        <div v-for="item in uploadingFiles" :key="item.id" class="progress-item">
          <span class="filename">{{ item.file.name }}</span>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: item.progress + '%' }"></div>
          </div>
          <span class="progress-text">{{ item.progress }}%</span>
          <span v-if="item.error" class="error-text">{{ item.error }}</span>
        </div>
      </div>
    </div>
    
    <!-- 已上传文件列表 -->
    <div class="files-section">
      <h3>已上传文件 ({{ files.length }})</h3>
      
      <div v-if="loading" class="loading">加载中...</div>
      
      <div v-else-if="files.length === 0" class="empty-state">
        暂无已上传的文件
      </div>
      
      <table v-else class="files-table">
        <thead>
          <tr>
            <th>文件名</th>
            <th>大小</th>
            <th>上传时间</th>
            <th>UUID</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in files" :key="file.file_id">
            <td class="filename-cell">{{ file.filename }}</td>
            <td>{{ formatFileSize(file.file_size) }}</td>
            <td>{{ formatDate(file.created_at) }}</td>
            <td class="uuid-cell">
              <code>{{ file.file_id }}</code>
              <button class="copy-btn" @click="copyUuid(file.file_id)">复制</button>
            </td>
            <td class="actions-cell">
              <button class="btn btn-primary" @click="transcribeFile(file)">转录</button>
              <button class="btn btn-danger" @click="deleteFile(file)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API_BASE = 'http://127.0.0.1:8020'
const API_KEY = 'oneasr-key'

const files = ref([])
const loading = ref(false)
const isDragging = ref(false)
const uploadingFiles = ref([])
const fileInput = ref(null)

// 加载文件列表
const loadFiles = async () => {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/api/v1/files/list`, {
      headers: { 'X-API-Key': API_KEY },
    })
    if (res.ok) {
      const data = await res.json()
      files.value = data.files
    }
  } catch (e) {
    console.error('加载文件列表失败:', e)
  } finally {
    loading.value = false
  }
}

// 触发文件选择
const triggerFileInput = () => {
  fileInput.value.click()
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  uploadFiles(selectedFiles)
  event.target.value = ''
}

// 处理拖拽
const handleDrop = (event) => {
  isDragging.value = false
  const droppedFiles = Array.from(event.dataTransfer.files)
  uploadFiles(droppedFiles)
}

// 上传文件
const uploadFiles = async (filesToUpload) => {
  for (const file of filesToUpload) {
    const itemId = Date.now() + Math.random()
    const item = { id: itemId, file, progress: 0, error: null }
    uploadingFiles.value.push(item)
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const xhr = new XMLHttpRequest()
      
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          item.progress = Math.round((e.loaded / e.total) * 100)
        }
      })
      
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          item.progress = 100
          setTimeout(() => {
            uploadingFiles.value = uploadingFiles.value.filter(i => i.id !== itemId)
          }, 1000)
          loadFiles()
        } else {
          item.error = '上传失败'
        }
      })
      
      xhr.addEventListener('error', () => {
        item.error = '上传失败'
      })
      
      xhr.open('POST', `${API_BASE}/api/v1/files/upload`)
      xhr.setRequestHeader('X-API-Key', API_KEY)
      xhr.send(formData)
      
    } catch (e) {
      item.error = e.message
    }
  }
}

// 删除文件
const deleteFile = async (file) => {
  if (!confirm(`确定要删除文件 "${file.filename}" 吗？`)) {
    return
  }
  
  try {
    const res = await fetch(`${API_BASE}/api/v1/files/${file.file_id}`, {
      method: 'DELETE',
      headers: { 'X-API-Key': API_KEY },
    })
    
    if (res.ok) {
      loadFiles()
    } else {
      alert('删除失败')
    }
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

// 复制UUID
const copyUuid = (uuid) => {
  navigator.clipboard.writeText(uuid)
  alert('UUID 已复制到剪贴板')
}

// 转录文件
const transcribeFile = (file) => {
  alert(`文件UUID: ${file.file_id}\n\n使用此UUID调用转录API:\nPOST /api/v1/audio/transcriptions\nfile_uuid: ${file.file_id}`)
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化日期
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleString()
}

onMounted(() => {
  loadFiles()
})
</script>

<style scoped>
.file-upload-page {
  padding: 20px;
}

h2 {
  margin-bottom: 20px;
  color: #333;
}

.upload-section {
  margin-bottom: 30px;
}

.upload-dropzone {
  border: 2px dashed #ccc;
  border-radius: 10px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-dropzone:hover,
.upload-dropzone.drag-over {
  border-color: #409eff;
  background-color: #f5f7fa;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.upload-hint {
  font-size: 12px;
  color: #999;
  margin-top: 10px;
}

.upload-progress {
  margin-top: 20px;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 5px;
  margin-bottom: 10px;
}

.progress-item .filename {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-bar {
  width: 200px;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #409eff;
  transition: width 0.3s;
}

.progress-text {
  width: 50px;
  text-align: right;
}

.error-text {
  color: #f56c6c;
}

.files-section h3 {
  margin-bottom: 15px;
  color: #333;
}

.loading,
.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
}

.files-table {
  width: 100%;
  border-collapse: collapse;
}

.files-table th,
.files-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.files-table th {
  background: #f5f7fa;
  font-weight: 600;
}

.filename-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.uuid-cell {
  font-size: 12px;
}

.uuid-cell code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  margin-right: 5px;
}

.copy-btn {
  font-size: 11px;
  padding: 2px 6px;
  cursor: pointer;
}

.actions-cell {
  white-space: nowrap;
}

.btn {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-right: 5px;
  font-size: 13px;
}

.btn-primary {
  background: #409eff;
  color: white;
}

.btn-danger {
  background: #f56c6c;
  color: white;
}

.btn:hover {
  opacity: 0.9;
}
</style>
