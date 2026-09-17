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

# מילים שמופיעות כמעט בכל שם הצעת חוק ולכן לא מעידות על דמיון.
_STOPWORDS = {"חוק", "הצעת", "הצעה", "תיקון", "מס", "מספר", "תיקוני", "חקיקה",
              "הוראת", "שעה", "של", "את", "על", "לתיקון", "התשפ", "התשפב", "התשפג"}

_STATUS_PASSED = 118  # התקבלה בקריאה שלישית


def _words(title: str) -> set[str]:
    cleaned = re.sub(r"[(),\"'׳״\-–]", " ", title)
    return {w for w in cleaned.split() if len(w) > 2 and w not in _STOPWORDS}


def _core_terms(title: str) -> list[str]:
    """שתי המילים הארוכות ביותר שאינן מילות-מילוי - הן שמשמשות
    כמסנן מול הפיד, כי `contains` דורש מחרוזת אחת ולא קבוצה."""
    return sorted(_words(title), key=len, reverse=True)[:2]


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
            select="Id,Name,KnessetNum,SubTypeDesc,StatusID,PrivateNumber,PublicationDate",
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
            "private_number": bill.get("PrivateNumber"),
            "became_law": bill.get("StatusID") == _STATUS_PASSED,
            "published_at": (bill.get("PublicationDate") or "")[:10] or None,
            "similarity": round(score, 3),
            "shared_words": sorted(shared),
        })
    scored.sort(key=lambda r: (-r["similarity"], -(r["knesset"] or 0)))
    return {
        "query": title,
        "terms": terms,
        "results": scored[:limit],
        "total_examined": len(seen),
        "note": "השוואת שמות בלבד - הצעה באותו נושא בשם שונה לא תיתפס כאן.",
    }


__all__ = ["OdataError", "similar_bills"]
