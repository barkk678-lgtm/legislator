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


class InsertSubsectionIn(BaseModel):
    kind: Literal["subsection"]
    anchor_node_id: str
    text: str


class InsertParagraphIn(BaseModel):
    kind: Literal["paragraph"]
    anchor_node_id: str
    text: str


InsertionIn = InsertSectionIn | InsertSubsectionIn | InsertParagraphIn


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


class InsertPreviewRequestIn(BaseModel):
    edits: list[TextEditIn] = []
    insertions: list[InsertionIn] = []
    anchor_node_id: str
    level: Literal["section", "subsection", "paragraph", "subparagraph"]
