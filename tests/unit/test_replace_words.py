"""בדיקות ל-ReplaceWords (transform.py) ול-_validate_replacement (engine.py).
ראו TASKS.md משימה 4א.

עיקרון מרכזי הנבדק כאן: הביטויים הישן/חדש הם בחירה מפורשת של
ReplaceWords, מועברים ל-engine.amend() כ-ReplacementAnnotation נפרדת -
לא מוטבעים כסמן טקסטואלי בתוך .text (ראו tests/unit/test_no_marker_leak.py
למחסום המבני שאוכף את זה). _validate_replacement רק מוודאת עקביות בין
האנוטציה לבין before/after בפועל - לא גוזרת אותה. אותו עיקרון-אי-ניחוש
נבדק גם ב-InsertWordsAfter (anchor_substring חייב להופיע פעם אחת בדיוק).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from transform import InsertWordsAfter, ReplaceWords, ReplacementAnnotation, apply  # noqa: E402
from engine import _validate_replacement  # noqa: E402


def _tree(text: str) -> LegislativeNode:
    leaf = LegislativeNode(
        id="law/s5/p0", node_type="paragraph", number="", margin_title=None, text=text
    )
    section = LegislativeNode(
        id="law/s5", node_type="section", number="5", margin_title="עונשין", text="",
        children=[leaf],
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        children=[section], is_normative=False,
    )


BEFORE_TEXT = "המנהל קייטנה בניגוד להוראות סעיפים 2 או 4, דינו – מאסר ששה חדשים."
AFTER_TEXT = "המנהל קייטנה בניגוד להוראות סעיפים 2 או 4, דינו – מאסר שנה."


def main():
    checks = []

    before = _tree(BEFORE_TEXT)
    after, annotations = apply(
        before,
        [ReplaceWords(target_id="law/s5/p0", old_phrase="מאסר ששה חדשים", new_phrase="מאסר שנה")],
    )
    leaf_after = after.children[0].children[0]
    checks.append(("after.text נקי לגמרי, בלי שום סמן", leaf_after.text == AFTER_TEXT))
    checks.append(("before לא השתנה (deepcopy)", before.children[0].children[0].text == BEFORE_TEXT))

    checks.append(("apply מחזירה בדיוק אנוטציה אחת", len(annotations) == 1))
    replacement = annotations[0]
    checks.append(("האנוטציה מסוג ReplacementAnnotation", isinstance(replacement, ReplacementAnnotation)))
    checks.append(("node_id נכון", replacement.node_id == "law/s5/p0"))
    checks.append(("old_phrase נכון", replacement.old_phrase == "מאסר ששה חדשים"))
    checks.append(("new_phrase נכון", replacement.new_phrase == "מאסר שנה"))

    # _validate_replacement לא אמורה לזרוק על קלט עקבי
    try:
        _validate_replacement(BEFORE_TEXT, AFTER_TEXT, replacement)
        checks.append(("_validate_replacement: קלט עקבי -> לא זורקת", True))
    except ValueError:
        checks.append(("_validate_replacement: קלט עקבי -> לא זורקת", False))

    # אפס הופעות
    try:
        apply(before, [ReplaceWords(target_id="law/s5/p0", old_phrase="לא קיים", new_phrase="x")])
        checks.append(("ReplaceWords: אפס הופעות -> שגיאה", False))
    except ValueError:
        checks.append(("ReplaceWords: אפס הופעות -> שגיאה", True))

    # יותר מהופעה אחת
    dup_before = _tree("מאסר שנה או מאסר שנה, לפי העניין.")
    try:
        apply(
            dup_before,
            [ReplaceWords(target_id="law/s5/p0", old_phrase="מאסר שנה", new_phrase="מאסר שנתיים")],
        )
        checks.append(("ReplaceWords: הופעה כפולה -> שגיאה (לא ניחוש)", False))
    except ValueError:
        checks.append(("ReplaceWords: הופעה כפולה -> שגיאה (לא ניחוש)", True))

    # _validate_replacement: חוסר עקביות בין האנוטציה לבין before בפועל
    try:
        _validate_replacement("טקסט לפני שלא תואם", AFTER_TEXT, replacement)
        checks.append(("_validate_replacement: חוסר עקביות -> שגיאה", False))
    except ValueError:
        checks.append(("_validate_replacement: חוסר עקביות -> שגיאה", True))

    # InsertWordsAfter: אותו עיקרון-אי-ניחוש
    ins_before = _tree("לא ינהל אדם קייטנה אלא אם כן יש בידו רשיון.")
    try:
        apply(
            ins_before,
            [InsertWordsAfter(target_id="law/s5/p0", anchor_substring="לא קיים", inserted_text="x")],
        )
        checks.append(("InsertWordsAfter: אפס הופעות -> שגיאה", False))
    except ValueError:
        checks.append(("InsertWordsAfter: אפס הופעות -> שגיאה", True))

    dup_ins_before = _tree("אדם ואדם אחר.")
    try:
        apply(
            dup_ins_before,
            [InsertWordsAfter(target_id="law/s5/p0", anchor_substring="אדם", inserted_text="X")],
        )
        checks.append(("InsertWordsAfter: הופעה כפולה -> שגיאה (לא ניחוש)", False))
    except ValueError:
        checks.append(("InsertWordsAfter: הופעה כפולה -> שגיאה (לא ניחוש)", True))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
