"""Whisper NPU integration for Speech-to-Text (STT).

Supports:
1. whisper-npu REST API service (http://localhost:8000/v3/audio/translations)
   from https://github.com/anubhavgupta/whisper-npu
2. Hardware-accelerated Qualcomm Hexagon NPU (45 TOPS) on Snapdragon X Plus
   using precompiled Distil-Whisper via QNNExecutionProvider.
"""

from __future__ import annotations

import io
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_NPU_APP = None
_NPU_LOCK = threading.Lock()
_NPU_FAILED = False


def _init_qualcomm_npu():
    global _NPU_APP, _NPU_FAILED
    if _NPU_APP is not None or _NPU_FAILED:
        return _NPU_APP

    with _NPU_LOCK:
        if _NPU_APP is not None or _NPU_FAILED:
            return _NPU_APP

        env_whisper = os.environ.get("ARGUS_WHISPER_DIR")
        whisper_small_win = Path(r"B:\projects\Qualcomm\whisper_bundle\whisper_small_quantized_onnx\whisper_small_quantized-precompiled_qnn_onnx-w8a16-qualcomm_snapdragon_x_elite")
        distil_whisper_win = Path(r"B:\projects\Qualcomm\whisper_bundle\distil_whisper_onnx\distil_whisper-precompiled_qnn_onnx-float-qualcomm_snapdragon_x_elite")
        local_model_dir = Path(__file__).resolve().parent.parent / "models" / "whisper-small"
        android_dir = Path(os.path.expanduser("~/models/whisper-small"))
        android_tmp = Path("/data/local/tmp/models/whisper-small")

        check_dirs = [
            (Path(env_whisper) if env_whisper else None, "Custom ARGUS_WHISPER_DIR"),
            (android_dir, "Android Termux ~/models"),
            (android_tmp, "Android /data/local/tmp"),
            (local_model_dir, "Local models/whisper-small"),
            (whisper_small_win, "Windows Snapdragon X Elite Whisper-Small"),
            (distil_whisper_win, "Windows Snapdragon X Elite Distil-Whisper"),
        ]

        candidates = []
        for d, name in check_dirs:
            if d and d.is_dir():
                enc = d / "encoder.onnx"
                dec = d / "decoder.onnx"
                hf_id = "openai/whisper-small"
                candidates.append((enc, dec, hf_id, name))

        selected = None
        for enc, dec, hf_id, name in candidates:
            if enc.is_file() and dec.is_file():
                selected = (enc, dec, hf_id, name)
                break

        if selected is None:
            _NPU_FAILED = True
            return None

        encoder_path, decoder_path, hf_model_id, model_name = selected

        try:
            whisper_py_dir = r"B:\projects\Qualcomm\whisper_app\whisper_windows_py"
            if whisper_py_dir not in sys.path:
                sys.path.insert(0, whisper_py_dir)

            import onnxruntime_qnn as qnn_ep

            dll_path = "C:/Qualcomm/AIStack/QAIRT/2.47.1.260610/lib/aarch64-windows-msvc"
            if os.path.exists(dll_path):
                os.add_dll_directory(dll_path)

            package_dir = os.path.dirname(qnn_ep.__file__)
            os.add_dll_directory(package_dir)

            adsp_path = f"C:/Qualcomm/AIStack/QAIRT/2.47.1.260610/lib/hexagon-v73/unsigned;{package_dir}"
            os.environ["ADSP_LIBRARY_PATH"] = adsp_path

            import qai_hub_models.utils.onnx.torch_wrapper as tw

            tw.ONNXRUNTIME_ENV_CHECKED = True
            tw.ONNXRUNTIME_QNN_ERROR = None

            from test_whisper_npu import (
                HfWhisperApp,
                NPUModelTorchWrapper,
                OnnxSessionOptions,
                QNNExecutionProviderOptions,
            )

            session_options = OnnxSessionOptions.aihub_defaults()
            session_options.context_enable = False
            npu_options = QNNExecutionProviderOptions.aihub_defaults()

            _NPU_APP = HfWhisperApp(
                NPUModelTorchWrapper(str(encoder_path), session_options, [npu_options]),
                NPUModelTorchWrapper(str(decoder_path), session_options, [npu_options]),
                hf_model_id,
            )
            print(f"[NPU] Qualcomm Hexagon NPU {model_name} initialized successfully.", flush=True)
            return _NPU_APP
        except Exception as e:
            logger.warning("Failed to initialize Qualcomm NPU Whisper: %s", e)
            _NPU_FAILED = True
            return None


def transcribe_whisper_rest(wav_bytes: bytes, port: int = 8000, timeout: float = 5.0) -> Optional[str]:
    """Transcribe audio using a running whisper-npu REST server.

    Compatible with https://github.com/anubhavgupta/whisper-npu endpoint.
    """
    import urllib.error
    import urllib.request

    url = f"http://localhost:{port}/v3/audio/translations"
    boundary = "----WebKitFormBoundaryWhisperNPU"
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    body = io.BytesIO()
    # model field
    body.write(f"--{boundary}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    body.write(b"whisper-npu\r\n")
    # response_format field
    body.write(f"--{boundary}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="response_format"\r\n\r\n')
    body.write(b"json\r\n")
    # file field
    body.write(f"--{boundary}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n')
    body.write(b"Content-Type: audio/wav\r\n\r\n")
    body.write(wav_bytes)
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(url, data=body.getvalue(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                import json

                data = json.loads(response.read().decode())
                if isinstance(data, dict):
                    return data.get("text", "").strip() or None
                return str(data).strip() or None
    except Exception:
        pass
    return None


def warmup_npu() -> None:
    """Pre-warm the Qualcomm Hexagon NPU Whisper model."""
    _init_qualcomm_npu()


def warmup_npu_background() -> None:
    """Pre-warm the Qualcomm Hexagon NPU Whisper model in a background thread."""
    def _worker():
        try:
            _init_qualcomm_npu()
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def transcribe_qualcomm_npu(audio_np, sample_rate: int = 16000) -> Optional[str]:
    """Transcribe numpy audio data directly on Qualcomm Hexagon NPU."""
    import numpy as np

    app = _init_qualcomm_npu()
    if app is None:
        logger.warning("[NPU] Qualcomm Hexagon NPU failed to initialize.")
        return None

    try:
        if audio_np.dtype == np.int16:
            audio_float = audio_np.astype(np.float32) / 32768.0
        elif audio_np.dtype == np.int32:
            audio_float = audio_np.astype(np.float32) / 2147483648.0
        else:
            audio_float = audio_np.astype(np.float32)

        if audio_float.ndim == 2:
            audio_float = audio_float.mean(-1)

        print("[NPU] Executing speech inference on Snapdragon Hexagon NPU (45 TOPS)...", flush=True)
        result = app.transcribe(audio_float, sample_rate)
        if result and isinstance(result, str):
            res_str = result.strip()
            if res_str:
                print(f"[NPU] Transcription successful on Hexagon NPU: '{res_str}'", flush=True)
                return res_str
        return None
    except Exception as e:
        logger.warning("Qualcomm NPU transcription failed: %s", e)
        print(f"[NPU] Transcription error: {e}", flush=True)
        return None

