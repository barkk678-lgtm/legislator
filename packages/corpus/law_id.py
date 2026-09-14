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

**סדר קדימות מחייב (ברק, 2026-09-14, אחרי שגילה 4 חוקים עם גם
KNS_Bill.Id וגם התאמת שם מדויקת ב-KNS_IsraelLaw):** IsraelLaw קודם,
Bill רק נפילה-אחורה כשאין רשומת IsraelLaw, מיפוי ידני אחרון.
"bill- הוא נפילה אחורה כשאין רשומת IsraelLaw מבנית, כי כל תוכן
החוק תיקון לחוקים אחרים - לא בחירה מקבילה." **הבדיקה חייבת להתעלם
מאיזו תבנית מופיעה בוויקיטקסט** (`{{ח:מאגר}}` מול `{{ח:מאגר2}}`) -
תמיד לבדוק קודם התאמה ל-KNS_IsraelLaw (לפי מספר *וגם* לפי שם), ורק
אם שתיהן נכשלות לעבור ל-Bill. שימוש ב-`{{ח:מאגר2}}` כשל למרות
שהחוק *כן* קיים ב-KNS_IsraelLaw הוא בחירת עריכה של מתנדב בוויקיטקסט,
לא עובדה על מבנה החוק - ולכן לא קובע. ראו resolve_law_id למטה, וגם
מראי מקום (TASKS.md משימה 8): חוק שיש לו IsraelLaw.Id ימצא בחיפוש
הרגיל שם; חוק שמקבל bill- בטעות (כשהיה לו גם IsraelLaw.Id) ייחשב
חריג בטעות בכל מקום שמניח שרק ל-bill- יש את זה.
"""

from typing import Literal

from knesset_odata import find_israel_law_id
from manual_law_ids import get_manual_slug

LawIdSource = Literal["israel_law", "bill", "manual"]

_PREFIXES: dict[LawIdSource, str] = {
    "israel_law": "law",
    "bill": "bill",
    "manual": "manual",
}


class LawIdResolutionError(Exception):
    """אין law_id לחוק - לא נמצא ב-KNS_IsraelLaw (לא לפי מספר ולא
    לפי שם), אין ח:מאגר2 תקף, ואין רשומה במיפוי הידני. נכשל ברעש
    בכוונה - אין fallback אוטומטי (ברק, 2026-09-14)."""


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


def resolve_law_id(
    *,
    wikitext_title: str,
    magar1: str | None,
    magar2: str | None,
    kns_records: list[dict],
) -> str:
    """קובעת את ה-law_id הסופי לחוק אחד, לפי סדר הקדימות המחייב
    שמתואר למעלה - IsraelLaw, אז Bill, אז מיפוי ידני, אחרת חריגה.
    היחידה שקוראת ל-build_law_id בפועל - כל שאר הקוד קורא לה, לא
    ל-build_law_id ישירות (חוץ מטסטים).

    wikitext_title: הכותרת כפי שמופיעה בוויקיטקסט (לשימוש בחיפוש שם).
    magar1/magar2: המספרים הגולמיים מ-{{ח:מאגר}}/{{ח:מאגר2}} בוויקיטקסט
    (או None אם התבנית לא נמצאה) - ראו wikitext_parser/tools/
    load_corpus.py לחילוץ. kns_records: כל רשומות KNS_IsraelLaw
    (מ-knesset_odata.fetch_israel_laws)."""
    israel_law_ids = {r["Id"] for r in kns_records}

    israel_id: int | None = None
    if magar1 is not None and int(magar1) in israel_law_ids:
        israel_id = int(magar1)
    if israel_id is None:
        israel_id = find_israel_law_id(wikitext_title, kns_records)
    if israel_id is not None:
        return build_law_id("israel_law", israel_id)

    if magar2 is not None:
        return build_law_id("bill", magar2)

    slug = get_manual_slug(wikitext_title)
    if slug is not None:
        return build_law_id("manual", slug)

    raise LawIdResolutionError(
        f"אין law_id לחוק {wikitext_title!r}: לא נמצא ב-KNS_IsraelLaw "
        "(לא לפי מספר ולא לפי שם), אין ח:מאגר2, ואין רשומה במיפוי "
        "הידני (manual_law_ids.MANUAL_LAW_IDS). הוסף רשומה למיפוי "
        "לפני טעינה - אין נפילה-אחורה אוטומטית."
    )
