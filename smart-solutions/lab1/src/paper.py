"""Paper sheet on the MG400 table: paper millimetres <-> robot XY, reach checks.

The sheet is calibrated with two taught robot points, both on its bottom edge as
the text will be read: the bottom-left corner and any point further right along
that edge. That fixes where the sheet is *and* how it is rotated, so the text
reads straight however the sheet lies relative to the robot axes.

Paper frame: X along the bottom edge to the right, Y up the sheet (90 degrees
counter-clockwise from X seen from above, like the robot's own X/Y).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from text_layout import Box

Point = tuple[float, float]

# Width x height in portrait orientation, millimetres (ISO 216 / US Letter).
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A5": (148.0, 210.0),
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "Letter": (215.9, 279.4),
}
ORIENTATIONS = ("portrait", "landscape")

# Reachable ring of the MG400 around the base axis, at table height. The
# datasheet says 440 mm working radius, but the inner limit depends on Z: the
# lab arm's joint/parallelogram model (mg400-base kinematics.check) gives
#   Z -60: 206..444 mm, Z -80: 202..444, Z -100: 194..440, Z -120: 212..432.
# So the ring here is 205..440 with a 10 mm margin (= 215..430 mm). Before a
# real run the station also asks mg400-base /api/check for every point.
REACH_MIN_MM = 205.0
REACH_MAX_MM = 440.0
REACH_MARGIN_MM = 10.0
MIN_EDGE_TEACH_MM = 50.0  # shorter baselines make the sheet angle unreliable


class PaperError(ValueError):
    """Invalid paper size, orientation or sheet calibration."""


def paper_size(size: str, orientation: str = "portrait") -> tuple[float, float]:
    if size not in PAPER_SIZES:
        raise PaperError(f"paper size must be one of {', '.join(PAPER_SIZES)}")
    if orientation not in ORIENTATIONS:
        raise PaperError("orientation must be portrait or landscape")
    width, height = PAPER_SIZES[size]
    return (height, width) if orientation == "landscape" else (width, height)


@dataclass(frozen=True)
class PaperFrame:
    corner_x: float
    corner_y: float
    edge_x: float
    edge_y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise PaperError("paper width and height must be positive")
        if self.baseline_length < MIN_EDGE_TEACH_MM:
            raise PaperError(
                f"taught edge point must be at least {MIN_EDGE_TEACH_MM:g} mm from "
                "the corner along the bottom edge"
            )

    @property
    def baseline_length(self) -> float:
        return math.hypot(self.edge_x - self.corner_x, self.edge_y - self.corner_y)

    @property
    def angle_deg(self) -> float:
        """Sheet X axis direction in the robot frame."""
        return math.degrees(
            math.atan2(self.edge_y - self.corner_y, self.edge_x - self.corner_x)
        )

    def to_robot(self, x: float, y: float) -> Point:
        length = self.baseline_length
        ux = (self.edge_x - self.corner_x) / length
        uy = (self.edge_y - self.corner_y) / length
        # Paper Y is paper X turned 90 degrees counter-clockwise.
        return (
            self.corner_x + x * ux - y * uy,
            self.corner_y + x * uy + y * ux,
        )

    def margin_box(self, margin_mm: float) -> Box:
        if margin_mm < 0 or 2 * margin_mm >= min(self.width, self.height):
            raise PaperError("margin is negative or leaves no drawing area")
        return Box(margin_mm, margin_mm, self.width - 2 * margin_mm, self.height - 2 * margin_mm)


def point_reachable(x: float, y: float, margin: float = REACH_MARGIN_MM) -> bool:
    radius = math.hypot(x, y)
    return REACH_MIN_MM + margin <= radius <= REACH_MAX_MM - margin


def segment_reachable(a: Point, b: Point, margin: float = REACH_MARGIN_MM) -> bool:
    """A straight move stays in the ring if both ends do and the closest point of
    the line to the base axis is not inside the inner circle."""
    if not (point_reachable(*a, margin) and point_reachable(*b, margin)):
        return False
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return True
    t = max(0.0, min(1.0, -(a[0] * dx + a[1] * dy) / length_sq))
    closest = math.hypot(a[0] + t * dx, a[1] + t * dy)
    return closest >= REACH_MIN_MM + margin


def reachable_grid(frame: PaperFrame, step_mm: float = 5.0) -> list[tuple[float, float, bool]]:
    """Sample the sheet (paper mm) and mark which points the arm can reach."""
    cells = []
    columns = int(frame.width // step_mm) + 1
    rows = int(frame.height // step_mm) + 1
    for row in range(rows):
        for column in range(columns):
            x, y = column * step_mm, row * step_mm
            cells.append((x, y, point_reachable(*frame.to_robot(x, y))))
    return cells


def largest_reachable_box(frame: PaperFrame, margin_mm: float, step_mm: float = 5.0) -> Box | None:
    """Biggest axis-aligned rectangle (paper frame) inside the margins whose
    every grid point is reachable. Grid search: maximal rectangle in a binary
    matrix via column heights, O(rows * columns)."""
    area = frame.margin_box(margin_mm)
    columns = int(area.width // step_mm) + 1
    rows = int(area.height // step_mm) + 1
    heights = [0] * columns
    best: tuple[float, Box] | None = None
    for row in range(rows):
        y = area.y + row * step_mm
        for column in range(columns):
            x = area.x + column * step_mm
            ok = point_reachable(*frame.to_robot(x, y))
            heights[column] = heights[column] + 1 if ok else 0
        stack: list[int] = []
        for column in range(columns + 1):
            current = heights[column] if column < columns else 0
            while stack and heights[stack[-1]] >= current:
                height = heights[stack.pop()]
                left = stack[-1] + 1 if stack else 0
                width_cells = column - left
                if height >= 2 and width_cells >= 2:
                    box = Box(
                        area.x + left * step_mm,
                        y - (height - 1) * step_mm,
                        (width_cells - 1) * step_mm,
                        (height - 1) * step_mm,
                    )
                    size = box.width * box.height
                    if best is None or size > best[0]:
                        best = (size, box)
            stack.append(column)
    return None if best is None else best[1]
