"""הכרעה ו (ברק, 26.9.2026): **גוון נייבי אחד בכל המערכת - #0B2A5B** (צבע התפריט).
פס ההרשמה, הטוקן --band שנוסף לדף הבית, ה-favicon וכל מקום אחר - עוברים אליו.

סריקה סטטית של כל קובצי הממשק (CSS, תבניות, JS, SVG): כל צבע שהוא "נייבי" - כחול
כהה ורווי (גוון 200-250, בהירות 12%-30%, רוויה 35% ומעלה) - חייב להיות בדיוק
#0B2A5B (מותר בשקיפות: rgba(11,42,91,α)). כחול הדגל (#0038B8) וכמעט-שחור (#14171C)
אינם נייבי. הבדיקה בדפדפן (tests/browser/test_navy.py) בודקת את הצבעים המחושבים.
נכשל על הקוד הקודם (#0E2A5A בפס ההרשמה, #1f3a5f ב-favicon).
"""

import colorsys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "apps/api/static/style.css", ROOT / "apps/api/static/app.js",
         ROOT / "apps/api/static/favicon.svg", *sorted((ROOT / "apps/api/templates").glob("*.html"))]
NAVY = (11, 42, 91)
_COLOR = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b|rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
_COMMENT = re.compile(r"/\*.*?\*/|<!--.*?-->", re.S)


def is_navy(rgb) -> bool:
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return 200 <= h * 360 <= 250 and 0.12 <= l <= 0.30 and s >= 0.35


def colors(text):
    for m in _COLOR.finditer(_COMMENT.sub("", text)):
        if m.group(1):
            hx = m.group(1)
            hx = "".join(c * 2 for c in hx) if len(hx) == 3 else hx
            yield m.group(0), tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))
        else:
            yield m.group(0), tuple(int(m.group(i)) for i in (2, 3, 4))


def test_classifier():
    assert is_navy((11, 42, 91)) and is_navy((14, 42, 90)) and is_navy((31, 58, 95))
    for other in ((0, 56, 184), (20, 23, 28), (17, 24, 39), (29, 78, 216), (55, 65, 81), (255, 255, 255)):
        assert not is_navy(other), other


def test_one_navy_everywhere():
    bad = []
    for f in FILES:
        for lit, rgb in colors(f.read_text(encoding="utf-8")):
            if is_navy(rgb) and rgb != NAVY:
                bad.append(f"{f.relative_to(ROOT)}: {lit}")
    assert not bad, bad


def test_no_band_token():
    css = (ROOT / "apps/api/static/style.css").read_text(encoding="utf-8")
    assert "--band" not in css, "פס ההרשמה - var(--navy)"


if __name__ == "__main__":      # גם מיובא מ-tests/browser/test_navy.py (המסווג)
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("test_single_navy: כל הבדיקות עברו")
