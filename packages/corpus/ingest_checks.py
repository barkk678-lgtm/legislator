"""בדיקות שפיות לפני כתיבת עץ שנפרסר מוויקיטקסט ל-DB (ראו TASKS.md,
תוכנית ה-ingest ב-decisions.md).

פונקציה טהורה בלבד: עובדות על הטקסט הגולמי + העץ שכבר נפרסר, בלי
רשת/DB - בדיוק כמו wikitext_parser.py עצמו.

הסיבה שהבדיקות האלה קיימות: פרסור שמצליח ומייצר תוצאה *חלקית* מסוכן
יותר מכשל פרסור מפורש. wikitext_parser.parse_wikitext מדלגת בשקט על
כל תבנית {{ח:...}} ברמה העליונה שאינה בטיפול המפורש שלה (ראו ההערה
בסוף אותו קובץ) - זה נכון ומכוון עבור תבניות מטא-דאטה/עיצוב (מאגר,
תיבה, חתימות...), אבל אם תבנית *מבנית* לא-מוכרת (עתידית, עדיין לא
נראתה בקורפוס) מדולגת באותה צורה, מתקבל עץ שנראה תקין אבל חסרים בו
סעיפים/רמות מבנה שלמות. הבדיקות כאן תופסות בדיוק את זה, ברעש, לפני
שהתוצאה נכתבת ל-DB. {{ח:קטע1}}/{{ח:קטע3}} (חלק/סימן) טופלו במלואן
ב-2026-09-14 (ראו TASKS.md משימה 7) - כלולות כעת ב-_KNOWN_STRUCTURAL_TEMPLATES.
"""

import re

from node import LegislativeNode

# תבניות ברמה העליונה (שורה שמתחילה ב-{{, כמו wikitext_parser.py עצמו
# בודק) ש-parse_wikitext יודעת לטפל בהן במפורש - תוכן/מבנה אמיתי.
_KNOWN_STRUCTURAL_TEMPLATES = {
    "ח:כותרת",
    "ח:קטע1",
    "ח:קטע2",
    "ח:קטע3",
    "ח:קטע4",
    "ח:סעיף",
    "ח:סעיף*",
    "ח:ת",
    "ח:תת",
    "ח:תתת",
    "ח:תתתת",
    "ח:תתתתת",
}

# תבניות ברמה העליונה שידוע שהן מטא-דאטה/עיצוב גרידא - מדולגות
# במכוון, לא פער. נבדק בפועל מול tests/fixtures/wikitext/*.wikitext.
_KNOWN_BENIGN_SKIP_TEMPLATES = {
    "ח:התחלה",
    "ח:סוף",
    "ח:פתיח-התחלה",
    "ח:פתיח-סוגר",
    "ח:סוגר",
    "ח:מאגר",
    "ח:מאגר2",  # וריאנט ממוספר של ח:מאגר - נבדק בפועל (2026-09-14): מכיל
    # רק מזהה מספרי גולמי (למשל "2204149"), אין נוסח. ראו TASKS.md משימה 7.
    "ח:תיבה",
    "ח:חתימות",
    "ח:מפריד",
    "ויקיפדיה",  # קישור-חוץ עיטורי לערך ויקיפדיה תואם - נבדק בפועל
    # (2026-09-14): הארגומנט היחיד הוא שם החוק עצמו כטקסט, אין נוסח.
}


def _top_level_templates(wikitext: str) -> list[str]:
    """שמות כל התבניות שמופיעות כשורה משל עצמה (אותו תנאי בדיוק כמו
    parse_wikitext: line.strip().startswith('{{')), כולל כפילויות -
    לא set, כדי לאפשר ספירה."""
    names = []
    for raw_line in wikitext.splitlines():
        line = raw_line.strip()
        if not line.startswith("{{"):
            continue
        match = re.match(r"\{\{([^|}]+)", line)
        if match:
            names.append(match.group(1))
    return names


def check_no_unknown_templates(wikitext: str) -> list[str]:
    """כל תבנית ברמה העליונה שאינה ב-שני האוספים הידועים = פער אמיתי
    בכיסוי הפרסר (כמו קטע1/קטע3 בחוק העונשין) - כשל, לא דילוג."""
    found = set(_top_level_templates(wikitext))
    unknown = found - _KNOWN_STRUCTURAL_TEMPLATES - _KNOWN_BENIGN_SKIP_TEMPLATES
    if unknown:
        return [f"תבנית לא מוכרת ברמה העליונה: {', '.join(sorted(unknown))}"]
    return []


def check_section_count(wikitext: str, tree: LegislativeNode) -> list[str]:
    """מספר {{ח:סעיף}}/{{ח:סעיף*}} ברמה העליונה בוויקיטקסט הגולמי
    חייב להיות זהה למספר צמתי node_type=='section' בעץ - כל אי-התאמה
    פירושה סעיף שנבלע/דולג בשקט."""
    raw_count = sum(1 for n in _top_level_templates(wikitext) if n in ("ח:סעיף", "ח:סעיף*"))
    tree_count = _count_node_type(tree, "section")
    if raw_count != tree_count:
        return [
            f"מספר {{{{ח:סעיף}}}} בוויקיטקסט הגולמי ({raw_count}) "
            f"לא תואם למספר צמתי section בעץ ({tree_count})"
        ]
    return []


def check_has_normative_content(tree: LegislativeNode) -> list[str]:
    if not _any_normative(tree):
        return ["העץ שנפרסר לא מכיל אף צומת נורמטיבי אחד (is_normative=True)"]
    return []


def check_unique_ids(tree: LegislativeNode) -> list[str]:
    """כל id בעץ חייב להיות ייחודי - זו לא בדיקה תיאורטית: התגלה בפועל
    (2026-09-13, ingest אמיתי על maavak-birgunei-plisha) ש-{{ח:סעיף}}
    בונה id מ-law_id בלבד (לא מ-parent_node.id), כך שסעיף 1 בחוק עצמו
    וסעיף 1 בכל תוספת (numbering_space='schedule', שמתחילה למספר
    מחדש) מקבלים בדיוק אותו id. לא היה עד כה שום צרכן שאוכף ייחודיות
    על העץ בזיכרון - ה-DB (composite PK) הוא הראשון, וזו בדיקה מקבילה
    שרצה לפני שמגיעים ל-DB בכלל."""
    seen: dict[str, int] = {}
    for node in _walk(tree):
        seen[node.id] = seen.get(node.id, 0) + 1
    duplicates = sorted(node_id for node_id, count in seen.items() if count > 1)
    if duplicates:
        return [f"id כפול בעץ: {', '.join(duplicates)}"]
    return []


def _walk(node: LegislativeNode):
    yield node
    for child in node.children:
        yield from _walk(child)


def _count_node_type(node: LegislativeNode, node_type: str) -> int:
    return sum(1 for n in _walk(node) if n.node_type == node_type)


def _any_normative(node: LegislativeNode) -> bool:
    return any(n.is_normative for n in _walk(node))


def run_sanity_checks(wikitext: str, tree: LegislativeNode) -> list[str]:
    """מריצה את כל הבדיקות, מחזירה רשימת תיאורי בעיות (ריקה = תקין)."""
    problems: list[str] = []
    problems += check_no_unknown_templates(wikitext)
    problems += check_section_count(wikitext, tree)
    problems += check_has_normative_content(tree)
    problems += check_unique_ids(tree)
    return problems
