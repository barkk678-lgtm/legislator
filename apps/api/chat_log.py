"""צ7 (26.9.2026) - שמירת כל השיחות בדאטהבייס, לפי כלי.

לכל הודעה: הכלי, מזהה שיחה, זמן, ההודעה של המשתמש, התשובה, והסיווג -
חולין, עלבון, ענייני, סירוב, "לא מצאתי", תשובה שהשומר החליף, תקלה. המטרה:
לנטר טעויות נפוצות, שאלות שאין להן תשובה וסירובים (ממשק ניהול - בהמשך).

- **אין הרשמה**: user_id הוא מזהה אנונימי שהדפדפן יוצר (localStorage).
- **רק השרת כותב וקורא** - בטבלה RLS בלי אף policy, ו-anon/authenticated
  בלי הרשאות (supabase/migrations/20260926120000_chat_log.sql).
- **כתיבה במאמץ הטוב ביותר.** כישלון (רשת, מפתח) נרשם ביומן ואינו נוגע
  בתשובה למשתמש. הרישום רץ אחרי שהתשובה נשלחה (BackgroundTasks / סוף הזרם).
- לפני השקה: תנאי השימוש חייבים לומר שהשיחות נשמרות (docs/open-gaps.md).
"""

from __future__ import annotations

import logging

import httpx

from law_registry import _supabase_config

log = logging.getLogger(__name__)

KINDS = {"chitchat", "insult", "substantive", "refused", "not_found", "guard_replaced", "error"}
_MAX = 20000   # תו - הודעה או תשובה ארוכה נחתכת, לא נזרקת


def _post(row: dict) -> None:
    url, key = _supabase_config()
    resp = httpx.post(f"{url}/rest/v1/chat_log", json=row, timeout=8.0,
                      headers={"apikey": key, "Authorization": f"Bearer {key}",
                               "Content-Type": "application/json", "Prefer": "return=minimal"})
    resp.raise_for_status()


def log_turn(*, tool: str, conversation_id: str | None, user_id: str | None,
             message: str, reply: str | None, kind: str, meta: dict | None = None,
             post=None) -> bool:
    """True אם נשמר. לא זורק לעולם."""
    row = {
        "tool": tool,
        "conversation_id": (conversation_id or None) and conversation_id[:100],
        "user_id": (user_id or None) and user_id[:100],
        "user_message": (message or "")[:_MAX],
        "reply": None if reply is None else reply[:_MAX],
        "kind": kind if kind in KINDS else "error",
        "meta": meta or {},
    }
    try:
        (post or _post)(row)
        return True
    except Exception as e:  # noqa: BLE001 - הרישום לעולם לא מפיל שיחה
        log.warning("רישום השיחה נכשל (%s): %s", tool, e)
        return False


def rules_kind(refused: bool, reason: str | None) -> str:
    """הסיווג של תשובת מומחה התקנון, לפי מה ששומר הציטוט החליט."""
    if not refused:
        return "substantive"
    r = reason or ""
    if "נדחתה כ" in r:                       # שומר הציטוט דחה את מה שהמודל כתב
        return "guard_replaced"
    if "[דעה]" in r or "[מחוץ לתחום]" in r:  # המודל סירב - שאלת דעה / מחוץ לתחום
        return "refused"
    return "not_found"


def draft_error_kind(detail: str) -> str:
    """שאילתה/הצעה לסדר: 422 מהכלי. "הניסוח כלל פרט שלא הופיע" - השומר חסם."""
    if "הניסוח כלל פרט שלא הופיע" in detail:
        return "guard_replaced"
    if detail.startswith("לא ניתן לנסח"):
        return "refused"
    return "error"
