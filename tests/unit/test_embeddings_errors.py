"""סיווג שגיאות 400 מ-OpenAI ב-packages/llm/embeddings.py - בלי רשת.

למה זו בדיקה נפרדת: ב-2026-09-17 חוק התכנון והבניה (החוק הראשון
ברשימת העדיפות) נפל בהרצה אמיתית כי OpenAI החזירה "maximum input
length is 8192 tokens" - ניסוח שהסיווג לא זיהה, ולכן כל החוק נכשל
במקום שה-chunk הבודד ידולג. ההבדל בין שתי החריגות הוא ההבדל בין
"דלג על סעיף אחד" ל"אבד חוק שלם", ולכן הוא ננעל בבדיקה.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))

import embeddings  # noqa: E402
from embeddings import EmbeddingRequestError, EmbeddingTooLongError, embed_batch  # noqa: E402


class _FakeResponse:
    def __init__(self, message):
        self.status_code = 400
        self._message = message
        self.text = message

    def json(self):
        return {"error": {"message": self._message}}


class _FakeClient:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, *args, **kwargs):
        return _FakeResponse(self._message)


def _classify(message):
    """מחזיר את סוג החריגה שנזרקת עבור הודעת 400 נתונה."""
    original_client, original_key = embeddings.httpx.Client, embeddings.os.environ.get("OPENAI_API_KEY")
    embeddings.httpx.Client = lambda *a, **k: _FakeClient(message)
    embeddings.os.environ["OPENAI_API_KEY"] = "sk-בדיקה"
    try:
        embed_batch(["טקסט כלשהו"])
        return None
    except EmbeddingTooLongError:
        return EmbeddingTooLongError
    except EmbeddingRequestError:
        return EmbeddingRequestError
    finally:
        embeddings.httpx.Client = original_client
        if original_key is None:
            del embeddings.os.environ["OPENAI_API_KEY"]
        else:
            embeddings.os.environ["OPENAI_API_KEY"] = original_key


def main():
    ok = True
    cases = [
        ("Invalid 'input[29]': maximum input length is 8192 tokens.", EmbeddingTooLongError,
         "'maximum input length' (הניסוח שהפיל את חוק התכנון והבניה בפועל)"),
        ("This model's maximum context length is 8192 tokens", EmbeddingTooLongError,
         "'maximum context length'"),
        ("Input is too long for this model", EmbeddingTooLongError, "'too long'"),
        ("Incorrect API key provided", EmbeddingRequestError,
         "400 שאינו בעיית אורך -> שגיאה רגילה, לא דילוג שקט על chunk"),
    ]
    for message, expected, label in cases:
        got = _classify(message)
        passed = got is expected
        ok = ok and passed
        print(("OK " if passed else "FAIL"), f"{label} -> {expected.__name__}",
              "" if passed else f"(קיבלנו {got.__name__ if got else None})")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
