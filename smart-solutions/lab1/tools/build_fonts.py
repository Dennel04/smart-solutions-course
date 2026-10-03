"""Generate the bundled single-stroke fonts in ``config/fonts/``.

Development tool only: the station reads the generated JSON files and does not
need this script or its dependency at run time.

Source: Hershey fonts (Dr. A. V. Hershey, US Naval Weapons Laboratory, 1967;
public-domain glyph data) through the ``Hershey-Fonts`` package (MIT).

Run from ``smart-solutions/lab1``:
    python -m pip install Hershey-Fonts==2.1.0
    python tools/build_fonts.py
"""

from __future__ import annotations

import json
from pathlib import Path

from HersheyFonts import HersheyFonts

OUT_DIR = Path(__file__).resolve().parents[1] / "config" / "fonts"

# name -> human title. Simplex fonts draw each line once (fastest, cleanest
# with a pen); duplex/triplex fonts draw thicker strokes with parallel lines.
FONTS = {
    "futural": "Hershey Sans (simplex, kiireim)",
    "futuram": "Hershey Sans Bold (duplex)",
    "timesr": "Hershey Serif (Times)",
    "scripts": "Hershey Script (simplex)",
    "cursive": "Hershey Cursive",
    "gothiceng": "Hershey Gothic English",
}


def build_font(name: str, title: str) -> dict[str, object]:
    font = HersheyFonts()
    font.load_default_font(name)
    options = font.render_options
    cap_line = options["cap_line"]
    base_line = options["base_line"]
    bottom_line = options["bottom_line"]

    glyphs: dict[str, object] = {}
    for char, glyph in sorted(font.all_glyphs.items()):
        left = glyph.left_offset
        strokes = []
        for stroke in glyph.strokes:
            # Hershey Y grows downwards; ours grows upwards from the baseline.
            points = [[x - left, base_line - y] for x, y in stroke]
            if len(points) >= 2:
                strokes.append(points)
        glyphs[char] = {"advance": glyph.char_width, "strokes": strokes}

    return {
        "version": 1,
        "name": name,
        "title": title,
        "source": "Hershey fonts (public domain) via Hershey-Fonts 2.1.0 (MIT)",
        "units": {
            "cap_height": base_line - cap_line,
            "descent": bottom_line - base_line,
        },
        "glyphs": glyphs,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, title in FONTS.items():
        document = build_font(name, title)
        path = OUT_DIR / f"{name}.json"
        path.write_text(
            json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"{path.name}: {len(document['glyphs'])} glyphs")


if __name__ == "__main__":
    main()
