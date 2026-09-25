#!/usr/bin/env python3
"""טעינה מלאה מחדש של הקורפוס אחרי שינוי פרסר - קודם השוואה, אחר כך כתיבה.

ח16-ב (ברק, 26.9): תיקון הפרסר נוגע ב-392 חוקים, מעל הסף של ~100 שנקבע
(docs/night-report.md, 19.9: "אם תיקון פרסור עתידי יגע ביותר מ-~100 חוקים,
טעינה מלאה נעשית פשוטה יותר מהחלפה סלקטיבית") - ולכן כל החוקים נטענים.

**שני שלבים, והראשון אינו כותב דבר:**

    python3 tools/reload_corpus.py plan --out DIR      # השוואה בלבד
    python3 tools/reload_corpus.py apply --dir DIR --reason "..."

`plan`: לכל חוק - שולף את הוויקיטקסט, **מוודא שזו אותה גרסה** שבמאגר
(`wikitext_revision_id`; גרסה שהשתנתה היא תוכן חדש, לא תיקון פרסר - היא
נרשמת ומדולגת, ו-check_for_update יטען אותה כגרסה חדשה), מפרסר בפרסר
הנוכחי, ומשווה צומת-צומת למאגר: מזהים, ו-md5 של טקסט + כותרת שוליים.
נכתב DIR/report.jsonl ו-DIR/<law>.sql לכל חוק שנבנה.

`apply`: לכל חוק ב-report עם status=planned - `replace_law_version_delete`
(RPC, מוחק את הגרסה הנוכחית ורושם ביומן) -> `load_one_law` (אותו נתיב
טעינה כמו כל הקורפוס) -> `record_law_version_replacement`. זה המנגנון
מ-16.9 (docs/strategy/decisions.md), לא קוד כתיבה חדש.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "corpus"))
sys.path.insert(0, str(ROOT / "tools"))

from db_ingest import SanityIngestError, build_ingest_plan, fetch_with_retry  # noqa: E402
from wikitext_client import extract_revision_id, extract_wikitext_body, extract_revision_timestamp  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402
from sql import query  # noqa: E402


def _h(text, margin_title) -> str:
    return hashlib.md5(f"{text or ''}\x1f{margin_title or ''}".encode("utf-8")).hexdigest()


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def _laws() -> list[dict]:
    return query(
        "select l.id, l.wikitext_title, l.current_version_id vid, v.wikitext_revision_id rev, "
        "coalesce(v.source_ref,'') source_ref from laws l join law_versions v on v.id = l.current_version_id "
        "order by l.id")


def _db_nodes(vid: int) -> dict[str, str]:
    rows = query(
        "select id, md5(coalesce(text,'') || chr(31) || coalesce(margin_title,'')) h "
        f"from nodes where law_version_id = {int(vid)}")
    return {r["id"]: r["h"] for r in rows}


def plan(out: Path, only: list[str] | None, limit: int | None) -> int:
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "report.jsonl"
    done = set()
    if report_path.exists():
        done = {json.loads(line)["law_id"] for line in report_path.read_text(encoding="utf-8").splitlines() if line}
    laws = [l for l in _laws() if (not only or l["id"] in only) and l["id"] not in done]
    if limit:
        laws = laws[:limit]
    print(f"{len(laws)} חוקים להשוואה ({len(done)} כבר בדוח)", flush=True)
    with report_path.open("a", encoding="utf-8") as rep:
        for i, law in enumerate(laws, 1):
            row = {"law_id": law["id"], "title": law["wikitext_title"], "old_vid": law["vid"]}
            try:
                export = fetch_with_retry(law["wikitext_title"])
                rev = extract_revision_id(export["export_xml"])
                if rev != law["rev"]:
                    row.update(status="revision_changed", old_rev=law["rev"], new_rev=rev)
                else:
                    wikitext = extract_wikitext_body(export["export_xml"])
                    as_of = extract_revision_timestamp(export["export_xml"])
                    tree = parse_wikitext(wikitext, law_id=law["id"], source_ref=law["source_ref"], as_of=as_of)
                    new = {n.id: _h(n.text, n.margin_title) for n in _walk(tree)}
                    old = _db_nodes(law["vid"])
                    changed = [k for k in new if k in old and new[k] != old[k]]
                    row.update(
                        old_nodes=len(old), new_nodes=len(new),
                        ids_only_old=sorted(set(old) - set(new))[:20], n_only_old=len(set(old) - set(new)),
                        ids_only_new=sorted(set(new) - set(old))[:20], n_only_new=len(set(new) - set(old)),
                        n_changed=len(changed), changed_sample=changed[:5])
                    if not changed and set(old) == set(new):
                        row["status"] = "unchanged"
                    else:
                        p = build_ingest_plan(law["id"], law["wikitext_title"], source_ref=law["source_ref"],
                                              law_is_new=False, fetch=lambda _t, _e=export: _e)
                        (out / f"{law['id']}.sql").write_text(p.sql, encoding="utf-8")
                        row["status"] = "planned"
            except SanityIngestError as e:
                row.update(status="sanity_failed", error=str(e)[:300])
            except Exception as e:  # noqa: BLE001
                row.update(status="error", error=f"{type(e).__name__}: {str(e)[:300]}")
            rep.write(json.dumps(row, ensure_ascii=False) + "\n")
            rep.flush()
            if i % 25 == 0 or row["status"] not in ("unchanged", "planned"):
                print(f"[{i}/{len(laws)}] {law['id']} {row['status']}", flush=True)
            time.sleep(0.2)
    return 0


def apply(directory: Path, reason: str, only: list[str] | None) -> int:
    from load_corpus_to_supabase_rest import _rest_request, load_one_law  # noqa: PLC0415

    rows = [json.loads(line) for line in (directory / "report.jsonl").read_text(encoding="utf-8").splitlines() if line]
    todo = [r for r in rows if r["status"] == "planned" and (not only or r["law_id"] in only)]
    applied_path = directory / "applied.jsonl"
    applied = set()
    if applied_path.exists():
        applied = {json.loads(line)["law_id"] for line in applied_path.read_text(encoding="utf-8").splitlines() if line}
    todo = [r for r in todo if r["law_id"] not in applied]
    print(f"{len(todo)} חוקים להחלפה", flush=True)
    failures = 0
    with applied_path.open("a", encoding="utf-8") as log:
        for i, r in enumerate(todo, 1):
            law_id = r["law_id"]
            out = {"law_id": law_id}
            try:
                _, resp = _rest_request("POST", "/rest/v1/rpc/replace_law_version_delete",
                                        body={"p_law_id": law_id, "p_reason": reason})
                log_id = resp[0]["log_id"]
                _, status, detail = load_one_law(directory / f"{law_id}.sql")
                out.update(log_id=log_id, status=status, detail=detail)
                if status == "ok":
                    vid = int(detail.split("version_id=")[1].split()[0])
                    nodes = int(detail.split("nodes=")[1].split()[0])
                    _rest_request("POST", "/rest/v1/rpc/record_law_version_replacement",
                                  body={"p_log_id": log_id, "p_new_version_id": vid, "p_new_node_count": nodes})
                else:
                    failures += 1
            except Exception as e:  # noqa: BLE001
                out.update(status="error", detail=f"{type(e).__name__}: {str(e)[:300]}")
                failures += 1
            log.write(json.dumps(out, ensure_ascii=False) + "\n")
            log.flush()
            if i % 25 == 0 or out["status"] != "ok":
                print(f"[{i}/{len(todo)}] {law_id} {out['status']} {out.get('detail', '')[:80]}", flush=True)
    print(f"כשלים: {failures}", flush=True)
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--only", nargs="*")
    p.add_argument("--limit", type=int)
    a = sub.add_parser("apply")
    a.add_argument("--dir", type=Path, required=True)
    a.add_argument("--reason", required=True)
    a.add_argument("--only", nargs="*")
    args = ap.parse_args()
    if args.cmd == "plan":
        return plan(args.out, args.only, args.limit)
    return apply(args.dir, args.reason, args.only)


if __name__ == "__main__":
    sys.exit(main())
