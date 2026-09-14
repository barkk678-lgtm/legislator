"""בדיקות ל-ingest_checks.py. ראו תוכנית ה-ingest ב-docs/strategy/decisions.md.

penal.wikitext (חוק העונשין) - מקרה הזהב לחלק/פרק/סימן (משימה 7).
עד 2026-09-14 נכשל ב-check_no_unknown_templates על {{ח:קטע1}}/{{ח:קטע3}}
(חלק/סימן) - תוקן (ראו wikitext_parser._CONTAINER_TEMPLATES). עדיין
נכשל על פער *אחר*, לא קשור: {{ח:מבוא}}/תבניות תיוג (`חוקי עונשין`) -
זה תיעוד של פער ידוע, לא מקרה סינתטי.
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

    # מאבק בארגוני פשיעה: תוקן (2026-09-13). {{ח:סעיף}} ב-
    # wikitext_parser.py היה בונה id מ-law_id בלבד, לא מ-parent_node.id -
    # סעיף 1 בחוק עצמו וסעיף 1 בכל אחת משתי התוספות (numbering_space
    # ="schedule", שמתחילה למספר מחדש) קיבלו בדיוק אותו id. תוקן
    # (id יחסי ל-parent_node, כמו subsection/paragraph כבר עשו) -
    # run_sanity_checks על מאבק חייב להיות נקי עכשיו.
    maavak_text, maavak_tree = _load("maavak-birgunei-plisha", "maavak-2003")
    checks.append(("מאבק: run_sanity_checks נקי (אחרי תיקון ה-id)", run_sanity_checks(maavak_text, maavak_tree) == []))

    # חלק/פרק/סימן (קטע1/2/3) - תוקן 2026-09-14 (ראו TASKS.md משימה 7).
    # עונשין: 4 part, 20 chapter, 75 siman, 673 section - כולם ללא כפילות id.
    penal_text, penal_tree = _load("penal", "penal-1977")
    checks.append(("עונשין: check_unique_ids נקי אחרי תיקון חלק/פרק/סימן", check_unique_ids(penal_tree) == []))

    def _count_type(node, node_type):
        total = 1 if node.node_type == node_type else 0
        for child in node.children:
            total += _count_type(child, node_type)
        return total

    checks.append(("עונשין: 4 צמתי part", _count_type(penal_tree, "part") == 4))
    checks.append(("עונשין: 20 צמתי chapter", _count_type(penal_tree, "chapter") == 20))
    checks.append(("עונשין: 75 צמתי siman", _count_type(penal_tree, "siman") == 75))

    # פער *אחר*, לא קשור לחלק/פרק/סימן, עדיין קיים בכוונה: ח:מבוא +
    # תבניות תיוג (חוקי עונשין) - ראו TASKS.md משימה 7 להמשך.
    penal_problems = check_no_unknown_templates(penal_text)
    checks.append(("עונשין: נכשל רק על ח:מבוא/תיוג (לא קטע1/קטע3 יותר)", len(penal_problems) == 1))
    checks.append(("עונשין: קטע1/קטע3 לא מופיעים יותר בבעיה", "ח:קטע1" not in penal_problems[0] and "ח:קטע3" not in penal_problems[0]))
    checks.append(("עונשין: הבעיה מזהה את ח:מבוא", "ח:מבוא" in penal_problems[0]))

    # ויקיפדיה/ח:מאגר2 - נוספו ל-allowlist 2026-09-14 אחרי בדיקת תוכן
    # אמיתי (ראו TASKS.md משימה 7): שתיהן עיטוריות בלבד, אין נוסח.
    decorative_text = (
        "{{ח:כותרת|חוק לדוגמה}}\n"
        "{{ויקיפדיה|חוק לדוגמה}}\n"
        "{{ח:מאגר2|1234567}}\n"
        "{{ח:סעיף|1||}}\n"
        "{{ח:ת|}} תוכן כלשהו.\n"
    )
    checks.append(
        ("ויקיפדיה/ח:מאגר2: לא נחשבות תבניות לא-מוכרות", check_no_unknown_templates(decorative_text) == [])
    )

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
