"""כלי שאילתא (משימה ו, 2026-09-16) - צ'אט שמנסח שאילתה לשר לפי
הפורמט הנהוג, על סמך תיאור חופשי של המשתמש. **לא כפוף לחוקי ברזל
1-2** (לא נוגע בנוסח חוק בכלל - ראו CLAUDE.md, "כלים עתידיים שאינם
נוגעים בנוסח חוק... אינם כפופים לחוקי ברזל 1-2"), משתמש ב-`draft()`
(לא `answer_with_sources()`) כי זו הכוונה/שכתוב של תיאור שהמשתמש
עצמו נתן (חוק ברזל 4, תפקיד 2), לא תשובה עובדתית שדורשת עיגון-מקור.

**מקור הפורמט - נבדק, לא הומצא (ברק ביקש לחפש קודם ולדווח):** כללי
התוכן המחייבים (לא רק מוסכמה) מגיעים ישירות מ-`תקנון הכנסת` עצמו
(נטען כ-fixture אמיתי מוויקיטקסט במשימה ג של אותו לילה, ראו
night-report.md): §46(א) - שאילתה חייבת להיות מנוסחת כשאלה, בעניין
עובדתי שבתחום תפקידי השר; §47(א)(1) - איסור על כינוי/ביטוי פוגע או
גזעני או פגיעה בכבוד הכנסת; §47(א)(2) - איסור על בקשת חוות דעת
כללית/עניין היפותטי/עניין שאינו בתחום תפקידי השר; §47(א)(3) - איסור
על פרטים אישיים פרטיים הפוגעים בפרטיות (למעט שאילתה ישירה); §48(א) -
שאילתה רגילה עד 50 מילים; §49(א) - שאילתה דחופה עד 40 מילים; §50(א) -
שאילתה ישירה בלי הגבלת מילים. **לא נמצא תבנית-כתובת רשמית מפורשת**
(איך פונים בדיוק לשר/מבנה שורת הנושא) - חיפוש בפרוטוקולי הכנסת/
knesset.gov.il לא הניב טופס רשמי נגיש (נחסם/לא קיים גישה ישירה) -
מבנה הכתובת/הנושא כאן הוא מוסכמה סבירה (נושא קצר + "אל"/"מאת"),
**לא** מקור מחייב כמו מגבלות התוכן - ראו night-report.md לפירוט.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
from service import LLMConfigError, LLMRequestError, draft  # noqa: E402
from simple_doc import write_simple_docx  # noqa: E402

QueryKind = Literal["רגילה", "דחופה", "ישירה"]

_WORD_LIMITS: dict[QueryKind, int | None] = {"רגילה": 50, "דחופה": 40, "ישירה": None}

_SUBJECT_MARK = "נושא:"
_BODY_MARK = "גוף:"

_INSTRUCTIONS_TEMPLATE = (
    "אתה מנסח שאילתה פרלמנטרית ישראלית (שאילתה {kind}) של חבר/ת כנסת "
    "אל שר, על סמך תיאור חופשי שנתן המשתמש. אלה כללי החובה (מתוך "
    "תקנון הכנסת, אינם ניתנים למשא ומתן):\n"
    "1. השאילתה חייבת להיות מנוסחת בצורת שאלה (לא קביעה/טענה), על "
    "עניין עובדתי שבתחום תפקידו של השר.\n"
    "2. אסור כינוי או ביטוי פוגע או גזעני, ואסורה כל פגיעה בכבוד "
    "הכנסת - לשון ענינית ומכובדת בלבד.\n"
    "3. אסור לבקש חוות דעת כללית, לעסוק בעניין היפותטי, או לשאול על "
    "עניין שאינו בתחום תפקידי השר.\n"
    "4. אסור לכלול פרטים אישיים פרטיים שפגיעתם בפרטיות (שמות פרטיים "
    "של אזרחים, מספרי זהות וכו').\n"
    "5. גוף השאילתה (בלי שורת הנושא) {word_limit_instruction}\n"
    "6. **גוף השאילתה לעולם אינו נוקב בשם השר ואינו פונה אליו.** "
    "הנמען נקבע בשדה נפרד ומוזרק למסמך בקוד, לא על ידך. אל תפתח "
    'ב"לשר X" או "לכבוד השר", ואל תכתוב את שם התיק בשום מקום בגוף - '
    "כתוב את השאלה עצמה בלבד.\n\n"
    "החזר בדיוק בפורמט הבא, שתי שורות בלבד:\n"
    f"{_SUBJECT_MARK} <נושא קצר, עד 8 מילים>\n"
    f"{_BODY_MARK} <גוף השאילתה המנוסח כשאלה>\n\n"
    "אם התיאור שהמשתמש נתן מבקש דבר שאסור לפי הכללים למעלה (חוות דעת "
    "כללית, עניין היפותטי, לשון פוגענית וכו') - נסח מחדש בעדינות "
    'לעניין עובדתי וממוקד במקום לסרב, אלא אם באמת אי אפשר: במקרה כזה החזר "לא ניתן לנסח שאילתה: <הסבר קצר>" בשורה יחידה.'
)


# פנייה לנמען בפתח גוף השאילתה. **הנמען אינו נתון שהמודל קובע** -
# המשתמש בוחר שר בשדה, והשם מוזרק למסמך ב-write_query_docx. נמצא
# בבדיקה מול 10 שאלות אמיתיות (2026-09-18) שהמודל פתח גוף שאילתה
# ב"לשר הפנים - " בזמן שהנמען שנבחר היה השר להגנת הסביבה: הוא הסיק
# מהנושא מי השר "הנכון" ודרס את בחירת המשתמש בתוך הטקסט.
#
# **התקלה לא הייתה דטרמיניסטית** - היא הופיעה פעם אחת מתוך ארבע
# הרצות של אותה שאלה בדיוק. לכן ההנחיה לבדה אינה מספיקה, וזה
# המקום שבו העובדה מופרדת מהניסוח בקוד ולא בבקשה.
_ADDRESSEE_PREFIX_RE = re.compile(
    r"^\s*(?:לכבוד\s+)?(?:ל|אל\s+)?(?:ה?שר(?:ת|ה)?|ה?ממונה)\b[^\n]{0,60}?"
    r"\s*[-–—:,]\s*"
)


def _strip_addressee(body: str) -> tuple[str, str]:
    """מסירה פנייה לנמען מתחילת גוף השאילתה. מחזירה (גוף, מה שהוסר).

    **הסרה ולא דחייה:** מה שנשאר אחרי הקידומת הוא השאלה עצמה, מנוסחת
    היטב - אין סיבה לזרוק טיוטה שלמה בגלל קידומת. ההסרה מדווחת החוצה
    (`removed_addressee`) ואינה שקטה.

    מטופלת רק **קידומת בפתח**, שהיא הדפוס שנצפה וההסרה בה בטוחה.
    אזכור שר באמצע הגוף עלול להיות תוכן השאלה עצמה ("מה עשה משרד
    הפנים") ולכן רק מסומן, לא נוגעים בו - ראו _mentions_minister."""
    match = _ADDRESSEE_PREFIX_RE.match(body)
    if not match:
        return body, ""
    stripped = body[match.end():].lstrip()
    if not stripped:
        return body, ""  # הכול היה קידומת - לא נוגעים, שהמשתמש יראה
    return stripped[0].upper() + stripped[1:] if stripped[:1].isascii() else stripped, match.group(0).strip()


class QueryDraftError(Exception):
    """שכבת אפליקציה - LLM לא זמין/נכשל, או המודל דיווח שאי אפשר לנסח."""


def _instructions(kind: QueryKind) -> str:
    limit = _WORD_LIMITS[kind]
    word_limit_instruction = (
        f"חייב להיות עד {limit} מילים בדיוק (מגבלת תקנון הכנסת, לא המלצה)."
        if limit
        else "אינו מוגבל במספר מילים (שאילתה ישירה)."
    )
    return _INSTRUCTIONS_TEMPLATE.format(kind=kind, word_limit_instruction=word_limit_instruction)


def _word_count(text: str) -> int:
    return len(text.split())


def draft_query(*, topic_description: str, kind: QueryKind, minister: str, mk_name: str) -> dict:
    """topic_description: תיאור חופשי של המשתמש (על מה לשאול). מחזירה
    dict עם subject/body/word_count/within_limit - **לא** חוסמת אם
    חורג מהמגבלה (המשתמש רואה ועורך), רק מסמנת within_limit=False כדי
    שהממשק יתריע במפורש, לא ינחש/יחתוך מילים בשקט."""
    try:
        raw = draft(instructions=_instructions(kind), content=topic_description, max_tokens=400)
    except (LLMConfigError, LLMRequestError) as e:
        raise QueryDraftError(f"שכבת ה-LLM לא זמינה: {e}") from None

    if raw.startswith("לא ניתן לנסח שאילתה"):
        raise QueryDraftError(raw)

    subject_match = re.search(rf"{re.escape(_SUBJECT_MARK)}\s*(.+)", raw)
    body_match = re.search(rf"{re.escape(_BODY_MARK)}\s*(.+)", raw, re.DOTALL)
    if not subject_match or not body_match:
        raise QueryDraftError(f"תשובת ה-LLM לא בפורמט הצפוי (נושא:/גוף:): {raw!r}")

    subject = subject_match.group(1).strip()
    body, removed_addressee = _strip_addressee(body_match.group(1).strip())
    limit = _WORD_LIMITS[kind]
    wc = _word_count(body)
    return {
        "kind": kind,
        "minister": minister,
        "mk_name": mk_name,
        "subject": subject,
        "body": body,
        "removed_addressee": removed_addressee,
        "word_count": wc,
        "word_limit": limit,
        "within_limit": limit is None or wc <= limit,
    }


def write_query_docx(query: dict, *, skeleton: Path, out: Path) -> Path:
    meta_lines = [
        f"אל: השר {query['minister']}",
        f"מאת: {query['mk_name']}, חבר/ת הכנסת",
        f"נושא: {query['subject']}",
    ]
    return write_simple_docx(
        title=f"שאילתה {query['kind']}",
        meta_lines=meta_lines,
        paragraphs=[query["body"]],
        skeleton=skeleton,
        out=out,
    )
