// 后端直连地址（SSE 流式请求绕过 Vite proxy，避免缓冲）
const API_BASE = 'http://127.0.0.1:8020'
// 代理地址（通过 Vite proxy，避免 CORS）
const PROXY_API = '/api/v1'

function getApiKey() {
  return localStorage.getItem('api_key') || ''
}

export function setApiKey(key) {
  localStorage.setItem('api_key', key)
}

export function getStoredApiKey() {
  return getApiKey()
}

// auth error 回调，由 Layout.vue 注入翻译后的消息
let _authErrorCallback = null
export function onAuthError(fn) {
  _authErrorCallback = fn
}

/**
 * 统一请求封装：自动携带 API Key，401 时触发全局提示
 */
async function apiFetch(url, options = {}) {
  const headers = { 'X-API-Key': getApiKey(), ...options.headers }
  const res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    const { showAuthError } = await import('../utils/notifications.js')
    const msg = _authErrorCallback ? _authErrorCallback() : 'API Key not configured or invalid'
    showAuthError(msg)
    throw new Error(msg)
  }
  return res
}

/**
 * 获取可用 Provider 列表
 */
export async function getEngines() {
  const res = await apiFetch(`${API_BASE}/api/v1/providers`)
  const data = await res.json()
  // 转换为兼容格式
  return {
    default: data.data[0]?.id || '',
    engines: data.data.map(m => ({
      name: m.id,
      engine: m.engine,
      type: m.type,
      model_name: m.model_name,
    })),
  }
}

/**
 * 通用 SSE 流式读取（fetch + ReadableStream）
 * 逐行解析 data: {...} 事件，调用 onSegment / onDone / onError
 */
async function streamSse(url, body, onSegment, onDone, onError, ctrl) {
  try {
    const isJson = typeof body === 'string'
    const res = await apiFetch(url, {
      method: 'POST',
      signal: ctrl?.signal,
      headers: isJson ? { 'Content-Type': 'application/json' } : {},
      body,
    })

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      onError(new Error(text || `请求失败: ${res.status}`))
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.done) {
            onDone()
            reader.cancel()
            return
          } else if (data.error) {
            onError(new Error(data.error))
            reader.cancel()
            return
          } else {
            onSegment(data)
          }
        } catch {}
      }
    }

    // 流结束但没有收到 done 事件
    onDone()
  } catch (err) {
    onError(err.message === 'Failed to fetch' ? new Error('Cannot connect to backend service') : err)
  }
}

/**
 * 流式文件识别（新接口）
 */
export function transcribeFileStream(file, engine, onSegment, onDone, onError) {
  const form = new FormData()
  form.append('file', file)
  if (engine) form.append('model', engine)

  const ctrl = new AbortController()
  streamSse(
    `${API_BASE}/api/v1/audio/transcriptions/stream`,
    form,
    onSegment,
    onDone,
    onError,
    ctrl,
  )
  return { abort: () => ctrl.abort() }
}

/**
 * 流式 URL 识别（新接口）
 */
export function transcribeUrlStream(url, engine, onSegment, onDone, onError) {
  const form = new FormData()
  form.append('url', url)
  if (engine) form.append('model', engine)

  const ctrl = new AbortController()
  streamSse(
    `${API_BASE}/api/v1/audio/transcriptions/stream`,
    form,
    onSegment,
    onDone,
    onError,
    ctrl,
  )
  return { abort: () => ctrl.abort() }
}

/**
 * 非流式文件识别（新接口，一次性返回完整结果）
 */
export async function transcribeFile(file, engine, format = 'json') {
  const form = new FormData()
  form.append('file', file)
  if (engine) form.append('model', engine)
  form.append('response_format', format)

  const res = await apiFetch(`${API_BASE}/api/v1/audio/transcriptions`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `请求失败: ${res.status}`)
  }

  if (format === 'json') {
    return res.json()
  }
  return res.text()
}

/**
 * 非流式 URL 识别（新接口，一次性返回完整结果）
 */
export async function transcribeUrl(url, engine, format = 'json') {
  const form = new FormData()
  form.append('url', url)
  if (engine) form.append('model', engine)
  form.append('response_format', format)

  const res = await apiFetch(`${API_BASE}/api/v1/audio/transcriptions`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `请求失败: ${res.status}`)
  }

  if (format === 'json') {
    return res.json()
  }
  return res.text()
}

/**
 * 上传文件到服务器
 */
export async function uploadFile(file, onProgress) {
  const form = new FormData()
  form.append('file', file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status === 401) {
        const msg = _authErrorCallback ? _authErrorCallback() : 'API Key not configured or invalid'
        import('../utils/notifications.js').then(({ showAuthError }) => showAuthError(msg))
        reject(new Error(msg))
        return
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        reject(new Error(xhr.responseText || '上传失败'))
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('上传失败'))
    })

    xhr.open('POST', `${API_BASE}/api/v1/files/upload`)
    xhr.setRequestHeader('X-API-Key', getApiKey())
    xhr.send(form)
  })
}

/**
 * 获取已上传文件列表
 */
export async function listUploadedFiles() {
  const res = await apiFetch(`${API_BASE}/api/v1/files/list`)
  if (!res.ok) throw new Error('获取文件列表失败')
  return res.json()
}

/**
 * 删除已上传文件
 */
export async function deleteUploadedFile(fileId) {
  const res = await apiFetch(`${API_BASE}/api/v1/files/${fileId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('删除文件失败')
  return res.json()
}

/**
 * 使用 file_uuid 进行转录
 */
export async function transcribeByUuid(fileUuid, engine, format = 'json', language = '') {
  const form = new FormData()
  form.append('file_uuid', fileUuid)
  if (engine) form.append('model', engine)
  form.append('response_format', format)
  if (language) form.append('language', language)

  const res = await apiFetch(`${API_BASE}/api/v1/audio/transcriptions`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `请求失败: ${res.status}`)
  }

  if (format === 'json') {
    return res.json()
  }
  return res.text()
}

// ── 记录查询 API ──────────────────────────────────────────────

function buildRecordParams(params) {
  const q = new URLSearchParams()
  if (params.page) q.set('page', params.page)
  if (params.page_size) q.set('page_size', params.page_size)
  if (params.sort_by) q.set('sort_by', params.sort_by)
  if (params.sort_order) q.set('sort_order', params.sort_order)
  return q.toString()
}

/**
 * 分页查询上传记录
 */
export async function getUploadRecords(params = {}) {
  const qs = buildRecordParams({ page: 1, page_size: 20, sort_by: 'created_at', sort_order: 'desc', ...params })
  const res = await apiFetch(`${PROXY_API}/records/uploads?${qs}`)
  if (!res.ok) throw new Error('获取上传记录失败')
  return res.json()
}

/**
 * 分页查询文件转录记录
 */
export async function getFileTranscriptionRecords(params = {}) {
  const qs = buildRecordParams({ page: 1, page_size: 20, sort_by: 'created_at', sort_order: 'desc', ...params })
  const res = await apiFetch(`${PROXY_API}/records/file-transcriptions?${qs}`)
  if (!res.ok) throw new Error('获取转录记录失败')
  return res.json()
}

/**
 * 分页查询流式识别记录
 */
export async function getStreamingRecords(params = {}) {
  const qs = buildRecordParams({ page: 1, page_size: 20, sort_by: 'created_at', sort_order: 'desc', ...params })
  const res = await apiFetch(`${PROXY_API}/records/streaming?${qs}`)
  if (!res.ok) throw new Error('获取流式记录失败')
  return res.json()
}
