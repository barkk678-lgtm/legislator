"""מומחה התקנון (משימה ברק, 2026-09-17: "חיבור ולא בנייה מאפס") -
תשובות מעוגנות-מקורות (packages/llm.answer_with_sources, לא draft())
על סמך תקנון הכנסת, חוק הכנסת, וחוק-יסוד: הכנסת בלבד - "כלי שעונה
על שאלת תקנון בלי להצביע על הסעיף הוא כלי פגום" (CLAUDE.md).

**retrieval - מילות מפתח, לא embeddings, בכוונה ומתועד:** חיפוש
סמנטי (משימה א) עדיין חסום (ראו night-report.md, api.openai.com).
עד שזה יזמין, האיתור כאן הוא חפיפת-מילים גסה (Jaccard-ish) בין
השאלה לתוכן כל סעיף - **לא** תחליף אמיתי לחיפוש סמנטי, רק דרך
עבודה כרגע. עדיין תקין תחת "חובת המקור" (CLAUDE.md) כי answer_
with_sources() מסרבת כשאין מקור מתאים - היא לא "מזייפת" עיגון על
תוצאות retrieval גרועות, רק על תוצאות ריקות. איכות ה-retrieval
עצמה תלויה בשיפור עתידי (משימה א), לא כאן.

בלי מטמון/state בשרת (10ב) - כל בקשה טוענת מחדש את שלושת המקורות
(אותו עיקרון בדיוק כמו law_registry.load_law בכל /render)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
from chunking import collect_text  # noqa: E402
from node import find_sections  # noqa: E402
from service import LLMConfigError, LLMRequestError, LLMResult, SourceChunk, answer_with_sources  # noqa: E402

from law_registry import LawNotFoundError, load_law  # noqa: E402

SOURCE_LAW_IDS = ["law-tkanon-haknesset", "law-2000325", "law-2000037"]
_TOP_K = 6

_WORD_RE = re.compile(r"[א-ת\w]+")

_EXTRA_INSTRUCTIONS = (
    "אתה מומחה תקנון הכנסת. אתה עונה רק על סמך תקנון הכנסת, חוק "
    "הכנסת וחוק-יסוד: הכנסת - שלושת המקורות שסופקו. אם השאלה נוגעת "
    "לנושא אחר (חקיקה כללית, עניינים אישיים וכו') - זה מחוץ לתחום שלך."
)


def _tokenize(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) > 1}


def _load_sources() -> list[SourceChunk]:
    """כל סעיף בשלושת החוקים הופך ל-SourceChunk מועמד (לא עדיין
    מדורג) - id ייחודי (law_id/section_number), label קריא, text
    מלא (כולל צאצאים, ראו chunking.collect_text - אותו הליכת-עץ
    בדיוק כמו ה-chunking ל-embeddings, שימוש חוזר לא שכפול)."""
    candidates: list[SourceChunk] = []
    for law_id in SOURCE_LAW_IDS:
        try:
            root = load_law(law_id)
        except LawNotFoundError:
            continue  # תקנון הכנסת עדיין לא נטען - לא שגיאה, רק פחות מקורות
        law_title = root.full_title or law_id
        for number, section in find_sections(root).items():
            text = collect_text(section)
            if not text:
                continue
            label = f"{law_title}, סעיף {number}"
            candidates.append(SourceChunk(id=f"{law_id}/{number}", label=label, text=text))
    return candidates


def _rank_sources(question: str, candidates: list[SourceChunk], *, top_k: int = _TOP_K) -> list[SourceChunk]:
    q_words = _tokenize(question)
    if not q_words:
        return []
    scored = []
    for c in candidates:
        overlap = len(q_words & _tokenize(c.label + " " + c.text))
        if overlap > 0:
            scored.append((overlap, c))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [c for _, c in scored[:top_k]]


class RulesExpertError(Exception):
    """שכבת אפליקציה - LLM לא זמין/נכשל (ANTHROPIC_API_KEY חסר/רשת),
    אותו דפוס כמו QueryDraftError/AgendaDraftError - סוג אחד ל-
    main.py, לא צריך להכיר את LLMConfigError/LLMRequestError הפנימיים."""


def ask(question: str) -> LLMResult:
    candidates = _load_sources()
    sources = _rank_sources(question, candidates)
    try:
        return answer_with_sources(question=question, sources=sources, extra_instructions=_EXTRA_INSTRUCTIONS)
    except (LLMConfigError, LLMRequestError) as e:
        raise RulesExpertError(f"שכבת ה-LLM לא זמינה: {e}") from None
