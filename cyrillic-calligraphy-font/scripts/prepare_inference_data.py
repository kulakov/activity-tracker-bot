#!/usr/bin/env python3
"""
Prepare inference data for VecGlypher to generate Cyrillic calligraphy glyphs.

Creates JSONL files in the format expected by VecGlypher's api_infer.py:
  - Alpaca format: {"system": ..., "instruction": ..., "input": "", "output": ""}
  - Or messages format: {"messages": [{"role": ..., "content": ...}]}

Each entry requests generation of a single Cyrillic character
in the Japanese calligraphy style.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from configs.style_config import (
    INFERENCE_PARAMS,
    STYLE_PROMPT,
    STYLE_VARIANTS,
    SYSTEM_PROMPT,
)
from data.cyrillic_chars import ALL_CHARS, CHAR_GROUPS


def build_instruction(style: str, char: str) -> str:
    """Build VecGlypher instruction for a single character.

    Follows the format from VecGlypher's build_sft_data_v2.py:
        Font design requirements: {style_str}
        Text content: {content_str}
    """
    return f"Font design requirements: {style}\nText content: {char}"


def build_messages_format(style: str, char: str) -> list[dict]:
    """Build in messages (chat) format for vLLM inference."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_instruction(style, char)},
    ]


def build_alpaca_format(style: str, char: str) -> dict:
    """Build in Alpaca format for LLaMA Factory inference."""
    return {
        "system": SYSTEM_PROMPT,
        "instruction": build_instruction(style, char),
        "input": "",
        "output": "",
    }


def build_batch_instruction(style: str, chars: list[str]) -> str:
    """Build VecGlypher instruction for multiple characters in one request.

    Uses <|SEP|> separator as per VecGlypher's data format.
    """
    content = "<|SEP|>".join(chars)
    return f"Font design requirements: {style}\nText content: {content}"


def prepare_single_char_data(
    chars: list[str],
    style: str,
    output_format: str = "alpaca",
) -> list[dict]:
    """Prepare one-char-per-request inference data."""
    data = []
    for char in chars:
        entry = {
            "char": char,
            "char_hex": f"U+{ord(char):04X}",
        }
        if output_format == "messages":
            entry["messages"] = build_messages_format(style, char)
        else:
            entry.update(build_alpaca_format(style, char))
        data.append(entry)
    return data


def prepare_batch_char_data(
    chars: list[str],
    style: str,
    batch_size: int = 8,
    output_format: str = "alpaca",
) -> list[dict]:
    """Prepare batched inference data (multiple chars per request)."""
    data = []
    for i in range(0, len(chars), batch_size):
        batch = chars[i : i + batch_size]
        entry = {
            "chars": batch,
            "batch_index": i // batch_size,
        }
        instruction = build_batch_instruction(style, batch)
        if output_format == "messages":
            entry["messages"] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": instruction},
            ]
        else:
            entry.update(
                {
                    "system": SYSTEM_PROMPT,
                    "instruction": instruction,
                    "input": "",
                    "output": "",
                }
            )
        data.append(entry)
    return data


def write_jsonl(data: list[dict], output_path: Path) -> None:
    """Write data as JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in data:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  Written {len(data)} entries to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare VecGlypher inference data for Cyrillic calligraphy"
    )
    parser.add_argument(
        "--style",
        default="default",
        choices=["default"] + list(STYLE_VARIANTS.keys()),
        help="Calligraphy style variant (default: %(default)s)",
    )
    parser.add_argument(
        "--chars",
        default="all",
        choices=["all"] + list(CHAR_GROUPS.keys()),
        help="Character group to generate (default: %(default)s)",
    )
    parser.add_argument(
        "--format",
        default="alpaca",
        choices=["alpaca", "messages"],
        help="Output data format (default: %(default)s)",
    )
    parser.add_argument(
        "--mode",
        default="single",
        choices=["single", "batch"],
        help="single = one char per request, batch = multiple (default: %(default)s)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Characters per batch in batch mode (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "inference_input",
        help="Output directory for JSONL files",
    )
    parser.add_argument(
        "--all-styles",
        action="store_true",
        help="Generate data for all style variants",
    )

    args = parser.parse_args()

    # Select characters
    if args.chars == "all":
        chars = ALL_CHARS
    else:
        chars = CHAR_GROUPS[args.chars]

    # Select styles
    if args.all_styles:
        styles = {"default": STYLE_PROMPT, **STYLE_VARIANTS}
    elif args.style == "default":
        styles = {"default": STYLE_PROMPT}
    else:
        styles = {args.style: STYLE_VARIANTS[args.style]}

    print(f"=== Preparing VecGlypher Inference Data ===")
    print(f"Characters: {len(chars)} ({args.chars})")
    print(f"Styles: {list(styles.keys())}")
    print(f"Mode: {args.mode}")
    print(f"Format: {args.format}")
    print()

    for style_name, style_prompt in styles.items():
        print(f"Style: {style_name}")

        if args.mode == "single":
            data = prepare_single_char_data(chars, style_prompt, args.format)
        else:
            data = prepare_batch_char_data(
                chars, style_prompt, args.batch_size, args.format
            )

        filename = f"cyrillic_{style_name}_{args.mode}_{args.chars}.jsonl"
        output_path = args.output_dir / filename
        write_jsonl(data, output_path)

    # Also write inference params config
    params_path = args.output_dir / "inference_params.json"
    with open(params_path, "w") as f:
        json.dump(INFERENCE_PARAMS, f, indent=2)
    print(f"\n  Inference params saved to {params_path}")

    print("\n=== Done ===")
    print(f"Files ready in: {args.output_dir}")


if __name__ == "__main__":
    main()
