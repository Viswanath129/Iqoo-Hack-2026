#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# ARGUS: iQOO 15 (Snapdragon 8 Elite Gen 5) On-Device Environment Setup
# Run inside Termux on the loaner phone
# ==============================================================================

set -e

echo "======================================================================"
echo "  ARGUS — On-Device AI Developer Testing Agent"
echo "  iQOO 15 / Snapdragon 8 Elite Gen 5 Hexagon NPU"
echo "======================================================================"

# 1. Update Termux base system
echo "[1/6] Updating Termux packages..."
pkg update -y
pkg install -y \
    python \
    python-pip \
    android-tools \
    termux-api \
    git \
    libjpeg-turbo \
    ffmpeg \
    ninja \
    build-essential \
    clang

# 2. Python dependencies
echo "[2/6] Installing Python dependencies..."
pip install --upgrade pip
pip install \
    pillow \
    numpy \
    requests \
    pytest

# Optional local SLM / ONNX packages
pip install huggingface-hub || true

# 3. Setup self-ADB wireless connection
echo "[3/6] Configuring Wireless ADB Loopback on iQOO 15..."
echo "NOTE: Make sure 'Wireless Debugging' is ENABLED in Developer Options!"
echo "If connected via USB during check-in, run 'adb tcpip 5555' once from PC."
adb connect localhost:5555 || true
adb devices

# 4. Prepare directories
echo "[4/6] Setting up project directories..."
mkdir -p ~/models/qwen2.5-0.5b
mkdir -p ~/models/whisper-small
mkdir -p ~/runs
mkdir -p /sdcard/argus/reports || true

# 5. Download On-Device Quantized SLM (Qwen 2.5 0.5B INT4)
echo "[5/6] Checking AI Models..."
if [ ! -f ~/models/qwen2.5-0.5b/qwen2.5-0.5b-instruct-q4_k_m.gguf ]; then
    echo "Downloading Qwen 2.5 0.5B GGUF for local NPU/CPU inference..."
    python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='Qwen/Qwen2.5-0.5B-Instruct-GGUF',
    filename='qwen2.5-0.5b-instruct-q4_k_m.gguf',
    local_dir='/data/data/com.termux/files/home/models/qwen2.5-0.5b'
)
print('✓ Model downloaded successfully')
" || echo "Model download can be resumed later or copied via Office Kit"
fi

# 6. Set Environment Variables
echo "[6/6] Writing environment variables to ~/.bashrc..."
cat << 'EOF' >> ~/.bashrc

# Argus Environment Settings
export ARGUS_TARGET=android
export ARGUS_SLM_GGUF=$HOME/models/qwen2.5-0.5b/qwen2.5-0.5b-instruct-q4_k_m.gguf
export ARGUS_SLM_MODEL_DIR=$HOME/models/qwen2.5-0.5b
export PYTHONPATH=$HOME/viswa_jav:$PYTHONPATH

alias argus="python -m typesafe_computer_use.cli --target android --act --speak"
alias argus-demo="python -m hackathon.demo"
EOF

echo "======================================================================"
echo "  ✓ Setup complete! Launch with: argus \"test the login flow\""
echo "======================================================================"
