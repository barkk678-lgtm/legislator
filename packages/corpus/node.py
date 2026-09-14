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


@dataclass
class LegislativeNode:
    id: str  # מזהה יציב: "penal-1977/s4/a/1"
    node_type: str  # law|part|chapter|siman|section|subsection|paragraph|subparagraph|definition
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
    id_collisions: list[str] = field(default_factory=list)  # יושב בשורש בלבד -
    # כל מקרה שבו wikitext_parser._unique_child_id נאלצה להוסיף סיומת סידורית
    # (id "טבעי" כבר תפוס בין האחים - ראו חוק החוזים סעיף 25). לא שגיאת פרסור
    # (העץ תקין, check_unique_ids נקי) - רק סימן שהמבנה לא כמצופה. ברק (2026-09-14):
    # "אם זה קורה באלפי מקומות, יש דפוס שלא זיהינו" - נרשם כאן כעובדה גולמית
    # (בלי I/O בפרסר עצמו), כדי שקוד ה-ingest/batch יוכל לספור/לרשום ביומן.


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
