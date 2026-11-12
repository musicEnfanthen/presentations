"""Render the M 317 sketch excerpt (sketchbook 3, fol. 38v, systems 1-3) once.

Usage: python build/make_m317_excerpt.py [path/to/awg-app]

Reads the AWG app's diplomatic transcriptions of M 317 Sk1, Sk2 and Sk2.1
(SVG, one per sketch, all in the coordinates of the same page), hides their
link boxes (the grey placeholders for the other sketches), renders each with
headless Edge and overlays them with "multiply", so the three sketches stand
together at their places on the page. Writes build/img/m317-38v-sk1-sk2-sk2_1.png
and prints the crop box in SVG units, which build_deck.py uses for its labels.

The PNG is committed: build_deck.py does not need the app or Edge.
"""

import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
APP = (
    sys.argv[1]
    if len(sys.argv) > 1
    else r"C:\Users\muennich\Repositories\webern-unibas-ch\awg-app"
)
SVG_DIR = os.path.join(
    APP, "src", "assets", "img", "edition", "series", "1", "section", "5", "op25"
)
SHEETS = ["M317_Sk2", "M317_Sk1", "M317_Sk2_1"]
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W, H, DPR = 1153, 508, 4  # SVG viewBox and device pixel ratio
CROP = (138, 160, 1008, 305)  # SVG units: systems 1-3, left brace to right edge
OUT = os.path.join(HERE, "img", "m317-38v-sk1-sk2-sk2_1.png")

HIDE = "<style>.link-box{display:none}</style>"

# On its own sheet, the deletion bracket closing Sk1 stands at x = 600, where
# Sk2.1 begins; superimposed, it would cover the bracketed clef of Sk2.1.
# Moved left to x = 586, just before the clef bracket of Sk2.1 (x = 591.5).
SHIFTS = {
    "M317_Sk1": [
        (
            '<g id="awg-tkk-m317_sk1-001" class="tkk">',
            '<g id="awg-tkk-m317_sk1-001" class="tkk" transform="translate(-14 0)">',
        )
    ],
}


def render(sheet, work):
    with open(os.path.join(SVG_DIR, f"{sheet}-1von1-final.svg"), encoding="utf-8") as f:
        svg = f.read()
    svg = svg.replace("</defs>", HIDE + "</defs>", 1)
    for old, new in SHIFTS.get(sheet, []):
        assert old in svg, (sheet, old)
        svg = svg.replace(old, new, 1)
    src = os.path.join(work, f"{sheet}.svg")
    with open(src, "w", encoding="utf-8") as f:
        f.write(svg)
    png = os.path.join(work, f"{sheet}.png")
    subprocess.run(
        [
            EDGE,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--user-data-dir={os.path.join(work, 'profile')}",
            f"--window-size={W},{H}",
            f"--force-device-scale-factor={DPR}",
            f"--screenshot={png}",
            "file:///" + src.replace(os.sep, "/"),
        ],
        check=True,
        timeout=120,
        capture_output=True,
    )
    return Image.open(png).convert("RGB")


def main():
    work = tempfile.mkdtemp(prefix="awg_m317_")
    try:
        layers = [render(s, work) for s in SHEETS]
        page = layers[0]
        for im in layers[1:]:
            page = ImageChops.multiply(page, im)
        box = tuple(round(v * DPR) for v in CROP)
        page.crop(box).save(OUT, optimize=True)
        print("saved", OUT, page.crop(box).size, "crop (SVG units):", CROP)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
