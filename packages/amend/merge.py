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
from parse_instructions import AmendmentPlan, InsertUnit  # noqa: E402
from transform import InsertAfter, apply  # noqa: E402

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


@dataclass(frozen=True)
class AppliedChange:
    """שינוי אחד שהוחל - מה שהממשק צריך כדי לסמן ולקשר בחזרה."""
    node_id: str          # הצומת החדש בעץ המשולב
    anchor_id: str        # אחרי מה הוא נכנס
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


def build_merged_text(root: LegislativeNode, plan: AmendmentPlan) -> MergeResult:
    """מחזירה את עץ החוק אחרי שכל הוראות התוכנית הוחלו.

    `plan.ok` נבדק כאן ולא מונח: תוכנית עם הוראות שלא זוהו, או
    כזו שמתקנת כמה חוקים, נעצרת עם הסיבה שהפרסר כבר ניסח."""
    if not plan.ok:
        return MergeResult(error=plan.blocking_reason)

    current = root
    applied: list[AppliedChange] = []
    for index, unit in enumerate(plan.operations):
        if not isinstance(unit, InsertUnit):
            return MergeResult(
                error=f"סוג הוראה שאינו נתמך עדיין בנוסח המשולב: {type(unit).__name__}"
            )
        resolved, message = _resolve_anchor(current, unit)
        if resolved is None:
            return MergeResult(error=message)
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
            return MergeResult(error=f"לא ניתן להחיל את ההוראה: {exc}")

        applied.append(AppliedChange(
            node_id=new_id, anchor_id=anchor.id,
            label=f"({_label(unit.new_label)})", text=unit.new_text,
            source_line=unit.source_line,
        ))

    return MergeResult(tree=current, applied=applied)


__all__ = ["AppliedChange", "MergeResult", "build_merged_text"]
