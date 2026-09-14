"""בניית law_id יציב - פונקציה יחידה, נקודת אכיפה אחת (ברק, 2026-09-14):
"התחילית חייבת להיאכף בקוד, לא במוסכמה. פונקציה אחת שבונה law_id,
ושום מקום אחר לא מרכיב אותו ידנית." שום קוד אחר בפרויקט אמור להרכיב
מחרוזת law_id בעצמו - תמיד דרך build_law_id כאן.

שלושה מקורות אפשריים, תחילית שונה לכל אחד - כדי שהמקור יהיה קריא
מתוך המזהה עצמו, לא רק מתיעוד חיצוני (ברק: "מזהה שאומר מאיזה מרחב
הוא בא חוסך חקירה בכל פעם שמשהו לא מסתדר"):

- **law-<KNS_IsraelLaw.Id>** - חוק עצמאי, מ-{{ח:מאגר|...}} בוויקיטקסט.
  אומת בפועל: מספר קייטנות בוויקיטקסט ("2000516") זהה בדיוק ל-Id
  שלה ב-KNS_IsraelLaw.
- **bill-<KNS_Bill.Id>** - חוק שכל תוכנו תיקון לחוקים אחרים (למשל
  "תיקוני חקיקה" לחוק אוויר נקי + חוק החומרים המסוכנים) ולכן אין
  לו רשומת IsraelLaw עצמאית משלו - מ-{{ח:מאגר2|...}}. אומת בפועל:
  15 מקרים בקורפוס, כל ה-15 תואמים במדויק KNS_Bill.Id עם
  StatusID=118 ו-PublicationSeriesDesc="ספר החוקים" (כלומר: הצעה
  שהתקבלה ופורסמה כחוק, לא הצעה שנפלה). ראו TASKS.md משימה 7 /
  docs/data-sources.md - הממצא נוגע ישירות למראי מקום (משימה 8):
  חוק כזה לא יימצא בחיפוש רגיל מול KNS_IsraelLaw.
- **manual-<slug>** - חוק בלי שום מספר כנסתי כלל: קדם למדינה/לכנסת
  (עות'מאני/מנדטורי), לא פורסם ברשומות (סטטוט קהילתי-דתי), או נעדר
  בפועל גם מ-KNS_IsraelLaw וגם מ-KNS_Bill. ה-slug נבחר ואושר ידנית
  אחד-אחד - **אסור פונקציית תעתיק אוטומטית** (ברק: "זו בדיוק הפונקציה
  שתיתן תוצאות שגויות בשקט על עברית"). ראו manual_law_ids.py.

עקביות מכוונת, בלי יוצא מן הכלל: **כל law_id בקורפוס נושא תחילית**
(ברק, 2026-09-14): "מזהה שחלקו מספר גולמי וחלקו לא הוא בדיוק חוסר
העקביות שמייצר באגים - מישהו יכתוב קוד שמניח ש-law_id הוא מספר,
והוא יעבוד על 96% מהמקרים." קוד שמניח שכל law_id הוא מחרוזת עם
תחילית-מקור (ולא, למשל, ינסה int(law_id)) יעבוד תמיד, לא רק ברוב
המקרים.
"""

from typing import Literal

LawIdSource = Literal["israel_law", "bill", "manual"]

_PREFIXES: dict[LawIdSource, str] = {
    "israel_law": "law",
    "bill": "bill",
    "manual": "manual",
}


def build_law_id(source: LawIdSource, identifier: str) -> str:
    """נקודת האכיפה היחידה לבניית law_id - ראו docstring המודול.

    identifier: מספר ה-Id הגולמי (כמחרוזת/int, KNS_IsraelLaw.Id או
    KNS_Bill.Id) עבור source="israel_law"/"bill"; ה-slug הידני (בלי
    תחילית, ראו manual_law_ids.MANUAL_LAW_IDS) עבור source="manual"."""
    if source not in _PREFIXES:
        raise ValueError(f"מקור law_id לא מוכר: {source!r} (חייב israel_law/bill/manual)")
    identifier = str(identifier).strip()
    if not identifier:
        raise ValueError("identifier ריק - אי אפשר לבנות law_id")
    return f"{_PREFIXES[source]}-{identifier}"
