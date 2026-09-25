"""ניסוח LLM לדברי הסבר ולחלק ה"מהות" בשם הצעת חוק - משימה ה
(ברק, 2026-09-16). **מרחיב**, לא מחליף, את explanatory_draft.py/
bill_title.py הדטרמיניסטיים - הם נשארים ה-fallback כש-LLM לא זמין
(`ANTHROPIC_API_KEY` חסר) או נכשל (רשת), כך ש-`/render` וה-docx
הרגילים אף פעם לא תלויים ברשת/במפתח כדי לעבוד בכלל.

נקרא רק מ-endpoint ייעודי (`POST .../draft`) שהמשתמש מפעיל במפורש -
**לא** מ-`_render`/`_bill_from_meta` הרגילים, כדי לא להוסיף latency/
עלות-רשת-LLM לכל preview חי בזמן שהמשתמש מקליד (זה קורה הרבה פעמים
בדקה בזרימת עריכה רגילה).

קוראת רק ל-`packages/llm.service.draft()` (חוק ברזל 4 - "אין קריאה
למודל מחוץ ל-packages/llm") - אף פעם לא נוגעת ב-`lines`/בנוסח החוק
עצמו, רק בונה טקסט מלווה נפרד. אין אכיפת-ציטוט כאן (draft(), לא
answer_with_sources()) - תואם את הכרעת המוצר המתועדת ב-CLAUDE.md §4:
דברי הסבר ושם ההצעה מנוסחים בחופשיות, כי הם לעולם לא נכנסים לטבלת
החקיקה עצמה.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
from service import LLMConfigError, LLMRequestError, draft  # noqa: E402
from node import LegislativeNode, find_sections  # noqa: E402
from chunking import collect_text  # noqa: E402
from render_bill import Line  # noqa: E402
from bill_title import default_bill_title, strip_law_own_year  # noqa: E402
from explanatory_draft import draft_explanatory_notes  # noqa: E402

_EXPLANATORY_INSTRUCTIONS = (
    "אתה מנסח דברי הסבר להצעת חוק ישראלית, בעברית, בסגנון 'דברי הסבר' "
    "רשמיים לכנסת. קיבלת את שם החוק, ולכל סעיף שמשתנה: מספרו, כותרת "
    "השוליים שלו, הנוסח לפני ואחרי, והוראת התיקון.\n\n"
    "**תאר את מהות השינוי בדין - לא את הפעולה על המילים.** מה ההסדר היום, "
    "ומה הוא יהיה. למשל: אם בסעיף 'מקום המושב' הוחלף 'ירושלים' ב'תל אביב' - "
    "'מוצע לקבוע כי מקום מושבה של הכנסת יהיה בתל אביב, במקום בירושלים.' "
    "ולא 'מוצע להחליף בסעיף 2 את המילה ירושלים'. היעזר בכותרת השוליים כדי "
    "להבין במה עוסק הסעיף.\n\n"
    "**אל תחזור על הוראות התיקון** ואל תכתוב רשימה 'תיקון סעיף 5: ...'. "
    "אזכור מספר הסעיף מותר, בתוך המשפט ('בסעיף 2 לחוק מוצע לקבוע...').\n\n"
    "**אל תמציא סיבות.** לא ניתן לך שום נימוק - ולכן אסור לכתוב למה השינוי "
    "נעשה: לא 'בשל', 'לאור', 'נוכח', 'על מנת', 'במטרה', 'כדי ל', 'מתוך "
    "הכרה', 'הצורך ב'. רק מה משתנה. את הנימוק יוסיף המנסח בעצמו.\n\n"
    "לשון: 'מוצע לקבוע', 'מוצע לבטל', 'מוצע להוסיף'. פסקה קצרה אחת לכל שינוי "
    "מהותי (שינויים באותו עניין - בפסקה אחת). ענייני בלבד. החזר רק את "
    "הפסקאות, מופרדות בשורה ריקה - בלי כותרת, בלי מספור, בלי סימני עיצוב."
)

# **שומר דטרמיניסטי נגד נימוק מומצא** (ח9) - אותו עיקרון כמו בשאילתות
# (query_tool.unsupported_source_claims): הנחיה אינה שומר. המשתמש לא נותן
# כאן נימוק בכלל, ולכן כל אחד מהצירופים האלה הוא המצאה של המודל.
_INVENTED_REASON = re.compile(
    r"(?:^|[\s(\-–,])(?:ו?(?:בשל|לאור|נוכח|עקב|בעקבות|על\s+מנת|במטרה|כדי\s+ל|מתוך\s+הכרה|"
    r"בשים\s+לב|הצורך\s+ב|מתוך\s+רצון|בהתאם\s+למגמה|תכלית\s+התיקון|מטרת\s+התיקון))"
)
_REWRITE_WITHOUT_REASON = (
    "כתבת נימוק שלא ניתן לך ({found}). כתוב מחדש את אותן פסקאות - רק מה "
    "משתנה בדין, בלי שום 'למה'."
)


def _phrases_in(text: str) -> set[str]:
    return {m.group(0).strip(" (-–,") for m in _INVENTED_REASON.finditer(text)}


def _sentences(paragraph: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+", paragraph.strip()) if x]


def _drop_reason_sentences(paragraphs: list[str], allowed: set[str] = frozenset()) -> list[str]:
    """המוצא האחרון: משפט עם נימוק מומצא יורד, המהות נשארת."""
    out = []
    for p in paragraphs:
        kept = [x for x in _sentences(p)
                if not (_phrases_in(x) - allowed)]
        if kept:
            out.append(" ".join(kept))
    return out


_TITLE_INSTRUCTIONS = (
    "אתה מנסח את חלק ה'מהות' בשם הצעת חוק ישראלית, שמופיע בפורמט "
    "הקבוע: \"הצעת חוק <שם החוק> (תיקון – <מהות>), <שנה>\". קיבלת את "
    "שם החוק ואת הוראות התיקון. החזר *רק* את מחרוזת ה'מהות' עצמה - "
    "ניסוח קצר (בדרך כלל 3-8 מילים) שמתאר במדויק מה משתנה. בלי "
    "מירכאות, בלי נקודה בסוף, בלי לחזור על שם החוק, בלי המילה 'תיקון' "
    "(היא כבר בתבנית). דוגמה לפורמט הרצוי בלבד (לא לתוכן): "
    "'הארכת תקופת ההתיישנות' או 'ביטול פטור ממכרז'."
)


def _sections_context(before: LegislativeNode, after: LegislativeNode, touched_numbers: set[str],
                      lines: list[Line] | None = None) -> str:
    """לכל סעיף שנגע בו: מספר, **כותרת השוליים**, הנוסח **המלא** לפני ואחרי
    (כולל סעיפים קטנים - node.text של סעיף עם סעיפים קטנים ריק), והוראת
    התיקון שלו. בלי כותרת השוליים המודל לא יודע שסעיף 2 הוא "מקום המושב"."""
    before_sections = find_sections(before)
    after_sections = find_sections(after)
    by_heading: dict[str, list[str]] = {}
    for ln in lines or []:
        if ln.side_heading:
            by_heading.setdefault(ln.side_heading, []).append(f"{ln.text}{ln.text_after}".strip())
    parts = []
    for number in sorted(touched_numbers, key=lambda n: (len(n), n)):
        b = before_sections.get(number)
        a = after_sections.get(number)
        title = (a or b).margin_title if (a or b) else None
        head = f"סעיף {number}" + (f" (כותרת השוליים: {title})" if title else "")
        if b and a and b.margin_title and a.margin_title and b.margin_title != a.margin_title:
            head += f" - כותרת השוליים משתנה ל: {a.margin_title}"
        before_text = collect_text(b) if b else "(סעיף חדש - לא היה קיים)"
        after_text = (collect_text(a) if a and a.status != "repealed" else "(הסעיף מבוטל)") if a else "(הסעיף מבוטל)"
        instr = [x for h, xs in by_heading.items() if number in h.split() for x in xs]
        block = f"{head}:\nלפני: {before_text}\nאחרי: {after_text}"
        if instr:
            block += "\nהוראת התיקון: " + " ".join(instr)
        parts.append(block)
    return "\n\n".join(parts)


def _lines_context(lines: list[Line]) -> str:
    parts = []
    seen: set[str] = set()
    for ln in lines:
        if not ln.side_heading or ln.side_heading in seen:
            continue
        seen.add(ln.side_heading)
        parts.append(f"{ln.side_heading}: {ln.text}{ln.text_after}")
    return "\n".join(parts)


def draft_explanatory_llm(
    lines: list[Line], before: LegislativeNode, after: LegislativeNode, touched_numbers: set[str],
    *, draft_fn=None,
) -> list[str]:
    """פסקאות דברי הסבר: מהות השינוי בדין, בלי נימוק מומצא (ח9). נופלת
    חזרה ל-explanatory_draft.draft_explanatory_notes (הדטרמיניסטי) אם
    ה-LLM לא זמין/נכשל - לא זורקת, לעולם מחזירה טיוטה כלשהי.

    draft_fn: הזרקה לבדיקות אופליין (ברירת מחדל - service.draft)."""
    run = draft_fn or draft
    try:
        content = (
            f"שם החוק: {before.full_title or ''}\n\n"
            f"{_sections_context(before, after, touched_numbers, lines)}"
        )
        text = run(instructions=_EXPLANATORY_INSTRUCTIONS, content=content, max_tokens=1000)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        # צירוף שמופיע בנוסח החוק עצמו ("... כדי לקבל היתר") הוא תוכן, לא נימוק.
        found = sorted({m.group(0).strip(" (-–,") for p in paragraphs
                        for m in _INVENTED_REASON.finditer(p)} - _phrases_in(content))
        if found:
            # קודם מנסחים מחדש, ורק אז מורידים משפטים - כמו בשאילתות.
            retry = run(instructions=_EXPLANATORY_INSTRUCTIONS,
                        content=content + "\n\n" + _REWRITE_WITHOUT_REASON.format(found=", ".join(found)),
                        max_tokens=1000)
            paragraphs = [p.strip() for p in retry.split("\n\n") if p.strip()]
            paragraphs = _drop_reason_sentences(paragraphs, allowed=_phrases_in(content))
        if paragraphs:
            return paragraphs
    except (LLMConfigError, LLMRequestError):
        pass
    return draft_explanatory_notes(lines)


def draft_bill_title_llm(law_full_title: str, lines: list[Line]) -> str:
    """שם מלא: 'הצעת חוק <שם> (תיקון – <מהות מנוסחת>), <שנה>'. נופלת
    חזרה ל-bill_title.default_bill_title (עם PLACEHOLDER) אם ה-LLM
    לא זמין/נכשל, או אם הפורמט של law_full_title לא מוכר (strip_law_
    own_year מחזירה את המקור כמו שהוא במקרה הזה - לא מנחשת)."""
    try:
        content = f"שם החוק: {law_full_title}\n\nהוראות התיקון:\n{_lines_context(lines)}"
        substance = draft(instructions=_TITLE_INSTRUCTIONS, content=content, max_tokens=100).strip()
        if substance:
            base_name = strip_law_own_year(law_full_title)
            from bill_title import current_hebrew_year_label
            from pyluach import dates

            gregorian_year = dates.GregorianDate.today().year
            return f"הצעת חוק {base_name} (תיקון – {substance}), {current_hebrew_year_label()}–{gregorian_year}"
    except (LLMConfigError, LLMRequestError):
        pass
    return default_bill_title(law_full_title)
