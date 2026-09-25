"""בדיקת הצעות חוק זהות או דומות (משימה 1.4, תוצר ב).

**למה זה קיים:** החוברת הסגולה מחייבת לבדוק אם כבר מונחת הצעה זהה
או דומה לפני הנחת הצעה חדשה. היום עוזר פרלמנטרי עושה את זה ידנית.

**איך:** `contains` על שם ההצעה ב-`KNS_Bill` (נבדק - עובד, 47
התאמות ל"תובענות"), ואז דירוג לפי חפיפת מילים בין השם שהוקלד לשם
ההצעה הקיימת. הדירוג מקומי בכוונה: הפיד לא מדרג רלוונטיות, והוצאת
כל ההתאמות ומיונן אצלנו נותנת שליטה מלאה בהסבר ("למה זה דומה").

**מה זה לא:** זו בדיקת *שמות*, לא בדיקת תוכן. שתי הצעות יכולות
לטפל באותו נושא בשמות שונים לגמרי, וזה לא ייתפס כאן. הממשק אומר
את זה במפורש - כלי עזר לעוזר הפרלמנטרי, לא תחליף לשיקול דעתו.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
from odata import OdataError, escape, fetch  # noqa: E402
from dates import display_date  # noqa: E402

# מילים שמופיעות כמעט בכל שם הצעת חוק ולכן לא מעידות על דמיון.
_STOPWORDS = {"חוק", "הצעת", "הצעה", "תיקון", "מס", "מספר", "תיקוני", "חקיקה",
              "הוראת", "שעה", "של", "את", "על", "לתיקון", "התשפ", "התשפב", "התשפג"}

_STATUS_PASSED = 118  # התקבלה בקריאה שלישית
_ID_CHUNK = 150  # מזהים ב-`in (...)` אחד - 200 עובר בפיד, 400 נשבר


# שנה לועזית (1990, 2026) ושנה עברית על כל הטיותיה. **שתיהן
# משתנות בין הצעה להצעה ואינן אומרות דבר על הנושא**, ולכן אינן
# משתתפות בהשוואה.
#
# נמדד (22.9): בלי הסינון הזה שתי הצעות **זהות לחלוטין** משנים
# שונות קיבלו ז'קארד 0.600 במקום 1.000 - קנס של 40% מהשנה בלבד.
# המשמעות המעשית: הצעה זהה מכנסת קודמת עלולה לרדת מתחת לסף
# ולא להופיע כלל, וזו בדיוק הבדיקה שהחוברת הסגולה מחייבת.
#
# מספר התיקון ("תיקון מס' 12") כבר היה מנוטרל: "תיקון" ו"מס"
# ברשימת מילות המילוי, והספרות נופלות בסינון האורך.
_YEAR_RE = re.compile(r"^(?:1[89]\d{2}|20\d{2}|הת[א-ת]{1,4})$")


def _words(title: str) -> set[str]:
    cleaned = re.sub(r"[(),\"'׳״\-–]", " ", title)
    return {
        w for w in cleaned.split()
        if len(w) > 2 and w not in _STOPWORDS and not _YEAR_RE.match(w)
    }


def _core_terms(title: str) -> list[str]:
    """שתי המילים הארוכות ביותר שאינן מילות-מילוי - הן שמשמשות
    כמסנן מול הפיד, כי `contains` דורש מחרוזת אחת ולא קבוצה."""
    return sorted(_words(title), key=len, reverse=True)[:2]




# המזהה שעוזר פרלמנטרי משתמש בו. **מורכב, לא שדה בפיד:**
# ב-KNS_Bill יש `PrivateNumber` (מספר עירום: 6803) ו-`KnessetNum`,
# והתווית המלאה מורכבת מהם. אומת מול הצעה 2244611, שבקובץ ה-docx
# שלה כתוב במפורש "פ/6803/25" - ובפיד PrivateNumber=6803,
# KnessetNum=25.
#
# **הצעה ממשלתית אין לה PrivateNumber בכלל** (נמדד: 106 הצעות
# ממשלתיות בכנסת ה-25, אפס עם PrivateNumber) - שם המספר יושב
# בשדה `Number` והקידומת היא מ'. הצעת ועדה - כ'.
_BILL_PREFIX = {"פרטית": "פ", "ממשלתית": "מ", "ועדה": "כ"}


def bill_label(bill: dict) -> str | None:
    """המזהה בצורה שמזהים בה הצעה בכנסת: `פ/6803/25`.

    מחזירה None כשאין מספיק נתונים - **ולא מזהה פנימי במקום**:
    מזהה פנימי אינו אומר דבר לעוזר פרלמנטרי, והצגתו כאילו הוא
    המזהה המוכר היא הטעיה."""
    prefix = _BILL_PREFIX.get(bill.get("SubTypeDesc") or "")
    knesset = bill.get("KnessetNum")
    serial = bill.get("PrivateNumber") or bill.get("Number")
    if not prefix or not serial:
        return None
    return f"{prefix}/{serial}/{knesset}" if knesset else f"{prefix}/{serial}"


def _attach_initiators(bills: list[dict]) -> None:
    """מוסיפה `initiators` לכל הצעה, במקום.

    **שתי קריאות בסך הכול, לא אחת לכל הצעה:** הראשונה מביאה את כל
    שיוכי-היוזמים של ההצעות שכבר נבחרו, והשנייה את שמות האנשים.

    **`in (...)` ולא שרשרת `or`** (132, 26.9.2026): הפיד דוחה שרשרת `or`
    ארוכה (מגבלת מורכבות). ב-knesset_citations נמדד ש-25 נדחים; כאן נדחו
    עד 24 שמות - המגבלה נמוכה מ-25, ואין לסמוך על שום אורך של `or`. השמות נשלפו
    במנות של 40 `Id eq X or ...`, ועשר הצעות פרטיות עם הרבה חותמים עברו
    את המגבלה - כל עשר התוצאות הוצגו "לא הצלחתי לבדוק את היוזמים". שוחזר
    באתר החי ("הגנת הצרכן (תיקון – עסקה ברוכלות)": 10/10, שלוש פעמים).
    `in` עובר עם 200 מזהים (knesset_citations), וסוגר אחד בלבד - הרחק
    מחומת האש (4 סוגריים ומעלה, ש2).

    **כישלון כאן אינו מפיל את התוצאה.** שמות היוזמים הם תוספת נוחות;
    אם הפיד לא החזיר אותם, ההצעות הדומות עדיין מוצגות עם כל השאר.
    """
    if not bills:
        return
    for bill in bills:
        # **שני מצבים שונים, ולכן שני שדות.** `initiators=[]` עם
        # `initiators_unavailable=False` פירושו "נבדק, אין יוזמים
        # רשומים" (הצעה ממשלתית). `initiators_unavailable=True`
        # פירושו "לא הצלחתי לבדוק". עד לתיקון הזה שניהם הופיעו
        # כרשימה ריקה, וכשל 400 מהפיד נראה בממשק כ"אין יוזמים".
        bill["initiators"] = []
        bill["initiators_unavailable"] = False
    try:
        ids = [b["bill_id"] for b in bills if b.get("bill_id")]
        if not ids:
            return
        clause = "BillID in (" + ",".join(str(int(i)) for i in ids) + ")"
        links = fetch("KNS_BillInitiator", filter=f"{clause} and IsInitiator eq true",
                      select="BillID,PersonID,Ordinal", top=500)
        if not links:
            return
        person_ids = sorted({row["PersonID"] for row in links if row.get("PersonID")})
        people: dict[int, str] = {}
        # מנות של 150, כמו ב-knesset_citations (200 עובר, 400 נשבר).
        for start in range(0, len(person_ids), _ID_CHUNK):
            chunk = person_ids[start:start + _ID_CHUNK]
            # **המפתח ב-KNS_Person הוא `Id`, לא `PersonID`** - זה
            # השם ב-KNS_BillInitiator בלבד. `$select=PersonID` על
            # KNS_Person מחזיר 400, והשגיאה נבלעה ב-except שלמטה
            # והתבטאה כ"אין יוזמים" בלי שום סימן. אומת מול הפיד.
            person_clause = "Id in (" + ",".join(str(int(p)) for p in chunk) + ")"
            for row in fetch("KNS_Person", filter=person_clause,
                             select="Id,FirstName,LastName", top=_ID_CHUNK):
                name = f"{row.get('FirstName') or ''} {row.get('LastName') or ''}".strip()
                if name:
                    people[row["Id"]] = name
        by_bill: dict[int, list[tuple[int, str]]] = {}
        for row in links:
            name = people.get(row.get("PersonID"))
            if name:
                by_bill.setdefault(row["BillID"], []).append((row.get("Ordinal") or 0, name))
        for bill in bills:
            ordered = sorted(by_bill.get(bill["bill_id"], []))
            bill["initiators"] = [name for _, name in ordered]
    except OdataError:
        for bill in bills:
            bill["initiators_unavailable"] = True
        return  # התוצאה עדיין מוצגת - אבל **מסומנת** כלא-נבדקה


def similar_bills(title: str, *, knesset_num: int | None = None, limit: int = 10) -> dict:
    """הצעות קיימות שדומות בשמן לכותרת שהוקלדה."""
    title = title.strip()
    if len(title) < 4:
        return {"query": title, "terms": [], "results": [], "note": "כותרת קצרה מכדי לחפש."}

    terms = _core_terms(title)
    if not terms:
        return {"query": title, "terms": [], "results": [],
                "note": "לא נמצאו מילות תוכן בכותרת (רק מילים כלליות כמו \"חוק\"/\"תיקון\")."}

    seen: dict[int, dict] = {}
    for term in terms:
        clause = f"contains(Name,'{escape(term)}')"
        if knesset_num:
            clause += f" and KnessetNum eq {knesset_num}"
        for bill in fetch(
            "KNS_Bill", filter=clause,
            select="Id,Name,KnessetNum,SubTypeDesc,StatusID,PrivateNumber,Number,PublicationDate",
            top=200,
        ):
            seen.setdefault(bill["Id"], bill)

    wanted = _words(title)
    scored = []
    for bill in seen.values():
        other = _words(bill.get("Name") or "")
        if not other:
            continue
        shared = wanted & other
        # ז'קארד: חפיפה יחסית לאיחוד, כך ששם ארוך לא מקבל יתרון מלאכותי
        score = len(shared) / len(wanted | other)
        if not shared:
            continue
        scored.append({
            "bill_id": bill["Id"],
            "title": bill.get("Name"),
            "knesset": bill.get("KnessetNum"),
            "kind": bill.get("SubTypeDesc"),
            "bill_label": bill_label(bill),
            "became_law": bill.get("StatusID") == _STATUS_PASSED,
            "published_at": display_date(bill.get("PublicationDate")),
            "similarity": round(score, 3),
            "shared_words": sorted(shared),
        })
    scored.sort(key=lambda r: (-r["similarity"], -(r["knesset"] or 0)))
    scored = scored[:limit]
    _attach_initiators(scored)
    return {
        "query": title,
        "terms": terms,
        "results": scored,
        "total_examined": len(seen),
        "note": "השוואת שמות בלבד - הצעה באותו נושא בשם שונה לא תיתפס כאן.",
    }


__all__ = ["OdataError", "similar_bills"]
