"""נוסח משולב: תוכנית תיקון מפורשת + עץ החוק -> עץ החוק **אחרי**.

**מה המשתמש רואה:** הוא מעלה קובץ Word של הצעת חוק מתקנת, ומקבל
את נוסח החוק כפי שהוא ייראה אם ההצעה תתקבל - עם היחידות שנוספו
מסומנות. זו העבודה שמתנדבי "ספר החוקים הפתוח" עושים היום ביד.

**זה החצי שהיה חסר.** `parse_instructions` כבר קוראת מה ההוראה
אומרת, ו-`transform.apply` כבר יודעת לבנות עץ "אחרי" נקי. מה
שחסר היה החוליה באמצע: **לאתר בעץ האמיתי** את הסעיף, את הסעיף
הקטן שבתוכו ואת הפסקה שאחריה מוסיפים, ולוודא שהם באמת שם.

**כל כשל עוצר ברעש, ואין מיזוג חלקי.** נוסח משולב חלקי הוא נוסח
חוק שגוי שנראה אמין - הכשל היחיד שהמוצר קיים כדי למנוע. לכן:
סעיף שלא נמצא, סעיף קטן שלא נמצא, עוגן שלא נמצא, או תווית חדשה
שכבר תפוסה - כולם מחזירים `error` מפורש ו-`tree=None`, ולא עץ
שחלק מההוראות הוחלו עליו.

**למה ההוראות מוחלות לפי הסדר, אחת-אחת, על העץ שכבר עודכן:**
הוראה יכולה להזיז את העוגן של הבאה אחריה (מספור מחדש, הוספה
לפני עוגן קיים). החלה במקביל על עץ המוצא הייתה נותנת תוצאה
שתלויה בסדר בלי שאיש הצהיר עליו.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
from node import LegislativeNode, find_sections  # noqa: E402
from parse_instructions import (  # noqa: E402
    AmendmentPlan, AppendAtEnd, InsertUnit, RelabelAndInsert, ReplaceWords,
)
from transform import (  # noqa: E402
    AddFirstParagraph, AddFirstSubsection, InsertAfter, ReplaceWords as ReplaceWordsTransform, apply,
)

_PARENS = re.compile(r"^\s*[(״\"']?\s*(?P<label>.+?)\s*[)״\"']?\s*$")


def _label(number: str | None) -> str:
    """התווית בלי הסוגריים. `number` מגיע מהפרסר **עם** סוגריים
    ("(2)"), ומההוראה **בלי** ("2") - משווים על הצורה החשופה."""
    if not number:
        return ""
    stripped = number.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        return stripped[1:-1].strip()
    match = _PARENS.match(stripped)
    return match.group("label").strip() if match else stripped



def _descendant_by_label(parent: LegislativeNode, label: str):
    """מאתרת יחידה לפי תווית בתוך סעיף, **גם מתחת לצומת בלי מספר**.

    נדרש מנתונים אמיתיים: בחוק דמי מחלה סעיף 3 מכיל פסקה בלי תווית
    ("לעניין סעיף 1 –") שמתחתיה יושבות (1) ו-(2), וההוראה כותבת
    "בסעיף 3(1)". חיפוש בילדים הישירים בלבד לא היה מוצא אותה.

    מחזירה (צומת, "") או (None, סיבה). **תווית שמופיעה יותר מפעם
    אחת בתוך הסעיף היא דו-משמעית ונדחית** - אין ניחוש איזו מהן
    ההצעה התכוונה אליה.
    """
    matches: list[LegislativeNode] = []

    def walk(node: LegislativeNode) -> None:
        for child in node.children:
            if not child.is_normative:
                continue
            if child.number and _label(child.number) == label:
                matches.append(child)
                continue  # לא יורדים לתוך התאמה - קינון של אותה תווית
            if not child.number:
                walk(child)  # צומת בלי תווית הוא שקוף למספור

    walk(parent)
    if not matches:
        return None, "לא נמצאה"
    if len(matches) > 1:
        return None, f"מופיעה {len(matches)} פעמים בסעיף - דו-משמעי"
    return matches[0], ""


def _container_node(root: LegislativeNode, section_number: str, container: str | None):
    """הסעיף, או היחידה שבתוכו שההוראה מצביעה עליה."""
    sections = find_sections(root)
    section = sections.get(section_number)
    if section is None:
        return None, (
            f"ההצעה מתקנת את סעיף {section_number}, ואין סעיף כזה בנוסח החוק "
            "שברשותי. ייתכן שההצעה מתייחסת לנוסח אחר."
        )
    if not container:
        return section, ""
    node, why = _descendant_by_label(section, _label(container))
    if node is None:
        return None, (
            f"ההצעה מתקנת את סעיף {section_number}({_label(container)}), "
            f"והיחידה הזו {why} בנוסח שברשותי."
        )
    return node, ""


def _text_target(node: LegislativeNode) -> LegislativeNode:
    """הצומת שנושא את הטקסט בפועל. סעיף שכל תוכנו יושב בילד יחיד
    בלי תווית (`.text` של הסעיף ריק) - הטקסט שם, לא בסעיף."""
    if node.text.strip():
        return node
    normative = [c for c in node.children if c.is_normative]
    if len(normative) == 1 and not normative[0].number and normative[0].text.strip():
        return normative[0]
    return node


@dataclass(frozen=True)
class AppliedChange:
    """שינוי אחד שהוחל - מה שהממשק צריך כדי לסמן ולקשר בחזרה."""
    kind: str             # "insert" | "replace" | "append" | "relabel"
    node_id: str          # הצומת שנוצר או שהשתנה
    anchor_id: str        # אחרי מה הוא נכנס (ריק בהחלפה/הוספה בסוף)
    label: str            # "(3)"
    text: str
    source_line: int      # שורת ההוראה בהצעה שיצרה אותו


@dataclass
class MergeResult:
    tree: LegislativeNode | None = None
    applied: list[AppliedChange] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.tree is not None and not self.error


def _child_by_label(parent: LegislativeNode, node_type: str, label: str):
    for child in parent.children:
        if not child.is_normative:
            continue
        if child.node_type == node_type and _label(child.number) == label:
            return child
    return None


def _resolve_anchor(root: LegislativeNode, unit: InsertUnit):
    """מאתרת בעץ את העוגן של הוראה אחת. מחזירה (עוגן, סעיף) או
    (None, הודעת שגיאה) - ההודעה מנוסחת למשתמש, לא למפתח."""
    sections = find_sections(root)
    section = sections.get(unit.section)
    if section is None:
        return None, (
            f"ההצעה מתקנת את סעיף {unit.section}, ואין סעיף כזה בנוסח החוק "
            "שברשותי. ייתכן שההצעה מתייחסת לנוסח אחר."
        )

    container = section
    if unit.subsection:
        wanted = _label(unit.subsection)
        container = _child_by_label(section, "subsection", wanted)
        if container is None:
            available = [
                _label(c.number) for c in section.children
                if c.is_normative and c.node_type == "subsection" and c.number
            ]
            return None, (
                f"ההצעה מתקנת את סעיף {unit.section}({wanted}), ואין סעיף קטן "
                f"כזה בנוסח שברשותי" + (f" (יש: {', '.join(available)})" if available else "")
            )

    anchor = _child_by_label(container, unit.after_kind, _label(unit.after_label))
    if anchor is None:
        where = f"{unit.section}({_label(unit.subsection)})" if unit.subsection else unit.section
        return None, (
            f"ההוראה מוסיפה אחרי ({_label(unit.after_label)}) בסעיף {where}, "
            "ואין יחידה כזו בנוסח שברשותי."
        )

    # התווית החדשה חייבת להיות פנויה. אם היא תפוסה, ההצעה מתייחסת
    # לנוסח אחר משלנו - וזה בדיוק המצב שבו מיזוג היה יוצר חוק עם
    # שתי פסקאות באותו מספר.
    if _child_by_label(container, unit.after_kind, _label(unit.new_label)) is not None:
        return None, (
            f"ההצעה מוסיפה יחידה בתווית ({_label(unit.new_label)}), אבל תווית "
            "זו כבר תפוסה בנוסח שברשותי - סימן שההצעה מתייחסת לנוסח אחר."
        )
    return (anchor, section), ""



def _apply_replace(current, unit, index):
    """החלפת מילים. הביטוי המוחלף חייב להופיע **פעם אחת בדיוק** -
    אותה דרישה בדיוק שיש ל-`amend()` בכיוון הכותב, מאותה סיבה:
    שתי הופעות ואין דרך לדעת לאיזו ההצעה התכוונה."""
    node, message = _container_node(current, unit.section, unit.container)
    if node is None:
        return current, None, message
    target = _text_target(node)
    count = target.text.count(unit.old_phrase)
    where = f"{unit.section}({_label(unit.container)})" if unit.container else unit.section
    if count == 0:
        return current, None, (
            f'ההצעה מחליפה את "{unit.old_phrase}" בסעיף {where}, '
            "והביטוי הזה אינו מופיע שם בנוסח שברשותי."
        )
    if count > 1:
        return current, None, (
            f'הביטוי "{unit.old_phrase}" מופיע {count} פעמים בסעיף {where} - '
            "דו-משמעי, ואין דרך לדעת לאיזו הופעה ההצעה התכוונה."
        )
    try:
        current, _ = apply(current, [ReplaceWordsTransform(
            target_id=target.id, old_phrase=unit.old_phrase, new_phrase=unit.new_phrase,
        )])
    except (ValueError, NotImplementedError) as exc:
        return current, None, f"לא ניתן להחיל את ההוראה: {exc}"
    return current, AppliedChange(
        kind="replace", node_id=target.id, anchor_id="",
        label=_label(unit.container), text=unit.new_phrase,
        source_line=unit.source_line,
    ), ""


def _apply_append(current, unit, index):
    """'ובסופו יבוא "X"'.

    **סימן הפיסוק הסוגר נשאר בסוף.** בהוראה האמיתית (13948380)
    הטקסט הקיים מסתיים ב-";", והתוצאה הנכונה היא
    "...פעולות יום-יום או שזקוק להשגחה מתמדת...;" - הוספה *אחרי*
    הנקודה-פסיק הייתה מייצרת יחידה שמסתיימת בלי סימן פיסוק ומשפט
    חדש תלוי באוויר. זו אינה העדפה סגנונית אלא הקריאה היחידה
    שמפיקה נוסח חוק תקין."""
    node, message = _container_node(current, unit.section, unit.container)
    if node is None:
        return current, None, message
    target = _text_target(node)
    existing = target.text.rstrip()
    if existing and existing[-1] in ".;,:":
        merged = f"{existing[:-1].rstrip()} {unit.text}{existing[-1]}"
    else:
        merged = f"{existing} {unit.text}"
    try:
        current, _ = apply(current, [ReplaceWordsTransform(
            target_id=target.id, old_phrase=target.text, new_phrase=merged,
        )])
    except (ValueError, NotImplementedError) as exc:
        return current, None, f"לא ניתן להחיל את ההוראה: {exc}"
    return current, AppliedChange(
        kind="append", node_id=target.id, anchor_id="",
        label=_label(unit.container), text=unit.text,
        source_line=unit.source_line,
    ), ""


def _apply_relabel(current, unit, index):
    """'האמור בו יסומן "(א)" ואחריו יבוא: "(ב) ..."'.

    `transform.AddFirstSubsection` כבר מממשת בדיוק את זה (§7.10.6(ד))
    וקובעת "(א)"/"(ב)" בעצמה. לכן התוויות שבהוראה **נבדקות** מולה
    ולא מוזנות לתוכה: הצעה שכותבת תוויות אחרות מתייחסת לנוסח אחר,
    וזו עצירה, לא התאמה."""
    sections = find_sections(current)
    section = sections.get(unit.section)
    if section is None:
        return current, None, (
            f"ההצעה מתקנת את סעיף {unit.section}, ואין סעיף כזה בנוסח החוק שברשותי."
        )
    if unit.container:
        return _apply_relabel_in_subsection(current, section, unit, index)
    if _label(unit.relabeled_label) != "א" or _label(unit.new_label) != "ב":
        return current, None, (
            f'ההצעה מסמנת את הקיים כ-({_label(unit.relabeled_label)}) ומוסיפה '
            f'({_label(unit.new_label)}). הדפוס הזה מוגדר במדריך על (א) ו-(ב) '
            "בלבד (§7.10.6(ד)), ולא אנחש מה נכון מחוץ לו."
        )
    new_id = f"{section.id}/merged-{index}"
    new_child = LegislativeNode(
        id=new_id, node_type="subsection", number="", margin_title=None,
        text=unit.new_text,
    )
    try:
        current, _ = apply(current, [AddFirstSubsection(
            section_number=section.number, new_child=new_child,
        )])
    except (ValueError, NotImplementedError) as exc:
        return current, None, (
            f"לא ניתן להחיל את הוראת המספור מחדש על סעיף {unit.section}: {exc}"
        )
    return current, AppliedChange(
        kind="relabel", node_id=new_id, anchor_id=section.id,
        label=f"({_label(unit.new_label)})", text=unit.new_text,
        source_line=unit.source_line,
    ), ""


def _apply_relabel_in_subsection(current, section, unit, index):
    """ח11-ב: 'בסעיף 34(א), האמור בו יסומן "(1)" ואחריו יבוא: "(2) ..."' -
    התקדים מרשומות (הצעת חוק הממשלה 1924, עמ' 676). transform.AddFirstParagraph
    קובעת "(1)"/"(2)" בעצמה; התוויות בהוראה נבדקות, לא מוזנות."""
    if _label(unit.relabeled_label) != "1" or _label(unit.new_label) != "2":
        return current, None, (
            f'ההצעה מסמנת את הנוסח של סעיף קטן ({unit.container}) כ-({_label(unit.relabeled_label)}) '
            f'ומוסיפה ({_label(unit.new_label)}). הדפוס הזה מוחל על (1) ו-(2) בלבד, ולא אנחש '
            "מה נכון מחוץ לו."
        )
    target, reason = _descendant_by_label(section, _label(unit.container))
    if target is None:
        return current, None, f"סעיף קטן ({unit.container}) בסעיף {unit.section}: {reason}."
    new_id = f"{target.id}/merged-{index}"
    new_child = LegislativeNode(
        id=new_id, node_type="paragraph", number="", margin_title=None, text=unit.new_text,
    )
    try:
        current, _ = apply(current, [AddFirstParagraph(
            section_number=section.number, unit_id=target.id, new_child=new_child,
        )])
    except (ValueError, NotImplementedError) as exc:
        return current, None, (
            f"לא ניתן להחיל את הוראת המספור מחדש על סעיף {unit.section}({unit.container}): {exc}"
        )
    return current, AppliedChange(
        kind="relabel", node_id=new_id, anchor_id=target.id,
        label="(2)", text=unit.new_text, source_line=unit.source_line,
    ), ""


def build_merged_text(root: LegislativeNode, plan: AmendmentPlan) -> MergeResult:
    """מחזירה את עץ החוק אחרי שכל הוראות התוכנית הוחלו.

    `plan.ok` נבדק כאן ולא מונח: תוכנית עם הוראות שלא זוהו, או
    כזו שמתקנת כמה חוקים, נעצרת עם הסיבה שהפרסר כבר ניסח."""
    if not plan.ok:
        return MergeResult(error=plan.blocking_reason)

    current = root
    applied: list[AppliedChange] = []
    for index, unit in enumerate(plan.operations):
        if isinstance(unit, ReplaceWords):
            current, change, message = _apply_replace(current, unit, index)
        elif isinstance(unit, AppendAtEnd):
            current, change, message = _apply_append(current, unit, index)
        elif isinstance(unit, RelabelAndInsert):
            current, change, message = _apply_relabel(current, unit, index)
        elif isinstance(unit, InsertUnit):
            current, change, message = _apply_insert(current, unit, index)
        else:
            return MergeResult(
                error=f"סוג הוראה שאינו נתמך עדיין בנוסח המשולב: {type(unit).__name__}"
            )
        if change is None:
            return MergeResult(error=message)
        applied.append(change)

    return MergeResult(tree=current, applied=applied)


def _apply_insert(current, unit, index):
    resolved, message = _resolve_anchor(current, unit)
    if resolved is None:
        return current, None, message
    anchor, section = resolved
    new_id = f"{anchor.id}/merged-{index}"
    new_child = LegislativeNode(
        id=new_id,
        node_type=unit.after_kind,
        number=f"({_label(unit.new_label)})",
        margin_title=None,
        text=unit.new_text,
    )
    try:
        current, _annotations = apply(
            current,
            [InsertAfter(section_number=section.number, anchor_id=anchor.id,
                         new_child=new_child)],
        )
    except (ValueError, NotImplementedError) as exc:
        return current, None, f"לא ניתן להחיל את ההוראה: {exc}"

    return current, AppliedChange(
        kind="insert", node_id=new_id, anchor_id=anchor.id,
        label=f"({_label(unit.new_label)})", text=unit.new_text,
        source_line=unit.source_line,
    ), ""


__all__ = ["AppliedChange", "MergeResult", "build_merged_text"]
