"""Text request -> laid-out strokes on the sheet -> robot motion plan + preview.

Pure computation: no network and no robot. The station runs the plan through
the same safety-gated executor as a single Atom letter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from html import escape

from fonts import DEFAULT_FONT, FontError, load_font
from motion_plan import MotionAction
from paper import (
    PaperError,
    PaperFrame,
    largest_reachable_box,
    paper_size,
    reachable_grid,
    segment_reachable,
)
from path_optimize import optimize_strokes, path_lengths
from robot_calibration import RobotCalibration
from text_layout import Box, LayoutError, TextStyle, fit_size, layout_in_box

Point = tuple[float, float]
Stroke = list[Point]

MAX_TEXT_LENGTH = 400
# mg400-base: 100 % speed = 200 mm/s, ramp (smoothness) 0.5 s by default.
MG400_MAX_MM_S = 200.0
MG400_RAMP_S = 0.5
PER_MOVE_OVERHEAD_S = 0.15  # HTTP + status polling + settling per point


class TextJobError(ValueError):
    """The request is invalid or cannot be drawn on this sheet."""


@dataclass(frozen=True)
class TextRequest:
    text: str
    font: str = DEFAULT_FONT
    size_mm: float | None = 20.0  # None = largest size that fits
    align: str = "left"
    line_spacing: float = 1.6
    letter_spacing_mm: float = 0.0
    area: str = "reachable"  # "reachable" part of the sheet or the whole "sheet"
    size: str | None = None  # paper size override (preview without calibration)
    orientation: str | None = None
    margin_mm: float | None = None


def _number(payload: dict, key: str, default: float | None) -> float | None:
    value = payload.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TextJobError(f"{key} must be a number")
    return float(value)


def parse_request(payload: object) -> TextRequest:
    if not isinstance(payload, dict):
        raise TextJobError("JSON object required")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TextJobError("text must be a non-empty string")
    text = text.replace("\r\n", "\n").strip("\n")
    if len(text) > MAX_TEXT_LENGTH:
        raise TextJobError(f"text is longer than {MAX_TEXT_LENGTH} characters")
    font = payload.get("font", DEFAULT_FONT)
    if not isinstance(font, str):
        raise TextJobError("font must be a string")
    fit = payload.get("fit", False)
    if not isinstance(fit, bool):
        raise TextJobError("fit must be true or false")
    area = payload.get("area", "reachable")
    if area not in ("reachable", "sheet"):
        raise TextJobError("area must be reachable or sheet")
    for key in ("align", "size", "orientation"):
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            raise TextJobError(f"{key} must be a string")
    return TextRequest(
        text=text,
        font=font,
        size_mm=None if fit else _number(payload, "size_mm", 20.0),
        align=payload.get("align", "left"),
        line_spacing=_number(payload, "line_spacing", 1.6),  # type: ignore[arg-type]
        letter_spacing_mm=_number(payload, "letter_spacing_mm", 0.0),  # type: ignore[arg-type]
        area=area,
        size=payload.get("size"),
        orientation=payload.get("orientation"),
        margin_mm=_number(payload, "margin_mm", None),
    )


@dataclass
class TextJob:
    request: TextRequest
    paper_width: float
    paper_height: float
    box: Box
    size_mm: float
    lines: list[str]
    paper_strokes: list[Stroke]
    frame: PaperFrame | None
    robot_strokes: list[Stroke] | None
    unreachable_segments: int
    drawn_mm: float
    travel_mm: float
    warnings: list[str] = field(default_factory=list)

    @property
    def calibrated(self) -> bool:
        return self.frame is not None

    @property
    def reachable(self) -> bool | None:
        return None if self.frame is None else self.unreachable_segments == 0

    def summary(self, speed_percent: float | None) -> dict[str, object]:
        return {
            "font": self.request.font,
            "size_mm": self.size_mm,
            "lines": self.lines,
            "paper": {"width": self.paper_width, "height": self.paper_height},
            "area": {"x": self.box.x, "y": self.box.y, "width": self.box.width, "height": self.box.height},
            "strokes": len(self.paper_strokes),
            "points": sum(len(s) for s in self.paper_strokes),
            "drawn_mm": round(self.drawn_mm, 1),
            "travel_mm": round(self.travel_mm, 1),
            "estimated_seconds": (
                None
                if speed_percent is None
                else round(estimate_seconds(self.paper_strokes, speed_percent), 0)
            ),
            "calibrated": self.calibrated,
            "reachable": self.reachable,
            "unreachable_segments": self.unreachable_segments,
            "warnings": self.warnings,
        }


def _frame(calibration: RobotCalibration | None, width: float, height: float) -> PaperFrame | None:
    if calibration is None or not calibration.paper.is_complete:
        return None
    paper = calibration.paper
    return PaperFrame(
        paper.corner_x, paper.corner_y, paper.edge_x, paper.edge_y, width, height  # type: ignore[arg-type]
    )


def build_text_job(request: TextRequest, calibration: RobotCalibration | None) -> TextJob:
    paper_cal = calibration.paper if calibration is not None else None
    size_name = request.size or (paper_cal.size if paper_cal else "A4")
    orientation = request.orientation or (paper_cal.orientation if paper_cal else "portrait")
    measured = (
        (paper_cal.width_mm, paper_cal.height_mm)
        if paper_cal is not None and paper_cal.width_mm and request.size is None
        else None
    )
    margin = (
        request.margin_mm
        if request.margin_mm is not None
        else (paper_cal.margin_mm if paper_cal else 15.0)
    )
    try:
        width, height = measured or paper_size(size_name, orientation)
        font = load_font(request.font)
        frame = _frame(calibration, width, height)
        warnings: list[str] = []
        if frame is None:
            box = Box(margin, margin, width - 2 * margin, height - 2 * margin)
            if box.width <= 0 or box.height <= 0:
                raise PaperError("margin leaves no drawing area")
            warnings.append("sheet is not calibrated: preview only, reach not checked")
        elif request.area == "reachable":
            reachable = largest_reachable_box(frame, margin)
            if reachable is None:
                raise PaperError("no part of this sheet is reachable; move the sheet")
            box = reachable
        else:
            box = frame.margin_box(margin)

        style = TextStyle(
            request.size_mm if request.size_mm is not None else 10.0,
            request.line_spacing,
            request.letter_spacing_mm,
            request.align,
        )
        if request.size_mm is None:
            style = TextStyle(
                fit_size(font, request.text, style, box),
                style.line_spacing,
                style.letter_spacing_mm,
                style.align,
            )
        layout = layout_in_box(font, request.text, style, box)
    except (FontError, LayoutError, PaperError) as exc:
        raise TextJobError(str(exc)) from exc

    strokes = optimize_strokes(layout.strokes)
    drawn, travel = path_lengths(strokes)
    robot_strokes = None
    unreachable = 0
    if frame is not None:
        robot_strokes = [[frame.to_robot(x, y) for x, y in s] for s in strokes]
        position: Point | None = None
        for stroke in robot_strokes:
            if position is not None and not segment_reachable(position, stroke[0]):
                unreachable += 1
            unreachable += sum(
                0 if segment_reachable(a, b) else 1 for a, b in zip(stroke, stroke[1:])
            )
            position = stroke[-1]
        if unreachable:
            warnings.append(f"{unreachable} segments are outside the MG400 reach")
    if style.size_mm < 5:
        warnings.append("letters under 5 mm get blurry with a pen; check on paper")
    return TextJob(
        request=request,
        paper_width=width,
        paper_height=height,
        box=box,
        size_mm=style.size_mm,
        lines=layout.lines,
        paper_strokes=strokes,
        frame=frame,
        robot_strokes=robot_strokes,
        unreachable_segments=unreachable,
        drawn_mm=drawn,
        travel_mm=travel,
        warnings=warnings,
    )


def build_robot_plan(job: TextJob) -> list[MotionAction]:
    """Same action vocabulary as letters, with robot XY in millimetres."""
    if job.robot_strokes is None:
        raise TextJobError("sheet is not calibrated; cannot build a robot plan")
    if job.unreachable_segments:
        raise TextJobError("text leaves the MG400 reach; move the sheet or the text")
    actions: list[MotionAction] = [{"action": "PEN_UP"}]
    for stroke in job.robot_strokes:
        x, y = stroke[0]
        actions.append({"action": "MOVE_ROBOT", "x": x, "y": y})
        actions.append({"action": "PEN_DOWN"})
        for x, y in stroke[1:]:
            actions.append({"action": "MOVE_ROBOT", "x": x, "y": y})
        actions.append({"action": "PEN_UP"})
    return actions


def _move_seconds(distance: float, speed: float, accel: float) -> float:
    if distance <= 0:
        return 0.0
    ramp_distance = speed * speed / accel
    if distance >= ramp_distance:
        return distance / speed + speed / accel
    return 2 * math.sqrt(distance / accel)


def estimate_seconds(strokes: list[Stroke], speed_percent: float, pen_lift_mm: float = 5.0) -> float:
    """Rough drawing time: every point is a stop (mg400-base follower ramps)."""
    speed = max(1.0, speed_percent) / 100 * MG400_MAX_MM_S
    accel = speed / MG400_RAMP_S
    total = 0.0
    position: Point | None = None
    for stroke in strokes:
        if position is not None:
            total += _move_seconds(math.dist(position, stroke[0]), speed, accel)
        total += 2 * (_move_seconds(pen_lift_mm, speed, accel) + PER_MOVE_OVERHEAD_S)
        for a, b in zip(stroke, stroke[1:]):
            total += _move_seconds(math.dist(a, b), speed, accel) + PER_MOVE_OVERHEAD_S
        position = stroke[-1]
    return total


def preview_svg(job: TextJob) -> str:
    """Sheet as read from the front: sheet, unreachable zone, area, strokes."""
    w, h = job.paper_width, job.paper_height
    flip = lambda y: h - y  # noqa: E731 - SVG Y grows downwards
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-4 -4 {w + 8:.1f} {h + 8:.1f}" '
        f'width="100%" role="img" aria-label="{escape(" / ".join(job.lines))}">',
        f'<rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" fill="#fff" stroke="#888" stroke-width="0.6"/>',
    ]
    if job.frame is not None:
        step = 5.0
        for x, y, ok in reachable_grid(job.frame, step):
            if not ok:
                parts.append(
                    f'<rect x="{x - step / 2:.1f}" y="{flip(y) - step / 2:.1f}" width="{step}" '
                    f'height="{step}" fill="#e5484d" fill-opacity="0.18"/>'
                )
    b = job.box
    parts.append(
        f'<rect x="{b.x:.1f}" y="{flip(b.y + b.height):.1f}" width="{b.width:.1f}" '
        f'height="{b.height:.1f}" fill="none" stroke="#3e63dd" stroke-width="0.5" '
        'stroke-dasharray="3 2"/>'
    )
    position: Point | None = None
    for stroke in job.paper_strokes:
        if position is not None:
            parts.append(
                f'<line x1="{position[0]:.2f}" y1="{flip(position[1]):.2f}" '
                f'x2="{stroke[0][0]:.2f}" y2="{flip(stroke[0][1]):.2f}" '
                'stroke="#aaa" stroke-width="0.25" stroke-dasharray="1 1"/>'
            )
        points = " ".join(f"{x:.2f},{flip(y):.2f}" for x, y in stroke)
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="#111" stroke-width="0.6" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
        position = stroke[-1]
    parts.append("</svg>")
    return "".join(parts)


def letter_on_paper(
    strokes: list[list[tuple[float, float]]],
    calibration: RobotCalibration,
    cursor: Point | None,
    size_mm: float,
) -> tuple[list[MotionAction], Point]:
    """Typewriter placement for Atom letters on the calibrated sheet.

    ``strokes`` is a normalized 0..1 letter. ``cursor`` is the paper point
    (left, top) of the next letter cell, None = top-left of the reachable
    area. Letters go left to right, then to the next line; a full sheet starts
    again at the top. Returns the robot plan and the cursor after the letter.
    """
    if not math.isfinite(size_mm) or size_mm <= 0:
        raise TextJobError("letter size must be a positive number")
    paper = calibration.paper
    try:
        width, height = (
            (paper.width_mm, paper.height_mm)
            if paper.width_mm and paper.height_mm
            else paper_size(paper.size, paper.orientation)
        )
        frame = _frame(calibration, width, height)
        if frame is None:
            raise TextJobError("sheet is not calibrated")
        box = largest_reachable_box(frame, paper.margin_mm)
    except PaperError as exc:
        raise TextJobError(str(exc)) from exc
    if box is None or box.width < size_mm or box.height < size_mm:
        raise TextJobError(f"no {size_mm:g} mm letter cell fits in the reachable part of the sheet")

    left, top = cursor if cursor is not None else (box.x, box.y + box.height)
    if left + size_mm > box.x + box.width + 1e-6:
        left, top = box.x, top - size_mm * 1.5
    if top - size_mm < box.y - 1e-6:
        left, top = box.x, box.y + box.height
    # The cursor can be set over HTTP: the wraps above only handle the right
    # and bottom edges, so a cell left of or above the area is refused here
    # instead of putting the pen down off the sheet.
    if left < box.x - 1e-6 or top > box.y + box.height + 1e-6:
        raise TextJobError("letter cell is outside the sheet's drawing area")

    def to_robot(u: float, v: float) -> Point:
        return frame.to_robot(left + u * size_mm, top - size_mm + v * size_mm)

    robot_strokes = [[to_robot(u, v) for u, v in stroke] for stroke in strokes]
    for stroke in robot_strokes:
        if not all(segment_reachable(a, b) for a, b in zip(stroke, stroke[1:])):
            raise TextJobError("letter cell leaves the MG400 reach")
    actions: list[MotionAction] = [{"action": "PEN_UP"}]
    for stroke in robot_strokes:
        actions.append({"action": "MOVE_ROBOT", "x": stroke[0][0], "y": stroke[0][1]})
        actions.append({"action": "PEN_DOWN"})
        actions.extend({"action": "MOVE_ROBOT", "x": x, "y": y} for x, y in stroke[1:])
        actions.append({"action": "PEN_UP"})
    return actions, (left + size_mm, top)
