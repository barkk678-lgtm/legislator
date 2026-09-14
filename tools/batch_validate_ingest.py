#!/usr/bin/env python3
"""ולידציה של ingest על מדגם מהקורפוס המלא - שלב 1.2, לפני ingest מלא.

שולף+מפרסר+בודק שפיות (packages/corpus/db_ingest.build_ingest_plan)
על מדגם אקראי מהקורפוס האמיתי (wikitext_client.list_category_titles),
בלי לכתוב ל-DB - זו בדיקת "כמה יעבור נקי" (ראו docs/strategy/decisions.md
"1.2 - שלוש מנות"), לא ה-ingest המלא עצמו.

מסונן כברירת מחדל לחוקים/חוקי-יסוד בלבד (is_primary_legislation_title) -
הוכרע במפורש 2026-09-13 שתקנות/צווים/כללים/פקודות לא נכנסים לקורפוס
כלל (לא רק לא-נבדקים) - ראו docs/strategy/decisions.md.

מסונן גם לפי תוקף מול KNS_IsraelLaw של הכנסת (knesset_odata.py) -
הוכרע במפורש 2026-09-14 שחוקים בטלים/פקעו/נושנו לא נטענים כלל
(אין להם ערך במערכת שמנסחת הצעות חוק חדשות). עקרון: שום חוק לא
נזרק בגלל שלא הצלחנו לבדוק אותו - "תקף" ו"לא ידוע" (אין התאמה/
עמימות) שניהם נטענים, רק התאמה חד-משמעית לבטל/פקע/נושן פוסלת.

שימוש:
    python3 tools/batch_validate_ingest.py <n> [--seed N] [--include-secondary] [--skip-validity-filter]
"""

import argparse
import json
import random
import sys
import time
import traceback
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "corpus"))

from db_ingest import NetworkIngestError, SanityIngestError, build_ingest_plan  # noqa: E402
from knesset_odata import classify_validity, fetch_israel_laws, should_ingest  # noqa: E402
from wikitext_client import is_primary_legislation_title, list_category_titles  # noqa: E402


def slugify(title: str, index: int) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = "".join(c for c in normalized if ord(c) < 128 and (c.isalnum() or c == " "))
    ascii_only = ascii_only.strip().replace(" ", "-").lower()
    return f"{index:04d}-{ascii_only[:40]}" if ascii_only else f"{index:04d}-law"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("n", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--titles-cache", type=Path, default=None)
    parser.add_argument("--include-secondary", action="store_true", help="לכלול תקנות/צווים/כללים/פקודות (לא ברירת המחדל - ראו decisions.md)")
    parser.add_argument("--kns-cache", type=Path, default=None, help="קובץ מטמון לרשומות KNS_IsraelLaw (2,024 רשומות, לא משתנה תדיר)")
    parser.add_argument("--skip-validity-filter", action="store_true", help="לדלג על סינון תוקף מול הכנסת (ברירת המחדל: מסונן)")
    args = parser.parse_args()

    if args.titles_cache and args.titles_cache.exists():
        all_titles = json.loads(args.titles_cache.read_text(encoding="utf-8"))
    else:
        all_titles = list_category_titles()
        if args.titles_cache:
            args.titles_cache.write_text(json.dumps(all_titles, ensure_ascii=False), encoding="utf-8")

    if not args.include_secondary:
        before = len(all_titles)
        all_titles = [t for t in all_titles if is_primary_legislation_title(t)]
        print(f"מסונן לחוקים/חוקי-יסוד בלבד: {before:,} -> {len(all_titles):,}", file=sys.stderr)

    validity_by_title = {}
    if not args.skip_validity_filter:
        if args.kns_cache and args.kns_cache.exists():
            kns_records = json.loads(args.kns_cache.read_text(encoding="utf-8"))
        else:
            kns_records = fetch_israel_laws()
            if args.kns_cache:
                args.kns_cache.write_text(json.dumps(kns_records, ensure_ascii=False), encoding="utf-8")
        before = len(all_titles)
        excluded_by_desc = Counter()
        kept_titles = []
        for t in all_titles:
            match = classify_validity(t, kns_records)
            validity_by_title[t] = match
            if should_ingest(match):
                kept_titles.append(t)
            else:
                excluded_by_desc[match.law_validity_desc] += 1
        all_titles = kept_titles
        print(
            f"מסונן לפי תוקף (KNS_IsraelLaw): {before:,} -> {len(all_titles):,} "
            f"(הוצאו: {dict(excluded_by_desc)})",
            file=sys.stderr,
        )

    rng = random.Random(args.seed)
    sample = rng.sample(all_titles, min(args.n, len(all_titles)))

    successes = []
    failures = []
    all_id_collisions = []  # ראו node.LegislativeNode.id_collisions - נספר על פני
    # הקורפוס כדי לראות אם _unique_child_id יורה הרבה (דפוס לא-מזוהה) או נדיר
    # (בדיוק המקרה החריג שנמצא, ראו TASKS.md משימה 7 / decisions.md 2026-09-14).
    all_content_derived_ids = []  # ראו node.LegislativeNode.content_derived_ids -
    # id-ים שנגזרו מ-hash תוכן (רשימות לא-ממוספרות) - נספר גם אותם, כמבוקש.

    for i, title in enumerate(sample):
        law_id = slugify(title, i)
        t0 = time.monotonic()
        try:
            plan = build_ingest_plan(
                law_id, title, source_ref="", law_is_new=True,
                validity=validity_by_title.get(title),
            )
            elapsed = time.monotonic() - t0
            successes.append(
                {
                    "title": title,
                    "law_validity_desc": validity_by_title[title].law_validity_desc if title in validity_by_title else None,
                    "validity_match_method": validity_by_title[title].match_method if title in validity_by_title else None,
                    "node_count": plan.node_count,
                    "section_count": plan.section_count,
                    "citation_count": plan.citation_count,
                    "token_count": plan.token_count,
                    "total_text_chars": plan.total_text_chars,
                    "elapsed_s": round(elapsed, 2),
                }
            )
            if plan.id_collisions:
                all_id_collisions.append((title, plan.id_collisions))
                for c in plan.id_collisions:
                    print(f"  [id_collision] {title}: {c}", file=sys.stderr)
            if plan.content_derived_ids:
                all_content_derived_ids.append((title, plan.content_derived_ids))
            print(f"OK   [{i+1}/{len(sample)}] {title} - {plan.node_count} nodes ({elapsed:.1f}s)")
        except NetworkIngestError as exc:
            failures.append({"title": title, "category": "network", "error": str(exc)})
            print(f"FAIL [{i+1}/{len(sample)}] {title} - [network] {exc}")
        except SanityIngestError as exc:
            failures.append({"title": title, "category": "sanity", "error": str(exc)})
            print(f"FAIL [{i+1}/{len(sample)}] {title} - [sanity] {exc}")
        except Exception as exc:  # noqa: BLE001 - כשל לא-צפוי, לא לבלוע, לתעד ולהמשיך
            failures.append({"title": title, "category": "unexpected", "error": f"{type(exc).__name__}: {exc}"})
            print(f"FAIL [{i+1}/{len(sample)}] {title} - [unexpected] {type(exc).__name__}: {exc}")
            traceback.print_exc(file=sys.stderr)

    print()
    print(f"===== סיכום: {len(successes)}/{len(sample)} הצליחו =====")
    if validity_by_title:
        method_counts = Counter(validity_by_title[t].match_method for t in sample if t in validity_by_title)
        print(f"שיטת התאמת תוקף במדגם: {dict(method_counts)}")
    total_collision_events = sum(len(cs) for _, cs in all_id_collisions)
    print(
        f"id_collisions: {total_collision_events} מקרים ב-{len(all_id_collisions)} חוקים "
        f"מתוך {len(successes)} שהצליחו (ראו stderr לפירוט)"
    )
    total_content_derived = sum(len(cs) for _, cs in all_content_derived_ids)
    print(
        f"content_derived_ids: {total_content_derived} id-ים נגזרו מתוכן ב-"
        f"{len(all_content_derived_ids)} חוקים מתוך {len(successes)} שהצליחו"
    )
    if failures:
        by_category = Counter(f["category"] for f in failures)
        print("כשלים לפי קטגוריה:", dict(by_category))
        print()
        print("כל הכשלים:")
        for f in failures:
            print(f"  [{f['category']}] {f['title']}: {f['error']}")

    if successes:
        total_nodes = sum(s["node_count"] for s in successes)
        total_chars = sum(s["total_text_chars"] for s in successes)
        print()
        print(f"סה\"כ nodes במדגם: {total_nodes}, ממוצע {total_nodes/len(successes):.0f} nodes/חוק")
        print(f"סה\"כ תווי טקסט (node.text בלבד): {total_chars:,}, ממוצע {total_chars/len(successes):,.0f}/חוק")
        print(f"גודל הקורפוס (אחרי סינון חוקים/חוקי-יסוד בלבד): {len(all_titles):,} כותרות")
        est_total_chars = total_chars / len(successes) * len(all_titles)
        est_total_tokens = est_total_chars / 4  # קירוב גס מקובל: ~4 תווים לטוקן
        print(f"הערכה לקורפוס המלא: ~{est_total_chars:,.0f} תווים, ~{est_total_tokens:,.0f} טוקנים")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
