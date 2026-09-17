"""Embeddings דרך OpenAI (`text-embedding-3-large`, כמבוקש) - חלק
מ-`packages/llm` (חוק ברזל 4/CLAUDE.md: "היחיד שקורא למודל" - זה חל
על כל מודל, כולל embeddings, לא רק Anthropic). `OPENAI_API_KEY`
נקרא רק בזמן קריאה בפועל - אותו עיקרון בדיוק כמו `client._api_key`
(שגיאה ברורה ומיידית אם חסר, לא כישלון שקט באמצע בקשה).

**מגבלת אורך - נבדקה בפועל, לא הונחה (2026-09-16):** `text-
embedding-3-large` דוחה קלט מעל 8,192 טוקן (`400 invalid_request_
error`). נבדק ישירות מול ה-API עם טקסט אמיתי מהקורפוס (`raw_block`
בגודל 80,348 תווים, התוספת הארוכה ביותר בקורפוס) - **נדחה בפועל**.
`chunking.py` (`packages/corpus`) אחראי לא לשלוח לכאן טקסט שחורג -
המודול הזה רק מזהה ומדווח את החריגה כ-`EmbeddingTooLongError`
ספציפית (לא כשל רשת סתמי), כדי שקוד ה-ingest ידע להבדיל "לדלג ולרשום"
(כמבוקש) מכשל רשת חולף שכן כדאי לנסות שוב.
"""

import os
import time
from dataclasses import dataclass

import httpx

_API_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_MODEL = "text-embedding-3-large"

# ממד מוקטן (Matryoshka - פרמטר `dimensions` הרשמי של OpenAI), לא
# ברירת המחדל של המודל (3072) - נמצא תוך כדי בניית סכמת ה-DB
# (2026-09-17): אינדקס HNSW/IVFFlat של pgvector תומך עד 2,000 מימדים
# בלבד (מגבלה מתועדת של pgvector עצמו, לא של Supabase) - 3072 היה
# נכשל ב-CREATE INDEX (`column cannot have more than 2000 dimensions
# for hnsw index`, נתפס בפועל מול ה-DB האמיתי). 1024 נשאר הרבה מתחת
# למגבלה, ולפי בנצ'מרק OpenAI עצמו על text-embedding-3-large האובדן
# באיכות בהקטנה הזו קטן. לא נבדק בפועל מול ה-API (api.openai.com
# חסום בסביבה הזו, ראו night-report) - החלטה תיעודית-מונחית, לא
# מדידה אמפירית.
EMBEDDING_DIM = 1024


class EmbeddingConfigError(Exception):
    """OPENAI_API_KEY חסר."""


class EmbeddingRequestError(Exception):
    """כשל רשת/HTTP כללי (לא חריגת-אורך) אחרי מיצוי הניסיונות."""


class EmbeddingTooLongError(EmbeddingRequestError):
    """הטקסט חורג ממגבלת האורך של המודל (400 מפורש על כך, לא כשל רשת
    סתמי) - מזוהה לפי הודעת השגיאה, לא ניחוש לפי אורך תווים מראש
    (אורך-בתווים הוא רק אומדן גס למספר טוקנים בעברית)."""


def _api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise EmbeddingConfigError(
            "חסר משתנה סביבה OPENAI_API_KEY - נדרש לכל קריאה ל-embeddings (packages/llm/embeddings.py)."
        )
    return key


@dataclass
class EmbedResult:
    vectors: list[list[float]]
    total_tokens: int  # usage.total_tokens האמיתי מ-OpenAI - לחישוב עלות מדויק, לא הערכה


def embed_batch_with_usage(
    texts: list[str], *, model: str = EMBEDDING_MODEL, dimensions: int = EMBEDDING_DIM
) -> EmbedResult:
    """כמו embed_batch, אבל גם מחזירה usage.total_tokens האמיתי -
    נדרש ל-ingest_log (tools/admin_ingest.py) לחשב עלות בפועל, לא
    להעריך לפי אורך תווים (עברית לא 1:1 עם אנגלית ב-tokenization).

    batch יחיד - ה-API של OpenAI תומך בכמה מחרוזות קלט באותה בקשה
    (מוזיל עלות תקורה), אבל **אם input בודד בתוך ה-batch חורג
    מהמגבלה, כל הבקשה נכשלת** - לכן קוד ה-ingest קורא כאן רק אחרי
    שכבר סינן/פיצל לפי chunking.py, לא שולח batch גדול בלי בקרה.

    dimensions: פרמטר רשמי של OpenAI (`text-embedding-3-large` תומך
    בהקטנת ממד) - ברירת המחדל כאן (1024) *חייבת* להתאים בדיוק ל-
    `vector(1024)` בסכמת `search_chunks` (supabase/migrations/
    20260917000000_search_chunks_hybrid_search.sql) - לא עצמאיים."""
    key = _api_key()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"model": model, "input": texts, "dimensions": dimensions}

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(_API_URL, json=body, headers=headers)
            if resp.status_code == 400:
                detail = resp.json().get("error", {}).get("message", resp.text[:300])
                if "maximum context length" in detail or "too long" in detail.lower():
                    raise EmbeddingTooLongError(detail)
                raise EmbeddingRequestError(f"HTTP 400 מ-OpenAI (לא-חולף): {detail}")
            if resp.status_code >= 500:
                raise EmbeddingRequestError(f"HTTP {resp.status_code} מ-OpenAI: {resp.text[:300]}")
            resp.raise_for_status()
            data = resp.json()
            break
        except EmbeddingTooLongError:
            raise
        except (httpx.TransportError, EmbeddingRequestError) as e:
            last_exc = e
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise EmbeddingRequestError(f"קריאה ל-OpenAI embeddings נכשלה: {e}") from None
    else:
        raise EmbeddingRequestError(f"לא אמור להגיע לכאן: {last_exc}")

    ordered = sorted(data["data"], key=lambda row: row["index"])
    return EmbedResult(
        vectors=[row["embedding"] for row in ordered],
        total_tokens=data.get("usage", {}).get("total_tokens", 0),
    )


def embed_batch(
    texts: list[str], *, model: str = EMBEDDING_MODEL, dimensions: int = EMBEDDING_DIM
) -> list[list[float]]:
    """כמו embed_batch_with_usage, בלי usage - לקוראים שלא צריכים
    עלות (semantic_search.py: embedding בודד לשאילתה, לא ingest)."""
    return embed_batch_with_usage(texts, model=model, dimensions=dimensions).vectors


def embed_one(text: str, *, model: str = EMBEDDING_MODEL, dimensions: int = EMBEDDING_DIM) -> list[float]:
    return embed_batch([text], model=model, dimensions=dimensions)[0]
