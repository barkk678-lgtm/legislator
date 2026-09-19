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

**הוא גם טוען** (ברק שינה את ההחלטה, 19.9). הנימוק המקורי
לאי-טעינה היה "אל תשנה נוסח תחת משתמש שעורך", אבל הריצה ב-04:00
ואיש אינו עורך אז - והמחיר של ההחלטה היה שבעה חוקים מיושנים
במערכת במשך שבוע. ראו decisions.md, 2026-09-19 (ו).

**ההגנה היחידה: חוק עם טיוטה פתוחה אינו מתעדכן**, רק מסומן.
ראו `laws_with_open_drafts` - ובפרט את ההבחנה בין "אין טיוטות"
לבין "לא ידעתי לבדוק".
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
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


class DraftGuardUnavailable(Exception):
    """טבלת הטיוטות קיימת אבל לא ניתן לקרוא אותה. **לא מעדכנים.**"""


def laws_with_open_drafts(url: str, key: str) -> tuple[set[str], str]:
    """(מזהי חוקים עם טיוטה פתוחה, תיאור מצב ההגנה).

    **שלושה מצבים, ורק אחד מהם הוא "אין טיוטות":**

    1. הטבלה אינה קיימת (404/PGRST205) - אין טיוטות במערכת בכלל,
       ולכן אין מה להגן עליו. מדווח במפורש, כדי שאיש לא יבלבל
       בין "ההגנה עברה" לבין "ההגנה לא רצה".
    2. הטבלה קיימת ונקראה - מחזירים את מי שיש עליו טיוטה.
    3. הטבלה קיימת והקריאה נכשלה - **זורקים**. עדכון במצב הזה
       עלול לדרוס טיוטה פתוחה, ואין דרך לדעת.
    """
    try:
        rows = _rest(url, key, "drafts",
                     {"select": "law_id", "status": "eq.open", "order": "law_id"})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        if exc.code in (404, 400) and ("PGRST205" in body or "does not exist" in body):
            return set(), "טבלת drafts אינה קיימת - אין טיוטות במערכת"
        raise DraftGuardUnavailable(
            f"טבלת drafts קיימת אך הקריאה נכשלה ({exc.code}): {body[:160]}") from None
    ids = {r["law_id"] for r in rows}
    return ids, f"טבלת drafts נקראה - {len(ids)} חוקים עם טיוטה פתוחה"


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


def load_updated(stale: list[dict]) -> list[dict]:
    """טוען את החוקים שהתעדכנו כ**גרסה חדשה**, ומחזיר את הכשלים.

    **גרסה חדשה ולא החלפה:** כאן הנוסח עצמו השתנה ויש
    `wikitext_revision_id` חדש, ולכן הגרסה הישנה נשמרת
    כהיסטוריה ו-`current_version_id` זז אליה. `replace_law_version`
    נדרש רק כשהפרסר משתנה והנוסח לא - ראו decisions.md.

    משתמש באותה שרשרת בדיוק כמו `tools/load_corpus.py`
    (`build_ingest_plan` -> `load_one_law`), לא בקוד טעינה חדש.
    חוק שנכשל **אינו מפיל את השאר** - כולם מנוסים, והכשלים
    מוחזרים כדי שהריצה תיכשל ברעש בסוף."""
    import tempfile  # noqa: PLC0415

    sys.path.insert(0, str(ROOT / "tools"))
    from db_ingest import SanityIngestError, build_ingest_plan, fetch_with_retry  # noqa: PLC0415
    from knesset_odata import classify_validity, fetch_israel_laws  # noqa: PLC0415
    from load_corpus_to_supabase_rest import load_one_law  # noqa: PLC0415

    print(f"\nטוען {len(stale)} חוקים שהתעדכנו...")
    kns = fetch_israel_laws()
    out_dir = Path(tempfile.mkdtemp(prefix="corpus-update-"))
    failures = []
    for law in stale:
        title, law_id = law["title"], law["id"]
        try:
            export = fetch_with_retry(title)
            plan = build_ingest_plan(
                law_id, title, source_ref="", law_is_new=True,
                fetch=lambda _t, _e=export: _e,
                validity=classify_validity(title, kns))
        except SanityIngestError as e:
            failures.append({**law, "error": f"בדיקת שפיות: {e}"})
            print(f"   ✗ {title[:46]:48s} בדיקת שפיות נכשלה")
            continue
        except Exception as e:  # noqa: BLE001
            failures.append({**law, "error": f"{type(e).__name__}: {e}"})
            print(f"   ✗ {title[:46]:48s} {type(e).__name__}")
            continue

        sql_path = out_dir / f"{law_id}.sql"
        sql_path.write_text(plan.sql, encoding="utf-8")
        try:
            _, status, detail = load_one_law(sql_path)
        except Exception as e:  # noqa: BLE001
            failures.append({**law, "error": f"{type(e).__name__}: {e}"})
            print(f"   ✗ {title[:46]:48s} טעינה: {type(e).__name__}")
            continue
        if status != "ok":
            failures.append({**law, "error": detail})
            print(f"   ✗ {title[:46]:48s} {detail[:70]}")
        else:
            print(f"   ✓ {title[:46]:48s} {detail}")
    return failures


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

    # ── טעינה אוטומטית ────────────────────────────────────────────
    drafted, guard_state = laws_with_open_drafts(url, key)
    print(f"\nהגנת טיוטות: {guard_state}")
    to_load = [s for s in stale if s["id"] not in drafted]
    skipped = [s for s in stale if s["id"] in drafted]
    for s in skipped:
        print(f"   דולג (טיוטה פתוחה): {s['title'][:56]}")

    failures = []
    if to_load and os.environ.get("CHECK_ONLY") != "1":
        failures = load_updated(to_load)

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
    # **מסומן רק מי שעדיין מפגר**: מי שנטען נמחק מהסימון, ומי
    # שדולג בגלל טיוטה או נכשל בטעינה - נשאר מסומן, וזה בדיוק
    # מה שהחיווי בממשק אמור להראות.
    failed_ids = {f["id"] for f in failures}
    still_stale = [s for s in stale
                   if s["id"] in {x["id"] for x in skipped} or s["id"] in failed_ids]
    for s_ in still_stale:
        _patch(url, key, "laws", {"id": f"eq.{s_['id']}"},
               {"latest_known_revision_id": s_["theirs"]})
    print(f"\nנרשם: {checked} נבדקו, {len(stale)} מפגרו, "
          f"{len(stale) - len(still_stale)} עודכנו, {len(still_stale)} נשארו מסומנים.")

    out = os.environ.get("OUT")
    if out:
        Path(out).write_text(json.dumps(stale, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"נכתב: {out}")
    # **כשל טעינה מפיל את הריצה.** חוק שנשאר מיושן בגלל כשל הוא
    # בדיוק המצב שהמנגנון הזה נבנה כדי למנוע, ולכן הוא חייב
    # להיות אדום ולא שורה בלוג. דילוג בגלל טיוטה **אינו** כשל.
    if failures:
        print(f"\n**{len(failures)} חוקים נכשלו בטעינה:**")
        for f in failures:
            print(f"   {f['title'][:50]:52s} {f['error'][:90]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
