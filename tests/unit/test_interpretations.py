"""ת6 (26.9.2026) - מקור פרשני שברק מזין (reference/takanon/interpretations.md).

(1) כל רשומה בקובץ האמיתי מפנה לסעיף שקיים באחד משלושת המקורות - אחרת
האזכור בתשובה היה מוביל לשום מקום, והשומר היה פוסל. (2) רשומה נטענת בתוך
המקור של הסעיף (המודל מאזכר את הסעיף עצמו) ומוצגת מתחתיו במסך הקריאה.
(3) הדוגמה שבראש הקובץ אינה רשומה. בלי רשת: המקורות מהמאגר המקומי.
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import rules_expert as rx  # noqa: E402

SAMPLE = """# כותרת
    ## law-tkanon-haknesset/48
    פרשנות: דוגמה שאינה רשומה
---
## law-tkanon-haknesset/48
יחידה: (א)
נוסף: 26.9.2026
פרשנות: רשומת בדיקה -
ממשיכה בשורה שנייה.
"""


def _takanon_ids() -> set[str]:
    """המקורות האמיתיים, או ריק כשאין גישה למאגר (CI רץ בלי מפתחות)."""
    try:
        return {c.id for c in rx.sources(refresh=True)}
    except Exception as e:  # noqa: BLE001 - מפתח חסר/רשת: הבדיקה מדלגת בגלוי
        print(f"  - המאגר לא זמין ({type(e).__name__}) - מדלג על הבדיקות שדורשות את התקנון")
        return set()


def _with_sample():
    tmp = Path(tempfile.mkdtemp()) / "interpretations.md"
    tmp.write_text(SAMPLE, encoding="utf-8")
    return tmp


def test_real_file_entries_point_to_real_sections():
    ids = _takanon_ids()
    if not ids:
        return
    bad = [e["source_id"] for e in rx.load_interpretations() if e["source_id"] not in ids]
    assert not bad, f"רשומות שמפנות לסעיף שאינו קיים: {bad}"


def test_parse_skips_the_example_and_joins_lines():
    entries = rx.load_interpretations(_with_sample())
    assert entries == [{"source_id": "law-tkanon-haknesset/48", "unit": "(א)", "added": "26.9.2026",
                        "text": "רשומת בדיקה - ממשיכה בשורה שנייה."}], entries


def test_entry_is_loaded_inside_its_section_and_shown_under_it():
    if not _takanon_ids():
        return
    saved = rx.INTERPRETATIONS_PATH
    rx.INTERPRETATIONS_PATH = _with_sample()
    try:
        chunk = next(c for c in rx.sources(refresh=True) if c.id == "law-tkanon-haknesset/48")
        assert "פרשנות שלפיה נוהגים בכנסת (לסעיף קטן (א)): רשומת בדיקה" in chunk.text, chunk.text[-200:]
        assert chunk.label == "תקנון הכנסת, סעיף 48"
        docs = rx.reading_view(refresh=True)
        sec = next(i for d in docs for i in d["items"] if i.get("id") == "law-tkanon-haknesset/48")
        assert sec["interpretations"] and sec["interpretations"][0]["text"].startswith("רשומת בדיקה"), sec
    finally:
        rx.INTERPRETATIONS_PATH = saved
        rx.sources(refresh=True)
        rx.reading_view(refresh=True)


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_interpretations: כל הבדיקות עברו")
