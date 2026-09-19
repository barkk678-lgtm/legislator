"""בדיקות ל-apps/api/admin_ingest.py (ברק, 2026-09-17) - בלי רשת/DB.
בודקות את שכבת האבטחה (_require_secret) ואת שלמות רשימת העדיפות
(data/indexing_priority.json) - שאר הלוגיקה (rate limit/עיבוד chunks
בפועל) דורשת DB+OpenAI אמיתיים, נבדקה בנפרד חי (ראו night-report.md).

רשימת העדיפות נבדקת כאן כי היא **חוזה**: ברק אישר את 67 חוקי שלב 1
ואת 11 הקטגוריות המחויבות + 14 חוקי היסוד בתוכם. עריכה שתפיל אחד
מהם (או תחרוג מתקציב האחסון) צריכה להיכשל בבדיקה, לא בהרצה שעולה כסף.
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import clear_secret, isolate, set_secret  # noqa: E402

# **הרמטיות.** עד 2026-09-19 הטסט הזה הסתמך על כך שבמקרה אין מפתחות
# בסביבה. מרגע שהם נטענים מקובץ, ההסתמכות הזו נשברה - ראו
# tests/support/isolate_env.py.
isolate()


import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import admin_ingest  # noqa: E402
from admin_ingest import IngestAuthError, _require_secret  # noqa: E402


def main():
    ok = True

    # --- INGEST_SECRET לא מוגדר בסביבה (המצב האמיתי כאן) -> נכשלת תמיד, גם עם טוקן ---
    assert os.environ.get("INGEST_SECRET") is None, "הבדיקה מניחה שאין INGEST_SECRET בסביבה"
    threw = False
    try:
        _require_secret("כל טוקן")
    except IngestAuthError:
        threw = True
    ok = ok and threw
    print(("OK " if threw else "FAIL"), "בלי INGEST_SECRET בסביבה -> תמיד IngestAuthError, לא endpoint פתוח בטעות")

    # --- INGEST_SECRET מוגדר, טוקן נכון -> עובר ---
    set_secret("INGEST_SECRET", "סוד-לבדיקה")
    try:
        threw = False
        try:
            _require_secret("סוד-לבדיקה")
        except IngestAuthError:
            threw = True
        passed = not threw
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "טוקן נכון -> עובר בלי שגיאה")

        # --- טוקן שגוי -> נכשל ---
        threw = False
        try:
            _require_secret("טוקן-שגוי")
        except IngestAuthError:
            threw = True
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "טוקן שגוי -> IngestAuthError")

        # --- בלי טוקן בכלל (None) -> נכשל ---
        threw = False
        try:
            _require_secret(None)
        except IngestAuthError:
            threw = True
        ok = ok and threw
        print(("OK " if threw else "FAIL"), "בלי טוקן בכלל -> IngestAuthError")
    finally:
        clear_secret("INGEST_SECRET")

    # --- ה-endpoint עצמו: בלי header, בלי INGEST_SECRET -> 401 ברור, לא קורס ---
    from fastapi.testclient import TestClient  # noqa: E402
    from main import app  # noqa: E402

    client = TestClient(app)
    resp = client.post("/api/admin/ingest-chunks")
    passed = resp.status_code == 401
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "POST /api/admin/ingest-chunks בלי טוקן -> 401 ->", resp.status_code if not passed else "")

    # --- רשימת העדיפות: החוזה שברק אישר ---
    import json  # noqa: PLC0415

    doc = json.loads((Path(__file__).resolve().parents[2] / "data" / "indexing_priority.json").read_text(encoding="utf-8"))
    laws = doc["laws"]
    phase1 = [l for l in laws if l["phase"] == 1]

    checks = [
        (len(laws) == 250, "250 חוקים ברשימה"),
        (len(phase1) == 67, "67 חוקים בשלב 1 (מה שנכנס ב-Free tier)"),
        ([l["rank"] for l in laws] == list(range(1, 251)), "הדירוג רציף 1..250 ובסדר"),
        (len({l["law_id"] for l in laws}) == 250, "אין מזהה כפול"),
        (all(l["phase"] == 1 for l in laws[:67]), "שלב 1 הוא בדיוק הראש של הרשימה (חיתוך מהתחתית)"),
        (sum(l["projected_mb"] for l in phase1) <= 235, "שלב 1 בתוך 235MB (285 פנויים פחות מרווח 50)"),
    ]
    # 11 הקטגוריות שברק דרש במפורש + כל חוקי היסוד
    required = {
        "law-2000479": "העונשין", "law-2000613": "תכנון ובניה", "law-2000198": "ביטוח לאומי",
        "law-2000289": "חוק החברות", "law-2001104": "ניירות ערך", "law-2000907": "פקודת העיריות",
        "law-2001189": "רישוי עסקים", "law-2000292": "חוק החוזים (כללי)",
        "law-2000293": "חוק החוזים (תרופות)", "law-2000416": "המקרקעין", "law-2000322": "הירושה",
    }
    phase1_ids = {l["law_id"] for l in phase1}
    for law_id, name in required.items():
        checks.append((law_id in phase1_ids, f"{name} ({law_id}) נמצא בשלב 1"))
    basic_laws = [l for l in phase1 if l["title"].startswith("חוק-יסוד")]
    checks.append((len(basic_laws) == 14, f"כל 14 חוקי היסוד בשלב 1 (נמצאו {len(basic_laws)})"))
    checks.append((all(l["forced"] for l in laws if l["law_id"] in required), "הקטגוריות המחויבות מסומנות forced"))

    for passed, label in checks:
        ok = ok and passed
        print(("OK " if passed else "FAIL"), label)

    # --- דילוג ממוקד על chunk חורג-אורך (במקום 50 קריאות בודדות) ---
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
    from embeddings import EmbeddingTooLongError  # noqa: PLC0415

    class _Chunk:
        def __init__(self, text):
            self.text = text

    network_calls = []

    def _fake_embed(texts):
        network_calls.append(list(texts))
        if "ענק" in texts:
            exc = EmbeddingTooLongError("Invalid 'input[%d]'" % texts.index("ענק"))
            exc.input_index = texts.index("ענק")
            raise exc
        result = type("R", (), {})()
        result.vectors = [[0.0] for _ in texts]
        result.total_tokens = 10 * len(texts)
        return result

    saved_embed, saved_write = admin_ingest.embed_batch_with_usage, admin_ingest._write_chunks
    try:
        admin_ingest.embed_batch_with_usage = _fake_embed
        admin_ingest._write_chunks = lambda client, chunks, vectors: None
        embedded, tokens, skipped = admin_ingest._embed_batch_skipping_too_long(
            None, [_Chunk("א"), _Chunk("ענק"), _Chunk("ב"), _Chunk("ג")]
        )
    finally:
        admin_ingest.embed_batch_with_usage, admin_ingest._write_chunks = saved_embed, saved_write

    for passed, label in [
        ((embedded, skipped) == (3, 1), "chunk חורג מדולג, שלושת התקינים מוטמעים"),
        (len(network_calls) == 2, f"2 קריאות רשת בלבד, לא אחת לכל chunk (היו {len(network_calls)})"),
    ]:
        ok = ok and passed
        print(("OK " if passed else "FAIL"), label)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
