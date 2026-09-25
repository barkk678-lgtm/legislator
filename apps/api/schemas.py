"""מודלי בקשה/תשובה ל-API של משימה 10ב. אין כאן לוגיקה - רק צורת
הנתונים שעוברים בין הלקוח לבין diff_translate.py/insert_preview.py/
packages/amend הקיימים.

עיצוב "בלי מצב בשרת" (כמו במשימה 10): הלקוח שולח בכל בקשה את מלוא
המצב שלו (edits + insertions) - אין session על השרת. כך אפשר להחליף
frontend בלי לגעת ב-API, וגם "ייצוא זמין תמיד" (docx) הוא פשוט אותה
בקשה בדיוק, ל-endpoint אחר.
"""

from typing import Literal

from pydantic import BaseModel


class TextEditIn(BaseModel):
    """עריכה חופשית של טקסט צומת בודד - הטקסט *הנוכחי* (אחרי עריכה),
    לא before/after. ה-before נלקח בשרת מהעץ המקורי (load_law) - לא
    סומכים על הלקוח שישלח את זה נכון.

    field: "text" (גוף הסעיף/פסקה/סעיף קטן) או "margin_title" (כותרת
    השוליים של סעיף - §7.8, ha-hoveret-ha-sgula.pdf). שני שדות שונים
    לגמרי מבחינה משפטית (דפוסי ניסוח נפרדים), גם כשמדובר באותו צומת."""

    node_id: str
    text: str
    field: Literal["text", "margin_title"] = "text"


class InsertSectionIn(BaseModel):
    kind: Literal["section"]
    anchor_node_id: str
    margin_title: str  # חובה - המשתמש מקליד, המערכת לא ממציאה
    text: str
    client_id: str  # מזהה יציב שהלקוח יצר - ראו InsertionIn למטה


class InsertSubsectionIn(BaseModel):
    kind: Literal["subsection"]
    anchor_node_id: str
    text: str
    client_id: str


class InsertParagraphIn(BaseModel):
    kind: Literal["paragraph"]
    anchor_node_id: str
    text: str
    client_id: str


class InsertDefinitionIn(BaseModel):
    kind: Literal["definition"]
    anchor_node_id: str
    text: str
    client_id: str


InsertionIn = InsertSectionIn | InsertSubsectionIn | InsertParagraphIn | InsertDefinitionIn
"""client_id: מזהה יציב שהלקוח יוצר בעצמו (10ב) כשההוספה נוצרת -
נשמר כ-id של הצומת החדש בעץ שחוזר מ-/render (ראו
insert_preview.build_insertion_transform). בלי זה, מזהה הצומת החדש
היה משתנה בכל קריאה חוזרת (מונה גלובלי מצטבר, ראו _fresh_id) - הלקוח
לא היה יכול לשייך DOM<->צומת אחרי רינדור-מחדש מלא של העץ."""


class BillMetaIn(BaseModel):
    """אין submitted_date/source_ref כאן בכוונה (10ב): תאריך ההגשה נקבע
    בפועל על ידי מזכירות הכנסת (לא המשתמש) - render_bill.Bill מספק
    placeholder משלו. מראה המקום (ס"ח) ידוע מראש לכל חוק ב-law_registry -
    main.py שולף אותו משם, לא מהמשתמש."""

    title: str
    initiator: str
    explanatory: list[str] = []  # דברי הסבר - שדה חדש במשימה 10ב


class RenderRequest(BaseModel):
    edits: list[TextEditIn] = []
    insertions: list[InsertionIn] = []
    bill: BillMetaIn
    # הערות שוליים למראי מקום. ברירת מחדל פעילה, כי הכלל נכון
    # לנוסח מוגמר - אבל ניתנת לכיבוי: ביקורת מול 40 הצעות אמיתיות
    # מצאה שרק 3 מהן כוללות מראה מקום בשלב ההנחה (ראו
    # drafting-rules.md §4). ברק, 2026-09-17.
    include_footnotes: bool = True


class InsertPreviewRequestIn(BaseModel):
    edits: list[TextEditIn] = []
    insertions: list[InsertionIn] = []
    anchor_node_id: str
    level: Literal["section", "subsection", "paragraph", "subparagraph", "definition"]


class DraftRequestIn(BaseModel):
    """בקשה לטיוטת LLM (משימה ה, 2026-09-16) - אותם edits/insertions
    כמו RenderRequest, בלי bill: זה בדיוק מה שה-endpoint הזה מייצר
    (title/explanatory), לא קלט לו."""

    edits: list[TextEditIn] = []
    insertions: list[InsertionIn] = []


class QueryTurnIn(BaseModel):
    """תור אחד בשיחת ניסוח השאילתה."""

    role: Literal["user", "assistant"]
    content: str


class QueryDraftRequestIn(BaseModel):
    """בקשה לניסוח שאילתה (משימה ו, 2026-09-16) - ראו query_tool.py.

    **turns הוא המסלול הנכון; topic_description נשאר לתאימות לאחור.**
    הדבקת ההיסטוריה למחרוזת אחת היא בדיוק הבאג שתוקן (ברק,
    2026-09-22): סירוב על שאלה אחת נדבק לשאלות הבאות."""

    topic_description: str = ""
    turns: list[QueryTurnIn] = []
    kind: Literal["רגילה", "דחופה", "ישירה"] = "רגילה"
    minister: str
    mk_name: str
    fit_limit: bool = False   # ש14: "התכנס למגבלת המילים"


class QueryExportRequestIn(BaseModel):
    """ייצוא לוורד - בלי state בשרת (10ב): הלקוח שולח את הטיוטה
    המלאה, כולל עריכות שהמשתמש עשה אחרי draft_query - לא רק מזהה."""

    kind: Literal["רגילה", "דחופה", "ישירה"]
    minister: str
    mk_name: str
    subject: str
    body: str
    # צ5 (26.9.2026): המגדר נשלף **כשהמשתמש ממלא את השם** (/api/queries/
    # mk-gender) ונשלח עם הייצוא. None = לא ידוע -> הצורה הכפולה. הייצוא
    # עצמו לא פונה למאגר הכנסת.
    gender: Literal["זכר", "נקבה"] | None = None


class AgendaDraftRequestIn(BaseModel):
    """בקשה לניסוח הצעה לסדר היום (משימה ז, 2026-09-16) - ראו
    agenda_tool.py. ס3 (26.9.2026): יש סוג - דחופה או רגילה, כמו בטופס של
    הכנסת (AGN_Type) - ויש ייצוא לוורד (ברק, 26.9 - במקום "בלי ייצוא")."""

    topic_description: str
    mk_name: str
    kind: Literal["דחופה", "רגילה"] = "דחופה"


class AgendaExportRequestIn(BaseModel):
    """ס3: ייצוא לוורד על שלד הטופס של הכנסת. בלי state בשרת - הלקוח שולח
    את הטיוטה. היו"ר מגיע עם הטיוטה (ס4 - נשלף כשנוסחה), כדי שההורדה לא
    תמתין למאגר הכנסת; בלי יו"ר - השרת משתמש במטמון/בגיבוי."""

    kind: Literal["דחופה", "רגילה"] = "דחופה"
    mk_name: str
    subject: str
    explanation: list[str]
    gender: Literal["זכר", "נקבה"] | None = None          # של חבר/ת הכנסת
    speaker_name: str | None = None
    speaker_gender: Literal["זכר", "נקבה"] | None = None


class RulesAskRequestIn(BaseModel):
    """בקשת שאלה למומחה התקנון (ברק, 2026-09-17) - ראו rules_expert.py."""

    question: str


class ResearchAskRequestIn(BaseModel):
    """שאלת מחקר בשפה חופשית (משימה 1.4)."""

    question: str
