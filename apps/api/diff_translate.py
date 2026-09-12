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
class Unsupported:
    """אי אפשר לבטא את השינוי הזה בבירור כהוראת תיקון - לא ניחוש, סירוב מפורש."""

    reason: str


TranslationResult = SupportedInsertWords | SupportedReplaceWords | Unsupported


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
            # הוספה בתחילת הטקסט - אין מילה קודמת לעגן עליה. יש דפוס
            # "לפני X יבוא Y" במדריך (§7.10.2), אבל transform.py עדיין
            # לא מממש InsertWordsBefore - פער ידוע, לא נתמך כרגע.
            return Unsupported(
                "הוספה בתחילת הטקסט - אין מילה קודמת לעגן עליה (דפוס "
                "'לפני X יבוא Y' לא ממומש עדיין)"
            )
        anchor_start = _word_boundary_left(before, insertion_point)
        anchor = _expand_until_unique(
            before, anchor_start, insertion_point, grow_left=True, grow_right=False
        )
        if anchor is None or not anchor.strip():
            return Unsupported(
                "לא נמצא עוגן ייחודי להוספה (אפילו אחרי הרחבה לכל הטקסט שלפני נקודת ההוספה)"
            )
        return SupportedInsertWords(anchor_substring=anchor, inserted_text=after_middle)

    # יש הסרה (עם או בלי הוספה בצדה) - דפוס החלפה.
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
