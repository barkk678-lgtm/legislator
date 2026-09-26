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
from service import LLMConfigError, LLMRequestError, ModelUnavailable, draft, draft_conversation  # noqa: E402
from query_tool import _normalize_for_support, unsupported_source_claims  # noqa: E402

# ס3 (26.9.2026): **המבנה של הטופס שהכנסת עצמה משתמשת בו** (reference/הצעה
# לסדר יום (8).docx, (10).docx): "לכבוד / יו"ר הכנסת, ח"כ ... / אדוני היושב
# ראש, / אבקש להעלות על סדר יומה של הכנסת הצעה דחופה בנושא: / <נושא> / דברי
# הסבר: / <הסבר> / בכבוד רב, / חבר/ת הכנסת ...". **הבקשה לדיון היא המשפט
# הקבוע של הטופס** - לא שורה שהמודל מנסח (עד כאן "בקשה: מוצע כי הכנסת
# תדון..."). המודל מנסח רק נושא ודברי הסבר; כל השאר - בקוד.
_SUBJECT_MARK = "נושא:"
_EXPLANATION_MARK = "דברי הסבר:"

_INSTRUCTIONS = (
    "אתה מנסח הצעה לסדר היום של חבר/ת כנסת, על סמך תיאור חופשי שנתן "
    "המשתמש. כללים (מתוך תקנון הכנסת ונוהג פרלמנטרי מקובל):\n"
    "1. חובה לצרף דברי הסבר להצעה (תקנון הכנסת §52(א)) - לא מספיק נושא בלבד.\n"
    "2. לשון ענינית ומכובדת - אסור כינוי או ביטוי פוגע או גזעני, "
    "ואסורה פגיעה בכבוד הכנסת.\n"
    "3. ההצעה מבקשת לקיים דיון - לא מכריעה דבר בעצמה. את משפט הבקשה "
    "(\"אבקש להעלות על סדר יומה של הכנסת הצעה בנושא\") הטופס כותב - אל "
    "תכתוב אותו, ואל תכתוב פנייה ליו\"ר, תאריך או חתימה.\n\n"
    "החזר בדיוק בפורמט הבא:\n"
    f"{_SUBJECT_MARK} <נושא ההצעה, שורה אחת>\n"
    f"{_EXPLANATION_MARK} <דברי ההסבר: למה הנושא חשוב לדיון עכשיו - פסקה אחת עד "
    "שלוש, כל פסקה בשורה נפרדת>\n\n"
    "אם התיאור שהמשתמש נתן כולל לשון פוגענית/גזענית - נסח מחדש "
    'בעדינות ללשון ענינית במקום לסרב, אלא אם באמת אי אפשר: במקרה כזה '
    'החזר "לא ניתן לנסח הצעה לסדר: <הסבר קצר>" בשורה יחידה.'
)

AGENDA_KINDS = ("דחופה", "רגילה")


class AgendaDraftError(Exception):
    """שכבת אפליקציה - LLM לא זמין/נכשל, או המודל דיווח שאי אפשר לנסח."""


class AgendaUnavailable(ModelUnavailable, AgendaDraftError):
    """המודל לא זמין: str() - ההודעה בעברית למשתמש; reason - הסיבה, ל-chat_log."""


# ── ס5 (ברק, 26.9): השומר נגד פרט חדש - אותו שומר כמו בשאילתות ──────
# נמצא באתר החי (26.9): על "מחסור חמור בשוטרים בנגב, תחנות נסגרות בלילה"
# המודל כתב "מתרבים הדיווחים על מחסור..." ו"...לצד **עלייה במקרי פשיעה**
# ואירועים פליליים באזור" - שתי טענות עובדתיות שהמשתמש לא אמר, בהצעה
# שמוגשת בשם חבר/ת כנסת.
#
# **הכלל: פרט חדש נתפס, ניסוח מחדש מותר.** "תחנות נסגרות בלילה" ->
# "סגירת תחנות בשעות הלילה" הוא ניסוח. מה שנתפס:
# - מקור, גוף או מספר שלא נמסרו - בדיוק השומר של השאילתות
#   (query_tool.unsupported_source_claims);
# - ובהצעה לסדר, שבה המודל כותב גם "למה עכשיו": **טענה על מגמה או על
#   דיווחים** - עלייה, ירידה, זינוק, "מתרבים", נתונים, דיווחים, פרסומים.
#   מילה כזו נחשבת נתמכת אם אותו שורש מופיע בדברי המשתמש.
_CLAIM_ROOTS = (
    ("עלייה", ("עלייה", "עליה", "עלו", "עולה", "עלה", "גובר", "גוברת")),
    ("עליה", ("עלייה", "עליה", "עלו", "עולה", "עלה", "גובר", "גוברת")),
    ("ירידה", ("ירידה", "ירד", "יורד")),
    ("גידול", ("גידול", "גדל", "גדלה", "גדלו")),
    ("זינוק", ("זינוק", "זינק", "זינקו")),
    ("הכפל", ("הכפל", "כפול")),
    ("שיא", ("שיא",)),
    ("מתרב", ("מתרב", "רבים", "הרבה", "ריבוי")),
    ("נתונ", ("נתונ",)),
    ("סטטיסט", ("סטטיסט",)),
    ("אחוז", ("אחוז", "%")),
    ("דיווח", ("דיווח", "דווח", "כתב", "פורסם", "פרסום", "שודר", "תחקיר")),
    ("דווח", ("דיווח", "דווח", "כתב", "פורסם", "פרסום", "שודר", "תחקיר")),
    ("פורסם", ("דיווח", "דווח", "כתב", "פורסם", "פרסום", "שודר", "תחקיר")),
    ("פרסומ", ("דיווח", "דווח", "כתב", "פורסם", "פרסום", "שודר", "תחקיר")),
    ("תלונ", ("תלונ", "התלונ")),
    # נמצא בהרצה מקומית (26.9): "סגירת סניפי דואר ביישובים קטנים בגליל" ->
    # "בחודשים האחרונים מסתמנת מגמה של סגירת סניפים" - מתי ו"מגמה" לא נמסרו.
    ("מגמ", ("מגמ",)),
    ("מסתמנ", ("מסתמנ", "מגמ")),
    ("האחרונ", ("האחרונ", "לאחרונה")),
    ("לאחרונה", ("האחרונ", "לאחרונה")),
)

_REWRITE_WITHOUT = (
    "בדברי ההסבר הופיעו פרטים שלא אמרתי: {items}. נסח מחדש את ההצעה בלי "
    "אף אחד מהם - בלי מגמה, נתון, דיווח או מקור שלא מסרתי. אל תחליף אותם "
    "בפרט אחר; תאר רק את מה שאמרתי ולמה הוא מצדיק דיון. החזר שוב בפורמט "
    "המלא (נושא:/דברי הסבר:)."
)


def unsupported_agenda_claims(text: str, user_text: str) -> list[str]:
    """פרטים בנושא ובדברי ההסבר שאין להם זכר בדברי המשתמש. פונקציה טהורה."""
    # "דיון" הוא מקור בשאילתה ("בדיון שהתקיים"), אבל בהצעה לסדר הוא מהות
    # הבקשה ("יש לקיים דיון"). דיון בוועדה עדיין נתפס - על "ועד".
    found = set(unsupported_source_claims(text, user_text)) - {"דיון"}
    haystack = _normalize_for_support(user_text)
    for marker, supports in _CLAIM_ROOTS:
        if marker in (text or "") and not any(s in haystack for s in supports):
            found.add(marker)
    return sorted(found)


def _parse(raw: str) -> tuple[str, list[str]]:
    subject_match = re.search(rf"{re.escape(_SUBJECT_MARK)}\s*(.+)", raw)
    explanation_match = re.search(rf"{re.escape(_EXPLANATION_MARK)}\s*(.+)", raw, re.DOTALL)
    if not subject_match or not explanation_match:
        raise AgendaDraftError(f"תשובת ה-LLM לא בפורמט הצפוי (נושא:/דברי הסבר:): {raw!r}")
    explanation = [ln.strip() for ln in explanation_match.group(1).split("\n") if ln.strip()]
    return subject_match.group(1).strip(), explanation


def draft_agenda(*, topic_description: str, mk_name: str, kind: str = "דחופה") -> dict:
    try:
        raw = draft(instructions=_INSTRUCTIONS, content=topic_description, max_tokens=700)
    except (LLMConfigError, LLMRequestError) as e:
        raise AgendaUnavailable(reason=str(e)) from None

    if raw.startswith("לא ניתן לנסח הצעה לסדר"):
        raise AgendaDraftError(raw)
    subject, explanation = _parse(raw)

    invented = unsupported_agenda_claims("\n".join([subject, *explanation]), topic_description)
    if invented:
        # כמו בשאילתות: קודם ניסוח מחדש בלי הפרט, ורק אז עצירה גלויה.
        turns = [{"role": "user", "content": topic_description},
                 {"role": "assistant", "content": raw},
                 {"role": "user", "content": _REWRITE_WITHOUT.format(items=", ".join(invented))}]
        try:
            retry = draft_conversation(instructions=_INSTRUCTIONS, turns=turns, max_tokens=700)
            subject, explanation = _parse(retry)
            invented = unsupported_agenda_claims("\n".join([subject, *explanation]), topic_description)
        except (LLMConfigError, LLMRequestError, AgendaDraftError, ValueError):
            pass
        if invented:
            raise AgendaDraftError(
                "לא ניתן לנסח הצעה לסדר: הניסוח כלל פרט שלא הופיע בדבריכם - "
                f"{', '.join(invented)}. ניסיתי לנסח מחדש בלעדיו וזה חזר. ההצעה "
                "מוגשת בשם חבר/ת הכנסת, ולכן כל עובדה בדברי ההסבר חייבת להגיע ממה "
                "שמסרתם. אפשר לציין את הפרט במפורש, או לבקש ניסוח בלעדיו."
            )

    return {
        "kind": kind if kind in AGENDA_KINDS else "דחופה",
        "mk_name": mk_name,
        "subject": subject,
        "explanation": explanation,
    }
