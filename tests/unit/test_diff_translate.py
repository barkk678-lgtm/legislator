"""בודק diff_translate.translate_text_edit: תרגום עריכה חופשית (before/
after של טקסט צומת בודד) להוראת תיקון, או ל"לא נתמך". ראו TASKS.md
משימה 10ב.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from diff_translate import (  # noqa: E402
    SupportedInsertWords,
    SupportedReplaceWords,
    Unsupported,
    translate_text_edit,
)
from node import LegislativeNode  # noqa: E402
from transform import InsertWordsAfter, ReplaceWords, apply  # noqa: E402


def main():
    ok = True

    def check(name, before, after, expected):
        got = translate_text_edit(before, after)
        passed = got == expected
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, "" if passed else f"-> {got!r}")
        if passed and isinstance(expected, SupportedInsertWords):
            # בדיקת עקביות: להטמיע מחדש חייב לשחזר את after במדויק.
            insert_at = before.find(expected.anchor_substring) + len(expected.anchor_substring)
            rebuilt = before[:insert_at] + expected.inserted_text + before[insert_at:]
            consistent = rebuilt == after
            ok = ok and consistent
            print(("OK  " if consistent else "FAIL"), f"  {name}: שחזור מדויק")
        if passed and isinstance(expected, SupportedReplaceWords):
            rebuilt = before.replace(expected.old_phrase, expected.new_phrase, 1)
            consistent = rebuilt == after
            ok = ok and consistent
            print(("OK  " if consistent else "FAIL"), f"  {name}: שחזור מדויק")

    # הוספה טהורה, עוגן מיידי ייחודי מיד.
    check(
        "הוספה פשוטה, עוגן ייחודי",
        "לא ינהל אדם קייטנה.",
        "לא ינהל אדם קייטנה מפוקחת.",
        SupportedInsertWords(anchor_substring="קייטנה", inserted_text=" מפוקחת"),
    )

    # הוספה בתחילת הטקסט (prefix ריק) - אין מילה קודמת לעגן עליה; פער
    # ידוע (דפוס "לפני X יבוא Y", §7.10.2, לא ממומש כ-transform עדיין).
    result_start = translate_text_edit(
        "ילד הוא מי שטרם מלאו לו שמונה עשרה שנים.",
        "כל ילד הוא מי שטרם מלאו לו שמונה עשרה שנים.",
    )
    passed_start = isinstance(result_start, Unsupported)
    ok = ok and passed_start
    print(("OK  " if passed_start else "FAIL"), "הוספה בתחילת הטקסט -> Unsupported",
          "" if passed_start else f"-> {result_start!r}")

    # "קייטנה" חוזרת פעמיים, וגם "מפעיל קייטנה" חוזר פעמיים - רק בהרחבה
    # לשלוש מילים ("אחר מפעיל קייטנה") מגיעים לייחודיות.
    check(
        "הוספה - עוגן מיידי לא ייחודי, נדרש להרחיב",
        "ארגון נוער מפעיל קייטנה בקיץ, וגם ארגון ותיק אחר מפעיל קייטנה.",
        "ארגון נוער מפעיל קייטנה בקיץ, וגם ארגון ותיק אחר מפעיל קייטנה מפוקחת.",
        SupportedInsertWords(anchor_substring="אחר מפעיל קייטנה", inserted_text=" מפוקחת"),
    )

    # החלפה פשוטה.
    check(
        "החלפה פשוטה",
        "דינו מאסר ששה חדשים.",
        "דינו מאסר שנה.",
        SupportedReplaceWords(old_phrase="ששה חדשים", new_phrase="שנה"),
    )

    # אין שינוי בכלל.
    passed_nochange = isinstance(translate_text_edit("זהה", "זהה"), Unsupported)
    ok = ok and passed_nochange
    print(("OK  " if passed_nochange else "FAIL"), "אין שינוי -> Unsupported")

    # פתולוגי: כל הטקסט חוזר על עצמו (משפט זהה פעמיים) - גם הרחבה
    # לכל הטקסט לא מגיעה לייחודיות -> Unsupported, לא ניחוש.
    repeated = "קייטנה טובה. קייטנה טובה."
    result_repeated = translate_text_edit(repeated, "קייטנה טובה מאוד. קייטנה טובה.")
    passed_repeated = isinstance(result_repeated, Unsupported)
    ok = ok and passed_repeated
    print(("OK  " if passed_repeated else "FAIL"), "משפט חוזר על עצמו -> Unsupported",
          "" if passed_repeated else f"-> {result_repeated!r}")

    # אינטגרציה אמיתית: מזינים תוצאה נתמכת ל-transform.apply() בפועל
    # (לא רק בודקים עקביות ידנית) - סוגר את הלולאה מול הוולידציה
    # האמיתית של InsertWordsAfter/ReplaceWords (הופעה יחידה בדיוק וכו').
    node = LegislativeNode(
        id="law/s1/p0", node_type="paragraph", number="", margin_title=None,
        text="לא ינהל אדם קייטנה.",
    )
    law = LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, children=[
            LegislativeNode(id="law/s1", node_type="section", number="1",
                             margin_title="כותרת", text="", children=[node]),
        ],
    )
    result_ins = translate_text_edit("לא ינהל אדם קייטנה.", "לא ינהל אדם קייטנה מפוקחת.")
    assert isinstance(result_ins, SupportedInsertWords)
    after_tree, _ = apply(law, [
        InsertWordsAfter(
            target_id="law/s1/p0",
            anchor_substring=result_ins.anchor_substring,
            inserted_text=result_ins.inserted_text,
        ),
    ])
    got_text = after_tree.children[0].children[0].text
    passed_integration1 = got_text == "לא ינהל אדם קייטנה מפוקחת."
    ok = ok and passed_integration1
    print(("OK  " if passed_integration1 else "FAIL"),
          "אינטגרציה: InsertWordsAfter אמיתי מקבל את התוצאה בלי שגיאה")

    node.text = "דינו מאסר ששה חדשים."
    result_rep = translate_text_edit("דינו מאסר ששה חדשים.", "דינו מאסר שנה.")
    assert isinstance(result_rep, SupportedReplaceWords)
    after_tree2, _ = apply(law, [
        ReplaceWords(
            target_id="law/s1/p0",
            old_phrase=result_rep.old_phrase,
            new_phrase=result_rep.new_phrase,
        ),
    ])
    got_text2 = after_tree2.children[0].children[0].text
    passed_integration2 = got_text2 == "דינו מאסר שנה."
    ok = ok and passed_integration2
    print(("OK  " if passed_integration2 else "FAIL"),
          "אינטגרציה: ReplaceWords אמיתי מקבל את התוצאה בלי שגיאה")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
