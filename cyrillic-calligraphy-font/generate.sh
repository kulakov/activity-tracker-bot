#!/usr/bin/env bash
# Main orchestration script for Cyrillic Calligraphy Font generation.
#
# Usage:
#   bash generate.sh [--style default|kaisho|gyosho|sosho|modern] [--skip-setup]
#
# Full pipeline:
#   1. Setup environment & download model
#   2. Prepare inference data
#   3. Run VecGlypher inference
#   4. Extract SVG glyphs
#   5. Generate preview
#   6. Assemble font

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Defaults
STYLE="default"
SKIP_SETUP=false
GPU_COUNT=1

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --style) STYLE="$2"; shift 2 ;;
        --skip-setup) SKIP_SETUP=true; shift ;;
        --gpu-count) GPU_COUNT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: bash generate.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --style STYLE    Calligraphy style: default, kaisho, gyosho, sosho, modern"
            echo "  --skip-setup     Skip environment setup (if already done)"
            echo "  --gpu-count N    Number of GPUs for inference (default: 1)"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║  書 KiriCallig — Кириллическая каллиграфия      ║"
echo "║  Japanese Calligraphy Inspired Cyrillic Font     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Style: $STYLE"
echo ""

# Step 1: Environment setup
if [ "$SKIP_SETUP" = false ]; then
    echo "━━━ Step 1/5: Environment Setup ━━━"
    bash scripts/setup_env.sh
    echo ""
else
    echo "━━━ Step 1/5: Environment Setup (skipped) ━━━"
    echo ""
fi

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate cyrillic_calligraphy

# Step 2: Prepare inference data
echo "━━━ Step 2/5: Preparing Inference Data ━━━"
python scripts/prepare_inference_data.py \
    --style "$STYLE" \
    --chars all \
    --mode single
echo ""

# Step 3: Run inference
echo "━━━ Step 3/5: Running VecGlypher Inference ━━━"
bash scripts/run_inference.sh \
    --style "$STYLE" \
    --gpu-count "$GPU_COUNT"
echo ""

# Step 4: Preview
echo "━━━ Step 4/5: Generating Preview ━━━"
python scripts/preview_glyphs.py --style "$STYLE"
echo ""

# Step 5: Assemble font
echo "━━━ Step 5/5: Assembling Font ━━━"
python scripts/assemble_font.py --style "$STYLE"
echo ""

echo "╔══════════════════════════════════════════════════╗"
echo "║  ✓ Generation Complete!                          ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Output files:"
echo "  Font:    output/font/KiriCallig-Regular.ttf"
echo "  SVGs:    output/svgs/$STYLE/"
echo "  Preview: output/preview.html"
echo ""
echo "Install the font on your system and enjoy! 書"
