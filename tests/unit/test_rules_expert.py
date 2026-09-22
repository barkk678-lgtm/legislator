"""בדיקות ל-apps/api/rules_expert.py ול-packages/llm הזרמה - בלי
רשת ובלי DB.

**מה השתנה ולמה הבדיקה הישנה נמחקה:** עד 2026-09-22 הכלי בחר שישה
סעיפים בעלי חפיפת-מילים והבדיקה כאן נעלה את הדירוג הזה. המדידה
הראתה שהאחזור עצמו הוא הבאג - הוא בחר 44/87/90/91/92/6 לשאלה על
הסתייגויות **בלי סעיף 86**, שממנו התשובה נובעת - ושלב האחזור בוטל.
בדיקה שנועלת מנגנון שהוסר אינה "נשברת", היא מיותרת; מה שנשאר לנעול
הוא מה שמחליף אותו: שומר הציטוט תחת הזרמה, ותרגום המזהים לעברית.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))

import rules_expert as rx  # noqa: E402
from client import RawCompletion  # noqa: E402
from service import SourceChunk, answer_with_sources_stream  # noqa: E402

SRC = [
    SourceChunk(id="law-tkanon-haknesset/86", label="תקנון הכנסת, סעיף 86", text="הסתייגות..."),
    SourceChunk(id="law-2000325/12", label="חוק הכנסת, סעיף 12", text="חסינות..."),
]


def fake_stream(chunks):
    """מחקה את complete_stream: מניב טקסט ואז RawCompletion אחד."""
    def _s(*, system, user_message, max_tokens, cache_system=False):
        for c in chunks:
            yield c
        yield RawCompletion(text="".join(chunks), input_tokens=154000,
                            output_tokens=len(chunks), stop_reason="end_turn")
    return _s


def run(chunks, sources=SRC):
    out, verdict = [], None
    for piece in answer_with_sources_stream(question="שאלה", sources=sources,
                                            stream_fn=fake_stream(chunks)):
        (out.append(piece) if isinstance(piece, str) else None)
        if not isinstance(piece, str):
            verdict = piece
    return "".join(out), verdict


def test_grounded_answer_streams_and_passes():
    streamed, v = run(["ההסתייגות מוגשת בוועדה ", "[מקור:law-tkanon-haknesset/86]."])
    assert "ההסתייגות" in streamed
    assert v.refused is False, v.refusal_reason
    assert v.cited_source_ids == ["law-tkanon-haknesset/86"]


def test_ungrounded_answer_is_refused_even_though_it_was_streamed():
    """**ההבדל היחיד מהמצב הקודם:** הטקסט כבר הוצג. השומר עדיין
    פוסל אותו, ו-text חוזר ריק - כדי שהקורא לא יוכל בטעות להשאיר
    על המסך תשובה שנפסלה."""
    streamed, v = run(["אפשר להגיש הסתייגויות בכל שלב."])
    assert streamed  # הוזרם
    assert v.refused is True
    assert v.text == ""


def test_citation_to_unknown_id_is_refused():
    _, v = run(["טענה [מקור:law-המצאה/999]."])
    assert v.refused is True
    assert "לא מוכרים" in (v.refusal_reason or "")


def test_model_refusal_prefix_is_passed_through_with_its_marker():
    """הסימון [דעה]/[מחוץ לתחום] נוסע בתוך הסיבה - הממשק מנסח
    לפיו, והשומר עצמו לא השתנה."""
    _, v = run(["אין מקור מספיק: [דעה] אין לי העדפות."])
    assert v.refused is True
    assert "[דעה]" in v.refusal_reason


def test_no_sources_refuses_without_any_network_call():
    def explode(**kwargs):
        raise AssertionError("נקראה הרשת למרות שאין מקורות")
        yield
    verdict = None
    for piece in answer_with_sources_stream(question="ש", sources=[], stream_fn=explode):
        verdict = piece
    assert verdict.refused is True


def test_source_labels_translate_ids_to_hebrew():
    rx._sources_cache = SRC
    assert rx.source_labels(["law-2000325/12"]) == ["חוק הכנסת, סעיף 12"]


def test_unknown_source_id_is_kept_not_dropped():
    """מזהה שלא נמצא מוחזר כפי שהוא - היעלמות מקור מהרשימה גרועה
    ממזהה מכוער."""
    rx._sources_cache = SRC
    assert rx.source_labels(["law-לא-קיים/1"]) == ["law-לא-קיים/1"]


def test_failed_load_is_not_cached():
    """טעינה שנכשלה מחזירה [] ו**אינה נשמרת** - אחרת הכלי היה
    עונה "אין מקורות" לנצח אחרי תקלה רגעית ב-DB."""
    rx._sources_cache = None
    rx._load_sources = lambda: []
    assert rx.sources() == []
    assert rx._sources_cache is None


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_rules_expert: כל הבדיקות עברו")
