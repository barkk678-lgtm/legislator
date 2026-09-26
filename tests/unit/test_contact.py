"""דף הבית 3 (26.9.2026) - "יצירת קשר", בלי רשת.

נבדק: אורח חייב שם, אימייל תקין ותוכן; משתמש רשום - רק תוכן; השדה הנסתר
מקבל "נשלח" ואינו נשמר; הגבלת הקצב לפי כתובת (10 דקות / יום) חוסמת ב-429;
הכתובת נשמרת כ-HMAC ולא כטקסט; תקלה בשמירה היא 503 גלוי ולא "נשלח".
הטבלה מוחלפת במאגר מקומי.
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import isolate  # noqa: E402

isolate()

import sys  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from fastapi.testclient import TestClient  # noqa: E402
import contact  # noqa: E402
import main  # noqa: E402

NOW = datetime(2026, 9, 27, 1, 0, tzinfo=timezone.utc)


class FakeStore:
    secret = "server-secret"

    def __init__(self, fail=False):
        self.rows, self.fail = [], fail

    def count_since(self, hashed, since):
        if self.fail:
            raise RuntimeError("Supabase down")
        return sum(1 for r in self.rows if r["ip_hash"] == hashed and r["_at"] >= since)

    def insert(self, row):
        self.rows.append({**row, "_at": self._now})


def _submit(store, sub, ip="1.2.3.4", at=NOW):
    store._now = at
    return contact.submit(sub, ip=ip, user_id="u1", store=store, now=at)


def _error(fn):
    try:
        fn()
    except contact.ContactError as e:
        return e
    raise AssertionError("צפויה ContactError")


GUEST = dict(name="ישראל ישראלי", email="israel@example.com", message="שלום, יש לי שאלה")


def test_guest_needs_all_three_fields():
    e = _error(lambda: contact.validate(contact.Submission()))
    assert e.status == 422 and set(e.errors) == {"name", "email", "message"}, e.errors


def test_guest_email_format():
    for bad in ("israel", "israel@", "a@b", "a b@c.io", "@example.com"):
        e = _error(lambda: contact.validate(contact.Submission(**{**GUEST, "email": bad})))
        assert set(e.errors) == {"email"}, (bad, e.errors)
    assert contact.validate(contact.Submission(**GUEST))["is_guest"] is True


def test_account_needs_only_the_message():
    row = contact.validate(contact.Submission(message="פנייה", account=True))
    assert row["is_guest"] is False and row["message"] == "פנייה"
    e = _error(lambda: contact.validate(contact.Submission(account=True)))
    assert set(e.errors) == {"message"}, e.errors


def test_honeypot_says_sent_but_stores_nothing():
    store = FakeStore()
    out = _submit(store, contact.Submission(**GUEST, website="http://spam.example"))
    assert out == {"ok": True, "stored": False} and store.rows == []


def test_stored_row_hashes_the_ip():
    store = FakeStore()
    assert _submit(store, contact.Submission(**GUEST))["stored"] is True
    row = store.rows[0]
    assert "1.2.3.4" not in str(row) and row["ip_hash"] == contact.ip_hash("1.2.3.4", "server-secret")
    assert row["user_id"] == "u1" and row["is_test"] is False


def test_rate_limit_per_ip():
    store = FakeStore()
    window, limit = contact.LIMITS[0]
    for i in range(limit):
        _submit(store, contact.Submission(**GUEST), at=NOW + timedelta(seconds=i))
    e = _error(lambda: _submit(store, contact.Submission(**GUEST), at=NOW + timedelta(seconds=limit)))
    assert e.status == 429 and str(e) == contact.RATE_LIMITED
    # כתובת אחרת - לא נחסמת
    assert _submit(store, contact.Submission(**GUEST), ip="5.6.7.8")["stored"]
    # אחרי החלון הקצר - שוב מותר, עד המכסה היומית
    later = NOW + timedelta(seconds=window + 60)
    assert _submit(store, contact.Submission(**GUEST), at=later)["stored"]


def test_daily_limit():
    store = FakeStore()
    (short, _), (_, day_max) = contact.LIMITS
    at = NOW
    for _ in range(day_max):   # כל פנייה אחרי החלון הקצר - רק המכסה היומית נספרת
        _submit(store, contact.Submission(**GUEST), at=at)
        at += timedelta(seconds=short + 1)
    e = _error(lambda: _submit(store, contact.Submission(**GUEST), at=at))
    assert e.status == 429, e


def test_store_failure_is_visible():
    e = _error(lambda: _submit(FakeStore(fail=True), contact.Submission(**GUEST)))
    assert e.status == 503 and "לא נשלחה" in str(e)


def test_client_ip_prefers_forwarded():
    assert contact.client_ip({"x-forwarded-for": "9.9.9.9, 10.0.0.1"}, "127.0.0.1") == "9.9.9.9"
    assert contact.client_ip({}, "127.0.0.1") == "127.0.0.1"


def test_endpoint():
    store = FakeStore()
    store._now = datetime.now(timezone.utc)
    main_store = contact.SupabaseStore
    contact.SupabaseStore = lambda: store
    try:
        api = TestClient(main.app)
        r = api.post("/api/contact", json={"message": "", "account": False})
        assert r.status_code == 422 and set(r.json()["errors"]) == {"name", "email", "message"}, r.text
        r = api.post("/api/contact", json={**GUEST, "message": contact.TEST_MARKER + " בדיקה"},
                     headers={"X-Chat-User": "anon-7", "x-forwarded-for": "8.8.8.8"})
        assert r.status_code == 200 and r.json() == {"ok": True}, r.text
        assert store.rows[-1]["user_id"] == "anon-7" and store.rows[-1]["is_test"] is True
        assert store.rows[-1]["ip_hash"] == contact.ip_hash("8.8.8.8", "server-secret")
    finally:
        contact.SupabaseStore = main_store


def test_auth_placeholders():
    api = TestClient(main.app)
    for kind, word in (("signup", "ההרשמה"), ("login", "הכניסה")):
        r = api.get(f"/auth/{kind}")
        assert r.status_code == 200 and f"{word} עוד לא פתוחה" in r.text, kind
    assert api.get("/auth/other").status_code == 404


def test_migration_blocks_the_browser():
    sql = (ROOT / "supabase" / "migrations" / "20260927010000_contact_messages.sql").read_text(encoding="utf-8")
    assert "enable row level security" in sql and "revoke all on table public.contact_messages from anon, authenticated" in sql
    assert "create policy" not in sql.lower()


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_contact: כל הבדיקות עברו")
