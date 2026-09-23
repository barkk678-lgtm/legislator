"""בקרות שליליות על ערוץ הקריאה `public.readonly_query` (tools/sql.py).

**בדיקה חיה** - נוגעת ב-Supabase האמיתי, ולכן ב-tests/live ולא
ב-tests/unit. אין כאן שום כתיבה: כל מה שהיא עושה זה לוודא שניסיונות
כתיבה **נכשלים**.

למה הבדיקה הזו קיימת: הפונקציה חשופה דרך PostgREST ומריצה SQL
שרירותי. שלוש ההבטחות שלה חייבות להיות מאומתות ולא מונחות -
אחרת יש כאן דלת אחורית לדאטהבייס.

**ולמה היא לא מסתפקת ב-INSERT פשוט:** הניסיון הראשון הראה ש-INSERT
דרך הפונקציה נכשל ב**שגיאת תחביר** (הוא נעטף ב-`select ... from
(%s) t`, ושם INSERT אינו חוקי) - כלומר הוא מעולם לא הגיע לאכיפה
עצמה. זה שומר שני, לא הוכחה. ההוכחה היא `nextval`, שהוא SELECT
תקין לחלוטין ומגיע להרצה - ושם נאכף `transaction_read_only`.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "packages" / "config"))

import env_file  # noqa: E402
import httpx  # noqa: E402
from sql import ReadOnlyQueryError, query  # noqa: E402

# המפתח הציבורי (anon) - לא סוד, מיועד לדפדפן. מופיע כאן כדי לוודא
# שהוא **אינו** מספיק כדי להריץ שאילתות.
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFhbXh3am1tbHNxa2lucnppcmR6Iiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3ODkzMTMyMjMsImV4cCI6MjEwNDg4OTIyM30."
    "nCkDGociftP4f-cXinKIDjG17E72fQJoQ2AYsPtoN8o"
)


def main() -> int:
    checks = []

    # 0. הערוץ בכלל עובד
    checks.append(("שאילתת קריאה עובדת", query("select 1 as x") == [{"x": 1}]))

    # 1. המפתח הציבורי נדחה
    url, _ = env_file.require_supabase()
    response = httpx.post(
        f"{url}/rest/v1/rpc/readonly_query",
        headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}",
                 "Content-Type": "application/json"},
        json={"q": "select 1 as x"}, timeout=60,
    )
    checks.append((f"מפתח ציבורי נדחה (HTTP {response.status_code})",
                   response.status_code >= 400 and "42501" in response.text))

    # 2. כתיבה נחסמת **בהרצה**, לא בתחביר
    try:
        query("select nextval('law_versions_id_seq') as v")
        checks.append(("nextval נחסם על ידי transaction_read_only", False))
    except ReadOnlyQueryError as exc:
        checks.append(("nextval נחסם על ידי transaction_read_only",
                       "25006" in str(exc)))

    # ובנוסף - השומר השני, שה-INSERT/UPDATE/DELETE/DROP אינם חוקיים
    # כתת-שאילתה מלכתחילה.
    for label, statement in (
        ("INSERT", "insert into laws (id, full_title) values ('x','y') returning id"),
        ("UPDATE", "update laws set full_title = full_title where false returning id"),
        ("DELETE", "delete from law_citations where false returning law_version_id"),
        ("DROP", "drop table if exists nodes"),
        ("CTE שמסתיר מחיקה",
         "with w as (delete from law_citations where false returning 1) select * from w"),
    ):
        try:
            query(statement)
            checks.append((f"{label} נכשל", False))
        except ReadOnlyQueryError:
            checks.append((f"{label} נכשל", True))

    # 3. statement_timeout קוטע
    started = time.time()
    try:
        query("select pg_sleep(30) as s")
        checks.append(("שאילתה ארוכה נקטעת", False))
    except ReadOnlyQueryError as exc:
        elapsed = time.time() - started
        checks.append((f"שאילתה ארוכה נקטעת ({elapsed:.1f}s)",
                       "57014" in str(exc) and elapsed < 20))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל - אל תסמוך על הערוץ")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
