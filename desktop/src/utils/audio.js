// Web Audio API & Microphone Toolkit for OneASR

export class AudioEngine {
  constructor() {
    this.audioContext = null;
    this.mediaStream = null;
    this.analyser = null;
    this.processor = null;
    this.isRecording = false;
    this.onVolumeCallback = null;
    this.onAudioChunkCallback = null;
    this.audioChunks = [];
    this.sourceSampleRate = 16000;
  }

  /**
   * Enumerate all audio input devices (microphones)
   */
  static async getMicrophones() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        return [];
      }
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices
        .filter((d) => d.kind === 'audioinput')
        .map((d, index) => ({
          deviceId: d.deviceId,
          label: d.label || `Microphone ${index + 1}`,
          groupId: d.groupId
        }));
    } catch (err) {
      console.warn('[OneASR Audio] Failed to enumerate audio devices:', err);
      return [];
    }
  }

  /**
   * Start microphone capture
   * @param {string} deviceId Specific deviceId or '' for default
   * @param {Function} onVolume Callback with volume percentage (0 - 100)
   * @param {Function} onAudioChunk Optional callback for streaming Float32 PCM
   */
  async startRecording(deviceId = '', onVolume = null, onAudioChunk = null) {
    if (this.isRecording) {
      await this.stopRecording();
    }

    this.onVolumeCallback = onVolume;
    this.onAudioChunkCallback = onAudioChunk;
    this.audioChunks = [];

    const audioConstraints = {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      ...(deviceId ? { deviceId: { exact: deviceId } } : {})
    };

    try {
      // 1. Acquire media stream (with fallback to basic audio: true)
      try {
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: audioConstraints
        });
      } catch (err) {
        console.warn('[OneASR Audio] Failed with constraints, retrying with simple audio request:', err);
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: true
        });
      }

      // 2. Initialize native AudioContext (supports any macOS hardware sample rate: 44.1k/48k/16k)
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioContextClass();
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }
      this.sourceSampleRate = this.audioContext.sampleRate || 44100;

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);

      // 3. Volume Analyser Node
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.4;
      source.connect(this.analyser);

      // 4. Audio Processor for PCM extraction
      const bufferSize = 4096;
      this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
      this.processor.onaudioprocess = (e) => {
        if (!this.isRecording) return;
        const inputData = e.inputBuffer.getChannelData(0);
        // Clone float32 data
        const pcmCopy = new Float32Array(inputData);
        this.audioChunks.push(pcmCopy);

        if (this.onAudioChunkCallback) {
          this.onAudioChunkCallback(pcmCopy);
        }
      };

      source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);

      this.isRecording = true;
      this._startVolumeMeter();
      return true;
    } catch (err) {
      console.error('[OneASR Audio] Error starting audio recording:', err);
      throw err;
    }
  }

  _startVolumeMeter() {
    if (!this.analyser) return;
    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);

    const updateVolume = () => {
      if (!this.isRecording || !this.analyser) return;
      this.analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const avg = sum / dataArray.length;
      const volumePct = Math.min(100, Math.round((avg / 128) * 100));

      if (this.onVolumeCallback) {
        this.onVolumeCallback(volumePct);
      }
      requestAnimationFrame(updateVolume);
    };

    requestAnimationFrame(updateVolume);
  }

  /**
   * Downsample Float32Array PCM buffer to target sample rate (default: 16000)
   */
  downsampleBuffer(buffer, inputRate, outputRate = 16000) {
    if (inputRate === outputRate) return buffer;
    const ratio = inputRate / outputRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0;
      let count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  /**
   * Convert Float32Array PCM chunk to 16kHz PCM16 Base64 string for WebSocket streaming
   */
  float32ToPcm16Base64(float32Chunk, inputRate = this.sourceSampleRate) {
    const resampled = this.downsampleBuffer(float32Chunk, inputRate, 16000);
    const int16Array = new Int16Array(resampled.length);
    for (let i = 0; i < resampled.length; i++) {
      const s = Math.max(-1, Math.min(1, resampled[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    const uint8 = new Uint8Array(int16Array.buffer);
    let binary = '';
    const len = uint8.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(uint8[i]);
    }
    return window.btoa(binary);
  }

  /**
   * Stop recording and export WAV Blob
   * @returns {Blob} 16kHz Mono WAV Blob
   */
  async stopRecording() {
    if (!this.isRecording) return null;
    this.isRecording = false;

    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    const rate = this.sourceSampleRate;
    if (this.audioContext) {
      await this.audioContext.close();
      this.audioContext = null;
    }

    if (this.onVolumeCallback) {
      this.onVolumeCallback(0);
    }

    // Merge audio chunks into a single Float32Array
    const totalLength = this.audioChunks.reduce((acc, chunk) => acc + chunk.length, 0);
    if (totalLength === 0) return null;

    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of this.audioChunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    // Downsample from hardware rate (e.g. 48000 or 44100) to 16000
    const resampled = this.downsampleBuffer(merged, rate, 16000);

    return this.encodeWAV(resampled, 16000);
  }

  /**
   * Convert Float32Array PCM to 16-bit PCM WAV Blob
   */
  encodeWAV(samples, sampleRate = 16000) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    const writeString = (offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    // RIFF identifier
    writeString(0, 'RIFF');
    // file length
    view.setUint32(4, 36 + samples.length * 2, true);
    // RIFF type
    writeString(8, 'WAVE');
    // format chunk identifier
    writeString(12, 'fmt ');
    // format chunk length
    view.setUint32(16, 16, true);
    // sample format (1 = PCM)
    view.setUint16(20, 1, true);
    // channel count (1 = mono)
    view.setUint16(22, 1, true);
    // sample rate
    view.setUint32(24, sampleRate, true);
    // byte rate (sample rate * block align)
    view.setUint32(28, sampleRate * 2, true);
    // block align (channel count * bytes per sample)
    view.setUint16(32, 2, true);
    // bits per sample
    view.setUint16(34, 16, true);
    // data chunk identifier
    writeString(36, 'data');
    // data chunk length
    view.setUint32(40, samples.length * 2, true);

    // Float32 to Int16
    let index = 44;
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      index += 2;
    }

    return new Blob([view], { type: 'audio/wav' });
  }
}
