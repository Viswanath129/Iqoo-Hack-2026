"""OCR engine adapter supporting Windows (NPU / WinRT OCR) and macOS (Vision via ocrmac)."""

from __future__ import annotations

import asyncio
import gc
import sys
import threading
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from .models import Box

Line = tuple[str, float, "Box"]

# ------------------------------------------------------------------ Windows NPU / WinRT OCR
_WINRT_OCR_AVAILABLE = False
_ocr_engine = None
_ocr_imaging = None
_ocr_crypto = None
_ocr_lock = threading.Lock()  # Serialize WinRT recognize_async calls


class _AsyncWorker:
    """Dedicated background thread hosting a persistent event loop for WinRT async calls."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="WinRT-OCR-Loop")
        self._thread.start()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()


_async_worker: _AsyncWorker | None = None

if sys.platform == "win32":
    try:
        import atexit

        import winsdk.windows.graphics.imaging as _ocr_imaging
        import winsdk.windows.media.ocr as win_ocr
        import winsdk.windows.security.cryptography as _ocr_crypto

        _ocr_engine = win_ocr.OcrEngine.try_create_from_user_profile_languages()
        if _ocr_engine is None:
            import winsdk.windows.globalization as glob

            _ocr_engine = win_ocr.OcrEngine.try_create_from_language(glob.Language("en-US"))

        if _ocr_engine is not None:
            _WINRT_OCR_AVAILABLE = True
            _async_worker = _AsyncWorker()

            def _cleanup_ocr_engine() -> None:
                global _ocr_engine, _async_worker
                _ocr_engine = None
                _async_worker = None
                gc.collect()

            atexit.register(_cleanup_ocr_engine)
    except Exception:
        _WINRT_OCR_AVAILABLE = False


async def _winrt_recognize_async(image: Image.Image) -> list[Line]:
    """Recognize text using Windows WinRT OCR, accelerated on Qualcomm Hexagon NPU / DirectML."""
    if _ocr_engine is None or _ocr_imaging is None or _ocr_crypto is None:
        return []

    # Ensure RGBA image for 32-bit pixel buffer
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    raw_bytes = rgba.tobytes()

    ibuffer = _ocr_crypto.CryptographicBuffer.create_from_byte_array(raw_bytes)
    software_bitmap = _ocr_imaging.SoftwareBitmap.create_copy_from_buffer(
        ibuffer,
        _ocr_imaging.BitmapPixelFormat.RGBA8,
        rgba.width,
        rgba.height,
        _ocr_imaging.BitmapAlphaMode.PREMULTIPLIED,
    )

    result = await _ocr_engine.recognize_async(software_bitmap)
    lines: list[Line] = []
    for line in result.lines:
        text = line.text.strip()
        if not text or not line.words:
            continue
        # Compute line bounding box in crop-relative coordinates
        x1 = min(float(w.bounding_rect.x) for w in line.words)
        y1 = min(float(w.bounding_rect.y) for w in line.words)
        x2 = max(float(w.bounding_rect.x + w.bounding_rect.width) for w in line.words)
        y2 = max(float(w.bounding_rect.y + w.bounding_rect.height) for w in line.words)
        lines.append((text, 1.0, (x1, y1, x2, y2)))
    return lines


def ocr_crop(image: Image.Image, rect: tuple[float, float, float, float]) -> list[Line]:
    """OCR one rectangle of the capture. Boxes come back in full-capture pixels,
    so nothing downstream knows a crop happened.
    """
    x1, y1, x2, y2 = (round(v) for v in rect)
    crop = image if (x1, y1, x2, y2) == (0, 0, image.width, image.height) else image.crop((x1, y1, x2, y2))

    if sys.platform == "darwin":
        from ocrmac import ocrmac

        raw = ocrmac.OCR(crop, recognition_level="accurate").recognize(px=True)
        return [(text, conf, (b[0] + x1, b[1] + y1, b[2] + x1, b[3] + y1)) for text, conf, b in raw]

    if _WINRT_OCR_AVAILABLE and _async_worker is not None:
        with _ocr_lock:
            raw_lines = _async_worker.run(_winrt_recognize_async(crop))
        return [(text, conf, (b[0] + x1, b[1] + y1, b[2] + x1, b[3] + y1)) for text, conf, b in raw_lines]

    # Optional fallback for other environments
    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        import numpy as np

        result, _ = engine(np.array(crop))
        if not result:
            return []
        out: list[Line] = []
        for dt_box, text, score in result:
            bx1 = min(pt[0] for pt in dt_box) + x1
            by1 = min(pt[1] for pt in dt_box) + y1
            bx2 = max(pt[0] for pt in dt_box) + x1
            by2 = max(pt[1] for pt in dt_box) + y1
            out.append((text, float(score), (bx1, by1, bx2, by2)))
        return out
    except ImportError as err:
        raise RuntimeError(
            "No supported OCR engine available. On Windows, install 'winsdk' for native NPU OCR. On macOS, install 'ocrmac'."
        ) from err
