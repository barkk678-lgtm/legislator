"""שליפת ויקיטקסט חי מ-he.wikisource.org. ראו TASKS.md משימה 3.

הקובץ היחיד ב-packages/corpus שנוגע ברשת. אסור לפרסר (wikitext_parser.py)
לייבא את זה - הפרסור צריך לרוץ על מחרוזת בלי תלות ברשת, כדי שהטסטים
ירוצו אופליין על tests/fixtures/wikitext/ (ראו CLAUDE.md).

מכבד את מדיניות ה-rate limit של ויקימדיה: User-Agent מזהה, וכיבוד
retry-after (ראו https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits).
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "mansach-hachukika-research/0.1 (educational legislative-drafting-tool)"
API_URL = "https://he.wikisource.org/w/api.php"
EXPORT_URL_TEMPLATE = "https://he.wikisource.org/wiki/Special:Export/{title}"


def _get(url: str, *, max_attempts: int = 10, backoff_seconds: float = 25.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code != 429:
                raise
            retry_after = float(exc.headers.get("retry-after", backoff_seconds))
            time.sleep(retry_after)
    raise RuntimeError(f"נכשל אחרי {max_attempts} ניסיונות: {last_error}")


def search_title(query: str, *, limit: int = 10) -> list[dict]:
    """מחפש כותרות דפים ב-he.wikisource.org. שימושי כדי לוודא את הכותרת
    המדויקת של חוק לפני שליפת הוויקיטקסט המלא - כותרות דף לרוב אינן
    כוללות את שנת החקיקה (ראו ממצא recon: 'חוק הקייטנות (רישוי ופיקוח)',
    בלי '-1990')."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": str(limit),
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    data = json.loads(_get(url))
    return data["query"]["search"]


def fetch_wikitext(title: str) -> dict:
    """שולף ויקיטקסט גולמי + מטא-דאטה של דף (page id, revision id,
    revision timestamp) דרך Special:Export. מחזיר מבנה מתאים לשמירה
    כ-fixture (ראו tests/fixtures/wikitext/ ו-scratchpad/extract_fixtures.py
    ששימש לבניית ה-fixtures הקיימים)."""
    title_encoded = urllib.parse.quote(title.replace(" ", "_"))
    url = EXPORT_URL_TEMPLATE.format(title=title_encoded)
    xml_bytes = _get(url)
    return {"title": title, "export_xml": xml_bytes.decode("utf-8")}
