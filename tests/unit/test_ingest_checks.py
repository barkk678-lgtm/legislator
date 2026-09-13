"""בדיקות ל-ingest_checks.py. ראו תוכנית ה-ingest ב-docs/strategy/decisions.md.

המקרה המרכזי: penal.wikitext (חוק העונשין) חייב להיכשל ב-
check_no_unknown_templates - זה בדיוק המצב האמיתי, המתועד ב-TASKS.md
משימה 7, שבו wikitext_parser.py עדיין לא מטפל ב-{{ח:קטע1}}/{{ח:קטע3}}.
לא מקרה סינתטי - זה הפער האמיתי שהבדיקה הזו נכתבה כדי לתפוס.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from ingest_checks import (  # noqa: E402
    check_has_normative_content,
    check_no_unknown_templates,
    check_section_count,
    check_unique_ids,
    run_sanity_checks,
)
from node import LegislativeNode  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikitext"


def _load(slug: str, law_id: str) -> tuple[str, LegislativeNode]:
    text = (FIXTURES / f"{slug}.wikitext").read_text(encoding="utf-8")
    return text, parse_wikitext(text, law_id=law_id)


def main():
    checks = []

    kaytanot_text, kaytanot_tree = _load("kaytanot", "kaytanot-1990")
    checks.append(
        ("קייטנות: אין תבניות לא מוכרות", check_no_unknown_templates(kaytanot_text) == [])
    )
    checks.append(
        ("קייטנות: ספירת סעיפים תואמת", check_section_count(kaytanot_text, kaytanot_tree) == [])
    )
    checks.append(
        ("קייטנות: יש תוכן נורמטיבי", check_has_normative_content(kaytanot_tree) == [])
    )
    checks.append(("קייטנות: run_sanity_checks נקי", run_sanity_checks(kaytanot_text, kaytanot_tree) == []))

    # מאבק בארגוני פשיעה: פער אמיתי, לא סינתטי - התגלה תוך כדי ingest
    # אמיתי (2026-09-13, לפני שהורץ ל-DB בפועל). {{ח:סעיף}} ב-
    # wikitext_parser.py בונה id מ-law_id בלבד, לא מ-parent_node.id -
    # סעיף 1 בחוק עצמו וסעיף 1 בכל אחת משתי התוספות (numbering_space
    # ="schedule", שמתחילה למספר מחדש) מקבלים בדיוק אותו id. עדיין
    # לא תוקן - ממתין להחלטה (ראו TASKS.md/decisions.md). הבדיקה כאן
    # מתעדת את המצב הנוכחי (עם הבאג), לא מנחשת תיקון.
    maavak_text, maavak_tree = _load("maavak-birgunei-plisha", "maavak-2003")
    maavak_problems = run_sanity_checks(maavak_text, maavak_tree)
    checks.append(("מאבק: run_sanity_checks תופס את התנגשות ה-id (עדיין לא תוקן)", len(maavak_problems) == 1))
    checks.append(
        (
            'מאבק: הבעיה מזהה בדיוק את "maavak-2003/s1" ו-"maavak-2003/s2" ככפולים',
            maavak_problems
            and "maavak-2003/s1" in maavak_problems[0]
            and "maavak-2003/s2" in maavak_problems[0],
        )
    )

    # המקרה המרכזי - פער אמיתי, לא סינתטי (ראו TASKS.md משימה 7).
    penal_text, penal_tree = _load("penal", "penal-1977")
    penal_problems = check_no_unknown_templates(penal_text)
    checks.append(("עונשין: נכשל על תבניות לא מוכרות (קטע1/קטע3/...)", len(penal_problems) == 1))
    checks.append(("עונשין: הבעיה מזהה את קטע1", "ח:קטע1" in penal_problems[0]))
    checks.append(("עונשין: הבעיה מזהה את קטע3", "ח:קטע3" in penal_problems[0]))

    # מקרים סינתטיים לבדיקות הנוספות - עץ מזויף במכוון.
    empty_root = LegislativeNode(
        id="x", node_type="law", number="", margin_title=None, text="", is_normative=False
    )
    checks.append(
        ("עץ בלי אף צומת נורמטיבי -> כשל", check_has_normative_content(empty_root) == [
            "העץ שנפרסר לא מכיל אף צומת נורמטיבי אחד (is_normative=True)"
        ])
    )

    normative_child = LegislativeNode(
        id="x/1", node_type="section", number="1", margin_title=None, text="טקסט", is_normative=True
    )
    root_with_content = LegislativeNode(
        id="x",
        node_type="law",
        number="",
        margin_title=None,
        text="",
        is_normative=False,
        children=[normative_child],
    )
    checks.append(("עץ עם תוכן נורמטיבי -> תקין", check_has_normative_content(root_with_content) == []))

    checks.append(("check_unique_ids: עץ בלי כפילויות -> תקין", check_unique_ids(root_with_content) == []))

    duplicate_tree = LegislativeNode(
        id="x",
        node_type="law",
        number="",
        margin_title=None,
        text="",
        is_normative=False,
        children=[
            LegislativeNode(id="x/s1", node_type="section", number="1", margin_title=None, text="", is_normative=True),
            LegislativeNode(id="x/s1", node_type="section", number="1", margin_title=None, text="", is_normative=True),
        ],
    )
    checks.append(
        ("check_unique_ids: תופס כפילות סינתטית", check_unique_ids(duplicate_tree) == ["id כפול בעץ: x/s1"])
    )

    # סעיף אחד "נבלע" - וויקיטקסט גולמי טוען 2 סעיפים, העץ מכיל רק 1.
    fake_wikitext = "{{ח:סעיף|1|א}}\n{{ח:סעיף|2|ב}}\n"
    checks.append(
        (
            "אי-התאמה בספירת סעיפים -> כשל",
            len(check_section_count(fake_wikitext, root_with_content)) == 1,
        )
    )

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
