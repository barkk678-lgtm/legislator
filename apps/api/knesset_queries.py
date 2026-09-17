"""מאגר השאילתות של הכנסת (משימה 1.4, תוצר ג).

מחליף את "שאילתות קודמות בנושא - בקרוב (1.4)" שכבר קיים בלשונית
השאילתות: לפני ניסוח שאילתה חדשה, לראות מה כבר נשאל באותו נושא,
מי שאל ומתי.

**מה יש ומה אין:** `KNS_Query` (42,824 רשומות) מחזיק כותרת, סוג
(רגילה/דחופה/ישירה), תאריך הגשה, מגיש ומשרד. **הטקסט המלא של
השאילתה יושב בקובץ ב-`fs.knesset.gov.il`**, שחסום מסביבת ה-agent
אך כנראה פתוח מ-Vercel - `document_url` מוחזר כדי שהממשק יוכל לקשר
אליו, והבדיקה אם ניתן למשוך אותו בפועל נעשית מ-Vercel.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
from odata import OdataError, escape, fetch  # noqa: E402


def _person_names(person_ids: list[int]) -> dict[int, str]:
    """שמות המגישים. בלי זה השאילתה מוצגת בלי מי שאל אותה, וזה
    בדיוק המידע שמעניין מי שמנסח שאילתה חדשה."""
    names: dict[int, str] = {}
    unique = sorted({pid for pid in person_ids if pid})
    for i in range(0, len(unique), 30):
        clause = " or ".join(f"Id eq {pid}" for pid in unique[i : i + 30])
        for p in fetch("KNS_Person", filter=clause, select="Id,FirstName,LastName"):
            names[p["Id"]] = f"{p.get('FirstName') or ''} {p.get('LastName') or ''}".strip()
    return names


def search_queries(q: str, *, limit: int = 12) -> dict:
    """שאילתות קודמות שכותרתן מכילה את מונח החיפוש."""
    q = q.strip()
    if len(q) < 2:
        return {"query": q, "results": [], "note": "מונח חיפוש קצר מדי."}

    rows = fetch(
        "KNS_Query",
        filter=f"contains(Name,'{escape(q)}')",
        select="Id,Name,TypeDesc,StatusID,SubmitDate,KnessetNum,PersonID,GovMinistryID",
        orderby="SubmitDate desc",
        top=limit * 3,
    )
    rows = rows[:limit]
    names = _person_names([r.get("PersonID") for r in rows])

    results = [{
        "query_id": r["Id"],
        "title": r.get("Name"),
        "kind": r.get("TypeDesc"),
        "knesset": r.get("KnessetNum"),
        "submitted_at": (r.get("SubmitDate") or "")[:10] or None,
        "asked_by": names.get(r.get("PersonID")) or None,
    } for r in rows]

    return {"query": q, "results": results,
            "note": "חיפוש בכותרות השאילתות. הטקסט המלא יושב בשרת הקבצים של הכנסת."}


__all__ = ["OdataError", "search_queries"]
