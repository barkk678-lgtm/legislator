"""דף הבית 3 (27.9.2026) - "יצירת קשר": פנייה נשמרת בטבלה, רק השרת ניגש אליה.

- **הטבלה** - contact_messages (supabase/migrations/20260927010000_contact_messages.sql):
  אותו דפוס כמו chat_log. RLS בלי policy, ו-anon/authenticated בלי הרשאות.
- **אורח** - שם מלא, אימייל ותוכן, כולם חובה. **משתמש רשום** - רק תוכן; השם
  והאימייל מהחשבון. עד שתהיה הרשמה, "החשבון" הוא חשבון הפיתוח שבדפדפן - ולכן
  השרת מקבל אותם מהבקשה. כשתהיה הרשמה הם יילקחו מהסשן, כאן בלבד.
- **הגנה מספאם** (הטופס פתוח לאורחים):
  1. **הגבלת קצב לפי כתובת** - LIMITS. הספירה בטבלה עצמה ולא בזיכרון: ב-Vercel
     כל בקשה יכולה לנחות במופע אחר, ומונה בזיכרון מתאפס.
  2. **שדה נסתר** (`website`) שבני אדם לא רואים ובוטים ממלאים. בקשה שמילאה
     אותו מקבלת "נשלח" - ולא נשמרת. בוט שמקבל שגיאה לומד לעקוף.
- **הכתובת לא נשמרת** - רק HMAC שלה (המפתח: מפתח השרת), מספיק כדי לספור.
- **מייל לברק - לא עדיין** (אין שירות שליחה). docs/open-gaps.md.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

# (חלון בשניות, מקסימום פניות מאותה כתובת בחלון)
LIMITS = ((600, 3), (86400, 10))
MAX_MESSAGE = 5000
MAX_NAME = 200
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
# הבדיקה החיה (tests/live_smoke.py) מסמנת את הפנייה שלה - כדי לסנן אותה בממשק הניהול
TEST_MARKER = "[בדיקה חיה]"

RATE_LIMITED = "נשלחו יותר מדי פניות מהכתובת הזו. נסו שוב מאוחר יותר."


class ContactError(ValueError):
    """פנייה שאינה תקינה - status ו-errors (לפי שדה) למשתמש."""

    def __init__(self, status: int, message: str, errors: dict | None = None):
        super().__init__(message)
        self.status = status
        self.errors = errors or {}


@dataclass
class Submission:
    name: str = ""
    email: str = ""
    message: str = ""
    website: str = ""        # השדה הנסתר
    account: bool = False    # משתמש רשום


def client_ip(headers: dict, fallback: str = "") -> str:
    """ב-Vercel הכתובת הראשונה ב-x-forwarded-for היא הלקוח (Vercel דורס את
    הכותרת, הלקוח לא יכול לזייף אותה). מקומית - כתובת החיבור."""
    fwd = (headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return fwd or (headers.get("x-real-ip") or "").strip() or fallback or "unknown"


def ip_hash(ip: str, secret: str) -> str:
    return hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]


def validate(s: Submission) -> dict:
    """השורה לשמירה, או ContactError(422) עם שגיאה לכל שדה."""
    name, email, message = s.name.strip(), s.email.strip(), s.message.strip()
    errors = {}
    if not message:
        errors["message"] = "נא לכתוב את תוכן הפנייה."
    elif len(message) > MAX_MESSAGE:
        errors["message"] = f"הפנייה ארוכה מדי (עד {MAX_MESSAGE:,} תווים)."
    if not s.account:
        if not name:
            errors["name"] = "נא למלא שם מלא."
        elif len(name) > MAX_NAME:
            errors["name"] = "השם ארוך מדי."
        if not email:
            errors["email"] = "נא למלא אימייל."
        elif len(email) > 254 or not EMAIL_RE.match(email):
            errors["email"] = "כתובת האימייל אינה תקינה."
    if errors:
        raise ContactError(422, "יש לתקן את השדות המסומנים.", errors)
    return {"is_guest": not s.account, "name": name[:MAX_NAME], "email": email[:254],
            "message": message, "is_test": message.startswith(TEST_MARKER)}


class SupabaseStore:
    """הטבלה, דרך מפתח השרת בלבד."""

    def __init__(self):
        from law_registry import _supabase_config  # noqa: PLC0415
        url, key = _supabase_config()
        self.secret = key
        self._client = httpx.Client(base_url=f"{url}/rest/v1", timeout=8.0, headers={
            "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"})

    def count_since(self, hashed: str, since: datetime) -> int:
        from supabase_rest import count_rows  # noqa: PLC0415
        return count_rows(self._client, "/contact_messages",
                          {"ip_hash": f"eq.{hashed}", "created_at": f"gte.{since.isoformat()}"})

    def insert(self, row: dict) -> None:
        resp = self._client.post("/contact_messages", json=row, headers={"Prefer": "return=minimal"})
        resp.raise_for_status()


def submit(s: Submission, *, ip: str, user_id: str | None, store, now: datetime | None = None) -> dict:
    """{"ok": True, "stored": bool}. זורק ContactError (422/429/503)."""
    if s.website.strip():
        # בוט: "נשלח", בלי לשמור ובלי לספור
        return {"ok": True, "stored": False}
    row = validate(s)
    hashed = ip_hash(ip, store.secret)
    now = now or datetime.now(timezone.utc)
    try:
        for seconds, limit in LIMITS:
            if store.count_since(hashed, now - timedelta(seconds=seconds)) >= limit:
                raise ContactError(429, RATE_LIMITED)
        store.insert({**row, "ip_hash": hashed, "user_id": (user_id or None) and user_id[:100]})
    except ContactError:
        raise
    except Exception as e:  # noqa: BLE001 - הפנייה לא נשמרה: המשתמש חייב לדעת
        raise ContactError(503, "הפנייה לא נשלחה בגלל תקלה זמנית. נסו שוב בעוד רגע.") from e
    return {"ok": True, "stored": True}


__all__ = ["ContactError", "LIMITS", "RATE_LIMITED", "Submission", "SupabaseStore", "TEST_MARKER",
           "client_ip", "ip_hash", "submit", "validate"]
