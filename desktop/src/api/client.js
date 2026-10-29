// OneASR API Client with Dynamic Base URL & Protocol Support
import { isTauri } from '../utils/env';

export const DEFAULT_LOCAL_API_BASE = 'http://127.0.0.1:8020';
export const DEFAULT_API_KEY = 'sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u';

export function getDefaultApiBaseUrl() {
  if (isTauri) {
    return DEFAULT_LOCAL_API_BASE;
  }
  if (typeof window !== 'undefined' && window.location) {
    const origin = window.location.origin;
    // When running in Vite dev server (port 8021), route API requests to local backend 8020
    if (origin && origin.includes(':8021')) {
      return DEFAULT_LOCAL_API_BASE;
    }
    // When running in pure web browser hosted by backend or reverse proxy, default to current host:port
    if (
      origin &&
      (origin.startsWith('http://') || origin.startsWith('https://')) &&
      !origin.includes('tauri.localhost')
    ) {
      return origin;
    }
  }
  return DEFAULT_LOCAL_API_BASE;
}

export function getApiBaseUrl() {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('oneasr_api_base');
    if (custom && custom.trim()) {
      return custom.trim().replace(/\/+$/, '');
    }
  }
  return getDefaultApiBaseUrl();
}

export function getWsBaseUrl() {
  const httpBase = getApiBaseUrl();
  if (httpBase.startsWith('https://')) {
    return httpBase.replace(/^https:\/\//, 'wss://');
  }
  return httpBase.replace(/^http:\/\//, 'ws://');
}

export function setApiBaseUrl(url) {
  if (typeof window !== 'undefined') {
    if (!url || !url.trim() || url.trim() === getDefaultApiBaseUrl()) {
      localStorage.removeItem('oneasr_api_base');
    } else {
      localStorage.setItem('oneasr_api_base', url.trim().replace(/\/+$/, ''));
    }
  }
}

export function resetApiBaseUrl() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('oneasr_api_base');
  }
}

export class OneASRClient {
  constructor(baseUrl = null) {
    this._customBaseUrl = baseUrl;
  }

  get baseUrl() {
    return this._customBaseUrl || getApiBaseUrl();
  }

  getWsBaseUrl() {
    return getWsBaseUrl();
  }

  getHeaders(customHeaders = {}) {
    const key = localStorage.getItem('oneasr_api_key') || DEFAULT_API_KEY;
    return {
      Authorization: `Bearer ${key}`,
      ...customHeaders
    };
  }

  async get(path) {
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        headers: this.getHeaders()
      });
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  }

  async post(path, body = {}) {
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: this.getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
      });
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  }

  async checkHealth() {
    try {
      const res = await fetch(`${this.baseUrl}/v1/x/info`, {
        method: 'GET',
        headers: this.getHeaders()
      });
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  }

  async testConnection(targetUrl = null) {
    const base = (targetUrl || this.baseUrl).replace(/\/+$/, '');
    try {
      const res = await fetch(`${base}/v1/x/info`, {
        method: 'GET',
        headers: this.getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        return { ok: true, data };
      }
      return { ok: false, status: res.status };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  }

  async getModels() {
    try {
      const res = await fetch(`${this.baseUrl}/v1/x/models`, {
        headers: this.getHeaders()
      });
      if (res.ok) {
        return await res.json();
      }
      // Fallback to standard OpenAI /v1/models
      const stdRes = await fetch(`${this.baseUrl}/v1/models`, {
        headers: this.getHeaders()
      });
      if (stdRes.ok) {
        const data = await stdRes.json();
        return {
          active_model: data.data?.[0]?.id || 'sensevoice-small',
          models: data.data || []
        };
      }
      return { active_model: 'sensevoice-small', models: [] };
    } catch (err) {
      console.warn('[OneASR API] getModels error:', err);
      return { active_model: 'sensevoice-small', models: [] };
    }
  }

  async loadModel(modelId) {
    const res = await fetch(`${this.baseUrl}/v1/x/models/${modelId}/load`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return await res.json();
  }

  async unloadModel(modelId) {
    const res = await fetch(`${this.baseUrl}/v1/x/models/${modelId}/unload`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    return await res.json();
  }

  async deleteModel(modelId) {
    const res = await fetch(`${this.baseUrl}/v1/x/models/${modelId}`, {
      method: 'DELETE',
      headers: this.getHeaders()
    });
    return await res.json();
  }

  async downloadModel(modelId, source = null) {
    const payload = { model_id: modelId };
    if (source) {
      payload.source = source;
    }
    const res = await fetch(`${this.baseUrl}/v1/x/models/pull`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    return await res.json();
  }

  async getSystemSettings() {
    try {
      const res = await fetch(`${this.baseUrl}/v1/x/system/settings`, {
        headers: this.getHeaders()
      });
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  }

  async updateSystemSettings(settings) {
    const res = await fetch(`${this.baseUrl}/v1/x/system/settings`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(settings)
    });
    return await res.json();
  }

  /**
   * Transcribe audio file or blob via /v1/audio/transcriptions
   */
  async transcribeAudio(fileOrBlob, model = 'sensevoice-small', language = '') {
    const formData = new FormData();
    const filename = fileOrBlob.name || 'dictation.wav';
    formData.append('file', fileOrBlob, filename);
    formData.append('model', model);
    formData.append('response_format', 'verbose_json');
    if (language) {
      formData.append('language', language);
    }

    const startTime = performance.now();
    const res = await fetch(`${this.baseUrl}/v1/audio/transcriptions`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: formData
    });

    const elapsedMs = Math.round(performance.now() - startTime);

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Server returned ${res.status}: ${errorText}`);
    }

    const data = await res.json();
    return {
      text: data.text || '',
      duration: data.duration || 0,
      segments: data.segments || [],
      latencyMs: elapsedMs,
      rtf: data.duration > 0 ? (elapsedMs / 1000 / data.duration).toFixed(3) : '0.00'
    };
  }

  /**
   * Upload audio/video file (multipart) via /v1/x/files (supports up to 2GB)
   */
  async uploadFile(fileOrBlob) {
    const formData = new FormData();
    const filename = fileOrBlob.name || 'audio.wav';
    formData.append('file', fileOrBlob, filename);

    const res = await fetch(`${this.baseUrl}/v1/x/files`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: formData
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Upload failed (${res.status}): ${errText}`);
    }
    return await res.json();
  }

  /**
   * Register local audio/video file path directly via /v1/x/files/import-local (instant, zero copy)
   */
  async importLocalFile(filePath) {
    const res = await fetch(`${this.baseUrl}/v1/x/files/import-local`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ file_path: filePath })
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Import failed (${res.status}): ${errText}`);
    }
    return await res.json();
  }

  /**
   * Create async transcription task via /v1/x/audio/transcriptions
   */
  async createTranscriptionTask(fileUuid, model, language = '') {
    const payload = {
      file_uuid: fileUuid,
      model: model,
      response_format: 'verbose_json'
    };
    if (language && language !== 'auto') {
      payload.language = language;
    }

    const res = await fetch(`${this.baseUrl}/v1/x/audio/transcriptions`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Task creation failed (${res.status}): ${errText}`);
    }
    return await res.json();
  }

  /**
   * Query transcription task status and progress via /v1/x/audio/transcriptions/{taskId}
   */
  async getTranscriptionTask(taskId) {
    const res = await fetch(`${this.baseUrl}/v1/x/audio/transcriptions/${taskId}`, {
      headers: this.getHeaders()
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Query failed (${res.status}): ${errText}`);
    }
    return await res.json();
  }

  /**
   * Cancel transcription task via /v1/x/audio/transcriptions/{taskId}/cancel
   */
  async cancelTranscriptionTask(taskId) {
    try {
      const res = await fetch(`${this.baseUrl}/v1/x/audio/transcriptions/${taskId}/cancel`, {
        method: 'POST',
        headers: this.getHeaders()
      });
      return await res.json();
    } catch (err) {
      console.warn('[OneASR API] cancel task error:', err);
      return null;
    }
  }
}

export const apiClient = new OneASRClient();
