"""מחסום מבני: .text של כל צומת, בכל עץ (כולל עצי "אחרי" שנבנו על ידי
transform.apply), חייב להכיל נוסח חוק בלבד - אף פעם לא תחביר סימון
פנימי (⟦...⟧). ראו TASKS.md משימה 4א (המשך): לפני התיקון הזה, apply()
הטביעה מידע "בתהליך" (ביטוי ישן/חדש שהוחלף, מיקום הערת שוליים) ישירות
בתוך .text כסמן טקסטואלי - עבד היום, אבל בלי שום מחסום שמונע מקוד
עתידי (למשל משימה 11: הכיוון ההפוך, הצעת חוק ← נוסח משולב) לקרוא את
עץ ה"אחרי" ישירות ולהציג את הסמן הגולמי כאילו הוא נוסח חוק אמיתי.
המידע עבר לערוץ אנוטציות נפרד (ReplacementAnnotation/FootnoteAnnotation,
ראו transform.py) בדיוק כדי לסגור את זה. הטסט הזה הוא המחסום שנשאר
לתמיד - הוא זה שהיה תופס את התקלה אילו חזרה.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "golden"))

from node import LegislativeNode  # noqa: E402

_FORBIDDEN = ("⟦", "⟧")


def _find_marker_leaks(root: LegislativeNode) -> list[str]:
    """סורקת רקורסיבית את .text של כל צומת בעץ ומחזירה רשימת node_id
    שבהם נמצא תו מהתחביר האסור. רשימה ריקה = העץ נקי לגמרי."""
    leaks = []

    def walk(node: LegislativeNode) -> None:
        if any(ch in node.text for ch in _FORBIDDEN):
            leaks.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return leaks


def main():
    checks = []

    # מוודא שהבודק עצמו לא ריק מתוכן: עץ מלאכותי עם "דליפה" מדומה
    # (בדיוק כמו שהמנגנון הישן היה מטביע) חייב להיתפס.
    leaky = LegislativeNode(
        id="fake/leaky",
        node_type="paragraph",
        number="",
        margin_title=None,
        text="טקסט עם ⟦replaced-from:x⟧y⟦/replaced⟧ שנשאר בטעות",
    )
    checks.append(("הבודק תופס דליפה מלאכותית", _find_marker_leaks(leaky) == ["fake/leaky"]))

    clean = LegislativeNode(
        id="fake/clean", node_type="paragraph", number="", margin_title=None, text="נוסח נקי לגמרי."
    )
    checks.append(("הבודק לא מתריע שווא על טקסט נקי", _find_marker_leaks(clean) == []))

    # שני עצי ה"אחרי" האמיתיים מהמקרים הזהב - שניהם עברו ReplaceWords
    # ו/או InsertAfter עם footnotes, ושניהם חייבים לצאת נקיים לגמרי.
    from test_kaytanot import load_before as load_kaytanot, build_after as build_kaytanot  # noqa: E402
    from test_kaytanot_section5 import build_after as build_section5  # noqa: E402

    kaytanot_before = load_kaytanot()
    kaytanot_after, _ = build_kaytanot(kaytanot_before)
    checks.append(("עץ 'אחרי' של קייטנות (משימה 4) נקי מסמנים", _find_marker_leaks(kaytanot_after) == []))

    section5_after, _ = build_section5(kaytanot_before)
    checks.append(("עץ 'אחרי' של סעיף 5 (משימה 4א) נקי מסמנים", _find_marker_leaks(section5_after) == []))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
