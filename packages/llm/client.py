"""קריאה גולמית ל-Anthropic Messages API - httpx בלבד (כבר תלות קיימת,
ראו apps/api/law_registry.py), בלי SDK חדש - עקבי עם "אל תוסיף תלויות"
(TASKS.md, night-report היסטורי). **הקובץ היחיד בכל הריפו שבו מותר
לבנות בקשת HTTP למודל שפה** - service.py הוא הממשק הציבורי היחיד
שקוראים אחרים משתמשים בו (ראו __init__.py/CLAUDE.md).

מפתח: ANTHROPIC_API_KEY, נקרא רק בזמן קריאה בפועל (לא בייבוא המודול) -
אותו עיקרון בדיוק כמו SUPABASE_SERVICE_ROLE_KEY ב-law_registry.py:
שגיאה ברורה ומיידית אם חסר, לפני כל קריאת רשת, לא כישלון שקט/מבלבל
באמצע בקשה.

thinking מכובה במפורש (type=disabled) - נבדק בפועל (2026-09-16):
בלי זה, המודל (claude-sonnet-5) מכניס content block מסוג "thinking"
לפני הטקסט, שיכול לצרוך את כל max_tokens ולהחזיר תשובה ריקה
(stop_reason="max_tokens") בלי טקסט בפועל בכלל - לא מתאים לשירות
מבני שדורש תשובת טקסט ודאית בכל קריאה.
"""

import os
import time
from dataclasses import dataclass

import httpx

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"


class LLMConfigError(Exception):
    """ANTHROPIC_API_KEY חסר - זהה בכוונה ל-RuntimeError שקוראים אחרים
    כבר יודעים לתפוס בדפוס law_registry._supabase_config."""


class LLMRequestError(Exception):
    """כשל רשת/HTTP אחרי מיצוי הניסיונות, או תשובה לא-תקינה מה-API."""


@dataclass
class RawCompletion:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str


def _api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMConfigError(
            "חסר משתנה סביבה ANTHROPIC_API_KEY - נדרש לכל קריאה לשכבת ה-LLM "
            "(packages/llm). בלי זה, כל הכלים שתלויים בה (דברי הסבר, שאילתא, "
            "הצעה לסדר) לא זמינים - זו שגיאת תצורה, לא כשל בקורפוס."
        )
    return key


def complete(
    *,
    system: str,
    user_message: str,
    max_tokens: int = 1500,
    model: str = DEFAULT_MODEL,
) -> RawCompletion:
    """קריאה סינכרונית בודדת. 3 ניסיונות עם השהיה גדלה על כשל רשת/5xx
    (אותו דפוס בדיוק כמו law_registry._fetch_all_pages/load_corpus_to_
    supabase_rest._rest_request - לא דפוס חדש). 4xx (מפתח שגוי, קלט
    לא תקין) לא מנסה שוב - זה לא כשל חולף.

    בלי `temperature` בכוונה - נבדק בפועל (2026-09-16): claude-sonnet-5
    דוחה את הפרמטר לגמרי (HTTP 400 "`temperature` is deprecated for
    this model") - לא רק לא-נתמך בערך המסוים, השדה עצמו אסור."""
    key = _api_key()
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": _API_VERSION,
        "content-type": "application/json",
    }

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(_API_URL, json=body, headers=headers)
            if resp.status_code >= 500:
                raise LLMRequestError(f"HTTP {resp.status_code} מ-Anthropic: {resp.text[:300]}")
            if resp.status_code >= 400:
                raise LLMRequestError(f"HTTP {resp.status_code} מ-Anthropic (לא-חולף): {resp.text[:300]}")
            data = resp.json()
            break
        except (httpx.TransportError, LLMRequestError) as e:
            last_exc = e
            is_5xx = isinstance(e, LLMRequestError) and "HTTP 5" in str(e)
            if attempt < 2 and (isinstance(e, httpx.TransportError) or is_5xx):
                time.sleep(2 * (attempt + 1))
                continue
            raise LLMRequestError(f"קריאה ל-Anthropic נכשלה: {e}") from None
    else:
        raise LLMRequestError(f"לא אמור להגיע לכאן: {last_exc}")

    text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    usage = data.get("usage", {})
    return RawCompletion(
        text="".join(text_parts),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        stop_reason=data.get("stop_reason", ""),
    )
