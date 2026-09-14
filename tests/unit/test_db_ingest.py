"""בדיקות ל-db_ingest.py - בלי רשת/DB אמיתיים. ראו docs/strategy/
decisions.md לתוכנית ה-ingest שאושרה (2026-09-13).

בונה export_xml סינתטי מה-fixtures הקיימים (כמו test_wikitext_client.py)
ומזריק אותו דרך פרמטר fetch של build_ingest_plan/fetch_with_retry -
כך שהצינור כולו (שליפה->פרסור->בדיקות שפיות->SQL) נבדק בלי רשת.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from db_ingest import (  # noqa: E402
    NetworkIngestError,
    SanityIngestError,
    _lit,
    build_ingest_plan,
    fetch_with_retry,
    record_failure_sql,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikitext"


def _fake_export(slug: str) -> dict:
    text = (FIXTURES / f"{slug}.wikitext").read_text(encoding="utf-8")
    meta = json.loads((FIXTURES / f"{slug}.meta.json").read_text(encoding="utf-8"))
    export_xml = f"""<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">
  <page>
    <title>{meta['title']}</title>
    <id>{meta['page_id']}</id>
    <revision>
      <id>{meta['revision_id']}</id>
      <timestamp>{meta['revision_timestamp']}</timestamp>
      <text bytes="{len(text)}" xml:space="preserve">{_xml_escape(text)}</text>
    </revision>
  </page>
</mediawiki>"""
    return {"title": meta["title"], "export_xml": export_xml}


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    checks = []

    # --- _lit: dollar-quoting בטוח ---
    checks.append(("_lit(None) -> NULL", _lit(None) == "NULL"))
    checks.append(("_lit עם גרשיים כפולות עובד", _lit('ס"ח התש"ן') == '$q$ס"ח התש"ן$q$'))
    checks.append(
        (
            "_lit בוחר תג אחר אם $q$ מופיע בתוכן",
            _lit("יש כאן $q$ בתוך הטקסט") == "$q1$יש כאן $q$ בתוך הטקסט$q1$",
        )
    )

    # --- build_ingest_plan על fixture אמיתי (קייטנות) ---
    def fake_fetch_kaytanot(title):
        return _fake_export("kaytanot")

    plan = build_ingest_plan(
        "kaytanot-1990",
        "חוק הקייטנות (רישוי ופיקוח)",
        source_ref='ס"ח התש"ן, עמ\' 155.',
        law_is_new=True,
        fetch=fake_fetch_kaytanot,
    )
    checks.append(("plan.section_count > 0", plan.section_count > 0))
    checks.append(("plan.node_count >= plan.section_count", plan.node_count >= plan.section_count))
    checks.append(("SQL מתחיל ב-begin ומסתיים ב-commit", plan.sql.startswith("begin;\n") and plan.sql.rstrip().endswith("commit;")))
    checks.append(("SQL כולל insert into laws (חוק חדש)", "insert into laws " in plan.sql))
    checks.append(
        (
            "מספר 'insert into nodes' תואם ל-node_count",
            plan.sql.count("insert into nodes ") == plan.node_count,
        )
    )

    # --- validity (2026-09-14) - כשמועבר, נכתב ל-insert into laws ---
    from knesset_odata import ValidityMatch  # noqa: E402 - כאן ולא בראש, כדי שלא ליצור תלות קשה ב-db_ingest.py עצמו

    plan_valid = build_ingest_plan(
        "kaytanot-1990",
        "חוק הקייטנות (רישוי ופיקוח)",
        source_ref="",
        law_is_new=True,
        fetch=fake_fetch_kaytanot,
        validity=ValidityMatch("תקף", "exact", "חוק הקייטנות (רישוי ופיקוח), התש\"ן-1990"),
    )
    checks.append(("validity מועבר -> law_validity_desc ב-SQL", "law_validity_desc" in plan_valid.sql and "'תקף'" not in plan_valid.sql))
    checks.append(("validity מועבר -> match_method ב-SQL", "$q$exact$q$" in plan_valid.sql or "exact" in plan_valid.sql))

    plan_unknown = build_ingest_plan(
        "kaytanot-1990",
        "חוק הקייטנות (רישוי ופיקוח)",
        source_ref="",
        law_is_new=True,
        fetch=fake_fetch_kaytanot,
        validity=ValidityMatch(None, "not_found"),
    )
    checks.append(("validity=לא ידוע -> law_validity_desc הוא NULL", "NULL" in plan_unknown.sql.split("insert into laws")[1].split(";")[0]))

    checks.append(("validity לא מועבר (ברירת מחדל) -> אין עמודות תוקף ב-SQL", "law_validity_desc" not in plan.sql))

    # law_is_new=False -> אין insert into laws
    plan_existing = build_ingest_plan(
        "kaytanot-1990",
        "חוק הקייטנות (רישוי ופיקוח)",
        source_ref='ס"ח התש"ן, עמ\' 155.',
        law_is_new=False,
        fetch=fake_fetch_kaytanot,
    )
    checks.append(("law_is_new=False -> בלי insert into laws", "insert into laws " not in plan_existing.sql))

    # --- עונשין: קטע1/קטע3/ח:מבוא/חוקי עונשין תוקנו בזה אחר זה עד
    # 2026-09-14 (ראו TASKS.md משימה 7). עכשיו נכשל שוב, אבל על סיבה
    # *חדשה ואמיתית*: check_no_unconsumed_content תופסת 327 שורות
    # <table>/<tr>/<td> גולמיות ("לוח השוואה") שנבלעו בשקט קודם - בדיוק
    # התרחיש המסוכן ביותר שהוגדר בפרויקט. לא רגרסיה - תיקון. ---
    def fake_fetch_penal(title):
        return _fake_export("penal")

    try:
        build_ingest_plan(
            "penal-1977", "חוק העונשין", source_ref="", law_is_new=True, fetch=fake_fetch_penal
        )
        checks.append(("עונשין -> SanityIngestError (unconsumed content)", False))
    except SanityIngestError as exc:
        checks.append(("עונשין -> SanityIngestError (unconsumed content)", "שורות תוכן שלא נצרכו" in str(exc)))

    # --- קטגוריית retry: כשל רשת חולף, מצליח בניסיון השלישי ---
    attempts = {"n": 0}

    def flaky_fetch(title):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("תקלת רשת מדומה")
        return _fake_export("kaytanot")

    result = fetch_with_retry("קייטנות", max_attempts=3, backoff_seconds=(0, 0, 0), fetch=flaky_fetch)
    checks.append(("כשל רשת חולף -> מצליח בניסיון השלישי", result is not None and attempts["n"] == 3))

    # כשל רשת מתמשך -> NetworkIngestError אחרי מיצוי הניסיונות, בלי לגעת ברשת האמיתית
    def always_fails(title):
        raise OSError("תמיד נכשל")

    try:
        fetch_with_retry("x", max_attempts=3, backoff_seconds=(0, 0, 0), fetch=always_fails)
        checks.append(("כשל רשת מתמשך -> NetworkIngestError", False))
    except NetworkIngestError as exc:
        checks.append(("כשל רשת מתמשך -> NetworkIngestError", "3 ניסיונות" in str(exc)))

    # --- record_failure_sql ---
    sql = record_failure_sql("kaytanot-1990", "network", "בדיקה")
    checks.append(("record_failure_sql כולל את קטגוריית הכשל", "[network] בדיקה" in sql))
    checks.append(("record_failure_sql מעדכן last_ingest_attempted_at", "last_ingest_attempted_at = now()" in sql))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
