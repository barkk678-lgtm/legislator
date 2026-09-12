"""מחשבת את התווית שתיווצר אם מוסיפים תוכן ברמה נתונה (סעיף ראשי/סעיף
קטן/פסקה) בהקשר של צומת עוגן נתון - בלי לבצע את ההוספה בפועל. ראו
TASKS.md משימה 10ב (היררכיית הוספה בממשק: "הוסף סעיף קטן (יהיה ג1)").

טהור: אין כאן לוגיקה משפטית, רק קריאה לפונקציות הקיימות ב-numbering.py
לפי המיקום המבוקש. אסור לנחש תווית - כל תווית מחושבת כאן היא בדיוק מה
ש-transform.py (InsertSectionAfter/AddFirstSubsection/InsertAfter) יפיקו
בפועל אם ההוספה תבוצע - לכן חשוב שהלוגיקה כאן תישאר תואמת ל-transform.py,
לא עותק עצמאי שעלול לסטות ממנו.

**היקף מכוון (לא כל צירוף אפשרי):** מותאם בדיוק למה שהמנוע תומך בו
היום:
- "section": תמיד זמין - מוסיף סעיף ראשי חדש אחרי הסעיף האב של הצומת
  הנוכחי (InsertSectionAfter, §7.12).
- "subsection": זמין כשהצומת הנוכחי הוא סעיף או סעיף קטן (לא פסקה/
  פסקת משנה) - סעיפים קטנים הם ילדים ישירים של סעיף (AddFirstSubsection
  אם עדיין אין; אחרת הוספה אחרי הסעיף הקטן העוגן, §7.10.6(ב)).
- "paragraph": זמין רק כשהצומת הנוכחי הוא פסקה שהיא ילד ישיר של סעיף
  (לא של סעיף קטן) - הכנסת פסקה לתוך סעיף קטן קיים אינה נתמכת עדיין
  (transform.InsertAfter מוצא רק node_type=="section", לא "subsection";
  זה פער אמיתי, לא הוסתר - ראו not_supported_reason).
- "subparagraph": לא נתמך בכלל כרגע - אין מקרה זהב.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
from node import LegislativeNode  # noqa: E402
from numbering import next_appended_label, next_inserted_label, sort_section_numbers  # noqa: E402


@dataclass
class InsertPreview:
    supported: bool
    label: str | None = None  # התווית שתיווצר, אם supported
    reason: str | None = None  # למה לא נתמך, אם not supported


def _find_by_id(node: LegislativeNode, node_id: str) -> LegislativeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find_by_id(child, node_id)
        if found:
            return found
    return None


def _find_parent(root: LegislativeNode, node_id: str) -> LegislativeNode | None:
    for child in root.children:
        if child.id == node_id:
            return root
        found = _find_parent(child, node_id)
        if found:
            return found
    return None


def _ancestor_of_type(root: LegislativeNode, node_id: str, node_type: str) -> LegislativeNode | None:
    """מוצאת את האב מהסוג המבוקש (כולל הצומת עצמו אם הוא כבר מהסוג הזה) -
    מטפסת מהצומת כלפי מעלה עד השורש."""
    node = _find_by_id(root, node_id)
    if node is None:
        return None
    if node.node_type == node_type:
        return node
    current_id = node.id
    while True:
        parent = _find_parent(root, current_id)
        if parent is None:
            return None
        if parent.node_type == node_type:
            return parent
        current_id = parent.id


def preview_insertion_label(root: LegislativeNode, node_id: str, level: str) -> InsertPreview:
    if _find_by_id(root, node_id) is None:
        return InsertPreview(supported=False, reason=f"צומת לא נמצא: {node_id!r}")

    if level == "section":
        anchor_section = _ancestor_of_type(root, node_id, "section")
        if anchor_section is None:
            return InsertPreview(supported=False, reason="לא נמצא סעיף אב להוספה אחריו")
        siblings = [c for c in root.children if c.node_type == "section"]
        existing_numbers = [c.number for c in siblings]
        idx = next(i for i, c in enumerate(siblings) if c.id == anchor_section.id)
        if idx == len(siblings) - 1:
            label = next_appended_label(sort_section_numbers(existing_numbers))
        else:
            label = next_inserted_label(anchor_section.number, set(existing_numbers))
        return InsertPreview(supported=True, label=label)

    if level == "subsection":
        anchor_section = _ancestor_of_type(root, node_id, "section")
        if anchor_section is None:
            return InsertPreview(supported=False, reason="לא נמצא סעיף אב")
        subsections = [c for c in anchor_section.children if c.is_normative and c.node_type == "subsection"]
        if not subsections:
            # עדיין אין סעיפים קטנים בסעיף הזה - AddFirstSubsection
            # תמיד קובע "א" לתוכן הקיים ו"ב" לחדש (§7.10.6(ד)).
            return InsertPreview(supported=True, label="ב")
        current_node = _find_by_id(root, node_id)
        anchor_subsection = current_node if current_node.node_type == "subsection" else subsections[-1]
        existing_numbers = [c.number for c in subsections]
        idx = next((i for i, c in enumerate(subsections) if c.id == anchor_subsection.id), len(subsections) - 1)
        if idx == len(subsections) - 1:
            label = next_appended_label(existing_numbers)
        else:
            label = next_inserted_label(anchor_subsection.number, set(existing_numbers))
        return InsertPreview(supported=True, label=label)

    if level == "paragraph":
        current_node = _find_by_id(root, node_id)
        parent = _find_parent(root, node_id)
        if current_node.node_type != "paragraph" or parent is None or parent.node_type != "section":
            return InsertPreview(
                supported=False,
                reason=(
                    "הוספת פסקה נתמכת רק כשהיא ילד ישיר של סעיף (לא של סעיף "
                    "קטן) - אין עדיין תמיכה בהוספת פסקה בתוך סעיף קטן קיים"
                ),
            )
        paragraphs = [c for c in parent.children if c.is_normative and c.node_type == "paragraph" and c.number]
        if not paragraphs:
            return InsertPreview(
                supported=False,
                reason="אין עדיין פסקאות ממוספרות בסעיף הזה להוסיף אחריהן",
            )
        existing_numbers = [c.number for c in paragraphs]
        idx = next((i for i, c in enumerate(paragraphs) if c.id == current_node.id), None)
        if idx is None:
            return InsertPreview(supported=False, reason="הפסקה הנוכחית אינה ממוספרת")
        if idx == len(paragraphs) - 1:
            label = next_appended_label(existing_numbers)
        else:
            label = next_inserted_label(current_node.number, set(existing_numbers))
        return InsertPreview(supported=True, label=label)

    return InsertPreview(supported=False, reason=f"רמה לא נתמכת: {level!r}")
