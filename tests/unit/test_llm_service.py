"""בדיקות ל-packages/llm/service.py - בלי רשת בכלל (complete_fn מוזרק,
אותו דפוס כמו fetch= ב-test_db_ingest.py). בודקות את שלוש האחריויות
שהמשימה דרשה: בניית הקשר, אכיפת ציטוט, סירוב בלי מקור - לא את
Anthropic API עצמו (זה נבדק ידנית מול המפתח האמיתי, ראו night-report).
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))

from service import LLMResult, SourceChunk, answer_with_sources, draft  # noqa: E402


@dataclass
class _FakeCompletion:
    text: str
    input_tokens: int = 10
    output_tokens: int = 5
    stop_reason: str = "end_turn"


def _fake_complete_factory(reply_text: str):
    calls = []

    def _fake(*, system, user_message, max_tokens=1500):
        calls.append({"system": system, "user_message": user_message, "max_tokens": max_tokens})
        return _FakeCompletion(text=reply_text)

    _fake.calls = calls
    return _fake


def _refuse_if_called(*, system, user_message, max_tokens=1500):
    raise AssertionError("אסור לקרוא ל-complete_fn בכלל כשאין sources")


def main():
    ok = True

    # --- draft(): מעבירה system/user_message נכון, מחזירה טקסט חתוך-רווחים ---
    fake = _fake_complete_factory("  דברי הסבר לדוגמה.  ")
    result = draft(instructions="נסח דברי הסבר", content="הוראות תיקון X", complete_fn=fake)
    passed = result == "דברי הסבר לדוגמה." and fake.calls[0]["system"] == "נסח דברי הסבר"
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "draft() מעבירה system/content נכון ומחתכת רווחים")

    # --- answer_with_sources(): בלי sources -> סירוב מיידי, בלי קריאת רשת בכלל ---
    res: LLMResult = answer_with_sources(question="מה אומר סעיף 5?", sources=[], complete_fn=_refuse_if_called)
    passed = res.refused and res.text == "" and res.cited_source_ids == []
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "answer_with_sources בלי sources -> סירוב בלי קריאת רשת")

    sources = [
        SourceChunk(id="law-1/s5", label="חוק הכנסת, סעיף 5", text="הכנסת בוחרת יושב ראש."),
        SourceChunk(id="law-1/s6", label="חוק הכנסת, סעיף 6", text="ליושב הראש סגנים."),
    ]

    # --- ציטוט תקין ומוכר -> לא-מסורב, cited_source_ids נכון ---
    fake_ok = _fake_complete_factory("הכנסת בוחרת יושב ראש [מקור:law-1/s5].")
    res = answer_with_sources(question="מי בוחר יו\"ר?", sources=sources, complete_fn=fake_ok)
    passed = (not res.refused) and res.cited_source_ids == ["law-1/s5"] and res.text != ""
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "ציטוט מוכר -> תשובה מתקבלת, cited_source_ids נכון")

    # --- ציטוט למזהה לא-מוכר -> סירוב (הפרת עיגון), לא מוצג כתקין ---
    fake_bad_id = _fake_complete_factory("תשובה עם ציטוט מומצא [מקור:law-999/s1].")
    res = answer_with_sources(question="שאלה", sources=sources, complete_fn=fake_bad_id)
    passed = res.refused and "law-999/s1" in (res.refusal_reason or "")
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "ציטוט למזהה לא-מוכר -> סירוב, לא מוצג כתקין")

    # --- בלי אף ציטוט כששסופקו sources -> סירוב (לא-מעוגנת) ---
    fake_no_cite = _fake_complete_factory("תשובה בלי שום ציטוט מקור.")
    res = answer_with_sources(question="שאלה", sources=sources, complete_fn=fake_no_cite)
    passed = res.refused and "לא כללה אף ציטוט" in (res.refusal_reason or "")
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "בלי אף ציטוט -> סירוב כלא-מעוגנת")

    # --- המודל עצמו מדווח "אין מקור מספיק" -> סירוב עם הסיבה שהוא נתן ---
    fake_model_refuses = _fake_complete_factory("אין מקור מספיק: המקורות לא עוסקים בנושא הזה.")
    res = answer_with_sources(question="שאלה לא-קשורה", sources=sources, complete_fn=fake_model_refuses)
    passed = res.refused and res.refusal_reason == "המקורות לא עוסקים בנושא הזה."
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "סירוב-מודל מפורש -> refused עם ההסבר שניתן")

    # --- context_block נבנה עם כל מקור, וה-id שלו מופיע כפי שהוא ---
    fake_ctx = _fake_complete_factory("תשובה [מקור:law-1/s6].")
    answer_with_sources(question="שאלה", sources=sources, complete_fn=fake_ctx)
    system_sent = fake_ctx.calls[0]["system"]
    passed = "[מקור:law-1/s5]" in system_sent and "[מקור:law-1/s6]" in system_sent and "הכנסת בוחרת יושב ראש" in system_sent
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "בניית ההקשר כוללת את כל המקורות עם מזהיהם ותוכנם")

    # --- תג אחד עם כמה מזהים (נצפה בבדיקה החיה, 26.9) - לא "מזהה לא מוכר" ---
    fake_multi = _fake_complete_factory("הכנסת בוחרת יושב ראש [מקור:law-1/s6, law-1/s5].")
    res = answer_with_sources(question="שאלה", sources=sources, complete_fn=fake_multi)
    passed = not res.refused and res.cited_source_ids == ["law-1/s5", "law-1/s6"]
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "תג עם שני מזהים מופרדים בפסיק - שניהם מוכרים, התשובה עוברת", res.refusal_reason or "")
    fake_multi_bad = _fake_complete_factory("טענה [מקור:law-1/s5, law-9/s1].")
    res = answer_with_sources(question="שאלה", sources=sources, complete_fn=fake_multi_bad)
    passed = res.refused and "law-9/s1" in (res.refusal_reason or "")
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "ואם אחד מהם לא מוכר - עדיין נדחית")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
