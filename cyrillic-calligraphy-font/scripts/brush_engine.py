#!/usr/bin/env python3
"""
Brush stroke engine for generating calligraphy-style SVG paths.

Simulates Japanese brush calligraphy (Shodo) characteristics:
- Variable stroke width (thick-to-thin transitions)
- Organic bezier curves with slight irregularity
- Ink pooling at stroke starts/ends
- Brush entry and exit dynamics
"""

import math
import random
from dataclasses import dataclass, field


@dataclass
class BrushParams:
    """Parameters controlling brush behavior."""
    base_width: float = 60.0       # Base stroke width
    pressure_start: float = 0.8    # Pressure at stroke start (0-1)
    pressure_mid: float = 1.0      # Pressure at midpoint
    pressure_end: float = 0.3      # Pressure at stroke end (thin exit)
    wobble: float = 3.0            # Random wobble magnitude
    entry_flare: float = 1.3       # Flare at stroke entry (ink pooling)
    taper_start: float = 0.15      # Where taper begins (0-1 along stroke)
    taper_end: float = 0.75        # Where end taper begins
    seed: int | None = None


@dataclass
class Point:
    x: float
    y: float

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, s):
        return Point(self.x * s, self.y * s)

    def lerp(self, other, t):
        return Point(self.x + (other.x - self.x) * t, self.y + (other.y - self.y) * t)

    def length(self):
        return math.sqrt(self.x**2 + self.y**2)

    def normalized(self):
        ln = self.length()
        if ln < 1e-9:
            return Point(0, 0)
        return Point(self.x / ln, self.y / ln)

    def normal(self):
        """Perpendicular (left-hand normal)."""
        return Point(-self.y, self.x).normalized()

    def tup(self):
        return (round(self.x, 1), round(self.y, 1))


def cubic_bezier_point(p0, p1, p2, p3, t):
    """Evaluate cubic bezier at parameter t."""
    u = 1 - t
    return (p0 * (u**3)) + (p1 * (3 * u**2 * t)) + (p2 * (3 * u * t**2)) + (p3 * (t**3))


def cubic_bezier_tangent(p0, p1, p2, p3, t):
    """Tangent of cubic bezier at parameter t."""
    u = 1 - t
    d = (p1 - p0) * (3 * u**2) + (p2 - p1) * (6 * u * t) + (p3 - p2) * (3 * t**2)
    return d


def pressure_profile(t, params: BrushParams):
    """Calculate brush pressure at position t (0..1) along stroke."""
    if t < params.taper_start:
        # Entry: ramp up with flare
        frac = t / max(params.taper_start, 0.01)
        p = params.pressure_start + (params.pressure_mid * params.entry_flare - params.pressure_start) * frac
        # Smooth flare falloff
        if frac > 0.5:
            p = params.pressure_mid * params.entry_flare - (params.pressure_mid * params.entry_flare - params.pressure_mid) * ((frac - 0.5) / 0.5)
        return p
    elif t > params.taper_end:
        # Exit: taper to thin
        frac = (t - params.taper_end) / max(1 - params.taper_end, 0.01)
        return params.pressure_mid + (params.pressure_end - params.pressure_mid) * frac
    else:
        return params.pressure_mid


def generate_brush_stroke_outline(
    spine_points: list[tuple[float, float]],
    params: BrushParams | None = None,
    num_samples: int = 40,
) -> str:
    """Generate a filled SVG path from a spine (center line) with brush dynamics.

    Args:
        spine_points: List of (x, y) defining the stroke center.
                      2 points = line, 3 = quadratic bezier, 4 = cubic bezier.
        params: Brush parameters.
        num_samples: Number of sample points along the stroke.

    Returns:
        SVG path 'd' attribute string for the filled brush stroke.
    """
    if params is None:
        params = BrushParams()

    rng = random.Random(params.seed)

    pts = [Point(x, y) for x, y in spine_points]

    # Evaluate spine as bezier
    if len(pts) == 2:
        # Line -> make it a cubic bezier
        p0, p3 = pts[0], pts[1]
        p1 = p0.lerp(p3, 0.33)
        p2 = p0.lerp(p3, 0.66)
    elif len(pts) == 3:
        # Quadratic -> elevate to cubic
        p0, q1, p3 = pts
        p1 = p0 + (q1 - p0) * (2.0 / 3.0)
        p2 = p3 + (q1 - p3) * (2.0 / 3.0)
    elif len(pts) == 4:
        p0, p1, p2, p3 = pts
    else:
        # More points: use first 4
        p0, p1, p2, p3 = pts[0], pts[1], pts[-2], pts[-1]

    # Sample points along spine
    left_side = []
    right_side = []

    for i in range(num_samples + 1):
        t = i / num_samples
        pos = cubic_bezier_point(p0, p1, p2, p3, t)
        tan = cubic_bezier_tangent(p0, p1, p2, p3, t)

        if tan.length() < 1e-9:
            tan = Point(1, 0)
        norm = Point(-tan.y, tan.x).normalized()

        # Pressure-dependent width
        pressure = pressure_profile(t, params)
        half_w = (params.base_width * pressure) / 2.0

        # Add wobble for organic feel
        wobble_offset = rng.gauss(0, params.wobble)

        left = pos + norm * (half_w + wobble_offset * 0.5)
        right = pos - norm * (half_w - wobble_offset * 0.5)

        left_side.append(left)
        right_side.append(right)

    # Build closed path: left side forward, right side backward
    right_side.reverse()
    outline = left_side + right_side

    # Generate SVG path with smooth curves
    if len(outline) < 4:
        return ""

    d = f"M{outline[0].x:.1f},{outline[0].y:.1f}"

    # Use cubic bezier approximation for smoothness
    i = 1
    while i < len(outline) - 2:
        p_curr = outline[i]
        p_next = outline[i + 1]
        # Simple Catmull-Rom to cubic bezier conversion
        p_prev = outline[i - 1]
        p_nn = outline[min(i + 2, len(outline) - 1)]

        cp1 = Point(
            p_curr.x + (p_next.x - p_prev.x) / 6.0,
            p_curr.y + (p_next.y - p_prev.y) / 6.0,
        )
        cp2 = Point(
            p_next.x - (p_nn.x - p_curr.x) / 6.0,
            p_next.y - (p_nn.y - p_curr.y) / 6.0,
        )

        d += f" C{cp1.x:.1f},{cp1.y:.1f} {cp2.x:.1f},{cp2.y:.1f} {p_next.x:.1f},{p_next.y:.1f}"
        i += 1

    d += " Z"
    return d


def make_stroke(spine, width=60, pressure_end=0.3, entry_flare=1.3, seed=None, wobble=3.0):
    """Shorthand for generating a single brush stroke."""
    params = BrushParams(
        base_width=width,
        pressure_end=pressure_end,
        entry_flare=entry_flare,
        seed=seed,
        wobble=wobble,
    )
    return generate_brush_stroke_outline(spine, params)


def compose_glyph(strokes: list[str], viewbox_size=1000) -> str:
    """Compose multiple stroke paths into a single SVG glyph string."""
    paths = "\n".join(
        f'  <path d="{d}" fill="black"/>' for d in strokes if d
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {viewbox_size} {viewbox_size}" '
        f'width="{viewbox_size}" height="{viewbox_size}">\n'
        f'{paths}\n'
        f'</svg>'
    )
