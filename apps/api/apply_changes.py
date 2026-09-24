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
from node import LegislativeNode, find_parent  # noqa: E402
from transform import (  # noqa: E402
    Annotation,
    RepealSection,
    InsertWordsAfter,
    ReplaceMarginTitleWords,
    AppendWordsAtEnd,
    DeleteWords,
    InsertWordsBefore,
    ReplaceWords,
    apply,
)

from diff_translate import (  # noqa: E402
    SupportedAppendAtEnd,
    SupportedDeleteWords,
    SupportedInsertAtStart,
    SupportedInsertWords,
    SupportedReplaceWords,
    Unsupported,
    translate_text_edit,
    translate_text_edits,
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
    field: str = "text"  # "text" | "margin_title" - ראו TextEditIn.field
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
    client_id: str


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
    current, edits, edit_statuses = _apply_section_repeals(before, list(edits), edit_statuses)

    for edit in edits:
        field = getattr(edit, "field", "text")
        original_node = _find_by_id(before, edit.node_id)
        if original_node is None:
            edit_statuses.append(
                EditStatus(node_id=edit.node_id, ok=False, field=field, reason="צומת לא נמצא")
            )
            continue

        is_title = field == "margin_title"
        if is_title and original_node.node_type != "section":
            edit_statuses.append(EditStatus(
                node_id=edit.node_id, ok=False, field=field,
                reason="כותרת שוליים קיימת רק לסעיפים ראשיים",
            ))
            continue

        original_text = (original_node.margin_title or "") if is_title else original_node.text
        # **כמה אזורי שינוי בצומת אחד = כמה הוראות.** עריכה חופשית
        # שמוסיפה מילה בתחילת הסעיף ומילה בסופו היא שני תיקונים
        # (מדריך §7.10.8), ולא החלפה של הסעיף כולו - הבאג שהמשתמש
        # דיווח עליו ב-22.9. כותרת שוליים נשארת פעולה יחידה: אין
        # דפוס של שתי פעולות על אותה כותרת.
        if is_title:
            results = [translate_text_edit(original_text, edit.text)]
        else:
            results = translate_text_edits(original_text, edit.text)

        # אזור שאי אפשר לתרגם פוסל את **כל** העריכה בצומת, ואינו
        # מושמט בשקט: עריכה שחלקה הוחל וחלקה לא היא בדיוק הנוסח
        # החלקי שנראה אמין.
        unsupported = next((r for r in results if isinstance(r, Unsupported)), None)
        if unsupported is not None:
            edit_statuses.append(
                EditStatus(node_id=edit.node_id, ok=False, field=field,
                           reason=unsupported.reason)
            )
            continue

        for result in results:
            current, annotations, edit_statuses = _apply_one_operation(
                current, result, edit, field, is_title, original_node,
                annotations, edit_statuses,
            )
        continue

    return _finish(before, current, annotations, edit_statuses, insertions)


def _containing_section(root: LegislativeNode, node_id: str) -> LegislativeNode | None:
    node = _find_by_id(root, node_id)
    while node is not None and node.node_type != "section":
        node = find_parent(root, node.id)
    return node


def _text_nodes(section: LegislativeNode) -> list[LegislativeNode]:
    """כל הצמתים בסעיף שיש בהם נוסח שהמשתמש יכול למחוק."""
    out = []

    def walk(n):
        if n is not section and n.is_normative and n.node_type != "raw_block" and n.text.strip():
            out.append(n)
        for c in n.children:
            walk(c)
    walk(section)
    return out


def _apply_section_repeals(before: LegislativeNode, edits: list, statuses: list):
    """ח3 (25.9.2026): **מחיקת כל הטקסט של סעיף היא ביטול הסעיף**, לא
    עריכה. עד כאן כל שדה שהתרוקן נשלח ל-translate_text_edits, שהחזיר
    Unsupported עם הודעה מטעה ("כנראה כמה עריכות נפרדות"), והוראת
    התיקון נעלמה מההצעה בשקט; ומחיקת כותרת השוליים הפיקה `במקום "X"
    יבוא ""` - ניסוח שאינו קיים.

    התנאי: **כל** צומת טקסט בסעיף התרוקן. כותרת השוליים אינה חלק
    מהתנאי - סעיף שכל תוכנו נמחק מבוטל גם אם הכותרת נשארה, ומחיקתה
    נבלעת בביטול. סעיף קטן אחד מתוך כמה אינו ביטול של הסעיף (ראו
    tests/unit/test_repeal_section.py, הבקרה השלילית)."""
    emptied: dict[str, set[str]] = {}
    for edit in edits:
        if getattr(edit, "field", "text") == "text" and not (edit.text or "").strip():
            section = _containing_section(before, edit.node_id)
            if section is not None and section.status == "active":
                emptied.setdefault(section.id, set()).add(edit.node_id)

    repealed: dict[str, LegislativeNode] = {}
    for section_id, ids in emptied.items():
        section = _find_by_id(before, section_id)
        text_ids = {n.id for n in _text_nodes(section)}
        if text_ids and text_ids <= ids:
            repealed[section_id] = section
    if not repealed:
        return before, edits, statuses

    remaining = []
    for edit in edits:
        field = getattr(edit, "field", "text")
        section = _containing_section(before, edit.node_id)
        if section is not None and section.id in repealed:
            node = _find_by_id(before, edit.node_id)
            original = (node.margin_title or "") if field == "margin_title" else node.text
            # old_phrase = כל הנוסח המקורי: הלקוח מציג אותו מחוק
            statuses.append(EditStatus(node_id=edit.node_id, ok=True, field=field,
                                       old_phrase=original or None, new_phrase=""))
            continue
        remaining.append(edit)
    after, _ = apply(before, [RepealSection(section_number=s.number) for s in repealed.values()])
    return after, remaining, statuses


def _apply_one_operation(current, result, edit, field, is_title, original_node,
                         annotations, edit_statuses):
    """פעולה אחת (מתוך אחת או יותר על אותו צומת) -> transform + סטטוס."""
    if is_title:
        # §7.8: אין דפוס "הוספת מילים" נפרד לכותרת שוליים, רק
        # "במקום X יבוא Y" - הוספה טהורה מתורגמת ל-old=anchor,
        # new=anchor+inserted (עדיין ReplaceMarginTitleWords יחיד).
        # §7.8 מגדיר לכותרת שוליים דפוס אחד בלבד - "במקום X יבוא Y".
        # כל שאר הדפוסים (הוספה בתחילה/בסוף, מחיקה) ממופים אליו,
        # ואינם מקבלים ניסוח משלהם: אין להם מקור לכותרת שוליים.
        if isinstance(result, SupportedInsertWords):
            old_phrase = result.anchor_substring
            new_phrase = result.anchor_substring + result.inserted_text
        elif isinstance(result, SupportedInsertAtStart):
            old_phrase = result.before_phrase
            new_phrase = f"{result.inserted_text} {result.before_phrase}"
        elif isinstance(result, SupportedAppendAtEnd):
            title = original_node.margin_title or ""
            old_phrase = title.split()[-1] if title.split() else title
            new_phrase = f"{old_phrase} {result.inserted_text}"
        elif isinstance(result, SupportedDeleteWords):
            old_phrase, new_phrase = result.phrase, ""
        else:
            old_phrase, new_phrase = result.old_phrase, result.new_phrase
        t = ReplaceMarginTitleWords(
            section_number=original_node.number, old_phrase=old_phrase, new_phrase=new_phrase,
        )
        current, ann = apply(current, [t])
        annotations.extend(ann)
        edit_statuses.append(EditStatus(
            node_id=edit.node_id, ok=True, field=field,
            old_phrase=old_phrase, new_phrase=new_phrase,
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
            node_id=edit.node_id, ok=True, field=field,
            anchor_substring=result.anchor_substring, inserted_text=result.inserted_text,
        ))
    elif isinstance(result, SupportedReplaceWords):
        t = ReplaceWords(
            target_id=edit.node_id, old_phrase=result.old_phrase, new_phrase=result.new_phrase,
        )
        current, ann = apply(current, [t])
        annotations.extend(ann)
        edit_statuses.append(EditStatus(
            node_id=edit.node_id, ok=True, field=field,
            old_phrase=result.old_phrase, new_phrase=result.new_phrase,
        ))
    elif isinstance(result, SupportedDeleteWords):
        # `המילים "X" – יימחקו` (§7.10.3), ולא החלפה בריק.
        current, ann = apply(current, [DeleteWords(
            target_id=edit.node_id, phrase=result.phrase)])
        annotations.extend(ann)
        edit_statuses.append(EditStatus(
            node_id=edit.node_id, ok=True, field=field,
            old_phrase=result.phrase, new_phrase="",
        ))
    elif isinstance(result, SupportedInsertAtStart):
        current, ann = apply(current, [InsertWordsBefore(
            target_id=edit.node_id, before_phrase=result.before_phrase,
            inserted_text=result.inserted_text)])
        annotations.extend(ann)
        edit_statuses.append(EditStatus(
            node_id=edit.node_id, ok=True, field=field,
            old_phrase=result.before_phrase, new_phrase=result.inserted_text,
        ))
    elif isinstance(result, SupportedAppendAtEnd):
        current, ann = apply(current, [AppendWordsAtEnd(
            target_id=edit.node_id, inserted_text=result.inserted_text)])
        annotations.extend(ann)
        edit_statuses.append(EditStatus(
            node_id=edit.node_id, ok=True, field=field,
            inserted_text=result.inserted_text,
        ))
    return current, annotations, edit_statuses


def _finish(before, current, annotations, edit_statuses, insertions):
    insertion_errors: list[InsertionError] = []
    for ins in insertions:
        margin_title = getattr(ins, "margin_title", None)
        t, err = build_insertion_transform(
            current, ins.anchor_node_id, ins.kind, text=ins.text, margin_title=margin_title,
            new_id=ins.client_id,
        )
        if t is None:
            insertion_errors.append(
                InsertionError(
                    anchor_node_id=ins.anchor_node_id, kind=ins.kind, reason=err,
                    client_id=ins.client_id,
                )
            )
            continue
        current, ann = apply(current, [t])
        annotations.extend(ann)

    return ApplyResult(
        after=current, annotations=annotations,
        edit_statuses=edit_statuses, insertion_errors=insertion_errors,
    )
