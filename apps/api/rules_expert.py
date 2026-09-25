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
    "אל תוסיף סימון.\n"
    # ת1 (25.9.2026): התשובה נפתחה ב"# ההבדל בין..." ו"## הצעה לסדר היום",
    # עם 7 זוגות **. הממשק מציג טקסט ולא Markdown, וסולמית היא רעש.
    "צורת התשובה: פסקאות רגילות. **בלי כותרות ובלי סימן #.** מותר להדגיש "
    "מונח מרכזי אחד או שניים ב-**כך**, לא יותר."
)


# ", התשנ"ד–1994" / ", תשכ"א–1961" בסוף שם החוק. בתשובה ברק רוצה
# "חוק הכנסת, סעיף 12" - השנה אינה מוסיפה כלום כשיש רק חוק כנסת אחד.
_LAW_YEAR_SUFFIX = re.compile(r",\s*ה?תש[^,]*[–-]\d{4}\s*$")


def short_law_name(full_title: str) -> str:
    return _LAW_YEAR_SUFFIX.sub("", full_title).strip()


# ── ת2 (25.9.2026): תגי המקור בתוך התשובה ────────────────────────────
# המודל כותב `[מקור:law-tkanon-haknesset/52]` - זה הפורמט ששומר הציטוט
# בודק, ולכן הוא לא משתנה בהנחיה. **מה שמשתנה הוא מה שהמשתמש רואה**:
# כל תג הופך ל-"(תקנון הכנסת, סעיף 52)", ותגים צמודים מתאחדים לסוגריים
# אחד. עד 25.9 רק רשימת המקורות שמתחת לתשובה תורגמה (task 94), והתגים
# בגוף הטקסט הגיעו למסך כמו שהם - בזרם ובטקסט הסופי כאחד.
_TAG = r"\[מקור:\s*([^\]]+?)\s*\]"
_TAG_RUN = re.compile(rf"\s*{_TAG}(?:\s*{_TAG})*")
_TAG_ONE = re.compile(_TAG)
_TAG_PREFIX = "[מקור:"


def humanize_citations(text: str) -> str:
    """`[מקור:id]` -> `(שם בעברית)`. מזהה לא מוכר - השומר ממילא יפסול
    את התשובה; עד אז הוא לא מוצג כמזהה גולמי אלא נשמט."""
    by_id = {c.id: c.label for c in sources()} if _TAG_PREFIX in text else {}

    def repl(m: re.Match) -> str:
        labels = [by_id[i.strip()] for i in _TAG_ONE.findall(m.group(0)) if i.strip() in by_id]
        return f" ({'; '.join(dict.fromkeys(labels))})" if labels else ""

    return _TAG_RUN.sub(repl, text)


class CitationHumanizer:
    """אותה המרה על זרם. הקושי: תג יכול להיחתך בין שני קטעים
    ("[מקור:law-tk" + "anon-haknesset/52]"), ותגים צמודים יכולים להגיע
    בקטעים נפרדים. לכן נשמר בחוצץ כל מה שאולי עוד יהפוך לתג: '[' פתוח
    בלי ']', וגם רצף תגים בסוף החוצץ (אולי יבוא עוד תג צמוד)."""

    def __init__(self) -> None:
        self._buf = ""

    def _cut(self) -> int:
        buf = self._buf
        cut = len(buf)
        start = buf.rfind("[")
        if start >= 0 and "]" not in buf[start:]:
            tail = buf[start:]
            # '[' שעדיין יכול להפוך ל-"[מקור:" - מחכים; אחרת לא תג
            if _TAG_PREFIX.startswith(tail[: len(_TAG_PREFIX)]) or tail.startswith(_TAG_PREFIX):
                cut = start
        last = None
        for last in _TAG_RUN.finditer(buf, 0, cut):
            pass
        if last is not None and not buf[last.end():cut].strip():
            cut = last.start()
        # רווח שלפני תג שעוד לא נסגר שייך להחלפה (_TAG_RUN בולע אותו).
        # אם הוא יוצא עכשיו, התוצאה היא רווח כפול, והזרם שונה מהטקסט
        # הסופי שהלקוח מציג בסוף - קפיצה שהמשתמש רואה.
        while cut > 0 and buf[cut - 1].isspace():
            cut -= 1
        return cut

    def feed(self, piece: str) -> str:
        self._buf += piece
        cut = self._cut()
        out, self._buf = self._buf[:cut], self._buf[cut:]
        return humanize_citations(out)

    def flush(self) -> str:
        out, self._buf = self._buf, ""
        return humanize_citations(out)


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
        law_title = short_law_name(root.full_title or law_id)
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
