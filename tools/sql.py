#!/usr/bin/env python3
"""שאילתת קריאה על ה-DB, דרך אותו ערוץ שדרכו נטען הקורפוס:
REST + service_role, בלי mcp execute_sql ובלי שער אישורים.

    python3 tools/sql.py "select count(*) from nodes"
    python3 tools/sql.py --file q.sql
    from tools.sql import query; rows = query("select 1 as x")

**לקריאה בלבד, והאכיפה בדאטהבייס.** `public.readonly_query` מעבירה
את הטרנזקציה ל-`transaction_read_only` לפני ההרצה, ולכן כל
INSERT/UPDATE/DELETE/DDL נכשל במנוע עצמו (SQLSTATE 25006) - לא
בבדיקת מחרוזת כמו "האם מתחיל ב-SELECT", שאפשר לעקוף.

**statement_timeout: 8 שניות, ונאכף בפלטפורמה ולא כאן.** הוא מגיע
מ-`authenticator` (rolconfig). ניסיון להגדיר אותו בתוך הפונקציה
נמדד ולא עבד - `current_setting` אמנם החזיר את הערך החדש, אבל
statement_timeout נתפס כשההצהרה העליונה מתחילה, והקריאה לפונקציה
כבר רצה: גם 2 שניות וגם 5 שניות נקטעו ב-8.6. פרמטר כזה היה נראה
כאילו הוא עובד, ולכן הוסר.

הרשאות: EXECUTE הוסר מ-PUBLIC/anon/authenticated וניתן ל-service_role
בלבד. הפונקציה חשופה דרך PostgREST, ובלי זה כל מי שמחזיק את המפתח
הציבורי היה יכול להריץ שאילתות.

המפתח נטען מ-`/root/.claude/legislator.env` דרך `packages/config/
env_file.py` - לא נכתב לקובץ, לא מודפס, ולא מועבר בשורת הפקודה.

**שינוי מבנה אינו עובר כאן.** מיגרציות ו-DDL נשארים ב-
mcp apply_migration/execute_sql, ושם הם ימשיכו לבקש אישור - בכוונה.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "config"))
import env_file  # noqa: E402

import httpx  # noqa: E402

_TIMEOUT_SECONDS = 90


class ReadOnlyQueryError(RuntimeError):
    """השאילתה נדחתה או נכשלה. ההודעה היא מה שהדאטהבייס החזיר."""


def query(sql: str) -> list[dict]:
    """מריצה שאילתת קריאה ומחזירה רשימת dict-ים (ריקה אם אין שורות)."""
    url, key = env_file.require_supabase()
    response = httpx.post(
        f"{url}/rest/v1/rpc/readonly_query",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={"q": sql},
        timeout=_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise ReadOnlyQueryError(f"HTTP {response.status_code}: {response.text[:600]}")
    return response.json() or []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sql", nargs="?", help="השאילתה עצמה")
    parser.add_argument("--file", type=Path, help="קובץ עם השאילתה")
    parser.add_argument("--raw", action="store_true", help="JSON גולמי, בלי עימוד")
    args = parser.parse_args()

    sql = args.file.read_text(encoding="utf-8") if args.file else args.sql
    if not sql:
        parser.error("צריך שאילתה או --file")

    try:
        rows = query(sql)
    except ReadOnlyQueryError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.raw or not rows:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    columns = list(rows[0])
    widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    print(" | ".join(str(c).ljust(widths[c]) for c in columns))
    print("-+-".join("-" * widths[c] for c in columns))
    for row in rows:
        print(" | ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))
    print(f"\n{len(rows)} שורות")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
