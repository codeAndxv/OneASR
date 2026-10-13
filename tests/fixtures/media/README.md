# OneASR Built-in Test Media Fixtures (100% Public Domain)

All audio and video files in this directory are derived from an official U.S. Federal Government work and are in the **Public Domain** worldwide pursuant to **17 U.S.C. § 105** (zero copyright restrictions).

## Source Information
- **Title**: *2015-05-02 President Obama's Weekly Address ("Ensuring Every Child Gets a Great Education")*
- **Source**: The White House / Wikimedia Commons (`File:2015-05-02 President Obama's Weekly Address.webm`)
- **License**: **Public Domain** (Work of the United States Government)

## Files Included

| Filename | Duration | Format | Size | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `en_speech_15s.wav` | 15s (`00:01`–`00:16`) | 16kHz, mono, 16-bit PCM WAV | ~469 KB | Fast ASR inference, WebSocket streaming (`xasr`), E2E API tests |
| `en_speech_120s.mp3` | 120s (`00:01`–`02:01`) | 16kHz, mono, 64kbps MP3 | ~939 KB | Long-audio VAD chunking (`process_long_audio`), SSE streaming, multi-segment SRT/VTT |
| `en_video_60s.mp4` | 60s (`00:01`–`01:01`) | H.264 (`320x180`) + AAC (`16kHz`) MP4 | ~668 KB | Video upload audio-extraction transcription & `cli/clip.py` video clipping tests |

## Ground Truth Excerpt (First 15s of Speech)
> "Hi, everybody. I'm speaking with you from the D.C. Public Library in Anacostia, where I just spent some time with some wonderful young people..."
