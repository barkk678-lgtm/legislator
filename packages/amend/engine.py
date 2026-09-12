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
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "render"))
from node import LegislativeNode  # noqa: E402
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
    node_id: str
    before_text: str
    after_text: str


def _diff_section(before_section: LegislativeNode, after_section: LegislativeNode):
    """משווה את הילדים הישירים (הנורמטיביים) של סעיף בין לפני/אחרי.
    לא יורד רקורסיבית לתוך תת-סעיפים - מספיק למקרה הזהב הנוכחי, שבו
    כל השינויים הם ברמת הילד הישיר של הסעיף."""
    before_children = [c for c in before_section.children if c.is_normative]
    after_children = [c for c in after_section.children if c.is_normative]
    before_ids = [c.id for c in before_children]

    instructions: list[_Insertion | _Mutation] = []
    for i, child in enumerate(after_children):
        if child.id not in before_ids:
            anchor = after_children[i - 1] if i > 0 else None
            if anchor is None:
                raise NotImplementedError(
                    "הוספה בתחילת סעיף (לפני הילד הראשון) - אין מקרה זהב עדיין"
                )
            anchor_is_last_child = anchor.id == before_ids[-1]
            instructions.append(
                _Insertion(anchor=anchor, anchor_is_last_child=anchor_is_last_child, new_node=child)
            )

    before_by_id = {c.id: c for c in before_children}
    for child in after_children:
        prior = before_by_id.get(child.id)
        if prior is not None and prior.text != child.text:
            instructions.append(_Mutation(node_id=child.id, before_text=prior.text, after_text=child.text))

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
    else:
        phrase = _strip_anchor_phrase(anchor.text)
        phrase_line = Line(text=f'אחרי "{phrase}" יבוא:', depth=0)

    text, text_after, footnotes = _wrap_new_content(insertion.new_node.text, terminator, footnote)
    content_line = Line(
        text=text, text_after=text_after, footnotes=footnotes, style="TableBlockOutdent", depth=0
    )
    return [phrase_line, content_line]


def _render_mutation(
    section_number: str, mutation: _Mutation, replacement: ReplacementAnnotation | None
) -> Line:
    if replacement is not None:
        # דפוס "החלפת מילים" (drafting-rules.md §1.1 שורה 1) - הביטויים
        # מגיעים מ-ReplacementAnnotation, לא נגזרים מדיף.
        _validate_replacement(mutation.before_text, mutation.after_text, replacement)
        text = (
            f'בסעיף {section_number} לחוק העיקרי, במקום "{replacement.old_phrase}" '
            f'יבוא "{replacement.new_phrase}".'
        )
        return Line(text=text, depth=0)
    anchor, inserted = _diff_text(mutation.before_text, mutation.after_text)
    anchor, inserted = anchor.strip(), inserted.strip()
    text = f'בסעיף {section_number} לחוק העיקרי, אחרי המילים "{anchor}" יבוא "{inserted}".'
    return Line(text=text, depth=0)


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

    before_sections = {c.number: c for c in before.children if c.node_type == "section"}
    after_sections = {c.number: c for c in after.children if c.node_type == "section"}

    lines: list[Line] = []
    touched_count = 0
    for number in sort_section_numbers(list(before_sections.keys())):
        instructions = _diff_section(before_sections[number], after_sections[number])
        if not instructions:
            continue
        touched_count += 1

        if len(instructions) == 1 and isinstance(instructions[0], _Mutation):
            # מוסק מדוגמה אחת: מוטציה בודדת מתלכדת לשורה אחת (סעיף 2),
            # לעומת הוספות שמקבלות שורת פתיח נפרדת (סעיף 1). לא ברור
            # מה בדיוק מפעיל את ההתלכדות - "מוטציה יחידה" (בלי קשר לסעיף)
            # או "סעיף שאינו הראשון שנוגעים בו"? בקייטנות שני התנאים
            # חופפים (סעיף 2 הוא גם מוטציה יחידה וגם לא-ראשון) ואי אפשר
            # להפריד ביניהם ממקרה אחד.
            replacement = replacements_by_id.get(instructions[0].node_id)
            mutation_line = _render_mutation(number, instructions[0], replacement)
            mutation_line.side_heading = f"תיקון סעיף {number}"
            if touched_count > 1:
                mutation_line.number = f"{touched_count}."
            lines.append(mutation_line)
            continue

        if touched_count == 1:
            # הכלל "רק הסעיף הראשון שנוגעים בו מקבל את שם החוק המלא" תואם
            # drafting-rules.md §7.3 במפורש - הכי מבוסס ברשימת הכללים כאן,
            # לא רק ניחוש ממקרה אחד.
            header = Line(
                side_heading=f"תיקון סעיף {number}",
                # מוכלל ממקרה יחיד, ו**חשוד במיוחד**: full_title (מ-{{ח:כותרת}})
                # משתמש ב-en dash ("–") אבל האזכור כאן בגוף ההוראה משתמש במקף
                # רגיל ("-"). זו עשויה להיות תקלה חד-פעמית בקובץ הזהב עצמו,
                # לא מוסכמה כללית - drafting-rules.md §6 קובע en dash כנכון
                # לשנה עברית, בלי חריג לאזכור חוזר. לא לסמוך על זה בלי מקרה
                # זהב שני שמאשש (או סותר) את ההמרה.
                text="ב" + (before.full_title or "").replace("–", "-"),
                text_after=f" (להלן – החוק העיקרי), בסעיף {number} – ",
                footnotes=[law_footnote_key],
                depth=0,
            )
        else:
            header = Line(
                side_heading=f"תיקון סעיף {number}",
                number=f"{touched_count}.",
                text=f"בסעיף {number} לחוק העיקרי – ",
                depth=0,
            )
        lines.append(header)

        for i, instruction in enumerate(instructions):
            if isinstance(instruction, _Insertion):
                terminator = "." if i == len(instructions) - 1 else ";"
                footnote = footnotes_by_id.get(instruction.new_node.id)
                lines.extend(_render_insertion(instruction, terminator, ordinal=i + 1, footnote=footnote))
            else:
                replacement = replacements_by_id.get(instruction.node_id)
                lines.append(_render_mutation(number, instruction, replacement))

    return lines
