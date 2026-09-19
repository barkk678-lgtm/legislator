#!/usr/bin/env python3
"""בודק אילו חוקים בקורפוס התעדכנו בוויקיטקסט מאז שנטענו.

**מה זה מממש:** `docs/strategy/plan.md` §1.2 - "הדאטהבייס הוא
מטמון מנוהל, לא ארכיון". התוכנית נכתבה ב-13.9 ו**מעולם לא הופעלה**:
`latest_known_revision_id` ו-`latest_checked_at` היו NULL בכל
1,109 החוקים. התוצאה - חוק ניירות ערך הוצג במערכת בנוסח שאינו
הדין, בלי שום סימן (נמצא 19.9).

**`recentchanges`, לא סריקה.** קריאה אחת למדיה-ויקי מחזירה אילו
דפים השתנו מאז חותמת זמן. סריקת 1,109 דפים הייתה 1,109 בקשות
ליום מול IP אחד; הדלתא היא בדרך כלל אפס עד עשרות.

**מה זה לא עושה: הוא לא טוען כלום.** הוא כותב
`latest_known_revision_id`/`latest_checked_at` ומדווח. הטעינה
עצמה היא החלטה נפרדת - ראו decisions.md.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "config"))
sys.path.insert(0, str(ROOT / "packages" / "corpus"))

from env_file import require_supabase  # noqa: E402
from wikitext_client import _get  # noqa: E402

API = "https://he.wikisource.org/w/api.php"
_PAGE = 1000  # תקרת PostgREST. **מפורשת**, לא מנוחשת.


def _api(params: dict) -> dict:
    """**משתמש ב-`wikitext_client._get`** ולא ב-urlopen ישיר:
    he.wikisource מחזיר 429 והוא כבר מטפל בזה עם `retry-after`.
    נכשלתי כאן פעם אחת לפני שהשתמשתי בו."""
    q = dict(params)
    q["format"] = "json"
    q["formatversion"] = "2"
    return json.loads(_get(f"{API}?{urllib.parse.urlencode(q)}").decode())


def recent_changes(since: str) -> dict[str, int]:
    """{כותרת: revid אחרון} לכל דף במרחב הראשי ששונה מאז `since`.

    `since` הוא ISO-8601 ב-UTC. מדפדף ב-`rccontinue` - **בלי להניח
    שדף אחד מספיק.**"""
    out: dict[str, int] = {}
    cont: dict = {}
    while True:
        data = _api({
            "action": "query", "list": "recentchanges",
            "rcstart": since, "rcdir": "newer", "rcnamespace": "0",
            "rclimit": "500", "rcprop": "title|ids|timestamp",
            "rctype": "edit|new", **cont,
        })
        for ch in data.get("query", {}).get("recentchanges", []):
            title = ch["title"]
            out[title] = max(out.get(title, 0), ch.get("revid", 0))
        if "continue" not in data:
            return out
        cont = data["continue"]


def _patch(url: str, key: str, path: str, where: dict, body: dict) -> None:
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}?" + urllib.parse.urlencode(where),
        data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    urllib.request.urlopen(req, timeout=120).read()


def _rest(url: str, key: str, path: str, params: dict) -> list:
    assert "order" in params, "בלי order הדפדוף אינו יציב"
    rows, off = [], 0
    while True:
        q = dict(params); q["limit"] = _PAGE; q["offset"] = off
        req = urllib.request.Request(
            f"{url}/rest/v1/{path}?" + urllib.parse.urlencode(q),
            headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=180) as r:
            page = json.loads(r.read().decode())
        rows.extend(page)
        if len(page) < _PAGE:
            return rows
        off += _PAGE


def main() -> int:
    url, key = require_supabase()
    laws = _rest(url, key, "laws",
                 {"select": "id,wikitext_title,current_version_id", "order": "id"})
    versions = {v["id"]: v for v in _rest(
        url, key, "law_versions",
        {"select": "id,wikitext_revision_id,ingested_at", "order": "id"})}

    since = os.environ.get("SINCE")
    if not since:
        stamps = [versions[l["current_version_id"]]["ingested_at"]
                  for l in laws if l["current_version_id"] in versions]
        since = min(stamps)[:19] + "Z"
    print(f"בודק שינויים בוויקיטקסט מאז {since} ...")
    changed = recent_changes(since)
    print(f"דפים שהשתנו במרחב הראשי: {len(changed)}")

    stale, checked = [], 0
    for law in laws:
        v = versions.get(law["current_version_id"])
        if not v:
            continue
        checked += 1
        live = changed.get(law["wikitext_title"])
        if live and live != v["wikitext_revision_id"]:
            stale.append({"id": law["id"], "title": law["wikitext_title"],
                          "ours": v["wikitext_revision_id"], "theirs": live})

    print(f"\nחוקים שנבדקו: {checked}")
    print(f"**חוקים שמפגרים אחרי ויקיטקסט: {len(stale)}**")
    for s in stale:
        print(f"   {s['title'][:56]:58s} {s['ours']} -> {s['theirs']}")

    # **כתיבה חזרה, בשתי בקשות ועוד אחת לכל חוק מפגר.**
    # הגרסה הראשונה כתבה `latest_known_revision_id` לכל 1,109
    # החוקים - 1,109 בקשות PATCH, שנחתכו באמצע (681). זה גם היה
    # מיותר: הסמנטיקה למטה מספיקה, והיא זולה.
    #
    #   latest_checked_at = NULL            -> מעולם לא נבדק
    #   נבדק, latest_known_revision_id NULL -> נבדק והוא עדכני
    #   שניהם, ושונים מהגרסה הטעונה         -> יש נוסח חדש יותר
    #
    # **"לא נבדק" אינו "עדכני".** הממשק מבדיל ביניהם.
    now = datetime.now(timezone.utc).isoformat()
    _patch(url, key, "laws", {"id": "not.is.null"},
           {"latest_checked_at": now, "latest_known_revision_id": None})
    for s_ in stale:
        _patch(url, key, "laws", {"id": f"eq.{s_['id']}"},
               {"latest_known_revision_id": s_["theirs"]})
    print(f"\nנרשם: {checked} חוקים נבדקו, {len(stale)} סומנו כמפגרים.")

    out = os.environ.get("OUT")
    if out:
        Path(out).write_text(json.dumps(stale, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"נכתב: {out}")
    # יציאה שאינה אפס כשיש פיגור - כדי שריצה מתוזמנת תצבע אדום
    # ולא תעבור בשקט. **זו כל הנקודה של התזמון.**
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
