"""Make a stroke list cheaper to draw without changing what ends up on paper.

* drop repeated points and points on a straight line (each point is a robot
  stop, so fewer points = faster and smoother drawing);
* reorder strokes greedily by nearest start (and reverse a stroke when its end
  is nearer), so pen-up travel between strokes is short;
* join a stroke to the previous one when it starts where that one ended, so
  the pen does not lift and drop on the same spot.
"""

from __future__ import annotations

import math

Point = tuple[float, float]
Stroke = list[Point]

JOIN_TOLERANCE_MM = 0.05
COLLINEAR_TOLERANCE_MM = 0.02


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _offset_from_line(point: Point, a: Point, b: Point) -> float:
    length = _distance(a, b)
    if length == 0:
        return _distance(point, a)
    return abs((b[0] - a[0]) * (a[1] - point[1]) - (a[0] - point[0]) * (b[1] - a[1])) / length


def simplify_stroke(stroke: Stroke) -> Stroke:
    points: Stroke = []
    for point in stroke:
        if not points or _distance(point, points[-1]) > JOIN_TOLERANCE_MM:
            points.append(point)
    if len(points) < 2:
        return points
    result = [points[0]]
    for index in range(1, len(points) - 1):
        nxt = points[index + 1]
        a, b = result[-1], points[index]
        # Keep the point if it bends the line or if the path turns back on itself.
        going_forward = (b[0] - a[0]) * (nxt[0] - b[0]) + (b[1] - a[1]) * (nxt[1] - b[1]) > 0
        if not going_forward or _offset_from_line(b, a, nxt) > COLLINEAR_TOLERANCE_MM:
            result.append(b)
    result.append(points[-1])
    return result


def optimize_strokes(strokes: list[Stroke], start: Point | None = None) -> list[Stroke]:
    pending = [s for s in (simplify_stroke(list(s)) for s in strokes) if len(s) >= 2]
    if not pending:
        return []
    position = start if start is not None else pending[0][0]
    ordered: list[Stroke] = []
    while pending:
        best_index, best_reverse, best_distance = 0, False, math.inf
        for index, stroke in enumerate(pending):
            for reverse, end in ((False, stroke[0]), (True, stroke[-1])):
                distance = _distance(position, end)
                if distance < best_distance:
                    best_index, best_reverse, best_distance = index, reverse, distance
        stroke = pending.pop(best_index)
        if best_reverse:
            stroke = list(reversed(stroke))
        if ordered and _distance(ordered[-1][-1], stroke[0]) <= JOIN_TOLERANCE_MM:
            ordered[-1] = simplify_stroke(ordered[-1] + stroke[1:])
        else:
            ordered.append(stroke)
        position = ordered[-1][-1]
    return ordered


def path_lengths(strokes: list[Stroke], start: Point | None = None) -> tuple[float, float]:
    """(pen-down length, pen-up travel) in the strokes' units."""
    drawn = sum(_distance(a, b) for s in strokes for a, b in zip(s, s[1:]))
    travel = 0.0
    position = start
    for stroke in strokes:
        if position is not None:
            travel += _distance(position, stroke[0])
        position = stroke[-1]
    return drawn, travel
