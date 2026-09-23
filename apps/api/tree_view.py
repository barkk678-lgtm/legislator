"""ממיר LegislativeNode לעץ dict-ים פשוט, קריא ל-Jinja2/JSON - לא בונה
HTML בפייתון (זו עבודת הטמפלט/הלקוח). טהור: אין כאן לוגיקה משפטית,
רק תיוג type_label ומעבר רקורסיבי. ראו TASKS.md משימה 10.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
from node import (  # noqa: E402
    LegislativeNode, deferred_sections, duplicate_section_numbers,
    effective_as_of, find_sections)
from dates import display_date  # noqa: E402

TYPE_HE = {
    "law": "חוק",
    "part": "חלק",
    "chapter": "פרק",
    "siman": "סימן",
    "section": "סעיף",
    "subsection": "סעיף קטן",
    "paragraph": "פסקה",
    "subparagraph": "פסקת משנה",
    "definition": "הגדרה",
}


def node_view(node: LegislativeNode, _ambiguous: frozenset[str] | None = None,
              _deferred: dict[str, str] | None = None) -> dict:
    """ראו TASKS.md משימה 10ב: צמתים עם is_normative=False מוסתרים
    לגמרי מהעץ שנשלח ללקוח (לא רק ב-CSS בצד הלקוח) - אין להם שום
    ייצוג בתגובה, לא רק "אינם מוצגים". השורש עצמו (is_normative=False
    בעצמו, מטא-דאטה של החוק) עדיין מיוצג - הסינון חל רק על ילדים.

    `_ambiguous` נגזר פעם אחת מהשורש ומועבר הלאה ברקורסיה - מספרי
    הסעיפים שמופיעים יותר מפעם אחת בחוק. פנימי; קוראים ל-node_view
    עם השורש בלבד."""
    if _ambiguous is None:
        _ambiguous = frozenset(duplicate_section_numbers(node))
    if _deferred is None:
        _deferred = deferred_sections(node)
    deferred_note = _deferred.get(node.id, "")
    return {
        "id": node.id,
        "node_type": node.node_type,
        "type_label": TYPE_HE.get(node.node_type, node.node_type),
        "number": node.number,
        "margin_title": node.margin_title,
        "full_title": node.full_title,  # משמעותי רק בשורש (node_type=="law")
        "text": node.text,
        "status": node.status,
        # **סעיף שאי אפשר לערוך חייב להיראות אחרת** (ברק, 2026-09-18).
        # עד כאן הוא נראה תקין לחלוטין ופשוט לא הגיב ללחיצה - הכישלון
        # השקט הגרוע ביותר בממשק. סעיף בלי מספר אינו נמצא על ידי
        # find_sections, ולכן amend() לא יראה אותו: 429 סעיפים
        # בקורפוס, מהם 111 בפקודת מס הכנסה לבדה. ראו
        # docs/night-report.md 18.9 לאבחון המלא (הסיבה: {{ח:סעיף*}}).
        # raw_block נוסף לכאן 23.9.2026: `amend()` זורקת עליו
        # NotImplementedError מפורש (ראו engine.py והבדיקה
        # test_raw_block_not_editable), אבל בעץ הוא נראה ככל צומת
        # אחר - כלומר המשתמש לוחץ, עורך, ומקבל שגיאה רק בסוף.
        # **אותו כלל בדיוק כמו סעיף בלי מספר:** מה שאי אפשר לערוך
        # חייב להיראות אחרת מראש. 397 בלוקים ב-119 חוקים.
        # **מספר סעיף כפול - אותו כלל בדיוק** (23.9.2026): כשיש בחוק
        # שני סעיפים 25, "בסעיף 25 לחוק העיקרי" אינה כתובת חד-משמעית
        # ו-`amend()` חוסמת. 96 צמתים ב-38 חוקים. עד לתיקון הזה
        # `find_sections` שמרה רק את האחרון, והמשתמש שערך את הסעיף
        # שבתוקף קיבל אפס הוראות תיקון בלי שום הודעה. **שני העותקים**
        # מסומנים, לא רק זה שנדרס: הבעיה היא הכתובת, לא הצומת.
        "editable": not (
            node.node_type == "raw_block"
            or (node.node_type == "section" and not node.number)
            or (node.node_type == "section" and node.number in _ambiguous)
            or bool(deferred_note)
        ),
        "ambiguous_number": (
            node.node_type == "section" and node.number in _ambiguous
        ),
        # **הוראה שתחולתה מתחילה במועד קובע** - הסימון כלשונו מהמקור
        # ("החל מיום 26.1.2027", "הוראת שעה עד יום 31.12.2026"). היא
        # **בתוקף**; מה שמוצג הוא מועד התחולה, ולעולם לא "לא בתוקף".
        # מוצגת לצד הנוסח שניתן לעריכה, לקריאה בלבד.
        "deferred_note": deferred_note,
        "children": [node_view(c, _ambiguous, _deferred)
                     for c in node.children if c.is_normative],
    }


def _serialize(node: LegislativeNode) -> str:
    """ייצוג טקסטואלי שטוח של צומת+צאצאיו - לצורך השוואת לפני/אחרי
    בלבד (touched_section_numbers), לא לתצוגה."""
    parts = [node.text]
    parts.extend(_serialize(c) for c in node.children)
    return "␟".join(parts)  # מפריד בקרה שלא אמור להופיע בנוסח אמיתי


def touched_section_numbers(before: LegislativeNode, after: LegislativeNode) -> set[str]:
    """סעיפים שהטקסט שלהם (או של מי מצאצאיהם) שונה בין העצים, וגם
    סעיפים ראשיים חדשים לגמרי (לא היו קיימים ב-before בכלל, §7.12) -
    כדי להדגיש בתצוגת ה'אחרי' איפה יש שינוי, בלי תלות בפרטי amend().

    **באג שנתפס ותוקן (2026-09):** הלולאה המקורית עברה רק על
    before_sections.items() - סעיף חדש שקיים רק ב-after (הוספת סעיף
    ראשי חדש) לא נספר בכלל כ"touched", למרות שהוא בעליל שונה. אותה
    מחלקת טעות בדיוק כמו amend()'s before_sections.keys()-only loop
    שתוקנה קודם ב-engine.py - נתפס כאן על ידי בדיקת אינטגרציה אמיתית
    ב-tests/unit/test_api.py, לא רק עיון בקוד."""
    # תוקן (2026-09-16): רקורסיבי בכל עומק, אותו באג בדיוק כמו
    # engine.amend() - ראו find_sections (node.py).
    before_sections = find_sections(before)
    after_sections = find_sections(after)
    touched = set()
    for number, before_sec in before_sections.items():
        after_sec = after_sections.get(number)
        if after_sec is None or _serialize(before_sec) != _serialize(after_sec):
            touched.add(number)
    touched.update(set(after_sections) - set(before_sections))
    return touched


def as_of_display(root: LegislativeNode) -> str | None:
    """הניסוח הקבוע: 'נוסח כפי שהופיע בוויקיטקסט ביום X' - לא 'מעודכן
    ליום X' (ראו docs/data-sources.md). הניסוח הוא תפקיד שכבת התצוגה,
    לא של node.py/wikitext_parser.py עצמם."""
    value = effective_as_of(root, root)
    if value is None:
        return None
    return f"נוסח כפי שהופיע בוויקיטקסט ביום {display_date(value) or value}"
