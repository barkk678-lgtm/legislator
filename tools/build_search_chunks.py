#!/usr/bin/env python3
"""בונה ומטעין search_chunks לכל הקורפוס (משימה א, 1.3 - חיפוש סמנטי).

**לא הורץ בפועל הלילה (2026-09-16/17)** - חסום בשתי חסימות נפרדות,
שתיהן מתועדות ב-docs/night-report.md:
1. `SUPABASE_SERVICE_ROLE_KEY` לא זמין בסשן (נדרש לכתיבת REST).
2. `api.openai.com` חסום ברמת מדיניות ה-proxy של סביבת ה-agent
   (`OPENAI_API_KEY` תקין, אבל אין תקשורת רשת לשרת בכלל).

מוכן לרוץ ברגע ששני אלה זמינים (למשל בסביבת production/Vercel):
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... OPENAI_API_KEY=... \\
        python3 tools/build_search_chunks.py [--law-id law-XXXX] [--dry-run]

בלי --law-id: עובר על כל 1,093 החוקים ב-DB (מ-/rest/v1/laws, אותו
דפוס בדיוק כמו law_registry._load_db_law - שחזור עץ מ-nodes, לא
פרסור מחדש). --dry-run: מריץ chunking בלבד (בלי embeddings/כתיבה) -
שימושי למדידת כמות ה-chunks/תווים בלי לבזבז קריאות API.

התקדמות נשמרת ב-build_search_chunks_progress.jsonl (לצד הסקריפט) -
אותו דפוס בדיוק כמו load_corpus_to_supabase_rest.py (ריצה חוזרת
מדלגת על חוקים שכבר נטענו בהצלחה).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
from chunking import chunk_law  # noqa: E402
from node import LegislativeNode  # noqa: E402
from embeddings import EmbeddingTooLongError, embed_batch  # noqa: E402

PROGRESS_LOG = Path(__file__).parent / "build_search_chunks_progress.jsonl"
EMBED_BATCH_SIZE = 50  # OpenAI תומך ביותר, אבל batch קטן שומר על retry זול אם משהו נכשל


def _supabase_config() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    missing = [n for n, v in [("SUPABASE_URL", url), ("SUPABASE_SERVICE_ROLE_KEY", key)] if not v]
    if missing:
        print(f"שגיאה: חסרים משתני סביבה: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return url.rstrip("/"), key


def _rest_request(base_url, key, method, path, body=None, prefer=None):
    url = f"{base_url}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    if prefer:
        req.add_header("Prefer", prefer)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} על {method} {path}: {e.read().decode('utf-8', 'replace')[:500]}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"רשת נכשלה אחרי 4 ניסיונות ({method} {path}): {e}") from None


def _fetch_all_pages(base_url, key, path, params, page_size=1000):
    """זהה בכוונה ל-law_registry._fetch_all_pages - אותה מגבלת 1,000
    שורות של PostgREST, אותו תיקון."""
    rows = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode({**params, "limit": page_size, "offset": offset})
        _, page = _rest_request(base_url, key, "GET", f"{path}?{qs}")
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def _build_tree(rows: list[dict]) -> LegislativeNode:
    """זהה ל-law_registry._build_tree_from_rows - שכפול מכוון (לא
    ייבוא apps/api מכאן: tools/ לא תלוי ב-apps/, כיוון תלות אחד בלבד
    בפרויקט הזה - apps/api תלוי ב-packages/, לא להפך)."""
    nodes_by_id, children_ids, root_id = {}, {}, None
    for row in rows:
        node = LegislativeNode(
            id=row["id"], node_type=row["node_type"], number=row["number"] or "",
            margin_title=row["margin_title"], text=row["text"] or "",
        )
        nodes_by_id[row["id"]] = node
        if row["parent_id"] is None:
            root_id = row["id"]
        else:
            children_ids.setdefault(row["parent_id"], []).append((row["raw_order"], row["id"]))
    for parent_id, ordered in children_ids.items():
        parent = nodes_by_id.get(parent_id)
        if parent:
            parent.children = [nodes_by_id[cid] for _, cid in sorted(ordered)]
    return nodes_by_id[root_id]


def load_law_tree(base_url, key, law_id: str) -> LegislativeNode:
    _, law_rows = _rest_request(
        base_url, key, "GET",
        f"/rest/v1/laws?id=eq.{urllib.parse.quote(law_id)}"
        "&select=full_title,law_versions!laws_current_version_fk(id)",
    )
    version_id = law_rows[0]["law_versions"]["id"]
    rows = _fetch_all_pages(
        base_url, key, "/rest/v1/nodes",
        {"law_version_id": f"eq.{version_id}",
         "select": "id,parent_id,raw_order,node_type,number,margin_title,text"},
    )
    root = _build_tree(rows)
    root.full_title = law_rows[0]["full_title"]
    return root


def list_all_law_ids(base_url, key) -> list[str]:
    rows = _fetch_all_pages(base_url, key, "/rest/v1/laws", {"select": "id", "current_version_id": "not.is.null"})
    return [r["id"] for r in rows]


def build_and_load_law(base_url, key, law_id: str, *, dry_run: bool) -> tuple[str, int, int]:
    """מחזירה (law_id, chunks_written, chunks_skipped)."""
    root = load_law_tree(base_url, key, law_id)
    chunks = chunk_law(root)
    if dry_run:
        return law_id, len(chunks), 0

    # מוחקים chunks קיימים של החוק הזה קודם (idempotent - ריצה חוזרת
    # אחרי תיקון בפרסר/chunking לא תשאיר chunks יתומים מגרסה קודמת).
    _rest_request(base_url, key, "DELETE", f"/rest/v1/search_chunks?law_id=eq.{urllib.parse.quote(law_id)}")

    written = skipped = 0
    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i : i + EMBED_BATCH_SIZE]
        try:
            vectors = embed_batch([c.text for c in batch])
        except EmbeddingTooLongError:
            # batch שלם נכשל אם input בודד בתוכו חורג (ראו embeddings.py
            # docstring) - נופלים לאחד-אחד כדי לבודד רק את החריג/ים.
            vectors = []
            for c in batch:
                try:
                    vectors.append(embed_batch([c.text])[0])
                except EmbeddingTooLongError:
                    skipped += 1
                    print(f"  דילוג (חריגת אורך): {law_id} סעיף {c.section_number} chunk {c.chunk_index}", file=sys.stderr)
                    vectors.append(None)
        rows = [
            {
                "law_id": c.law_id, "section_number": c.section_number, "chunk_index": c.chunk_index,
                "node_ids": c.node_ids, "context_prefix": c.context_prefix, "body": c.body,
                "contains_raw_block": c.contains_raw_block, "embedding": v,
            }
            for c, v in zip(batch, vectors) if v is not None
        ]
        if rows:
            _rest_request(base_url, key, "POST", "/rest/v1/search_chunks", body=rows, prefer="return=minimal")
            written += len(rows)
    return law_id, written, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--law-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base_url, key = _supabase_config()
    law_ids = [args.law_id] if args.law_id else list_all_law_ids(base_url, key)

    already_done = set()
    if PROGRESS_LOG.exists() and not args.dry_run:
        for line in PROGRESS_LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                already_done.add(json.loads(line)["law_id"])
    todo = [lid for lid in law_ids if lid not in already_done]
    print(f"סה\"כ חוקים: {len(law_ids)}, כבר נטענו: {len(already_done)}, נותרו: {len(todo)}")

    total_written = total_skipped = 0
    log_f = None if args.dry_run else PROGRESS_LOG.open("a", encoding="utf-8")
    try:
        for i, law_id in enumerate(todo, 1):
            try:
                lid, written, skipped = build_and_load_law(base_url, key, law_id, dry_run=args.dry_run)
                total_written += written
                total_skipped += skipped
                if log_f:
                    log_f.write(json.dumps({"law_id": lid, "chunks": written, "skipped": skipped}) + "\n")
                    log_f.flush()
                if i % 25 == 0 or args.dry_run:
                    print(f"[{i}/{len(todo)}] {law_id}: {written} chunks" + (f", {skipped} דולגו" if skipped else ""))
            except Exception as e:  # noqa: BLE001 - חוק אחד לא עוצר את כל הריצה, כמו load_corpus_to_supabase_rest
                print(f"[{i}/{len(todo)}] ERROR {law_id}: {e}", file=sys.stderr)
    finally:
        if log_f:
            log_f.close()

    print(f"סיום. chunks שנכתבו: {total_written}, דולגו (חריגת אורך): {total_skipped}")


if __name__ == "__main__":
    main()
