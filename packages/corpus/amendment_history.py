"""פענוח תחביר היסטוריית התיקונים של {{ח:סעיף}} (TASKS.md משימה 7א).

קלט: raw_amendment_note (ראו node.py) - למשל, מסעיף 34כד בחוק העונשין:
"תיקון: [1939], [תשי״ז], [תשל״ה], תשמ״ח־3, תשנ״ד־3, תשנ״ה־4, תשנ״ו־6,
תשנ״ח־2|אחר=[א/5]"

פונקציה טהורה בלבד - אין כאן רשת ואין I/O, בדיוק כמו wikitext_parser.py.
parse_citation_registry עובד על אותה מחרוזת ויקיטקסט (הפתיח של דף החוק),
לא על רשת - היא כבר נשלפת ונשמרת ע"י wikitext_client.fetch_wikitext.

**שכבות (ראו CLAUDE.md "ה-ingest שומר עובדות, לא פרשנויות"):**
raw_amendment_note הוא העובדה שנשמרת בקורפוס - כמו שהיא. כל הפונקציות
במודול הזה (כולל parse_citation_registry, שגם היא פרסור דטרמיניסטי של
טקסט גולמי כבר-שמור) רצות מעל טקסט שכבר שמור, ולא כותבות עמודות מחושבות
חזרה לקורפוס ב-ingest. resolve_amendment_tokens היא הפונקציה היחידה
שמכילה שיפוט (צימוד בין שני מקורות שאינו תמיד ודאי) - היא מיועדת
לריצה בזמן שאילתה, לא לאחסון כתוצאה קבועה: אם היא תשתפר בעתיד, אסור
שזה יחייב ingest חוזר לקורפוס.

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

**מה בכוונה לא פוענח/נפתר - הוכרע (2026-09-13, ברק) לשמור טוקן גולמי
בלי להכריע, במקום לנחש (ראו TASKS.md 7א):**

1. טוקן בלי סוגריים ובלי סיומת "־N" (למשל "תשס״ז" לבדו) - **אין ברירת
   מחדל**. ordinal_in_year=None. נבדק בפועל בקורפוס (penal.wikitext):
   131 מופעים כאלה, ומתוכם 117 (89%) לשנה שלהם יש יותר מציטוט אחד
   ברשימה - כלומר "להניח שזה הציטוט הראשון" היה טעות שקטה ברוב
   המקרים, לא ברירת מחדל סבירה. resolve_amendment_tokens מחזירה את
   כל מועמדי אותה שנה (בדיוק כמו legacy, סעיף 2 למטה) - לא בוחרת.
2. טוקנים בסוגריים מרובעים ([1939], [תשי״ז] וכו') - תיקונים מלפני
   הקונסולידציה של תשל"ז. ordinal_in_year=None גם כאן (לרשימת "נוסחים
   קודמים" אין מנגנון "־N" מקביל בוויקיטקסט המקורי עצמו - זו מגבלה
   אמיתית של המקור, לא של הפרסר: ל-34כד ולתשי״ז יש 5 מועמדים תואמים,
   ואין דרך לדעת מהמקור איזה מהם). resolve_amendment_tokens מחזירה
   את כל המועמדים התואמים לפי שנה בלבד - 84 מתוך 162 מופעי legacy
   בקורפוס דו-משמעיים כך גם, 4 לא נמצא להם מועמד כלל.
3. הארגומנט "אחר=..." (למשל "[א/5]", "[יא/32א]") - לא מפוענח כלל,
   נשמר גולמי ב-ParsedAmendmentNote.other_raw. 255 מופעים בקורפוס,
   בפורמט עקבי [אות/מספר] - לא נבדקה משמעותו (ראו TASKS.md, משימת
   חקירה נפרדת, לא נפתחה עדיין לעבודה).
4. טוקן עם "־" אבל בלי מספר תקין אחריו (למשל "תשס״ה־3 תשע״ד" בחוק
   העמותות - כנראה פסיק חסר במקור בין שני טוקנים, ראו TASKS.md
   משימה 7) - **לא קורס** (2026-09-14, ברק: "תוכנה שקורסת על קלט
   פגום היא באג בתוכנה"). נשמר גולמי (`AmendmentToken.raw`),
   `unparsed=True`, `hebrew_year=None`/`ordinal_in_year=None` - לא
   מנחש חלוקה לשני טוקנים, לא זורק. `resolve_amendment_tokens`
   מתעלמת מטוקנים כאלה ממילא (hebrew_year=None לא תואם שום רשומה
   ברשימה - 0 מועמדים, בדיוק כמו "לא נמצא").
"""

import re
from dataclasses import dataclass

_HEBREW_MAQAF = "־"  # "־" - המפריד בין שנה למספר סידורי, למשל "תשנ״ד־3"


@dataclass(frozen=True)
class AmendmentToken:
    """טוקן בודד בתוך רשימת 'תיקון: ...'."""

    hebrew_year: str | None  # "תשנ״ד" וכו'; None רק אם unparsed=True (ראו שם)
    ordinal_in_year: int | None  # מיקום 1-based, רק אם צוין במקור כ-"־N"; None = לא ידוע, לא מנוחש
    is_legacy: bool  # True = טוקן בסוגריים מרובעים (טרום-קונסולידציה)
    raw: str = ""  # הטקסט הגולמי של הטוקן, תמיד נשמר - גם כשהפענוח הצליח
    unparsed: bool = False  # True = לא הצלחנו לפענח בכלל (ראו סעיף 4 למעלה) -
    # hebrew_year/ordinal_in_year לא משמעותיים, raw הוא היחיד שאפשר לסמוך עליו


@dataclass(frozen=True)
class ParsedAmendmentNote:
    tokens: tuple[AmendmentToken, ...]
    other_raw: str | None  # ערך "אחר=..." הגולמי, לא מפוענח (ראו סעיף 3 בדוקסטרינג המודול)
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
        return AmendmentToken(hebrew_year=chunk[1:-1].strip(), ordinal_in_year=None, is_legacy=True, raw=chunk)
    if _HEBREW_MAQAF in chunk:
        year, _, ordinal_str = chunk.rpartition(_HEBREW_MAQAF)
        ordinal_str = ordinal_str.strip()
        if ordinal_str.isdigit():
            return AmendmentToken(
                hebrew_year=year.strip(),
                ordinal_in_year=int(ordinal_str),
                is_legacy=False,
                raw=chunk,
            )
        # "־" קיים אבל מה שאחריו לא מספר תקין (ראו סעיף 4 בדוקסטרינג
        # המודול) - לא קורסים, לא מנחשים חלוקה - נשמר גולמי בלבד.
        return AmendmentToken(hebrew_year=None, ordinal_in_year=None, is_legacy=False, raw=chunk, unparsed=True)
    return AmendmentToken(hebrew_year=chunk.strip(), ordinal_in_year=None, is_legacy=False, raw=chunk)


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
    """מצמידה לכל טוקן את כל ה-CitationEntry התואמים לו ברשימה - פונקציית
    שאילתה, לא שלב ב-ingest (ראו docstring המודול).

    כשה-ordinal לא ידוע במקור (ordinal_in_year=None - גם legacy וגם טוקן
    בלי סיומת, ראו סעיפים 1-2 בדוקסטרינג) מתאימה לפי שנה בלבד ומחזירה
    את *כל* המועמדים, בלי לבחור. 0 תוצאות = לא נמצא; 1 = פתירה חד-משמעית;
    יותר מ-1 = דו-משמעי במקור עצמו - לא מנוחש."""
    resolved = []
    for token in tokens:
        if token.ordinal_in_year is None:
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
