"""
Style configuration for Japanese calligraphy-inspired Cyrillic font.

Defines style descriptors used in VecGlypher inference prompts to guide
the model toward generating glyphs that blend Japanese calligraphy aesthetics
with Cyrillic letterforms.
"""

# Font metadata
FONT_NAME = "KiriCallig"
FONT_FAMILY = "KiriCallig"
FONT_VERSION = "1.0"
FONT_DESCRIPTION = "Cyrillic font inspired by Japanese calligraphy (Shodo)"

# Primary style prompt — describes the desired aesthetic for VecGlypher.
# VecGlypher expects style descriptors similar to Google Fonts metadata tags:
# category, classification, stroke type, weight, style, plus expressive tags.
STYLE_PROMPT = (
    "display, handwritten, calligraphic, brush-stroke, medium-weight, "
    "expressive, organic, fluid strokes with varied thickness, "
    "inspired by Japanese shodo calligraphy, bold brush dynamics, "
    "elegant flowing curves, ink-brush texture feel, "
    "thick-to-thin stroke transitions, dramatic contrast"
)

# Alternative style variants for experimentation
STYLE_VARIANTS = {
    # Formal/kaisho (楷書) style — more structured, block-like
    "kaisho": (
        "display, handwritten, calligraphic, brush-stroke, bold-weight, "
        "structured, angular, strong vertical strokes, "
        "inspired by Japanese kaisho formal calligraphy, "
        "deliberate brush placement, clear stroke endings, "
        "balanced proportions, strong ink presence"
    ),
    # Semi-cursive/gyosho (行書) style — flowing but readable
    "gyosho": (
        "display, handwritten, calligraphic, brush-stroke, medium-weight, "
        "semi-cursive, flowing, connected strokes, "
        "inspired by Japanese gyosho semi-cursive calligraphy, "
        "fluid transitions between strokes, moderate speed impression, "
        "graceful curves, natural ink flow"
    ),
    # Cursive/sosho (草書) style — very fluid and abstract
    "sosho": (
        "display, handwritten, calligraphic, brush-stroke, light-weight, "
        "cursive, highly expressive, abstract, fluid continuous strokes, "
        "inspired by Japanese sosho grass script calligraphy, "
        "rapid brush movement, minimal lifting, "
        "wild energy, extreme thick-thin variation"
    ),
    # Modern minimal — clean brush aesthetic
    "modern": (
        "display, handwritten, calligraphic, brush-stroke, regular-weight, "
        "modern, minimal, clean brush strokes, "
        "japanese-inspired minimalist calligraphy, "
        "precise yet organic, restrained elegance, "
        "balanced white space, contemporary feel"
    ),
}

# VecGlypher inference parameters
INFERENCE_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "repetition_penalty": 1.05,
    "max_tokens": 1024,
}

# System prompt for VecGlypher (from their docs)
SYSTEM_PROMPT = (
    "You are a specialized vector glyph designer creating SVG path elements.\n\n"
    "CRITICAL REQUIREMENTS:\n"
    "- Each glyph must be a complete, self-contained <path> element\n"
    "- Terminate each <path> element with a newline character\n"
    "- Output ONLY valid SVG <path> elements"
)

# SVG canvas settings
SVG_CANVAS = {
    "width": 1000,
    "height": 1000,
    "viewbox": "0 0 1000 1000",
}
