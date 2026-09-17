"""amend(before, after, annotations) -> list[Line]. מנוע ה-diff. ראו TASKS.md משימה 4.

טהור: בלי רשת, בלי LLM (חוק ברזל 2). קלט זהה נותן פלט זהה תמיד.

היקף מכוון (לא מנוע כללי): מזהה רק שלושה סוגי שינוי שיש להם מקרה זהב
אמיתי כרגע - הוספת ילד חדש בתוך רשימת ילדיו של סעיף (הגדרה/פסקה
חדשה), הוספת מילים בתוך טקסט קיים של ילד שלא השתנה זהותו, והחלפת
מילים מסומנת במפורש (annotations, ראו transform.py). שינויים אחרים
(מחיקת סעיף, החלפת סעיף שלם, תיקון עקיף וכו') לא נתמכים - יחכו
למקרה זהב משלהם, לפי עקרון "התחל מהטסט" ב-CLAUDE.md.

כמה כללי ניסוח כאן הוסקו ממקרה זהב *יחיד* (חוק הקייטנות) ומסומנים
"מוסק מדוגמה אחת" למטה - ייתכן שידרשו הכללה כשיגיע מקרה שני.

annotations: הידע ה"בתהליך" (ביטוי ישן/חדש שהוחלף, מיקום הפניית הערת
שוליים) מגיע כרשימת FootnoteAnnotation/ReplacementAnnotation (ראו
transform.py) שמצביעות על צמתים לפי id - לא מוטבע כסמן טקסטואלי בתוך
.text. לכן .text בכל צומת, בכל עץ, מכיל נוסח חוק בלבד תמיד; ראו
tests/unit/test_no_marker_leak.py למחסום המבני שאוכף את זה.

provenance (חוק ברזל 3, משימה 5א): כל Line שהמנוע מייצר מקבל
source_node_id ו-as_of (ראו _stamp_provenance) - הצומת ב"לפני" שממנו
נגזרה השורה, ותאריך הנוסח שלו (node.effective_as_of). שני השדות לא
משפיעים על הרינדור - הם קיימים כדי שהוולידטור (משימה 6) יוכל לוודא
שלכל שורה יש provenance, לא כדי לשנות התנהגות.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "render"))
from node import LegislativeNode, effective_as_of, find_sections  # noqa: E402
from numbering import sort_section_numbers  # noqa: E402
from render_bill import Line  # noqa: E402
from transform import Annotation, FootnoteAnnotation, ReplacementAnnotation  # noqa: E402

_QUOTED_TERM_RE = re.compile(r'^"([^"]+)"')


def _quoted_term(text: str) -> str:
    match = _QUOTED_TERM_RE.match(text)
    if not match:
        raise ValueError(f"לא נמצא מונח מצוטט בתחילת: {text!r}")
    return match.group(1)


def _strip_anchor_phrase(text: str) -> str:
    return text.rstrip(" –-")


def _diff_text(before: str, after: str) -> tuple[str, str]:
    """מחזיר (anchor_phrase, inserted_phrase) עבור הכנסה רציפה אחת של
    מילים בתוך טקסט קיים (דפוס "הוספת מילים", drafting-rules.md §1.2).

    מגן מפורש: אם אחרי הסרת ה-prefix/suffix המשותפים נשאר משהו בצד
    ה"לפני" - זו לא הכנסה טהורה אלא **החלפה** (משהו הוסר, לא רק נוסף).
    זוהה בפועל ב-2026-09: מקרה בוחן "מאסר ששה חדשים" -> "מאסר שנה"
    (סעיף 5 בקייטנות) גרם לפונקציה הזו "לחשוב" שרק "נה" הוכנס אחרי
    "...מאסר ש", בגלל חפיפה מקרית של האות "ש" - שורה משפטית שגויה
    שהייתה נכנסת לרנדרר בלי שום שגיאה. מוטציה כזו צריכה ReplacementAnnotation
    (ראו transform.ReplaceWords) - בלעדיה, זו טעות קלט, לא מקרה נתמך.
    """
    max_prefix = min(len(before), len(after))
    prefix_len = 0
    while prefix_len < max_prefix and before[prefix_len] == after[prefix_len]:
        prefix_len += 1
    max_suffix = min(len(before), len(after)) - prefix_len
    suffix_len = 0
    while (
        suffix_len < max_suffix
        and before[len(before) - 1 - suffix_len] == after[len(after) - 1 - suffix_len]
    ):
        suffix_len += 1
    before_middle = before[prefix_len : len(before) - suffix_len]
    if before_middle:
        raise NotImplementedError(
            "החלפת מילים אינה נתמכת עדיין על ידי _diff_text - נדרש דפוס "
            f'"במקום X יבוא Y" (drafting-rules.md §1.1). זוהה טקסט קיים '
            f"שהוסר ולא רק נוסף: {before_middle!r}. יש לבנות את ה'אחרי' דרך "
            "transform.ReplaceWords (מייצרת ReplacementAnnotation), לא ידנית."
        )
    anchor = before[:prefix_len].rstrip()
    inserted = after[prefix_len : len(after) - suffix_len]
    return anchor, inserted


def _validate_replacement(before: str, after: str, replacement: ReplacementAnnotation) -> None:
    """מוודאת עקביות בין ReplacementAnnotation (שהביטויים בה נבחרו
    במפורש על ידי transform.ReplaceWords) לבין before/after בפועל -
    **לא** גוזרת את הגבול בעצמה (ראו TASKS.md משימה 4א: דיף מינימלי
    לא יכול לשמש להחלפה, כי גבול הביטוי הוא החלטת ניסוח משפטית, לא
    עובדה טקסטואלית - זו בדיוק הסיבה ש-ReplacementAnnotation קיימת)."""
    occurrences = before.count(replacement.old_phrase)
    if occurrences != 1:
        raise ValueError(
            f"'{replacement.old_phrase}' אמור להופיע פעם אחת בדיוק בטקסט "
            f"ה'לפני' אבל מופיע {occurrences} פעמים - חוסר עקביות בין "
            "האנוטציה לטקסט בפועל."
        )
    expected_after = before.replace(replacement.old_phrase, replacement.new_phrase, 1)
    if expected_after != after:
        raise ValueError(
            "שחזור ה'אחרי' מתוך ReplacementAnnotation לא תואם את הטקסט "
            "בפועל - חוסר עקביות בין transform.ReplaceWords לבין "
            "before/after שהתקבלו."
        )


@dataclass
class _Insertion:
    anchor: LegislativeNode
    # קובע ניסוח: "בסופו יבוא" מול "אחרי X יבוא". מוכלל ממקרה יחיד: בקייטנות
    # ההוספה האחרונה ברשימת ההוראות גם מעוגנת בילד האחרון של הסעיף - לא
    # נבדק מצב שבו הם נבדלים (הוספה אחרונה שמעוגנת אחרי הגדרה אמצעית, לא
    # בסוף ממש). ראו amend() למטה: is_last_instruction (למספור/terminator)
    # מחושב בנפרד מ-anchor_is_last_child (לניסוח) בדיוק כדי לא לבלבל בין
    # שני המושגים גם אם הם חופפים כרגע.
    anchor_is_last_child: bool
    new_node: LegislativeNode


@dataclass
class _Mutation:
    before_node: LegislativeNode
    before_text: str
    after_text: str

    @property
    def node_id(self) -> str:
        return self.before_node.id


@dataclass
class _MarginTitleMutation:
    """שינוי בכותרת השוליים של סעיף (לא בגוף הטקסט שלו) - ha-hoveret-
    ha-sgula.pdf §7.8. before_node הוא הסעיף עצמו (לא ילד) - הכותרת
    שייכת לסעיף, לא לתוכן שבתוכו. מזוהה בנפרד מ-_diff_section (שמשווה
    רק ילדים) - amend() בודק את זה ישירות ברמת הסעיף."""

    before_node: LegislativeNode
    before_title: str
    after_title: str

    @property
    def node_id(self) -> str:
        return self.before_node.id


@dataclass
class _RelabelAndInsert:
    """סעיף שאין בו עדיין סעיפים קטנים מקבל את הראשון שלו - ראו
    ha-hoveret-ha-sgula.pdf §7.10.6(ד) ב-_diff_section. before_node הוא
    התוכן הקיים כפי שהוא ב"לפני" (בלי תווית); relabeled_number הוא
    התווית שהוא מקבל ("א"); new_node הוא הסעיף הקטן החדש שנוסף אחריו
    ("ב"). זה שני תיקונים נפרדים מבחינה משפטית (סימון + הוספה) שמתלכדים
    לפסקה אחת בניסוח, בדיוק כמו שדפוסי הוספה אחרים מתלכדים - ראו
    _render_relabel_and_insert."""

    before_node: LegislativeNode
    relabeled_number: str
    new_node: LegislativeNode

    @property
    def node_id(self) -> str:
        return self.before_node.id


def _diff_section(before_section: LegislativeNode, after_section: LegislativeNode):
    """משווה את הילדים הישירים (הנורמטיביים) של סעיף בין לפני/אחרי.
    לא יורד רקורסיבית לתוך תת-סעיפים - מספיק למקרה הזהב הנוכחי, שבו
    כל השינויים הם ברמת הילד הישיר של הסעיף."""
    before_children = [c for c in before_section.children if c.is_normative]
    after_children = [c for c in after_section.children if c.is_normative]
    before_ids = [c.id for c in before_children]

    if (
        len(before_children) == 1
        and not before_children[0].number
        and len(after_children) == 2
        and after_children[0].id == before_children[0].id
        and after_children[0].number
        # התנאי האחרון (התוכן הקיים קיבל תווית) הוא ההבחנה החיונית בין
        # דפוס זה לבין הכנסה רגילה של ילד חדש אחרי עוגן לא-ממוספר (למשל
        # הגדרה חדשה אחרי משפט פתיח) - שם after_children[0].number
        # נשאר ריק, כמו ב"לפני". בלעדיו, כל הכנסה כזו הייתה מסווגת
        # (בטעות) כרילייבל - נתפס על ידי tests/unit/test_provenance.py.
    ):
        # סעיף שאין בו עדיין סעיפים קטנים (תוכנו כולו ילד יחיד בלי תווית)
        # מקבל את הסעיף הקטן הראשון שלו - דפוס מובחן מהותית מ"הוספת ילד
        # חדש" הרגיל, כי הוא גם משנה את תווית התוכן הקיים (לא רק מוסיף
        # שכן). ha-hoveret-ha-sgula.pdf §7.10.6(ד), עמ' 29-30 [PDF 58-59],
        # לפי הדוגמה מחוק העונשין, התשל"ז-1977 §6: "בסעיף 6, האמור בו
        # יסומן '(א)' ואחריו יבוא: '(ב) ...'." - נבדק במפורש (לא מונח
        # בשקט) שהתוויות אכן א/ב, כדי לא "לתקן" קלט לא צפוי בניחוש.
        relabeled_number = after_children[0].number
        new_child = after_children[1]
        if relabeled_number != "(א)":
            raise ValueError(
                f"סעיף בלי סעיפים קטנים קיימים אמור לקבל תווית '(א)' לתוכנו "
                f"הקיים (ha-hoveret-ha-sgula.pdf §7.10.6(ד)) - התקבל "
                f"{relabeled_number!r}."
            )
        if new_child.id in before_ids:
            raise NotImplementedError(
                "הילד השני אחרי רילייבל אמור להיות תוכן חדש, לא צומת קיים "
                "- דפוס לא נתמך."
            )
        if new_child.number != "(ב)":
            raise ValueError(
                f"הסעיף הקטן החדש שנוסף אחרי רילייבל אמור להיות תוית '(ב)' "
                f"(ha-hoveret-ha-sgula.pdf §7.10.6(ד)) - התקבל "
                f"{new_child.number!r}."
            )
        return [
            _RelabelAndInsert(
                before_node=before_children[0],
                relabeled_number=relabeled_number,
                new_node=new_child,
            )
        ]

    instructions: list[_Insertion | _Mutation] = []
    for i, child in enumerate(after_children):
        if child.id not in before_ids:
            anchor = after_children[i - 1] if i > 0 else None
            if anchor is None:
                # זו התנהגות נכונה בכוונה, לא פער/פיצ'ר חסר - אסור "לתקן"
                # את זה בעתיד. ha-hoveret-ha-sgula.pdf §7.10.6(א), עמ' 29
                # [PDF 58]: ככלל אסור להוסיף סעיף קטן/פסקה *לפני* הקיים
                # הראשון (לפני סעיף קטן (א) או פסקה (1) קיימים), כי אין
                # דרך לסמן זאת בלי לשנות את מספור הסעיפים הקטנים/הפסקאות
                # הקיימים - ומספור קיים משמש הפניות בחקיקה ובפסיקה אחרת
                # (אותה סיבה בדיוק כמו האיסור על "8א ולא 9" בהוספת סעיף
                # ראשי, §7.12). המדריך מפנה במפורש: יש למקם את התוכן
                # הרצוי בתוך סעיף קטן/פסקה קיימים, באמצע הסעיף, או בסופו.
                raise NotImplementedError(
                    "הוספה לפני הילד הראשון של סעיף אסורה לפי הכלל המשפטי "
                    "עצמו (ha-hoveret-ha-sgula.pdf §7.10.6(א)) - לא רק "
                    "שאין מקרה זהב, אלא שאסור לתמוך בזה: הוספה כזו הייתה "
                    "מחייבת לשנות מספור סעיפים קטנים/פסקאות קיימים, מה "
                    "שפוגע בהפניות קיימות בחקיקה ובפסיקה."
                )
            anchor_is_last_child = anchor.id == before_ids[-1]
            instructions.append(
                _Insertion(anchor=anchor, anchor_is_last_child=anchor_is_last_child, new_node=child)
            )

    before_by_id = {c.id: c for c in before_children}
    for child in after_children:
        prior = before_by_id.get(child.id)
        if prior is not None and prior.text != child.text:
            if prior.node_type == "raw_block":
                # בלוק <table> גולמי (ראו node.py, wikitext_parser
                # ._consume_html_table) - נטען כדי לא לזרוק את כל החוק,
                # אבל לא ניתן לעריכה תכנותית: אין ניסיון לפרק/להשוות
                # מבנה טבלה פנימי, ואין ניחוש של הוראת תיקון עליו. ברק
                # (2026-09-14): "הוראת תיקון על טבלה = NotImplementedError
                # מפורש, לא ניסיון."
                raise NotImplementedError(
                    f"תיקון על תוכן מסוג raw_block (טבלת HTML גולמית, "
                    f"id={prior.id!r}) אינו נתמך - טבלאות נטענות לתצוגה "
                    "בלבד, לא לעריכה תכנותית."
                )
            instructions.append(_Mutation(before_node=prior, before_text=prior.text, after_text=child.text))

    return instructions


def _wrap_new_content(
    text: str, terminator: str, footnote: FootnoteAnnotation | None
) -> tuple[str, str, list[str]]:
    """עוטף תוכן חדש במרכאות (חוק ברזל: מילים חדשות מובאות במרכאות),
    ומפצל בנקודת footnote.offset אם יש הערת שוליים (footnote הוא
    FootnoteAnnotation שמצביע לצומת הזה, ראו transform.py - לא סמן
    מוטבע בטקסט). terminator (';' לפריט לא-אחרון ברשימת ההוספות של
    הסעיף, '.' לפריט האחרון) מתווסף גם מחוץ למרכאות הסוגרות - בלי קשר
    לסימן הפיסוק הפנימי של התוכן עצמו (שנקבע על ידי מחבר הטקסט, לא על
    ידי המנוע - כך נמדד בקובץ הזהב: לתוכן עם כמה משפטים מחוברים
    בפסיקים אין בהכרח סימן פיסוק לפני המרכאה הסוגרת).

    מוכלל ממקרה יחיד: אומת מול 3 הוספות בקייטנות (שתיים עם ';' פנימי
    לפני הסגירה, אחת בלי) - 3 דוגמאות מאותו קובץ, לא 3 מקורות עצמאיים.
    """
    wrapped = f'"{text}"{terminator}'
    if footnote is None:
        return wrapped, "", []
    split_at = footnote.offset + 1  # +1: המרכאה הפותחת שנוספה ב-wrapped
    before_marker = wrapped[:split_at]
    after_marker = wrapped[split_at:]
    return before_marker, after_marker, [footnote.key]


def _wrap_closing_quote_only(
    text: str, terminator: str, footnote: FootnoteAnnotation | None
) -> tuple[str, str, list[str]]:
    """כמו _wrap_new_content, אבל בלי מרכאה פותחת - לדפוס "סעיף פנימי"
    (הוספת סעיף ראשי חדש, drafting-rules.md §8.5) המרכאה הפותחת כבר
    יושבת כתו הראשון של כותרת השוליים (inner_heading, תא נפרד), לא
    בתחילת תא התוכן עצמו - ראו _render_new_section. offset של footnote
    לא זז ב-1 כאן (בניגוד ל-_wrap_new_content) כי לא נוסף תו לפני
    הטקסט."""
    return _split_at_footnote(f'{text}"{terminator}', footnote)


def _split_at_footnote(
    wrapped: str, footnote: FootnoteAnnotation | None
) -> tuple[str, str, list[str]]:
    """מפצלת טקסט לשני חלקים בנקודה שבה יושב סימן הערת השוליים
    (render_bill.render_line מוסיף את הסימן בדיוק בין text ל-text_after).
    בלי הערת שוליים - הטקסט כולו ב-text."""
    if footnote is None:
        return wrapped, "", []
    return wrapped[: footnote.offset], wrapped[footnote.offset :], [footnote.key]


def _new_sections_side_heading(numbers: list[str]) -> str:
    """כותרת השוליים להוספת סעיף חדש אחד או כמה רצופים.

    הצורה לכמה סעיפים ("הוספת סעיפים 2ג ו־2ד") נצפתה בהצעה אמיתית
    שהונחה בכנסת - tests/fixtures/real-bills/13948392.docx, הוראת
    תיקון 1 - עם מקף עברי (U+05BE) ב-"ו־", לא מקף רגיל ולא en-dash.
    לשלושה ומעלה נגזרת הצורה הרגילה בעברית ("א, ב ו־ג"); **זו הכללה
    ולא ציטוט** - בין 40 ההצעות שנבדקו לא נצפתה הוראה אחת שמוסיפה
    שלושה סעיפים רצופים."""
    if len(numbers) == 1:
        return f"הוספת סעיף {numbers[0]}"
    head = ", ".join(numbers[:-1])
    return f"הוספת סעיפים {head} ו\u05be{numbers[-1]}"


def _render_new_sections(
    anchor_number: str,
    new_sections: list[LegislativeNode],
    footnotes: dict[str, FootnoteAnnotation],
    *,
    full_title: str | None = None,
    law_footnote_key: str | None = None,
) -> list[Line]:
    """מנסחת הוספת סעיף ראשי חדש אחד או כמה רצופים - ha-hoveret-ha-sgula.pdf
    §7.12, עמ' 31 [PDF 60]: "בחוק [שם החוק], אחרי סעיף [מספר הסעיף]
    לחוק העיקרי יבוא: 'כותרת שוליים [מספר הסעיף החדש] [תוכן הסעיף].'"
    full_title/law_footnote_key: אותה משמעות כמו ב-_render_mutation/
    _render_relabel_and_insert - מועברים רק כשזו הפעם הראשונה שהחוק
    מוזכר בהצעה (touched_count==1).

    **מרכאות (השאלה הפתוחה ב-drafting-rules.md §8.5, הוכרעה 2026-09-12
    מול reference/skeleton-pshia.docx - הצעה פרטית טרומית אמיתית,
    פ/6158/25, הכנסת 25, לא ניחוש):** כן נושא מרכאות, אבל מרכאה אחת
    בודדת שעוטפת את כל הבלוק המצוטט כיחידה (מהתו הראשון של כותרת
    השוליים ועד התו האחרון של תוכן הסעיף), לא מרכאות נפרדות בכל תא.
    לכן הפותחת מוטבעת כתו הראשון של inner_heading **של הסעיף הראשון
    בלבד**, והסוגרת כתו האחרון של תא התוכן **של האחרון בלבד**: כמה
    סעיפים שנוספים באותה הוראה הם בלוק מצוטט אחד, לא כמה ציטוטים -
    אומת מול tests/fixtures/real-bills/13948392.docx (2ג ו-2ד: מרכאה
    פותחת רק לפני "איסור עיסוק ברבייה...", סוגרת רק בסוף סעיף 2ד)."""
    phrase = f"אחרי סעיף {anchor_number} לחוק העיקרי יבוא:"
    if full_title is not None:
        # מראה המקום (הערת השוליים למקור) חייב לשבת מיד אחרי שם החוק,
        # לפני "(להלן..." - לכן הפיצול ל-text/text_after, לא מחרוזת
        # אחת (ראו render_bill.render_line: מוסיף footnotes בדיוק בין
        # text ל-text_after).
        phrase_line = Line(
            text=f"ב{full_title}",
            text_after=f" (להלן – החוק העיקרי), {phrase}",
            footnotes=[law_footnote_key] if law_footnote_key else [],
            depth=0,
        )
    else:
        phrase_line = Line(text=phrase, depth=0)

    lines = [phrase_line]
    for position, section in enumerate(new_sections):
        is_first = position == 0
        is_last = position == len(new_sections) - 1
        footnote = footnotes.get(section.id)
        # terminator ריק, בניגוד ל-_render_insertion/_render_relabel_and_insert:
        # שם ה-"." החיצוני נחוץ כי התוכן המצוטט עצמו נגמר לפעמים ב-";"
        # (פריט ברשימת הוספות בתוך סעיף קיים וזקוק לחותם משפטי חיצוני).
        # כאן זו הוראה עצמאית ("אחרי סעיף X לחוק העיקרי יבוא:"), לא פריט
        # ברשימה - אומת מול reference/skeleton-pshia.docx: המרכאה הסוגרת
        # שם היא התו האחרון ממש בתא, בלי תו נוסף אחריה (התוכן המצוטט עצמו
        # כבר מסתיים בנקודה משלו, כמשפט משפטי שלם).
        if is_last:
            body_text, body_after, keys = _wrap_closing_quote_only(section.text, "", footnote)
        else:
            body_text, body_after, keys = _split_at_footnote(section.text, footnote)
        margin = section.margin_title or ""
        lines.append(
            Line(
                text=body_text,
                text_after=body_after,
                footnotes=keys,
                style="TableBlock",
                inner_heading=f'"{margin}' if is_first else margin,
                inner_number=f"{section.number}.",
                depth=0,
            )
        )
    return lines


def _render_new_section(
    anchor_number: str,
    new_section: LegislativeNode,
    footnote: FootnoteAnnotation | None,
    *,
    full_title: str | None = None,
    law_footnote_key: str | None = None,
) -> list[Line]:
    """עטיפה לסעיף חדש בודד - ראו _render_new_sections."""
    return _render_new_sections(
        anchor_number,
        [new_section],
        {new_section.id: footnote} if footnote else {},
        full_title=full_title,
        law_footnote_key=law_footnote_key,
    )


def _render_insertion(
    insertion: _Insertion, terminator: str, ordinal: int, footnote: FootnoteAnnotation | None
) -> list[Line]:
    anchor = insertion.anchor
    if insertion.anchor_is_last_child:
        # מוסק מדוגמה אחת: הוספה בסוף הרשימה מקבלת מספר-פסקה מפורש (המיקום
        # הסידורי שלה בין הוראות התיקון של הסעיף), כי אין לה עוגן טקסטואלי
        # ספציפי שמזהה אותה (ראו drafting-rules.md §1.2 "הוספה בסוף").
        phrase_line = Line(marker=f"({ordinal})", text="בסופו יבוא:", depth=0)
    elif anchor.node_type == "definition":
        term = _quoted_term(anchor.text)
        phrase_line = Line(text=f'אחרי ההגדרה "{term}" יבוא:', depth=0)
    elif anchor.node_type == "subsection" and anchor.number:
        # תוקן (באג, לא פיצ'ר): עוגן ממוספר (סעיף קטן/פסקה) מעוגן לפי
        # התווית שלו, לא לפי ציטוט הטקסט המלא - ha-hoveret-ha-sgula.pdf
        # §7.10.6(ב), עמ' 29: "אחרי סעיף קטן (ג) יבוא: '(ג1)...'". עד
        # לתיקון זה, _render_insertion ציטט תמיד את טקסט העוגן המלא גם
        # כשהיה לו מספר - ניסוח שגוי שהיה יוצא מהמערכת בפועל (עדיין לא
        # נתפס במקרה הזהב של קייטנות, ששם כל העוגנים שם היו לא-ממוספרים
        # - הגדרה או פתיח).
        #
        # anchor.number כבר כולל סוגריים משלו ("(ג)") - כך בדיוק הוא
        # מגיע מ-wikitext_parser (הארגומנט הגולמי בתבנית כולל את
        # הסוגריים, ראו _SUBSECTION_LABEL/_PARAGRAPH_LABEL). קודם
        # התיקון הזה הוספנו כאן עוד זוג סוגריים ("((ג))") - באג אמיתי
        # שנתפס רק כשמשתמש בדק את זה מול חוק אמיתי (לא fixture סינתטי
        # עם תוויות בלי סוגריים).
        phrase_line = Line(text=f'אחרי סעיף קטן {anchor.number} יבוא:', depth=0)
    elif anchor.node_type == "paragraph" and anchor.number:
        # אותו תיקון, לפסקה - §7.10.6(ב), עמ' 29: "אחרי פסקה (2) יבוא:
        # '(2א)...'".
        phrase_line = Line(text=f'אחרי פסקה {anchor.number} יבוא:', depth=0)
    else:
        # עוגן בלי מספר (הגדרה טופלה למעלה; כאן: פתיח/פסקה בלי תווית) -
        # ציטוט הטקסט, כפי שהיה תמיד (drafting-rules.md §1.2).
        phrase = _strip_anchor_phrase(anchor.text)
        phrase_line = Line(text=f'אחרי "{phrase}" יבוא:', depth=0)

    new_node = insertion.new_node
    label_prefix = ""
    if new_node.node_type in ("subsection", "paragraph") and new_node.number:
        # תוקן (באג, לא פיצ'ר): התווית של הסעיף הקטן/פסקה החדשים היא
        # חלק מנוסח החוק עצמו שמצוטט - צריכה להופיע בתוך המרכאות, בדיוק
        # כפי שדוגמאות המדריך עצמן כתובות ("(ג1) תוכן הסעיף הקטן החדש").
        # עד לתיקון זה, התוכן המצוטט לא כלל את התווית בכלל.
        label_prefix = f"{new_node.number} "
    content_source = label_prefix + new_node.text
    adjusted_footnote = footnote
    if footnote is not None and label_prefix:
        # ה-offset של footnote חושב יחסית ל-new_node.text הנקי (ראו
        # transform.apply) - עם prefix התווית צריך להזיז אותו באותו
        # אורך, אחרת ההפניה תנחת במקום הלא נכון בטקסט המצוטט.
        adjusted_footnote = FootnoteAnnotation(
            node_id=footnote.node_id, offset=footnote.offset + len(label_prefix), key=footnote.key
        )
    text, text_after, footnotes = _wrap_new_content(content_source, terminator, adjusted_footnote)
    content_line = Line(
        text=text, text_after=text_after, footnotes=footnotes, style="TableBlockOutdent", depth=0
    )
    return [phrase_line, content_line]


def _render_relabel_and_insert(
    section_number: str,
    item: _RelabelAndInsert,
    footnote: FootnoteAnnotation | None,
    *,
    full_title: str | None = None,
    law_footnote_key: str | None = None,
) -> list[Line]:
    """מנסחת "האמור בו יסומן... ואחריו יבוא:" - ha-hoveret-ha-sgula.pdf
    §7.10.6(ד), עמ' 29-30 [PDF 58-59], לפי הדוגמה מחוק העונשין,
    התשל"ז-1977 §6. full_title/law_footnote_key: אותה משמעות כמו
    ב-_render_mutation - מועברים רק כשזו הפעם הראשונה שהחוק מוזכר
    בהצעה (touched_count==1)."""
    # item.relabeled_number כבר כולל סוגריים משלו ("(א)") - תוקן (באג,
    # לא פיצ'ר) יחד עם transform.AddFirstSubsection, שקודם קבע number
    # בלי סוגריים ("א"), לא תואם את הפורמט האמיתי מ-wikitext_parser.
    phrase = f'האמור בו יסומן "{item.relabeled_number}" ואחריו יבוא:'
    if full_title is not None:
        # ראו הערה מקבילה ב-_render_new_section: מראה המקום חייב לשבת
        # מיד אחרי שם החוק, לפני "(להלן...".
        phrase_line = Line(
            text=f"ב{full_title}",
            text_after=f" (להלן – החוק העיקרי), בסעיף {section_number}, {phrase}",
            footnotes=[law_footnote_key] if law_footnote_key else [],
            depth=0,
        )
    else:
        text = f"בסעיף {section_number} לחוק העיקרי, {phrase}"
        phrase_line = Line(text=text, depth=0)

    # התווית של הסעיף הקטן החדש ("(ב)") היא חלק מנוסח החוק עצמו שמצוטט -
    # מופיעה בתוך המרכאות, בדיוק כפי שדוגמאות המדריך עצמן כתובות (למשל
    # "(ג1) תוכן הסעיף הקטן החדש", "(ב) תוכן הסעיף הקטן החדש") - לא
    # שדה marker נפרד, כי אין עדיין מקרה זהב אמיתי שמראה איך marker
    # מתנהג עבור תווית סעיף-קטן (marker הקיים משמש למספר-פסקת-ההוראה
    # הסידורי בתוך הצעת החוק, ראו _render_insertion, לא לתווית המשפטית).
    labeled_content = f"{item.new_node.number} {item.new_node.text}"
    content_text, content_after, footnotes = _wrap_new_content(labeled_content, ".", footnote)
    content_line = Line(
        text=content_text,
        text_after=content_after,
        footnotes=footnotes,
        style="TableBlockOutdent",
        depth=0,
    )
    return [phrase_line, content_line]


def _render_mutation(
    section_number: str,
    mutation: _Mutation,
    replacement: ReplacementAnnotation | None,
    *,
    full_title: str | None = None,
    law_footnote_key: str | None = None,
) -> Line:
    """full_title/law_footnote_key: מועברים רק כשזו הפעם הראשונה שהחוק
    מוזכר בהצעה (touched_count==1), גם כשמדובר במוטציה בודדת. תוקן ב-
    TASKS.md משימה 6א: לפני התיקון, הענף "מוטציה בודדת מתלכדת לשורה
    אחת" (למטה, ב-amend()) מעולם לא בנה את הכותרת "(להלן – החוק
    העיקרי)" - בין אם זה היה הסעיף הראשון שנוגעים בו ובין אם לא. זו
    הייתה טעות מבנית: התנאי הנכון הוא "פעם ראשונה שהחוק מוזכר בהצעה",
    לא "איזה ענף מטפל בסעיף הזה". הוולידטור (בדיקה 3) תפס את זה על
    הצעה שמתקנת סעיף יחיד בהחלפת מילים - בדיוק המקרה הנפוץ ביותר
    בהצעות פרטיות טרומיות.

    כשהקיצור "(להלן – החוק העיקרי)" מוגדר באותה שורה, הוא לא משמש שוב
    בה: "בסעיף N," ולא "בסעיף N לחוק העיקרי," (ראו מקרה הזהב, סעיף 5)."""
    if replacement is not None:
        # דפוס "החלפת מילים" (drafting-rules.md §1.1 שורה 1) - הביטויים
        # מגיעים מ-ReplacementAnnotation, לא נגזרים מדיף.
        _validate_replacement(mutation.before_text, mutation.after_text, replacement)
        body = f'במקום "{replacement.old_phrase}" יבוא "{replacement.new_phrase}".'
    else:
        anchor, inserted = _diff_text(mutation.before_text, mutation.after_text)
        anchor, inserted = anchor.strip(), inserted.strip()
        body = f'אחרי המילים "{anchor}" יבוא "{inserted}".'

    if full_title is not None:
        # ראו הערה מקבילה ב-_render_new_section: מראה המקום חייב לשבת
        # מיד אחרי שם החוק, לפני "(להלן...".
        return Line(
            text=f"ב{full_title}",
            text_after=f" (להלן – החוק העיקרי), בסעיף {section_number}, {body}",
            footnotes=[law_footnote_key] if law_footnote_key else [],
            depth=0,
        )

    text = f"בסעיף {section_number} לחוק העיקרי, {body}"
    return Line(text=text, depth=0)


def _render_margin_title_mutation(
    section_number: str,
    mutation: _MarginTitleMutation,
    replacement: ReplacementAnnotation | None,
    *,
    full_title: str | None = None,
    law_footnote_key: str | None = None,
) -> Line:
    """שינוי כותרת שוליים - ha-hoveret-ha-sgula.pdf §7.8, עמ' 26 [PDF 55]:
    "בסעיף מס' הסעיף לחוק העיקרי, בכותרת השוליים, במקום 'טקסט קיים'
    יבוא 'טקסט חדש'". דורש ReplacementAnnotation מפורש, בדיוק כמו
    _render_mutation לגוף הטקסט - אין דיף אוטומטי לכותרות שוליים (אין
    עדיין מקרה זהב שמצדיק לבנות דיף כזה, ואותה בעיית גבול-ביטוי
    שכבר תועדה עבור טקסט רגיל חלה באותה מידה כאן)."""
    if replacement is None:
        raise NotImplementedError(
            "שינוי כותרת שוליים בלי ReplacementAnnotation מפורש - אין "
            "עדיין דיף אוטומטי לכותרות שוליים (ראו transform."
            "ReplaceMarginTitleWords). לא ניחוש."
        )
    _validate_replacement(mutation.before_title, mutation.after_title, replacement)
    body = f'בכותרת השוליים, במקום "{replacement.old_phrase}" יבוא "{replacement.new_phrase}".'

    if full_title is not None:
        # ראו הערה מקבילה ב-_render_new_section: מראה המקום חייב לשבת
        # מיד אחרי שם החוק, לפני "(להלן...".
        return Line(
            text=f"ב{full_title}",
            text_after=f" (להלן – החוק העיקרי), בסעיף {section_number}, {body}",
            footnotes=[law_footnote_key] if law_footnote_key else [],
            depth=0,
        )

    text = f"בסעיף {section_number} לחוק העיקרי, {body}"
    return Line(text=text, depth=0)


def _find_by_id(node: LegislativeNode, node_id: str) -> LegislativeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find_by_id(child, node_id)
        if found:
            return found
    return None


def _stamp_provenance(line: Line, source: LegislativeNode, before_root: LegislativeNode) -> Line:
    """ממלאת source_node_id/as_of על Line (חוק ברזל 3, משימה 5א) - הצומת
    ב'לפני' שממנו נגזרה השורה (מוטציה: הצומת שהוחלף/הוכנסו בו מילים;
    הכנסה: העוגן שאחריו מוכנס תוכן חדש; כותרת סעיף: הסעיף/השורש עצמו).
    לא נוגעת ברינדור - שני השדות לא נקראים על ידי render_bill.py."""
    line.source_node_id = source.id
    line.as_of = effective_as_of(before_root, source)
    return line


def amend(
    before: LegislativeNode,
    after: LegislativeNode,
    annotations: list[Annotation] | None = None,
    *,
    law_footnote_key: str,
) -> list[Line]:
    """משווה שני עצי LegislativeNode של אותו חוק ומחזיר רשימת Line
    (ראו packages/render/render_bill.py) - הוראות תיקון מוכנות לרינדור.

    annotations: הרשימה שהוחזרה מ-transform.apply() לצד after - הידע
    ה"בתהליך" (ביטוי ישן/חדש, מיקום הערת שוליים) שלא מוטבע ב-.text.
    law_footnote_key: מפתח הערת השוליים לחוק עצמו (מראה מקום), כפי
    שמוגדר בטבלת REFS החיצונית - זה חלק מהחיווט הכללי של הצעת החוק,
    לא נגזר מהעץ עצמו.
    """
    annotations = annotations or []
    replacements_by_id = {
        a.node_id: a for a in annotations if isinstance(a, ReplacementAnnotation)
    }
    footnotes_by_id = {a.node_id: a for a in annotations if isinstance(a, FootnoteAnnotation)}

    # תוקן (2026-09-16): רקורסיבי בכל עומק, לא רק before.children/
    # after.children - ראו find_sections (node.py) להסבר המלא. חוק
    # עם מבנה חלק/פרק/סימן פשוט לא היה "נראה" כאן בכלל.
    before_sections = find_sections(before)
    after_sections = find_sections(after)

    # תוקן (פער, לא רק דפוס לא ממומש - ראו drafting-rules.md §8.5): עד
    # כאן הלולאה עברה רק על before_sections.keys(), כך שסעיף ראשי חדש
    # לגמרי (לא קיים ב"לפני" בכלל, לא רק שינוי בתוך סעיף קיים) היה
    # בלתי-נראה למנוע - מפיק אפס פלט בשקט, לא שגיאה. all_numbers כולל
    # גם מספרי סעיפים חדשים; sort_section_numbers כבר יודע למיין "8א"
    # מיד אחרי "8" (packages/corpus/numbering.py), כך שהשכן הקודם של
    # סעיף חדש ב-all_numbers הוא תמיד העוגן הסמנטי הנכון.
    all_numbers = sort_section_numbers(list(set(before_sections) | set(after_sections)))

    # קיבוץ סעיפים חדשים רצופים להוראת תיקון אחת (2026-09-17). עד כאן
    # שני סעיפים חדשים זה אחרי זה נחסמו ב-NotImplementedError מפורש -
    # "היקף שלא נכלל" לפי §8.5. הביקורת מול 40 ההצעות האמיתיות מצאה
    # שזהו הפער הנפוץ ביותר: הצעה אמיתית מוסיפה שני סעיפים רצופים
    # בהוראה אחת עם כותרת "הוספת סעיפים 2ג ו־2ד"
    # (tests/fixtures/real-bills/13948392.docx). המפתח הוא המספר הראשון
    # ברצף, הערך הוא כל הרצף; שאר חברי הרצף נדלגים בלולאה כי כבר טופלו.
    new_runs: dict[str, list[str]] = {}
    covered_by_run: set[str] = set()
    position = 0
    while position < len(all_numbers):
        if all_numbers[position] in before_sections:
            position += 1
            continue
        end = position
        while end < len(all_numbers) and all_numbers[end] not in before_sections:
            end += 1
        run = all_numbers[position:end]
        new_runs[run[0]] = run
        covered_by_run.update(run[1:])
        position = end

    lines: list[Line] = []
    touched_count = 0
    for idx, number in enumerate(all_numbers):
        if number in covered_by_run:
            continue  # טופל כבר כחלק מקבוצת ההוספה שנפתחה בסעיף קודם
        if number not in before_sections:
            if idx == 0:
                raise NotImplementedError(
                    f"סעיף {number} חדש בלי אף סעיף קודם קיים ב'לפני' אינו "
                    "נתמך - אין עוגן קיים להוראת 'אחרי סעיף X לחוק העיקרי "
                    "יבוא'."
                )
            # number הוא ראש רצף, ולכן קודמו ב-all_numbers אינו חדש -
            # העוגן קיים תמיד ב'לפני'. אין כאן הנחה שקטה: הבנייה של
            # new_runs היא שמבטיחה את זה.
            anchor_number = all_numbers[idx - 1]
            run_numbers = new_runs[number]
            touched_count += 1
            run_sections = [after_sections[n] for n in run_numbers]
            if touched_count == 1:
                new_lines = _render_new_sections(
                    anchor_number, run_sections, footnotes_by_id,
                    full_title=before.full_title or "", law_footnote_key=law_footnote_key,
                )
            else:
                new_lines = _render_new_sections(anchor_number, run_sections, footnotes_by_id)
            new_lines[0].side_heading = _new_sections_side_heading(run_numbers)
            # תוקן (באג אמיתי, לא מוסכמה): golden-kaytanot.docx משאיר את
            # הסעיף הראשון שנוגעים בו בלי מספר בכלל - הוכח שגוי מול
            # reference/skeleton-pshia.docx (הצעה אמיתית שאומתה מול ה-API
            # של הכנסת), ששם הוראת התיקון הראשונה ממוספרת "1." כרגיל.
            # קובץ הזהב עצמו כנראה הוקלד ידנית עם השמטה - לא תבנית.
            new_lines[0].number = f"{touched_count}."
            anchor_before_node = before_sections[anchor_number]
            for new_line in new_lines:
                _stamp_provenance(new_line, anchor_before_node, before)
            lines.extend(new_lines)
            continue

        instructions = _diff_section(before_sections[number], after_sections[number])
        # שינוי בכותרת השוליים של הסעיף עצמו (§7.8) - לא נבדק בתוך
        # _diff_section (שמשווה רק ילדים; הכותרת שייכת לסעיף עצמו).
        # נבדק כאן ישירות ומתווסף בתחילת רשימת ההוראות - סדר קריאה
        # טבעי (כותרת לפני תוכן), ואין מקרה זהב שקובע אחרת.
        before_sec = before_sections[number]
        after_sec = after_sections[number]
        if before_sec.margin_title != after_sec.margin_title:
            instructions = [
                _MarginTitleMutation(
                    before_node=before_sec,
                    before_title=before_sec.margin_title or "",
                    after_title=after_sec.margin_title or "",
                )
            ] + instructions
        if not instructions:
            continue
        touched_count += 1

        if len(instructions) == 1 and isinstance(instructions[0], _MarginTitleMutation):
            # מוסק מדפוס _Mutation: שינוי כותרת שוליים בודד מתלכד לשורה
            # אחת, באותו אופן בדיוק שמוטציית טקסט בודדת מתלכדת.
            replacement = replacements_by_id.get(instructions[0].node_id)
            if touched_count == 1:
                title_line = _render_margin_title_mutation(
                    number, instructions[0], replacement,
                    full_title=before.full_title or "", law_footnote_key=law_footnote_key,
                )
            else:
                title_line = _render_margin_title_mutation(number, instructions[0], replacement)
            title_line.side_heading = f"תיקון סעיף {number}"
            title_line.number = f"{touched_count}."
            _stamp_provenance(title_line, instructions[0].before_node, before)
            lines.append(title_line)
            continue

        if len(instructions) == 1 and isinstance(instructions[0], _Mutation):
            # מוסק מדוגמה אחת: מוטציה בודדת מתלכדת לשורה אחת (סעיף 2),
            # לעומת הוספות שמקבלות שורת פתיח נפרדת (סעיף 1). לא ברור
            # מה בדיוק מפעיל את ההתלכדות - "מוטציה יחידה" (בלי קשר לסעיף)
            # או "סעיף שאינו הראשון שנוגעים בו"? בקייטנות שני התנאים
            # חופפים (סעיף 2 הוא גם מוטציה יחידה וגם לא-ראשון) ואי אפשר
            # להפריד ביניהם ממקרה אחד.
            replacement = replacements_by_id.get(instructions[0].node_id)
            if touched_count == 1:
                # תוקן במשימה 6א: התנאי ל"החוק מוזכר בפעם הראשונה" הוא
                # touched_count==1, בלי קשר לאיזה ענף מטפל בסעיף - ראו
                # תיעוד ב-_render_mutation.
                mutation_line = _render_mutation(
                    number,
                    instructions[0],
                    replacement,
                    full_title=before.full_title or "",
                    law_footnote_key=law_footnote_key,
                )
            else:
                mutation_line = _render_mutation(number, instructions[0], replacement)
            mutation_line.side_heading = f"תיקון סעיף {number}"
            mutation_line.number = f"{touched_count}."
            _stamp_provenance(mutation_line, instructions[0].before_node, before)
            lines.append(mutation_line)
            continue

        if len(instructions) == 1 and isinstance(instructions[0], _RelabelAndInsert):
            # סעיף שאין בו עדיין סעיפים קטנים מקבל את הראשון שלו - ראו
            # ha-hoveret-ha-sgula.pdf §7.10.6(ד) ב-_diff_section. מתלכד
            # לפסקה אחת (שתי שורות: פתיח + תוכן מצוטט), באותו אופן
            # שהתלכדות _Mutation למעלה מתלכדת - ראו שם.
            item = instructions[0]
            footnote = footnotes_by_id.get(item.new_node.id)
            if touched_count == 1:
                relabel_lines = _render_relabel_and_insert(
                    number, item, footnote,
                    full_title=before.full_title or "",
                    law_footnote_key=law_footnote_key,
                )
            else:
                relabel_lines = _render_relabel_and_insert(number, item, footnote)
            relabel_lines[0].side_heading = f"תיקון סעיף {number}"
            relabel_lines[0].number = f"{touched_count}."
            for relabel_line in relabel_lines:
                _stamp_provenance(relabel_line, item.before_node, before)
            lines.extend(relabel_lines)
            continue

        if touched_count == 1:
            # הכלל "רק הסעיף הראשון שנוגעים בו מקבל את שם החוק המלא" תואם
            # drafting-rules.md §7.3 במפורש - הכי מבוסס ברשימת הכללים כאן,
            # לא רק ניחוש ממקרה אחד.
            header = Line(
                side_heading=f"תיקון סעיף {number}",
                # הוכרע במשימה 6א: full_title (מ-{{ח:כותרת}}) משתמש תמיד
                # ב-en-dash (–) לשנה עברית, בלי המרה למקף רגיל - ראו
                # drafting-rules.md §6.1. קובץ הזהב עצמו (golden-kaytanot.docx)
                # מכיל מקף רגיל בשורה הזו בלבד, לעומת en-dash בשלושה מקומות
                # עצמאיים אחרים באותו מסמך (כולל אזכור נפרד של אותה שנה בדברי
                # ההסבר) - שגיאת הקלדה חד-פעמית בקובץ המקור, לא מוסכמה.
                # המערכת לא משחזרת את השגיאה הזו.
                number=f"{touched_count}.",
                text="ב" + (before.full_title or ""),
                text_after=f" (להלן – החוק העיקרי), בסעיף {number} – ",
                footnotes=[law_footnote_key],
                depth=0,
            )
            _stamp_provenance(header, before, before)
        else:
            header = Line(
                side_heading=f"תיקון סעיף {number}",
                number=f"{touched_count}.",
                text=f"בסעיף {number} לחוק העיקרי – ",
                depth=0,
            )
            _stamp_provenance(header, before_sections[number], before)
        lines.append(header)

        for i, instruction in enumerate(instructions):
            if isinstance(instruction, _Insertion):
                terminator = "." if i == len(instructions) - 1 else ";"
                footnote = footnotes_by_id.get(instruction.new_node.id)
                insertion_lines = _render_insertion(
                    instruction, terminator, ordinal=i + 1, footnote=footnote
                )
                # instruction.anchor הוא צומת מעץ ה"אחרי" (ראו _diff_section) -
                # provenance צריך את המקבילה שלו ב"לפני" בפועל, כדי ש-
                # effective_as_of יוכל לטפס מהשורש האמיתי. אם העוגן עצמו הוכנס
                # זה עתה (הכנסה משורשרת אחרי הוספה חדשה) - אין לו מקבילה
                # ב"לפני" ואין מקרה זהב עדיין למצב הזה.
                before_anchor = _find_by_id(before, instruction.anchor.id)
                if before_anchor is None:
                    raise NotImplementedError(
                        f"עוגן {instruction.anchor.id!r} אינו צומת קיים ב'לפני' "
                        "(כנראה הכנסה משורשרת אחרי הוספה חדשה) - אין מקרה זהב "
                        "עדיין ל-provenance במצב הזה."
                    )
                for insertion_line in insertion_lines:
                    _stamp_provenance(insertion_line, before_anchor, before)
                lines.extend(insertion_lines)
            elif isinstance(instruction, _MarginTitleMutation):
                replacement = replacements_by_id.get(instruction.node_id)
                title_line = _render_margin_title_mutation(number, instruction, replacement)
                _stamp_provenance(title_line, instruction.before_node, before)
                lines.append(title_line)
            else:
                replacement = replacements_by_id.get(instruction.node_id)
                mutation_line = _render_mutation(number, instruction, replacement)
                _stamp_provenance(mutation_line, instruction.before_node, before)
                lines.append(mutation_line)

    _drop_principal_law_alias_if_single(lines, touched_count)
    return lines


_PRINCIPAL_ALIAS = " (להלן – החוק העיקרי)"


def _drop_principal_law_alias_if_single(lines: list[Line], touched_count: int) -> None:
    """מסירה את "(להלן – החוק העיקרי)" כשיש הוראת תיקון אחת בלבד.

    **ממצא מ-40 הצעות חוק אמיתיות שהונחו בכנסת ה-25** (ראו
    drafting-rules.md §5.8): מתוך 22 ההצעות המתקנות, רק 10 מגדירות
    את הקיצור - ו-12 פותחות ישירות בשם החוק המלא. ההבדל אינו
    שרירותי: הקיצור נועד לחסוך חזרה על שם החוק, ולכן הוא מופיע רק
    כשיש **יותר מהוראת תיקון אחת** לאותו חוק. בתיקון יחיד אין למה
    לקצר, והניסוח המקובל הוא "בחוק X, התשנ\"ט–1999, בסעיף N –".

    עד לתיקון הזה המערכת ייצרה את הקיצור תמיד, כלומר **ניסוח שגוי
    דווקא במקרה הנפוץ ביותר** - הצעה פרטית שמתקנת סעיף אחד.

    המימוש הוא מעבר אחרי הלולאה ולא תנאי בתוכה, כדי שלא יוכל
    להתנתק מהלוגיקה שקובעת מה נספר כהוראת תיקון."""
    if touched_count > 1:
        return
    for line in lines:
        if _PRINCIPAL_ALIAS in line.text_after:
            line.text_after = line.text_after.replace(_PRINCIPAL_ALIAS, "", 1)
            return
