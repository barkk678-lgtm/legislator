"""בדיקות ל-ReplaceWords (transform.py) ול-_diff_replace (engine.py).
ראו TASKS.md משימה 4א.

עיקרון מרכזי הנבדק כאן: הביטויים הישן/חדש הם בחירה מפורשת של
ReplaceWords, לא נגזרים מדיף טקסטואלי - _diff_replace רק מוודאת
עקביות בין הסמן הפנימי (⟦replaced-from:...⟧...⟦/replaced⟧) לבין
before/after בפועל. אותו עיקרון-אי-ניחוש נבדק גם ב-InsertWordsAfter
(anchor_substring חייב להופיע פעם אחת בדיוק).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from transform import InsertWordsAfter, ReplaceWords, apply  # noqa: E402
from engine import _diff_replace  # noqa: E402


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
    after = apply(
        before,
        [ReplaceWords(target_id="law/s5/p0", old_phrase="מאסר ששה חדשים", new_phrase="מאסר שנה")],
    )
    leaf_after = after.children[0].children[0]
    checks.append(
        (
            "ReplaceWords מטביע סמן replaced-from עם שני הביטויים",
            leaf_after.text
            == "המנהל קייטנה בניגוד להוראות סעיפים 2 או 4, דינו – "
            "⟦replaced-from:מאסר ששה חדשים⟧מאסר שנה⟦/replaced⟧.",
        )
    )
    checks.append(("before לא השתנה (deepcopy)", before.children[0].children[0].text == BEFORE_TEXT))

    old, new = _diff_replace(BEFORE_TEXT, leaf_after.text)
    checks.append(("_diff_replace שולפת old_phrase נכון", old == "מאסר ששה חדשים"))
    checks.append(("_diff_replace שולפת new_phrase נכון", new == "מאסר שנה"))

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

    # _diff_replace: חוסר עקביות בין הסמן לבין before בפועל
    try:
        _diff_replace("טקסט לפני שלא תואם", leaf_after.text)
        checks.append(("_diff_replace: חוסר עקביות -> שגיאה", False))
    except ValueError:
        checks.append(("_diff_replace: חוסר עקביות -> שגיאה", True))

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
