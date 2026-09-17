"""לקוח OData של הכנסת (משימה 1.4) - שכבה משותפת לשלושת התוצרים:
מראי מקום, בדיקת הצעות דומות, ומאגר השאילתות.

**הפיד מחזיר 100 שורות לכל בקשה, ו-`$top` גדול יותר נחתך בלי להתריע**
(נבדק: `$top=5000` החזיר 100). זו בדיוק המלכודת של PostgREST שהכתה
כאן פעמיים, ולכן העימוד כאן הוא דרך `@odata.nextLink` שהשרת מחזיר -
ולא לולאת `$skip` משלנו שתסתמך על הנחה לגבי גודל העמוד.

**קריאה חיה, בלי להעתיק את המאגר אלינו.** שאילתה ממוקדת נמדדה ב-~0.6
שניות, ושלוש הטבלאות היו תופסות ~30MB מתוך 52MB שנותרו ב-Free tier.
אם יתברר שזה איטי מדי בשימוש אמיתי - נוסיף cache אז, על בסיס מדידה.

**רשת:** `knesset.gov.il` נגיש גם מסביבת ה-agent וגם מ-Vercel, אבל
`fs.knesset.gov.il` (שרת הקבצים, שם יושבים טקסטים מלאים של שאילתות
והצעות) חסום מסביבת ה-agent. ראו CLAUDE.md "גבולות רשת".
"""

from __future__ import annotations

import httpx

BASE_URL = "https://knesset.gov.il/OdataV4/ParliamentInfo"
_TIMEOUT = 20.0
# תקרת בטיחות מפני לולאה אינסופית. **חריגה ממנה זורקת שגיאה ולא
# מחזירה תוצאה חלקית** - החזרה שקטה של 5,000 מתוך 15,326 היא בדיוק
# סוג הכשל שהמסמכים כאן מזהירים ממנו, והיא קרתה בפועל בפיתוח הקובץ
# הזה עצמו.
_MAX_PAGES = 400


class OdataError(Exception):
    """כשל רשת/HTTP מול הפיד של הכנסת."""


def _client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT, headers={"Accept": "application/json"})


def fetch(entity: str, *, filter: str | None = None, select: str | None = None,
          orderby: str | None = None, top: int | None = None) -> list[dict]:
    """שורות מהפיד, עם עימוד מלא דרך nextLink.

    top הוא תקרה *שלנו* על סך השורות המוחזרות (לא `$top` של השרת,
    שנחתך ב-100 ממילא) - שימושי כשרוצים "10 התוצאות הראשונות" בלי
    למשוך את כל ההתאמות."""
    params = {k: v for k, v in (
        ("$filter", filter), ("$select", select), ("$orderby", orderby)
    ) if v}

    rows: list[dict] = []
    url: str | None = f"{BASE_URL}/{entity}"
    with _client() as client:
        for _ in range(_MAX_PAGES):
            try:
                resp = client.get(url, params=params if params and url.endswith(entity) else None)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise OdataError(f"כשל בקריאה ל-{entity} מהפיד של הכנסת: {e}") from None
            payload = resp.json()
            rows.extend(payload.get("value", []))
            if top is not None and len(rows) >= top:
                return rows[:top]
            url = payload.get("@odata.nextLink")
            if not url:
                return rows
    raise OdataError(
        f"{entity}: נמשכו {len(rows)} שורות ועדיין יש המשך - חריגה מתקרת "
        f"{_MAX_PAGES} העמודים. עדיף לצמצם את ה-filter מאשר להחזיר נתונים חלקיים."
    )


def count(entity: str, *, filter: str | None = None) -> int:
    """ספירה בלבד. `$count=true` מחזיר את הסכום האמיתי ולא את מספר
    השורות שחזרו בעמוד - אותו לקח כמו ב-PostgREST."""
    params = {"$count": "true", "$top": "1"}
    if filter:
        params["$filter"] = filter
    with _client() as client:
        try:
            resp = client.get(f"{BASE_URL}/{entity}", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OdataError(f"כשל בספירת {entity}: {e}") from None
    return int(resp.json().get("@odata.count", 0))


def escape(value: str) -> str:
    """מירכאה בודדת בתוך מחרוזת OData מוכפלת. בלי זה, שם חוק עם
    גרש (נפוץ בעברית: "התשס\"ו") שובר את ה-filter או גרוע מזה -
    מאפשר הזרקה לביטוי."""
    return value.replace("'", "''")


def fetch_raw_array(entity: str, *, filter: str | None = None) -> list[dict]:
    """ישויות שמחזירות **מערך JSON חשוף** במקום המעטפת התקנית של
    OData (`{"value": [...]}`), עם מפתחות ב-camelCase קטן במקום
    PascalCase - למשל `KNS_DocumentQuery`. זו חריגה אמיתית בפיד,
    לא טעות שלנו: אותו שרת, שתי צורות תשובה.

    אין כאן `@odata.nextLink`, ולכן **אין דרך לדעת אם התשובה נחתכה**.
    מיועד אך ורק לשליפות ממוקדות לפי מזהה (עשרות שורות לכל היותר),
    לא לסריקה - ראו CLAUDE.md על ההנחה שכל תשובה מעומדת."""
    params = {"$filter": filter} if filter else None
    with _client() as client:
        try:
            resp = client.get(f"{BASE_URL}/{entity}", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OdataError(f"כשל בקריאה ל-{entity}: {e}") from None
    payload = resp.json()
    return payload if isinstance(payload, list) else payload.get("value", [])
