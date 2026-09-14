"""בדיקות ל-ingest_checks.py. ראו תוכנית ה-ingest ב-docs/strategy/decisions.md.

penal.wikitext (חוק העונשין) - מקרה הזהב לחלק/פרק/סימן (משימה 7).
עד 2026-09-14 נכשל ב-check_no_unknown_templates על {{ח:קטע1}}/{{ח:קטע3}}
(חלק/סימן) - תוקן (ראו wikitext_parser._CONTAINER_TEMPLATES). {{ח:מבוא}}
תוקן גם הוא (נוסף ל-_KNOWN_BENIGN_SKIP_TEMPLATES). עדיין נכשל על פער
*אחר*, לא קשור: תבנית תיוג (`חוקי עונשין`) - עדיין לא ב-allowlist
(ראו TASKS.md משימה 7, סעיף allowlist ממתין לאישור מרוכז) - זה תיעוד
של פער ידוע, לא מקרה סינתטי.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from ingest_checks import (  # noqa: E402
    check_has_normative_content,
    check_no_unconsumed_content,
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

    # allowlist מרוכז אושר (ברק, 2026-09-14, כולל חוקי עונשין) - עונשין
    # נקי לגמרי עכשיו. ראו TASKS.md משימה 7 להיסטוריה (קטע1/קטע3/מבוא/
    # תבניות תיוג - כולם תוקנו בזה אחר זה).
    checks.append(("עונשין: check_no_unknown_templates נקי לגמרי", check_no_unknown_templates(penal_text) == []))

    # check_no_unconsumed_content (2026-09-14) - הכיוון ההפוך: "מה אבד",
    # לא "מה נוצר". עונשין חושף בדיוק את התרחיש שהיא נועדה לתפוס: 327
    # שורות <table>/<tr>/<td> גולמיות ב-"לוח השוואה" (מספור ישן מול חדש)
    # שנבלעות בשקט לגמרי כי אף שורה בהן לא מתחילה ב-{{ - ראו TASKS.md
    # משימה 7. run_sanity_checks לכן נכשל על עונשין שוב - נכון, לא רגרסיה.
    unconsumed = check_no_unconsumed_content(penal_text)
    checks.append(("עונשין: check_no_unconsumed_content תופס את לוח ההשוואה", len(unconsumed) == 1 and "327 שורות" in unconsumed[0]))
    checks.append(("עונשין: run_sanity_checks נכשל רק על unconsumed (לא על שום דבר אחר)", run_sanity_checks(penal_text, penal_tree) == unconsumed))

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

    # check_no_unconsumed_content (2026-09-14) - "מה אבד", לא "מה נוצר".
    orphaned_table_text = (
        "{{ח:כותרת|חוק לדוגמה}}\n"
        "{{ח:סעיף|1||}}\n"
        "{{ח:ת}} תוכן תקין.\n"
        "\n"
        '<table border="0">\n'
        "<tr><td>נתון שאבד בשקט</td></tr>\n"
        "</table>\n"
    )
    checks.append(("unconsumed: תופס <table> יתום", len(check_no_unconsumed_content(orphaned_table_text)) == 1))

    toc_text = (
        "{{ח:כותרת|חוק לדוגמה}}\n"
        '{{ח:קטע2||תוכן עניינים}}\n\n'
        '<div class="law-toc">\n'
        '<div class="law-toc-2">{{ח:פנימי|פרק א|פרק א}}</div>\n'
        "</div>\n\n"
        "{{ח:סעיף|1||}}\n"
        "{{ח:ת}} תוכן תקין.\n"
    )
    checks.append(("unconsumed: תוכן עניינים אוטומטי (law-toc) לא נתפס", check_no_unconsumed_content(toc_text) == []))

    signatures_text = (
        "{{ח:כותרת|חוק לדוגמה}}\n"
        "{{ח:חתימות|התקבל בכנסת.}}\n"
        "* '''פלוני אלמוני'''<br>ראש הממשלה\n"
        "{{ח:סוגר}}\n"
        "{{ח:סעיף|1||}}\n"
        "{{ח:ת}} תוכן תקין.\n"
    )
    checks.append(("unconsumed: חתימות בתוך הקופסה לא נתפסות", check_no_unconsumed_content(signatures_text) == []))

    category_text = (
        "{{ח:כותרת|חוק לדוגמה}}\n"
        "{{ח:סעיף|1||}}\n"
        "{{ח:ת}} תוכן תקין.\n"
        "[[קטגוריה:בוט חוקים]]\n"
    )
    checks.append(("unconsumed: שורת קטגוריה לא נתפסת", check_no_unconsumed_content(category_text) == []))

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
