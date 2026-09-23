"""§4 + §4א - סעיף שמספרו אינו ייחודי: מתי זו דו-משמעות ומתי לא.

**מה היה קורה למשתמש:** `find_sections` בנתה `dict[number, node]`,
ולכן מתוך כל קבוצת סעיפים בעלי אותו מספר רק אחד שרד - והוא היה
**האחרון** בסדר המסמך. מי שערך את הסעיף שבתוקף השווה מול נוסח אחר,
וקיבל **אפס הוראות תיקון בלי שום הודעה**.

**ולא כל כפילות היא דו-משמעות** (ברק, 23.9.2026). כשהמקור מסמן
איזו הוראה חלה ממועד קובע, נשארת בדיוק הוראה מבצעית אחת - וזו
כתובת חד-משמעית. נמדד על הקורפוס: 44 מתוך 78 הכפילויות בגוף החוק
הן מהסוג הזה (88 סעיפים ב-24 חוקים).

**דיוק במונחים:** הוראה שתחולתה ממועד קובע היא **בתוקף**. היא
נחקקה, ורק החלתה מתחילה במועד. אסור לסמן אותה כ"לא בתוקף" בשום
מקום - לא בקוד ולא בממשק.

**כל הסימונים כאן צוטטו מהקורפוס** ולא הומצאו: `(החל מהמועד
הקובע)` ו-`(החל מיום 26.1.2027)`, `(ספרור שגוי במקור)`, `(פקע)`.
המבנה נגזר מחוק אוויר נקי (`law-2000055`): שני סעיפים 25 תחת
"פרק ד סימן ב", הטקסט בצומת-ילד ולא על הסעיף עצמו. ראו CLAUDE.md,
"נתוני בדיקה נגזרים ממבנים שקיימים בקורפוס".
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
    LegislativeNode, deferred_sections, duplicate_section_numbers,
    find_sections, find_sections_all, section_source_note)
from tree_view import node_view  # noqa: E402


def _para(node_id: str, text: str) -> LegislativeNode:
    return LegislativeNode(id=node_id, node_type="paragraph", number="",
                           margin_title=None, text=text, text_raw=text,
                           is_normative=True)


def _section(node_id: str, number: str, margin: str, text: str) -> LegislativeNode:
    return LegislativeNode(id=node_id, node_type="section", number=number,
                           margin_title=margin, text="", text_raw="",
                           is_normative=True, children=[_para(node_id + "/p0", text)])


def _law(second_text: str) -> LegislativeNode:
    """שני סעיפים 25 ועוד סעיף 26 רגיל. `second_text` הוא הפתיח של
    העותק השני - הוא שקובע לאיזו משפחה הכפילות שייכת."""
    siman = LegislativeNode(
        id="L/פרק ד/סימן ב", node_type="siman", number="", margin_title="סימן ב",
        text="", is_normative=True,
        children=[
            _section("L/פרק ד/סימן ב/s25", "25", "תוקף היתר פליטה וחידושו",
                     "תוקף היתר פליטה יהיה שבע שנים."),
            _section("L/פרק ד/סימן ב/s25-2", "25", "תוקף היתר, חידושו וסיום פעילות",
                     second_text),
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


DEFERRED = "(החל מהמועד הקובע): תוקף היתר יהיה עשר שנים."
UNMARKED = "תוקף היתר יהיה עשר שנים."
NUMBERING_ERROR = "(ספרור שגוי במקור): תוקף היתר יהיה עשר שנים."
EXPIRED = "(פקע)."


def _sections(tree: LegislativeNode) -> list[LegislativeNode]:
    return tree.children[0].children[0].children


def _view_sections(tree: LegislativeNode) -> list[dict]:
    return node_view(tree)["children"][0]["children"][0]["children"]


def main() -> int:
    checks = []

    # ── אף צומת לא נעלם ──────────────────────────────────────────────
    before = _law(DEFERRED)
    checks.append(("find_sections_all שומרת את שני הסעיפים 25",
                   [n.id for n in find_sections_all(before)["25"]]
                   == ["L/פרק ד/סימן ב/s25", "L/פרק ד/סימן ב/s25-2"]))

    # ── הסימון נקרא מהמקור כלשונו ───────────────────────────────────
    checks.append(("הסימון מזוהה ומוחזר כלשונו",
                   section_source_note(_sections(before)[1]) == ("deferred", "החל מהמועד הקובע")))
    checks.append(("סעיף בלי סימון מחזיר None",
                   section_source_note(_sections(before)[0]) is None))
    checks.append(("טעות מספור מזוהה בנפרד",
                   section_source_note(_sections(_law(NUMBERING_ERROR))[1])
                   == ("numbering_error", "ספרור שגוי במקור")))
    checks.append(("סעיף שפקע מזוהה בנפרד",
                   section_source_note(_sections(_law(EXPIRED))[1]) == ("expired", "פקע")))

    # ── הוראה שתחולתה ממועד קובע: לא חסימה ──────────────────────────
    checks.append(("הוראה שתחולתה ממועד קובע אינה דו-משמעות",
                   duplicate_section_numbers(before) == {}))
    checks.append(("find_sections מחזירה את הנוסח שבתוקף עכשיו",
                   find_sections(before)["25"].id == "L/פרק ד/סימן ב/s25"))
    checks.append(("ההוראה שתחולתה ממועד קובע מסומנת, עם המועד כלשונו",
                   deferred_sections(before) == {"L/פרק ד/סימן ב/s25-2": "החל מהמועד הקובע"}))

    # והעריכה של הנוסח שבתוקף עובדת כרגיל - זה הלב של ההחלטה.
    after = _law(DEFERRED)
    _sections(after)[0].children[0].text = "תוקף היתר פליטה יהיה שבע שנים תמימות."
    lines = amend(before, after, [], law_footnote_key="k")
    checks.append(("עריכת הנוסח שבתוקף מפיקה הוראת תיקון",
                   len(lines) == 1 and lines[0].side_heading == "תיקון סעיף 25"))

    # ומי שכן ינסה לערוך את ההוראה שתחולתה ממועד קובע - מקבל שגיאה
    # מפורשת, לא אפס הוראות בשקט.
    after_deferred = _law(DEFERRED)
    _sections(after_deferred)[1].children[0].text = "(החל מהמועד הקובע): תוקף היתר יהיה עשר שנים תמימות."
    try:
        amend(before, after_deferred, [], law_footnote_key="k")
        checks.append(("עריכת ההוראה שתחולתה ממועד קובע -> שגיאה מפורשת", False))
    except NotImplementedError as exc:
        checks.append(("עריכת ההוראה שתחולתה ממועד קובע -> שגיאה מפורשת",
                       "החל מהמועד הקובע" in str(exc) and "בתוקף" in str(exc)))

    view = _view_sections(before)
    checks.append(("הנוסח שבתוקף ניתן לעריכה, וההוראה שלצידו לקריאה",
                   [s["editable"] for s in view] == [True, False, True]))
    checks.append(("ולא מסומן כדו-משמעי",
                   [s["ambiguous_number"] for s in view] == [False, False, False]))
    checks.append(("המועד מוצג כלשונו מהמקור",
                   [s["deferred_note"] for s in view] == ["", "החל מהמועד הקובע", ""]))
    # **הניסוח עצמו הוא חלק מהנכונות** - ההוראה בתוקף.
    checks.append(('שום מקום בעץ אינו אומר "לא בתוקף"',
                   not any("לא בתוקף" in str(s) for s in view)))

    # ── ושלוש המשפחות שנשארות חסומות ────────────────────────────────
    for label, text in (("כפילות בלי שום סימון", UNMARKED),
                        ("טעות מספור במקור", NUMBERING_ERROR),
                        ("סעיף שפקע", EXPIRED)):
        blocked_before = _law(text)
        checks.append((f"{label} - נשאר דו-משמעי",
                       list(duplicate_section_numbers(blocked_before)) == ["25"]))
        blocked_after = _law(text)
        _sections(blocked_after)[0].children[0].text = "תוקף היתר פליטה יהיה שבע שנים תמימות."
        try:
            amend(blocked_before, blocked_after, [], law_footnote_key="k")
            checks.append((f"{label} - העריכה נחסמת", False))
        except NotImplementedError as exc:
            checks.append((f"{label} - העריכה נחסמת", "25" in str(exc)))
        blocked_view = _view_sections(blocked_before)
        checks.append((f"{label} - שני העותקים מסומנים",
                       [s["editable"] for s in blocked_view] == [False, False, True]))

    # ── ובלי לחסום את שאר החוק ──────────────────────────────────────
    after_ok = _law(UNMARKED)
    _sections(after_ok)[2].children[0].text = "בעל היתר יגיש בקשה בכתב."
    lines = amend(_law(UNMARKED), after_ok, [], law_footnote_key="k")
    checks.append(("עריכה בסעיף לא-כפול באותו חוק ממשיכה לעבוד",
                   len(lines) == 1 and lines[0].side_heading == "תיקון סעיף 26"))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
