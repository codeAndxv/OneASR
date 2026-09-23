"""AudioConverter 单元测试。

测试项目：
1. PCM16 与 Float32 相互转换精度与边界
2. 异常字节（奇数长度、空字节）容错处理
3. Base64 编解码安全验证
4. 内存 WAV 生成与解析
5. 音频时长计算
6. FFmpeg 内存管道全格式解码
"""

import io
import wave
import numpy as np
import pytest

from app.utils.audio_converter import AudioConverter


class TestAudioConverterPCM:
    """PCM 与 Float32 转换测试。"""

    def test_pcm16_to_float32_basic(self):
        # 构建已知的 int16 采样点: 0, 32767, -32768, 16384, -16384
        i16_arr = np.array([0, 32767, -32768, 16384, -16384], dtype=np.int16)
        raw_bytes = i16_arr.tobytes()

        float_arr = AudioConverter.pcm16_to_float32(raw_bytes)

        assert float_arr.dtype == np.float32
        assert len(float_arr) == 5
        assert np.isclose(float_arr[0], 0.0, atol=1e-4)
        assert np.isclose(float_arr[1], 32767.0 / 32768.0, atol=1e-4)
        assert np.isclose(float_arr[2], -1.0, atol=1e-4)
        assert np.isclose(float_arr[3], 0.5, atol=1e-4)
        assert np.isclose(float_arr[4], -0.5, atol=1e-4)

    def test_pcm16_to_float32_empty_and_odd_bytes(self):
        # 空数据
        assert len(AudioConverter.pcm16_to_float32(b"")) == 0
        assert len(AudioConverter.pcm16_to_float32(None)) == 0

        # 单字节（不完整采样点）
        assert len(AudioConverter.pcm16_to_float32(b"\x00")) == 0

        # 奇数个字节（应截断最后一个多余字节）
        i16_arr = np.array([1000, 2000], dtype=np.int16)
        odd_bytes = i16_arr.tobytes() + b"\xff"
        res = AudioConverter.pcm16_to_float32(odd_bytes)
        assert len(res) == 2
        assert np.isclose(res[0], 1000.0 / 32768.0, atol=1e-4)
        assert np.isclose(res[1], 2000.0 / 32768.0, atol=1e-4)

    def test_float32_to_pcm16_basic(self):
        float_arr = np.array([0.0, 1.0, -1.0, 0.5, -0.5], dtype=np.float32)
        pcm_bytes = AudioConverter.float32_to_pcm16(float_arr)

        assert len(pcm_bytes) == len(float_arr) * 2
        recovered_i16 = np.frombuffer(pcm_bytes, dtype=np.int16)

        assert recovered_i16[0] == 0
        assert recovered_i16[1] == 32767
        assert recovered_i16[2] == -32767
        assert np.isclose(recovered_i16[3], 16383, atol=1)
        assert np.isclose(recovered_i16[4], -16383, atol=1)

    def test_float32_to_pcm16_clipping(self):
        # 超过 [-1.0, 1.0] 的极值测试
        float_arr = np.array([2.5, -3.0], dtype=np.float32)
        pcm_bytes = AudioConverter.float32_to_pcm16(float_arr)
        recovered_i16 = np.frombuffer(pcm_bytes, dtype=np.int16)

        assert recovered_i16[0] == 32767
        assert recovered_i16[1] == -32767

    def test_roundtrip_pcm16_float32(self):
        # 生成随机音频信号进行往返转换测试
        np.random.seed(42)
        orig_i16 = (np.random.randn(16000) * 10000).astype(np.int16)
        raw_bytes = orig_i16.tobytes()

        float_arr = AudioConverter.pcm16_to_float32(raw_bytes)
        recovered_bytes = AudioConverter.float32_to_pcm16(float_arr)
        recovered_i16 = np.frombuffer(recovered_bytes, dtype=np.int16)

        # 整数往返误差不应超过 1
        max_diff = np.max(np.abs(orig_i16.astype(np.int32) - recovered_i16.astype(np.int32)))
        assert max_diff <= 1


class TestAudioConverterBase64:
    """Base64 转换测试。"""

    def test_base64_roundtrip(self):
        raw = b"\x01\x02\x03\x04\x05\x06"
        b64 = AudioConverter.pcm16_to_base64(raw)
        assert isinstance(b64, str)
        decoded = AudioConverter.base64_to_pcm16(b64)
        assert decoded == raw

    def test_base64_invalid(self):
        assert AudioConverter.base64_to_pcm16("") == b""
        assert AudioConverter.base64_to_pcm16(None) == b""


class TestAudioConverterWAV:
    """WAV 封装与解析测试。"""

    def test_pcm16_to_wav_bytes(self):
        i16_arr = np.zeros(16000, dtype=np.int16)  # 1秒 16kHz 静音
        wav_bytes = AudioConverter.pcm16_to_wav_bytes(i16_arr.tobytes(), sample_rate=16000, channels=1)

        assert len(wav_bytes) == 16000 * 2 + 44  # 44字节头 + 32000 字节数据
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 16000

    def test_float32_to_wav_bytes(self):
        float_arr = np.zeros(8000, dtype=np.float32)  # 0.5秒 16kHz
        wav_bytes = AudioConverter.float32_to_wav_bytes(float_arr, sample_rate=16000, channels=1)

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 8000

    def test_wav_bytes_to_pcm16_roundtrip(self):
        orig_i16 = np.array([100, 200, 300, -100, -200], dtype=np.int16)
        wav_bytes = AudioConverter.pcm16_to_wav_bytes(orig_i16.tobytes(), sample_rate=16000, channels=1)

        raw_pcm, rate, channels = AudioConverter.wav_bytes_to_pcm16(wav_bytes)
        assert rate == 16000
        assert channels == 1
        assert raw_pcm == orig_i16.tobytes()

    def test_get_audio_duration(self):
        # 1. 裸 PCM 时长计算（16000 采样点 = 1 秒）
        raw_pcm = np.zeros(16000, dtype=np.int16).tobytes()
        assert AudioConverter.get_audio_duration(raw_pcm, sample_rate=16000) == 1.0

        # 2. WAV 时长计算
        wav_bytes = AudioConverter.pcm16_to_wav_bytes(raw_pcm, sample_rate=16000)
        assert AudioConverter.get_audio_duration(wav_bytes) == 1.0


class TestAudioConverterFFmpeg:
    """FFmpeg 内存管道解码测试。"""

    def test_decode_wav_bytes_to_float32(self):
        # 生成 1 秒的正弦波 WAV 数据
        sr = 16000
        t = np.linspace(0, 1, sr, endpoint=False)
        sin_wave = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        wav_bytes = AudioConverter.float32_to_wav_bytes(sin_wave, sample_rate=sr)

        # 通过 FFmpeg 内存管道解码
        decoded_float = AudioConverter.decode_to_pcm_float32(wav_bytes, sample_rate=sr)

        assert len(decoded_float) == sr
        # 验证信号波形相关性
        correlation = np.corrcoef(sin_wave, decoded_float)[0, 1]
        assert correlation > 0.99

    def test_decode_to_pcm16_bytes(self):
        sr = 16000
        sin_wave = np.zeros(8000, dtype=np.float32)  # 0.5s
        wav_bytes = AudioConverter.float32_to_wav_bytes(sin_wave, sample_rate=sr)

        pcm16_bytes = AudioConverter.decode_to_pcm16_bytes(wav_bytes, sample_rate=sr)
        assert len(pcm16_bytes) == 8000 * 2
