#!/usr/bin/env python3
"""מכין SQL לטעינה מלאה של הקורפוס ל-Supabase - שלב 1.2 (התיעוד המלא
של כל ההחלטות: TASKS.md משימה 7, docs/data-sources.md).

**לא מריץ SQL בעצמו.** הסביבה הזו לא מחזיקה credentials ישירים
ל-Postgres (ראו db_ingest.py docstring) - לכל חוק נבנית תוכנית ingest
מלאה (law_id דרך law_id.resolve_law_id + SQL דרך db_ingest.build_ingest_plan)
ונכתבת כקובץ נפרד תחת --out-dir. הביצוע בפועל דרך mcp Supabase
execute_sql, **חוק אחד בכל קריאה** (לא כמה חוקים מאוחדים לקריאה אחת) -
כדי לשמר בידוד טרנזקציה מלא: begin/commit של חוק אחד לעולם לא יכול
להיכשל בגלל/להשפיע על חוק אחר (ברק, 2026-09-14, ביקש אישור מפורש
על זה).

**סינון, מעבר לסינון הרגיל (חוקים/חוקי-יסוד + תוקף מול KNS, ראו
batch_validate_ingest.py):**
- תת-דפים - כותרת עם "/" שהכותרת-אב שלה (החלק לפני ה-"/" האחרון)
  קיימת בעצמה בקורפוס. אין להם קיום עצמאי כחוק - ראו TASKS.md משימה 7.
- 4 חוקים שהוצאו במפורש: 3 "חוק עזר..." + "חוק שלל המלחמה" (ברק,
  2026-09-14 - הכרעת תוכן, לא טכנית).

**אידמפוטנטי:** --existing-state מקבל JSON של המצב הקיים ב-DB (ראו
פלט השאילתה בתחתית הקובץ) - {law_id: wikitext_revision_id}. חוק
שכבר נטען באותה גרסה בדיוק מדולג (לא נכשל, לא משוכפל, לא נכתב לו
SQL). חוק שקיים בגרסה *שונה* נטען כגרסה חדשה (law_is_new=False) -
לא ממומש כרגע (הטעינה הראשונה הזו - כל חוק הוא law_is_new=True).

שימוש:
    python3 tools/load_corpus.py --out-dir SQLDIR --manifest manifest.json \
        [--titles-cache F] [--kns-cache F] [--existing-state existing.json] [--limit N]

שאילתה לשליפת --existing-state (dry-run תמיד, קריאה בלבד):
    select l.id as law_id, lv.wikitext_revision_id
    from laws l join law_versions lv on lv.id = l.current_version_id;
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "corpus"))

from db_ingest import NetworkIngestError, SanityIngestError, build_ingest_plan, fetch_with_retry  # noqa: E402
from knesset_odata import classify_validity, fetch_israel_laws, should_ingest  # noqa: E402
from law_id import LawIdResolutionError, resolve_law_id  # noqa: E402
from wikitext_client import (  # noqa: E402
    extract_revision_id,
    extract_wikitext_body,
    is_primary_legislation_title,
    list_category_titles,
)

_DROPPED_TITLES = {
    "חוק עזר לאיגוד ערים כנרת (הסדרת הרחצה בכנרת)",
    "חוק עזר לגנים לאומיים ושמורות טבע",
    "חוק עזר לרשות נחל הירקון (שמירה על הירקון וגדותיו)",
    "חוק שלל המלחמה",
}


def _filter_subpages(titles: list[str]) -> list[str]:
    title_set = set(titles)
    kept = []
    for t in titles:
        if "/" in t:
            parent = t.rsplit("/", 1)[0]
            if parent in title_set:
                continue  # תת-דף - לא חוק עצמאי (ראו TASKS.md משימה 7)
        kept.append(t)
    return kept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--titles-cache", type=Path, default=None)
    parser.add_argument("--kns-cache", type=Path, default=None)
    parser.add_argument("--existing-state", type=Path, default=None, help="JSON {law_id: wikitext_revision_id} - ראו docstring")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.titles_cache and args.titles_cache.exists():
        all_titles = json.loads(args.titles_cache.read_text(encoding="utf-8"))
    else:
        all_titles = list_category_titles()
    before = len(all_titles)
    all_titles = [t for t in all_titles if is_primary_legislation_title(t)]
    print(f"חוקים/חוקי-יסוד: {before:,} -> {len(all_titles):,}", file=sys.stderr)

    if args.kns_cache and args.kns_cache.exists():
        kns_records = json.loads(args.kns_cache.read_text(encoding="utf-8"))
    else:
        kns_records = fetch_israel_laws()
    before = len(all_titles)
    all_titles = [t for t in all_titles if should_ingest(classify_validity(t, kns_records))]
    print(f"סינון תוקף מול KNS: {before:,} -> {len(all_titles):,}", file=sys.stderr)

    before = len(all_titles)
    all_titles = _filter_subpages(all_titles)
    print(f"סינון תת-דפים: {before:,} -> {len(all_titles):,}", file=sys.stderr)

    before = len(all_titles)
    all_titles = [t for t in all_titles if t not in _DROPPED_TITLES]
    print(f"סינון 4 חוקים שהוצאו במפורש: {before:,} -> {len(all_titles):,}", file=sys.stderr)

    existing_state: dict[str, int] = {}
    if args.existing_state and args.existing_state.exists():
        existing_state = json.loads(args.existing_state.read_text(encoding="utf-8"))
        print(f"מצב DB קיים: {len(existing_state)} חוקים כבר טעונים", file=sys.stderr)

    if args.limit:
        all_titles = all_titles[: args.limit]

    manifest = []
    skipped_existing = 0
    resolution_failures = []
    other_failures = []

    for i, title in enumerate(all_titles):
        try:
            export = fetch_with_retry(title)
        except NetworkIngestError as exc:
            other_failures.append({"title": title, "category": "network", "error": str(exc)})
            print(f"FAIL [{i+1}/{len(all_titles)}] {title} - [network] {exc}")
            continue
        wikitext = extract_wikitext_body(export["export_xml"])

        magar1 = None
        magar2 = None
        full_title = None
        for line in wikitext.split("\n"):
            s = line.strip()
            if magar1 is None and s.startswith("{{ח:מאגר|"):
                magar1 = s[len("{{ח:מאגר|") : s.index("}}")]
            if magar2 is None and s.startswith("{{ח:מאגר2|"):
                magar2 = s[len("{{ח:מאגר2|") : s.index("}}")]
            if full_title is None and s.startswith("{{ח:כותרת|"):
                full_title = s[len("{{ח:כותרת|") : s.index("}}")]
            if magar1 and magar2 and full_title:
                break

        try:
            law_id = resolve_law_id(
                wikitext_title=title, magar1=magar1, magar2=magar2,
                kns_records=kns_records, wikitext_full_title=full_title,
            )
        except LawIdResolutionError as exc:
            resolution_failures.append({"title": title, "error": str(exc)})
            print(f"FAIL [{i+1}/{len(all_titles)}] {title} - [law_id] {exc}")
            continue

        revision_id = None
        try:
            revision_id = extract_revision_id(export["export_xml"])
        except Exception:
            pass
        if law_id in existing_state and revision_id is not None and existing_state[law_id] == revision_id:
            skipped_existing += 1
            print(f"SKIP [{i+1}/{len(all_titles)}] {title} - {law_id} כבר טעון (revision {revision_id})")
            continue

        try:
            plan = build_ingest_plan(
                law_id, title, source_ref="", law_is_new=True,
                fetch=lambda _t, _export=export: _export,
                validity=classify_validity(title, kns_records),
            )
        except SanityIngestError as exc:
            other_failures.append({"title": title, "category": "sanity", "error": str(exc)})
            print(f"FAIL [{i+1}/{len(all_titles)}] {title} - [sanity] {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            other_failures.append({"title": title, "category": "unexpected", "error": f"{type(exc).__name__}: {exc}"})
            print(f"FAIL [{i+1}/{len(all_titles)}] {title} - [unexpected] {type(exc).__name__}: {exc}")
            traceback.print_exc(file=sys.stderr)
            continue

        sql_file = args.out_dir / f"{law_id}.sql"
        sql_file.write_text(plan.sql, encoding="utf-8")
        manifest.append(
            {
                "law_id": law_id,
                "title": title,
                "sql_file": str(sql_file),
                "node_count": plan.node_count,
                "section_count": plan.section_count,
                "total_text_chars": plan.total_text_chars,
                "magar1": magar1,
                "magar2": magar2,
            }
        )
        print(f"OK   [{i+1}/{len(all_titles)}] {title} -> {law_id} ({plan.node_count} nodes)")

    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print(f"===== סיכום: {len(manifest)} מוכנים לטעינה, {skipped_existing} כבר טעונים (דולגו) =====")
    print(f"כשלי law_id: {len(resolution_failures)}")
    for f in resolution_failures:
        print(f"  {f['title']}: {f['error']}")
    print(f"כשלים אחרים: {len(other_failures)}")
    for f in other_failures:
        print(f"  [{f['category']}] {f['title']}: {f['error']}")
    total_nodes = sum(m["node_count"] for m in manifest)
    total_chars = sum(m["total_text_chars"] for m in manifest)
    print(f"סה\"כ nodes: {total_nodes:,}, סה\"כ תווי טקסט: {total_chars:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
