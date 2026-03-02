#!/usr/bin/env bash
# Run VecGlypher inference to generate Cyrillic calligraphy glyphs.
#
# Usage:
#   bash scripts/run_inference.sh [--style default|kaisho|gyosho|sosho|modern]
#                                 [--gpu-count 1]
#                                 [--port 30000]
#
# Prerequisites:
#   1. Run setup_env.sh first
#   2. Run prepare_inference_data.py first
#   3. conda activate cyrillic_calligraphy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VECGLYPHER_DIR="$PROJECT_DIR/third_party/VecGlypher"

# Defaults
STYLE="default"
GPU_COUNT=1
PORT=30000
MODE="single"
CHARS="all"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --style) STYLE="$2"; shift 2 ;;
        --gpu-count) GPU_COUNT="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        --mode) MODE="$2"; shift 2 ;;
        --chars) CHARS="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

INPUT_FILE="$PROJECT_DIR/data/inference_input/cyrillic_${STYLE}_${MODE}_${CHARS}.jsonl"
OUTPUT_DIR="$PROJECT_DIR/output/inference_raw/${STYLE}"
MODEL_DIR="$PROJECT_DIR/models/qwen3-4b-full-sft"

# Validate
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found: $INPUT_FILE"
    echo "Run prepare_inference_data.py first."
    exit 1
fi

if [ ! -d "$MODEL_DIR" ]; then
    echo "Error: Model not found at: $MODEL_DIR"
    echo "Run setup_env.sh first or download model manually."
    exit 1
fi

echo "=== VecGlypher Inference: Cyrillic Calligraphy ==="
echo "Style:      $STYLE"
echo "Input:      $INPUT_FILE"
echo "Output:     $OUTPUT_DIR"
echo "Model:      $MODEL_DIR"
echo "GPU count:  $GPU_COUNT"
echo "Port:       $PORT"
echo ""

mkdir -p "$OUTPUT_DIR"

# --- Step 1: Start vLLM server ---
echo "[1/3] Starting vLLM server..."

# Check if server is already running
if curl -s "http://localhost:${PORT}/v1/models" > /dev/null 2>&1; then
    echo "  vLLM server already running on port $PORT."
else
    echo "  Launching vLLM server in background..."

    python -m vllm.entrypoints.openai.api_server \
        --model "$MODEL_DIR" \
        --served-model-name "vecglypher" \
        --port "$PORT" \
        --tensor-parallel-size "$GPU_COUNT" \
        --trust-remote-code \
        --max-model-len 2048 \
        --gpu-memory-utilization 0.9 \
        > "$OUTPUT_DIR/vllm_server.log" 2>&1 &

    VLLM_PID=$!
    echo "  vLLM server PID: $VLLM_PID"
    echo "$VLLM_PID" > "$OUTPUT_DIR/vllm_server.pid"

    # Wait for server to be ready
    echo "  Waiting for server to be ready..."
    for i in $(seq 1 120); do
        if curl -s "http://localhost:${PORT}/v1/models" > /dev/null 2>&1; then
            echo "  Server ready after ${i}s."
            break
        fi
        if ! kill -0 "$VLLM_PID" 2>/dev/null; then
            echo "  Error: vLLM server died. Check $OUTPUT_DIR/vllm_server.log"
            exit 1
        fi
        sleep 1
    done

    if ! curl -s "http://localhost:${PORT}/v1/models" > /dev/null 2>&1; then
        echo "  Error: Server failed to start within 120s."
        echo "  Check logs: $OUTPUT_DIR/vllm_server.log"
        exit 1
    fi
fi

# --- Step 2: Run batch inference ---
echo "[2/3] Running batch inference..."

cd "$VECGLYPHER_DIR"

python src/serve/api_infer.py \
    --input_file "$INPUT_FILE" \
    --output_dir "$OUTPUT_DIR/results" \
    --api_base "http://localhost:${PORT}/v1" \
    --model "vecglypher" \
    --temperature 0.7 \
    --top_p 0.8 \
    --top_k 20 \
    --repetition_penalty 1.05 \
    --max_tokens 1024 \
    --num_workers 4

cd "$PROJECT_DIR"

echo "  Inference complete."

# --- Step 3: Extract SVGs ---
echo "[3/3] Extracting SVG files from results..."

python scripts/extract_svgs.py \
    --input-dir "$OUTPUT_DIR/results" \
    --output-dir "$PROJECT_DIR/output/svgs/$STYLE" \
    --input-data "$INPUT_FILE"

echo ""
echo "=== Inference Complete ==="
echo "Raw results:  $OUTPUT_DIR/results/"
echo "SVG files:    $PROJECT_DIR/output/svgs/$STYLE/"
echo ""
echo "Next step: python scripts/assemble_font.py --style $STYLE"

# Cleanup: stop vLLM server if we started it
if [ -f "$OUTPUT_DIR/vllm_server.pid" ]; then
    echo ""
    read -p "Stop vLLM server? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill "$(cat "$OUTPUT_DIR/vllm_server.pid")" 2>/dev/null || true
        rm "$OUTPUT_DIR/vllm_server.pid"
        echo "Server stopped."
    fi
fi
