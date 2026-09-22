"""High-accuracy Speech Engine: Speech Recognition (STT) and Speech Synthesis (TTS).

Supports hardware audio capture from Qualcomm Microphone Array, ffmpeg-accelerated FLAC encoding,
Google Speech Recognition, Windows SAPI offline dictation, and Windows Media Speech Synthesis.
"""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import sys
import threading
from typing import Optional

# Monkeypatch SpeechRecognition's FLAC encoder to use ffmpeg when available
try:
    import speech_recognition as _sr

    def _ffmpeg_get_flac_data(self, convert_rate=None, convert_width=None):
        wav_data = self.get_wav_data(convert_rate, convert_width)
        startup_info = None
        if os.name == "nt":
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = subprocess.SW_HIDE

        proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-f", "flac", "pipe:1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startup_info,
        )
        flac_data, _ = proc.communicate(wav_data)
        if flac_data and flac_data[:4] == b"fLaC":
            return flac_data
        # Fallback to original
        return _orig_get_flac_data(self, convert_rate, convert_width)

    _orig_get_flac_data = _sr.AudioData.get_flac_data
    _sr.AudioData.get_flac_data = _ffmpeg_get_flac_data
except Exception:
    pass


# ------------------------------------------------------------------ TTS (Speech Synthesis)

_synth = None
_synth_lock = threading.Lock()


def _init_windows_synth():
    global _synth
    if _synth is None and sys.platform == "win32":
        try:
            import winsdk.windows.media.speechsynthesis as ss

            _synth = ss.SpeechSynthesizer()
        except Exception:
            _synth = None
    return _synth


def speak(text: str, wait: bool = True) -> None:
    """Speak text aloud using on-device speech synthesis."""
    text = text.strip()
    if not text:
        return

    def _do_speak():
        # Android / Termux TTS
        if os.environ.get("ARGUS_TARGET") == "android" or os.path.exists("/data/data/com.termux"):
            try:
                subprocess.run(["termux-tts-speak", text], check=False)
                return
            except Exception:
                pass

        if sys.platform == "win32":
            synth = _init_windows_synth()
            if synth is not None:
                try:
                    import winsound
                    import winsdk.windows.storage.streams as streams

                    async def _synthesize():
                        with _synth_lock:
                            stream = await synth.synthesize_text_to_stream_async(text)
                            reader = streams.DataReader(stream.get_input_stream_at(0))
                            await reader.load_async(stream.size)
                            data = bytes(reader.read_buffer(stream.size))
                            return data

                    wav_bytes = asyncio.run(_synthesize())
                    flags = winsound.SND_MEMORY
                    if not wait:
                        flags |= winsound.SND_ASYNC
                    winsound.PlaySound(wav_bytes, flags)
                    return
                except Exception:
                    pass

            # Fallback to PowerShell SAPI
            try:
                safe_text = text.replace(chr(34), "")
                for ch in ("$", "`", "(", ")", "{", "}"):
                    safe_text = safe_text.replace(ch, "")
                ps_script = f'Add-Type -AssemblyName System.speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Speak("{safe_text}")'
                subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script], capture_output=True)
                return
            except Exception:
                pass

        elif sys.platform == "darwin":
            subprocess.run(["say", text], check=False)
        else:
            subprocess.run(["spd-say", text], check=False)

    if wait:
        _do_speak()
    else:
        t = threading.Thread(target=_do_speak, daemon=True)
        t.start()


# ------------------------------------------------------------------ STT (Speech Recognition)

def _listen_windows_sapi(timeout_seconds: float = 8.0) -> str:
    """Listen to the default microphone using Windows SAPI SpeechRecognitionEngine."""
    script = f"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Add-Type -AssemblyName System.Speech
    $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $g = New-Object System.Speech.Recognition.DictationGrammar
    $rec.LoadGrammar($g)
    $rec.InitialSilenceTimeout = [TimeSpan]::FromSeconds({int(timeout_seconds)})
    $rec.BabbleTimeout = [TimeSpan]::FromSeconds({int(timeout_seconds)})
    $rec.EndSilenceTimeout = [TimeSpan]::FromSeconds(1.5)
    $rec.SetInputToDefaultAudioDevice()
    $r = $rec.Recognize([TimeSpan]::FromSeconds({int(timeout_seconds)}))
    if ($r -and $r.Text) {{
        Write-Output $r.Text
    }}
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 5,
        )
        return proc.stdout.strip()
    except Exception:
        return ""


def listen(prompt: str = "Listening (speak into your microphone)...", timeout_seconds: float = 6.0) -> str:
    """Listen to microphone input using Qualcomm microphone array and high-accuracy speech recognition."""
    print(f"\n======================================================================", flush=True)
    print(f" [SPEECH] {prompt}", flush=True)
    print(f" [SPEECH] Recording from Qualcomm Microphone Array ({int(timeout_seconds)}s)...", flush=True)
    print(f"======================================================================", flush=True)

    if sys.platform == "win32":
        try:
            import winsound

            winsound.Beep(1000, 150)  # Audio chime to start speaking
        except Exception:
            pass

    # Primary method: Real-time streaming audio capture with dynamic Voice Activity Detection (VAD)
    try:
        import sounddevice as sd
        import numpy as np
        import time

        sample_rate = 16000
        block_duration = 0.05  # 50ms chunks
        block_size = int(block_duration * sample_rate)

        silence_timeout = 1.2           # Seconds of silence after speech to finish utterance
        max_duration = max(timeout_seconds, 15.0)

        print("[ASR] Calibrating microphone noise level...", flush=True)

        frames = []
        is_speech_started = False
        silence_start_time = None
        last_dot_time = time.time()

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=block_size) as stream:
            # Calibrate ambient noise across first 200ms
            calib_chunks = []
            for _ in range(4):
                chunk, _ = stream.read(block_size)
                calib_chunks.append(chunk.flatten())
            ambient_noise = float(np.abs(np.concatenate(calib_chunks)).max()) if calib_chunks else 15.0
            speech_energy_threshold = max(ambient_noise * 2.2, 45.0)

            print(f"[ASR] Microphone active (ambient noise={ambient_noise:.0f}, trigger={speech_energy_threshold:.0f}). Listening for speech...", flush=True)
            start_time = time.time()

            while True:
                chunk, overflowed = stream.read(block_size)
                chunk_np = chunk.flatten()
                frames.append(chunk_np)

                chunk_amp = float(np.abs(chunk_np).max()) if len(chunk_np) > 0 else 0.0

                now = time.time()
                elapsed = now - start_time

                if not is_speech_started:
                    # Show a subtle listening dot every 1.5s
                    if now - last_dot_time > 1.5:
                        print(".", end="", flush=True)
                        last_dot_time = now

                    if chunk_amp > speech_energy_threshold:
                        is_speech_started = True
                        print(f"\n[ASR] Speech detected (amp={chunk_amp:.0f})! Streaming utterance...", flush=True)
                        silence_start_time = None
                    elif elapsed > max_duration:
                        # Timed out waiting for speech to begin
                        break
                else:
                    if chunk_amp > speech_energy_threshold:
                        silence_start_time = None
                    else:
                        if silence_start_time is None:
                            silence_start_time = now
                        elif now - silence_start_time >= silence_timeout:
                            # User stopped talking
                            print("[ASR] End of speech detected.", flush=True)
                            break

                if elapsed > max_duration:
                    print("\n[ASR] Maximum utterance duration reached.", flush=True)
                    break

        if frames:
            rec = np.concatenate(frames, axis=0)
        else:
            rec = np.array([], dtype=np.int16)

        max_amp = float(np.abs(rec).max()) if len(rec) > 0 else 0.0

        if is_speech_started and max_amp > 30:
            print("[ASR] Transcribing utterance on Qualcomm Snapdragon Hexagon NPU...", flush=True)

            # 1. Native Qualcomm Hexagon NPU Whisper (45 TOPS hardware accelerated)
            try:
                from . import whisper_npu

                npu_text = whisper_npu.transcribe_qualcomm_npu(rec, sample_rate)
                if npu_text and npu_text.strip():
                    print(f"\n[SPEECH] Heard (Qualcomm Hexagon NPU): '{npu_text.strip()}'\n", flush=True)
                    speak(f"Understood: {npu_text.strip()}", wait=True)
                    return npu_text.strip()
            except Exception as e:
                print(f"[NPU] On-device Whisper NPU error: {e}", flush=True)

            # 2. Try whisper-npu REST endpoint if running locally
            try:
                import speech_recognition as sr
                from . import whisper_npu

                audio_data = sr.AudioData(rec.tobytes(), sample_rate, 2)
                rest_text = whisper_npu.transcribe_whisper_rest(audio_data.get_wav_data(), timeout=1.0)
                if rest_text and rest_text.strip():
                    print(f"\n[SPEECH] Heard (whisper-npu REST): '{rest_text.strip()}'\n", flush=True)
                    speak(f"Understood: {rest_text.strip()}", wait=True)
                    return rest_text.strip()
            except Exception:
                pass

            # 3. Cloud Speech Recognizer (Fallback only if NPU did not transcribe)
            try:
                import speech_recognition as sr

                recognizer = sr.Recognizer()
                audio_data = sr.AudioData(rec.tobytes(), sample_rate, 2)
                print("[SPEECH] NPU gave empty transcript, trying fallback recognizer...", flush=True)
                text = recognizer.recognize_google(audio_data)
                if text and text.strip():
                    print(f"\n[SPEECH] Heard (Cloud Fallback): '{text.strip()}'\n", flush=True)
                    speak(f"Understood: {text.strip()}", wait=True)
                    return text.strip()
            except Exception as e:
                print(f"[SPEECH] Cloud recognizer error ({e}), trying local engine...", flush=True)
        else:
            print("\n[ASR] No speech input detected.", flush=True)
    except Exception as e:
        print(f"[ASR] Streaming audio capture error: {e}", flush=True)

    # Secondary method: Offline Windows SAPI dictation engine
    if sys.platform == "win32":
        text = _listen_windows_sapi(timeout_seconds)
        if text and text.strip():
            print(f"\n[SPEECH] Heard (Windows SAPI): '{text.strip()}'\n", flush=True)
            speak(f"Understood: {text.strip()}", wait=True)
            return text.strip()

    # Final fallback: Console keyboard entry
    try:
        spoken = input("Enter goal / command (or type here): ").strip()
        return spoken
    except (EOFError, KeyboardInterrupt):
        return ""
