"""§4 - סעיפים שנעלמים בגלל מספר כפול (ברק, 23.9.2026: "הפער החמור
ביותר").

**מה היה קורה למשתמש:** `find_sections` בונה `dict[number, node]`,
ולכן מתוך כל קבוצת סעיפים בעלי אותו מספר רק אחד שרד - והצומת ששרד
היה **האחרון** בסדר המסמך. נמדד על הקורפוס: מתוך 78 הכפילויות בגוף
החוק, 45 מהן הצומת השני הוא נוסח עתידי או זמני ("(החל מהמועד
הקובע)", "(הוראת שעה עד יום 31.12.2026)"). כלומר מי שערך את הסעיף
שבתוקף השווה מול נוסח אחר לגמרי, וקיבל **אפס הוראות תיקון בלי שום
הודעה**.

**המבנה כאן נגזר מחוק אמיתי** (חוק אוויר נקי, `law-2000055`: שני
סעיפים 25 תחת "פרק ד סימן ב", הטקסט בצומת-ילד ולא על הסעיף עצמו -
בדיוק כפי שהוא ב-DB). ראו CLAUDE.md: "נתוני בדיקה נגזרים ממבנים
שקיימים בקורפוס".
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))
sys.path.insert(0, str(ROOT / "packages" / "render"))
sys.path.insert(0, str(ROOT / "packages" / "amend"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from engine import amend  # noqa: E402
from node import (  # noqa: E402
    LegislativeNode, duplicate_section_numbers, find_sections, find_sections_all)
from tree_view import node_view  # noqa: E402


def _para(node_id: str, text: str) -> LegislativeNode:
    return LegislativeNode(id=node_id, node_type="paragraph", number="",
                           margin_title=None, text=text, text_raw=text,
                           is_normative=True)


def _section(node_id: str, number: str, margin: str, text: str) -> LegislativeNode:
    return LegislativeNode(id=node_id, node_type="section", number=number,
                           margin_title=margin, text="", text_raw="",
                           is_normative=True, children=[_para(node_id + "/p0", text)])


def _law() -> LegislativeNode:
    siman = LegislativeNode(
        id="L/פרק ד/סימן ב", node_type="siman", number="", margin_title="סימן ב",
        text="", is_normative=True,
        children=[
            _section("L/פרק ד/סימן ב/s25", "25", "תוקף היתר פליטה וחידושו",
                     "תוקף היתר פליטה יהיה שבע שנים."),
            _section("L/פרק ד/סימן ב/s25-2", "25", "תוקף היתר, חידושו וסיום פעילות",
                     "(החל מהמועד הקובע): תוקף היתר יהיה עשר שנים."),
            _section("L/פרק ד/סימן ב/s26", "26", "בקשה לחידוש",
                     "בעל היתר יגיש בקשה."),
        ])
    chapter = LegislativeNode(id="L/פרק ד", node_type="chapter", number="",
                              margin_title="פרק ד", text="", is_normative=True,
                              children=[siman])
    return LegislativeNode(id="L", node_type="law", number="", margin_title=None,
                           text="", is_normative=False,
                           full_title='חוק אוויר נקי, התשס"ח–2008',
                           children=[chapter])


def _sections(tree: LegislativeNode) -> list[LegislativeNode]:
    return tree.children[0].children[0].children


def main() -> int:
    checks = []

    before = _law()

    # ── אף צומת לא נעלם ──────────────────────────────────────────────
    all_sections = find_sections_all(before)
    checks.append(("find_sections_all שומרת את שני הסעיפים 25",
                   [n.id for n in all_sections["25"]]
                   == ["L/פרק ד/סימן ב/s25", "L/פרק ד/סימן ב/s25-2"]))
    checks.append(("duplicate_section_numbers מחזירה רק את הכפול",
                   list(duplicate_section_numbers(before)) == ["25"]))
    checks.append(("חוק בלי כפילויות מחזיר {}",
                   duplicate_section_numbers(
                       _law().children[0].children[0].children[2]) == {}))

    # ── הראשון בסדר המסמך, לא האחרון ────────────────────────────────
    # זה הלב: הצומת השני הוא הנוסח שטרם נכנס לתוקף.
    checks.append(("find_sections מחזירה את הנוסח שבתוקף (הראשון)",
                   find_sections(before)["25"].id == "L/פרק ד/סימן ב/s25"))

    # ── עריכה של סעיף כפול נחסמת במפורש, לא בשקט ────────────────────
    after = _law()
    _sections(after)[0].children[0].text = "תוקף היתר פליטה יהיה חמש שנים."
    try:
        amend(before, after, [], law_footnote_key="k")
        checks.append(("עריכת סעיף כפול -> NotImplementedError", False))
    except NotImplementedError as exc:
        checks.append(("עריכת סעיף כפול -> NotImplementedError",
                       "25" in str(exc) and "חד-משמעי" in str(exc)))

    # והעריכה של הצומת השני נחסמת גם היא - הבעיה היא הכתובת, לא הצומת.
    after_second = _law()
    _sections(after_second)[1].children[0].text = "תוקף היתר יהיה שמונה שנים."
    try:
        amend(before, after_second, [], law_footnote_key="k")
        checks.append(("גם עריכת העותק השני נחסמת", False))
    except NotImplementedError:
        checks.append(("גם עריכת העותק השני נחסמת", True))

    # ── ובלי לחסום את שאר החוק ──────────────────────────────────────
    after_ok = _law()
    _sections(after_ok)[2].children[0].text = "בעל היתר יגיש בקשה בכתב."
    lines = amend(before, after_ok, [], law_footnote_key="k")
    checks.append(("עריכה בסעיף לא-כפול באותו חוק ממשיכה לעבוד",
                   len(lines) == 1 and lines[0].side_heading == "תיקון סעיף 26"))

    # ── והמשתמש רואה את זה לפני שהוא לוחץ ───────────────────────────
    view_sections = node_view(before)["children"][0]["children"][0]["children"]
    checks.append(("שני העותקים מסומנים לא-ניתנים-לעריכה",
                   [s["editable"] for s in view_sections] == [False, False, True]))
    checks.append(("ועם דגל הסיבה, לא רק editable",
                   [s["ambiguous_number"] for s in view_sections] == [True, True, False]))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
