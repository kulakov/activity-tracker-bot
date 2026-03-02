#!/usr/bin/env python3
"""
Extract individual SVG files from VecGlypher inference results.

Reads JSONL output from api_infer.py and creates standalone SVG files
for each generated Cyrillic glyph.
"""

import argparse
import json
import re
from pathlib import Path


SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 1000 1000"
     width="1000" height="1000">
{paths}
</svg>"""


def extract_paths_from_prediction(predict_text: str) -> list[str]:
    """Extract SVG <path> elements from model prediction text.

    VecGlypher outputs raw SVG path data like:
        M10,20 L30,40 Z
        M50,20 L70,40 Z

    Or full <path> elements:
        <path d="M10,20 L30,40 Z"/>
    """
    paths = []

    # Try extracting full <path> elements first
    path_elements = re.findall(r"<path\s[^>]*/>", predict_text, re.DOTALL)
    if path_elements:
        return path_elements

    # Try extracting path data (lines starting with M)
    for line in predict_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Check if it looks like SVG path data
        if re.match(r"^[MmLlHhVvCcSsQqTtAaZz]", line):
            paths.append(f'  <path d="{line}" fill="black"/>')

    return paths


def load_inference_results(result_dir: Path) -> list[dict]:
    """Load all JSONL result files from inference output directory."""
    results = []
    for jsonl_file in sorted(result_dir.glob("*.jsonl")):
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
    return results


def load_input_data(input_file: Path) -> list[dict]:
    """Load original input data to get char metadata."""
    entries = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Extract SVG files from VecGlypher inference results"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing inference result JSONL files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write individual SVG files",
    )
    parser.add_argument(
        "--input-data",
        type=Path,
        required=True,
        help="Original input JSONL file (for char metadata)",
    )

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading inference results from {args.input_dir}...")
    results = load_inference_results(args.input_dir)
    print(f"  Found {len(results)} results")

    print(f"Loading input data from {args.input_data}...")
    input_data = load_input_data(args.input_data)
    print(f"  Found {len(input_data)} input entries")

    success_count = 0
    fail_count = 0

    for i, result in enumerate(results):
        predict = result.get("predict", "")
        if not predict:
            fail_count += 1
            continue

        # Match result to input entry
        if i < len(input_data):
            entry = input_data[i]
            char = entry.get("char", f"unknown_{i}")
            char_hex = entry.get("char_hex", f"U+{ord(char):04X}" if len(char) == 1 else "batch")
        else:
            char = f"unknown_{i}"
            char_hex = "unknown"

        # Extract SVG paths
        paths = extract_paths_from_prediction(predict)
        if not paths:
            print(f"  Warning: No paths extracted for '{char}' ({char_hex})")
            fail_count += 1
            continue

        # Create SVG file
        svg_content = SVG_TEMPLATE.format(paths="\n".join(paths))
        # Use hex code for filename to avoid filesystem issues
        safe_name = char_hex.replace("+", "").lower()
        svg_path = args.output_dir / f"{safe_name}_{char}.svg"
        svg_path.write_text(svg_content, encoding="utf-8")
        success_count += 1

    print(f"\n=== Extraction Complete ===")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")
    print(f"  Output:  {args.output_dir}")


if __name__ == "__main__":
    main()
