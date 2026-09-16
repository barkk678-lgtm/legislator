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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "llm"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))
from service import LLMConfigError, LLMRequestError, draft  # noqa: E402
from node import LegislativeNode, find_sections  # noqa: E402
from render_bill import Line  # noqa: E402
from bill_title import default_bill_title, strip_law_own_year  # noqa: E402
from explanatory_draft import draft_explanatory_notes  # noqa: E402

_EXPLANATORY_INSTRUCTIONS = (
    "אתה מנסח דברי הסבר להצעת חוק ישראלית, בעברית, בסגנון הנהוג במסמכי "
    "'דברי הסבר' רשמיים לכנסת. כתוב בין 2 ל-5 פסקאות קצרות, כל פסקה "
    "כמה משפטים. השתמש בלשון 'מוצע לקבוע'/'מוצע לתקן'/'מוצע להוסיף' "
    "וכיו\"ב - לשון הצעה ענינית, לא גוף ראשון ולא לשון אישית. אסור "
    "בהחלט להשתמש בלשון פוגענית, מאשימה, פוליטית או שיפוטית כלפי אדם "
    "או גורם כלשהו - רק תיאור עובדתי-ענייני של התיקון ותכליתו. אתה "
    "כותב אך ורק את הטקסט המלווה (דברי ההסבר עצמם) - אסור לך לצטט "
    "מחדש, לשנות, לסכם-כניסוח-חדש או להמציא נוסח סעיפים; הוראות "
    "התיקון המדויקות מובאות לך כרפרנס לצורך הבנת השינוי בלבד, לא "
    "לשכתוב. החזר רק את הפסקאות עצמן, מופרדות בשורה ריקה - בלי כותרת "
    "'דברי הסבר', בלי מספור."
)

_TITLE_INSTRUCTIONS = (
    "אתה מנסח את חלק ה'מהות' בשם הצעת חוק ישראלית, שמופיע בפורמט "
    "הקבוע: \"הצעת חוק <שם החוק> (תיקון – <מהות>), <שנה>\". קיבלת את "
    "שם החוק ואת הוראות התיקון. החזר *רק* את מחרוזת ה'מהות' עצמה - "
    "ניסוח קצר (בדרך כלל 3-8 מילים) שמתאר במדויק מה משתנה. בלי "
    "מירכאות, בלי נקודה בסוף, בלי לחזור על שם החוק, בלי המילה 'תיקון' "
    "(היא כבר בתבנית). דוגמה לפורמט הרצוי בלבד (לא לתוכן): "
    "'הארכת תקופת ההתיישנות' או 'ביטול פטור ממכרז'."
)


def _sections_context(before: LegislativeNode, after: LegislativeNode, touched_numbers: set[str]) -> str:
    """נוסח לפני/אחרי לכל סעיף שנגע בו - לא רק הוראת התיקון המנוסחת,
    גם הנוסח הישיר, כדי שה-LLM יבין את מהות השינוי בלי לנחש מהניסוח
    המשפטי-פורמלי של הוראת התיקון בלבד."""
    before_sections = find_sections(before)
    after_sections = find_sections(after)
    parts = []
    for number in sorted(touched_numbers):
        before_node = before_sections.get(number)
        after_node = after_sections.get(number)
        before_text = before_node.text if before_node else "(סעיף חדש - לא היה קיים)"
        after_text = after_node.text if after_node else "(הוסר)"
        parts.append(f"סעיף {number}:\nלפני: {before_text}\nאחרי: {after_text}")
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
    lines: list[Line], before: LegislativeNode, after: LegislativeNode, touched_numbers: set[str]
) -> list[str]:
    """2-5 פסקאות בסגנון דברי הסבר. נופלת חזרה ל-explanatory_draft.
    draft_explanatory_notes (הדטרמיניסטי) אם ה-LLM לא זמין/נכשל -
    לא זורקת, לעולם מחזירה טיוטה כלשהי (גם אם פחות עשירה)."""
    try:
        content = (
            f"הוראות התיקון שכבר נוסחו:\n{_lines_context(lines)}\n\n"
            f"נוסח הסעיפים לפני/אחרי:\n{_sections_context(before, after, touched_numbers)}"
        )
        text = draft(instructions=_EXPLANATORY_INSTRUCTIONS, content=content, max_tokens=1000)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
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
