"""Download pre-quantized models for on-device Argus inference.

Downloads from Hugging Face Hub:
  1. Qwen 2.5 0.5B-Instruct (INT4 ONNX or GGUF) — decision engine
  2. Whisper Small (INT4 ONNX) — speech-to-text (optional)

Usage:
  python -m hackathon.download_models              # download all
  python -m hackathon.download_models --qwen-only   # decision model only
  python -m hackathon.download_models --whisper-only # STT model only
  python -m hackathon.download_models --gguf         # GGUF format instead of ONNX
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Default model output directory
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"

# Hugging Face model IDs
QWEN_ONNX_REPO = "Qwen/Qwen2.5-0.5B-Instruct"
QWEN_GGUF_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
QWEN_GGUF_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
WHISPER_ONNX_REPO = "openai/whisper-small"

# Qualcomm AI Hub model IDs (pre-quantized for Snapdragon NPU)
QAIHUB_QWEN = "qualcomm/Qwen2.5-0.5B-Instruct"
QAIHUB_WHISPER = "qualcomm/whisper-small-en"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, printing it first."""
    print(f"  $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, **kwargs)


def _ensure_pip_package(package: str) -> None:
    """Install a pip package if not present."""
    try:
        __import__(package.split("[")[0].replace("-", "_"))
    except ImportError:
        print(f"  Installing {package}...", flush=True)
        _run([sys.executable, "-m", "pip", "install", "-q", package])


def download_qwen_gguf(output_dir: Path) -> Path:
    """Download Qwen 2.5 0.5B-Instruct GGUF (Q4_K_M quantized).

    This is the simplest format — one file, works with llama-cpp-python.
    """
    dest = output_dir / "qwen2.5-0.5b"
    dest.mkdir(parents=True, exist_ok=True)
    gguf_path = dest / QWEN_GGUF_FILE

    if gguf_path.is_file():
        print(f"  ✓ GGUF already downloaded: {gguf_path}", flush=True)
        return gguf_path

    print(f"\n[DOWNLOAD] Qwen 2.5 0.5B-Instruct GGUF → {dest}", flush=True)
    _ensure_pip_package("huggingface-hub")

    from huggingface_hub import hf_hub_download
    downloaded = hf_hub_download(
        repo_id=QWEN_GGUF_REPO,
        filename=QWEN_GGUF_FILE,
        local_dir=str(dest),
    )
    print(f"  ✓ Downloaded: {downloaded}", flush=True)
    return Path(downloaded)


def download_qwen_onnx(output_dir: Path) -> Path:
    """Download Qwen 2.5 0.5B-Instruct ONNX (for onnxruntime-genai + QNN EP).

    This requires the onnxruntime-genai model builder or a pre-exported model
    from Qualcomm AI Hub.
    """
    dest = output_dir / "qwen2.5-0.5b"
    dest.mkdir(parents=True, exist_ok=True)
    config_path = dest / "genai_config.json"

    if config_path.is_file():
        print(f"  ✓ ONNX model already present: {dest}", flush=True)
        return dest

    print(f"\n[DOWNLOAD] Qwen 2.5 0.5B-Instruct ONNX → {dest}", flush=True)

    # Try Qualcomm AI Hub first (pre-quantized for Snapdragon)
    try:
        _ensure_pip_package("qai-hub")
        print("  Trying Qualcomm AI Hub (pre-quantized for Hexagon NPU)...", flush=True)
        import qai_hub as hub
        model = hub.get_model(QAIHUB_QWEN)
        model.download(str(dest))
        print(f"  ✓ Downloaded from Qualcomm AI Hub: {dest}", flush=True)
        return dest
    except Exception as e:
        print(f"  Qualcomm AI Hub unavailable: {e}", flush=True)

    # Fall back to onnxruntime-genai model builder
    try:
        _ensure_pip_package("onnxruntime-genai")
        print("  Using onnxruntime-genai model builder...", flush=True)
        _run([
            sys.executable, "-m", "onnxruntime_genai.models.builder",
            "-m", QWEN_ONNX_REPO,
            "-o", str(dest),
            "-p", "int4",
            "-e", "cpu",  # Will be overridden at runtime with QNN EP
        ])
        if config_path.is_file():
            print(f"  ✓ Model built: {dest}", flush=True)
            return dest
    except Exception as e:
        print(f"  onnxruntime-genai builder failed: {e}", flush=True)

    # Last resort: download raw model and let user quantize
    print("  ⚠ Could not build ONNX model. Falling back to GGUF download.", flush=True)
    return download_qwen_gguf(output_dir)


def download_whisper(output_dir: Path) -> Path:
    """Download Whisper Small ONNX for on-device speech-to-text."""
    dest = output_dir / "whisper-small"
    dest.mkdir(parents=True, exist_ok=True)

    encoder = dest / "encoder.onnx"
    decoder = dest / "decoder.onnx"

    if encoder.is_file() and decoder.is_file():
        print(f"  ✓ Whisper already downloaded: {dest}", flush=True)
        return dest

    print(f"\n[DOWNLOAD] Whisper Small ONNX → {dest}", flush=True)

    # Try Qualcomm AI Hub first
    try:
        _ensure_pip_package("qai-hub")
        import qai_hub as hub
        model = hub.get_model(QAIHUB_WHISPER)
        model.download(str(dest))
        print(f"  ✓ Downloaded from Qualcomm AI Hub: {dest}", flush=True)
        return dest
    except Exception as e:
        print(f"  Qualcomm AI Hub unavailable: {e}", flush=True)

    # Fall back to HuggingFace optimum export
    try:
        _ensure_pip_package("optimum[onnxruntime]")
        print("  Using optimum ONNX export...", flush=True)
        _run([
            sys.executable, "-m", "optimum.exporters.onnx",
            "--model", WHISPER_ONNX_REPO,
            str(dest),
        ])
        if encoder.is_file():
            print(f"  ✓ Model exported: {dest}", flush=True)
            return dest
    except Exception as e:
        print(f"  optimum export failed: {e}", flush=True)

    print("  ⚠ Could not download Whisper model. STT will use cloud fallback.", flush=True)
    return dest


def main():
    parser = argparse.ArgumentParser(description="Download models for Argus on-device AI inference.")
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_DIR, help="Output directory for models")
    parser.add_argument("--qwen-only", action="store_true", help="Download only the Qwen decision model")
    parser.add_argument("--whisper-only", action="store_true", help="Download only the Whisper STT model")
    parser.add_argument("--gguf", action="store_true", help="Download GGUF format instead of ONNX (for llama.cpp)")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Model output directory: {args.output}\n", flush=True)

    if not args.whisper_only:
        qwen_path = download_qwen_gguf(args.output) if args.gguf else download_qwen_onnx(args.output)
        print(f"\n✓ Qwen model ready at: {qwen_path}", flush=True)
        print(f"  Set JEVON_SLM_MODEL_DIR={qwen_path} or JEVON_SLM_GGUF={qwen_path}", flush=True)

    if not args.qwen_only:
        whisper_path = download_whisper(args.output)
        print(f"\n✓ Whisper model ready at: {whisper_path}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("All models downloaded. Ready for hackathon!", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
