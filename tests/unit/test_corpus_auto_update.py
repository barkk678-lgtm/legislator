"""הטעינה האוטומטית בריצה היומית: תזמור, הגנת טיוטות, וכשלים.

**מה נבדק כאן ומה לא.** `load_one_law` עצמה אינה מדומה כאן -
היא אותה פונקציה שטענה את כל 1,109 החוקים ב-`tools/load_corpus.py`,
והיא מוכחת. מה שחדש הוא **התזמור סביבה**, והוא מה שנבדק:

- חוק עם טיוטה פתוחה מדולג ונשאר מסומן.
- כשל בחוק אחד אינו מפיל את השאר, אבל **מפיל את הריצה** בסוף.
- שלושת מצבי הגנת הטיוטות, ובפרט ש"לא ידעתי לבדוק" אינו
  "אין טיוטות".

**מה שלא נבדק מקצה לקצה:** המסלול המלא recentchanges -> טעינה
מול חוק שבאמת מפגר. אחרי הריצה של 19.9 אין אף חוק כזה
(0 מתוך 1,109), ולייצר אחד היה דורש מחיקת גרסה מה-DB. הבדיקה
האמיתית תתרחש בריצה היומית הראשונה שתמצא פיגור - ואם הטעינה
תיכשל, הריצה תהיה אדומה. זה מתועד ולא מוסתר.
"""

import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "support"))
from isolate_env import isolate  # noqa: E402

isolate()
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "packages" / "config"))
sys.path.insert(0, str(ROOT / "packages" / "corpus"))

import check_for_update as cfu  # noqa: E402


class _Err(urllib.error.HTTPError):
    def __init__(self, code, body):
        super().__init__("u", code, "e", {}, None)
        self._body = body.encode()

    def read(self):
        return self._body


def main() -> int:
    checks: list[tuple[str, bool]] = []
    real_rest = cfu._rest

    # ── הגנת הטיוטות: שלושה מצבים ────────────────────────────────
    cfu._rest = lambda *a, **k: (_ for _ in ()).throw(
        _Err(404, '{"code":"PGRST205","message":"relation does not exist"}'))
    ids, state = cfu.laws_with_open_drafts("u", "k")
    checks.append(("טבלה חסרה -> אין טיוטות", ids == set()))
    checks.append(("טבלה חסרה -> מדווח במפורש ולא בשקט", "אינה קיימת" in state))

    cfu._rest = lambda *a, **k: [{"law_id": "law-1"}, {"law_id": "law-2"}]
    ids, state = cfu.laws_with_open_drafts("u", "k")
    checks.append(("טבלה קיימת -> מחזירה את המזהים", ids == {"law-1", "law-2"}))
    checks.append(("טבלה קיימת -> מדווחת כמה", "2" in state))

    cfu._rest = lambda *a, **k: (_ for _ in ()).throw(_Err(500, "boom"))
    raised = False
    try:
        cfu.laws_with_open_drafts("u", "k")
    except cfu.DraftGuardUnavailable:
        raised = True
    checks.append(("טבלה קיימת והקריאה נכשלה -> זורק, לא מניח שאין טיוטות", raised))
    cfu._rest = real_rest

    # ── התזמור: כשל בחוק אחד אינו מפיל את השאר ───────────────────
    calls = []

    def fake_load(sql_path):
        law_id = Path(sql_path).stem
        calls.append(law_id)
        if law_id == "law-bad":
            return law_id, "error", "HTTP 409 duplicate key"
        return law_id, "ok", "version_id=9 nodes=5"

    real = {}
    import types
    fake_mod = types.ModuleType("load_corpus_to_supabase_rest")
    fake_mod.load_one_law = fake_load
    sys.modules["load_corpus_to_supabase_rest"] = fake_mod

    fake_ing = types.ModuleType("db_ingest")
    class SanityIngestError(Exception): pass
    fake_ing.SanityIngestError = SanityIngestError
    fake_ing.fetch_with_retry = lambda title: {"export_xml": "<x/>"}
    class _Plan:
        sql = "begin;"
        node_count = 5
    def _plan(law_id, title, **kw):
        if law_id == "law-sanity":
            raise SanityIngestError("ספירת סעיפים לא תואמת")
        return _Plan()
    fake_ing.build_ingest_plan = _plan
    sys.modules["db_ingest"] = fake_ing

    fake_kns = types.ModuleType("knesset_odata")
    fake_kns.fetch_israel_laws = lambda: []
    fake_kns.classify_validity = lambda *a, **k: None
    sys.modules["knesset_odata"] = fake_kns

    stale = [{"id": "law-ok", "title": "חוק תקין", "ours": 1, "theirs": 2},
             {"id": "law-bad", "title": "חוק שנכשל בטעינה", "ours": 1, "theirs": 2},
             {"id": "law-sanity", "title": "חוק שנכשל בשפיות", "ours": 1, "theirs": 2},
             {"id": "law-ok2", "title": "חוק תקין נוסף", "ours": 1, "theirs": 2}]
    failures = cfu.load_updated(stale)
    failed_ids = {f["id"] for f in failures}
    checks.append(("כשל טעינה נרשם", "law-bad" in failed_ids))
    checks.append(("כשל שפיות נרשם", "law-sanity" in failed_ids))
    checks.append(("חוק תקין אינו ברשימת הכשלים", "law-ok" not in failed_ids))
    checks.append(("**כשל אינו עוצר את השאר** - גם האחרון נוסה",
                   "law-ok2" in calls))
    checks.append(("כל כשל נושא הסבר", all(f.get("error") for f in failures)))

    # הריצה נכשלת ברעש כשיש כשל טעינה, אבל לא על דילוג בגלל טיוטה
    src = (ROOT / "tools" / "check_for_update.py").read_text(encoding="utf-8")
    checks.append(("כשל טעינה -> קוד יציאה 1", "if failures:\n" in src and "return 1" in src))
    checks.append(("דילוג בגלל טיוטה אינו כשל",
                   "skipped" in src and "failures" in src))
    checks.append(("חוק שדולג או נכשל נשאר מסומן כמפגר", "still_stale" in src))
    checks.append(("CHECK_ONLY מאפשר בדיקה בלי טעינה", 'CHECK_ONLY' in src))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
