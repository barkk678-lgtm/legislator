"""טיוטת דברי הסבר, כשהמשתמש לא הזין דברי הסבר משלו.

טהור ודטרמיניסטי (אין LLM, אין ניחוש כוונה): כל משפט נגזר ישירות
מ-side_heading/text של Line-ים שכבר נוסחו על ידי engine.amend() - לא
מנחש למה השינוי נעשה, רק מתאר בקצרה מה נעשה. המשתמש עדיין עורך את
הטיוטה בעצמו בוורד לפני הגשה (ראו TASKS.md משימה 10ב, משוב המשתמש:
"אני מצפה ממך לדעת לנסח דברי הסבר, גם אם כטיוטה").
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
from render_bill import Line  # noqa: E402

_ADD_PREFIX = "הוספת "
_FIX_PREFIX = "תיקון "


def draft_explanatory_notes(lines: list[Line]) -> list[str]:
    """פסקה אחת לכל סעיף שנוגע בו (side_heading ייחודי, לפי סדר
    הופעה) - לא נספר יותר מפעם אחת אם לסעיף כמה הוראות. מבוססת רק על
    מה שכבר קיים ב-Line (side_heading, text/text_after) - לא דיף חדש."""
    paragraphs: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        heading = ln.side_heading
        if not heading or heading in seen:
            continue
        seen.add(heading)
        combined = ln.text + ln.text_after
        if heading.startswith(_ADD_PREFIX):
            what = heading[len(_ADD_PREFIX):]
            paragraphs.append(f"מוצע להוסיף לחוק את {what}.")
        elif "בכותרת השוליים" in combined:
            what = heading[len(_FIX_PREFIX):] if heading.startswith(_FIX_PREFIX) else heading
            paragraphs.append(f"מוצע לשנות את כותרת השוליים של {what}.")
        else:
            what = heading[len(_FIX_PREFIX):] if heading.startswith(_FIX_PREFIX) else heading
            paragraphs.append(f"מוצע לתקן את {what}.")
    return paragraphs
