#!/usr/bin/env python3
"""מריץ ingest לחוק בודד: שולף מוויקיטקסט חי, פרסר, בדיקות שפיות,
ובונה תוכנית SQL - לא מבצע אותה. ראו docs/strategy/decisions.md.

שימוש:
    python3 tools/ingest_law.py <law_id> <wikitext_title> [source_ref]

כותב את ה-SQL הבנוי ל-stdout (או לקובץ עם --out). את ה-SQL עצמו
צריך להריץ בנפרד (2026-09-13: דרך mcp Supabase, כי הסביבה הזו לא
מחזיקה credentials/חיבור Postgres ישיר - ראו db_ingest.py docstring).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "corpus"))

from db_ingest import (  # noqa: E402
    NetworkIngestError,
    SanityIngestError,
    build_ingest_plan,
    record_failure_sql,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("law_id")
    parser.add_argument("wikitext_title")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--law-is-new", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    try:
        plan = build_ingest_plan(
            args.law_id,
            args.wikitext_title,
            source_ref=args.source_ref,
            law_is_new=args.law_is_new,
        )
    except NetworkIngestError as exc:
        print(record_failure_sql(args.law_id, "network", str(exc)))
        return 1
    except SanityIngestError as exc:
        print(record_failure_sql(args.law_id, "sanity", str(exc)))
        return 1

    print(f"-- law_id={plan.law_id} revision={plan.wikitext_revision_id} as_of={plan.as_of}", file=sys.stderr)
    print(
        f"-- nodes={plan.node_count} sections={plan.section_count} "
        f"citations={plan.citation_count} tokens={plan.token_count}",
        file=sys.stderr,
    )

    if args.out:
        args.out.write_text(plan.sql, encoding="utf-8")
        print(f"-- SQL נכתב ל-{args.out}", file=sys.stderr)
    else:
        print(plan.sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
