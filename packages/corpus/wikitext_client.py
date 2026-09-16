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
import xml.etree.ElementTree as ET

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


LAW_CATEGORY = "קטגוריה:בוט חוקים"  # ראו docs/strategy/decisions.md - מנגנון המניה למשימה 1.2/7


def list_category_titles(category: str = LAW_CATEGORY) -> list[str]:
    """מונה את כל כותרות הדפים בקטגוריה נתונה, עם pagination מלא (cmcontinue).
    זה מנגנון המניה של הקורפוס השלם - אומת בפועל (2026-09-13): 6,121
    כותרות, קרוב ל-'~5,900' המתועד ב-docs/data-sources.md/TASKS.md
    משימה 7 (המספר המדויק תמיד ישתנה מעט - זה תיאור, לא קבוע)."""
    titles: list[str] = []
    cmcontinue: str | None = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": "500",
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        url = f"{API_URL}?{urllib.parse.urlencode(params)}"
        data = json.loads(_get(url))
        titles.extend(member["title"] for member in data["query"]["categorymembers"])
        cont = data.get("continue")
        if not cont:
            break
        cmcontinue = cont["cmcontinue"]
    return titles


def is_primary_legislation_title(title: str) -> bool:
    """True לחוקים, חוקי-יסוד, פקודות ודברי המלך - חקיקה ראשית
    שהכנסת מתקנת בהצעת חוק. **לא** תקנות/צווים/כללים/הוראות/אכרזות
    וכו' - חקיקת משנה שהממשלה/שר מחוקקים מכוח הסמכה בחוק קיים, לא
    ברת-תיקון בהצעת חוק (73% מ"קטגוריה:בוט חוקים" - ראו ההחלטה
    המקורית ב-docs/strategy/decisions.md, 2026-09-13/14).

    **תוקן (2026-09-16, ברק) - ההחלטה המקורית להוציא פקודות/דברי
    המלך התבררה כשגויה.** ההחלטה מ-2026-09-13 סיננה לפי **צורת
    השם** (רק "חוק "/"חוק-יסוד:") ולא לפי **מהות** (מי מתקן: הכנסת
    או הממשלה). פקודות מהתקופה המנדטורית ודברי המלך הם חקיקה ראשית
    לכל דבר - מתוקנים בפועל בהצעת חוק של הכנסת בדיוק כמו חוק רגיל
    (אומת: 94 מתוכם עדיין "תקף" ב-KNS_IsraelLaw) - והוצאו בטעות
    רק כי שמם לא מתחיל ב"חוק ". ראו docs/strategy/decisions.md
    ל-post-mortem מלא כולל הלקח (לסנן לפי מהות, לא צורת שם)."""
    return (
        title.startswith("חוק ")
        or title.startswith("חוק-יסוד:")
        or title == "חוק"
        or title.startswith("פקודת ")
        or title.startswith("פקודה ")
        or title.startswith("דבר המלך ")
        or title.startswith("דברי המלך ")
    )


def fetch_wikitext(title: str) -> dict:
    """שולף ויקיטקסט גולמי + מטא-דאטה של דף (page id, revision id,
    revision timestamp) דרך Special:Export. מחזיר מבנה מתאים לשמירה
    כ-fixture (ראו tests/fixtures/wikitext/ ו-scratchpad/extract_fixtures.py
    ששימש לבניית ה-fixtures הקיימים)."""
    title_encoded = urllib.parse.quote(title.replace(" ", "_"))
    url = EXPORT_URL_TEMPLATE.format(title=title_encoded)
    xml_bytes = _get(url)
    return {"title": title, "export_xml": xml_bytes.decode("utf-8")}


def _local_tag(tag: str) -> str:
    """שם התג בלי namespace ({http://...}tag -> tag) - Special:Export
    מכריז xmlns גרסתי (export-0.11 וכו') שמשתנה בין דפים/גרסאות ויקי,
    ואין טעם להתאים אליו במפורש כדי לשלוף שדה יחיד."""
    return tag.rsplit("}", 1)[-1]


def extract_revision_timestamp(export_xml: str) -> str:
    """שולפת את revision/timestamp מתוך XML של Special:Export - זה
    המקור היחיד שיש לנו ל-as_of (חוק ברזל 3, ראו docs/data-sources.md
    וnode.py: 'נוסח כפי שהופיע בוויקיטקסט ביום X', לא 'מעודכן ליום X').
    לא שולפת page id/revision id - as_of לא זקוק להם היום.

    היה קודם לכן שדה שנשלף באופן חד-פעמי (ידני, בסקריפט scratchpad
    שאבד) בזמן בניית ה-fixtures, ולא הפך לקוד אמיתי בפרויקט - ולכן
    מעולם לא זרם הלאה ל-LegislativeNode.as_of. זו הפעם הראשונה שזו
    פונקציה אמיתית וניתנת לבדיקה (ראו tests/unit/test_wikitext_client.py)."""
    root = ET.fromstring(export_xml)
    for elem in root.iter():
        if _local_tag(elem.tag) == "revision":
            for child in elem:
                if _local_tag(child.tag) == "timestamp" and child.text:
                    return child.text
            raise ValueError("נמצא revision ללא timestamp ב-export XML")
    raise ValueError("לא נמצא revision ב-export XML")


def extract_revision_id(export_xml: str) -> int:
    """שולפת את revision/id (מזהה גרסה מספרי) מתוך XML של Special:Export -
    נדרש ל-law_versions.wikitext_revision_id (ראו supabase/migrations),
    כדי לדעת אם גרסה מסוימת כבר נטענה בלי לטעון אותה שוב."""
    root = ET.fromstring(export_xml)
    for elem in root.iter():
        if _local_tag(elem.tag) == "revision":
            for child in elem:
                if _local_tag(child.tag) == "id" and child.text:
                    return int(child.text)
            raise ValueError("נמצא revision ללא id ב-export XML")
    raise ValueError("לא נמצא revision ב-export XML")


def extract_wikitext_body(export_xml: str) -> str:
    """שולפת את הוויקיטקסט הגולמי עצמו (revision/text) מתוך XML של
    Special:Export - זה בדיוק מה שנשמר בקבצי tests/fixtures/wikitext/*.wikitext
    (לא ה-XML המלא). זו הפעם הראשונה שזו פונקציה אמיתית - קודם זה נעשה
    ידנית בסקריפט scratchpad שאבד (ראו extract_revision_timestamp)."""
    root = ET.fromstring(export_xml)
    for elem in root.iter():
        if _local_tag(elem.tag) == "revision":
            for child in elem:
                if _local_tag(child.tag) == "text":
                    return child.text or ""
            raise ValueError("נמצא revision בלי טקסט ב-export XML")
    raise ValueError("לא נמצא revision ב-export XML")
