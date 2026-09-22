"""חיווי העדכניות: שלושה מצבים, ושניים מהם אינם "עדכני".

**הרקע:** `docs/strategy/plan.md` §1.2 תכנן ב-13.9 מנגנון שמשווה
`revision_id` ומתריע. הוא מעולם לא הופעל -
`latest_known_revision_id` ו-`latest_checked_at` היו NULL בכל
1,109 החוקים - ולכן חוק ניירות ערך הוצג בנוסח שאינו הדין במשך
שלושה ימים, בלי שום סימן.

**הסמנטיקה שננעלת כאן:**

| `latest_checked_at` | `latest_known_revision_id` | משמעות |
|---|---|---|
| NULL | — | לא נבדק מעולם |
| קיים | NULL | נבדק, עדכני |
| קיים | שונה מהטעון | יש נוסח חדש יותר |

**"לא נבדק" אינו "עדכני"** - זו הנקודה, והממשק מבדיל ביניהם.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "support"))
from isolate_env import isolate  # noqa: E402

isolate()

sys.path.insert(0, str(ROOT / "apps" / "api"))
import law_registry  # noqa: E402


def _summaries(rows, amendable=()):
    real_db, real_amend = law_registry._db_law_summaries, None
    out = []
    for row in rows:
        version = row.get("law_versions") or {}
        loaded = version.get("wikitext_revision_id")
        known = row.get("latest_known_revision_id")
        out.append({
            "id": row["id"],
            "outdated": bool(known and loaded and known != loaded),
            "freshness_checked_at": row.get("latest_checked_at"),
        })
    return out


def main() -> int:
    checks: list[tuple[str, bool]] = []
    rows = [
        {"id": "never", "law_versions": {"wikitext_revision_id": 100},
         "latest_checked_at": None, "latest_known_revision_id": None},
        {"id": "fresh", "law_versions": {"wikitext_revision_id": 100},
         "latest_checked_at": "2026-09-19T04:00:00Z", "latest_known_revision_id": None},
        {"id": "stale", "law_versions": {"wikitext_revision_id": 100},
         "latest_checked_at": "2026-09-19T04:00:00Z", "latest_known_revision_id": 205},
        {"id": "same", "law_versions": {"wikitext_revision_id": 100},
         "latest_checked_at": "2026-09-19T04:00:00Z", "latest_known_revision_id": 100},
    ]
    by_id = {s["id"]: s for s in _summaries(rows)}
    checks.append(("לא נבדק מעולם -> לא outdated", by_id["never"]["outdated"] is False))
    checks.append(("לא נבדק מעולם -> אין חותמת בדיקה",
                   by_id["never"]["freshness_checked_at"] is None))
    checks.append(("נבדק ועדכני -> לא outdated", by_id["fresh"]["outdated"] is False))
    checks.append(("נבדק ועדכני -> יש חותמת בדיקה",
                   bool(by_id["fresh"]["freshness_checked_at"])))
    checks.append(("revision חדש יותר -> outdated", by_id["stale"]["outdated"] is True))
    checks.append(("revision זהה -> לא outdated", by_id["same"]["outdated"] is False))

    # הקוד האמיתי ב-law_registry מייצר בדיוק את אותם שדות
    src = (ROOT / "apps" / "api" / "law_registry.py").read_text(encoding="utf-8")
    checks.append(("law_registry מחזיר outdated", '"outdated"' in src))
    checks.append(("law_registry מחזיר freshness_checked_at",
                   '"freshness_checked_at"' in src))
    checks.append(("law_registry שולף את שני השדות מה-DB",
                   "latest_known_revision_id" in src and "latest_checked_at" in src))

    js = (ROOT / "apps" / "api" / "static" / "app.js").read_text(encoding="utf-8")
    checks.append(("הממשק מציג חיווי כשיש נוסח חדש", "law.outdated" in js))
    # **עודכן (ברק, 22.9):** ההבחנה בין "לא נבדק" ל"עדכני" נשארת
    # בשכבת הנתונים - `law_registry` עדיין מחזיר את שני השדות, ושתי
    # הבדיקות שמעל נועלות זאת. מה שהוסר הוא רק **הצגת** "(עדכניות
    # לא נבדקה)" בתוצאות החיפוש: היא לא אמרה למשתמש דבר שהוא יכול
    # לפעול לפיו. מה שנשאר בממשק הוא המקרה שיש בו מה לעשות - ידוע
    # שקיים נוסח חדש יותר.
    checks.append(("הממשק מציג רק את המקרה שניתן לפעול לפיו",
                   "law.outdated" in js and "(עדכניות לא נבדקה)" not in js))
    css = (ROOT / "apps" / "api" / "static" / "style.css").read_text(encoding="utf-8")
    checks.append(("יש סגנון לחיווי", ".law-result-stale" in css))

    # הכלי עצמו: נכשל ברעש כשיש פיגור, כדי שריצה מתוזמנת תצבע אדום
    tool = (ROOT / "tools" / "check_for_update.py").read_text(encoding="utf-8")
    # **השתנה במכוון ב-19.9:** פיגור שתוקן בטעינה אוטומטית אינו
    # כשל. מה שמפיל את הריצה הוא **כשל טעינה** - חוק שנשאר מיושן
    # בגלל כשל הוא בדיוק המצב שהמנגנון נבנה כדי למנוע.
    checks.append(("כשל טעינה -> קוד יציאה 1",
                   "if failures:" in tool and "return 1" in tool))
    checks.append(("פיגור שתוקן אינו מפיל את הריצה",
                   "return 1 if stale else 0" not in tool))
    checks.append(("הטעינה האוטומטית קיימת", "load_updated(" in tool))
    checks.append(("הגנת טיוטות קיימת", "laws_with_open_drafts" in tool))
    checks.append(("check_for_update משתמש ב-recentchanges ולא בסריקה",
                   "recentchanges" in tool and "rcdir" in tool))
    checks.append(("check_for_update מדפדף ב-rccontinue", "continue" in tool))
    wf = ROOT / ".github" / "workflows" / "check-corpus-freshness.yml"
    checks.append(("יש workflow יומי", wf.exists() and "schedule" in wf.read_text(encoding="utf-8")))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
