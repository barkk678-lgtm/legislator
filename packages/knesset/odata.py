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

import time

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


class FeedBlockedError(OdataError):
    """ה-WAF של הכנסת חוסם את כתובת ה-IP שלנו (HTTP 474)."""


# **מפסק לחסימת IP** (ש4, 25.9.2026). ל-WAF של הכנסת שני סוגי דחייה,
# ונמדדו בנפרד:
# - **473 - לפי התוכן, דטרמיניסטי:** מסנן עם 4 סוגריים פותחים ומעלה
#   נחסם תמיד (ראו knesset_queries.feed_filter). ניסיון חוזר לא יעזור.
# - **474 - לפי הכתובת:** אותה בקשה בדיוק עברה, עברה, נחסמה ועברה;
#   אחר כך 16 מתוך 25 נחסמו (בהפסקה של שנייה ובלי הפסקה - אותו שיעור,
#   כלומר זו אינה מגבלת קצב רגילה), ובסוף **הכול** נחסם, גם
#   `KnessetNum eq 25` בלי שום מילה. גם האתר החי נחסם באותו זמן.
# ניסיון חוזר על 474 רק מוסיף בקשות לכתובת שכבר מסומנת. ולכן: 474
# אחד -> כל קריאה לפיד נכשלת מיד, בלי רשת, למשך BLOCK_COOLDOWN, והממשק
# אומר "לא זמין כרגע" (ולא "לא נמצא").
BLOCK_COOLDOWN = 60.0
_blocked_until = 0.0


def _get(client: httpx.Client, url: str, params: dict | None, what: str) -> httpx.Response:
    global _blocked_until
    if time.time() < _blocked_until:
        raise FeedBlockedError(f"{what}: הפיד של הכנסת חוסם כרגע את השרת (474), לא נשלחה בקשה.")
    try:
        resp = client.get(url, params=params)
    except httpx.HTTPError as e:
        raise OdataError(f"{what}: {e}") from None
    if resp.status_code == 474:
        _blocked_until = time.time() + BLOCK_COOLDOWN
        raise FeedBlockedError(f"{what}: הפיד של הכנסת חוסם את השרת (474).")
    try:
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise OdataError(f"{what}: {e}") from None
    return resp


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
            resp = _get(client, url, params if params and url.endswith(entity) else None,
                        f"כשל בקריאה ל-{entity} מהפיד של הכנסת")
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
        resp = _get(client, f"{BASE_URL}/{entity}", params, f"כשל בספירת {entity}")
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
        resp = _get(client, f"{BASE_URL}/{entity}", params, f"כשל בקריאה ל-{entity}")
    payload = resp.json()
    return payload if isinstance(payload, list) else payload.get("value", [])


def fetch_apply(entity: str, apply_expr: str, page_size: int = 100) -> list[dict]:
    """צבירה בצד השרת (`$apply`), עם עימוד ידני.

    **זו הצורה המסוכנת ביותר בפיד:** התשובה היא מערך חשוף, **בלי
    מעטפת `value` ובלי `@odata.nextLink`**, והיא נחתכת ב-100 שורות
    בלי שום סימן. נמדד בפועל: `groupby((KnessetNum,StatusID))` החזיר
    100 שורות בעוד קיימות 312 - כלומר שני שלישים מהתשובה נעלמו
    בשקט. העימוד כאן הוא `$skip` ידני, וממשיכים עד שעמוד חוזר קטן
    מ-page_size.

    **אין לצרף `$filter`:** הפיד דוחה אותו יחד עם `$apply`, ו-
    `filter(...)` *בתוך* הביטוי נחסם על ידי ה-WAF (סטטוס 473).
    הסינון נעשה מקומית על התוצאה."""
    rows: list[dict] = []
    skip = 0
    with _client() as client:
        for _ in range(_MAX_PAGES):
            params = {"$apply": apply_expr}
            if skip:
                params["$skip"] = str(skip)
            resp = _get(client, f"{BASE_URL}/{entity}", params, f"כשל בצבירה על {entity}")
            payload = resp.json()
            page = payload if isinstance(payload, list) else payload.get("value", [])
            rows.extend(page)
            if len(page) < page_size:
                return rows
            skip += page_size
    raise OdataError(
        f"צבירה על {entity} חרגה מתקרת {_MAX_PAGES} העמודים - עדיף לצמצם "
        f"את הביטוי מאשר להחזיר תוצאה חלקית."
    )
