#!/usr/bin/env python3
"""
Cyrillic glyph definitions as brush stroke compositions.

Each glyph is defined as a list of "spine" paths — center lines of brush strokes.
The brush engine converts these into filled outlines with calligraphic dynamics.

Coordinate system: 0-1000 x 0-1000 (SVG viewBox).
Origin is top-left. Y increases downward.

Typical glyph metrics:
  - Cap height: y=150 to y=800
  - x-height:   y=350 to y=800
  - Baseline:   y=800
  - Descender:  y=950
"""

from brush_engine import make_stroke

# Convenience: standard glyph bounds
TOP = 150       # Cap height top
MID = 475       # Midline
BOT = 800       # Baseline
X_TOP = 350     # x-height top
LEFT = 150      # Left bearing
RIGHT = 850     # Right bearing
CENTER = 500    # Horizontal center
DESC = 950      # Descender

# Default brush settings for different stroke types
W_MAIN = 65     # Main strokes (verticals, heavy)
W_THIN = 40     # Thin strokes (horizontals, connectors)
W_MED = 52      # Medium strokes
W_ACCENT = 35   # Accents, dots


def _vstroke(x, y1, y2, w=W_MAIN, seed=1):
    """Vertical stroke — strong, main structural element."""
    return make_stroke([(x, y1), (x, y2)], width=w, pressure_end=0.25, entry_flare=1.4, seed=seed)


def _hstroke(y, x1, x2, w=W_THIN, seed=2):
    """Horizontal stroke — thinner, like Japanese horizontal strokes."""
    return make_stroke([(x1, y), (x2, y)], width=w, pressure_end=0.4, entry_flare=1.2, seed=seed)


def _diag(x1, y1, x2, y2, w=W_MED, seed=3):
    """Diagonal stroke."""
    return make_stroke([(x1, y1), (x2, y2)], width=w, pressure_end=0.3, entry_flare=1.3, seed=seed)


def _curve(pts, w=W_MED, seed=4, pressure_end=0.3):
    """Curved stroke (bezier)."""
    return make_stroke(pts, width=w, pressure_end=pressure_end, entry_flare=1.2, seed=seed, wobble=2.5)


# ============================================================
# UPPERCASE CYRILLIC (А-Я + Ё)
# ============================================================

def glyph_A():
    """А — two diagonals meeting at top + horizontal bar."""
    return [
        _diag(CENTER, TOP, LEFT + 30, BOT, W_MAIN, seed=10),
        _diag(CENTER, TOP, RIGHT - 30, BOT, W_MAIN, seed=11),
        _hstroke(MID + 50, LEFT + 120, RIGHT - 120, W_THIN, seed=12),
    ]


def glyph_Be():
    """Б — vertical + top horizontal extending right + bottom bowl."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=20),
        _hstroke(TOP, LEFT + 40, RIGHT - 80, W_THIN, seed=21),
        _hstroke(MID, LEFT + 40, RIGHT - 120, W_THIN, seed=22),
        _curve([(RIGHT - 120, MID), (RIGHT + 20, MID + 60), (RIGHT + 20, BOT - 60), (LEFT + 40, BOT)],
               W_MED, seed=23),
    ]


def glyph_Ve():
    """В — vertical + two bumps (top and bottom)."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=30),
        _curve([(LEFT + 40, TOP), (RIGHT - 60, TOP + 20), (RIGHT - 60, MID - 20), (LEFT + 40, MID)],
               W_MED, seed=31),
        _curve([(LEFT + 40, MID), (RIGHT, MID + 20), (RIGHT, BOT - 20), (LEFT + 40, BOT)],
               W_MED, seed=32),
    ]


def glyph_Ge():
    """Г — vertical + top horizontal (like an L rotated)."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=40),
        _hstroke(TOP, LEFT + 40, RIGHT - 50, W_MED, seed=41),
    ]


def glyph_De():
    """Д — wide triangular top + bottom platform with legs."""
    return [
        _diag(CENTER - 30, TOP, LEFT + 10, BOT, W_MED, seed=50),
        _diag(CENTER + 30, TOP, RIGHT - 10, BOT, W_MED, seed=51),
        _hstroke(BOT, LEFT - 30, RIGHT + 30, W_MED, seed=52),
        _vstroke(LEFT - 30, BOT, BOT + 100, W_THIN, seed=53),
        _vstroke(RIGHT + 30, BOT, BOT + 100, W_THIN, seed=54),
    ]


def glyph_Ye():
    """Е — vertical + three horizontals."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=60),
        _hstroke(TOP, LEFT + 40, RIGHT - 80, W_THIN, seed=61),
        _hstroke(MID, LEFT + 40, RIGHT - 140, W_THIN, seed=62),
        _hstroke(BOT, LEFT + 40, RIGHT - 80, W_THIN, seed=63),
    ]


def glyph_Zhe():
    """Ж — central vertical + four diagonals spreading out."""
    return [
        _vstroke(CENTER, TOP, BOT, W_MAIN, seed=70),
        _diag(CENTER, MID - 50, LEFT + 20, TOP, W_MED, seed=71),
        _diag(CENTER, MID - 50, RIGHT - 20, TOP, W_MED, seed=72),
        _diag(CENTER, MID + 50, LEFT + 20, BOT, W_MED, seed=73),
        _diag(CENTER, MID + 50, RIGHT - 20, BOT, W_MED, seed=74),
    ]


def glyph_Ze():
    """З — two curved bumps on the right, open left (like 3)."""
    return [
        _curve([(LEFT + 100, TOP + 30), (RIGHT - 50, TOP), (RIGHT - 50, MID - 20), (CENTER, MID)],
               W_MED, seed=80),
        _curve([(CENTER, MID), (RIGHT - 30, MID + 20), (RIGHT - 30, BOT - 20), (LEFT + 100, BOT - 30)],
               W_MED, seed=81),
    ]


def glyph_I():
    """И — two verticals + diagonal connector (bottom-left to top-right)."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=90),
        _vstroke(RIGHT - 40, TOP, BOT, W_MAIN, seed=91),
        _diag(LEFT + 40, BOT, RIGHT - 40, TOP, W_THIN, seed=92),
    ]


def glyph_I_kratkoye():
    """Й — И with a breve accent on top."""
    strokes = glyph_I()
    # Breve (short curved mark above)
    strokes.append(_curve(
        [(CENTER - 80, TOP - 60), (CENTER, TOP - 100), (CENTER + 80, TOP - 60)],
        W_ACCENT, seed=95, pressure_end=0.5
    ))
    return strokes


def glyph_Ka():
    """К — vertical + two diagonals from mid."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=100),
        _diag(RIGHT - 40, TOP, LEFT + 80, MID, W_MED, seed=101),
        _diag(LEFT + 80, MID, RIGHT - 40, BOT, W_MED, seed=102),
    ]


def glyph_El():
    """Л — two diagonals meeting at top, like an inverted V but asymmetric."""
    return [
        _diag(LEFT + 80, BOT, CENTER + 20, TOP, W_MAIN, seed=110),
        _vstroke(RIGHT - 40, TOP, BOT, W_MAIN, seed=111),
        _hstroke(TOP, CENTER + 20, RIGHT - 40, W_THIN, seed=112),
    ]


def glyph_Em():
    """М — two outer verticals + two inner diagonals meeting at bottom-center."""
    return [
        _vstroke(LEFT + 30, TOP, BOT, W_MAIN, seed=120),
        _vstroke(RIGHT - 30, TOP, BOT, W_MAIN, seed=121),
        _diag(LEFT + 30, TOP, CENTER, MID + 80, W_MED, seed=122),
        _diag(CENTER, MID + 80, RIGHT - 30, TOP, W_MED, seed=123),
    ]


def glyph_En():
    """Н — two verticals + horizontal bar at mid."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=130),
        _vstroke(RIGHT - 40, TOP, BOT, W_MAIN, seed=131),
        _hstroke(MID, LEFT + 40, RIGHT - 40, W_THIN, seed=132),
    ]


def glyph_O():
    """О — oval/circle."""
    return [
        _curve([(CENTER, TOP), (RIGHT + 40, TOP), (RIGHT + 40, BOT), (CENTER, BOT)],
               W_MAIN, seed=140, pressure_end=0.5),
        _curve([(CENTER, BOT), (LEFT - 40, BOT), (LEFT - 40, TOP), (CENTER, TOP)],
               W_MAIN, seed=141, pressure_end=0.5),
    ]


def glyph_Pe():
    """П — two verticals + top horizontal (gate shape)."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=150),
        _vstroke(RIGHT - 40, TOP, BOT, W_MAIN, seed=151),
        _hstroke(TOP, LEFT + 40, RIGHT - 40, W_MED, seed=152),
    ]


def glyph_Er():
    """Р — vertical + top bump (like P)."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=160),
        _curve([(LEFT + 40, TOP), (RIGHT, TOP + 20), (RIGHT, MID - 20), (LEFT + 40, MID)],
               W_MED, seed=161),
    ]


def glyph_Es():
    """С — open curve (like C)."""
    return [
        _curve([(RIGHT - 80, TOP + 30), (LEFT - 20, TOP - 20), (LEFT - 20, BOT + 20), (RIGHT - 80, BOT - 30)],
               W_MAIN, seed=170),
    ]


def glyph_Te():
    """Т — one vertical from center + top horizontal bar."""
    return [
        _vstroke(CENTER, TOP, BOT, W_MAIN, seed=180),
        _hstroke(TOP, LEFT + 20, RIGHT - 20, W_MED, seed=181),
    ]


def glyph_U():
    """У — two diagonals: one from top-left to center, one from top-right descending."""
    return [
        _diag(LEFT + 40, TOP, CENTER, MID + 60, W_MAIN, seed=190),
        _diag(RIGHT - 40, TOP, CENTER - 60, BOT + 40, W_MAIN, seed=191),
    ]


def glyph_Ef():
    """Ф — central vertical + large circle/oval through center."""
    return [
        _vstroke(CENTER, TOP, BOT, W_MAIN, seed=200),
        _curve([(CENTER, TOP + 80), (RIGHT + 30, TOP + 80), (RIGHT + 30, BOT - 80), (CENTER, BOT - 80)],
               W_MED, seed=201, pressure_end=0.5),
        _curve([(CENTER, BOT - 80), (LEFT - 30, BOT - 80), (LEFT - 30, TOP + 80), (CENTER, TOP + 80)],
               W_MED, seed=202, pressure_end=0.5),
    ]


def glyph_Kha():
    """Х — two crossing diagonals (like X)."""
    return [
        _diag(LEFT + 60, TOP, RIGHT - 60, BOT, W_MAIN, seed=210),
        _diag(RIGHT - 60, TOP, LEFT + 60, BOT, W_MAIN, seed=211),
    ]


def glyph_Tse():
    """Ц — like П but with a small descender leg on the right."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=220),
        _vstroke(RIGHT - 80, TOP, BOT, W_MAIN, seed=221),
        _hstroke(BOT, LEFT + 40, RIGHT - 20, W_THIN, seed=222),
        _vstroke(RIGHT - 20, BOT - 30, BOT + 120, W_THIN, seed=223),
    ]


def glyph_Che():
    """Ч — left vertical from top to mid + curve to right vertical."""
    return [
        _vstroke(LEFT + 60, TOP, MID + 40, W_MAIN, seed=230),
        _curve([(LEFT + 60, MID + 40), (LEFT + 60, MID + 120), (RIGHT - 60, MID + 60), (RIGHT - 60, MID)],
               W_THIN, seed=231),
        _vstroke(RIGHT - 60, TOP, BOT, W_MAIN, seed=232),
    ]


def glyph_Sha():
    """Ш — three verticals + bottom horizontal."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=240),
        _vstroke(CENTER, TOP, BOT, W_MAIN, seed=241),
        _vstroke(RIGHT - 40, TOP, BOT, W_MAIN, seed=242),
        _hstroke(BOT, LEFT + 40, RIGHT - 40, W_THIN, seed=243),
    ]


def glyph_Shcha():
    """Щ — like Ш but with descender leg on right."""
    return [
        _vstroke(LEFT + 30, TOP, BOT, W_MED, seed=250),
        _vstroke(CENTER - 20, TOP, BOT, W_MED, seed=251),
        _vstroke(RIGHT - 80, TOP, BOT, W_MED, seed=252),
        _hstroke(BOT, LEFT + 30, RIGHT - 20, W_THIN, seed=253),
        _vstroke(RIGHT - 20, BOT - 30, BOT + 120, W_THIN, seed=254),
    ]


def glyph_Hard():
    """Ъ — top-left horizontal stub + vertical + bottom-right bump."""
    return [
        _hstroke(TOP, LEFT + 40, CENTER - 40, W_THIN, seed=260),
        _vstroke(CENTER - 40, TOP, BOT, W_MAIN, seed=261),
        _curve([(CENTER - 40, MID), (RIGHT + 20, MID + 20), (RIGHT + 20, BOT - 20), (CENTER - 40, BOT)],
               W_MED, seed=262),
    ]


def glyph_Yeru():
    """Ы — left vertical with bump + right vertical."""
    return [
        _vstroke(LEFT + 60, TOP, BOT, W_MAIN, seed=270),
        _curve([(LEFT + 60, MID), (CENTER + 60, MID + 20), (CENTER + 60, BOT - 20), (LEFT + 60, BOT)],
               W_MED, seed=271),
        _vstroke(RIGHT - 60, TOP, BOT, W_MAIN, seed=272),
    ]


def glyph_Soft():
    """Ь — vertical + bottom-right bump."""
    return [
        _vstroke(LEFT + 80, TOP, BOT, W_MAIN, seed=280),
        _curve([(LEFT + 80, MID), (RIGHT + 10, MID + 20), (RIGHT + 10, BOT - 20), (LEFT + 80, BOT)],
               W_MED, seed=281),
    ]


def glyph_E_oborot():
    """Э — reversed С with horizontal bar."""
    return [
        _curve([(LEFT + 80, TOP + 30), (RIGHT + 20, TOP - 20), (RIGHT + 20, BOT + 20), (LEFT + 80, BOT - 30)],
               W_MAIN, seed=290),
        _hstroke(MID, LEFT + 120, RIGHT - 40, W_THIN, seed=291),
    ]


def glyph_Yu():
    """Ю — left vertical + horizontal bar + right O."""
    return [
        _vstroke(LEFT + 40, TOP, BOT, W_MAIN, seed=300),
        _hstroke(MID, LEFT + 40, CENTER - 60, W_THIN, seed=301),
        _curve([(CENTER + 80, TOP), (RIGHT + 40, TOP), (RIGHT + 40, BOT), (CENTER + 80, BOT)],
               W_MED, seed=302, pressure_end=0.5),
        _curve([(CENTER + 80, BOT), (CENTER - 80, BOT), (CENTER - 80, TOP), (CENTER + 80, TOP)],
               W_MED, seed=303, pressure_end=0.5),
    ]


def glyph_Ya():
    """Я — mirrored Р: right vertical + top-left bump + left diagonal leg."""
    return [
        _vstroke(RIGHT - 40, TOP, BOT, W_MAIN, seed=310),
        _curve([(RIGHT - 40, TOP), (LEFT, TOP + 20), (LEFT, MID - 20), (RIGHT - 40, MID)],
               W_MED, seed=311),
        _diag(RIGHT - 40, MID, LEFT + 40, BOT, W_MED, seed=312),
    ]


def glyph_Yo():
    """Ё — same as Е but with two dots above."""
    strokes = glyph_Ye()
    # Two dots
    strokes.append(_curve(
        [(CENTER - 80, TOP - 80), (CENTER - 70, TOP - 60), (CENTER - 80, TOP - 40)],
        W_ACCENT, seed=320, pressure_end=0.7
    ))
    strokes.append(_curve(
        [(CENTER + 60, TOP - 80), (CENTER + 70, TOP - 60), (CENTER + 60, TOP - 40)],
        W_ACCENT, seed=321, pressure_end=0.7
    ))
    return strokes


# ============================================================
# LOWERCASE CYRILLIC (а-я + ё)
# Lowercase uses x-height (X_TOP to BOT) and thinner strokes
# ============================================================

LW_MAIN = 55    # Lowercase main width
LW_THIN = 35
LW_MED = 45


def glyph_a_lower():
    """а — round bowl + right vertical."""
    return [
        _curve([(RIGHT - 60, X_TOP + 30), (LEFT - 10, X_TOP - 10), (LEFT - 10, BOT + 10), (RIGHT - 60, BOT - 10)],
               LW_MED, seed=400, pressure_end=0.5),
        _vstroke(RIGHT - 60, X_TOP, BOT, LW_MAIN, seed=401),
    ]


def glyph_be_lower():
    """б — like о but with ascending stroke curving up to the right."""
    return [
        _curve([(CENTER, X_TOP), (RIGHT + 20, X_TOP), (RIGHT + 20, BOT), (CENTER, BOT)],
               LW_MED, seed=410, pressure_end=0.5),
        _curve([(CENTER, BOT), (LEFT - 20, BOT), (LEFT - 20, X_TOP), (CENTER, X_TOP)],
               LW_MED, seed=411, pressure_end=0.5),
        _curve([(CENTER - 20, X_TOP), (CENTER + 40, TOP + 40), (RIGHT - 40, TOP)],
               LW_THIN, seed=412),
    ]


def glyph_ve_lower():
    """в — two small bumps (like uppercase В but at x-height)."""
    return [
        _vstroke(LEFT + 60, X_TOP, BOT, LW_MAIN, seed=420),
        _curve([(LEFT + 60, X_TOP), (RIGHT - 80, X_TOP + 10), (RIGHT - 80, MID - 10), (LEFT + 60, MID + 20)],
               LW_MED, seed=421),
        _curve([(LEFT + 60, MID + 20), (RIGHT - 60, MID + 30), (RIGHT - 60, BOT - 10), (LEFT + 60, BOT)],
               LW_MED, seed=422),
    ]


def glyph_ge_lower():
    """г — short: horizontal + vertical drop."""
    return [
        _hstroke(X_TOP, LEFT + 60, RIGHT - 100, LW_MED, seed=430),
        _vstroke(LEFT + 60, X_TOP, BOT, LW_MAIN, seed=431),
    ]


def glyph_de_lower():
    """д — like а but with bottom platform and descender legs."""
    return [
        _curve([(RIGHT - 80, X_TOP + 20), (LEFT, X_TOP - 10), (LEFT, BOT + 10), (RIGHT - 80, BOT)],
               LW_MED, seed=440, pressure_end=0.5),
        _vstroke(RIGHT - 80, X_TOP, BOT, LW_MAIN, seed=441),
        _hstroke(BOT, LEFT - 30, RIGHT - 20, LW_THIN, seed=442),
        _vstroke(LEFT - 30, BOT, BOT + 100, LW_THIN, seed=443),
        _vstroke(RIGHT - 20, BOT, BOT + 100, LW_THIN, seed=444),
    ]


def glyph_ye_lower():
    """е — like с but with horizontal bar inside."""
    return [
        _hstroke(MID + 20, LEFT + 40, RIGHT - 40, LW_THIN, seed=450),
        _curve([(RIGHT - 40, MID + 20), (RIGHT - 20, X_TOP - 10), (LEFT - 10, X_TOP - 10), (LEFT - 10, MID + 20)],
               LW_MED, seed=451),
        _curve([(LEFT - 10, MID + 20), (LEFT - 10, BOT + 10), (RIGHT - 40, BOT + 10), (RIGHT - 60, BOT - 30)],
               LW_MED, seed=452),
    ]


def glyph_zhe_lower():
    """ж — central vertical + four small diagonals."""
    return [
        _vstroke(CENTER, X_TOP, BOT, LW_MAIN, seed=460),
        _diag(CENTER, MID - 30, LEFT + 30, X_TOP, LW_MED, seed=461),
        _diag(CENTER, MID - 30, RIGHT - 30, X_TOP, LW_MED, seed=462),
        _diag(CENTER, MID + 30, LEFT + 30, BOT, LW_MED, seed=463),
        _diag(CENTER, MID + 30, RIGHT - 30, BOT, LW_MED, seed=464),
    ]


def glyph_ze_lower():
    """з — two bumps like uppercase З but shorter."""
    return [
        _curve([(LEFT + 120, X_TOP + 20), (RIGHT - 80, X_TOP), (RIGHT - 80, MID), (CENTER, MID + 20)],
               LW_MED, seed=470),
        _curve([(CENTER, MID + 20), (RIGHT - 60, MID + 30), (RIGHT - 60, BOT - 10), (LEFT + 120, BOT - 20)],
               LW_MED, seed=471),
    ]


def glyph_i_lower():
    """и — two verticals + diagonal bottom-left to top-right."""
    return [
        _vstroke(LEFT + 60, X_TOP, BOT, LW_MAIN, seed=480),
        _vstroke(RIGHT - 60, X_TOP, BOT, LW_MAIN, seed=481),
        _diag(LEFT + 60, BOT, RIGHT - 60, X_TOP, LW_THIN, seed=482),
    ]


def glyph_i_kratkoye_lower():
    """й — и + breve."""
    strokes = glyph_i_lower()
    strokes.append(_curve(
        [(CENTER - 70, X_TOP - 50), (CENTER, X_TOP - 85), (CENTER + 70, X_TOP - 50)],
        W_ACCENT, seed=485, pressure_end=0.5
    ))
    return strokes


def glyph_ka_lower():
    """к — vertical + two small diagonals."""
    return [
        _vstroke(LEFT + 60, X_TOP, BOT, LW_MAIN, seed=490),
        _diag(RIGHT - 60, X_TOP, LEFT + 100, MID + 20, LW_MED, seed=491),
        _diag(LEFT + 100, MID + 20, RIGHT - 60, BOT, LW_MED, seed=492),
    ]


def glyph_el_lower():
    """л — inverted V, left leg diagonal, right leg vertical."""
    return [
        _diag(LEFT + 80, BOT, CENTER + 20, X_TOP, LW_MAIN, seed=500),
        _vstroke(RIGHT - 60, X_TOP, BOT, LW_MAIN, seed=501),
        _hstroke(X_TOP, CENTER + 20, RIGHT - 60, LW_THIN, seed=502),
    ]


def glyph_em_lower():
    """м — like uppercase М but at x-height."""
    return [
        _vstroke(LEFT + 40, X_TOP, BOT, LW_MAIN, seed=510),
        _vstroke(RIGHT - 40, X_TOP, BOT, LW_MAIN, seed=511),
        _diag(LEFT + 40, X_TOP, CENTER, MID + 60, LW_MED, seed=512),
        _diag(CENTER, MID + 60, RIGHT - 40, X_TOP, LW_MED, seed=513),
    ]


def glyph_en_lower():
    """н — two verticals + horizontal bar."""
    return [
        _vstroke(LEFT + 60, X_TOP, BOT, LW_MAIN, seed=520),
        _vstroke(RIGHT - 60, X_TOP, BOT, LW_MAIN, seed=521),
        _hstroke(MID + 30, LEFT + 60, RIGHT - 60, LW_THIN, seed=522),
    ]


def glyph_o_lower():
    """о — small oval."""
    return [
        _curve([(CENTER, X_TOP), (RIGHT + 20, X_TOP), (RIGHT + 20, BOT), (CENTER, BOT)],
               LW_MED, seed=530, pressure_end=0.5),
        _curve([(CENTER, BOT), (LEFT - 20, BOT), (LEFT - 20, X_TOP), (CENTER, X_TOP)],
               LW_MED, seed=531, pressure_end=0.5),
    ]


def glyph_pe_lower():
    """п — gate shape at x-height."""
    return [
        _vstroke(LEFT + 60, X_TOP, BOT, LW_MAIN, seed=540),
        _vstroke(RIGHT - 60, X_TOP, BOT, LW_MAIN, seed=541),
        _hstroke(X_TOP, LEFT + 60, RIGHT - 60, LW_MED, seed=542),
    ]


def glyph_er_lower():
    """р — descending vertical + top bump (like p)."""
    return [
        _vstroke(LEFT + 80, X_TOP, DESC, LW_MAIN, seed=550),
        _curve([(LEFT + 80, X_TOP), (RIGHT + 10, X_TOP + 10), (RIGHT + 10, BOT - 10), (LEFT + 80, BOT)],
               LW_MED, seed=551),
    ]


def glyph_es_lower():
    """с — open curve like С but at x-height."""
    return [
        _curve([(RIGHT - 80, X_TOP + 20), (LEFT - 10, X_TOP - 10), (LEFT - 10, BOT + 10), (RIGHT - 80, BOT - 20)],
               LW_MAIN, seed=560),
    ]


def glyph_te_lower():
    """т — like uppercase Т at x-height."""
    return [
        _vstroke(CENTER, X_TOP, BOT, LW_MAIN, seed=570),
        _hstroke(X_TOP, LEFT + 40, RIGHT - 40, LW_MED, seed=571),
    ]


def glyph_u_lower():
    """у — two diagonals, right one descends below baseline."""
    return [
        _diag(LEFT + 60, X_TOP, CENTER, MID + 60, LW_MAIN, seed=580),
        _diag(RIGHT - 60, X_TOP, CENTER - 80, DESC, LW_MAIN, seed=581),
    ]


def glyph_ef_lower():
    """ф — central vertical + circle through center."""
    return [
        _vstroke(CENTER, TOP, DESC, LW_MAIN, seed=590),
        _curve([(CENTER, X_TOP + 20), (RIGHT + 20, X_TOP + 20), (RIGHT + 20, BOT - 20), (CENTER, BOT - 20)],
               LW_MED, seed=591, pressure_end=0.5),
        _curve([(CENTER, BOT - 20), (LEFT - 20, BOT - 20), (LEFT - 20, X_TOP + 20), (CENTER, X_TOP + 20)],
               LW_MED, seed=592, pressure_end=0.5),
    ]


def glyph_kha_lower():
    """х — two crossing diagonals."""
    return [
        _diag(LEFT + 80, X_TOP, RIGHT - 80, BOT, LW_MAIN, seed=600),
        _diag(RIGHT - 80, X_TOP, LEFT + 80, BOT, LW_MAIN, seed=601),
    ]


def glyph_tse_lower():
    """ц — like п but with descender."""
    return [
        _vstroke(LEFT + 60, X_TOP, BOT, LW_MAIN, seed=610),
        _vstroke(RIGHT - 100, X_TOP, BOT, LW_MAIN, seed=611),
        _hstroke(BOT, LEFT + 60, RIGHT - 40, LW_THIN, seed=612),
        _vstroke(RIGHT - 40, BOT - 20, BOT + 100, LW_THIN, seed=613),
    ]


def glyph_che_lower():
    """ч — left stub from top + curve to right vertical."""
    return [
        _vstroke(LEFT + 80, X_TOP, MID + 40, LW_MAIN, seed=620),
        _curve([(LEFT + 80, MID + 40), (LEFT + 80, MID + 110), (RIGHT - 80, MID + 50), (RIGHT - 80, MID)],
               LW_THIN, seed=621),
        _vstroke(RIGHT - 80, X_TOP, BOT, LW_MAIN, seed=622),
    ]


def glyph_sha_lower():
    """ш — three verticals + bottom bar."""
    return [
        _vstroke(LEFT + 50, X_TOP, BOT, LW_MAIN, seed=630),
        _vstroke(CENTER, X_TOP, BOT, LW_MAIN, seed=631),
        _vstroke(RIGHT - 50, X_TOP, BOT, LW_MAIN, seed=632),
        _hstroke(BOT, LEFT + 50, RIGHT - 50, LW_THIN, seed=633),
    ]


def glyph_shcha_lower():
    """щ — ш + descender."""
    return [
        _vstroke(LEFT + 40, X_TOP, BOT, LW_MED, seed=640),
        _vstroke(CENTER - 15, X_TOP, BOT, LW_MED, seed=641),
        _vstroke(RIGHT - 90, X_TOP, BOT, LW_MED, seed=642),
        _hstroke(BOT, LEFT + 40, RIGHT - 30, LW_THIN, seed=643),
        _vstroke(RIGHT - 30, BOT - 20, BOT + 100, LW_THIN, seed=644),
    ]


def glyph_hard_lower():
    """ъ — top-left stub + vertical + bump."""
    return [
        _hstroke(X_TOP, LEFT + 60, CENTER - 20, LW_THIN, seed=650),
        _vstroke(CENTER - 20, X_TOP, BOT, LW_MAIN, seed=651),
        _curve([(CENTER - 20, MID + 20), (RIGHT + 10, MID + 30), (RIGHT + 10, BOT - 10), (CENTER - 20, BOT)],
               LW_MED, seed=652),
    ]


def glyph_yeru_lower():
    """ы — left vertical + bump + right vertical."""
    return [
        _vstroke(LEFT + 80, X_TOP, BOT, LW_MAIN, seed=660),
        _curve([(LEFT + 80, MID + 20), (CENTER + 40, MID + 30), (CENTER + 40, BOT - 10), (LEFT + 80, BOT)],
               LW_MED, seed=661),
        _vstroke(RIGHT - 60, X_TOP, BOT, LW_MAIN, seed=662),
    ]


def glyph_soft_lower():
    """ь — vertical + bottom bump."""
    return [
        _vstroke(LEFT + 100, X_TOP, BOT, LW_MAIN, seed=670),
        _curve([(LEFT + 100, MID + 20), (RIGHT, MID + 30), (RIGHT, BOT - 10), (LEFT + 100, BOT)],
               LW_MED, seed=671),
    ]


def glyph_e_oborot_lower():
    """э — reversed с + bar."""
    return [
        _curve([(LEFT + 80, X_TOP + 20), (RIGHT + 10, X_TOP - 10), (RIGHT + 10, BOT + 10), (LEFT + 80, BOT - 20)],
               LW_MAIN, seed=680),
        _hstroke(MID + 20, LEFT + 120, RIGHT - 40, LW_THIN, seed=681),
    ]


def glyph_yu_lower():
    """ю — left vertical + bar + right oval."""
    return [
        _vstroke(LEFT + 50, X_TOP, BOT, LW_MAIN, seed=690),
        _hstroke(MID + 20, LEFT + 50, CENTER - 40, LW_THIN, seed=691),
        _curve([(CENTER + 60, X_TOP), (RIGHT + 20, X_TOP), (RIGHT + 20, BOT), (CENTER + 60, BOT)],
               LW_MED, seed=692, pressure_end=0.5),
        _curve([(CENTER + 60, BOT), (CENTER - 60, BOT), (CENTER - 60, X_TOP), (CENTER + 60, X_TOP)],
               LW_MED, seed=693, pressure_end=0.5),
    ]


def glyph_ya_lower():
    """я — mirrored а: right vertical + left bump + left diagonal."""
    return [
        _vstroke(RIGHT - 60, X_TOP, BOT, LW_MAIN, seed=700),
        _curve([(RIGHT - 60, X_TOP), (LEFT + 10, X_TOP + 10), (LEFT + 10, MID + 10), (RIGHT - 60, MID + 20)],
               LW_MED, seed=701),
        _diag(RIGHT - 60, MID + 20, LEFT + 60, BOT, LW_MED, seed=702),
    ]


def glyph_yo_lower():
    """ё — е + two dots."""
    strokes = glyph_ye_lower()
    strokes.append(_curve(
        [(CENTER - 70, X_TOP - 60), (CENTER - 60, X_TOP - 40), (CENTER - 70, X_TOP - 20)],
        W_ACCENT, seed=710, pressure_end=0.7
    ))
    strokes.append(_curve(
        [(CENTER + 50, X_TOP - 60), (CENTER + 60, X_TOP - 40), (CENTER + 50, X_TOP - 20)],
        W_ACCENT, seed=711, pressure_end=0.7
    ))
    return strokes


# ============================================================
# DIGITS
# ============================================================

def glyph_0():
    return [
        _curve([(CENTER, X_TOP), (RIGHT + 10, X_TOP), (RIGHT + 10, BOT), (CENTER, BOT)],
               LW_MED, seed=800, pressure_end=0.5),
        _curve([(CENTER, BOT), (LEFT - 10, BOT), (LEFT - 10, X_TOP), (CENTER, X_TOP)],
               LW_MED, seed=801, pressure_end=0.5),
    ]


def glyph_1():
    return [
        _vstroke(CENTER, X_TOP, BOT, LW_MAIN, seed=810),
        _diag(CENTER, X_TOP, CENTER - 80, X_TOP + 80, LW_THIN, seed=811),
    ]


def glyph_2():
    return [
        _curve([(LEFT + 60, X_TOP + 60), (LEFT + 60, X_TOP - 20), (RIGHT - 60, X_TOP - 20), (RIGHT - 60, MID)],
               LW_MED, seed=820),
        _diag(RIGHT - 60, MID, LEFT + 40, BOT, LW_MED, seed=821),
        _hstroke(BOT, LEFT + 40, RIGHT - 40, LW_MED, seed=822),
    ]


def glyph_3():
    return [
        _curve([(LEFT + 80, X_TOP + 20), (RIGHT - 60, X_TOP), (RIGHT - 60, MID), (CENTER, MID + 20)],
               LW_MED, seed=830),
        _curve([(CENTER, MID + 20), (RIGHT - 40, MID + 30), (RIGHT - 40, BOT - 10), (LEFT + 80, BOT - 20)],
               LW_MED, seed=831),
    ]


def glyph_4():
    return [
        _vstroke(RIGHT - 120, TOP + 40, BOT, LW_MAIN, seed=840),
        _diag(RIGHT - 120, MID + 40, LEFT + 40, X_TOP, LW_MED, seed=841),
        _hstroke(MID + 40, LEFT + 40, RIGHT - 40, LW_THIN, seed=842),
    ]


def glyph_5():
    return [
        _hstroke(X_TOP, LEFT + 60, RIGHT - 60, LW_MED, seed=850),
        _vstroke(LEFT + 60, X_TOP, MID + 20, LW_MAIN, seed=851),
        _curve([(LEFT + 60, MID + 20), (RIGHT, MID), (RIGHT, BOT - 10), (LEFT + 80, BOT - 20)],
               LW_MED, seed=852),
    ]


def glyph_6():
    return [
        _curve([(RIGHT - 60, X_TOP + 20), (LEFT - 10, X_TOP - 10), (LEFT - 10, BOT + 10), (CENTER, BOT)],
               LW_MED, seed=860),
        _curve([(CENTER, BOT), (RIGHT + 10, BOT), (RIGHT + 10, MID), (CENTER, MID)],
               LW_MED, seed=861, pressure_end=0.5),
        _curve([(CENTER, MID), (LEFT + 20, MID), (LEFT + 20, BOT), (CENTER, BOT)],
               LW_MED, seed=862, pressure_end=0.5),
    ]


def glyph_7():
    return [
        _hstroke(X_TOP, LEFT + 40, RIGHT - 40, LW_MED, seed=870),
        _diag(RIGHT - 40, X_TOP, CENTER - 20, BOT, LW_MAIN, seed=871),
    ]


def glyph_8():
    return [
        _curve([(CENTER, MID + 10), (LEFT + 40, MID), (LEFT + 40, X_TOP), (CENTER, X_TOP)],
               LW_MED, seed=880, pressure_end=0.5),
        _curve([(CENTER, X_TOP), (RIGHT - 40, X_TOP), (RIGHT - 40, MID), (CENTER, MID + 10)],
               LW_MED, seed=881, pressure_end=0.5),
        _curve([(CENTER, MID + 10), (LEFT + 20, MID + 20), (LEFT + 20, BOT), (CENTER, BOT)],
               LW_MED, seed=882, pressure_end=0.5),
        _curve([(CENTER, BOT), (RIGHT - 20, BOT), (RIGHT - 20, MID + 20), (CENTER, MID + 10)],
               LW_MED, seed=883, pressure_end=0.5),
    ]


def glyph_9():
    return [
        _curve([(CENTER, X_TOP), (RIGHT + 10, X_TOP), (RIGHT + 10, MID + 20), (CENTER, MID + 20)],
               LW_MED, seed=890, pressure_end=0.5),
        _curve([(CENTER, MID + 20), (LEFT - 10, MID + 20), (LEFT - 10, X_TOP), (CENTER, X_TOP)],
               LW_MED, seed=891, pressure_end=0.5),
        _curve([(CENTER, MID + 20), (RIGHT + 10, MID + 30), (RIGHT + 10, BOT + 10), (LEFT + 60, BOT - 20)],
               LW_MED, seed=892),
    ]


# ============================================================
# PUNCTUATION
# ============================================================

def glyph_period():
    return [_curve([(CENTER - 15, BOT - 20), (CENTER + 15, BOT - 30), (CENTER, BOT)],
                   W_ACCENT + 10, seed=900, pressure_end=0.8)]


def glyph_comma():
    return [_curve([(CENTER, BOT - 30), (CENTER + 10, BOT), (CENTER - 15, BOT + 50)],
                   W_ACCENT + 5, seed=910, pressure_end=0.3)]


def glyph_exclam():
    return [
        _vstroke(CENTER, X_TOP, BOT - 100, LW_MAIN, seed=920),
        _curve([(CENTER - 12, BOT - 15), (CENTER + 12, BOT - 25), (CENTER, BOT)],
               W_ACCENT + 8, seed=921, pressure_end=0.8),
    ]


def glyph_question():
    return [
        _curve([(LEFT + 100, X_TOP + 40), (LEFT + 80, X_TOP - 10), (RIGHT - 80, X_TOP - 10), (RIGHT - 80, MID)],
               LW_MED, seed=930),
        _vstroke(CENTER, MID, BOT - 100, LW_MED, seed=931),
        _curve([(CENTER - 12, BOT - 15), (CENTER + 12, BOT - 25), (CENTER, BOT)],
               W_ACCENT + 8, seed=932, pressure_end=0.8),
    ]


def glyph_hyphen():
    return [_hstroke(MID + 30, LEFT + 120, RIGHT - 120, LW_MED, seed=940)]


def glyph_semicolon():
    return [
        _curve([(CENTER - 12, MID - 20), (CENTER + 12, MID - 30), (CENTER, MID)],
               W_ACCENT + 5, seed=945, pressure_end=0.8),
        _curve([(CENTER, BOT - 30), (CENTER + 10, BOT), (CENTER - 15, BOT + 50)],
               W_ACCENT + 5, seed=946, pressure_end=0.3),
    ]


def glyph_colon():
    return [
        _curve([(CENTER - 12, MID - 20), (CENTER + 12, MID - 30), (CENTER, MID)],
               W_ACCENT + 5, seed=947, pressure_end=0.8),
        _curve([(CENTER - 12, BOT - 15), (CENTER + 12, BOT - 25), (CENTER, BOT)],
               W_ACCENT + 8, seed=948, pressure_end=0.8),
    ]


def glyph_lparen():
    return [_curve([(CENTER + 60, TOP), (LEFT + 40, MID), (CENTER + 60, BOT + 40)],
                   LW_MED, seed=950)]


def glyph_rparen():
    return [_curve([(CENTER - 60, TOP), (RIGHT - 40, MID), (CENTER - 60, BOT + 40)],
                   LW_MED, seed=951)]


def glyph_laquo():
    """«"""
    return [
        _diag(CENTER, MID, LEFT + 80, X_TOP + 40, LW_THIN, seed=960),
        _diag(CENTER, MID, LEFT + 80, BOT - 40, LW_THIN, seed=961),
        _diag(RIGHT - 80, MID, CENTER - 20, X_TOP + 40, LW_THIN, seed=962),
        _diag(RIGHT - 80, MID, CENTER - 20, BOT - 40, LW_THIN, seed=963),
    ]


def glyph_raquo():
    """»"""
    return [
        _diag(LEFT + 120, MID, CENTER + 20, X_TOP + 40, LW_THIN, seed=970),
        _diag(LEFT + 120, MID, CENTER + 20, BOT - 40, LW_THIN, seed=971),
        _diag(CENTER + 20, MID, RIGHT - 80, X_TOP + 40, LW_THIN, seed=972),
        _diag(CENTER + 20, MID, RIGHT - 80, BOT - 40, LW_THIN, seed=973),
    ]


# ============================================================
# MASTER GLYPH TABLE
# Maps each character to its generator function
# ============================================================

GLYPH_TABLE = {
    # Uppercase
    'А': glyph_A, 'Б': glyph_Be, 'В': glyph_Ve, 'Г': glyph_Ge,
    'Д': glyph_De, 'Е': glyph_Ye, 'Ж': glyph_Zhe, 'З': glyph_Ze,
    'И': glyph_I, 'Й': glyph_I_kratkoye, 'К': glyph_Ka, 'Л': glyph_El,
    'М': glyph_Em, 'Н': glyph_En, 'О': glyph_O, 'П': glyph_Pe,
    'Р': glyph_Er, 'С': glyph_Es, 'Т': glyph_Te, 'У': glyph_U,
    'Ф': glyph_Ef, 'Х': glyph_Kha, 'Ц': glyph_Tse, 'Ч': glyph_Che,
    'Ш': glyph_Sha, 'Щ': glyph_Shcha, 'Ъ': glyph_Hard, 'Ы': glyph_Yeru,
    'Ь': glyph_Soft, 'Э': glyph_E_oborot, 'Ю': glyph_Yu, 'Я': glyph_Ya,
    'Ё': glyph_Yo,
    # Lowercase
    'а': glyph_a_lower, 'б': glyph_be_lower, 'в': glyph_ve_lower,
    'г': glyph_ge_lower, 'д': glyph_de_lower, 'е': glyph_ye_lower,
    'ж': glyph_zhe_lower, 'з': glyph_ze_lower, 'и': glyph_i_lower,
    'й': glyph_i_kratkoye_lower, 'к': glyph_ka_lower, 'л': glyph_el_lower,
    'м': glyph_em_lower, 'н': glyph_en_lower, 'о': glyph_o_lower,
    'п': glyph_pe_lower, 'р': glyph_er_lower, 'с': glyph_es_lower,
    'т': glyph_te_lower, 'у': glyph_u_lower, 'ф': glyph_ef_lower,
    'х': glyph_kha_lower, 'ц': glyph_tse_lower, 'ч': glyph_che_lower,
    'ш': glyph_sha_lower, 'щ': glyph_shcha_lower, 'ъ': glyph_hard_lower,
    'ы': glyph_yeru_lower, 'ь': glyph_soft_lower, 'э': glyph_e_oborot_lower,
    'ю': glyph_yu_lower, 'я': glyph_ya_lower, 'ё': glyph_yo_lower,
    # Digits
    '0': glyph_0, '1': glyph_1, '2': glyph_2, '3': glyph_3, '4': glyph_4,
    '5': glyph_5, '6': glyph_6, '7': glyph_7, '8': glyph_8, '9': glyph_9,
    # Punctuation
    '.': glyph_period, ',': glyph_comma, '!': glyph_exclam,
    '?': glyph_question, '-': glyph_hyphen, ';': glyph_semicolon,
    ':': glyph_colon, '(': glyph_lparen, ')': glyph_rparen,
    '«': glyph_laquo, '»': glyph_raquo,
}
