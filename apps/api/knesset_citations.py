"""מראי מקום לחוק מתוך OData של הכנסת (משימה 1.4, תוצר א).

**הצירוף שפותח את זה:** `KNS_LawBinding` מקשר בין החוק שלנו
(`IsraelLawID` = ה-law_id בקורפוס) לבין ההצעה שחוקקה או תיקנה אותו
(`LawID`), ו-`KNS_Bill` מחזיק את פרטי הפרסום עצמם - סדרה, מספר
חוברת, עמוד ותאריך. ביחד הם נותנים "ס\"ח מס' 2054, עמ' 264" מלא,
לחוק המקורי ולכל תיקון.

**לא נשענים על KNS_IsraelLaw כמקור יחיד** (הוא מפגר על חוקים חדשים,
ו-15 חוקים שכל תוכנם תיקון לא מקבלים בו רשומה לעולם - ראו
docs/data-sources.md). כאן בכלל לא נדרשת רשומת IsraelLaw: מספיק
ש-`IsraelLawID` מופיע ב-LawBinding. כשאין - מחזירים תשובה מפורשת
("אין רשומה במאגר הכנסת") ולא רשימה ריקה שנראית כמו תקלה.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
from odata import OdataError, fetch  # noqa: E402

_BILL_FIELDS = "Id,Name,PublicationSeriesDesc,MagazineNumber,PageNumber,PublicationDate"
_BILL_ID_CHUNK = 150  # 200 עובר, 400 נשבר - 150 משאיר מרווח


def _israel_law_id(law_id: str) -> int | None:
    """law_id בקורפוס הוא "law-2000613"; ב-OData זה 2000613. חוקים
    עם קידומת "bill-" הם מרחב מזהים אחר לגמרי (KNS_Bill) ואין להם
    IsraelLawID - ראו docs/data-sources.md."""
    if not law_id.startswith("law-"):
        return None
    suffix = law_id[len("law-"):]
    return int(suffix) if suffix.isdigit() else None


def _format_reference(bill: dict, page_number: int | None) -> str:
    """מראה מקום בפורמט המקובל. העמוד מגיע מה-binding (העמוד שבו
    מופיע התיקון הזה) ולא מה-Bill (שם מתחיל החוק המתקן כולו) -
    ההבדל הזה נצפה בפועל."""
    series = bill.get("PublicationSeriesDesc") or "פרסום"
    parts = [series]
    if bill.get("MagazineNumber"):
        parts.append(f"מס' {bill['MagazineNumber']}")
    page = page_number if page_number is not None else bill.get("PageNumber")
    if page:
        parts.append(f"עמ' {page}")
    return ", ".join(parts)


def citations_for_law(law_id: str) -> dict:
    """שרשרת הפרסומים של חוק: המקורי וכל תיקוניו.

    מחזירה גם `in_knesset_db` - ההבחנה בין "אין תיקונים" לבין "החוק
    הזה לא קיים במאגר הכנסת", בדיוק כמו הבחנת הכיסוי בחיפוש הסמנטי."""
    israel_law_id = _israel_law_id(law_id)
    if israel_law_id is None:
        note = (
            "חוק שכל תוכנו תיקון לחוקים אחרים - אין לו רשומת חוק עצמאית "
            "במאגר הכנסת, ולכן אין לו מראי מקום משלו."
            if law_id.startswith("bill-")
            else "למזהה הזה אין מקבילה במאגר הכנסת (למשל תקנון הכנסת, "
                 "שאינו חוק, או חוק לדוגמה לבדיקות)."
        )
        return {"law_id": law_id, "in_knesset_db": False, "citations": [], "note": note}

    bindings = fetch(
        "KNS_LawBinding",
        filter=f"IsraelLawID eq {israel_law_id}",
        select="Id,LawID,BindingType,BindingTypeDesc,PageNumber,AmendmentTypeDesc,CorrectionNumber",
    )
    if not bindings:
        return {
            "law_id": law_id, "in_knesset_db": False, "citations": [],
            "note": "לא נמצאה רשומה במאגר הכנסת לחוק הזה.",
        }

    bill_ids = sorted({b["LawID"] for b in bindings if b.get("LawID")})
    bills: dict[int, dict] = {}
    # **`in (...)` ולא שרשרת `or`:** נמדד מול השרת - 25 תנאי `or`
    # מוחזרים כ-400 (מגבלת מורכבות על עץ הביטוי), בעוד `in` עובר
    # בנוחות עם 200 מזהים ונשבר רק סביב 400. חוק מתוקן כמו העונשין
    # (169 קישורים) היה נכשל לגמרי בגרסת ה-or.
    for i in range(0, len(bill_ids), _BILL_ID_CHUNK):
        chunk = bill_ids[i : i + _BILL_ID_CHUNK]
        clause = "Id in (" + ",".join(str(bid) for bid in chunk) + ")"
        for bill in fetch("KNS_Bill", filter=clause, select=_BILL_FIELDS):
            bills[bill["Id"]] = bill

    citations = []
    for b in bindings:
        bill = bills.get(b.get("LawID"))
        if not bill:
            continue  # binding שמצביע להצעה שאינה ב-KNS_Bill - מדווח בכיסוי, לא ממציאים
        citations.append({
            "bill_id": bill["Id"],
            "title": bill.get("Name"),
            "kind": b.get("BindingTypeDesc"),
            "is_original": b.get("BindingTypeDesc") == "החוק המקורי",
            "amendment_kind": b.get("AmendmentTypeDesc"),
            "correction_number": b.get("CorrectionNumber"),
            "published_at": (bill.get("PublicationDate") or "")[:10],
            "reference": _format_reference(bill, b.get("PageNumber")),
        })
    citations.sort(key=lambda c: (not c["is_original"], c["published_at"]))

    return {
        "law_id": law_id,
        "in_knesset_db": True,
        "citations": citations,
        "bindings_total": len(bindings),
        "bindings_unresolved": len(bindings) - len(citations),
    }


__all__ = ["OdataError", "citations_for_law"]
