from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

LAB1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB1_ROOT / "src"))

from fonts import COMPOSED, FontError, available_fonts, load_font, normalized_letter
from paper import (
    PaperError,
    PaperFrame,
    largest_reachable_box,
    paper_size,
    point_reachable,
    segment_reachable,
)
from path_optimize import optimize_strokes, path_lengths, simplify_stroke
from robot_calibration import CalibrationError, validate_robot_calibration
from test_robot_calibration import synthetic_document
from text_job import (
    TextJobError,
    build_robot_plan,
    build_text_job,
    estimate_seconds,
    letter_on_paper,
    parse_request,
    preview_svg,
)
from text_layout import Box, LayoutError, TextStyle, fit_size, layout_in_box, layout_text


def text_calibration(**paper: object):
    document = synthetic_document()
    document["paper"] = {
        # Bottom edge along robot -Y at X 200: the sheet extends towards +X.
        "corner_x": 200.0,
        "corner_y": 105.0,
        "edge_x": 200.0,
        "edge_y": -105.0,
        "size": "A4",
        "orientation": "landscape",
        "margin_mm": 15.0,
        **paper,
    }
    return validate_robot_calibration(document)


def bounds(strokes):
    points = [p for s in strokes for p in s]
    return (
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )


class FontTests(unittest.TestCase):
    def test_bundled_fonts_load_with_full_latin_alphabet(self) -> None:
        names = available_fonts()
        self.assertIn("futural", names)
        for name in names:
            font = load_font(name)
            self.assertEqual(font.missing_characters("AZaz09 .,!?"), [], name)

    def test_estonian_letters_are_composed(self) -> None:
        font = load_font("futural")
        for char, (base, _) in COMPOSED.items():
            glyph = font.glyph(char)
            self.assertGreater(len(glyph.strokes), len(font.glyph(base).strokes), char)
            self.assertEqual(glyph.advance, font.glyph(base).advance)

    def test_accent_sits_above_the_letter(self) -> None:
        font = load_font("futural")
        base_top = bounds(font.glyph("A").strokes)[3]
        accent = font.glyph("Ä").strokes[len(font.glyph("A").strokes):]
        self.assertGreater(bounds(accent)[1], base_top)

    def test_unknown_and_path_like_font_names_are_rejected(self) -> None:
        for name in ("nope", "../config/letters", ""):
            with self.assertRaises(FontError):
                load_font(name)

    def test_normalized_letter_stays_in_unit_box(self) -> None:
        for char in "AMWgQ":
            strokes = normalized_letter(char, load_font("futural"))
            x0, y0, x1, y1 = bounds(strokes)
            self.assertGreaterEqual(min(x0, y0), 0.0)
            self.assertLessEqual(max(x1, y1), 1.0)


class LayoutTests(unittest.TestCase):
    font = load_font("futural")

    def test_capital_height_matches_requested_size(self) -> None:
        layout = layout_text(self.font, "H", TextStyle(size_mm=20))
        _, y0, _, y1 = bounds(layout.strokes)
        self.assertAlmostEqual(y1 - y0, 20.0, places=6)

    def test_words_wrap_to_width_and_are_never_split(self) -> None:
        layout = layout_in_box(
            self.font, "TERE TERE TERE", TextStyle(size_mm=10), Box(0, 0, 60, 100)
        )
        self.assertEqual(layout.lines, ["TERE", "TERE", "TERE"])
        with self.assertRaisesRegex(LayoutError, "wider"):
            layout_in_box(self.font, "NUTIKADLAHENDUSED", TextStyle(size_mm=20), Box(0, 0, 60, 100))

    def test_text_stays_inside_box_for_every_alignment(self) -> None:
        box = Box(10, 20, 150, 80)
        for align in ("left", "center", "right"):
            layout = layout_in_box(self.font, "Tere\nMG400", TextStyle(12, align=align), box)
            x0, y0, x1, y1 = bounds(layout.strokes)
            self.assertGreaterEqual(x0, box.x - 1e-6)
            self.assertLessEqual(x1, box.x + box.width + 1e-6)
            self.assertGreaterEqual(y0, box.y - 1e-6)
            self.assertLessEqual(y1, box.y + box.height + 1e-6)

    def test_accents_and_script_overhang_stay_inside_box(self) -> None:
        box = Box(0, 0, 200, 100)
        for name in ("futural", "scripts", "gothiceng"):
            font = load_font(name)
            size = fit_size(font, "ÕÄÖÜ Šž gjy", TextStyle(10), box)
            layout = layout_in_box(font, "ÕÄÖÜ Šž gjy", TextStyle(size), box)
            x0, y0, x1, y1 = bounds(layout.strokes)
            self.assertGreaterEqual(x0, -1e-6, name)
            self.assertGreaterEqual(y0, -1e-6, name)
            self.assertLessEqual(x1, box.width + 1e-6, name)
            self.assertLessEqual(y1, box.height + 1e-6, name)

    def test_too_big_text_is_rejected_not_clipped(self) -> None:
        with self.assertRaisesRegex(LayoutError, "use a smaller size"):
            layout_in_box(self.font, "A\nB\nC", TextStyle(size_mm=40), Box(0, 0, 200, 60))

    def test_fit_finds_the_largest_size_that_fits(self) -> None:
        box = Box(0, 0, 180, 120)
        style = TextStyle(size_mm=10)
        size = fit_size(self.font, "Nutikad lahendused", style, box)
        layout_in_box(self.font, "Nutikad lahendused", TextStyle(size), box)
        with self.assertRaises(LayoutError):
            layout_in_box(self.font, "Nutikad lahendused", TextStyle(size + 1), box)

    def test_missing_character_is_reported(self) -> None:
        with self.assertRaisesRegex(FontError, "cannot draw"):
            layout_text(self.font, "Привет", TextStyle(size_mm=10))


class PaperTests(unittest.TestCase):
    def test_paper_sizes_and_orientation(self) -> None:
        self.assertEqual(paper_size("A4"), (210.0, 297.0))
        self.assertEqual(paper_size("A4", "landscape"), (297.0, 210.0))
        with self.assertRaises(PaperError):
            paper_size("B5")

    def test_frame_follows_the_taught_rotation(self) -> None:
        frame = PaperFrame(200, 100, 200, -100, 297, 210)
        self.assertEqual(frame.to_robot(0, 0), (200, 100))
        x, y = frame.to_robot(10, 0)
        self.assertAlmostEqual(x, 200)
        self.assertAlmostEqual(y, 90)
        # Up the sheet = 90 degrees counter-clockwise from the bottom edge.
        x, y = frame.to_robot(0, 10)
        self.assertAlmostEqual(x, 210)
        self.assertAlmostEqual(y, 100)

    def test_short_taught_edge_is_rejected(self) -> None:
        with self.assertRaises(PaperError):
            PaperFrame(200, 0, 210, 0, 210, 297)

    def test_reach_ring_and_chord_through_the_base(self) -> None:
        self.assertTrue(point_reachable(300, 0))
        self.assertFalse(point_reachable(100, 0))
        self.assertFalse(point_reachable(450, 0))
        # Both ends reachable, but the straight line passes the base axis.
        self.assertFalse(segment_reachable((170, 120), (-170, 120)))
        self.assertTrue(segment_reachable((250, 50), (250, -50)))

    def test_largest_reachable_box_is_all_reachable(self) -> None:
        frame = PaperFrame(200, 105, 200, -105, 210, 297)
        box = largest_reachable_box(frame, 15)
        self.assertIsNotNone(box)
        assert box is not None
        for x in (box.x, box.x + box.width):
            for y in (box.y, box.y + box.height):
                self.assertTrue(point_reachable(*frame.to_robot(x, y)))


class PathOptimizeTests(unittest.TestCase):
    def test_collinear_and_duplicate_points_are_removed(self) -> None:
        self.assertEqual(
            simplify_stroke([(0, 0), (0, 0), (1, 0), (2, 0), (2, 1)]),
            [(0, 0), (2, 0), (2, 1)],
        )

    def test_reversal_point_is_kept(self) -> None:
        self.assertEqual(simplify_stroke([(0, 0), (2, 0), (1, 0)]), [(0, 0), (2, 0), (1, 0)])

    def test_reordering_reduces_travel_and_keeps_ink(self) -> None:
        strokes = [[(0, 0), (1, 0)], [(100, 0), (101, 0)], [(2, 0), (3, 0)], [(99, 0), (98, 0)]]
        before = path_lengths(strokes)
        after = path_lengths(optimize_strokes(strokes))
        self.assertAlmostEqual(before[0], after[0])
        self.assertLess(after[1], before[1])

    def test_touching_strokes_are_joined(self) -> None:
        joined = optimize_strokes([[(0, 0), (1, 0)], [(1, 0), (1, 1)]])
        self.assertEqual(joined, [[(0, 0), (1, 0), (1, 1)]])


class TextJobTests(unittest.TestCase):
    def test_request_validation(self) -> None:
        for payload in (None, {}, {"text": "  "}, {"text": "A", "size_mm": True},
                        {"text": "A", "fit": "yes"}, {"text": "A", "area": "moon"},
                        {"text": "x" * 401}):
            with self.assertRaises(TextJobError, msg=payload):
                parse_request(payload)

    def test_uncalibrated_preview_works_but_cannot_plan(self) -> None:
        job = build_text_job(parse_request({"text": "TERE", "size_mm": 20}), None)
        self.assertIsNone(job.reachable)
        self.assertIn("<svg", preview_svg(job))
        with self.assertRaisesRegex(TextJobError, "not calibrated"):
            build_robot_plan(job)

    def test_calibrated_plan_is_reachable_pen_safe_and_in_robot_mm(self) -> None:
        job = build_text_job(parse_request({"text": "TERE ÕUN", "size_mm": 15}), text_calibration())
        self.assertTrue(job.reachable)
        plan = build_robot_plan(job)
        self.assertEqual(plan[0], {"action": "PEN_UP"})
        self.assertEqual(plan[-1], {"action": "PEN_UP"})
        moves = [a for a in plan if a["action"] == "MOVE_ROBOT"]
        for move in moves:
            self.assertTrue(point_reachable(move["x"], move["y"]))
        # The pen never goes down twice without lifting in between.
        pen = [a["action"] for a in plan if a["action"] != "MOVE_ROBOT"]
        for a, b in zip(pen, pen[1:]):
            self.assertNotEqual(a, b)

    def test_fit_fills_reachable_area(self) -> None:
        job = build_text_job(parse_request({"text": "MG400", "fit": True}), text_calibration())
        self.assertGreater(job.size_mm, 20)
        x0, y0, x1, y1 = bounds(job.paper_strokes)
        self.assertGreaterEqual(x0, job.box.x - 1e-6)
        self.assertLessEqual(x1, job.box.x + job.box.width + 1e-6)

    def test_whole_sheet_out_of_reach_is_refused(self) -> None:
        calibration = text_calibration(corner_x=330.0, edge_x=330.0)
        job = build_text_job(
            parse_request({"text": "TERE " * 20, "size_mm": 12, "area": "sheet"}), calibration
        )
        self.assertFalse(job.reachable)
        with self.assertRaisesRegex(TextJobError, "reach"):
            build_robot_plan(job)

    def test_estimate_grows_with_lower_speed(self) -> None:
        strokes = [[(0, 0), (50, 0), (50, 50)]]
        self.assertGreater(estimate_seconds(strokes, 5), estimate_seconds(strokes, 50))


class LetterOnPaperTests(unittest.TestCase):
    strokes = [[(0.2, 1.0), (0.2, 0.0), (0.85, 0.0)]]

    def test_wraps_to_next_line_and_restarts_when_full(self) -> None:
        calibration = text_calibration()
        cursor = None
        lines_seen = set()
        for _ in range(200):
            plan, cursor = letter_on_paper(self.strokes, calibration, cursor, 20)
            lines_seen.add(round(cursor[1], 3))
            for action in plan:
                if action["action"] == "MOVE_ROBOT":
                    self.assertTrue(point_reachable(action["x"], action["y"]))
        self.assertGreater(len(lines_seen), 2)

    def test_cursor_outside_the_drawing_area_is_refused(self) -> None:
        # POST /api/paper/cursor takes any x/top; a letter cell left of or
        # above the area would put the pen down off the sheet.
        calibration = text_calibration()
        _, start = letter_on_paper(self.strokes, calibration, None, 20)
        left, top = start[0] - 20, start[1]          # first cell of the area
        for bad in ((left - 50, top), (left, top + 50), (-1e6, top), (left, 1e6)):
            with self.assertRaises(TextJobError, msg=bad):
                letter_on_paper(self.strokes, calibration, bad, 20)
        letter_on_paper(self.strokes, calibration, (left, top), 20)    # still fine

    def test_needs_a_calibrated_sheet(self) -> None:
        with self.assertRaises(TextJobError):
            letter_on_paper(self.strokes, validate_robot_calibration(synthetic_document()), None, 20)


class PaperCalibrationTests(unittest.TestCase):
    def test_old_file_without_paper_is_still_valid(self) -> None:
        calibration = validate_robot_calibration(synthetic_document())
        self.assertFalse(calibration.paper.is_complete)
        with self.assertRaises(CalibrationError):
            calibration.require_text_ready()

    def test_complete_paper_section(self) -> None:
        calibration = text_calibration()
        calibration.require_text_ready()
        self.assertEqual(calibration.paper.orientation, "landscape")

    def test_measured_sheet_size_overrides_the_preset(self) -> None:
        calibration = text_calibration(width_mm=264.0, height_mm=210.0)
        job = build_text_job(parse_request({"text": "A", "size_mm": 10}), calibration)
        self.assertEqual((job.paper_width, job.paper_height), (264.0, 210.0))
        with self.assertRaises(CalibrationError):
            text_calibration(width_mm=264.0)
        with self.assertRaises(CalibrationError):
            text_calibration(width_mm=-1.0, height_mm=210.0)

    def test_invalid_paper_values(self) -> None:
        for override in ({"size": "B4"}, {"orientation": "up"}, {"margin_mm": -1},
                         {"edge_x": 200.0, "edge_y": 90.0}, {"corner_x": True}):
            with self.assertRaises(CalibrationError, msg=override):
                text_calibration(**override)


if __name__ == "__main__":
    unittest.main()
