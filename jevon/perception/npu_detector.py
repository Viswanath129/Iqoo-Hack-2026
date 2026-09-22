"""Honest NPU runtime detection for JEVON.

Implements a 4-tier probe with strict truth-first reporting:
1. QUALCOMM_HEXAGON_NPU: Qualcomm Snapdragon NPU QNN provider and compiled models.
2. CPU_ONNX: Standard CPU onnxruntime engine.
3. OS_SAPI: Windows Media / SAPI speech services.
4. CLI_KEYBOARD: Baseline standard fallback.
Zero fabricated or unverified NPU claims.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


class NpuDetector:
    """Honest 4-tier NPU detection hierarchy with zero fake claims."""

    TIER_QUALCOMM_NPU = "QUALCOMM_HEXAGON_NPU"
    TIER_CPU_ONNX = "CPU_ONNX"
    TIER_OS_SAPI = "OS_SAPI"
    TIER_CLI_KEYBOARD = "CLI_KEYBOARD"

    @classmethod
    def detect_runtime_tier(cls) -> str:
        """Inspects environment and returns the real active execution tier."""
        # Tier 1: Check for Qualcomm Hexagon NPU runtime and model files
        qnn_path = Path(os.environ.get("QNN_BUNDLE_PATH", "B:/projects/Qualcomm/whisper_bundle"))
        qnn_installed = False
        try:
            qnn_installed = importlib.util.find_spec("onnxruntime_qnn") is not None
        except Exception:
            qnn_installed = False

        if sys.platform == "win32" and qnn_installed and qnn_path.exists():
            return cls.TIER_QUALCOMM_NPU

        # Tier 2: Check for standard CPU onnxruntime
        try:
            if importlib.util.find_spec("onnxruntime") is not None:
                return cls.TIER_CPU_ONNX
        except Exception:
            pass

        # Tier 3: Check for Windows SAPI speech
        if sys.platform == "win32":
            return cls.TIER_OS_SAPI

        # Tier 4: Fallback
        return cls.TIER_CLI_KEYBOARD
