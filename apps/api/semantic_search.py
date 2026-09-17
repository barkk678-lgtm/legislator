"""חיפוש סמנטי היברידי (משימה א, 1.3, 2026-09-16/17) - "איתור חוקים/
סעיפים משפה חופשית" (חוק ברזל 4, תפקיד 3 - CLAUDE.md). שכבה דקה:
embedding לשאילתה (packages/llm/embeddings.embed_one) + קריאת RPC
אחת ל-hybrid_search_chunks (supabase/migrations/20260917000000_
search_chunks_hybrid_search.sql) - כל החישוב (BM25-קירוב + דמיון
וקטורי + שקלול) בצד ה-DB, לא כאן.

**לא נבדק בפועל מקצה לקצה** - חסום כפול (SUPABASE_SERVICE_ROLE_KEY
+ api.openai.com, ראו docs/night-report.md). קוד מוכן, בדפוס זהה
ל-law_registry.py (אותה שכבת REST, אותה קריאת משתני סביבה בזמן
קריאה בפועל - לא בייבוא המודול).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
from embeddings import EmbeddingConfigError, EmbeddingRequestError, embed_one  # noqa: E402


class SemanticSearchConfigError(Exception):
    """תצורה חסרה (SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY *או*
    OPENAI_API_KEY - שתיהן נדרשות) - סוג אחד לקורא ב-main.py, לא
    צריך להכיר את שני מקורות השגיאה הפנימיים בנפרד."""


class SemanticSearchRequestError(Exception):
    """כשל רשת/API (לא תצורה חסרה) - ב-embeddings או ב-Supabase RPC."""


def _supabase_client() -> httpx.Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    missing = [n for n, v in [("SUPABASE_URL", url), ("SUPABASE_SERVICE_ROLE_KEY", key)] if not v]
    if missing:
        raise SemanticSearchConfigError(
            "חסרים משתני סביבה נדרשים לחיפוש סמנטי: " + ", ".join(missing)
        )
    return httpx.Client(
        base_url=f"{url.rstrip('/')}/rest/v1",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def search(query: str, *, limit: int = 10, full_text_weight: float = 0.5, semantic_weight: float = 0.5) -> list[dict]:
    """query ריק -> [] מיידית, בלי embedding/קריאת DB בכלל - אין מה
    לחפש. אחרת: embedding לשאילתה (עולה כסף/רשת - פעם אחת, לא לכל
    chunk) ואז RPC יחיד שמחזיר תוצאות מדורגות מוכנות.

    **בודקת תצורת Supabase לפני קריאת embedding בכוונה** (לא אחרי) -
    כדי לא לשלם על קריאת embedding אמיתית כש-DB ממילא לא מוגדר;
    שתי הבדיקות (Supabase + OpenAI) מתכנסות לאותו סוג שגיאה אחד
    (SemanticSearchConfigError) כלפי הקורא."""
    query = query.strip()
    if not query:
        return []

    with _supabase_client() as client:
        try:
            query_embedding = embed_one(query)
        except EmbeddingConfigError as e:
            raise SemanticSearchConfigError(str(e)) from None
        except EmbeddingRequestError as e:
            raise SemanticSearchRequestError(f"כשל בקבלת embedding לשאילתה: {e}") from None

        try:
            resp = client.post(
                "/rpc/hybrid_search_chunks",
                json={
                    "query_text": query,
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "full_text_weight": full_text_weight,
                    "semantic_weight": semantic_weight,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SemanticSearchRequestError(f"כשל בקריאת חיפוש מ-Supabase: {e}") from None
        return resp.json()
