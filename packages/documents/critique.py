"""ביקורת טיוטה: הבדיקות דטרמיניסטיות, ההסבר בשפה מובנת (משימה 2.2).

**הפיצ'ר הזה התגלה, לא תוכנן.** כלי התקציר (summarize.py) הצביע מעצמו
על ליקוי ניסוח בהצעה אמיתית - סעיף שהוכנס שלא במקומו הכרונולוגי -
והממצא הזה היה שווה יותר מהתקציר עצמו. ברק: "זה הופך אותו מכלי קריאה
לכלי ביקורת". ההחלטה שהתקבלה: **לבנות את הביקורת על הוולידטור הקיים,
לא על ה-LLM.**

**חלוקת התפקידים, וזה הגבול של הקובץ הזה:**

- מי שמוצא ליקוי הוא `packages/validate` בלבד - קוד טהור, בלי רשת ובלי
  מודל, שקלט זהה נותן לו פלט זהה. כל ממצא מגיע משם ורק משם.
- מי שמסביר הוא ה-LLM, ו**רק** מסביר: הוא מקבל את רשימת הממצאים
  הסגורה ואת נוסח ההצעה, ומנסח לכל ממצא הסבר בשפה מובנת. הוא לא מוסיף
  ממצאים, לא מוריד ממצאים ולא הופך כשל ל"בסדר".
- אם אין ממצאים - **אין קריאת LLM בכלל**. "עברה את כל הבדיקות" היא
  עובדה שנקבעת בקוד, לא דעה של מודל.

אם ההסבר של המודל לא חוזר תקין (JSON פגום, ממצא לא מוכר), הממצאים
הדטרמיניסטיים עדיין מוחזרים במלואם - עם `explained=False`. ליקוי אמיתי
לא נעלם בגלל שהניסוח שלו נכשל.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

_PKGS = Path(__file__).resolve().parents[1]
for _sub in ("render", "corpus", "validate"):
    sys.path.insert(0, str(_PKGS / _sub))

from render_bill import Bill, Line  # noqa: E402
from validator import DRAFT_CHECKS, Finding, validate_draft  # noqa: E402

_MAX_DEPTH = 5

_INSTRUCTIONS = """אתה מסביר ממצאי בדיקה בהצעת חוק לעוזר פרלמנטרי שאינו מנסח מקצועי.

תקבל רשימה סגורה של ממצאים שנמצאו על ידי בודק אוטומטי, וכן את נוסח
ההצעה. לכל ממצא, ורק לממצאים שברשימה, כתוב הסבר קצר.

החזר JSON בלבד - מערך של אובייקטים, אחד לכל ממצא, בסדר שבו קיבלת אותם:
[{"check": <מספר הבדיקה>, "what": "...", "why": "...", "fix": "..."}]

- "what": מה נמצא, במשפט אחד, בשפה פשוטה. הצבע על המקום המדויק בהצעה.
- "why": למה זה משנה, במשפט אחד.
- "fix": מה לעשות, במשפט אחד. אם התיקון אינו ברור מהמסמך - כתוב מה
  צריך לברר.

כללים מחייבים:
- אל תוסיף ממצאים שאינם ברשימה, ואל תשמיט ממצא שקיבלת.
- אל תרכך ממצא ואל תקבע שהוא בסדר. מי שקבע שזה ליקוי הוא הבודק, לא אתה.
- אל תמציא מספרי סעיפים, שמות חוקים או ציטוטים שאינם בנוסח שקיבלת.
- בלי טקסט מחוץ ל-JSON. בלי הקדמה ובלי סיכום."""


@dataclass
class CritiqueItem:
    check_number: int
    description: str
    severity: str
    status: str
    message: str          # הניסוח הדטרמיניסטי של הוולידטור - תמיד קיים
    what: str = ""        # ההסבר של המודל - ריק אם ההסבר לא נוצר
    why: str = ""
    fix: str = ""


@dataclass
class BillCritique:
    title: str
    items: list[CritiqueItem] = field(default_factory=list)   # ליקויים בלבד
    passed: list[int] = field(default_factory=list)
    not_checked: list[int] = field(default_factory=list)
    checks_run: tuple[int, ...] = DRAFT_CHECKS
    explained: bool = False
    explain_error: str = ""
    extraction_warnings: list[str] = field(default_factory=list)


def as_render_bill(extracted) -> Bill:
    """ExtractedBill -> render_bill.Bill, בשביל הוולידטור בלבד.

    depth נחתך ל-MAX_DEPTH של התבנית: מסמך חיצוני יכול להיות מוזח
    עמוק יותר ממה שהתבנית שלנו מכירה, וזו אינה סיבה להפיל את הבדיקה.
    submitted_date נשאר ריק במכוון - מזכירות הכנסת כותבת אותו, לא
    המנסח (ראו render_bill.Bill ובדיקה 8)."""
    return Bill(
        knesset=extracted.knesset,
        title=extracted.title,
        initiator=extracted.initiator,
        bill_number=extracted.bill_number or "פ/?????????",
        submitted_date="",
        explanatory=list(extracted.explanatory),
        lines=[
            Line(
                text=ln.text,
                depth=min(ln.depth, _MAX_DEPTH),
                side_heading=ln.side_heading,
                number=ln.number,
                marker=ln.marker,
                inner_heading=ln.inner_heading,
                inner_number=ln.inner_number,
            )
            for ln in extracted.lines
        ],
    )


def _findings_as_prompt(findings: list[Finding], bill: Bill) -> str:
    parts = ["--- ממצאי הבודק האוטומטי ---"]
    for f in findings:
        parts.append(f"בדיקה {f.check_number} [{f.status}]: {f.description}\n   {f.message}")
    parts.append("\n--- נוסח ההצעה ---")
    parts.append(f"שם: {bill.title or '(לא זוהה)'}")
    for i, ln in enumerate(bill.lines):
        head = f"[{ln.side_heading}] " if ln.side_heading else ""
        num = f"{ln.number} " if ln.number else ""
        inner = f"[{ln.inner_heading} {ln.inner_number}] " if ln.inner_number else ""
        parts.append(f"שורה {i}: {'  ' * ln.depth}{head}{num}{inner}{ln.marker} {ln.text}".rstrip())
    return "\n".join(parts)


def _parse_explanations(text: str, expected: list[int]) -> dict[int, dict]:
    """JSON -> {מספר בדיקה: הסבר}. מתעלם מכל מפתח שאינו ברשימת הממצאים
    שנשלחה - המודל לא מוסיף ממצאים דרך ההסבר."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").lstrip("json").strip()
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("ההסבר אינו מערך JSON")
    allowed = set(expected)
    out: dict[int, dict] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            number = int(entry.get("check"))
        except (TypeError, ValueError):
            continue
        if number in allowed:
            out[number] = entry
    return out


def critique_bill(extracted, *, draft_fn=None) -> BillCritique:
    """ביקורת על הצעה שחולצה ממסמך. `draft_fn` מוזרק כדי שהשכבה לא
    תהיה כבולה לספק LLM מסוים וכדי שהבדיקות ירוצו בלי רשת."""
    bill = as_render_bill(extracted)
    findings = validate_draft(bill)

    problems = [f for f in findings if f.status in ("נכשל", "אזהרה")]
    critique = BillCritique(
        title=extracted.title,
        items=[
            CritiqueItem(f.check_number, f.description, f.severity, f.status, f.message)
            for f in problems
        ],
        passed=[f.check_number for f in findings if f.status == "עבר"],
        not_checked=[f.check_number for f in findings if f.status == "לא נבדק"],
        extraction_warnings=list(extracted.warnings),
    )
    if not problems:
        return critique  # אין ליקוי - אין למה לקרוא למודל

    if draft_fn is None:
        sys.path.insert(0, str(_PKGS / "llm"))
        from service import draft as draft_fn  # noqa: PLC0415

    try:
        raw = draft_fn(
            instructions=_INSTRUCTIONS,
            content=_findings_as_prompt(problems, bill),
            max_tokens=1200,
        )
        explanations = _parse_explanations(raw, [f.check_number for f in problems])
    except Exception as exc:  # noqa: BLE001 - ראו ה-docstring: הממצאים שורדים
        critique.explain_error = f"{type(exc).__name__}: {exc}"
        return critique

    for item in critique.items:
        entry = explanations.get(item.check_number)
        if entry:
            item.what = str(entry.get("what", "")).strip()
            item.why = str(entry.get("why", "")).strip()
            item.fix = str(entry.get("fix", "")).strip()
    critique.explained = any(item.what for item in critique.items)
    if not critique.explained:
        critique.explain_error = "המודל לא החזיר הסבר לאף ממצא"
    return critique


__all__ = ["BillCritique", "CritiqueItem", "as_render_bill", "critique_bill"]
