"""התאמת חוק (כותרת ויקיטקסט) לתוקפו לפי KNS_IsraelLaw של הכנסת
(OData v4). ראו TASKS.md משימה 7 / docs/strategy/decisions.md
(2026-09-14) - למה נדרש: הקטגוריה "בוט חוקים" מכילה גם חוקים
שבוטלו/פקעו/נושנו, ואין להם ערך במערכת שמנסחת הצעות חוק חדשות.

הקובץ השני (אחרי wikitext_client.py) שנוגע ברשת ב-packages/corpus -
מקור נתונים נפרד לגמרי (הכנסת, לא ויקיטקסט), ולכן קובץ נפרד, לא
עירוב בתוך wikitext_client.py. כמו שם: פונקציית הרשת (fetch_israel_laws)
מובחנת בבירור מהפונקציות הטהורות (classify_validity ואילך), שרצות
על מחרוזות/רשימות בזיכרון בלבד - ניתנות לבדיקה בלי רשת.

עקרון מנחה (ברק, 2026-09-14): "שום חוק לא נזרק בגלל שלא הצלחנו
לבדוק אותו". לכן should_ingest מחזיר True גם למצב "לא נמצאה
התאמה" וגם ל"נמצאו כמה מועמדים ואף אחד לא תקף" (עמימות) - False
רק כשנמצאה התאמה חד-משמעית לחוק בטל/פקע/נושן.

אין fuzzy matching/סף דמיון בכוונה (ברק, 2026-09-14): "סף התאמה
הוא בדיוק המקום שבו חוק אחד מותאם לחוק אחר בשקט". הנירמול כאן
דטרמיניסטי לגמרי - הסרת גרשיים/מקפים/רווחים, הסרת סיומת שנה
עברית, הסרת "[...]" בסוגריים, והסרת אימות קריאה (ו/י שאינן אות
ראשונה של מילה) - לא השוואת דמיון עם סף. נוסה גם נירמול לשנה
לועזית בסוגריים ("(1988)") אך **נדחה במפורש**: הוא איחד בשקט בין
חוקי הסדרים/התייעלות שנתיים שהם באמת חוקים שונים (ראו decisions.md) -
דוגמה מדויקת לסיכון שהעיקרון אוסר עליו.
"""

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Literal

from wikitext_client import USER_AGENT

ODATA_ISRAEL_LAW_URL = "https://knesset.gov.il/OdataV4/ParliamentInfo/KNS_IsraelLaw"

# "תקף" בלבד נחשב תוקף חיובי לצורך פישור עמימות (בחירת מועמד יחיד
# מתוך כמה). "לא ידוע"/"נושן"/"בטל"/"פקע" - ראו should_ingest.
_VALID_DESC = "תקף"
_EXCLUDED_DESCS = {"בטל", "פקע", "נושן"}

MatchMethod = Literal["exact", "normalized", "ambiguous", "not_found"]


@dataclass
class ValidityMatch:
    law_validity_desc: str | None  # None = לא נמצאה התאמה חד-משמעית
    match_method: MatchMethod
    matched_kns_name: str | None = None  # לצורך ביקורת אנושית - השם שהותאם בפועל


def fetch_israel_laws() -> list[dict]:
    """שולפת את כל רשומות KNS_IsraelLaw (OData v4, paginated עם
    @odata.nextLink) - נבדק בפועל 2026-09-14: 2,024 רשומות. יש לבקש
    $top גדול מ-100 (התקרה בפועל של השרת) כדי לקבל nextLink בכלל -
    אם מבקשים בדיוק $top=100 השרת לא מחזיר nextLink למרות שיש עוד."""
    url = f"{ODATA_ISRAEL_LAW_URL}?$top=2200"
    records: list[dict] = []
    while url:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read())
        records.extend(data["value"])
        url = data.get("@odata.nextLink")
    return records


def _normalize_punctuation(s: str) -> str:
    s = s.strip()
    s = s.replace("“", '"').replace("”", '"').replace("״", '"')
    s = s.replace("’", "'").replace("׳", "'")
    s = s.replace("–", "-").replace("—", "-").replace("־", "-")
    return re.sub(r"\s+", " ", s)


# פסיק + "מילת תאריך עברית" (אותיות/גרשיים) + מקף + 4 ספרות, ואופציונלית
# "[...]" אחריה (כמו "[נוסח משולב]") - סיומת שם רשמית שוויקיטקסט משמיט.
_HEBREW_YEAR_SUFFIX_RE = re.compile(r",\s*[א-ת\"'״׳]+[-–־]\d{4}\s*(\[.*\])?\s*$")


def base_title(name: str) -> str:
    """שם מנורמל להשוואה: בלי גרשיים/מקפים לא-אחידים, בלי סיומת שנה
    עברית רשמית, בלי "[...]" באמצע. לא מוריד שנה לועזית בסוגריים
    בכוונה - ראו ההסבר בראש הקובץ (סיכון איחוד חוקי הסדרים שונים)."""
    n = _normalize_punctuation(name)
    n = _HEBREW_YEAR_SUFFIX_RE.sub("", n)
    n = re.sub(r"\s*\[.*?\]\s*", " ", n)
    n = n.replace("-", " ")
    return re.sub(r"\s+", " ", n).strip()


def strip_matres_lectionis(s: str) -> str:
    """מסירה ו/י כאימות קריאה - לא באות הראשונה של כל מילה (שם/שורש
    כמעט אף פעם לא פותח ב-ו/י כתנועה). לא ניחוש/fuzzy - החלטה
    דטרמיניסטית קבועה, ראו ההסבר בראש הקובץ."""
    words = s.split(" ")
    out = []
    for w in words:
        if len(w) <= 1:
            out.append(w)
            continue
        stripped = w[0] + re.sub(r"[וי]", "", w[1:])
        out.append(stripped if stripped else w)
    return " ".join(out)


def _pick_valid_candidate(candidates: list[dict]) -> dict | None:
    """מתוך רשימת רשומות KNS עם אותו שם-בסיס - מחזירה את זו שתוקפה
    'תקף' אם יש בדיוק אחת כזו. אחרת None (עמימות אמיתית - לא ניחוש
    לפי תאריך/מיון שרירותי, ראו הכרעת ברק 2026-09-14)."""
    valid = [r for r in candidates if r.get("LawValidityDesc") == _VALID_DESC]
    return valid[0] if len(valid) == 1 else None


def classify_validity(wikisource_title: str, kns_records: list[dict]) -> ValidityMatch:
    """מסווגת כותרת ויקיטקסט מול רשימת KNS_IsraelLaw. פונקציה טהורה -
    kns_records מועברת מבחוץ (מ-fetch_israel_laws, פעם אחת לכל ריצה),
    לא נשלפת כאן - כדי שאפשר יהיה לבדוק בלי רשת."""
    by_exact: dict[str, list[dict]] = {}
    by_skeleton: dict[str, list[dict]] = {}
    for r in kns_records:
        b = base_title(r["Name"])
        by_exact.setdefault(b, []).append(r)
        by_skeleton.setdefault(strip_matres_lectionis(b), []).append(r)

    wiki_base = base_title(wikisource_title)
    exact_candidates = by_exact.get(wiki_base, [])
    if exact_candidates:
        if len(exact_candidates) == 1:
            r = exact_candidates[0]
            return ValidityMatch(r["LawValidityDesc"], "exact", r["Name"])
        chosen = _pick_valid_candidate(exact_candidates)
        if chosen:
            return ValidityMatch(chosen["LawValidityDesc"], "exact", chosen["Name"])
        return ValidityMatch(None, "ambiguous")

    skeleton_candidates = by_skeleton.get(strip_matres_lectionis(wiki_base), [])
    if skeleton_candidates:
        if len(skeleton_candidates) == 1:
            r = skeleton_candidates[0]
            return ValidityMatch(r["LawValidityDesc"], "normalized", r["Name"])
        chosen = _pick_valid_candidate(skeleton_candidates)
        if chosen:
            return ValidityMatch(chosen["LawValidityDesc"], "normalized", chosen["Name"])
        return ValidityMatch(None, "ambiguous")

    return ValidityMatch(None, "not_found")


def find_israel_law_id(wikisource_title: str, kns_records: list[dict]) -> int | None:
    """כמו classify_validity, אבל מחזירה את ה-Id של הרשומה התואמת
    במקום את סיווג התוקף שלה - ל-law_id.resolve_law_id (ברק,
    2026-09-14: "הלוגיקה לא יכולה להסתמך רק על איזו תבנית מופיעה
    בוויקיטקסט - צריך לבדוק התאמה ל-IsraelLaw תחילה, בלי קשר למה
    שכתוב בדף"). משתמשת באותה לוגיקת התאמה/עמימות בדיוק (קוראת
    ל-classify_validity עצמה - לא כפילות), רק מתרגמת את השם התואם
    בחזרה ל-Id. None אם לא נמצאה התאמה חד-משמעית (not_found/ambiguous)."""
    match = classify_validity(wikisource_title, kns_records)
    if match.matched_kns_name is None:
        return None
    for r in kns_records:
        if r["Name"] == match.matched_kns_name:
            return r["Id"]
    return None  # לא אמור לקרות - matched_kns_name הגיע מתוך kns_records עצמה


def should_ingest(match: ValidityMatch) -> bool:
    """עיקרון: שום חוק לא נזרק בגלל שלא הצלחנו לבדוק אותו (ברק,
    2026-09-14). True לתקף/לא-ידוע (not_found/ambiguous) - רק
    False כשנמצאה התאמה חד-משמעית לבטל/פקע/נושן."""
    if match.law_validity_desc is None:
        return True
    return match.law_validity_desc not in _EXCLUDED_DESCS
