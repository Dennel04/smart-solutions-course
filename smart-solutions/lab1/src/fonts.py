"""Single-stroke (pen plotter) fonts bundled in ``config/fonts/``.

Glyph units: X grows to the right from the glyph's left side, Y grows upwards
from the baseline. ``units.cap_height`` is the height of a capital letter; the
text layout scales it to the requested size in millimetres.

The Hershey data has no Estonian letters, so Õ Ä Ö Ü Š Ž (and lowercase) are
composed from the base letter plus a stroked accent above it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

Point = tuple[float, float]
Stroke = list[Point]

FONTS_DIR = Path(__file__).resolve().parents[1] / "config" / "fonts"
DEFAULT_FONT = "futural"


class FontError(ValueError):
    """Unknown font, broken font file or a character the font cannot draw."""


@dataclass(frozen=True)
class Glyph:
    advance: float
    strokes: tuple[tuple[Point, ...], ...]


@dataclass(frozen=True)
class Font:
    name: str
    title: str
    cap_height: float
    descent: float
    glyphs: dict[str, Glyph]

    def glyph(self, char: str) -> Glyph:
        try:
            return self.glyphs[char]
        except KeyError as exc:
            raise FontError(f"font {self.name} cannot draw {char!r}") from exc

    def missing_characters(self, text: str) -> list[str]:
        return sorted({c for c in text if c not in self.glyphs and c != "\n"})


def _accent_strokes(kind: str, center_x: float, base_y: float, unit: float) -> list[Stroke]:
    """Accent strokes centred on ``center_x`` starting at height ``base_y``."""
    u = unit
    if kind == "diaeresis":
        # A pen dot is a tiny cross so it leaves a visible mark.
        return [
            [(center_x - 3.5 * u, base_y + u), (center_x - 2.5 * u, base_y + u)],
            [(center_x - 3 * u, base_y + 0.5 * u), (center_x - 3 * u, base_y + 1.5 * u)],
            [(center_x + 2.5 * u, base_y + u), (center_x + 3.5 * u, base_y + u)],
            [(center_x + 3 * u, base_y + 0.5 * u), (center_x + 3 * u, base_y + 1.5 * u)],
        ]
    if kind == "tilde":
        return [
            [
                (center_x - 4 * u, base_y + 0.5 * u),
                (center_x - 2.5 * u, base_y + 1.8 * u),
                (center_x - 1 * u, base_y + 1.6 * u),
                (center_x + 1 * u, base_y + 0.6 * u),
                (center_x + 2.5 * u, base_y + 0.4 * u),
                (center_x + 4 * u, base_y + 1.7 * u),
            ]
        ]
    if kind == "caron":
        return [
            [
                (center_x - 3 * u, base_y + 2.5 * u),
                (center_x, base_y + 0.5 * u),
                (center_x + 3 * u, base_y + 2.5 * u),
            ]
        ]
    raise FontError(f"unknown accent {kind}")


# Composed letter -> (base letter, accent).
COMPOSED = {
    "Õ": ("O", "tilde"),
    "Ä": ("A", "diaeresis"),
    "Ö": ("O", "diaeresis"),
    "Ü": ("U", "diaeresis"),
    "Š": ("S", "caron"),
    "Ž": ("Z", "caron"),
    "õ": ("o", "tilde"),
    "ä": ("a", "diaeresis"),
    "ö": ("o", "diaeresis"),
    "ü": ("u", "diaeresis"),
    "š": ("s", "caron"),
    "ž": ("z", "caron"),
}


def _compose(base: Glyph, accent: str, cap_height: float) -> Glyph:
    points = [p for stroke in base.strokes for p in stroke]
    xs = [p[0] for p in points]
    top = max(p[1] for p in points)
    center_x = (min(xs) + max(xs)) / 2
    # Accents scale with the font: 21 units is the Hershey capital height.
    unit = cap_height / 21.0
    accent_strokes = _accent_strokes(accent, center_x, top + 1.5 * unit, unit)
    strokes = tuple(base.strokes) + tuple(tuple(s) for s in accent_strokes)
    return Glyph(advance=base.advance, strokes=strokes)


def _number(value: object, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FontError(f"{location} must be a number")
    return float(value)


def parse_font(document: object, source: str = "font") -> Font:
    if not isinstance(document, dict) or document.get("version") != 1:
        raise FontError(f"{source}: font version must be 1")
    units = document.get("units")
    raw_glyphs = document.get("glyphs")
    if not isinstance(units, dict) or not isinstance(raw_glyphs, dict):
        raise FontError(f"{source}: units and glyphs must be objects")
    cap_height = _number(units.get("cap_height"), f"{source}.units.cap_height")
    descent = _number(units.get("descent", 0), f"{source}.units.descent")
    if cap_height <= 0:
        raise FontError(f"{source}: cap_height must be positive")

    glyphs: dict[str, Glyph] = {}
    for char, raw in raw_glyphs.items():
        location = f"{source}.glyphs[{char!r}]"
        if not isinstance(char, str) or len(char) != 1 or not isinstance(raw, dict):
            raise FontError(f"{location}: invalid glyph")
        strokes = []
        for stroke in raw.get("strokes", []):
            if not isinstance(stroke, list) or len(stroke) < 2:
                raise FontError(f"{location}: stroke needs at least 2 points")
            points = []
            for point in stroke:
                if not isinstance(point, list) or len(point) != 2:
                    raise FontError(f"{location}: point must be [x, y]")
                points.append((_number(point[0], location), _number(point[1], location)))
            strokes.append(tuple(points))
        glyphs[char] = Glyph(_number(raw.get("advance"), location), tuple(strokes))

    for char, (base, accent) in COMPOSED.items():
        if char not in glyphs and base in glyphs and glyphs[base].strokes:
            glyphs[char] = _compose(glyphs[base], accent, cap_height)

    return Font(
        name=str(document.get("name", source)),
        title=str(document.get("title", source)),
        cap_height=cap_height,
        descent=descent,
        glyphs=glyphs,
    )


def available_fonts(fonts_dir: Path = FONTS_DIR) -> list[str]:
    return sorted(path.stem for path in fonts_dir.glob("*.json"))


@lru_cache(maxsize=None)
def load_font(name: str = DEFAULT_FONT, fonts_dir: Path = FONTS_DIR) -> Font:
    # Font names are file stems; never let a request walk out of the folder.
    if not name or not name.replace("_", "").isalnum():
        raise FontError(f"invalid font name {name!r}")
    path = fonts_dir / f"{name}.json"
    if not path.is_file():
        raise FontError(
            f"unknown font {name!r}; available: {', '.join(available_fonts(fonts_dir))}"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FontError(f"cannot read font {path}: {exc}") from exc
    return parse_font(document, name)


def normalized_letter(char: str, font: Font) -> list[list[Point]]:
    """One glyph scaled into the 0..1 letter box used by ``letters.json``.

    Capital height fills the box height; the glyph is centred horizontally and
    never wider than the box.
    """
    glyph = font.glyph(char)
    if not glyph.strokes:
        raise FontError(f"font {font.name} has no strokes for {char!r}")
    points = [p for stroke in glyph.strokes for p in stroke]
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(min(p[1] for p in points), 0.0)
    max_y = max(max(p[1] for p in points), font.cap_height)
    scale = 1.0 / max(max_x - min_x, max_y - min_y)
    offset_x = (1.0 - (max_x - min_x) * scale) / 2
    return [
        [
            (
                min(1.0, max(0.0, offset_x + (x - min_x) * scale)),
                min(1.0, max(0.0, (y - min_y) * scale)),
            )
            for x, y in stroke
        ]
        for stroke in glyph.strokes
    ]
