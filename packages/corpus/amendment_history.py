"""פענוח תחביר היסטוריית התיקונים של {{ח:סעיף}} (TASKS.md משימה 7א).

קלט: raw_amendment_note (ראו node.py) - למשל, מסעיף 34כד בחוק העונשין:
"תיקון: [1939], [תשי״ז], [תשל״ה], תשמ״ח־3, תשנ״ד־3, תשנ״ה־4, תשנ״ו־6,
תשנ״ח־2|אחר=[א/5]"

פונקציה טהורה בלבד - אין כאן רשת ואין I/O, בדיוק כמו wikitext_parser.py.
parse_citation_registry עובד על אותה מחרוזת ויקיטקסט (הפתיח של דף החוק),
לא על רשת - היא כבר נשלפת ונשמרת ע"י wikitext_client.fetch_wikitext.

מה פוענח, ואיך אומת (מקור עצמאי - ראו "הסתיים כאשר" במשימה 7א):
דף חוק העונשין בוויקיטקסט מכיל בעצמו רשימת ציטוטים כרונולוגית של כל
תיקוני החוק, בשורה שמתחילה ב-'''נוסח מאוחד:''' (אחרי הקונסולידציה של
תשל"ז/1977) ו-'''נוסחים קודמים:''' (לפניה) - כל ציטוט הוא
{{ח:תיבה|<שנה עברית>, <עמוד>|<שם החוק/התיקון>|<קישור>}}, וכשכמה תיקונים
חלים באותה שנה עברית, רק הראשון נושא את השנה - השאר רק מספר עמוד.

זו בדיוק ה"אימות עצמאי" הנדרש: הסיומת "־N" בטוקן תיקון (כמו "תשנ״ד־3")
זוהתה, ואומתה, כמיקום (1-based) של הציטוט בתוך רשימת הציטוטים הכרונולוגית
של אותה שנה עברית ברשימה הזו - כשסופרים כל ציטוט (כולל "ת״ט"/תיקוני-טעות
וחוקים אחרים שמוזכרים לצורך הקשר, לא רק "תיקון מס'" ממוספר). אימות מרכזי:
סעיף 34כד מוגדר ("הגדרות") ותיקון "תשנ״ד־3" מוביל לציטוט השלישי של תשנ״ד
ברשימה - "348 | תיקון מס' 39 (חלק מקדמי וחלק כללי)" - הרפורמה הגדולה
הידועה בחלק המקדמי של חוק העונשין, שתואמת בדיוק את הטווח הרחב של סעיפים
שנושאים את אותו תיקון (1 ועד למעלה מ-20 ברצף - ראו טסטים).

**מה עדיין לא פוענח/לא ודאי - לא ינוחש:**
1. טוקן בלי סיומת "־N" ובלי סוגריים (למשל "תשס״ז" לבדו) - ההשערה שהוא
   שווה-ערך ל-"־1" (הציטוט הראשון של אותה שנה) נתמכת רק במקרה בדיקה אחד
   (סעיף 15, "תשס״ז" → ציטוט ראשון של תשס״ז, "חוק איסור סחר בבני אדם" -
   סביר תוכנית לסעיף על סמכות שיפוט חוץ-טריטוריאלית, אבל לא אומת מול
   מקור נוסף). מסומן ordinal_explicit=False - לא להתייחס אליו כוודאי.
2. טוקנים בסוגריים מרובעים ([1939], [תשי״ז] וכו') - תיקונים מלפני
   הקונסולידציה של תשל"ז. לרשימת "נוסחים קודמים" אין מנגנון "־N"
   מקביל בוויקיטקסט המקורי עצמו (נבדק: ל-תשי״ז יש שני ציטוטים ברשימה
   הזו, אבל 34כד לא מבחין ביניהם בסוגריים) - זו מגבלה אמיתית של
   המקור, לא של הפרסר. resolve_amendment_tokens מחזירה את כל
   המועמדים התואמים (candidates) ולא מנחשת איזה מהם.
3. הארגומנט "אחר=..." (למשל "[א/5]") - לא מפוענח כלל, נשמר גולמי
   ב-ParsedAmendmentNote.other_raw. אין עדיין השערה נבדקת למשמעותו.
"""

import re
from dataclasses import dataclass

_HEBREW_MAQAF = "־"  # "־" - המפריד בין שנה למספר סידורי, למשל "תשנ״ד־3"


@dataclass(frozen=True)
class AmendmentToken:
    """טוקן בודד בתוך רשימת 'תיקון: ...'."""

    hebrew_year: str  # "תשנ״ד", או שנה גולמית טרום-1977 (עברית או לועזית) לטוקן legacy
    ordinal_in_year: int  # מיקום 1-based בין ציטוטי אותה שנה (ברירת מחדל 1 אם לא צוין סיומת)
    ordinal_explicit: bool  # True אם ה-"־N" הופיע במפורש; False = ברירת מחדל לא-מאומתת (ראו סעיף 1 למעלה)
    is_legacy: bool  # True = טוקן בסוגריים מרובעים (טרום-קונסולידציה)


@dataclass(frozen=True)
class ParsedAmendmentNote:
    tokens: tuple[AmendmentToken, ...]
    other_raw: str | None  # ערך "אחר=..." הגולמי, לא מפוענח (ראו סעיף 3 למעלה)
    unrecognized_parts: tuple[str, ...]  # ארגומנטים נוספים שלא זוהו - לא נזרקים


def parse_amendment_note(raw: str | None) -> ParsedAmendmentNote:
    """מפרסרת raw_amendment_note (ראו node.py) לרשימת טוקני תיקון מזוהים.

    הקלט מורכב מארגומנטים גולמיים מחוברים ב-"|" (ראו wikitext_parser.py,
    ח:סעיף: `"|".join(extra_args)`), כשהראשון (אם קיים) מתחיל ב-"תיקון:"."""
    if not raw:
        return ParsedAmendmentNote(tokens=(), other_raw=None, unrecognized_parts=())

    tokens: list[AmendmentToken] = []
    other_raw: str | None = None
    unrecognized: list[str] = []

    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("תיקון:"):
            body = part[len("תיקון:") :].strip()
            for chunk in body.split(","):
                chunk = chunk.strip()
                if chunk:
                    tokens.append(_parse_token(chunk))
        elif part.startswith("אחר="):
            other_raw = part[len("אחר=") :].strip()
        else:
            unrecognized.append(part)

    return ParsedAmendmentNote(
        tokens=tuple(tokens),
        other_raw=other_raw,
        unrecognized_parts=tuple(unrecognized),
    )


def _parse_token(chunk: str) -> AmendmentToken:
    if chunk.startswith("[") and chunk.endswith("]"):
        return AmendmentToken(
            hebrew_year=chunk[1:-1].strip(),
            ordinal_in_year=1,
            ordinal_explicit=False,
            is_legacy=True,
        )
    if _HEBREW_MAQAF in chunk:
        year, _, ordinal_str = chunk.rpartition(_HEBREW_MAQAF)
        return AmendmentToken(
            hebrew_year=year.strip(),
            ordinal_in_year=int(ordinal_str.strip()),
            ordinal_explicit=True,
            is_legacy=False,
        )
    return AmendmentToken(
        hebrew_year=chunk.strip(),
        ordinal_in_year=1,
        ordinal_explicit=False,
        is_legacy=False,
    )


@dataclass(frozen=True)
class CitationEntry:
    """ציטוט בודד מרשימת הציטוטים הכרונולוגית שבפתיח דף החוק בוויקיטקסט."""

    hebrew_year: str
    ordinal_in_year: int  # 1-based, בין ציטוטי אותה שנה ברשימה זו בלבד
    page: str
    name: str
    amendment_number: str | None  # נחלץ מ-name אם מופיע "תיקון מס' N"


_CITATION_BOX_RE = re.compile(r"\{\{ח:תיבה\|(.*?)\}\}")
_YEAR_PREFIX_RE = re.compile(r"^(?P<year>[^,]+),\s*(?P<page>.+)$")
_AMENDMENT_NUMBER_RE = re.compile(r"תיקון מס[׳']\s*(\d+)")
_PREAMBLE_LINE_MARKERS = ("נוסח מאוחד", "נוסחים קודמים")


def parse_citation_registry(wikitext: str) -> list[CitationEntry]:
    """מפרסרת את רשימת הציטוטים הכרונולוגית מפתיח דף החוק (בין
    {{ח:פתיח-התחלה}} ל-{{ח:סוגר}} הראשון) לרשימת CitationEntry מסודרת.

    מסתכלת רק על שורות שמכילות את הסמנים '''נוסח מאוחד:''' או
    '''נוסחים קודמים:''' - לא על כל שורה בפתיח (יש שם גם שורות לא
    קשורות, כמו עדכוני קנסות בתקנות - ראו docstring המודול)."""
    start = wikitext.find("{{ח:פתיח-התחלה}}")
    if start == -1:
        return []
    end = wikitext.find("{{ח:סוגר}}", start)
    preamble = wikitext[start:end] if end != -1 else wikitext[start:]

    entries: list[CitationEntry] = []
    current_year = ""
    year_counters: dict[str, int] = {}
    for line in preamble.splitlines():
        if not any(marker in line for marker in _PREAMBLE_LINE_MARKERS):
            continue
        for body in _CITATION_BOX_RE.findall(line):
            # {{ח:תיבה|CITE|NAME}} (בלי קישור) קיים בפועל, למשל ...|XVI|ת״ט}}
            # - לא לחייב 3 ארגומנטים, ולא לתפוס בחמדנות לתוך הקריאה הבאה.
            fields = body.split("|")
            if len(fields) < 2:
                continue
            cite = fields[0].strip()
            name = fields[1].strip()
            match = _YEAR_PREFIX_RE.match(cite)
            if match:
                current_year = match.group("year").strip()
                page = match.group("page").strip()
            else:
                page = cite
            year_counters[current_year] = year_counters.get(current_year, 0) + 1
            amendment_match = _AMENDMENT_NUMBER_RE.search(name)
            entries.append(
                CitationEntry(
                    hebrew_year=current_year,
                    ordinal_in_year=year_counters[current_year],
                    page=page,
                    name=name,
                    amendment_number=amendment_match.group(1) if amendment_match else None,
                )
            )
    return entries


def resolve_amendment_tokens(
    tokens: tuple[AmendmentToken, ...], registry: list[CitationEntry]
) -> list[tuple[AmendmentToken, tuple[CitationEntry, ...]]]:
    """מצמידה לכל טוקן את כל ה-CitationEntry התואמים לו ברשימה.

    0 תוצאות = לא נמצא; תוצאה 1 = פתירה חד-משמעית; יותר מ-1 = דו-משמעי
    (קורה בפועל עם טוקני legacy - ראו סעיף 2 בדוקסטרינג המודול, לא
    מנחשת איזה מהם נכון)."""
    resolved = []
    for token in tokens:
        if token.is_legacy:
            candidates = tuple(e for e in registry if e.hebrew_year == token.hebrew_year)
        else:
            candidates = tuple(
                e
                for e in registry
                if e.hebrew_year == token.hebrew_year
                and e.ordinal_in_year == token.ordinal_in_year
            )
        resolved.append((token, candidates))
    return resolved
