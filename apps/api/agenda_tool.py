"""כלי הצעה לסדר היום (משימה ז, 2026-09-16) - זהה מבנית לכלי השאילתא
(query_tool.py) **בלי ייצוא** (ברק, במפורש: "זהה ל-ו' בלי ייצוא") -
נושא, נימוק (דברי הסבר), ובקשה לדיון. לא כפוף לחוקי ברזל 1-2 (לא
נוגע בנוסח חוק). משתמש ב-`draft()` (לא `answer_with_sources()`) -
אותו נימוק בדיוק כמו query_tool.py: זו הכוונה/שכתוב של תיאור שהמשתמש
נתן, לא תשובה עובדתית ממקור.

**מקור הפורמט - נבדק בתקנון הכנסת עצמו (אותו fixture ממשימה ג):**
§52(א) - "חבר הכנסת יצרף להצעה דברי הסבר" - חובה לצרף נימוק/דברי
הסבר, לא רק כותרת נושא. **בניגוד לשאילתה - אין מגבלת מילים מפורשת**
להצעה לסדר בסעיפים שנבדקו (§52). מכסה סיעתית (§99) קיימת אך לא
רלוונטית כאן (לא עניין ניסוח, עניין הגשה בפועל דרך המזכירות - מחוץ
להיקף כלי הניסוח). איסור לשון פוגענית/גזענית - לא נמצא סעיף ספציפי
להצעה לסדר בחיפוש שבוצע; הכלל שמוחל כאן מגיע מ-§47(א)(1) (שאילתות)
כקו-מנחה כללי-סביר ל"כבוד הכנסת" שסביר שחל גם כאן, **לא** כי אותו
סעיף חל פורמלית - מסומן בבירור, לא מוצג כמצוטט-במדויק.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
from service import LLMConfigError, LLMRequestError, draft  # noqa: E402

_SUBJECT_MARK = "נושא:"
_REASONING_MARK = "נימוק:"
_REQUEST_MARK = "בקשה:"

_INSTRUCTIONS = (
    "אתה מנסח הצעה לסדר היום של חבר/ת כנסת, על סמך תיאור חופשי שנתן "
    "המשתמש. כללים (מתוך תקנון הכנסת ונוהג פרלמנטרי מקובל):\n"
    "1. חובה לצרף דברי הסבר/נימוק להצעה (תקנון הכנסת §52(א)) - לא "
    "מספיק נושא בלבד.\n"
    "2. לשון ענינית ומכובדת - אסור כינוי או ביטוי פוגע או גזעני, "
    "ואסורה פגיעה בכבוד הכנסת.\n"
    "3. ההצעה מבקשת לקיים דיון בנושא מסוים - לא מכריעה/קובעת דבר "
    "בעצמה, רק מציעה לדון.\n\n"
    "החזר בדיוק בפורמט הבא, שלוש שורות בלבד:\n"
    f"{_SUBJECT_MARK} <נושא קצר, עד 10 מילים>\n"
    f"{_REASONING_MARK} <נימוק/דברי הסבר - כמה משפטים, למה הנושא חשוב לדיון>\n"
    f"{_REQUEST_MARK} <ניסוח הבקשה לדיון עצמה, משפט אחד - 'מוצע כי הכנסת תדון ב...'>\n\n"
    "אם התיאור שהמשתמש נתן כולל לשון פוגענית/גזענית - נסח מחדש "
    'בעדינות ללשון ענינית במקום לסרב, אלא אם באמת אי אפשר: במקרה כזה '
    'החזר "לא ניתן לנסח הצעה לסדר: <הסבר קצר>" בשורה יחידה.'
)


class AgendaDraftError(Exception):
    """שכבת אפליקציה - LLM לא זמין/נכשל, או המודל דיווח שאי אפשר לנסח."""


def draft_agenda(*, topic_description: str, mk_name: str) -> dict:
    try:
        raw = draft(instructions=_INSTRUCTIONS, content=topic_description, max_tokens=500)
    except (LLMConfigError, LLMRequestError) as e:
        raise AgendaDraftError(f"שכבת ה-LLM לא זמינה: {e}") from None

    if raw.startswith("לא ניתן לנסח הצעה לסדר"):
        raise AgendaDraftError(raw)

    subject_match = re.search(rf"{re.escape(_SUBJECT_MARK)}\s*(.+)", raw)
    reasoning_match = re.search(rf"{re.escape(_REASONING_MARK)}\s*(.+?)(?={re.escape(_REQUEST_MARK)}|$)", raw, re.DOTALL)
    request_match = re.search(rf"{re.escape(_REQUEST_MARK)}\s*(.+)", raw, re.DOTALL)
    if not subject_match or not reasoning_match or not request_match:
        raise AgendaDraftError(f"תשובת ה-LLM לא בפורמט הצפוי (נושא:/נימוק:/בקשה:): {raw!r}")

    return {
        "mk_name": mk_name,
        "subject": subject_match.group(1).strip(),
        "reasoning": reasoning_match.group(1).strip(),
        "request_text": request_match.group(1).strip(),
    }
