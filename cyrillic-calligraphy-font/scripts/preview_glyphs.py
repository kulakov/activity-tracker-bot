#!/usr/bin/env python3
"""
Generate an HTML preview page showing all generated Cyrillic glyphs.

Creates a visual grid of all SVG glyphs for quick quality inspection
before font assembly.
"""

import argparse
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>KiriCallig - Предпросмотр глифов</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Sans', sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            padding: 2rem;
        }}
        h1 {{
            text-align: center;
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #ff6b6b;
        }}
        .subtitle {{
            text-align: center;
            color: #888;
            margin-bottom: 2rem;
            font-size: 0.9rem;
        }}
        .style-selector {{
            text-align: center;
            margin-bottom: 2rem;
        }}
        .style-selector button {{
            background: #16213e;
            color: #e0e0e0;
            border: 1px solid #333;
            padding: 0.5rem 1rem;
            margin: 0 0.25rem;
            border-radius: 4px;
            cursor: pointer;
        }}
        .style-selector button.active {{
            background: #ff6b6b;
            color: #1a1a2e;
            border-color: #ff6b6b;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 1rem;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .glyph-card {{
            background: #16213e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .glyph-card:hover {{
            transform: scale(1.05);
            border-color: #ff6b6b;
        }}
        .glyph-card .char {{
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
            color: #888;
        }}
        .glyph-card .svg-container {{
            width: 80px;
            height: 80px;
            margin: 0 auto;
            background: #fff;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .glyph-card .svg-container img {{
            max-width: 72px;
            max-height: 72px;
        }}
        .glyph-card .code {{
            font-size: 0.7rem;
            color: #666;
            margin-top: 0.5rem;
            font-family: monospace;
        }}
        .section {{
            margin-bottom: 2rem;
        }}
        .section h2 {{
            color: #ff6b6b;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #333;
        }}
        .stats {{
            text-align: center;
            margin-bottom: 2rem;
            color: #888;
        }}
        .sample-text {{
            max-width: 800px;
            margin: 2rem auto;
            padding: 2rem;
            background: #fff;
            border-radius: 8px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>書 KiriCallig</h1>
    <p class="subtitle">Кириллический шрифт в стиле японской каллиграфии</p>
    <p class="stats">Сгенерировано глифов: {glyph_count}</p>

    {sections}

</body>
</html>"""

SECTION_TEMPLATE = """
    <div class="section">
        <h2>{title}</h2>
        <div class="grid">
            {cards}
        </div>
    </div>
"""

CARD_TEMPLATE = """
            <div class="glyph-card">
                <div class="char">{char}</div>
                <div class="svg-container">
                    <img src="{svg_path}" alt="{char}"/>
                </div>
                <div class="code">U+{codepoint:04X}</div>
            </div>"""


def generate_preview(svg_dir: Path, output_path: Path):
    """Generate HTML preview of all SVG glyphs."""
    import re

    # Collect glyphs
    glyphs: list[tuple[str, Path]] = []
    for svg_file in sorted(svg_dir.glob("*.svg")):
        match = re.match(r"u([0-9a-f]+)_(.+)\.svg", svg_file.name, re.IGNORECASE)
        if match:
            char = match.group(2)
            glyphs.append((char, svg_file))

    if not glyphs:
        print("No SVG files found!")
        return

    # Group by type
    groups = {
        "Прописные / Uppercase": [],
        "Строчные / Lowercase": [],
        "Цифры / Digits": [],
        "Знаки препинания / Punctuation": [],
    }

    for char, svg_path in glyphs:
        if len(char) == 1:
            cp = ord(char)
            if char.isupper() and 0x0400 <= cp <= 0x04FF:
                groups["Прописные / Uppercase"].append((char, svg_path))
            elif char.islower() and 0x0400 <= cp <= 0x04FF:
                groups["Строчные / Lowercase"].append((char, svg_path))
            elif char.isdigit():
                groups["Цифры / Digits"].append((char, svg_path))
            else:
                groups["Знаки препинания / Punctuation"].append((char, svg_path))
        else:
            groups["Знаки препинания / Punctuation"].append((char, svg_path))

    # Build HTML
    sections_html = ""
    for title, group_glyphs in groups.items():
        if not group_glyphs:
            continue
        cards_html = ""
        for char, svg_path in group_glyphs:
            rel_path = svg_path.relative_to(output_path.parent)
            cards_html += CARD_TEMPLATE.format(
                char=char,
                svg_path=str(rel_path),
                codepoint=ord(char) if len(char) == 1 else 0,
            )
        sections_html += SECTION_TEMPLATE.format(title=title, cards=cards_html)

    html = HTML_TEMPLATE.format(
        glyph_count=len(glyphs),
        sections=sections_html,
    )

    output_path.write_text(html, encoding="utf-8")
    print(f"Preview generated: {output_path}")
    print(f"Open in browser: file://{output_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate HTML preview of Cyrillic calligraphy glyphs"
    )
    parser.add_argument(
        "--style",
        default="default",
        help="Style variant name",
    )
    parser.add_argument(
        "--svg-dir",
        type=Path,
        default=None,
        help="Override SVG directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output HTML path",
    )

    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent.parent

    svg_dir = args.svg_dir or project_root / "output" / "svgs" / args.style
    output = args.output or project_root / "output" / "preview.html"

    if not svg_dir.exists():
        print(f"Error: SVG directory not found: {svg_dir}")
        return

    generate_preview(svg_dir, output)


if __name__ == "__main__":
    main()
