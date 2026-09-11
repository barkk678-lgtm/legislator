"""ייצוג צומת בעץ חוק. ראו TASKS.md משימה 2.

number הוא מספר הסעיף *בחוק המתוקן עצמו* (3א, 34כד, (א), (1)) - מרחב
מספור נפרד לגמרי ממספר הסעיף הרץ בהצעת החוק (1., 2., 3...), שמטופל
כבר ב-packages/render/render_bill.py (Line.number). אסור לבלבל בין
שני המרחבים.
"""

from dataclasses import dataclass, field


@dataclass
class LegislativeNode:
    id: str  # מזהה יציב: "penal-1977/s4/a/1"
    node_type: str  # chapter|section|subsection|paragraph|subparagraph|definition
    number: str  # "4", "3א", "34כד", "(א)", "(1)" - מספור החוק המתוקן בלבד
    margin_title: str | None  # כותרת שוליים - רק לסעיף ראשי
    text: str
    children: list["LegislativeNode"] = field(default_factory=list)
    source_ref: str = ""  # מקור + תאריך נוסח
