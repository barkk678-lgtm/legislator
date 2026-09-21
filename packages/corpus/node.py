"""ייצוג צומת בעץ חוק. ראו TASKS.md משימות 2-3 (recon על ויקיטקסט).

number הוא מספר הסעיף *בחוק המתוקן עצמו* (3א, 34כד, (א), (1)) - מרחב
מספור נפרד לגמרי ממספר הסעיף הרץ בהצעת החוק (1., 2., 3...), שמטופל
כבר ב-packages/render/render_bill.py (Line.number). אסור לבלבל בין
שני המרחבים.

is_normative ו-status נוספו בעקבות recon אמיתי על חוק הקייטנות
בוויקיטקסט (ראו תבניות {{ח:הערה}} וסעיף 7 שם):

- is_normative=False מסמן צומת שהוא הערת עורך ({{ח:הערה}} בוויקיטקסט)
  ולא נוסח חוק. הערה היא תוכן שמתנדבים כתבו, לא נוסח חוק - אם היא
  תיכנס להוראת תיקון זו הפרה של חוק ברזל 1. packages/amend חייב
  להתעלם לגמרי מצמתים עם is_normative=False (ראו TASKS.md משימה 4).
- status מייצג את מצב הסעיף בחוק: active (בתוקף), repealed (בוטל
  ולא הוחלף), merged (שולב בחוק אחר - כמו סעיף 7 בחוק הקייטנות).
  סעיפים בטלים/משולבים הם תופעה נפוצה בחקיקה אמיתית, לא מקרה קצה,
  וחייבים לשרוד בעץ כדי שרצף המספור לא יישבר.

שדות נוספים, מ-recon על חוק העונשין (694 קריאות {{ח:סעיף}}, מבנה
חלק/פרק/סימן, ולוח השוואה כתוספת נספחת):

- raw_amendment_note שומר גולמית את הארגומנט הרביעי/השלישי של
  {{ח:סעיף}} בעונשין, למשל "תיקון: [1939], [תשי״ז], תשמ״ח־3,
  תשנ״ד־3, ...אחר=[א/5]" עבור סעיף 34כד. זה בדיוק מה שחוק ברזל 3
  דורש - ברזולוציית תיקון-אחרון-לפי-סעיף, לא timestamp כללי של
  העמוד - אבל התחביר לא פוענח (ראו TASKS.md משימה 7א). אם פרסר
  היה זורק את המחרוזת הזו, המידע היה אובד לצמיתות - צריך ingest
  חוזר של כל הקורפוס כדי להחזיר אותו. לכן נשמר גולמי כאן, ולא
  ממתינים לפרסר שיבין אותו.
- numbering_space מבחין בין מספור סעיפי החוק עצמו ("law", ברירת
  המחדל) לבין מרחבי מספור נפרדים באותו מסמך - כמו ה"לוח השוואה"
  בעונשין, שבו סעיפים ממוספרים באותיות (א, א1, ב, ...) אך אינם
  המשך למספור סעיפי החוק (הוא טבלת המרה בין מספור חוק קודם
  למספור הנוכחי, לא נוסח מהותי). sort_section_numbers אסור
  שיערבב בין מרחבים שונים - זו אותה הבחנה שכבר קיימת בין מספור
  החוק למספור הצעת החוק.

margin_title מכיל תבניות מקוננות לפעמים (למשל הפניות {{ח:פנימי}}
בתוך כותרת השוליים עצמה, כפי שנצפה בסעיף 34כג בעונשין). margin_title
שומר את הטקסט השטוח (מפוענח/מוצג), ו-margin_title_raw שומר את
הוויקיטקסט הגולמי של הכותרת אם הוא מכיל תבניות.

text_raw שומר את הטקסט לפני normalize_text (ראו packages/corpus/
text_normalize.py) - טקסט שנשלף מוויקיטקסט, בלי החלפות תווים.
text מחזיק את הגרסה המנורמלת. שני השדות נשמרים כדי שלא נגלה בעוד
חודש שנרמלנו יותר מדי ואיבדנו מידע - קל להשוות בין השניים בכל שלב.

full_title נוסף לטובת משימה 4 (amend): שם החוק המלא כפי שמופיע
ב-{{ח:כותרת}} בוויקיטקסט, כולל שנה (למשל 'חוק הקייטנות (רישוי
ופיקוח), התש"ן–1990'). רק לצומת ה-law. **לא** margin_title - זה שם
שמור לכותרת שוליים של סעיף, ושימוש כפול בו יבלבל בין "שם החוק" לבין
"כותרת שוליים של סעיף מסוים".

as_of (משימה 5א) הוא "תאריך הנוסח" מחוק ברזל 3: מתי בדיוק הוויקיטקסט
הזה נערך לאחרונה (revision timestamp, ראו wikitext_client.
extract_revision_timestamp) - **לא** "מעודכן ליום X" (ראו ההבחנה
המפורשת ב-docs/data-sources.md: אין ערבות שהחוק לא תוקן בעולם האמיתי
אחרי התאריך הזה, רק שכך הוא הופיע בוויקיטקסט ביום זה). כמו source_ref:
יושב בשורש בלבד, וצמתים אחרים יורשים אותו דרך effective_as_of()
למטה - לא מוצג ישירות למשתמש כמו שהוא (בלי הניסוח "נוסח כפי שהופיע
ביום..."), זה תפקיד השכבה שמציגה, לא של המודל.

מבנה משימה 3 (ingest): שורש העץ הוא LegislativeNode(node_type="law"),
עם source_ref מחושב פעם אחת ו-is_normative=False (השורש הוא מטא-דאטה
של החוק - שם, מספר מאגר, מראה מקום - לא נוסח, ואסור שייכנס ל-diff,
בדיוק כמו הערת עורך). source_ref *לא* מועתק לכל צומת בעץ - הוא יושב
רק בשורש, וצמתים אחרים משאירים אותו ריק (""); effective_source_ref()
למטה מטפס במעלה העץ כדי למצוא אותו בזמן קריאה, כדי שלא נצטרך לעדכן
מאות עותקים כשהוא משתנה. raw_amendment_note לעומת זאת יושב ברמת
הסעיף עצמו, כי הוא באמת שונה בין סעיפים.
"""

from dataclasses import dataclass, field
from typing import Literal

from numbering import parse_section_number


@dataclass
class LegislativeNode:
    id: str  # מזהה יציב: "penal-1977/s4/a/1"
    node_type: str  # law|part|chapter|siman|section|subsection|paragraph|subparagraph|definition|raw_block
    # raw_block (2026-09-14): בלוק <table> גולמי ב-HTML (לא MediaWiki) -
    # ראו wikitext_parser._consume_html_table. text/text_raw מכילים את
    # ה-HTML הגולמי כפי שהוא, is_normative=True (לרוב תוכן מהותי - תעריפים/
    # מדרגות מס, לא רק "לוח השוואה" עיטורי - ראו TASKS.md משימה 7).
    # **לא ניתן לעריכה תכנותית** - packages/amend מעלה NotImplementedError
    # מפורש על ניסיון תיקון; בממשק (טרם קיים) יוצג בלבד, לא ייערך.
    number: str  # "4", "3א", "34כד", "(א)", "(1)" - מספור החוק המתוקן בלבד
    margin_title: str | None  # כותרת שוליים, טקסט שטוח - רק לסעיף ראשי
    text: str  # טקסט מנורמל (ראו text_normalize.normalize_text)
    children: list["LegislativeNode"] = field(default_factory=list)
    source_ref: str = ""  # יושב בשורש בלבד - ראו effective_source_ref()
    is_normative: bool = True  # False = הערת עורך/מטא-דאטה, לא נוסח חוק
    status: Literal["active", "repealed", "merged"] = "active"
    raw_amendment_note: str | None = None  # הארגומנט הגולמי "תיקון: ...אחר=..." בלי פענוח
    numbering_space: str = "law"  # "law" | "comparison-table" | ...
    margin_title_raw: str | None = None  # כותרת השוליים כוויקיטקסט גולמי, אם היא מכילה תבניות
    text_raw: str = ""  # הטקסט לפני normalize_text
    full_title: str | None = None  # רק לצומת law - שם החוק המלא, מ-{{ח:כותרת}}
    as_of: str | None = None  # יושב בשורש בלבד - ראו effective_as_of()
    version_id: int | None = None  # יושב בשורש בלבד - law_versions.id שממנו
    # נטען העץ. None ל-fixtures ולעצים שנבנו מוויקיטקסט ישירות. נדרש כדי
    # שטיוטה שמורה תדע על איזה נוסח בדיוק היא נבנתה: המזהה משתנה גם
    # כשנטענת גרסה חדשה וגם כשגרסה קיימת הוחלפה בתיקון פרסור, וזה בדיוק
    # מה שקובע אם הטקסט שמתחת לטיוטה זז.
    id_collisions: list[str] = field(default_factory=list)  # יושב בשורש בלבד -
    # כל מקרה שבו wikitext_parser._unique_child_id נאלצה להוסיף סיומת סידורית
    # (id "טבעי" כבר תפוס בין האחים - ראו חוק החוזים סעיף 25). לא שגיאת פרסור
    # (העץ תקין, check_unique_ids נקי) - רק סימן שהמבנה לא כמצופה. ברק (2026-09-14):
    # "אם זה קורה באלפי מקומות, יש דפוס שלא זיהינו" - נרשם כאן כעובדה גולמית
    # (בלי I/O בפרסר עצמו), כדי שקוד ה-ingest/batch יוכל לספור/לרשום ביומן.
    content_derived_ids: list[str] = field(default_factory=list)  # יושב בשורש בלבד -
    # כל סעיף בלי מספר טבעי (ראו התנגשויות ה-id ב-חוק מועצת הצמחים וכו') שקיבל
    # id יציב הנגזר מ-hash של תוכנו (לא ממיקום) - ראו wikitext_parser._lookahead_content.
    # ברק (2026-09-14): id לפי מיקום "שובר את הבסיס" של יציבות provenance בין
    # גרסאות - נרשם כאן כדי לספור שכיחות על הקורפוס המלא, כמו id_collisions.
    completed_by_continuation: bool = False  # True אם טקסט הצומת הזה
    # כולל לפחות שורה שצורפה אליו כהשלמה (שורה בוויקיטקסט שלא התחילה
    # ב-{{ ולא הייתה באזור מוכר - ראו wikitext_parser, הלולאה הראשית),
    # לא מתבנית מפורשת משלה. בלי לנחש מבנה - מצורף לצומת האחרון שנפתח
    # כפי שהוא (ברק, 2026-09-14, אחרי סריקת קורפוס-שלם שחשפה 7 מקרים
    # כאלה - TASKS.md משימה 7). שדה על הצומת עצמו, לא רק לוג בשורש -
    # ברק ביקש "לדעת אילו צמתים במערכת נבנו מהשלמה ולא מתבנית מפורשת".
    unrecognized_starred: bool = False  # True אם הצומת נוצר מ-
    # {{ח:סעיף*}} שלא היה אפשר לסווג. **לא ניחוש לשום כיוון** (ברק,
    # 2026-09-19): 278 מופעים בקורפוס נושאים ארגומנט מיקומי ריק ואין
    # להם `עוגן=` כלל. הגרסה הקודמת סיווגה אותם בשקט כסעיף קטן, ואין
    # לכך ראיה - עשרת האחים שלהם שכן נושאים עוגן אומרים "תוספת". לכן
    # הם נשארים בדיוק כפי שהיו לפני התיקון, ומסומנים. אם יימצא סימן -
    # יסווגו אז.
    starred_as_subsection: list[str] = field(default_factory=list)  # יושב
    # בשורש בלבד - כל {{ח:סעיף*}} שזוהה כסעיף קטן ולכן **לא** יצר
    # צומת section. נדרש כדי ש-check_section_count תישאר שוויון מדויק
    # ולא אי-שוויון מרופף: raw == section_nodes + len(זה). ראו
    # ingest_checks.check_section_count.
    unrecognized_starred_ids: list[str] = field(default_factory=list)  # יושב
    # בשורש בלבד - כל id של צומת עם unrecognized_starred=True, לספירה
    # על הקורפוס המלא (אותו דפוס כמו id_collisions/content_derived_ids).
    continuation_completions: list[str] = field(default_factory=list)  # יושב
    # בשורש בלבד - כל id של צומת שקיבל completed_by_continuation=True,
    # לספירה על הקורפוס המלא (אותו דפוס בדיוק כמו id_collisions/
    # content_derived_ids למעלה).


def effective_source_ref(root: LegislativeNode, target: LegislativeNode) -> str:
    """מוצא את source_ref בפועל של target, בטיפוס במעלה העץ מהשורש.

    source_ref נשמר רק בצמתים שבהם הוא הוגדר בפועל (כרגע: שורש ה-law
    בלבד) - צמתים אחרים יורשים אותו לפי המיקום שלהם בעץ, כדי שלא
    נשמור את אותה מחרוזת פעמים רבות ונצטרך לעדכן את כולן יחד.
    """
    stack: list[tuple[LegislativeNode, str]] = [(root, root.source_ref)]
    while stack:
        node, inherited = stack.pop()
        current = node.source_ref or inherited
        if node is target:
            return current
        for child in node.children:
            stack.append((child, current))
    raise ValueError("target אינו צומת בעץ שמשורשו root")


def effective_as_of(root: LegislativeNode, target: LegislativeNode) -> str | None:
    """מוצא את as_of בפועל של target, בטיפוס במעלה העץ מהשורש - אותו
    דפוס בדיוק כמו effective_source_ref (as_of יושב רק בשורש, צמתים
    אחרים יורשים אותו לפי מיקומם בעץ)."""
    stack: list[tuple[LegislativeNode, str | None]] = [(root, root.as_of)]
    while stack:
        node, inherited = stack.pop()
        current = node.as_of or inherited
        if node is target:
            return current
        for child in node.children:
            stack.append((child, current))
    raise ValueError("target אינו צומת בעץ שמשורשו root")


def find_sections(root: LegislativeNode, *, numbering_space: str = "law") -> dict[str, "LegislativeNode"]:
    """אוספת את כל צמתי node_type=="section" בעץ, **בכל עומק** - לא רק
    ילדים ישירים של השורש. תוקן (2026-09-16, ברק: "42.3% מהקורפוס לא
    ניתן לעריכה... זה חור בלב המוצר"): עד כה כל קוד ה-amend חיפש רק
    ב-root.children - חוק עם מבנה חלק/פרק/סימן (20 החוקים הגדולים
    בקורפוס, בלי יוצא מן הכלל) לא היה "נראה" בכלל, `lines=[]` בשקט.

    numbering_space="law" (ברירת המחדל) מסננת בכוונה סעיפי תוספת/לוח-
    השוואה (numbering_space שונה) - אלה משתמשים במרחב מספור נפרד
    (לפעמים מתחיל מחדש מ-1) ועלולים להתנגש עם מספרי הסעיפים הרגילים
    אם היו נכללים כאן. אומת בפועל (לא הונח): מספור סעיפים ב-numbering_
    space="law" רץ ברצף גלובלי לאורך כל החוק בלי איפוס בכל חלק/פרק/
    סימן - "סעיף 47" מזהה סעיף יחיד בחוק כולו, בלי תלות במיקומו בעץ.

    **הגנה נוספת שנמצאה תוך כדי (2026-09-16), לא רק תיאוריה:** "לוח
    השוואה" בחוק העונשין מתויג בפועל numbering_space="law" בנתוני
    ה-ingest הקיימים (לא "comparison-table" כפי שהתיעוד למעלה מניח -
    פער תיוג אמיתי ב-ingest, מחוץ להיקף התיקון הזה) - ומספר הסעיף שלו
    שם הוא אות בודדת ("ו"), פורמט שלא קיים בכלל בסעיפי חוק רגילים
    (numbering.parse_section_number דורש ספרה מובילה). בלי ההגנה כאן,
    זה קרס את /render (ValueError לא-מטופל) על כל חוק עם לוח השוואה -
    נתפס רק בבדיקה אמיתית בדפדפן על חוק העונשין, לא בטסטים. תוכן כזה
    מדולג בשקט (לא חלק מהמספור הרגיל, בדיוק כמו הכוונה המקורית של
    numbering_space) - לא זורק, כי זו עובדה ידועה על מקור, לא קלט פגום."""
    result: dict[str, LegislativeNode] = {}

    def _walk(node: LegislativeNode) -> None:
        if node.node_type == "section" and node.numbering_space == numbering_space:
            try:
                parse_section_number(node.number)
            except ValueError:
                pass  # ראו התיעוד למעלה - "לוח השוואה" וכדומה, לא מספור-סעיף רגיל
            else:
                result[node.number] = node
        for child in node.children:
            _walk(child)

    _walk(root)
    return result


def find_parent(root: LegislativeNode, node_id: str) -> "LegislativeNode | None":
    """מוצאת את ההורה הישיר של צומת לפי id, בכל עומק - None אם node_id
    הוא השורש עצמו או לא נמצא. נדרשת (בניגוד ל-effective_source_ref/
    effective_as_of, שרק *קוראות* את העץ) כדי לדעת לאיזו רשימת-ילדים
    בפועל להכניס צומת חדש (InsertSectionAfter) - חייבת להיות אותו
    פרק/סימן שהעוגן נמצא בו, לא root.children."""
    for child in root.children:
        if child.id == node_id:
            return root
        found = find_parent(child, node_id)
        if found:
            return found
    return None
