// OneASR API Client
const API_BASE = 'http://127.0.0.1:8020';
const DEFAULT_API_KEY = 'sk-oneasr-v1-p_L3kXm9QZ8sT2vA4wE7rY1u';

export class OneASRClient {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
  }

  getHeaders(customHeaders = {}) {
    const key = localStorage.getItem('oneasr_api_key') || DEFAULT_API_KEY;
    return {
      Authorization: `Bearer ${key}`,
      ...customHeaders
    };
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

  async downloadModel(modelId) {
    const res = await fetch(`${this.baseUrl}/v1/x/models/pull`, {
      method: 'POST',
      headers: this.getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ model_id: modelId, source: 'auto' })
    });
    return await res.json();
  }

  async getSystemSettings() {
    try {
      const res = await fetch(`${this.baseUrl}/v1/x/system`, {
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
}

export const apiClient = new OneASRClient();
