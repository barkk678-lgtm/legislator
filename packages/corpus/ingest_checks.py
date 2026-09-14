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
    "ח:תתתתתת",  # עומק 6 - אותה משפחה, אותם ארגומנטים, קינון עמוק
    # יותר (ראו wikitext_parser._CONTENT_DEPTH, 2026-09-14).
    "ח:תתתתתתת",  # עומק 7.
}

# תבניות ברמה העליונה שידוע שהן מטא-דאטה/עיצוב גרידא - מדולגות
# במכוון, לא פער. נבדק בפועל מול tests/fixtures/wikitext/*.wikitext.
_KNOWN_BENIGN_SKIP_TEMPLATES = {
    "ח:התחלה",
    "ח:סוף",
    "ח:פתיח-התחלה",
    "ח:פתיח-סוגר",
    "ח:סוגר",
    "ח:מבוא",  # קופסת-הערה כללית (זוג פתיחה/סגירה כמו ח:פתיח-התחלה), לא
    # ספציפית לחקיקת משנה כפי שהונח בטעות בהתחלה - נבדק בפועל (2026-09-14)
    # על מספר חוקים: הודעות עריכה (שינויי תואר) והודעות ביטול חוק (שתי
    # דוגמאות אמיתיות). זיהוי חוק מבוטל עבר ל-knesset_odata.py (מקור
    # סמכותי, לא ניחוש טקסט) - ראו TASKS.md משימה 7 / decisions.md.
    "ח:מאגר",
    "ח:מאגר2",  # וריאנט ממוספר של ח:מאגר - נבדק בפועל (2026-09-14): מכיל
    # רק מזהה מספרי גולמי (למשל "2204149"), אין נוסח. ראו TASKS.md משימה 7.
    "ח:תיבה",
    "ח:חתימות",
    "ח:מפריד",
    "ויקיפדיה",  # קישור-חוץ עיטורי לערך ויקיפדיה תואם - נבדק בפועל
    # (2026-09-14): הארגומנט היחיד הוא שם החוק עצמו כטקסט, אין נוסח.
    # 11 תבניות תיוג/עיטור, אושרו במרוכז (ברק, 2026-09-14) אחרי הצגת
    # תוכן אמיתי לכל אחת - ראו TASKS.md משימה 7 לטבלה המלאה. כולן
    # תבניות ניווט/קטגוריה בעליל, אין נוסח באף דוגמה.
    "מיזמים",
    "חוקי יסוד",
    "חוקי מקרקעין",
    "חוקי בחירות",
    "חוקי אזרחות, תושבות וכניסה לישראל",  # שם תבנית אחד עם פסיק
    # בתוכו - לא שתי תבניות (אומת במפורש, ראו TASKS.md).
    "חוקי עונשין",
    "חוקי ביטחון סוציאלי",
    "חוקי קורונה",
    "חוקי מס",
    "חוק נתוני אשראי",  # תבנית ניווט, שם זהה לשם חוק אמיתי, בלי ארגומנטים
    "ח:הערה",  # הערת עריכה ברמה העליונה - נבדק בפועל על 47 חוקים
    # (2026-09-14): **תמיד** בתוך קופסת ח:פתיח-התחלה/ח:חתימות/ח:מבוא
    # (בין הפתיחה ל-ח:סוגר התואם) - אותו in_skip_zone שכבר קיים
    # (wikitext_parser ו-ingest_checks כאחד) כבר מתעלם מהתוכן שבפנים
    # בלי קשר לשם התבנית - זה רק מוריד את הדגל השגוי ב-check_no_unknown_templates
    # עצמה (_top_level_templates לא מודעת לאזורי דילוג, ראו שם).
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


_SKIP_ZONE_OPENERS = {"ח:פתיח-התחלה", "ח:חתימות", "ח:מבוא"}  # קופסאות
# עם תוכן פנימי שאינו {{...}} (ציטוטים/חתימות/הערות) - לגיטימי בכוונה,
# לא פער. ראו _KNOWN_BENIGN_SKIP_TEMPLATES; parse_citation_registry
# (amendment_history.py) היא זו שקוראת בפועל את תוכן ה-פתיח-התחלה.
_SKIP_ZONE_CLOSER = "ח:סוגר"
_CATEGORY_LINE_RE = re.compile(r"^\[\[קטגוריה:")  # [[קטגוריה:...]] - מנוהל
# בנפרד (wikitext_client.list_category_titles), לא חלק מהנוסח בכלל.
_TOC_DIV_OPEN_RE = re.compile(r'^<div class="law-toc">$')  # תוכן העניינים
# האוטומטי של ויקיטקסט - בלוק HTML גולמי, עודף לגמרי מול העץ שכבר נבנה
# (כל {{ח:פנימי}} בפנים כבר קיים כ-node אמיתי). תמיד תחום ב-<div
# class="law-toc"> יחיד ו-</div> יחיד בשורה נפרדת (נבדק בפועל, ראו
# TASKS.md משימה 7) - לא זקוק לספירת קינון, רק זיהוי הפתיחה/סגירה.
_TOC_DIV_CLOSE_LINE = "</div>"
_TABLE_OPEN_RE = re.compile(r"(?i)^<table\b")  # אותו regex בדיוק כמו
# wikitext_parser._TABLE_OPEN_RE - בלוקי <table> גולמיים נצרכים בפועל
# עכשיו כצומת raw_block (ראו TASKS.md משימה 7), לא אבודים יותר.
_TABLE_CLOSE_RE = re.compile(r"(?i)</table\s*>")
_INCLUDEONLY_CATEGORY_RE = re.compile(r"(?i)^<includeonly>.*קטגוריה.*</includeonly>$")
# זריקת קטגוריה אוטומטית עטופה ב-<includeonly> (חוק הרשות לפיתוח
# ירושלים) - אותה משפחת תוכן-בוט כמו [[קטגוריה:...]] הרגיל, רק עטופה
# (נמצא בסריקת הקורפוס השלם, ראו TASKS.md משימה 7, 2026-09-14).
_STRAY_PUNCTUATION_RE = re.compile(r"^[.,;:]$")  # תו פיסוק בודד בשורה
# נפרדת (למשל "." בחוק הנוער) - רעש עריכה במקור, לא תוכן (אותה סריקה).
_MAX_UNCONSUMED_EXAMPLES = 5


def check_no_unconsumed_content(wikitext: str) -> list[str]:
    """הכיוון ההפוך מ-check_no_unknown_templates: לא "מה נוצר", אלא
    "מה אבד" (ברק, 2026-09-14). לפני 2026-09-14, parse_wikitext דילגה
    בשקט על **כל** שורה לא-ריקה שלא מתחילה ב-'{{' - ללא יוצא מן הכלל,
    וללא שום בדיקה שתופסת את זה (התרחיש המסוכן ביותר שהוגדר בפרויקט:
    פרסור שמצליח ומייצר עץ *חסר* בשקט). בלוקי <table> גולמיים (97/1,021
    חוקים - ראו TASKS.md משימה 7) **נצרכים כעת בפועל** כצומת raw_block
    (ראו wikitext_parser._consume_html_table) - הבדיקה הזו מזהה את אותם
    אזורי טבלה ולא מתריעה עליהם (ראו _TABLE_OPEN_RE/_TABLE_CLOSE_RE
    למטה, זהים ל-wikitext_parser).

    לא מתריעה גם על תוכן שכן מכוסה במקום אחר, ולא בכוונה חלק מהנוסח:
    שורות בתוך קופסת פתיח-התחלה/חתימות/מבוא (בין הפתיחה ל-{{ח:סוגר}}
    התואם - ציטוטים/חתימות/הערות עריכה, לא נוסח), תוכן עניינים אוטומטי
    (<div class="law-toc">...</div>), [[קטגוריה:...]], אותה קטגוריה
    עטופה ב-<includeonly>, ותו פיסוק בודד בשורה נפרדת.

    **מ-2026-09-14: כל שורה אחרת (לא-ריקה, לא-{{, לא באחד מהאזורים
    למעלה) נצרכת בפועל על ידי הלולאה הראשית ב-wikitext_parser** -
    מצורפת כהשלמה לצומת האחרון שנפתח (LegislativeNode.
    completed_by_continuation, ראו node.py) במקום ללכת לאיבוד בשקט.
    זה נמצא אחרי סריקת קורפוס-שלם (1,021 חוקים, לא מדגם) שחשפה 7
    מקרים אמיתיים בלבד - ראו TASKS.md משימה 7. הבדיקה הזו, אחרי התיקון,
    לכן לא-אמורה למצוא עוד בעיות מהמשפחה הזו על קלט תקין - היא נשארת
    קו-הגנה שקוף (לא הוסרה) למקרה שבעתיד תיפתח דרך פרסור חדשה שכן
    מדלגת בשקט על תוכן בלי לעבור דרך הענף הזה."""
    problems: list[str] = []
    in_skip_zone = False
    in_toc_zone = False
    in_table_zone = False
    for line_number, raw_line in enumerate(wikitext.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if in_table_zone:
            if _TABLE_CLOSE_RE.search(line):
                in_table_zone = False
            continue
        if in_toc_zone:
            if line == _TOC_DIV_CLOSE_LINE:
                in_toc_zone = False
            continue
        if _TOC_DIV_OPEN_RE.match(line):
            in_toc_zone = True
            continue
        if _TABLE_OPEN_RE.match(line):
            # טבלה "יתומה" (לא אחרי {{ח:ת...}}) - נצרכת בפועל כ-raw_block.
            if not _TABLE_CLOSE_RE.search(line):
                in_table_zone = True
            continue
        if line.startswith("{{"):
            match = re.match(r"\{\{([^|}]+)", line)
            name = match.group(1) if match else ""
            if name in _SKIP_ZONE_OPENERS:
                in_skip_zone = True
            elif name == _SKIP_ZONE_CLOSER:
                in_skip_zone = False
            elif "}}" in line:
                # טבלה מוטבעת מיד אחרי תבנית עומק, למשל {{ח:ת}} <table...>
                # (ראו wikitext_parser._TABLE_OPEN_RE - אותה בדיקה בדיוק).
                remainder = line.split("}}", 1)[1].strip()
                if _TABLE_OPEN_RE.match(remainder) and not _TABLE_CLOSE_RE.search(remainder):
                    in_table_zone = True
            continue
        if in_skip_zone:
            continue
        if _CATEGORY_LINE_RE.match(line) or _INCLUDEONLY_CATEGORY_RE.match(line):
            continue
        if _STRAY_PUNCTUATION_RE.match(line):
            continue
        # כל מה שנשאר: נצרך כהשלמה (ראו docstring למעלה) - לא פער.

    if not problems:
        return []
    shown = problems[:_MAX_UNCONSUMED_EXAMPLES]
    more = f" (+{len(problems) - len(shown)} נוספות)" if len(problems) > len(shown) else ""
    return [f"{len(problems)} שורות תוכן שלא נצרכו על ידי אף ענף בפרסר: " + "; ".join(shown) + more]


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
    problems += check_no_unconsumed_content(wikitext)
    problems += check_section_count(wikitext, tree)
    problems += check_has_normative_content(tree)
    problems += check_unique_ids(tree)
    return problems
