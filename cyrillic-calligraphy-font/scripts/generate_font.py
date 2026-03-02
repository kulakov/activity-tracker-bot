#!/usr/bin/env python3
"""
Generate the KiriCallig font — full pipeline.

1. Generate SVG glyphs using brush engine + glyph definitions
2. Assemble into a TrueType font (.ttf) using fonttools
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from brush_engine import compose_glyph
from glyph_definitions import GLYPH_TABLE

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPointPen
from svgpathtools import parse_path

# Output paths
PROJECT_ROOT = SCRIPTS_DIR.parent
SVG_DIR = PROJECT_ROOT / "output" / "svgs" / "generated"
FONT_DIR = PROJECT_ROOT / "output" / "font"

# Font metrics
FONT_NAME = "KiriCallig"
UPM = 1000
ASCENDER = 800
DESCENDER = -200
DEFAULT_WIDTH = 650
SVG_SIZE = 1000


def step1_generate_svgs():
    """Generate SVG files for all defined glyphs."""
    SVG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating {len(GLYPH_TABLE)} SVG glyphs...")
    count = 0
    for char, glyph_fn in sorted(GLYPH_TABLE.items(), key=lambda x: ord(x[0])):
        strokes = glyph_fn()
        svg_content = compose_glyph(strokes)

        filename = f"u{ord(char):04x}_{char}.svg"
        (SVG_DIR / filename).write_text(svg_content, encoding="utf-8")
        count += 1

    print(f"  Done: {count} SVG files in {SVG_DIR}")
    return count


def parse_svg_paths(svg_file):
    """Extract 'd' attributes from all <path> elements in an SVG."""
    tree = ET.parse(svg_file)
    paths = []
    for elem in tree.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "path":
            d = elem.get("d", "").strip()
            if d:
                paths.append(d)
    return paths


def draw_glyph_to_pen(pen, svg_paths, scale=1.0):
    """Draw SVG paths onto a fonttools pen, flipping Y axis."""
    for d_string in svg_paths:
        try:
            path = parse_path(d_string)
        except Exception:
            continue
        if not path:
            continue

        start = path[0].start
        pen.moveTo((
            round(start.real * scale),
            round((SVG_SIZE - start.imag) * scale),
        ))

        for seg in path:
            stype = type(seg).__name__
            if stype == "Line":
                pen.lineTo((
                    round(seg.end.real * scale),
                    round((SVG_SIZE - seg.end.imag) * scale),
                ))
            elif stype == "CubicBezier":
                pen.curveTo(
                    (round(seg.control1.real * scale), round((SVG_SIZE - seg.control1.imag) * scale)),
                    (round(seg.control2.real * scale), round((SVG_SIZE - seg.control2.imag) * scale)),
                    (round(seg.end.real * scale), round((SVG_SIZE - seg.end.imag) * scale)),
                )
            elif stype == "QuadraticBezier":
                pen.qCurveTo(
                    (round(seg.control.real * scale), round((SVG_SIZE - seg.control.imag) * scale)),
                    (round(seg.end.real * scale), round((SVG_SIZE - seg.end.imag) * scale)),
                )
            else:
                pen.lineTo((
                    round(seg.end.real * scale),
                    round((SVG_SIZE - seg.end.imag) * scale),
                ))

        if path.isclosed():
            pen.closePath()
        else:
            pen.endPath()


def step2_assemble_font():
    """Assemble SVG glyphs into a TrueType font."""
    FONT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect SVG -> char mapping
    glyph_map = {}
    for svg_file in sorted(SVG_DIR.glob("*.svg")):
        match = re.match(r"u([0-9a-f]+)_(.+)\.svg", svg_file.name, re.IGNORECASE)
        if match and len(match.group(2)) == 1:
            glyph_map[match.group(2)] = svg_file

    if not glyph_map:
        print("Error: no SVG files found!")
        return None

    print(f"\nAssembling font from {len(glyph_map)} glyphs...")

    scale = UPM / SVG_SIZE

    # Build glyph order and cmap
    glyph_names = [".notdef", "space"]
    char_map = {32: "space"}
    for char in sorted(glyph_map.keys(), key=ord):
        gname = f"uni{ord(char):04X}"
        glyph_names.append(gname)
        char_map[ord(char)] = gname

    # Create font — draw glyphs using TTGlyphPointPen
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_names)
    fb.setupCharacterMap(char_map)

    # Build all glyphs via pen drawing
    # Create empty .notdef and space glyphs
    from fontTools.ttLib.tables._g_l_y_f import Glyph as TTGlyph
    empty_glyph = TTGlyph()
    empty_glyph.numberOfContours = 0
    glyph_dict = {".notdef": empty_glyph, "space": empty_glyph}
    metrics = {".notdef": (UPM, 0), "space": (DEFAULT_WIDTH // 2, 0)}

    for char, svg_file in sorted(glyph_map.items(), key=lambda x: ord(x[0])):
        gname = f"uni{ord(char):04X}"
        svg_paths = parse_svg_paths(svg_file)

        if not svg_paths:
            metrics[gname] = (DEFAULT_WIDTH, 0)
            continue

        # Record the drawing commands
        rec = RecordingPen()
        draw_glyph_to_pen(rec, svg_paths, scale)

        # Replay into a TTGlyphPointPen to get a proper TrueType glyph
        from fontTools.pens.pointPen import SegmentToPointPen
        tt_pen = TTGlyphPointPen(None)
        seg2pt = SegmentToPointPen(tt_pen)
        rec.replay(seg2pt)

        glyph_dict[gname] = tt_pen.glyph()
        metrics[gname] = (DEFAULT_WIDTH, 0)
        print(f"  {char} (U+{ord(char):04X}) — {len(svg_paths)} strokes")

    # Allow cubic bezier in TrueType (glyphDataFormat=1, supported by modern renderers)
    fb.font["head"].glyphDataFormat = 1
    fb.setupGlyf(glyph_dict)

    # Setup tables
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ASCENDER, descent=DESCENDER)
    fb.setupNameTable({
        "familyName": FONT_NAME,
        "styleName": "Regular",
        "psName": f"{FONT_NAME}-Regular",
        "uniqueFontIdentifier": f"{FONT_NAME};1.0",
        "version": "Version 1.0",
        "description": "Cyrillic font inspired by Japanese calligraphy (Shodo). "
                       "Generated with procedural brush stroke engine.",
    })
    fb.setupOS2(
        sTypoAscender=ASCENDER,
        sTypoDescender=DESCENDER,
        sTypoLineGap=0,
        usWinAscent=ASCENDER,
        usWinDescent=abs(DESCENDER),
        sxHeight=500,
        sCapHeight=700,
        ulCodePageRange1=(1 << 2),  # Cyrillic
    )
    fb.setupPost()

    font_path = FONT_DIR / f"{FONT_NAME}-Regular.ttf"
    fb.font.save(str(font_path))
    print(f"\nFont saved: {font_path}")
    print(f"Size: {font_path.stat().st_size / 1024:.1f} KB")
    return font_path


def main():
    print("=" * 55)
    print("  書 KiriCallig — Procedural Calligraphy Font Generator")
    print("=" * 55)
    print()

    step1_generate_svgs()
    font_path = step2_assemble_font()

    if font_path:
        print()
        print("=" * 55)
        print(f"  Done! Font: {font_path}")
        print("=" * 55)


if __name__ == "__main__":
    main()
