#!/usr/bin/env python3
"""סריקת קורפוס-שלם (לא מדגם) לשורות תוכן שלא נצרכות (ingest_checks.
check_no_unconsumed_content) - לא רק סופרת, אלא מסווגת כל שורה חשודה
לאחת משלוש קטגוריות היפותזה, כדי לענות על שאלת ברק (2026-09-14):
"אם זה עשרות חוקים - זה תיקון. אם זה מאות - זו אותה עבודת המעבר
לפרסור לא-שורתי שדחינו".

חייב לרוץ על כל הקורפוס המסונן (חוקים/חוקי-יסוד בתוקף), לא מדגם -
מטרת המדידה היא להכריע אם התופעה נדירה או שיטתית, ומדגם אקראי לא
עונה על זה במידה מספקת.

סיווג לכל שורה חשודה (היוריסטי, לא מדויק - מתועד ככזה):
  1. DUPLICATE  - תוכן השורה (או רובו) מופיע כבר בתוך השורה הבאה
     שלא ריקה - חשד לכפילות עריכה במקור (כמו מקרקעי ישראל).
  2. CONTINUATION - השורה הקודמת שלא ריקה לא מסתיימת בסימן פיסוק
     מסיים (. ; : ! ?) - חשד להמשך משפט שנשבר לשורה פיזית נפרדת.
  3. STANDALONE - לא כפילות ולא המשך ברור - טקסט עצמאי, ככל הנראה
     חסר לו תבנית פותחת ({{ח:ת}}/{{ח:ת|...}}) במקור.

שימוש:
    python3 tools/scan_unconsumed_content.py [--titles-cache F] [--kns-cache F] [--limit N]
"""

import argparse
import json
import re
import sys
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "corpus"))

from ingest_checks import (  # noqa: E402
    _CATEGORY_LINE_RE,
    _SKIP_ZONE_CLOSER,
    _SKIP_ZONE_OPENERS,
    _TABLE_CLOSE_RE,
    _TABLE_OPEN_RE,
    _TOC_DIV_CLOSE_LINE,
    _TOC_DIV_OPEN_RE,
)
from db_ingest import fetch_with_retry, NetworkIngestError  # noqa: E402
from knesset_odata import classify_validity, fetch_israel_laws, should_ingest  # noqa: E402
from wikitext_client import extract_wikitext_body, is_primary_legislation_title, list_category_titles  # noqa: E402

_TERMINAL_PUNCT = ".;:!?" + "”\"׃"  # תווי סיום משפט (כולל מרכאות סוגרות)
_TEMPLATE_NAME_RE = re.compile(r"\{\{([^|}]+)")


def find_unconsumed_lines(wikitext: str) -> list[tuple[int, str, str]]:
    """כמו ingest_checks.check_no_unconsumed_content, אבל מחזירה את
    הרשימה הגולמית (מספר שורה, טקסט, טקסט השורה הקודמת שלא-ריקה) -
    לא הודעה מפורמטת - כדי לאפשר סיווג בהמשך. אותה לוגיקה בדיוק,
    שכפול מכוון (לא ייבוא של הפונקציה הפנימית) כדי לא לצמד לפורמט
    ההודעה של ingest_checks."""
    results: list[tuple[int, str, str]] = []
    in_skip_zone = False
    in_toc_zone = False
    in_table_zone = False
    prev_nonblank = ""
    for line_number, raw_line in enumerate(wikitext.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if in_table_zone:
            if _TABLE_CLOSE_RE.search(line):
                in_table_zone = False
            prev_nonblank = line
            continue
        if in_toc_zone:
            if line == _TOC_DIV_CLOSE_LINE:
                in_toc_zone = False
            prev_nonblank = line
            continue
        if _TOC_DIV_OPEN_RE.match(line):
            in_toc_zone = True
            prev_nonblank = line
            continue
        if _TABLE_OPEN_RE.match(line):
            if not _TABLE_CLOSE_RE.search(line):
                in_table_zone = True
            prev_nonblank = line
            continue
        if line.startswith("{{"):
            match = _TEMPLATE_NAME_RE.match(line)
            name = match.group(1) if match else ""
            if name in _SKIP_ZONE_OPENERS:
                in_skip_zone = True
            elif name == _SKIP_ZONE_CLOSER:
                in_skip_zone = False
            elif "}}" in line:
                remainder = line.split("}}", 1)[1].strip()
                if _TABLE_OPEN_RE.match(remainder) and not _TABLE_CLOSE_RE.search(remainder):
                    in_table_zone = True
            prev_nonblank = line
            continue
        if in_skip_zone:
            prev_nonblank = line
            continue
        if _CATEGORY_LINE_RE.match(line):
            prev_nonblank = line
            continue
        results.append((line_number, line, prev_nonblank))
        prev_nonblank = line
    return results


def classify(line: str, prev_line: str, next_line: str) -> str:
    if line and next_line and line in next_line:
        return "DUPLICATE"
    if prev_line and prev_line[-1] not in _TERMINAL_PUNCT:
        return "CONTINUATION"
    return "STANDALONE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--titles-cache", type=Path, default=None)
    parser.add_argument("--kns-cache", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="להגביל למספר חוקים ראשונים (בדיקה מהירה)")
    args = parser.parse_args()

    if args.titles_cache and args.titles_cache.exists():
        all_titles = json.loads(args.titles_cache.read_text(encoding="utf-8"))
    else:
        all_titles = list_category_titles()

    before = len(all_titles)
    all_titles = [t for t in all_titles if is_primary_legislation_title(t)]
    print(f"מסונן לחוקים/חוקי-יסוד בלבד: {before:,} -> {len(all_titles):,}", file=sys.stderr)

    if args.kns_cache and args.kns_cache.exists():
        kns_records = json.loads(args.kns_cache.read_text(encoding="utf-8"))
    else:
        kns_records = fetch_israel_laws()
    before = len(all_titles)
    all_titles = [t for t in all_titles if should_ingest(classify_validity(t, kns_records))]
    print(f"מסונן לפי תוקף (KNS_IsraelLaw): {before:,} -> {len(all_titles):,}", file=sys.stderr)

    if args.limit:
        all_titles = all_titles[: args.limit]

    laws_with_any = 0
    laws_by_category = Counter()  # חוק נספר בכל קטגוריה שיש לו בה לפחות שורה אחת
    lines_by_category = Counter()
    total_lines = 0
    fetch_errors = []
    examples_by_category = {"DUPLICATE": [], "CONTINUATION": [], "STANDALONE": []}

    for i, title in enumerate(all_titles):
        try:
            export = fetch_with_retry(title)
            wikitext = extract_wikitext_body(export["export_xml"])
        except NetworkIngestError as exc:
            fetch_errors.append((title, str(exc)))
            print(f"[{i+1}/{len(all_titles)}] {title} - שגיאת רשת, מדולג: {exc}", file=sys.stderr)
            continue
        except Exception as exc:  # noqa: BLE001
            fetch_errors.append((title, f"{type(exc).__name__}: {exc}"))
            print(f"[{i+1}/{len(all_titles)}] {title} - שגיאה לא צפויה, מדולג: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            continue

        flagged = find_unconsumed_lines(wikitext)
        if not flagged:
            if (i + 1) % 50 == 0:
                print(f"[{i+1}/{len(all_titles)}] ...", file=sys.stderr)
            continue

        laws_with_any += 1
        lines = wikitext.splitlines()
        law_categories = set()
        for line_number, line_text, prev_text in flagged:
            next_text = ""
            for j in range(line_number, min(line_number + 3, len(lines))):
                candidate = lines[j].strip()
                if candidate:
                    next_text = candidate
                    break
            cat = classify(line_text, prev_text, next_text)
            law_categories.add(cat)
            lines_by_category[cat] += 1
            total_lines += 1
            if len(examples_by_category[cat]) < 8:
                examples_by_category[cat].append((title, line_number, line_text))
        for cat in law_categories:
            laws_by_category[cat] += 1
        print(f"[{i+1}/{len(all_titles)}] {title} - {len(flagged)} שורות לא נצרכות ({sorted(law_categories)})")

    print()
    print("===== סיכום סריקת קורפוס-שלם =====")
    print(f"סה\"כ חוקים נסרקו: {len(all_titles)}, שגיאות שליפה: {len(fetch_errors)}")
    print(f"חוקים עם לפחות שורה לא-נצרכת אחת: {laws_with_any}")
    print(f"סה\"כ שורות לא-נצרכות: {total_lines}")
    print()
    print("לפי קטגוריה (חוק יכול להימנות ביותר מקטגוריה אחת):")
    for cat in ("DUPLICATE", "CONTINUATION", "STANDALONE"):
        print(f"  {cat}: {laws_by_category[cat]} חוקים, {lines_by_category[cat]} שורות")
    print()
    for cat in ("DUPLICATE", "CONTINUATION", "STANDALONE"):
        print(f"--- דוגמאות {cat} ---")
        for title, line_number, line_text in examples_by_category[cat]:
            print(f"  {title} שורה {line_number}: {line_text[:120]!r}")
    if fetch_errors:
        print()
        print("שגיאות שליפה:")
        for title, err in fetch_errors:
            print(f"  {title}: {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
