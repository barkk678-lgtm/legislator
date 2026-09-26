#!/usr/bin/env python3
"""הבדיקה בקנה מידה של קריאת ה-PDF (הסתייגויות 1, 26.9) - רצה ב-GitHub Actions.

    python3 tools/reservations_scale_sample.py --n 60 --delay 8 --work /tmp/sample --out results.json

1. **בדיקת גישה** - קובץ אחד מ-fs.knesset.gov.il. בלי גישה - יציאה עם הודעה
   (לא מדגם חלקי שנראה כמו תוצאה).
2. **המדגם** - מ-KNS_DocumentBill, "הצעת חוק לקריאה השנייה והשלישית", PDF;
   N מסמכים בפיזור שווה על פני כל המזהים (לא רק האחרונים), דטרמיניסטי.
3. **הורדה לאט** - השהיה בין בקשות (ברירת מחדל 8 שניות + אקראיות קטנה);
   חסימה (403/429) - המתנה ארוכה וניסיון אחד נוסף, ושתי חסימות ברצף - עצירה.
   מאגר הכנסת חוסם בקשות מרובות (ברק, 26.9).
4. **המדידה** - tools/reservations_quote_check.check על כל קובץ.

**המדגם לא נכנס לריפו** - הקבצים יושבים בתיקייה זמנית של ה-runner.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "knesset"))
sys.path.insert(0, str(ROOT / "tools"))

import odata  # noqa: E402
import reservations_quote_check as quote_check  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
DOC_TYPE = "הצעת חוק לקריאה השנייה והשלישית"


def _url(row: dict) -> str:
    return (row.get("FilePath") or "").replace("\\", "/")


FILTER = f"GroupTypeDesc eq '{DOC_TYPE}' and ApplicationDesc eq 'PDF'"


def _row_at(client: httpx.Client, skip: int) -> dict | None:
    """שורה אחת במקום skip (לפי Id) - בקשה קטנה אחת. **לא עימוד על כל
    הטבלה:** ה-WAF של הכנסת (474) חוסם עשרות בקשות רצופות, גם קטנות."""
    params = {"$filter": FILTER, "$select": "Id,BillID,FilePath", "$orderby": "Id",
              "$top": "1", "$skip": str(skip)}
    resp = client.get(f"{odata.BASE_URL}/KNS_DocumentBill", params=params)
    if resp.status_code != 200:
        print(f"   OData: HTTP {resp.status_code} (skip={skip})", flush=True)
        return None
    values = resp.json().get("value", [])
    return values[0] if values else None


def _row_by_id(client: httpx.Client, doc_id: str) -> dict | None:
    resp = client.get(f"{odata.BASE_URL}/KNS_DocumentBill",
                      params={"$filter": f"Id eq {int(doc_id)}", "$select": "Id,BillID,FilePath"})
    if resp.status_code != 200:
        print(f"   OData: HTTP {resp.status_code} (Id={doc_id})", flush=True)
        return None
    values = resp.json().get("value", [])
    return values[0] if values else None


def download(client: httpx.Client, url: str, dest: Path, delay: float) -> str:
    for attempt in range(2):
        try:
            resp = client.get(url)
        except httpx.HTTPError as exc:
            if attempt:
                return f"network: {type(exc).__name__}"
            time.sleep(delay * 4)
            continue
        if resp.status_code in (403, 429):
            if attempt:
                return f"blocked: HTTP {resp.status_code}"
            print(f"   חסימה (HTTP {resp.status_code}) - המתנה ארוכה", flush=True)
            time.sleep(120)
            continue
        if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
            return f"bad: HTTP {resp.status_code}, {len(resp.content)} bytes"
        dest.write_bytes(resp.content)
        return "ok"
    return "failed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--delay", type=float, default=8.0)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ids", default="", help="מזהי מסמך (Id) מופרדים בפסיקים - במקום מדגם; לאבחון")
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)

    ids = [i.strip() for i in args.ids.split(",") if i.strip().isdigit()]
    if ids:
        offsets = ids
        print(f"אבחון: {len(ids)} מסמכים לפי מזהה", flush=True)
    else:
        total_docs = odata.count("KNS_DocumentBill", filter=FILTER)
        print(f"{total_docs} נוסחים לקריאה שנייה ושלישית (PDF) ב-OData", flush=True)
        offsets = [int(i * total_docs / args.n) for i in range(args.n)]
    downloads: dict[str, str] = {}
    blocked_in_row = 0
    with httpx.Client(timeout=90.0, headers=UA, follow_redirects=True) as client, \
            httpx.Client(timeout=60.0, headers={**UA, "Accept": "application/json"}) as feed:
        for i, skip in enumerate(offsets, 1):
            if i > 1:
                time.sleep(args.delay + random.uniform(0, args.delay / 2))
            row = _row_by_id(feed, skip) if ids else _row_at(feed, skip)
            if row is None or not _url(row).startswith("https://fs.knesset.gov.il/"):
                downloads[f"skip{skip}"] = "no row"
                continue
            time.sleep(args.delay / 2)
            status = download(client, _url(row), args.work / f"{row['Id']}.pdf", args.delay)
            downloads[str(row["Id"])] = status
            print(f"[{i}/{len(offsets)}] {row['Id']}: {status}", flush=True)
            if i == 1 and status != "ok":
                # 1. גישה: הקובץ הראשון נכשל - אין טעם להמשיך, וזו לא תוצאה.
                args.out.write_text(json.dumps({"access": status, "url": _url(row)}, ensure_ascii=False),
                                    encoding="utf-8")
                print(f"אין גישה לקבצים מה-runner ({status}, {_url(row)}) - המדגם לא הורץ.")
                return 2
            if i == 1:
                print(f"בדיקת גישה ל-fs.knesset.gov.il: עברה ({_url(row)})", flush=True)
            blocked_in_row = blocked_in_row + 1 if status.startswith("blocked") else 0
            if blocked_in_row >= 2:
                print("שתי חסימות ברצף - עוצרים את ההורדה.", flush=True)
                break
    rows = offsets

    # 4. המדידה
    summaries, quotes, diagnoses = [], [], []
    for pdf in sorted(args.work.glob("*.pdf")):
        try:
            qs, summary = quote_check.check(pdf)
        except Exception as exc:  # noqa: BLE001
            summaries.append({"file": pdf.name, "error": f"{type(exc).__name__}: {exc}"[:300]})
            continue
        summaries.append(summary)
        quotes += [q.__dict__ for q in qs]
        try:
            diagnoses += quote_check.diagnose(pdf, qs)
        except Exception as exc:  # noqa: BLE001
            print(f"  אבחון נכשל ב-{pdf.name}: {type(exc).__name__}: {exc}"[:200])

    counts = Counter(q["result"] for q in quotes)
    total = len(quotes)
    found = counts["exact"] + counts["typography"] + counts["inner_quotes"]
    with_quotes = sum(1 for s in summaries if s.get("quotes"))
    errors = [s for s in summaries if "error" in s]
    no_sections = [s["file"] for s in summaries if not s.get("error") and not s.get("sections")]
    print("\n══ תוצאות ══")
    print(f"הורדו {sum(v == 'ok' for v in downloads.values())} מתוך {len(rows)}; "
          f"{with_quotes} עם הסתייגויות שמצטטות מההצעה; {len(errors)} שגיאות קריאה; "
          f"{len(no_sections)} בלי סעיפים שזוהו")
    if total:
        print(f"ציטוטים: {total} - נמצאו {found} ({100 * found / total:.1f}%), "
              f"מילה במילה {counts['exact']} ({100 * counts['exact'] / total:.1f}%)")
        print("לפי סוג:", dict(counts))
        # הכרעה ז (26.9): קובץ שהספרות בשכבת הטקסט שלו משובשות (263401) - כל ההצעה לא
        # ודאית ואין בה עוגנים; ציטוט "נמצא" בו רק כי גם ההסתייגות משובשת באותו אופן.
        bad = {s["file"] for s in summaries if any("אינם קריאים" in w for w in s.get("warnings", []))}
        if bad:
            rest = [q for q in quotes if q["file"] not in bad]
            ok = sum(q["result"] in ("exact", "typography", "inner_quotes") for q in rest)
            print(f"קבצים עם ספרות לא קריאות (לא ודאיים, בלי עוגנים): {sorted(bad)} - "
                  f"{total - len(rest)} ציטוטים; בלעדיהם: {ok}/{len(rest)} ({100 * ok / max(1, len(rest)):.1f}%)")
    for s in summaries:
        if s.get("error"):
            print(f"  שגיאה {s['file']}: {s['error']}")
        elif s.get("quotes"):
            print(f"  {s['file']}: {s['quotes']} ציטוטים {s['counts']} | סעיפים: {s['sections']}")
    print("\n── ציטוטים שלא נמצאו (עד 150) ──")
    for q in [q for q in quotes if q["result"] in ("missing", "section_only")][:150]:
        print(f"  {q['file']} #{q['reservation']} [{q['result']}] {q['heading']} {q['unit'] or '-'} {q['kind']}: {q['phrase'][:120]}")
    print(f"\nבלי סעיפים: {no_sections[:40]}")
    print("\n── אבחון הכשלים ──")
    print("לפי סוג:", dict(Counter(d["diagnosis"] for d in diagnoses)))
    by_file = Counter((d["file"], d["diagnosis"]) for d in diagnoses)
    for (f, kind), n in sorted(by_file.items()):
        print(f"  {f}: {kind} x{n}")
    for d in diagnoses[:200]:
        print(f"  {d['file']} #{d['reservation']} [{d['diagnosis']} {d['ratio']}] {d['phrase'][:70]!r} ~ {d['closest'][:90]!r}")
        if d.get("where"):
            print(f"      {d['where'][:200]}")
    for s in summaries:
        if s.get("section_numbers"):
            dup = sorted({n for n in s["section_numbers"] if s["section_numbers"].count(n) > 1})
            print(f"  {s['file']}: {len(s['section_numbers'])} סעיפים, כפולים: {dup[:20]}")
    args.out.write_text(json.dumps({"downloads": downloads, "summaries": summaries, "quotes": quotes,
                                    "diagnoses": diagnoses},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
