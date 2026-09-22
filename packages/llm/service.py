"""ממשק ה-LLM הציבורי היחיד (CLAUDE.md: "packages/llm - היחיד שקורא
למודל"). כל כלי אחר (הצעת חוק/דברי הסבר, שאילתא, הצעה לסדר, ובעתיד
מומחה תקנון/מחקר) קורא לפונקציות כאן - **לא** בונה קריאת HTTP למודל
בעצמו (client.py הוא פרטי לחבילה הזו). אם אתה מוצא את עצמך כותב קריאה
למודל מחוץ לקובץ הזה - זה הגבול, עצור (ברק, 2026-09-16).

שני מצבים, לא אחד - כי חוק ברזל 4 מגדיר שני סוגי היתר שונים:

1. `draft()` - ניסוח חופשי של טקסט מלווה (דברי הסבר, שם הצעה, שכתוב
   ניסוח שהמשתמש כתב). **בלי אכיפת ציטוט** - בכוונה, לא פער: ההחלטה
   המתועדת ב-CLAUDE.md §4 ("שם הצעת החוק ודברי ההסבר מנוסחים בחופשיות
   כברירת מחדל") קבעה במפורש שזה מותר, כי הטקסט הזה לעולם לא נכנס
   לטבלת החקיקה עצמה (packages/amend לא קורא לכאן בכלל - זה האכיפה
   האמיתית, לא runtime check).

2. `answer_with_sources()` - תשובה מעוגנת במקורות: איתור סעיפים
   מתיאור חופשי (חוק ברזל 4, תפקיד 3), וכל כלי עתידי שעונה על שאלה
   על סמך הקורפוס (מומחה תקנון, מחקר) - "חובת המקור חלה עליהם במלואה:
   כלי שעונה על שאלת תקנון בלי להצביע על הסעיף הוא כלי פגום" (CLAUDE.md).
   בלי sources בכלל - סירוב **בלי קריאת רשת** (לא "מבקשים מהמודל
   לסרב" - זה שקוף לניצול/הזיה, ראו _NO_SOURCES_REFUSAL). עם sources -
   כל משפט בתשובה חייב לצטט מזהה מקור אמיתי מתוך מה שסופק; ציטוט
   למזהה לא-מוכר, או תשובה בלי אף ציטוט כששסופקו מקורות, נחשבים
   הפרת-עיגון ומטופלים כסירוב - לא מוחזרים למשתמש כאילו הם תקינים.
"""

import re
from dataclasses import dataclass

from client import (  # noqa: F401 (re-exported)
    LLMConfigError,
    LLMRequestError,
    RawCompletion,
    complete,
    complete_stream,
)

_CITATION_RE = re.compile(r"\[מקור:([^\]]+)\]")
_NO_SOURCES_REFUSAL = "אין מקורות רלוונטיים סופקו - לא ניתן לענות בלי עיגון בקורפוס."
_MODEL_REFUSAL_PREFIX = "אין מקור מספיק:"


@dataclass
class SourceChunk:
    """יחידת מקור אחת שמוזנת להקשר. id הוא מה שהמודל מצטט בחזרה
    (חייב להיות ייחודי בתוך קריאה בודדת); label הוא מה שמוצג למשתמש
    (למשל "חוק הכנסת, סעיף 12"), text הוא הנוסח עצמו."""

    id: str
    label: str
    text: str


@dataclass
class LLMResult:
    text: str
    refused: bool
    refusal_reason: str | None
    cited_source_ids: list[str]
    input_tokens: int
    output_tokens: int


def draft(*, instructions: str, content: str, max_tokens: int = 1500, complete_fn=complete) -> str:
    """ניסוח/שכתוב חופשי של טקסט מלווה - לא נוגע בנוסח חוק (חוק ברזל 4,
    תפקידים 1-2). instructions: מה מבקשים (למשל "כתוב דברי הסבר לפי
    סגנון Hesber"). content: החומר הגולמי לניסוח על בסיסו (למשל הוראות
    התיקון + לפני/אחרי, או טיוטת טקסט של המשתמש לשכתוב). complete_fn:
    הזרקה לבדיקות אופליין (ברירת מחדל - קריאת הרשת האמיתית ל-Anthropic),
    אותו דפוס בדיוק כמו fetch= ב-db_ingest.build_ingest_plan."""
    result = complete_fn(system=instructions, user_message=content, max_tokens=max_tokens)
    return result.text.strip()


def answer_with_sources(
    *,
    question: str,
    sources: list[SourceChunk],
    extra_instructions: str = "",
    max_tokens: int = 1500,
    complete_fn=complete,
) -> LLMResult:
    """תשובה מעוגנת-מקורות עם אכיפת ציטוט וסירוב-בלי-מקור. ראו דוקסטרינג
    העליון להסבר המלא. extra_instructions: הנחיות ספציפיות-לכלי מעבר
    לחוזה הבסיסי (למשל "ענה בפורמט שאילתא לשר")."""
    if not sources:
        return LLMResult(
            text="",
            refused=True,
            refusal_reason=_NO_SOURCES_REFUSAL,
            cited_source_ids=[],
            input_tokens=0,
            output_tokens=0,
        )

    known_ids = {s.id for s in sources}
    context_block = "\n\n".join(f"[מקור:{s.id}] ({s.label})\n{s.text}" for s in sources)

    system = (
        "אתה עונה אך ורק על סמך המקורות שסופקו למטה, בעברית. "
        "כל משפט עובדתי בתשובה חייב להסתיים בציטוט בפורמט [מקור:<מזהה>], "
        "כשה-<מזהה> הוא בדיוק אחד ממזהי המקורות שסופקו - אסור להמציא מזהה. "
        "אם המקורות שסופקו אינם מכילים מספיק מידע לענות על השאלה, "
        f'אל תנחש ואל תשתמש בידע כללי - השב בדיוק במילים: "{_MODEL_REFUSAL_PREFIX} <הסבר קצר>".\n\n'
        f"{extra_instructions}\n\nהמקורות:\n{context_block}"
    )

    completion = complete_fn(system=system, user_message=question, max_tokens=max_tokens)
    text = completion.text.strip()

    if text.startswith(_MODEL_REFUSAL_PREFIX):
        return LLMResult(
            text="",
            refused=True,
            refusal_reason=text[len(_MODEL_REFUSAL_PREFIX):].strip() or "המודל דיווח שאין מספיק מידע במקורות.",
            cited_source_ids=[],
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )

    cited = _CITATION_RE.findall(text)
    unknown = [c for c in cited if c not in known_ids]
    if unknown:
        return LLMResult(
            text="",
            refused=True,
            refusal_reason=f"התשובה ציטטה מזהי מקור לא מוכרים: {unknown} - נדחתה כהפרת-עיגון, לא הוצגה כתקינה.",
            cited_source_ids=[],
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
    if not cited:
        return LLMResult(
            text="",
            refused=True,
            refusal_reason="התשובה לא כללה אף ציטוט מקור, למרות שסופקו מקורות - נדחתה כלא-מעוגנת.",
            cited_source_ids=[],
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )

    return LLMResult(
        text=text,
        refused=False,
        refusal_reason=None,
        cited_source_ids=sorted(set(cited)),
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
    )


def _grounding_verdict(text: str, known_ids: set[str]) -> tuple[bool, str | None, list[str]]:
    """**שומר הציטוט, מופרד מההרכבה של התשובה.** בדיוק אותן שלוש
    בדיקות של answer_with_sources - סירוב מפורש של המודל, ציטוט
    למזהה לא מוכר, ותשובה בלי אף ציטוט - כדי שגרסת ההזרמה לא תהיה
    עותק שני שנסחף. מחזיר (refused, reason, cited)."""
    if text.startswith(_MODEL_REFUSAL_PREFIX):
        return True, text[len(_MODEL_REFUSAL_PREFIX):].strip() or "המודל דיווח שאין מספיק מידע במקורות.", []
    cited = _CITATION_RE.findall(text)
    unknown = [c for c in cited if c not in known_ids]
    if unknown:
        return True, f"התשובה ציטטה מזהי מקור לא מוכרים: {unknown} - נדחתה כהפרת-עיגון, לא הוצגה כתקינה.", []
    if not cited:
        return True, "התשובה לא כללה אף ציטוט מקור, למרות שסופקו מקורות - נדחתה כלא-מעוגנת.", []
    return False, None, sorted(set(cited))


def answer_with_sources_stream(
    *,
    question: str,
    sources: list[SourceChunk],
    extra_instructions: str = "",
    max_tokens: int = 1500,
    cache_sources: bool = True,
    stream_fn=complete_stream,
):
    """גרסת הזרמה של answer_with_sources. מניבה מחרוזות טקסט ככל
    שהן מגיעות, ובסוף **מניבה LLMResult אחד** עם פסק הדין של שומר
    הציטוט על הטקסט המלא.

    **שומר הציטוט לא נחלש - אבל הוא מגיע אחרי שהטקסט כבר על המסך,
    וזה שינוי אמיתי שצריך להיות מודע לו.** ב-answer_with_sources
    תשובה לא-מעוגנת לעולם לא נראתה; כאן היא נראית ואז נמשכת. ולכן
    הקורא **חייב** לבדוק את ה-LLMResult האחרון ולהחליף את מה שהוצג
    כשהוא refused - הזרמה שמתעלמת ממנו מציגה תשובה לא-מעוגנת
    כתקינה, וזה בדיוק מה שהשומר נועד למנוע.

    בלי sources - סירוב בלי קריאת רשת, זהה ל-answer_with_sources."""
    if not sources:
        yield LLMResult(text="", refused=True, refusal_reason=_NO_SOURCES_REFUSAL,
                        cited_source_ids=[], input_tokens=0, output_tokens=0)
        return

    known_ids = {s.id for s in sources}
    context_block = "\n\n".join(f"[מקור:{s.id}] ({s.label})\n{s.text}" for s in sources)
    system = (
        "אתה עונה אך ורק על סמך המקורות שסופקו למטה, בעברית. "
        "כל משפט עובדתי בתשובה חייב להסתיים בציטוט בפורמט [מקור:<מזהה>], "
        "כשה-<מזהה> הוא בדיוק אחד ממזהי המקורות שסופקו - אסור להמציא מזהה. "
        "מותר וצריך להסיק מצירוף של כמה מקורות; כשהמסקנה נובעת מכמה "
        "סעיפים - צטט את כולם. אם המקורות שסופקו אינם מכילים מספיק מידע "
        "לענות על השאלה, אל תנחש ואל תשתמש בידע כללי - השב בדיוק במילים: "
        f'"{_MODEL_REFUSAL_PREFIX} <הסבר קצר>".\n\n'
        f"{extra_instructions}\n\nהמקורות:\n{context_block}"
    )

    completion: RawCompletion | None = None
    for piece in stream_fn(system=system, user_message=question,
                           max_tokens=max_tokens, cache_system=cache_sources):
        if isinstance(piece, RawCompletion):
            completion = piece
        else:
            yield piece
    if completion is None:
        raise LLMRequestError("ההזרמה הסתיימה בלי סיכום שימוש - תשובה לא שלמה.")

    text = completion.text.strip()
    refused, reason, cited = _grounding_verdict(text, known_ids)
    yield LLMResult(text="" if refused else text, refused=refused, refusal_reason=reason,
                    cited_source_ids=cited, input_tokens=completion.input_tokens,
                    output_tokens=completion.output_tokens)
