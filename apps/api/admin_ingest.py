"""endpoint מוגן-טוקן ל-ingest embeddings (משימה א, 1.3 - ברק,
2026-09-17: "תתחיל, אבל שלוש דרישות אבטחה קודם"). **נועד לרוץ
מ-Vercel בלבד** - זו הסביבה שכן מגיעה ל-api.openai.com (ראו
CLAUDE.md "גבולות רשת" ו-night-report.md 2026-09-17).

שלוש דרישות האבטחה (ברק):
1. טוקן סוד (`INGEST_SECRET`, משתנה סביבה) - בלעדיו 401. לא ב-URL
   (נשמר בלוגים) - header ייעודי (`X-Ingest-Secret`).
2. מגבלת קצב קשיחה: `MAX_CALLS_PER_HOUR`/`MAX_CHUNKS_PER_CALL` -
   חוסמת נזק גם אם הטוקן דלף (ראו night-report.md לחישוב $ מדויק).
   הטבלה ingest_log משמשת גם למגבלה עצמה (ספירת קריאות בשעה
   האחרונה) וגם ללוג המבוקש - לא שני מנגנונים נפרדים.
3. לוג מלא לכל הפעלה - ingest_log (זמן, chunks, טוקנים, עלות
   מחושבת מ-usage.total_tokens האמיתי, לא הערכה).

**מסלול הרצה יזומה (ברק, 2026-09-17):** `bypass_rate_limit=True`
עוקף את מגבלת הקצב (ורק אותה) - מוגן באותו טוקן בדיוק, מסומן
ב-`ingest_log.rate_limit_bypassed`. המגבלה נשארת כברירת המחדל לכל
קריאה אחרת. תקציב ה-chunks לקריאה *לא* נעקף - הוא מה ששומר על
הקריאה בתוך תקרת הזמן של פונקציית Vercel.

**סדר העיבוד לפי `data/indexing_priority.json`** (לא לפי law_id
עולה) - רשימת 250 החוקים המדורגת, שלב 1 = 67 החוקים שנכנסים
ב-Free tier. חוק שאינו ברשימת השלב המבוקש לא נוגעים בו בכלל.

**שומר המרווח:** לפני כל מנה נמדד גודל ה-DB האמיתי
(`db_size_bytes()`); אם נותרו פחות מ-`MIN_FREE_MARGIN_MB` מתקרת
ה-Free tier - עצירה קשיחה (507), לא המשך "עד שנתפוס".

**הרצה-חוזרת (ברק, במפורש):** chunk שכבר קיים ב-search_chunks
(עם embedding) לא מחושב מחדש - נבדק לפי (law_id, section_number,
chunk_index) לפני שליחה ל-OpenAI. התקדמות ברמת-חוק ב-ingest_progress
(status='done' רק אחרי שכל ה-chunks של חוק נכתבו) - קריאה חוזרת
ממשיכה מהחוק הבא שלא הושלם, לא סורקת הכול מחדש.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
from chunking import chunk_law  # noqa: E402
from embeddings import EmbeddingConfigError, EmbeddingRequestError, EmbeddingTooLongError, embed_batch_with_usage  # noqa: E402

from law_registry import LawNotFoundError, load_law  # noqa: E402

# --- מגבלות קצב (ברק, 2026-09-17) - ראו night-report.md לחישוב
# העלות המרבית התיאורטי לשעה/ליום מהמספרים האלה. ---
MAX_CALLS_PER_HOUR = 5
MAX_CHUNKS_PER_CALL = 300
_EMBED_API_BATCH_SIZE = 50  # כמה chunks בכל קריאת embeddings בודדת ל-OpenAI

# $0.13 ל-1M טוקן, text-embedding-3-large, מחיר API רגיל (לא batch) -
# נבדק מול תיעוד OpenAI (2026-09-17), לא הונח.
_COST_PER_1M_TOKENS_USD = 0.13

# תקרת ה-Free tier של Supabase והמרווח שברק דרש לשמור מתחתיה.
FREE_TIER_LIMIT_MB = 500
MIN_FREE_MARGIN_MB = 50

_PRIORITY_PATH = Path(__file__).resolve().parents[2] / "data" / "indexing_priority.json"


class IngestAuthError(Exception):
    """טוקן חסר/שגוי - 401."""


class IngestRateLimitError(Exception):
    """יותר מ-MAX_CALLS_PER_HOUR קריאות בשעה האחרונה - 429."""


class IngestStorageLimitError(Exception):
    """נותר פחות מ-MIN_FREE_MARGIN_MB עד תקרת ה-Free tier - 507."""


def _require_secret(provided: str | None) -> None:
    expected = os.environ.get("INGEST_SECRET")
    if not expected:
        raise IngestAuthError("INGEST_SECRET לא מוגדר בסביבה - ה-endpoint חסום כברירת מחדל, לא פתוח.")
    if not provided or provided != expected:
        raise IngestAuthError("טוקן שגוי/חסר.")


def _supabase_client() -> httpx.Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("חסרים SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY.")
    return httpx.Client(
        base_url=f"{url.rstrip('/')}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _calls_in_last_hour(client: httpx.Client) -> int:
    """PostgREST לא תומך בביטוי interval דרך query param רגיל -
    מחשבים את חתך הזמן ב-Python ומשווים ישירות (פשוט וברור יותר
    מ-RPC ייעודי לצורך הזה בלבד)."""
    one_hour_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    resp = client.get(
        "/ingest_log",
        params={"select": "id", "called_at": f"gte.{one_hour_ago}"},
        headers={"Prefer": "count=exact"},
    )
    resp.raise_for_status()
    content_range = resp.headers.get("content-range", "")  # "0-4/5"
    if "/" in content_range:
        return int(content_range.split("/")[-1])
    return len(resp.json())


def _ensure_progress_seeded(client: httpx.Client) -> None:
    """כל law_id שאין לו עדיין שורה ב-ingest_progress מקבל 'pending' -
    אידמפוטנטי (on_conflict do nothing), רץ בכל קריאה כדי לתפוס גם
    חוקים חדשים שנוספו לקורפוס אחרי הפעם הראשונה."""
    resp = client.get("/laws", params={"select": "id", "current_version_id": "not.is.null"})
    resp.raise_for_status()
    law_ids = [row["id"] for row in resp.json()]
    rows = [{"law_id": lid, "status": "pending"} for lid in law_ids]
    if rows:
        client.post(
            "/ingest_progress",
            params={"on_conflict": "law_id"},
            json=rows,
            headers={"Prefer": "resolution=ignore-duplicates,return=minimal"},
        )


def _priority_law_ids(phase: int) -> list[str]:
    """מזהי החוקים של השלב המבוקש (וכל השלבים שלפניו), בסדר הדירוג.
    ראו docs/indexing-priority-250.md לקריטריון ולרשימה עצמה."""
    with open(_PRIORITY_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    return [law["law_id"] for law in doc["laws"] if law["phase"] <= phase]


def _next_pending_law_ids(client: httpx.Client, phase: int) -> list[str]:
    """החוקים שטרם הושלמו מתוך רשימת העדיפות, **בסדר הדירוג**.
    שולפים את כל ה-pending בקריאה אחת (payload קטן) וחותכים מולם
    מקומית - במקום in.(...) עם מאות מזהים ב-URL."""
    resp = client.get(
        "/ingest_progress",
        params={"select": "law_id", "status": "eq.pending", "limit": "2000"},
    )
    resp.raise_for_status()
    pending = {row["law_id"] for row in resp.json()}
    return [law_id for law_id in _priority_law_ids(phase) if law_id in pending]


def _db_size_mb(client: httpx.Client) -> float:
    resp = client.post("/rpc/db_size_bytes", json={})
    resp.raise_for_status()
    return resp.json() / 1024 / 1024


def _existing_chunk_keys(client: httpx.Client, law_id: str) -> set[tuple[str, int]]:
    resp = client.get(
        "/search_chunks",
        params={"select": "section_number,chunk_index", "law_id": f"eq.{law_id}", "embedding": "not.is.null"},
    )
    resp.raise_for_status()
    return {(row["section_number"], row["chunk_index"]) for row in resp.json()}


def _write_chunks(client: httpx.Client, chunks, vectors) -> None:
    rows = [
        {
            "law_id": c.law_id,
            "section_number": c.section_number,
            "chunk_index": c.chunk_index,
            "node_ids": c.node_ids,
            "context_prefix": c.context_prefix,
            "body": c.body,
            "contains_raw_block": c.contains_raw_block,
            "embedding": v,
        }
        for c, v in zip(chunks, vectors)
    ]
    resp = client.post(
        "/search_chunks",
        params={"on_conflict": "law_id,section_number,chunk_index"},
        json=rows,
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )
    resp.raise_for_status()


def _mark_progress(client: httpx.Client, law_id: str, *, status: str, chunks_count: int = 0, error_detail: str | None = None) -> None:
    client.post(
        "/ingest_progress",
        params={"on_conflict": "law_id"},
        json=[{"law_id": law_id, "status": status, "chunks_count": chunks_count, "error_detail": error_detail}],
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


def run_ingest_batch(
    *,
    secret: str | None,
    max_laws: int | None = None,
    bypass_rate_limit: bool = False,
    phase: int = 1,
) -> dict:
    """הפעלה אחת, מוגבלת-תקציב. מחזירה סיכום JSON-friendly.

    max_laws: תקרה נוספת (לא חלק משלוש דרישות האבטחה של ברק, שכבר
    אוכפות MAX_CHUNKS_PER_CALL/MAX_CALLS_PER_HOUR) - לריצות-בדיקה
    מבוקרות ("הרץ על 50 חוקים בלבד") בלי לסמוך על גודל מקרי של
    תקציב ה-chunks לחתוך בדיוק במספר החוקים הרצוי.

    bypass_rate_limit: מסלול ההרצה היזומה (ברק) - מדלג על מגבלת
    הקצב בלבד. הטוקן עדיין נדרש, תקציב ה-chunks עדיין נאכף, שומר
    המרווח עדיין נאכף, והקריאה מסומנת ככזו בלוג.

    phase: איזה שלב מתוך data/indexing_priority.json לעבד (1 = 67
    החוקים של ה-Free tier, 2 = כל 250 אחרי שדרוג ל-Pro)."""
    start = time.monotonic()
    _require_secret(secret)

    with _supabase_client() as client:
        if not bypass_rate_limit:
            calls = _calls_in_last_hour(client)
            if calls >= MAX_CALLS_PER_HOUR:
                raise IngestRateLimitError(
                    f"מגבלת קצב: {calls} קריאות בשעה האחרונה (מקסימום {MAX_CALLS_PER_HOUR})."
                )
        else:
            calls = _calls_in_last_hour(client)

        # שומר המרווח של ברק - מול גודל ה-DB האמיתי, לפני שמוציאים
        # אגורה על embeddings של מנה שאין לה מקום להיכתב אליו.
        free_mb = FREE_TIER_LIMIT_MB - _db_size_mb(client)
        if free_mb < MIN_FREE_MARGIN_MB:
            raise IngestStorageLimitError(
                f"נותרו {free_mb:.0f}MB עד תקרת ה-Free tier ({FREE_TIER_LIMIT_MB}MB) - "
                f"מתחת למרווח המינימלי ({MIN_FREE_MARGIN_MB}MB). ההרצה נעצרה."
            )

        _ensure_progress_seeded(client)

        budget = MAX_CHUNKS_PER_CALL
        laws_processed: list[str] = []
        laws_errored: list[str] = []
        chunks_embedded = chunks_skipped_existing = chunks_skipped_too_long = total_tokens = 0

        candidate_law_ids = _next_pending_law_ids(client, phase)
        for law_id in candidate_law_ids:
            if budget <= 0:
                break
            if max_laws is not None and len(laws_processed) >= max_laws:
                break
            try:
                root = load_law(law_id)
                all_chunks = chunk_law(root)
                existing = _existing_chunk_keys(client, law_id)
                new_chunks = [c for c in all_chunks if (c.section_number, c.chunk_index) not in existing]
                chunks_skipped_existing += len(all_chunks) - len(new_chunks)

                to_process = new_chunks[:budget]
                for i in range(0, len(to_process), _EMBED_API_BATCH_SIZE):
                    batch = to_process[i : i + _EMBED_API_BATCH_SIZE]
                    try:
                        result = embed_batch_with_usage([c.text for c in batch])
                        _write_chunks(client, batch, result.vectors)
                        chunks_embedded += len(batch)
                        total_tokens += result.total_tokens
                        budget -= len(batch)
                    except EmbeddingTooLongError:
                        for c in batch:
                            try:
                                r = embed_batch_with_usage([c.text])
                                _write_chunks(client, [c], r.vectors)
                                chunks_embedded += 1
                                total_tokens += r.total_tokens
                                budget -= 1
                            except EmbeddingTooLongError:
                                chunks_skipped_too_long += 1

                if len(to_process) == len(new_chunks):
                    _mark_progress(client, law_id, status="done", chunks_count=len(all_chunks))
                    laws_processed.append(law_id)
                # אחרת: נשאר 'pending' בכוונה - התקציב נגמר באמצע החוק,
                # הצ'אנקים שכן נכתבו לא ייכתבו שוב (existing chunk keys
                # יתפוס אותם בקריאה הבאה).
            except (LawNotFoundError, EmbeddingConfigError, EmbeddingRequestError, httpx.HTTPError) as e:
                _mark_progress(client, law_id, status="error", error_detail=str(e)[:500])
                laws_errored.append(law_id)

        duration_ms = round((time.monotonic() - start) * 1000)
        estimated_cost_usd = round(total_tokens * _COST_PER_1M_TOKENS_USD / 1_000_000, 6)
        client.post(
            "/ingest_log",
            json=[
                {
                    "laws_processed": len(laws_processed),
                    "chunks_embedded": chunks_embedded,
                    "chunks_skipped_existing": chunks_skipped_existing,
                    "chunks_skipped_too_long": chunks_skipped_too_long,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": estimated_cost_usd,
                    "duration_ms": duration_ms,
                    "rate_limit_bypassed": bypass_rate_limit,
                }
            ],
            headers={"Prefer": "return=minimal"},
        )

    return {
        "laws_processed": laws_processed,
        "laws_errored": laws_errored,
        "chunks_embedded": chunks_embedded,
        "chunks_skipped_existing": chunks_skipped_existing,
        "chunks_skipped_too_long": chunks_skipped_too_long,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "duration_ms": duration_ms,
        "calls_remaining_this_hour": MAX_CALLS_PER_HOUR - calls - 1,
        "rate_limit_bypassed": bypass_rate_limit,
        "phase": phase,
        "laws_remaining_in_phase": max(0, len(candidate_law_ids) - len(laws_processed)),
        "free_mb_before": round(free_mb),
    }
