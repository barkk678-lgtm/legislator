#!/usr/bin/env python3
"""מדידת צורת הכתובת בהוראות תיקון מקוננות, מול 40 ההצעות האמיתיות.

מייצרת כל מספר שמופיע ב-docs/drafting-rules.md §8.7. הרצה:
    python3 docs/measurements/nested-locator-2026-09-22/measure.py
מתוך שורש המאגר. אופליין לגמרי - קורא רק את tests/fixtures/real-bills/.
"""
import glob
import re
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BILLS = "tests/fixtures/real-bills/*.docx"

# "כתובת ההוראה" היא "בסעיף" בתחילת השורה (אחרי מספר פריט אופציונלי) -
# להבדיל מ"בסעיף" באמצע שורה, שהוא הפניה פנימית בתוך נוסח החוק המוצע
# ולא כתובת של הוראת תיקון. ההבחנה הזו מכריעה: בלעדיה נספרות גם
# הפניות כמו "כאמור בסעיף 7(א3)" ומספרי הצורות מנופחים פי חמישה.
HEAD = r"^\s*(?:\(\d+\)|\([א-ת]\)|\d+[א-ת]?\d*\.)?\s*"
SECTION = r"\d+[א-ת]?\d*"

CONTAINER = re.compile(HEAD + rf"בסעיף\s+{SECTION}\s*\(")            # בסעיף 17(א), ...
LONG_FORM = re.compile(HEAD + rf"בסעיף\s+{SECTION}[^)\n]{{0,60}}?בסעיף\s+קטן")
OPENER = re.compile(rf"^\s*(?:\(\d+\)|\d+\.)?\s*בסעיף\s+\S+(?:\s+לחוק\s+העיקרי)?\s*[–\-—]\s*$")
SUB_ITEM = re.compile(r"^\s*\((?:\d+|[א-ת])\)\s*\S")
NEXT_ADDRESS = re.compile(HEAD + rf"בסעיף\s+{SECTION}")

AFTER_WORDS = re.compile(r'אחרי\s+המיל(?:ה|ים)\s*["״”″]')
AFTER_BARE = re.compile(r'אחרי\s+["״”″]')
INSTEAD_WORDS = re.compile(r'במקום\s+המיל(?:ה|ים)\s*["״”″]')
INSTEAD_BARE = re.compile(r'במקום\s+["״”″]')


def paragraphs(path: str) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    out = []
    for para in root.iter(W + "p"):
        text = "".join(t.text or "" for t in para.iter(W + "t")).strip()
        if text:
            out.append(text)
    return out


def main() -> None:
    files = sorted(glob.glob(BILLS))
    per_file = {f.split("/")[-1][:-5]: paragraphs(f) for f in files}
    lines = [(name, line) for name, ps in per_file.items() for line in ps]
    print(f"הצעות: {len(files)}   פסקאות: {len(lines)}")

    container = [(n, l) for n, l in lines if CONTAINER.match(l)]
    long_form = [(n, l) for n, l in lines if LONG_FORM.match(l)]
    print(f'צורה קצרה "בסעיף N(x), ...": {len(container)} '
          f"ב-{len(set(n for n, _ in container))} הצעות")
    print(f'צורה ארוכה "בסעיף N, בסעיף קטן (x)": {len(long_form)}')
    for name, line in container:
        print(f"    [{name}] {line[:150]}")

    # ספירה אוטומטית של תת-הסעיפים אינה אמינה כאן: בתוך הבלוק המצוטט
    # של הוספה יש שורות שנפתחות בתווית משלהן ("(א1)תוכנית הלימודים..."),
    # והן נוסח החוק החדש - לא תת-הוראות. לכן מודפסות השורות כלשונן
    # והספירה נעשתה בעין על כל שש שורות הפתיח: לכולן שתי תת-הוראות ומעלה.
    print("\nשורות פתיח היררכיות והשורות שאחריהן (ספירה בעין):")
    for name, ps in per_file.items():
        for i, line in enumerate(ps):
            if not OPENER.match(line):
                continue
            print(f"\n    === [{name}] {line}")
            for nxt in ps[i + 1:i + 9]:
                if OPENER.match(nxt) or NEXT_ADDRESS.match(nxt):
                    break
                print(f"        {nxt[:130]}")

    print("\nציון מילים מצוטטות:")
    for label, rx in (('אחרי המילים "..."', AFTER_WORDS), ('אחרי "..."', AFTER_BARE),
                      ('במקום המילים "..."', INSTEAD_WORDS), ('במקום "..."', INSTEAD_BARE)):
        print(f"    {label:<22} {sum(1 for _, l in lines if rx.search(l))}")


if __name__ == "__main__":
    main()
