"""מאגר השאילתות של הכנסת (משימה 1.4, תוצר ג).

מחליף את "שאילתות קודמות בנושא - בקרוב (1.4)" שכבר קיים בלשונית
השאילתות: לפני ניסוח שאילתה חדשה, לראות מה כבר נשאל באותו נושא,
מי שאל ומתי.

**מה יש ומה אין:** `KNS_Query` (42,824 רשומות) מחזיק כותרת, סוג
(רגילה/דחופה/ישירה), תאריך הגשה, מגיש ומשרד. הטקסט המלא יושב
כקובץ Word ב-`fs.knesset.gov.il` - **נבדק ואומת שהוא נגיש מ-Vercel**
(200, application/msword), אף שהוא חסום מסביבת ה-agent.

**מחזירים קישור ולא מושכים את הקובץ** (החלטת ברק): המשתמש פותח
בעצמו. משיכה ופרסור של קובצי doc לכל חיפוש הייתה מאטה את החיפוש
עצמו בלי שביקשו זאת.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
from odata import OdataError, escape, fetch, fetch_raw_array  # noqa: E402


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


def _document_links(query_ids: list[int]) -> dict[int, str]:
    """קישור לקובץ המקורי של כל שאילתה. `KNS_DocumentQuery` מחזיר
    מערך חשוף עם מפתחות camelCase (ראו odata.fetch_raw_array), ולכן
    לא עובר דרך fetch הרגילה."""
    links: dict[int, str] = {}
    ids = [qid for qid in query_ids if qid]
    if not ids:
        return links
    for i in range(0, len(ids), 50):
        clause = "QueryID in (" + ",".join(str(q) for q in ids[i : i + 50]) + ")"
        try:
            for row in fetch_raw_array("KNS_DocumentQuery", filter=clause):
                qid, path = row.get("queryID"), row.get("filePath")
                if qid and path:
                    links.setdefault(qid, path)
        except OdataError:
            return links  # הקישור הוא תוספת, לא תנאי - חיפוש שעובד חשוב יותר
    return links


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

    docs = _document_links([r["Id"] for r in rows])
    results = [{
        "query_id": r["Id"],
        "document_url": docs.get(r["Id"]),
        "title": r.get("Name"),
        "kind": r.get("TypeDesc"),
        "knesset": r.get("KnessetNum"),
        "submitted_at": (r.get("SubmitDate") or "")[:10] or None,
        "asked_by": names.get(r.get("PersonID")) or None,
    } for r in rows]

    return {"query": q, "results": results,
            "note": "חיפוש בכותרות השאילתות. הטקסט המלא יושב בשרת הקבצים של הכנסת."}


__all__ = ["OdataError", "search_queries"]
