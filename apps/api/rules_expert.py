"""מומחה התקנון (משימה ברק, 2026-09-17: "חיבור ולא בנייה מאפס") -
תשובות מעוגנות-מקורות (packages/llm.answer_with_sources, לא draft())
על סמך תקנון הכנסת, חוק הכנסת, וחוק-יסוד: הכנסת בלבד - "כלי שעונה
על שאלת תקנון בלי להצביע על הסעיף הוא כלי פגום" (CLAUDE.md).

**אין שלב אחזור - כל המאגר נכנס לכל שאלה.** עד 2026-09-22 נבחרו
ששת הסעיפים בעלי חפיפת-המילים הגבוהה ביותר, והמודל ראה רק אותם.
המדידה הראתה שזה נכשל בדיוק בשאלות שבהן הכלי נחוץ: על "האם אפשר
להגיש הסתייגויות בקריאה ראשונה?" נבחרו סעיפים 44, 87, 90, 91, 92
ו-6 - **בלי סעיף 86**, שממנו התשובה נובעת - והכלי סירב. התשובה
אינה כתובה בסעיף בודד; היא מצטרפת מכמה מקומות, וזה בדיוק מה
שאחזור top-k אינו יכול לספק.

**ומדידה נגדית שהפכה את ההנחה:** החשד היה שהאחזור עולה זמן. הוא
עולה **0.01 שניות**. העיכוב היה טעינת 285 הסעיפים מ-Supabase בכל
שאלה (4.8-5.9 שניות) - ולכן המאגר נטען כאן **פעם אחת לכל תהליך**
(_sources_cached), והוא אינו משתנה בין שאלות.

**שלושת המספרים שקבעו את הארכיטקטורה** (נמדדו, 2026-09-22):
- כל המאגר = **154,238 טוקנים** - נכנס בחלון של 200K.
- בלי הזרמה: 17.5 שניות עד שמופיע משהו. **עם הזרמה ומטמון חם:
  0.6 שניות למילה הראשונה** - מהר יותר מהמצב הקודם (1.1).
- עלות: $0.04 לשאלה במטמון חם, $0.62 לכתיבת מטמון של שעה.

**מגבלה ידועה:** 154K מתוך 200K משאירים ~45K לתשובה, וזה מספיק
לשאלה בודדת ולא לשיחה רב-תורית. ראו docs/open-gaps.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
from chunking import collect_text  # noqa: E402
from node import find_sections  # noqa: E402
from service import (  # noqa: E402
    LLMConfigError,
    LLMRequestError,
    LLMResult,
    SourceChunk,
    answer_with_sources,
    answer_with_sources_stream,
)

from law_registry import LawNotFoundError, load_law  # noqa: E402

SOURCE_LAW_IDS = ["law-tkanon-haknesset", "law-2000325", "law-2000037"]

_WORD_RE = re.compile(r"[א-ת\w]+")

# המאגר נטען פעם אחת לכל תהליך. נמדד שטעינתו מ-Supabase עולה
# 4.8-5.9 שניות - כמחצית מזמן התגובה - והוא אינו משתנה בין שאלות.
# **ריק ולא None כשהטעינה נכשלה אינו מצב תקין:** רשימה ריקה גורמת
# לסירוב "אין מקורות", שנראה למשתמש כמו "אין תשובה". ולכן כישלון
# טעינה אינו נשמר במטמון - הניסיון הבא ינסה שוב.
_sources_cache: list[SourceChunk] | None = None

# 2,500 מספיקים לתשובה מנומקת עם ציטוטים (נמדד: 865-900 בפועל),
# ונשארים בתוך ~45K שנותרו בחלון אחרי 154K של המקורות.
_MAX_TOKENS = 2500

_EXTRA_INSTRUCTIONS = (
    "אתה מומחה תקנון הכנסת. אתה עונה רק על סמך תקנון הכנסת, חוק "
    "הכנסת וחוק-יסוד: הכנסת - שלושת המקורות שסופקו. אם השאלה נוגעת "
    "לנושא אחר (חקיקה כללית, עניינים אישיים וכו') - זה מחוץ לתחום שלך.\n"
    "שלושת המקורות ניתנים לך במלואם - אל תניח שסעיף חסר. תשובה נובעת "
    "לעתים קרובות מצירוף של כמה סעיפים ולא מאחד: אם שאלו אותך על שלב "
    "בהליך שאינו מוזכר במפורש, בדוק היכן כן מוזכר הנושא והסק מכך.\n"
    # שני הסימונים האלה **אינם מחלישים את שומר הציטוט** - הם נוסעים
    # בתוך אותו ניסוח סירוב שהשומר כבר מכיר, ורק מאפשרים לממשק
    # להבדיל בין "לא מצאתי" לבין "זו לא שאלה למאגר". כך אין כאן
    # רשימת מילות-מפתח ("מה דעתך") בקוד - המודל מסווג לפי ההקשר.
    "כשאתה משיב בניסוח הסירוב, הוסף בתחילת ההסבר סימון אחד: "
    "\"[דעה]\" אם נשאלת לדעתך האישית או להעדפה שלך; "
    "\"[מחוץ לתחום]\" אם השאלה אינה נוגעת לתקנון, לחוק הכנסת או "
    "לחוק-יסוד: הכנסת. אם השאלה כן בתחום ופשוט לא מצאת תשובה - "
    "אל תוסיף סימון."
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


def sources(*, refresh: bool = False) -> list[SourceChunk]:
    """שלושת המקורות, נטענים פעם אחת לכל תהליך. refresh=True מאלץ
    טעינה מחדש (לשימוש אחרי ingest, ובבדיקות)."""
    global _sources_cache
    if refresh or not _sources_cache:
        loaded = _load_sources()
        if not loaded:
            return []          # לא שומרים כישלון במטמון
        _sources_cache = loaded
    return _sources_cache


class RulesExpertError(Exception):
    """שכבת אפליקציה - LLM לא זמין/נכשל (ANTHROPIC_API_KEY חסר/רשת),
    אותו דפוס כמו QueryDraftError/AgendaDraftError - סוג אחד ל-
    main.py, לא צריך להכיר את LLMConfigError/LLMRequestError הפנימיים."""


def source_labels(source_ids: list[str]) -> list[str]:
    """מזהה פנימי (law-2000325/12) -> שם קריא בעברית ("חוק הכנסת,
    סעיף 12"). התווית כבר נבנית ב-_load_sources; כאן רק מחפשים
    אותה. מזהה שלא נמצא מוחזר כפי שהוא - **לא נשמט**, כי היעלמות
    מקור מרשימת המקורות גרועה ממזהה מכוער."""
    by_id = {c.id: c.label for c in sources()}
    return [by_id.get(sid, sid) for sid in source_ids]


def ask(question: str) -> LLMResult:
    """תשובה מלאה בבת אחת. נשאר ל-API ולבדיקות; הממשק משתמש
    ב-ask_stream, כי 17 שניות של מסך ריק גרועות מהמצב שהוחלף."""
    try:
        return answer_with_sources(question=question, sources=sources(),
                                   extra_instructions=_EXTRA_INSTRUCTIONS,
                                   max_tokens=_MAX_TOKENS)
    except (LLMConfigError, LLMRequestError) as e:
        raise RulesExpertError(f"שכבת ה-LLM לא זמינה: {e}") from None


def ask_stream(question: str):
    """מניב מחרוזות טקסט ככל שהן מגיעות, ובסוף LLMResult אחד עם
    פסק הדין של שומר הציטוט. **הקורא חייב לכבד את הפסק הזה** -
    ראו service.answer_with_sources_stream."""
    try:
        yield from answer_with_sources_stream(
            question=question, sources=sources(),
            extra_instructions=_EXTRA_INSTRUCTIONS, max_tokens=_MAX_TOKENS)
    except (LLMConfigError, LLMRequestError) as e:
        raise RulesExpertError(f"שכבת ה-LLM לא זמינה: {e}") from None
