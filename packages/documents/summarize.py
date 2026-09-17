"""תקציר הצעת חוק (משימה 2.1, המוצר הראשון).

**גבול השכבה:** הקובץ הזה בונה את *הקלט* ל-LLM מתוך `ExtractedBill`
ומחזיר טקסט. הוא אינו יודע דבר על HTTP, על הממשק או על מקור המסמך -
בדיוק כמו `extract_docx`. מי שקורא לו מחליט מה לעשות עם התוצאה.

**למה התקציר הוא המוצר הראשון:** הוא צריך רק את שלב החילוץ, ולכן
הוא מוכיח שהתשתית עובדת על מסמכים אמיתיים לפני שמשקיעים בזיהוי
מבנה ובהמרה ל-LegislativeNode.

**התקציר נשען על הנוסח, לא על דברי ההסבר.** דברי ההסבר הם טיעון
פוליטי של המגיש; הנוסח הוא מה שההצעה באמת עושה. שניהם נמסרים
ל-LLM, אבל ההנחיה מפרידה ביניהם במפורש.
"""

from __future__ import annotations

from dataclasses import dataclass

_INSTRUCTIONS = """אתה מסכם הצעות חוק עבור עוזר פרלמנטרי.

כתוב תקציר קצר בעברית, בשלושה חלקים ובכותרות האלה בדיוק:

**מה ההצעה עושה**
שתיים עד ארבע שורות, מתוך *נוסח ההצעה* בלבד - אילו חוקים היא מתקנת
ומה היא משנה בפועל. אל תסתמך כאן על דברי ההסבר.

**הנימוק של המגיש**
שורה עד שתיים, מתוך דברי ההסבר. נסח כטענה של המגיש ("לדברי המגיש...")
ולא כעובדה.

**על מה לשים לב**
שורה עד שתיים: מה לא ברור מהמסמך, או מה שכדאי לבדוק לפני דיון.
אם אין דבר כזה - כתוב "אין הערות מיוחדות".

כללים:
- אל תמציא מספרי סעיפים, שמות חוקים או תאריכים שאינם בטקסט.
- אם הנוסח ריק או חלקי, אמור זאת במפורש במקום לנחש.
- בלי הקדמות ובלי סיכום בסוף. רק שלושת החלקים."""


@dataclass
class BillSummary:
    text: str
    title: str
    initiators: list[str]
    lines_used: int
    explanatory_used: int
    warnings: list[str]


def _bill_as_prompt(bill) -> str:
    parts = [f"שם ההצעה: {bill.title or '(לא זוהה)'}"]
    if bill.initiators:
        parts.append("מגישים: " + ", ".join(bill.initiators))
    if bill.knesset:
        parts.append(bill.knesset)

    parts.append("\n--- נוסח ההצעה ---")
    if bill.lines:
        for ln in bill.lines:
            prefix = ""
            if ln.number:
                prefix = f"[{ln.side_heading}] {ln.number} " if ln.side_heading else f"{ln.number} "
            elif ln.inner_number:
                prefix = f"[{ln.inner_heading}] {ln.inner_number} "
            indent = "  " * ln.depth
            marker = f"{ln.marker} " if ln.marker else ""
            parts.append(f"{indent}{prefix}{marker}{ln.text}")
    else:
        parts.append("(לא חולץ נוסח מהמסמך)")

    parts.append("\n--- דברי הסבר ---")
    parts.extend(bill.explanatory or ["(אין דברי הסבר במסמך)"])
    return "\n".join(parts)


def summarize_bill(bill, *, draft_fn=None) -> BillSummary:
    """תקציר מ-`ExtractedBill`. `draft_fn` מוזרק כדי שהשכבה לא
    תהיה כבולה לספק LLM מסוים - וכדי שהבדיקות ירוצו בלי רשת."""
    if draft_fn is None:
        import sys  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llm"))
        from service import draft as draft_fn  # noqa: PLC0415

    text = draft_fn(instructions=_INSTRUCTIONS, content=_bill_as_prompt(bill), max_tokens=900)
    return BillSummary(
        text=text.strip(),
        title=bill.title,
        initiators=list(bill.initiators),
        lines_used=len(bill.lines),
        explanatory_used=len(bill.explanatory),
        warnings=list(bill.warnings),
    )


__all__ = ["BillSummary", "summarize_bill"]
