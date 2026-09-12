"""ייצוג צומת בעץ חוק. ראו TASKS.md משימה 2, ומשימה 3 (recon על ויקיטקסט).

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
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LegislativeNode:
    id: str  # מזהה יציב: "penal-1977/s4/a/1"
    node_type: str  # chapter|section|subsection|paragraph|subparagraph|definition
    number: str  # "4", "3א", "34כד", "(א)", "(1)" - מספור החוק המתוקן בלבד
    margin_title: str | None  # כותרת שוליים - רק לסעיף ראשי
    text: str
    children: list["LegislativeNode"] = field(default_factory=list)
    source_ref: str = ""  # מקור + תאריך נוסח
    is_normative: bool = True  # False = הערת עורך, לא נוסח חוק
    status: Literal["active", "repealed", "merged"] = "active"
