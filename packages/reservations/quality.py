"""מצב האיכות: נקודות עיגון מובחנות, כל אחת הסתייגות שעומדת בפני
עצמה.

**ההבדל מהותי ממצב הכמות, ולא כמותי.** מצב הכמות מייצר וריאציות על
אותו ערך; מצב האיכות מנסח שינוי מהותי אחד לכל נקודה. לכן כאן המודל
**כן** כותב טקסט, וכאן - ורק כאן - שומר 86(ד)(2) חל.

**המסלול, לפי הסדר, ואף שלב אינו ניתן לדילוג:**

1. נקודות העיגון נבחרות **דטרמיניסטית** מעץ הסעיף - סעיף קטן,
   פסקה, הגדרה, תנאי. המודל אינו בוחר על מה להסתייג.
2. המודל מנסח הסתייגות לכל נקודה.
3. **כל הסתייגות עוברת את השומרים. מה שנחסם נזרק ואינו מוחזר** -
   לא עם אזהרה, לא עם סימון (CLAUDE.md חוק ברזל 7).
4. מה שנשאר מוחזר עם מספר הסעיף, בסדר נקודות העיגון.
"""

from __future__ import annotations

import json
import re

from guards import screen_bill_name, screen_content, screen_negates_bill
from model import DraftedReservation

_INSTRUCTIONS = """אתה מנסח הסתייגויות להצעת חוק, לפי תקנון הכנסת.

תקבל נוסח של סעיף אחד ורשימה סגורה של נקודות עיגון בתוכו. לכל נקודה,
ורק לנקודות שברשימה, נסח הסתייגות אחת.

הסתייגות היא **תיקון מוצע לנוסח** - לא נאום ולא נימוק. הצורות
המקובלות: 'במקום "X" יבוא "Y".' / 'אחרי "X" יבוא "Y".' /
'X – יימחק.' / 'בסופו יבוא "Y".'

החזר JSON בלבד - מערך של אובייקטים:
[{"point": <מספר הנקודה>, "text": "<ההסתייגות>", "rationale": "<שורה אחת>"}]

כללים מחייבים:
- הסתייגות לא תשלול את עצם ההצעה, ולא תיגע בשם ההצעה.
- לשון עניינית ומכובדת בלבד. אסור כינוי או ביטוי פוגע או גזעני,
  ואסורה כל פגיעה בכבוד הכנסת.
- אל תמציא מספרי סעיפים או ציטוטים שאינם בנוסח שקיבלת.
- בלי טקסט מחוץ ל-JSON."""

_POINT_MARKERS = re.compile(r"^\s*(\([א-ת]{1,2}\)|\(\d{1,2}\)|\"[^\"]{2,40}\"\s*–)")


def anchor_points(section_text: str) -> list[str]:
    """נקודות עיגון מובחנות בסעיף - **דטרמיניסטי**, בלי מודל.

    נקודה היא יחידה שאפשר להסתייג עליה בנפרד: סעיף קטן, פסקה,
    הגדרה. אם אין חלוקה פנימית, הסעיף כולו הוא נקודה אחת."""
    points = [
        line.strip()
        for line in re.split(r"(?<=[.;])\s+", section_text)
        if line.strip() and _POINT_MARKERS.match(line.strip())
    ]
    return points or ([section_text.strip()] if section_text.strip() else [])


def quality_reservations(
    section_text: str,
    *,
    section_number: str = "",
    section_heading: str = "",
    draft_fn=None,
    screen_fn=None,
    screen_draft_fn=None,
) -> tuple[list[DraftedReservation], list[str]]:
    """מחזירה (הסתייגויות שעברו, סיבות חסימה). **הנחסמות אינן
    מוחזרות** - רק ספירה וסיבה, לדיווח פנימי, לא להצגה למשתמש."""
    points = anchor_points(section_text)
    if not points:
        return [], []

    if draft_fn is None:
        import sys  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llm"))
        from service import draft as draft_fn  # noqa: PLC0415

    listing = "\n".join(f"{i + 1}. {p[:200]}" for i, p in enumerate(points))
    content = f"--- נוסח הסעיף ---\n{section_text}\n\n--- נקודות עיגון ---\n{listing}"
    raw = draft_fn(instructions=_INSTRUCTIONS, content=content, max_tokens=1600).strip()
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return [], ["הניסוח לא חזר כ-JSON תקין"]

    # `screen_draft_fn` מעביר את **התחבורה** של קריאת הסינון בלבד -
    # ההכרעה ("תקין" בלבד עובר, כל השאר חוסם) נשארת כולה בתוך
    # screen_content. זה נדרש כדי שקריאת הסינון תיספר בעלות: היא
    # קריאה נפרדת בתשלום לכל הסתייגות, ודיווח שמתעלם ממנה מציג
    # כמחצית מהעלות האמיתית.
    if screen_fn is not None:
        screen = screen_fn
    elif screen_draft_fn is not None:
        def screen(item):
            return screen_content(item, draft_fn=screen_draft_fn)
    else:
        screen = screen_content
    passed: list[DraftedReservation] = []
    blocked: list[str] = []
    allowed_points = set(range(1, len(points) + 1))
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        try:
            point = int(entry.get("point"))
        except (TypeError, ValueError):
            continue
        if point not in allowed_points:
            blocked.append("נקודת עיגון שאינה ברשימה שנשלחה")
            continue
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        item = DraftedReservation(
            text=text, section_number=section_number,
            rationale=str(entry.get("rationale", "")).strip(),
        )
        for verdict in (
            screen(item),
            screen_negates_bill(text, section_heading=section_heading),
            screen_bill_name(text),
        ):
            if not verdict.allowed:
                blocked.append(f"{verdict.rule}: {verdict.reason}")
                break
        else:
            passed.append(item)
    return passed, blocked
