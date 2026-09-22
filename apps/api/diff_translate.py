"""מתרגם עריכה חופשית (טקסט 'לפני'/'אחרי' של צומת בודד, מ-contenteditable)
להוראת תיקון תואמת-מנוע (transform.InsertWordsAfter / transform.ReplaceWords),
או ל"לא נתמך" אם אי אפשר לבטא את השינוי בבירור. ראו TASKS.md משימה 10ב.

טהור: אין כאן לוגיקה משפטית, רק גזירת גבולות ביטוי מתוך דיף טקסטואלי.
אסור לנחש: transform.InsertWordsAfter/ReplaceWords דורשות ש-anchor_substring/
old_phrase יופיעו פעם אחת בדיוק ב-before - זה בדיוק מה שהאלגוריתם כאן
עובד כדי להבטיח (הרחבה איטרטיבית לגבולות מילה עד ייחודיות), לא מניח
את זה בשקט.

שלבים (כפי שהוצגו ואושרו למשתמש): דיף-תווים מינימלי (prefix/suffix
משותפים) -> הרחבה לגבולות מילה -> בדיקת ייחודיות בתוך הצומת הבודד
(הצומת עצמו הוא היקף העריכה) -> נפילה ל"לא נתמך" אם ההרחבה לא מגיעה
לייחודיות.

**תיקון חשוב לפני הרחבת-הייחודיות (לא רק אחריה):** דיף prefix/suffix
תווי-גרידא עלול לעצור *באמצע מילה* בגלל חפיפת אות מקרית - בדיוק התקלה
שכבר תועדה ב-packages/amend/engine.py._diff_text ("מאסר ששה חדשים" ->
"מאסר שנה", חפיפה מקרית באות "ש"). לכן prefix_len/suffix_len הגולמיים
מתוקננים ("נצמדים") לגבול מילה *לפני* שממשיכים לשלב הייחודיות - אחרת
אפשר לקבל עוגן/ביטוי שמתחיל או נגמר באמצע מילה, טכנית עקבי (משחזר את
after בייטים) אבל לא ניסוח שאפשר להציג למשתמש.

גבול מילה כאן = רווח, או פיסוק מפריד (. , ; :) - לא רק whitespace,
כדי שנקודה בסוף משפט לא "תידבק" בטעות לביטוי המוחלף (נצפה בפועל:
"ששה חדשים." היה יוצא כביטוי במקום "ששה חדשים" הנקי)."""

import difflib
from dataclasses import dataclass

_BOUNDARY_CHARS = set(" \t\n\r.,;:")


@dataclass
class SupportedInsertWords:
    """הוספת מילים טהורה (שום דבר לא הוסר) - מתאים ל-transform.InsertWordsAfter."""

    anchor_substring: str
    inserted_text: str


@dataclass
class SupportedReplaceWords:
    """החלפת ביטוי (משהו הוסר, גם אם גם נוסף) - מתאים ל-transform.ReplaceWords."""

    old_phrase: str
    new_phrase: str


@dataclass
class SupportedInsertAtStart:
    """הוספה בתחילת היחידה - מדריך משפטים §7.10.2, עמ' 27 [PDF 56]:
    `בסעיף מס' הסעיף לחוק העיקרי, לפני "ציטוט המילים בתחילת הסעיף
    הקיים" יבוא "תוספת".`

    עד לתיקון הזה המקרה הזה הוחזר כ-`Unsupported` ("אין מילה קודמת
    לעגן עליה"), והוא בדיוק החצי הראשון של הבאג שהמשתמש דיווח עליו:
    מילה בתחילת סעיף ומילה בסופו."""

    before_phrase: str
    inserted_text: str


@dataclass
class SupportedAppendAtEnd:
    """הוספה בסוף היחידה - §7.10.2, עמ' 28 [PDF 57]:
    `בסעיף מס' הסעיף לחוק העיקרי, בסופו יבוא "תוספת".`

    **דפוס נפרד מ"אחרי X יבוא Y"**, ולא רק קיצור שלו: עיגון על
    המילה האחרונה היה מייצר `אחרי "עסקים." יבוא "..."` - כלומר
    טקסט אחרי הנקודה הסוגרת."""

    inserted_text: str


@dataclass
class SupportedDeleteWords:
    """מחיקת מילים טהורה (שום דבר לא נוסף במקומן).

    **דפוס נפרד, לא החלפה בריק.** מדריך משפטים §7.10.3, עמ' 28
    [PDF 57]: `בסעיף מס' הסעיף לחוק העיקרי, המילים "ציטוט מהסעיף
    הקיים" – יימחקו.` עד לתיקון הזה מחיקה נפלה לענף ההחלפה ויצאה
    כ-`במקום "X" יבוא ""` - ניסוח שאינו קיים במדריך.

    שימו לב ש**כאן "המילים" כן נכתבת**: היא הנושא הדקדוקי של הפועל,
    ובלעדיה אין למשפט נושא - בניגוד לתפקיד העוגן, שבו היא נעדרת.
    ראו drafting-rules.md §8.7.1."""

    phrase: str


@dataclass
class Unsupported:
    """אי אפשר לבטא את השינוי הזה בבירור כהוראת תיקון - לא ניחוש, סירוב מפורש."""

    reason: str


TranslationResult = (
    SupportedInsertWords | SupportedInsertAtStart | SupportedAppendAtEnd
    | SupportedReplaceWords | SupportedDeleteWords | Unsupported
)


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    limit = min(len(a), len(b))
    while n < limit and a[n] == b[n]:
        n += 1
    return n


def _common_suffix_len(a: str, b: str, max_len: int) -> int:
    n = 0
    while n < max_len and a[len(a) - 1 - n] == b[len(b) - 1 - n]:
        n += 1
    return n


def _is_boundary_char(ch: str) -> bool:
    return ch in _BOUNDARY_CHARS


def _word_boundary_left(text: str, pos: int) -> int:
    """מזיז pos שמאלה (אחורה) עד לגבול מילה (בלי לחצות אותו)."""
    while pos > 0 and not _is_boundary_char(text[pos - 1]):
        pos -= 1
    return pos


def _word_boundary_right(text: str, pos: int) -> int:
    """מזיז pos ימינה (קדימה) עד לגבול מילה (בלי לחצות אותו)."""
    while pos < len(text) and not _is_boundary_char(text[pos]):
        pos += 1
    return pos


def _prev_word_boundary(text: str, pos: int) -> int:
    """הרחבה איטרטיבית שלב אחד אחורה: מדלג על תווי-גבול (רווח/פיסוק)
    ואז חוזר לתחילת המילה שלפניהם."""
    p = pos
    while p > 0 and _is_boundary_char(text[p - 1]):
        p -= 1
    return _word_boundary_left(text, p)


def _next_word_boundary(text: str, pos: int) -> int:
    p = pos
    while p < len(text) and _is_boundary_char(text[p]):
        p += 1
    return _word_boundary_right(text, p)


def _snap_prefix_suffix_to_word_boundaries(
    before: str, after: str, prefix_len: int, suffix_len: int
) -> tuple[int, int]:
    """מתקננת prefix_len/suffix_len (שהם דיף תווי-גרידא) לגבול מילה,
    כדי שהאזור המשתנה לא יתחיל/יסתיים באמצע מילה בגלל חפיפת אות מקרית.
    prefix מצטמצם (אם עצר באמצע מילה, חוזרים לתחילתה); suffix מצטמצם
    גם הוא (אם עצר באמצע מילה, "משחררים" את שאריתה לאזור המשתנה)."""
    if prefix_len > 0 and not _is_boundary_char(before[prefix_len - 1]) and (
        prefix_len < len(before) and not _is_boundary_char(before[prefix_len])
    ):
        prefix_len = _word_boundary_left(before, prefix_len)

    mid_end_before = len(before) - suffix_len
    if (
        mid_end_before < len(before)
        and mid_end_before > 0
        and not _is_boundary_char(before[mid_end_before - 1])
        and not _is_boundary_char(before[mid_end_before])
    ):
        new_mid_end_before = _word_boundary_right(before, mid_end_before)
        suffix_len = len(before) - new_mid_end_before
    return prefix_len, suffix_len


def _expand_until_unique(
    haystack: str, start: int, end: int, *, grow_left: bool, grow_right: bool
) -> str | None:
    """מרחיבה את haystack[start:end] כלפי חוץ (שמאלה/ימינה, לפי הדגלים),
    מילה שלמה בכל שלב, עד שהיא מופיעה פעם אחת בדיוק ב-haystack. מחזירה
    None אם ההרחבה מיצתה את שני הכיוונים בלי להגיע לייחודיות."""
    while True:
        candidate = haystack[start:end]
        if candidate and haystack.count(candidate) == 1:
            return candidate
        new_start = _prev_word_boundary(haystack, start) if grow_left else start
        new_end = _next_word_boundary(haystack, end) if grow_right else end
        if new_start == start and new_end == end:
            return None  # מיצינו את שני הכיוונים - אין עוד לאן להרחיב
        start, end = new_start, new_end




def _collapse_spaces(text: str) -> str:
    """להשוואה בלבד: רווחים שנוצרים או נעלמים סביב הסרת קטע אינם
    הבדל בנוסח. גם רווח שנשאר לפני נקודה ("רשיון .") הוא תיקון
    מכני ולא שינוי משפטי, ולכן ההשוואה מתעלמת מרווחים לגמרי."""
    return "".join(text.split())


def _tokenize(text: str) -> tuple[list[str], list[tuple[int, int]]]:
    """מפרקת לרצפי-מילה עם המיקום של כל אחד. תווי גבול (רווח, פיסוק)
    אינם אסימונים בפני עצמם - הם מה שמפריד ביניהם."""
    words: list[str] = []
    spans: list[tuple[int, int]] = []
    start = None
    for index, char in enumerate(text):
        if char in _BOUNDARY_CHARS:
            if start is not None:
                words.append(text[start:index])
                spans.append((start, index))
                start = None
        elif start is None:
            start = index
    if start is not None:
        words.append(text[start:])
        spans.append((start, len(text)))
    return words, spans


def translate_text_edits(before: str, after: str) -> list[TranslationResult]:
    """עריכה חופשית -> **רשימת** הוראות תיקון, אחת לכל אזור שינוי.

    **זה התיקון לבאג שהמשתמש דיווח עליו (22.9):** הוספת מילה בתחילת
    סעיף ומילה בסופו ייצרה `במקום "<כל הסעיף>" יבוא "<כל הסעיף>"` -
    כלומר החלפה של הסעיף כולו. הסיבה לא הייתה במנגנון שורת-הפתיח
    ב-engine.py אלא **כאן**: `translate_text_edit` מחשבת חלון יחיד
    של prefix/suffix משותפים, ולכן שני שינויים נפרדים בקצוות פורשים
    חלון שמשתרע על כל הטקסט.

    הצורה הנכונה היא כמה תיקונים באותו סעיף - מדריך משפטים §7.10.8,
    עמ' 30 [PDF 59] "תיקונים שלובים בסעיף אחד":
    `בסעיף 5, במקום "שבהם" יבוא "שלגביהם" ובכל מקום, במקום "ייקבעו"
    יבוא "יחושבו".` הפונקציה הזו מחזירה את הפעולות; הניסוח המשולב
    נעשה ב-engine._render_mutation.

    **אזור שינוי אחד -> רשימה באורך 1**, זהה למה ש-translate_text_edit
    הייתה מחזירה. שום התנהגות קיימת לא משתנה במקרה הנפוץ.

    אזור שאי אפשר לתרגם מחזיר `Unsupported` **ברשימה**, ואינו מושמט:
    עריכה שחלקה מתורגם וחלקה נבלע בשקט היא בדיוק הכשל שהמוצר קיים
    כדי למנוע.
    """
    if before == after:
        return [Unsupported("אין שינוי בטקסט")]

    # **ההשוואה על מילים, לא על תווים.** גרסה ראשונה של הפונקציה
    # הזו הריצה SequenceMatcher על תווים, ו"רשיון" -> "היתר" התפצל
    # לשני אזורים בגלל האות "ר" המשותפת: הוספת "הית" והחלפת
    # "רשיון"->"ר". זו בדיוק מלכודת חפיפת-האות המקרית שכבר מתועדת
    # פעמיים במאגר הזה ("מאסר ששה חדשים" -> "מאסר שנה", חפיפה
    # באות "ש"), והיא חזרה ברגע שהוחזרה השוואה תווית.
    before_words, before_spans = _tokenize(before)
    after_words, after_spans = _tokenize(after)
    matcher = difflib.SequenceMatcher(a=before_words, b=after_words, autojunk=False)
    regions: list[tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        start = before_spans[i1][0] if i1 < len(before_spans) else len(before)
        end = before_spans[i2 - 1][1] if i2 > i1 else start
        new_start = after_spans[j1][0] if j1 < len(after_spans) else len(after)
        new_end = after_spans[j2 - 1][1] if j2 > j1 else new_start
        if regions and _only_boundary_between(before, regions[-1][1], start):
            # שני אזורים שמפריד ביניהם רק רווח/פיסוק הם שינוי אחד
            # לכל דבר - פיצולם היה מייצר שתי הוראות על אותה מילה.
            prev = regions[-1]
            regions[-1] = (prev[0], end, prev[2], new_end)
        else:
            regions.append((start, end, new_start, new_end))

    if len(regions) <= 1:
        return [translate_text_edit(before, after)]

    results: list[TranslationResult] = []
    for i1, i2, j1, j2 in regions:
        # כל אזור מתורגם על **הטקסט המלא**, כשרק הוא משתנה - כך
        # העוגן/הביטוי נבדקים לייחודיות מול הצומת כולו, בדיוק כמו
        # בעריכה בודדת, ולא מול קטע מנותק.
        region_after = before[:i1] + after[j1:j2] + before[i2:]
        results.append(translate_text_edit(before, region_after))
    return results


def _only_boundary_between(text: str, start: int, end: int) -> bool:
    """האם בין שני אזורי שינוי יש רק תווי גבול (רווח/פיסוק)?"""
    return start < end and all(c in _BOUNDARY_CHARS for c in text[start:end])


def translate_text_edit(before: str, after: str) -> TranslationResult:
    """גוזרת הוראת תיקון מתוך (before, after) של טקסט צומת בודד, או
    Unsupported אם אי אפשר. before==after (אין שינוי בפועל) הוא גם
    Unsupported - זה לא באמת עריכה."""
    if before == after:
        return Unsupported("אין שינוי בטקסט")

    prefix_len = _common_prefix_len(before, after)
    max_suffix = min(len(before), len(after)) - prefix_len
    suffix_len = _common_suffix_len(before, after, max_suffix)
    prefix_len, suffix_len = _snap_prefix_suffix_to_word_boundaries(
        before, after, prefix_len, suffix_len
    )

    before_middle = before[prefix_len : len(before) - suffix_len]
    after_middle = after[prefix_len : len(after) - suffix_len]

    if before_middle == "":
        # הוספה טהורה: שום דבר לא הוסר מ-before.
        insertion_point = prefix_len
        if insertion_point == 0:
            # הוספה בתחילת הטקסט: אין מילה קודמת לעגן עליה, ולכן
            # מעגנים על המילה **שאחריה** - `לפני "X" יבוא "Y"`
            # (§7.10.2). קודם לכן המקרה הזה הוחזר כ-Unsupported.
            rest = before.lstrip()
            offset = len(before) - len(rest)
            phrase_end = _word_boundary_right(before, offset + 1)
            phrase = _expand_until_unique(
                before, offset, phrase_end, grow_left=False, grow_right=True
            )
            if phrase is None or not phrase.strip():
                return Unsupported(
                    "לא נמצא ביטוי ייחודי בתחילת הטקסט לעגן עליו את ההוספה"
                )
            return SupportedInsertAtStart(
                before_phrase=phrase.strip(), inserted_text=after_middle.strip()
            )
        # הוספה בסוף: אחרי נקודת ההוספה אין עוד אלא סימני פיסוק.
        # `בסופו יבוא` ולא `אחרי "המילה האחרונה." יבוא` (§7.10.2).
        if not before[insertion_point:].strip(" \t\n\r.;:"):
            return SupportedAppendAtEnd(inserted_text=after_middle.strip())
        anchor_start = _word_boundary_left(before, insertion_point)
        anchor = _expand_until_unique(
            before, anchor_start, insertion_point, grow_left=True, grow_right=False
        )
        if anchor is None or not anchor.strip():
            return Unsupported(
                "לא נמצא עוגן ייחודי להוספה (אפילו אחרי הרחבה לכל הטקסט שלפני נקודת ההוספה)"
            )
        return SupportedInsertWords(anchor_substring=anchor, inserted_text=after_middle)

    if after_middle == "":
        # מחיקה טהורה: שום דבר לא נוסף במקום מה שהוסר. **דפוס נפרד**
        # (§7.10.3), לא החלפה בריק - ראו SupportedDeleteWords.
        # **הצמדת הגבולות מבפנים, לא מבחוץ.** האזור שהוסר הוא
        # before[prefix_len:len(before)-suffix_len], ולעתים הוא כולל
        # את הרווח שאחריו - ואז `_word_boundary_right` מרחיבה אל
        # **תוך המילה הבאה**, שכלל לא נמחקה. נצפה בפועל: מחיקת
        # " רישוי" החזירה את הביטוי "רישוי עסקים".
        region_start, region_end = prefix_len, len(before) - suffix_len
        while region_start < region_end and before[region_start] in _BOUNDARY_CHARS:
            region_start += 1
        while region_end > region_start and before[region_end - 1] in _BOUNDARY_CHARS:
            region_end -= 1
        del_start = _word_boundary_left(before, region_start)
        del_end = _word_boundary_right(before, region_end)
        phrase = _expand_until_unique(
            before, del_start, del_end, grow_left=True, grow_right=True
        )
        if phrase is None or not phrase.strip():
            return Unsupported(
                "לא נמצא ביטוי ייחודי למחיקה (אפילו אחרי הרחבה לגבולות מילה)"
            )
        # המחיקה חייבת לשחזר את ה'אחרי' במדויק. רווח כפול שנשאר
        # אחרי ההסרה הוא סימן שגבול המילה נבחר שגוי - לא "כמעט נכון".
        if before.count(phrase) != 1:
            return Unsupported(f'הביטוי "{phrase}" אינו ייחודי בצומת')
        # **חובה לשחזר את ה'אחרי' במדויק.** בלי הבדיקה הזו הרחבת-
        # הייחודיות בולעת מילים שלא נמחקו: מחיקת " לפי חוק רישוי
        # עסקים" החזירה את הביטוי "רשיון לפי חוק רישוי עסקים",
        # כלומר הוראה שמוחקת גם מילה שנשארה בנוסח.
        if _collapse_spaces(before.replace(phrase, "", 1)) != _collapse_spaces(after):
            return Unsupported(
                "המחיקה לא משחזרת את הנוסח המבוקש במדויק - כנראה כמה "
                "עריכות נפרדות באותו צומת"
            )
        return SupportedDeleteWords(phrase=phrase)

    # יש הסרה וגם הוספה - דפוס החלפה.
    old_start = _word_boundary_left(before, prefix_len)
    old_end = _word_boundary_right(before, len(before) - suffix_len)
    old_phrase = _expand_until_unique(
        before, old_start, old_end, grow_left=True, grow_right=True
    )
    if old_phrase is None or not old_phrase.strip():
        return Unsupported(
            "לא נמצא ביטוי ייחודי להחלפה (אפילו אחרי הרחבה לגבולות מילה משני הצדדים)"
        )

    # new_phrase: אותם היסטי-הרחבה (בתווים) חלים גם על after, כי before
    # ו-after חולקים את אותם prefix_len/suffix_len (אחרי התקנון, prefix_len
    # עצמו כבר על גבול מילה - ראו _snap_prefix_suffix_to_word_boundaries).
    left_extra = prefix_len - old_start
    right_extra = old_end - (len(before) - suffix_len)
    new_start = prefix_len - left_extra
    new_end = (len(after) - suffix_len) + right_extra
    new_phrase = after[new_start:new_end]

    reconstructed = before.replace(old_phrase, new_phrase, 1)
    if before.count(old_phrase) != 1 or reconstructed != after:
        return Unsupported(
            "הרחבת הביטוי לא הצליחה לשחזר את הטקסט המבוקש במדויק - "
            "כנראה כמה עריכות נפרדות באותו צומת"
        )
    return SupportedReplaceWords(old_phrase=old_phrase, new_phrase=new_phrase)
