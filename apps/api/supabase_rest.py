"""עימוד לכל קריאת קריאה ל-PostgREST - מקור יחיד.

**למה זה מודול נפרד ולא עוד פונקציה מקומית:** מגבלת 1,000 השורות של
PostgREST (`db-max-rows`) הכתה כאן פעמיים, ובשני המקרים **בשקט** -
התשובה חוקית, הקוד לא נופל, פשוט חסרות שורות:

1. חוק העונשין נטען עם 1,000 מתוך 2,682 צמתים - עץ תקין-למראה, חסר
   60% מהתוכן.
2. 94 מתוך 1,094 חוקים לא נרשמו ל-ingest_progress, ולכן לא היו קיימים
   מבחינת ה-ingest (ביניהם פקודת העיריות). ההרצה דיווחה "הושלם".

בכל פעם הסיבה הייתה מימוש-עימוד מקומי נוסף שמישהו שכח. שלושה עותקים
של אותה לולאה הם שלוש הזדמנויות לשכוח; עותק אחד הוא אחת.
"""

from __future__ import annotations

import httpx

PAGE_SIZE = 1000


def fetch_all(client: httpx.Client, path: str, params: dict, page_size: int = PAGE_SIZE) -> list[dict]:
    """כל השורות התואמות, בלי תלות בתקרת השורות של השרת.

    משתמשים ב-Range (ולא ב-limit/offset) כי `limit` גדול מ-db-max-rows
    פשוט נחתך בלי להתריע, בעוד Range מכבד את הבקשה עד התקרה ומאפשר
    להמשיך מהמקום הנכון."""
    rows: list[dict] = []
    offset = 0
    while True:
        resp = client.get(
            path,
            params=params,
            headers={"Range-Unit": "items", "Range": f"{offset}-{offset + page_size - 1}"},
        )
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def count_rows(client: httpx.Client, path: str, params: dict) -> int:
    """ספירה בלבד, בלי להוריד שורות. `Prefer: count=exact` מחזיר את
    הסכום האמיתי ב-content-range גם כשהוא גדול מתקרת השורות - ולכן
    אסור ליפול כאן ל-len() על גוף התשובה, שכן *הוא* חתוך."""
    resp = client.get(path, params={**params, "select": "count"}, headers={"Prefer": "count=exact"})
    resp.raise_for_status()
    content_range = resp.headers.get("content-range", "")  # "0-4/5"
    if "/" in content_range:
        total = content_range.split("/")[-1]
        if total.isdigit():
            return int(total)
    raise RuntimeError(f"PostgREST לא החזיר ספירה ב-content-range עבור {path} (התקבל: {content_range!r})")
