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
    סומכים על הלקוח שישלח את זה נכון."""

    node_id: str
    text: str


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
    title: str
    initiator: str
    submitted_date: str
    source_ref: str  # מראה מקום - שדה חובה (ראו law_registry.LawConfig)
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
