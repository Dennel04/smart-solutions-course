"""Lay text out in millimetres with a single-stroke font.

Coordinates are paper millimetres: X to the right, Y up, as the sheet is read.
``size_mm`` is the capital-letter height (what a ruler measures on an "H").
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fonts import Font, FontError

Point = tuple[float, float]
Stroke = list[Point]

ALIGNMENTS = ("left", "center", "right")
MIN_SIZE_MM = 3.0  # below this a 0.5-1 mm pen turns letters into blobs


class LayoutError(ValueError):
    """The text cannot be laid out with the requested settings."""


@dataclass(frozen=True)
class TextStyle:
    size_mm: float
    line_spacing: float = 1.6  # baseline-to-baseline distance / size_mm
    letter_spacing_mm: float = 0.0
    align: str = "left"

    def validate(self) -> None:
        if not math.isfinite(self.size_mm) or self.size_mm <= 0:
            raise LayoutError("size_mm must be a positive number")
        if not math.isfinite(self.line_spacing) or self.line_spacing < 1.0:
            raise LayoutError("line_spacing must be at least 1.0")
        if not math.isfinite(self.letter_spacing_mm) or self.letter_spacing_mm < -self.size_mm / 4:
            raise LayoutError("letter_spacing_mm is too negative")
        if self.align not in ALIGNMENTS:
            raise LayoutError(f"align must be one of {', '.join(ALIGNMENTS)}")


@dataclass(frozen=True)
class Box:
    """Rectangle on the paper: lower-left corner plus size, millimetres."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class TextLayout:
    strokes: list[Stroke]
    lines: list[str]
    size_mm: float
    width: float  # block width, mm
    height: float  # cap top of the first line to descender of the last, mm


def _scale(font: Font, style: TextStyle) -> float:
    return style.size_mm / font.cap_height


def line_width(font: Font, line: str, style: TextStyle) -> float:
    if not line:
        return 0.0
    scale = _scale(font, style)
    advances = sum(font.glyph(c).advance for c in line) * scale
    return advances + style.letter_spacing_mm * (len(line) - 1)


def wrap_text(font: Font, text: str, style: TextStyle, max_width: float | None) -> list[str]:
    """Split on newlines, then greedily wrap words to ``max_width`` mm.

    Words are never broken: a word wider than the line is an error, so fit
    mode picks a size where every word fits whole.
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        if max_width is None:
            lines.append(" ".join(words))
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if line_width(font, candidate, style) <= max_width:
                current = candidate
                continue
            if line_width(font, word, style) > max_width:
                raise LayoutError(
                    f"word {word!r} is wider than {max_width:.1f} mm at "
                    f"{style.size_mm:g} mm; use a smaller size or fit"
                )
            if current:
                lines.append(current)
            current = word
        lines.append(current)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def layout_text(
    font: Font,
    text: str,
    style: TextStyle,
    max_width: float | None = None,
) -> TextLayout:
    """Strokes of the text block with its top-left corner at (0, 0)."""
    style.validate()
    missing = font.missing_characters(text)
    if missing:
        raise FontError(
            f"font {font.name} cannot draw: {' '.join(repr(c) for c in missing)}"
        )
    lines = wrap_text(font, text, style, max_width)
    if not any(line.strip() for line in lines):
        raise LayoutError("text is empty")

    scale = _scale(font, style)
    pitch = style.size_mm * style.line_spacing
    widths = [line_width(font, line, style) for line in lines]
    block_width = max(widths)
    strokes: list[Stroke] = []
    for index, (line, width) in enumerate(zip(lines, widths)):
        baseline = -index * pitch
        if style.align == "center":
            cursor = (block_width - width) / 2
        elif style.align == "right":
            cursor = block_width - width
        else:
            cursor = 0.0
        for char in line:
            glyph = font.glyph(char)
            for stroke in glyph.strokes:
                strokes.append(
                    [(cursor + x * scale, baseline + y * scale) for x, y in stroke]
                )
            cursor += glyph.advance * scale + style.letter_spacing_mm

    # The block is measured by real ink as well as by font metrics: accents
    # (Õ, Ä) rise above the capital height and some script glyphs overhang.
    points = [p for stroke in strokes for p in stroke]
    left = min([0.0] + [p[0] for p in points])
    right = max([block_width] + [p[0] for p in points])
    top = max([style.size_mm] + [p[1] for p in points])
    bottom = min(
        [-(len(lines) - 1) * pitch - font.descent * scale] + [p[1] for p in points]
    )
    moved = [[(x - left, y - top) for x, y in stroke] for stroke in strokes]
    return TextLayout(moved, lines, style.size_mm, right - left, top - bottom)


def layout_in_box(
    font: Font,
    text: str,
    style: TextStyle,
    box: Box,
    *,
    wrap: bool = True,
) -> TextLayout:
    """Lay the text out inside ``box``: top-aligned, horizontally per style."""
    layout = layout_text(font, text, style, box.width if wrap else None)
    if layout.width > box.width + 1e-6 or layout.height > box.height + 1e-6:
        raise LayoutError(
            f"text needs {layout.width:.1f} x {layout.height:.1f} mm but the area is "
            f"{box.width:.1f} x {box.height:.1f} mm; use a smaller size or fit"
        )
    if style.align == "center":
        left = box.x + (box.width - layout.width) / 2
    elif style.align == "right":
        left = box.x + box.width - layout.width
    else:
        left = box.x
    top = box.y + box.height
    moved = [[(left + x, top + y) for x, y in stroke] for stroke in layout.strokes]
    return TextLayout(moved, layout.lines, layout.size_mm, layout.width, layout.height)


def fit_size(
    font: Font,
    text: str,
    style: TextStyle,
    box: Box,
    *,
    wrap: bool = True,
    max_size_mm: float | None = None,
) -> float:
    """Largest capital height (0.1 mm steps) that fits the text in ``box``."""
    def fits(size: float) -> bool:
        trial = TextStyle(size, style.line_spacing, style.letter_spacing_mm, style.align)
        try:
            layout_in_box(font, text, trial, box, wrap=wrap)
        except LayoutError:
            return False
        return True

    low = MIN_SIZE_MM
    high = max_size_mm if max_size_mm is not None else box.height
    if not fits(low):
        raise LayoutError(
            f"text does not fit {box.width:.0f} x {box.height:.0f} mm even at "
            f"{MIN_SIZE_MM:g} mm; shorten it or use a larger area"
        )
    if fits(high):
        return round(high, 1)
    for _ in range(40):
        middle = (low + high) / 2
        if fits(middle):
            low = middle
        else:
            high = middle
    return math.floor(low * 10) / 10
