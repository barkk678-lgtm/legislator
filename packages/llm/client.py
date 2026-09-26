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

from pathlib import Path
import sys
import time
from dataclasses import dataclass

import json

import httpx

# ── מקור יחיד למפתחות ──────────────────────────────────────────────
# ראו packages/config/env_file.py: סביבה גוברת, ואם המשתנה אינו שם -
# נטען מ-/root/.claude/legislator.env (600, מחוץ לריפו).
_CONFIG_DIR = str(Path(__file__).resolve().parents[2] / "packages" / "config")
if _CONFIG_DIR not in sys.path:
    sys.path.insert(0, _CONFIG_DIR)
from env_file import MissingSecret, require, require_supabase  # noqa: E402


_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
# מטמון של שעה במקום חמש דקות - נדרש header ניסיוני, נבדק בפועל
# (2026-09-22): התשובה חזרה עם ephemeral_1h_input_tokens=154,230.
_CACHE_1H_BETA = "extended-cache-ttl-2025-04-11"
DEFAULT_MODEL = "claude-sonnet-5"


class LLMConfigError(Exception):
    """ANTHROPIC_API_KEY חסר - זהה בכוונה ל-RuntimeError שקוראים אחרים
    כבר יודעים לתפוס בדפוס law_registry._supabase_config."""


class LLMRequestError(Exception):
    """כשל רשת/HTTP אחרי מיצוי הניסיונות, או תשובה לא-תקינה מה-API."""


# **מה המשתמש רואה כשהמודל לא זמין** - קרדיט שנגמר, מגבלת קצב, שירות שנפל, מפתח חסר
# (סבב הסגירה של ההסתייגויות, ברק 26.9.2026). נמצא באתר החי: כשהחשבון התרוקן, המשתמש
# קיבל את שגיאת ה-API הגולמית ("HTTP 400 מ-Anthropic: {...credit balance...}"). הסיבה
# הטכנית לא נעלמת - היא נרשמת ב-chat_log כ-error; היא רק לא מגיעה למסך.
UNAVAILABLE_MESSAGE = "השירות אינו זמין כרגע, נסו שוב בעוד כמה דקות"


class ModelUnavailable(Exception):
    """מה שכלי זורק כשהמודל לא זמין: str() - ההודעה למשתמש; reason - הסיבה הטכנית
    (ל-chat_log בלבד). הכלים (שאילתה, הצעה לסדר, מומחה התקנון) יורשים ממנה."""

    def __init__(self, message: str = UNAVAILABLE_MESSAGE, *, reason: str = ""):
        super().__init__(message)
        self.reason = reason or message


@dataclass
class RawCompletion:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str


def _api_key() -> str:
    try:
        return require("ANTHROPIC_API_KEY", used_for="שכבת ה-LLM (packages/llm)")
    except MissingSecret as e:
        # שגיאת תצורה, לא כשל בקורפוס - ההבחנה הזו חשובה למשתמש.
        raise LLMConfigError(str(e)) from None


def complete(
    *,
    system: str,
    user_message: str | None = None,
    messages: list[dict] | None = None,
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
    # **תור שיחה, לא הדבקה של ההיסטוריה למחרוזת אחת.** עד 2026-09-22
    # כלי השאילתא הדביק את כל הודעות המשתמש ב-"\n" ושלח אותן כהודעה
    # אחת; התוצאה הייתה שסירוב על שאלה אחת "נדבק" לשאלות הבאות -
    # המודל ראה גוש אחד שמכיל גם את מה שנדחה, וסירב שוב בצדק.
    if (user_message is None) == (messages is None):
        raise ValueError("יש לספק user_message או messages - בדיוק אחד מהם.")
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "system": system,
        "messages": messages or [{"role": "user", "content": user_message}],
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


def complete_stream(
    *,
    system: str | list[dict],
    user_message: str,
    max_tokens: int = 1500,
    model: str = DEFAULT_MODEL,
    cache_system: bool = False,
):
    """גרסת הזרמה של complete(). מחזירה generator שמניב מחרוזות טקסט
    ככל שהן מגיעות, ובסופו **מניבה אובייקט RawCompletion אחד** עם
    הטקסט המלא וספירת הטוקנים - כדי שהקורא יוכל להריץ את אותן
    בדיקות בדיוק על הטקסט המוגמר.

    **למה הזרמה ולא complete():** נמדד (2026-09-22) שעם כל מאגר
    התקנון בהקשר (154K טוקנים) התשובה המלאה לוקחת 17.5 שניות -
    17 שניות של מסך ריק, גרוע מהמצב שהיא מחליפה. בהזרמה עם מטמון
    חם המילה הראשונה מגיעה ב-**0.6 שניות**. ההזרמה אינה נוחות כאן
    אלא תנאי לכך שהשינוי לא יהיה נסיגה.

    cache_system=True מסמן את גוש ה-system למטמון של שעה. הערך נבחר
    כי השימוש בכלי מגיע בפרצים (ברק: "עשרים דקות, עשר שאלות, ואז לא
    נוגע בו יום") - מטמון של חמש דקות היה נכתב מחדש בכל פרץ.

    **בלי ניסיונות חוזרים, בניגוד ל-complete().** ברגע שהתחלנו
    להזרים טקסט למשתמש אי אפשר "לנסות שוב" בלי להציג לו תשובה
    שנייה על גבי הראשונה; וכשל לפני התו הראשון מדווח מיד ובגלוי.
    """
    key = _api_key()
    blocks = [{"type": "text", "text": system}] if isinstance(system, str) else list(system)
    if cache_system and blocks:
        blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral", "ttl": "1h"}}
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "stream": True,
        "system": blocks,
        "messages": [{"role": "user", "content": user_message}],
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": _API_VERSION,
        "content-type": "application/json",
    }
    if cache_system:
        headers["anthropic-beta"] = _CACHE_1H_BETA

    parts: list[str] = []
    usage_in = usage_out = 0
    stop_reason = ""
    try:
        with httpx.Client(timeout=300.0) as client:
            with client.stream("POST", _API_URL, json=body, headers=headers) as resp:
                if resp.status_code >= 400:
                    resp.read()
                    raise LLMRequestError(
                        f"HTTP {resp.status_code} מ-Anthropic: {resp.text[:300]}")
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    kind = event.get("type")
                    if kind == "message_start":
                        u = event["message"].get("usage", {})
                        # טוקנים שנקראו מהמטמון הם קלט לכל דבר מבחינת
                        # מה שהמודל ראה - נספרים, אחרת המדידה משקרת.
                        usage_in = (u.get("input_tokens", 0)
                                    + u.get("cache_read_input_tokens", 0)
                                    + u.get("cache_creation_input_tokens", 0))
                    elif kind == "content_block_delta":
                        piece = event.get("delta", {}).get("text", "")
                        if piece:
                            parts.append(piece)
                            yield piece
                    elif kind == "message_delta":
                        usage_out = event.get("usage", {}).get("output_tokens", usage_out)
                        stop_reason = event.get("delta", {}).get("stop_reason", stop_reason)
    except httpx.TransportError as e:
        raise LLMRequestError(f"קריאה מוזרמת ל-Anthropic נכשלה: {e}") from None

    yield RawCompletion(text="".join(parts), input_tokens=usage_in,
                        output_tokens=usage_out, stop_reason=stop_reason)
