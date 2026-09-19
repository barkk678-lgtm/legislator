#!/usr/bin/env python3
"""טוען קורפוס SQL (שכבר נוצר ע"י tools/load_corpus.py) ל-Supabase דרך
REST API (PostgREST), לא psql/mcp execute_sql.

למה REST ולא psql/DATABASE_URL: נבדק ב-2026-09-15 - לסביבת ה-agent
הזו יש גישת רשת רק לפורט 443 (HTTPS, דרך proxy), אין TCP ישיר לפורטי
Postgres (5432/6543 חסומים גם ל-direct connection וגם ל-pooler).
psycopg/psql לא יעבדו כאן. REST (Supabase project URL, לא ה-DB host)
עובד כי הוא HTTPS רגיל.

למה לא mcp Supabase execute_sql: הקורפוס המלא הוא ~187MB של SQL -
כל תו שעובר כ-argument לקריאת כלי MCP עובר גם דרך קונטקסט ה-LLM
(unbounded, גם בקריאה וגם בכתיבה) - לא ישים בסדר גודל הזה.

איך זה עובד: sql_parser.py (packages/corpus) מפרסר מכנית (בלי LLM)
כל קובץ .sql שכבר אומת ע"י tools/load_corpus.py, ל-Python
dicts/values, והסקריפט הזה שולח אותם כ-JSON ישירות ל-REST endpoints
של הטבלאות. law_version_id (subquery ב-SQL המקורי, כי id הוא IDENTITY
עולה) מתחלף כאן בערך האמיתי שחוזר מה-POST של law_versions.

שימוש:
  1. python tools/load_corpus.py ... -> מייצר קבצי .sql (ברירת מחדל
     SRC_DIR למטה, אפשר לשנות עם --sql-out שם, ולעדכן SRC_DIR כאן
     או להעביר דרך משתנה סביבה LOAD_CORPUS_SQL_DIR).
  2. export SUPABASE_SERVICE_KEY=... (מ-Dashboard -> Project Settings
     -> API -> service_role - לעולם לא לשמור בקובץ בריפו)
  3. python tools/load_corpus_to_supabase_rest.py

התקדמות נשמרת ב-load_progress.jsonl (לצד הסקריפט) - ריצה חוזרת
מדלגת על חוקים שכבר סומנו "ok", כך שניתן להריץ שוב בבטחה אחרי כשל
חלקי/ניתוק.

בטיחות:
- מפתח ה-service_role מגיע *רק* ממשתנה סביבה - לעולם לא נכתב לקובץ,
  לא מודפס ב-stdout.
- כל חוק מטופל בנפרד: אם שלב כלשהו נכשל, laws.current_version_id
  נשאר NULL (המצב המקורי - "לא הושלם"), בדיוק כמו שה-SQL המקורי
  התכוון (UPDATE current_version_id הוא הצעד האחרון בטרנזקציה).
  שורות יתומות (law_versions/nodes של ניסיון שנכשל) הן garbage לא
  מזיק - מנוקות אוטומטית בניסיון החוזר (ראו הטיפול ב-23505 למטה).
- לא עוצר את כל הריצה על כשל בחוק בודד - ממשיך לחוק הבא, מדווח בסוף.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "corpus"))
from sql_parser import ParseError, parse_law_file  # noqa: E402

# ── מקור יחיד למפתחות ──────────────────────────────────────────────
# ראו packages/config/env_file.py: סביבה גוברת, ואם המשתנה אינו שם -
# נטען מ-/root/.claude/legislator.env (600, מחוץ לריפו).
_CONFIG_DIR = str(Path(__file__).resolve().parents[1] / "packages" / "config")
if _CONFIG_DIR not in sys.path:
    sys.path.insert(0, _CONFIG_DIR)
from env_file import MissingSecret, get as env_get, require, require_supabase  # noqa: E402


SUPABASE_PROJECT_URL = "https://aamxwjmmlsqkinrzirdz.supabase.co"
SRC_DIR = Path(os.environ.get("LOAD_CORPUS_SQL_DIR", "/tmp/corpus_sql"))
PROGRESS_LOG = Path(__file__).parent / "load_progress.jsonl"

# שני השמות נתמכים, והקנוני הוא SUPABASE_SERVICE_ROLE_KEY - זה מה
# שכל שאר הקוד קורא (apps/api/admin_ingest.py, research.py,
# tools/build_search_chunks.py) וזה מה שמוגדר ב-Vercel. הקובץ הזה
# היה היחיד שציפה ל-SUPABASE_SERVICE_KEY, והפער הזה שווה שעה של
# חיפוש למי שמגדיר את המפתח פעם אחת ומריץ (נמצא 2026-09-18).
# SUPABASE_SERVICE_KEY נשאר כשם חלופי לתאימות לאחור עם סקריפטים ישנים.
SERVICE_KEY = env_get("SUPABASE_SERVICE_ROLE_KEY") or env_get("SUPABASE_SERVICE_KEY")
if not SERVICE_KEY:
    print("שגיאה: SUPABASE_SERVICE_KEY לא מוגדר בסביבה", file=sys.stderr)
    sys.exit(1)


def _rest_request(method, path, body=None, prefer=None):
    url = f"{SUPABASE_PROJECT_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("apikey", SERVICE_KEY)
    req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("Content-Type", "application/json")
    if prefer:
        req.add_header("Prefer", prefer)
    last_exc = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} on {method} {path}: {err_body[:500]}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_exc = e
            if attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"רשת נכשלה אחרי 4 ניסיונות ({method} {path}): {e}") from None
    raise RuntimeError(f"לא אמור להגיע לכאן: {last_exc}")


def _bulk_insert_chunked(table, rows, chunk_size=500):
    """מחלקת insert גדול (הרבה שורות) ל-batches - חוק אחד (law-2000613,
    4,794 nodes) גרם ל-statement timeout (57014) ב-INSERT אחד ענק.
    סדר נשמר (חשוב ל-FK העצמי של nodes: הורה חייב להופיע קודם) -
    הלולאה סדרתית, וכל POST מתחייב (commit) לפני שהבא נשלח."""
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        _rest_request("POST", f"/rest/v1/{table}", body=chunk, prefer="return=minimal")


def _row(parsed_dict):
    return {k: v.value for k, v in parsed_dict.items()}


def load_one_law(sql_path: Path) -> tuple[str, str, str]:
    """מחזירה (law_id, status, detail). status: 'ok' | 'error'."""
    text = sql_path.read_text(encoding="utf-8")
    try:
        parsed = parse_law_file(text)
    except ParseError as e:
        return sql_path.stem, "error", f"parse: {e}"

    law_id = parsed["update_law_id"]

    try:
        if parsed["laws_row"] is not None:
            law_row = _row(parsed["laws_row"])
            _rest_request(
                "POST",
                "/rest/v1/laws?on_conflict=id",
                body=[law_row],
                prefer="resolution=merge-duplicates,return=minimal",
            )

        lv_row = _row(parsed["law_version_row"])
        try:
            status, resp = _rest_request(
                "POST", "/rest/v1/law_versions", body=[lv_row], prefer="return=representation"
            )
        except RuntimeError as e:
            if "23505" not in str(e) or "law_id, wikitext_revision_id" not in str(e):
                raise
            # ניסיון קודם על אותו חוק כבר יצר law_versions אבל נכשל בשלב
            # מאוחר יותר - זו שורה יתומה (רק אם laws.current_version_id
            # לא מצביע עליה בפועל - בדיקה מפורשת, לא הנחה, לפני מחיקה
            # של נתונים בפרודקשן).
            _, law_rows = _rest_request(
                "GET",
                f"/rest/v1/laws?id=eq.{urllib.parse.quote(law_id)}&select=current_version_id",
            )
            _, orphan_rows = _rest_request(
                "GET",
                f"/rest/v1/law_versions?law_id=eq.{urllib.parse.quote(law_id)}"
                f"&wikitext_revision_id=eq.{lv_row['wikitext_revision_id']}&select=id",
            )
            current_id = law_rows[0]["current_version_id"] if law_rows else None
            orphan_ids = [r["id"] for r in orphan_rows if r["id"] != current_id]
            if not orphan_ids:
                raise
            _rest_request("DELETE", f"/rest/v1/law_versions?id=eq.{orphan_ids[0]}", prefer="return=minimal")
            status, resp = _rest_request(
                "POST", "/rest/v1/law_versions", body=[lv_row], prefer="return=representation"
            )
        if not resp or "id" not in resp[0]:
            return law_id, "error", f"law_versions לא החזיר id: {resp}"
        version_id = resp[0]["id"]

        def with_version(rows):
            out = []
            for r in rows:
                d = _row(r)
                d["law_version_id"] = version_id
                out.append(d)
            return out

        node_rows = with_version(parsed["nodes"])
        _bulk_insert_chunked("nodes", node_rows)

        if parsed["citations"]:
            _bulk_insert_chunked("law_citations", with_version(parsed["citations"]))

        if parsed["tokens"]:
            _bulk_insert_chunked("section_amendment_tokens", with_version(parsed["tokens"]))

        _rest_request(
            "PATCH",
            f"/rest/v1/laws?id=eq.{urllib.parse.quote(law_id)}",
            body={"current_version_id": version_id},
            prefer="return=minimal",
        )
        return law_id, "ok", f"version_id={version_id} nodes={len(node_rows)}"
    except RuntimeError as e:
        return law_id, "error", str(e)[:400]


def main():
    already_done = set()
    if PROGRESS_LOG.exists():
        for line in PROGRESS_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["status"] == "ok":
                already_done.add(rec["law_id"])

    files = sorted(SRC_DIR.glob("*.sql"))
    todo = [f for f in files if f.stem not in already_done]
    print(f"סה\"כ קבצים: {len(files)}, כבר נטענו בהצלחה (מה-log): {len(already_done)}, נותרו: {len(todo)}")

    ok = err = 0
    with PROGRESS_LOG.open("a", encoding="utf-8") as log_f:
        for i, f in enumerate(todo, 1):
            law_id, status, detail = load_one_law(f)
            log_f.write(json.dumps({"law_id": law_id, "status": status, "detail": detail}, ensure_ascii=False) + "\n")
            log_f.flush()
            if status == "ok":
                ok += 1
            else:
                err += 1
                print(f"[{i}/{len(todo)}] ERROR {law_id}: {detail}")
            if i % 50 == 0:
                print(f"[{i}/{len(todo)}] ok={ok} err={err}")

    print(f"סיום. ok={ok} err={err}")


if __name__ == "__main__":
    main()
