/**
 * 测试文件识别流式返回接口
 *
 * 用法: node test-stream.js <音频文件路径> [引擎名称]
 * 示例: node test-stream.js ../test.mp3 faster-whisper
 */

import { readFileSync } from 'fs'
import { basename } from 'path'

const BASE = 'http://127.0.0.1:8000'
const API_KEY = 'oneasr-key'

const filePath = process.argv[2] || '/Users/dudu/Files/Video/哔哩哔哩(bilibili)视频解析下载 - 保存B站视频到手机、电脑(3).mp4'
const engine = process.argv[3] || 'faster-whisper'

const fileBuffer = readFileSync(filePath)
const fileName = basename(filePath)

// 构造 multipart/form-data
const boundary = '----TestBoundary' + Date.now()
const filePart = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${fileName}"\r\nContent-Type: application/octet-stream\r\n\r\n`
const enginePart = engine ? `\r\n--${boundary}\r\nContent-Disposition: form-data; name="engine"\r\n\r\n${engine}` : ''
const ending = `\r\n--${boundary}--\r\n`

const body = engine
  ? Buffer.concat([Buffer.from(filePart, 'utf-8'), fileBuffer, Buffer.from(enginePart, 'utf-8'), Buffer.from(ending, 'utf-8')])
  : Buffer.concat([Buffer.from(filePart, 'utf-8'), fileBuffer, Buffer.from(ending, 'utf-8')])

const url = `${BASE}/api/v1/transcribe/file/stream`

console.log(`请求: POST ${url}`)
console.log(`文件: ${fileName} (${fileBuffer.length} bytes)`)
console.log(`引擎: ${engine || '默认'}`)
console.log('---')

try {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': `multipart/form-data; boundary=${boundary}`,
    },
    body,
  })

  if (!res.ok) {
    console.error(`请求失败: ${res.status} ${res.statusText}`)
    console.error(await res.text())
    process.exit(1)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let count = 0
  const startTime = Date.now()
  let firstChunkTime = 0

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const parts = buffer.split('\n\n')
    buffer = parts.pop()

    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data: ')) continue
      const data = JSON.parse(line.slice(6))
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
      if (data.done) {
        const totalTime = ((Date.now() - startTime) / 1000).toFixed(1)
        console.log(`\n--- 识别完成 --- 总耗时: ${totalTime}s`)
      } else if (data.error) {
        console.error(`\n错误: ${data.error}`)
      } else {
        count++
        if (count === 1) firstChunkTime = Date.now() - startTime
        console.log(`[${count}] [+${elapsed}s] ${data.start.toFixed(1)}s ~ ${data.end.toFixed(1)}s: ${data.text}`)
      }
    }
  }

  const totalTime = ((Date.now() - startTime) / 1000).toFixed(1)
  console.log(`\n共识别 ${count} 句`)
  console.log(`首句延迟: ${(firstChunkTime / 1000).toFixed(1)}s`)
  console.log(`总耗时: ${totalTime}s`)
} catch (err) {
  console.error('请求异常:', err.message)
  process.exit(1)
}
