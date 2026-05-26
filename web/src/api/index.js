// 后端直连地址（SSE 流式请求绕过 Vite proxy，避免缓冲）
const API_BASE = 'http://127.0.0.1:8000'
const PROXY_BASE = '/api/v1'

function getApiKey() {
  return localStorage.getItem('api_key') || ''
}

export function setApiKey(key) {
  localStorage.setItem('api_key', key)
}

export function getStoredApiKey() {
  return getApiKey()
}

export async function getEngines() {
  const res = await fetch(`${PROXY_BASE}/engines`, {
    headers: { 'X-API-Key': getApiKey() },
  })
  if (res.status === 401) throw new Error('API Key 无效')
  return res.json()
}

/**
 * 通用 SSE 流式读取（fetch + ReadableStream）
 * 逐行解析 data: {...} 事件，调用 onSegment / onDone / onError
 */
async function streamSse(url, body, onSegment, onDone, onError) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'X-API-Key': getApiKey(),
      },
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
    onError(err.message === 'Failed to fetch' ? new Error('无法连接后端服务') : err)
  }
}

export function transcribeFileStream(file, engine, onSegment, onDone, onError) {
  const form = new FormData()
  form.append('file', file)
  const params = engine ? `?engine=${engine}` : ''

  const ctrl = new AbortController()
  streamSse(
    `${API_BASE}/api/v1/transcribe/file/stream${params}`,
    form,
    onSegment,
    onDone,
    onError,
  )
  // 返回可中止的对象
  return { abort: () => ctrl.abort() }
}

export function transcribeUrlStream(url, engine, onSegment, onDone, onError) {
  const params = engine ? `?engine=${engine}` : ''

  const ctrl = new AbortController()
  streamSse(
    `${API_BASE}/api/v1/transcribe/url/stream${params}`,
    JSON.stringify({ url, engine }),
    onSegment,
    onDone,
    onError,
  )
  return { abort: () => ctrl.abort() }
}
