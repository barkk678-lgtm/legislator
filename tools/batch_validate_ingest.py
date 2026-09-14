#!/usr/bin/env python3
"""ולידציה של ingest על מדגם מהקורפוס המלא - שלב 1.2, לפני ingest מלא.

שולף+מפרסר+בודק שפיות (packages/corpus/db_ingest.build_ingest_plan)
על מדגם אקראי מהקורפוס האמיתי (wikitext_client.list_category_titles),
בלי לכתוב ל-DB - זו בדיקת "כמה יעבור נקי" (ראו docs/strategy/decisions.md
"1.2 - שלוש מנות"), לא ה-ingest המלא עצמו.

שימוש:
    python3 tools/batch_validate_ingest.py <n> [--seed N]
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
from wikitext_client import list_category_titles  # noqa: E402


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
    args = parser.parse_args()

    if args.titles_cache and args.titles_cache.exists():
        all_titles = json.loads(args.titles_cache.read_text(encoding="utf-8"))
    else:
        all_titles = list_category_titles()
        if args.titles_cache:
            args.titles_cache.write_text(json.dumps(all_titles, ensure_ascii=False), encoding="utf-8")

    rng = random.Random(args.seed)
    sample = rng.sample(all_titles, min(args.n, len(all_titles)))

    successes = []
    failures = []

    for i, title in enumerate(sample):
        law_id = slugify(title, i)
        t0 = time.monotonic()
        try:
            plan = build_ingest_plan(law_id, title, source_ref="", law_is_new=True)
            elapsed = time.monotonic() - t0
            successes.append(
                {
                    "title": title,
                    "node_count": plan.node_count,
                    "section_count": plan.section_count,
                    "citation_count": plan.citation_count,
                    "token_count": plan.token_count,
                    "total_text_chars": plan.total_text_chars,
                    "elapsed_s": round(elapsed, 2),
                }
            )
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
        print(f"גודל הקטגוריה המלאה: {len(all_titles):,} כותרות")
        est_total_chars = total_chars / len(successes) * len(all_titles)
        est_total_tokens = est_total_chars / 4  # קירוב גס מקובל: ~4 תווים לטוקן
        print(f"הערכה לקורפוס המלא: ~{est_total_chars:,.0f} תווים, ~{est_total_tokens:,.0f} טוקנים")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
