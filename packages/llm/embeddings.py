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

import httpx

_API_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072  # ממד ברירת המחדל של text-embedding-3-large - אומת בפועל


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


def embed_batch(texts: list[str], *, model: str = EMBEDDING_MODEL) -> list[list[float]]:
    """מחזירה embedding אחד לכל טקסט ב-texts, באותו סדר. batch יחיד -
    ה-API של OpenAI תומך בכמה מחרוזות קלט באותה בקשה (מוזיל עלות
    תקורה), אבל **אם input בודד בתוך ה-batch חורג מהמגבלה, כל הבקשה
    נכשלת** - לכן קוד ה-ingest קורא כאן רק אחרי שכבר סינן/פיצל לפי
    chunking.py, לא שולח batch גדול בלי בקרה."""
    key = _api_key()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"model": model, "input": texts}

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
    return [row["embedding"] for row in ordered]


def embed_one(text: str, *, model: str = EMBEDDING_MODEL) -> list[float]:
    return embed_batch([text], model=model)[0]
