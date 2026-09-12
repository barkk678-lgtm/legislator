"""amend(before, after) -> list[Line]. מנוע ה-diff. ראו TASKS.md משימה 4.

טהור: בלי רשת, בלי LLM (חוק ברזל 2). קלט זהה נותן פלט זהה תמיד.

היקף מכוון (לא מנוע כללי): מזהה רק שני סוגי שינוי שיש להם מקרה זהב
אמיתי כרגע - הוספת ילד חדש בתוך רשימת ילדיו של סעיף (הגדרה/פסקה
חדשה), והוספת מילים בתוך טקסט קיים של ילד שלא השתנה זהותו. שינויים
אחרים (מחיקת סעיף, החלפת סעיף שלם, תיקון עקיף וכו') לא נתמכים -
יחכו למקרה זהב משלהם, לפי עקרון "התחל מהטסט" ב-CLAUDE.md.

כמה כללי ניסוח כאן הוסקו ממקרה זהב *יחיד* (חוק הקייטנות) ומסומנים
"מוסק מדוגמה אחת" למטה - ייתכן שידרשו הכללה כשיגיע מקרה שני.
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

_FOOTNOTE_MARKER_RE = re.compile(r"⟦footnote:(\w+)⟧")
_QUOTED_TERM_RE = re.compile(r'^"([^"]+)"')
_REPLACE_MARKER_RE = re.compile(r"⟦replaced-from:(?P<old>.*?)⟧(?P<new>.*?)⟦/replaced⟧")


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
    שהייתה נכנסת לרנדרר בלי שום שגיאה. ראו packages/amend/transform.py
    (ReplaceWords) ו-_diff_replace() לדפוס "החלפת מילים" הנתמך (משימה 4א).
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
            f"שהוסר ולא רק נוסף: {before_middle!r}. השתמשו ב-_diff_replace "
            "או בדפוס ReplaceWords, לא בפונקציה הזו."
        )
    anchor = before[:prefix_len].rstrip()
    inserted = after[prefix_len : len(after) - suffix_len]
    return anchor, inserted


def _diff_replace(before: str, after: str) -> tuple[str, str]:
    """מחזיר (old_phrase, new_phrase) עבור החלפת מילים מפורשת (דפוס
    "החלפת מילים", drafting-rules.md §1.1 שורה 1). בכוונה **לא** דיף:
    בניגוד ל-_diff_text (הכנסה), שם גבול ההכנסה נקבע באופן חד-משמעי
    על ידי המשותף (prefix/suffix) לפני/אחרי, בהחלפה אין דרך לגזור את
    גבול הביטוי מהטקסט בלבד - "מאסר ששה חדשים" -> "מאסר שנה" ו"ששה
    חדשים" -> "שנה" מייצרים בדיוק אותו before/after, וההבדל ביניהם הוא
    החלטת ניסוח משפטית (מה ראוי לצטט לשם בהירות), לא עובדה טקסטואלית.
    אלגוריתם שהיה "מחליט" לבד איפה הביטוי מתחיל ונגמר הוא ניחוש גם אם
    הוא דטרמיניסטי - הפרה של חוק ברזל 2 (ראו TASKS.md משימה 4א).

    לכן: הביטויים המפורשים מגיעים מ-transform.ReplaceWords, מוטבעים
    ב-after כסמן פנימי (⟦replaced-from:old⟧new⟦/replaced⟧, ראו
    transform.apply). הפונקציה הזו רק *מוודאת עקביות* בין הסמן לבין
    before/after בפועל - לא גוזרת את הגבול בעצמה."""
    match = _REPLACE_MARKER_RE.search(after)
    if not match:
        raise NotImplementedError(
            "מוטציה שאינה הכנסה טהורה, וללא סמן replaced-from - לא "
            "נתמך. אם מדובר בהחלפת מילים, יש לבנות את ה'אחרי' דרך "
            "transform.ReplaceWords, לא באופן ידני."
        )
    old_phrase = match.group("old")
    new_phrase = match.group("new")
    occurrences = before.count(old_phrase)
    if occurrences != 1:
        raise ValueError(
            f"'{old_phrase}' אמור להופיע פעם אחת בדיוק בטקסט ה'לפני' "
            f"אבל מופיע {occurrences} פעמים - חוסר עקביות בין הסמן "
            "לטקסט בפועל."
        )
    reconstructed_before = after[: match.start()] + old_phrase + after[match.end() :]
    if reconstructed_before != before:
        raise ValueError(
            "שחזור ה'לפני' מתוך סמן replaced-from לא תואם את הטקסט "
            "בפועל - חוסר עקביות בין transform.ReplaceWords לבין "
            "before/after שהתקבלו."
        )
    return old_phrase, new_phrase


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


def _wrap_new_content(text: str, terminator: str) -> tuple[str, str, list[str]]:
    """עוטף תוכן חדש במרכאות (חוק ברזל: מילים חדשות מובאות במרכאות),
    ומפצל סביב סמן ⟦footnote:key⟧ אם יש. terminator (';' לפריט לא-אחרון
    ברשימת ההוספות של הסעיף, '.' לפריט האחרון) מתווסף גם מחוץ למרכאות
    הסוגרות - בלי קשר לסימן הפיסוק הפנימי של התוכן עצמו (שנקבע על ידי
    מחבר הטקסט, לא על ידי המנוע - כך נמדד בקובץ הזהב: לתוכן עם כמה
    משפטים מחוברים בפסיקים אין בהכרח סימן פיסוק לפני המרכאה הסוגרת).

    מוכלל ממקרה יחיד: אומת מול 3 הוספות בקייטנות (שתיים עם ';' פנימי
    לפני הסגירה, אחת בלי) - 3 דוגמאות מאותו קובץ, לא 3 מקורות עצמאיים.
    """
    wrapped = f'"{text}"{terminator}'
    match = _FOOTNOTE_MARKER_RE.search(wrapped)
    if not match:
        return wrapped, "", []
    before_marker = wrapped[: match.start()]
    after_marker = wrapped[match.end() :]
    return before_marker, after_marker, [match.group(1)]


def _render_insertion(insertion: _Insertion, terminator: str, ordinal: int) -> list[Line]:
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

    text, text_after, footnotes = _wrap_new_content(insertion.new_node.text, terminator)
    content_line = Line(
        text=text, text_after=text_after, footnotes=footnotes, style="TableBlockOutdent", depth=0
    )
    return [phrase_line, content_line]


def _render_mutation(section_number: str, mutation: _Mutation) -> Line:
    if _REPLACE_MARKER_RE.search(mutation.after_text):
        # דפוס "החלפת מילים" (drafting-rules.md §1.1 שורה 1) - הביטויים
        # מגיעים מסומנים מ-transform.ReplaceWords, לא מדיף (_diff_replace).
        old, new = _diff_replace(mutation.before_text, mutation.after_text)
        text = f'בסעיף {section_number} לחוק העיקרי, במקום "{old}" יבוא "{new}".'
        return Line(text=text, depth=0)
    anchor, inserted = _diff_text(mutation.before_text, mutation.after_text)
    anchor, inserted = anchor.strip(), inserted.strip()
    text = f'בסעיף {section_number} לחוק העיקרי, אחרי המילים "{anchor}" יבוא "{inserted}".'
    return Line(text=text, depth=0)


def amend(before: LegislativeNode, after: LegislativeNode, *, law_footnote_key: str) -> list[Line]:
    """משווה שני עצי LegislativeNode של אותו חוק ומחזיר רשימת Line
    (ראו packages/render/render_bill.py) - הוראות תיקון מוכנות לרינדור.

    law_footnote_key: מפתח הערת השוליים לחוק עצמו (מראה מקום), כפי
    שמוגדר בטבלת REFS החיצונית - זה חלק מהחיווט הכללי של הצעת החוק,
    לא נגזר מהעץ עצמו.
    """
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
            mutation_line = _render_mutation(number, instructions[0])
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
                lines.extend(_render_insertion(instruction, terminator, ordinal=i + 1))
            else:
                lines.append(_render_mutation(number, instruction))

    return lines
