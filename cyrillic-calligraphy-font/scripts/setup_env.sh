#!/usr/bin/env bash
# Setup environment for VecGlypher-based Cyrillic calligraphy font generation.
#
# This script:
# 1. Clones VecGlypher repository
# 2. Creates a conda environment
# 3. Installs all dependencies
# 4. Downloads the pre-trained model from HuggingFace

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
THIRD_PARTY_DIR="$PROJECT_DIR/third_party"
ENV_NAME="cyrillic_calligraphy"
PYTHON_VERSION="3.11"

echo "=== Cyrillic Calligraphy Font - Environment Setup ==="
echo "Project directory: $PROJECT_DIR"
echo ""

# --- Step 1: Clone VecGlypher ---
echo "[1/4] Cloning VecGlypher..."
mkdir -p "$THIRD_PARTY_DIR"

if [ -d "$THIRD_PARTY_DIR/VecGlypher" ]; then
    echo "  VecGlypher already cloned, pulling latest..."
    cd "$THIRD_PARTY_DIR/VecGlypher"
    git pull
    cd "$PROJECT_DIR"
else
    git clone https://github.com/xk-huang/VecGlypher.git "$THIRD_PARTY_DIR/VecGlypher"
fi

echo "  Done."

# --- Step 2: Create conda environment ---
echo "[2/4] Setting up conda environment '$ENV_NAME'..."

if conda env list | grep -q "^${ENV_NAME} "; then
    echo "  Environment '$ENV_NAME' already exists, activating..."
else
    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y
fi

# Activate environment
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

echo "  Python: $(python --version)"
echo "  Done."

# --- Step 3: Install dependencies ---
echo "[3/4] Installing dependencies..."

# Install uv for faster package management
pip install uv

# Core VecGlypher dependencies
cd "$THIRD_PARTY_DIR/VecGlypher"
if [ -f requirements.txt ]; then
    uv pip install -r requirements.txt
fi

# Install LLaMA Factory for inference
uv pip install "llamafactory[torch,metrics,vllm]==0.9.3"

# Install flash-attention (if CUDA available)
if python -c "import torch; print(torch.cuda.is_available())" 2>/dev/null | grep -q True; then
    echo "  CUDA detected, installing flash-attn..."
    uv pip install flash-attn==2.7.2.post1 --no-build-isolation
else
    echo "  No CUDA detected, skipping flash-attn (CPU-only mode)."
fi

# Font assembly dependencies
uv pip install fonttools svgpathtools cairosvg pillow

# Install VecGlypher as editable package if setup.py/pyproject.toml exists
if [ -f setup.py ] || [ -f pyproject.toml ]; then
    uv pip install -e .
fi

cd "$PROJECT_DIR"
echo "  Done."

# --- Step 4: Download model ---
echo "[4/4] Downloading VecGlypher model from HuggingFace..."

MODEL_DIR="$PROJECT_DIR/models"
mkdir -p "$MODEL_DIR"

# Try downloading the model via huggingface-cli
if command -v huggingface-cli &>/dev/null; then
    echo "  Downloading VecGlypher model..."
    echo "  Note: If this fails, you may need to run 'huggingface-cli login' first."
    huggingface-cli download VecGlypher/qwen3-4b-full-sft \
        --local-dir "$MODEL_DIR/qwen3-4b-full-sft" \
        --local-dir-use-symlinks False \
        2>/dev/null || {
        echo "  Warning: Could not download model automatically."
        echo "  Please download manually from: https://huggingface.co/VecGlypher"
        echo "  Place model files in: $MODEL_DIR/qwen3-4b-full-sft/"
    }
else
    pip install huggingface_hub[cli]
    huggingface-cli download VecGlypher/qwen3-4b-full-sft \
        --local-dir "$MODEL_DIR/qwen3-4b-full-sft" \
        --local-dir-use-symlinks False \
        2>/dev/null || {
        echo "  Warning: Could not download model automatically."
        echo "  Please download manually from: https://huggingface.co/VecGlypher"
        echo "  Place model files in: $MODEL_DIR/qwen3-4b-full-sft/"
    }
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Activate the environment:  conda activate $ENV_NAME"
echo "  2. Prepare inference data:    python scripts/prepare_inference_data.py"
echo "  3. Run inference:             bash scripts/run_inference.sh"
echo "  4. Assemble font:             python scripts/assemble_font.py"
