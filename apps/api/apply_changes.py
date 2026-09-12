"""מרכיבה מתוך רשימת עריכות חופשיות + הוספות (כפי שהלקוח שולח בכל
בקשה, ראו schemas.RenderRequest) עץ "אחרי" אחד + רשימת אנוטציות, מוכן
להעברה ל-engine.amend(). ראו TASKS.md משימה 10ב.

טהור יחסית: אין כאן לוגיקה משפטית משל עצמו - כל החלטה (מה נתמך, איזו
טרנספורמציה מתאימה) כבר התקבלה ב-diff_translate.py/insert_preview.py.
המודול הזה רק מפעיל אותן ברצף ואוסף תוצאות/שגיאות בלי לבלוע אותן בשקט.

**סדר עיבוד:** קודם כל העריכות (edits), אחר כך ההוספות (insertions).
עריכות טקסט לא משנות מבנה (מספרים/הורות) אז אינן תלויות סדר בינן
לבין עצמן; הוספות עשויות להיות תלויות-סדר (הוספה שנייה באותו סעיף
רואה את הראשונה) - ולכן מיושמות אחת-אחת, כל אחת מול העץ המעודכן
בפועל מהקודמת לה (לא כולן מול העץ המקורי בבת אחת)."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
from node import LegislativeNode  # noqa: E402
from transform import (  # noqa: E402
    Annotation,
    InsertWordsAfter,
    ReplaceMarginTitleWords,
    ReplaceWords,
    apply,
)

from diff_translate import (  # noqa: E402
    SupportedInsertWords,
    SupportedReplaceWords,
    Unsupported,
    translate_text_edit,
)
from insert_preview import build_insertion_transform  # noqa: E402


def _find_by_id(node: LegislativeNode, node_id: str) -> LegislativeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find_by_id(child, node_id)
        if found:
            return found
    return None


@dataclass
class EditStatus:
    node_id: str
    ok: bool
    reason: str | None = None
    # לצורך דקורציית track-changes בצד הלקוח (ראו diff_translate) -
    # ריקים אם ok=False.
    old_phrase: str | None = None
    new_phrase: str | None = None
    anchor_substring: str | None = None
    inserted_text: str | None = None


@dataclass
class InsertionError:
    anchor_node_id: str
    kind: str
    reason: str


@dataclass
class ApplyResult:
    after: LegislativeNode
    annotations: list[Annotation]
    edit_statuses: list[EditStatus]
    insertion_errors: list[InsertionError]


def apply_pending_changes(before: LegislativeNode, edits: list, insertions: list) -> ApplyResult:
    """edits: רשימת אובייקטים עם .node_id/.text (schemas.TextEditIn).
    insertions: רשימת אובייקטים עם .kind/.anchor_node_id/.text (ו-
    .margin_title עבור kind=='section') - schemas.InsertionIn."""
    current = before
    annotations: list[Annotation] = []
    edit_statuses: list[EditStatus] = []

    for edit in edits:
        original_node = _find_by_id(before, edit.node_id)
        if original_node is None:
            edit_statuses.append(EditStatus(node_id=edit.node_id, ok=False, reason="צומת לא נמצא"))
            continue

        is_title = getattr(edit, "field", "text") == "margin_title"
        if is_title and original_node.node_type != "section":
            edit_statuses.append(EditStatus(
                node_id=edit.node_id, ok=False,
                reason="כותרת שוליים קיימת רק לסעיפים ראשיים",
            ))
            continue

        original_text = (original_node.margin_title or "") if is_title else original_node.text
        result = translate_text_edit(original_text, edit.text)
        if isinstance(result, Unsupported):
            edit_statuses.append(EditStatus(node_id=edit.node_id, ok=False, reason=result.reason))
            continue

        if is_title:
            # §7.8: אין דפוס "הוספת מילים" נפרד לכותרת שוליים, רק
            # "במקום X יבוא Y" - הוספה טהורה מתורגמת ל-old=anchor,
            # new=anchor+inserted (עדיין ReplaceMarginTitleWords יחיד).
            if isinstance(result, SupportedInsertWords):
                old_phrase = result.anchor_substring
                new_phrase = result.anchor_substring + result.inserted_text
            else:
                old_phrase, new_phrase = result.old_phrase, result.new_phrase
            t = ReplaceMarginTitleWords(
                section_number=original_node.number, old_phrase=old_phrase, new_phrase=new_phrase,
            )
            current, ann = apply(current, [t])
            annotations.extend(ann)
            edit_statuses.append(EditStatus(
                node_id=edit.node_id, ok=True, old_phrase=old_phrase, new_phrase=new_phrase,
            ))
        elif isinstance(result, SupportedInsertWords):
            t = InsertWordsAfter(
                target_id=edit.node_id,
                anchor_substring=result.anchor_substring,
                inserted_text=result.inserted_text,
            )
            current, ann = apply(current, [t])
            annotations.extend(ann)
            edit_statuses.append(EditStatus(
                node_id=edit.node_id, ok=True,
                anchor_substring=result.anchor_substring, inserted_text=result.inserted_text,
            ))
        elif isinstance(result, SupportedReplaceWords):
            t = ReplaceWords(
                target_id=edit.node_id, old_phrase=result.old_phrase, new_phrase=result.new_phrase,
            )
            current, ann = apply(current, [t])
            annotations.extend(ann)
            edit_statuses.append(EditStatus(
                node_id=edit.node_id, ok=True,
                old_phrase=result.old_phrase, new_phrase=result.new_phrase,
            ))

    insertion_errors: list[InsertionError] = []
    for ins in insertions:
        margin_title = getattr(ins, "margin_title", None)
        t, err = build_insertion_transform(
            current, ins.anchor_node_id, ins.kind, text=ins.text, margin_title=margin_title
        )
        if t is None:
            insertion_errors.append(
                InsertionError(anchor_node_id=ins.anchor_node_id, kind=ins.kind, reason=err)
            )
            continue
        current, ann = apply(current, [t])
        annotations.extend(ann)

    return ApplyResult(
        after=current, annotations=annotations,
        edit_statuses=edit_statuses, insertion_errors=insertion_errors,
    )
