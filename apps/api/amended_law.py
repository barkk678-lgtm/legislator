"""איתור החוק שהצעה שהועלתה מתקנת, ושליפת מספרי הסעיפים שלו -
המקור לבדיקה 1 על מסמך חיצוני (ברק, 23.9.2026).

**למה כאן ולא ב-packages/validate:** הוולידטור טהור - בלי רשת ובלי
מאגר. הוא מקבל את מספרי הסעיפים כנתון (`validate_draft(law_sections=)`)
ואינו יודע מאין הם. הגישה למאגר היא תפקיד שכבת ה-API, בדיוק כמו
בכל שאר הכלים.

**ההתאמה שמרנית בכוונה.** רק התאמה מדויקת אחרי נורמליזציה, או
התאמת-קידומת **יחידה**, מתקבלת. חוק דומה-בשמו הוא התאמה שגויה
שנראית בטוחה - והיא תייצר רשימת "סעיפים חסרים" שכולה שגיאת שווא.
עדיף "לא נבדק" עם סיבה (CLAUDE.md: "לא נמצא" מול "לא הצלחתי לבדוק").
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKGS = Path(__file__).resolve().parents[2] / "packages"
for _sub in ("corpus", "validate"):
    sys.path.insert(0, str(_PKGS / _sub))

from cited_sections import main_law_citations  # noqa: E402
from law_search import normalize_for_search  # noqa: E402
from node import find_sections  # noqa: E402

import law_registry  # noqa: E402


def _match(name: str) -> dict | None:
    hits = law_registry.search_law_titles(name, limit=5)
    target = normalize_for_search(name)
    exact = [h for h in hits if normalize_for_search(h["title"]) == target]
    if exact:
        return exact[0]
    prefix = [h for h in hits if normalize_for_search(h["title"]).startswith(target)]
    return prefix[0] if len(prefix) == 1 else None


def sections_for_bill(bill) -> tuple[set[str] | None, str]:
    """(מספרי הסעיפים של החוק המתוקן, סיבה אם לא נמצא).

    מוחזר כפי שהוא ל-`validate_draft(law_sections=..., law_note=...)`.
    None אינו שגיאה - הוא מצב לגיטימי ושכיח (חוק שאינו בקורפוס,
    או הצעה שמפנה ל"החוק העיקרי" בלי לחזור על שמו)."""
    name, _ = main_law_citations(bill)
    if not name:
        return None, (
            "ההצעה אינה נוקבת בשם החוק שהיא מתקנת (היא מפנה אליו כ\"החוק "
            "העיקרי\" בלבד), ולכן לא ניתן לאתר אותו במאגר ולוודא מולו את "
            "מספרי הסעיפים."
        )
    law = _match(name)
    if law is None:
        return None, (
            f"\"{name}\" אינו נמצא במאגר החוקים של המערכת, ולכן מספרי "
            "הסעיפים שההצעה מפנה אליהם לא אומתו מול נוסח החוק."
        )
    try:
        root = law_registry.load_law(law["id"])
    except Exception as exc:  # noqa: BLE001 - כישלון טעינה אינו "עבר"
        return None, (
            f"\"{name}\" נמצא במאגר אך טעינת נוסחו נכשלה "
            f"({type(exc).__name__}), ולכן מספרי הסעיפים לא אומתו."
        )
    return set(find_sections(root)), ""


__all__ = ["sections_for_bill"]
