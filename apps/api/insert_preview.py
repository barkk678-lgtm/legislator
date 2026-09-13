"""פותרת "היכן ואיך" הוספת תוכן חדש (סעיף ראשי/סעיף קטן/פסקה) בהקשר של
צומת עוגן נתון - גם לתצוגה מקדימה (התווית שתיווצר, בלי לבצע כלום) וגם
לבניית טרנספורמציית transform.py בפועל בעת שליחה. ראו TASKS.md משימה 10ב
(היררכיית הוספה בממשק: "הוסף סעיף קטן (יהיה ג1)").

טהור: אין כאן לוגיקה משפטית, רק קריאה לפונקציות הקיימות ב-numbering.py
לפי המיקום המבוקש. שתי הפעולות (תצוגה מקדימה, בנייה בפועל) עוברות דרך
אותה פונקציית פתרון יחידה (_resolve) - כדי שהתווית שמוצגת למשתמש *לפני*
הלחיצה תמיד תהיה בדיוק התווית שתיווצר בפועל אחריה, לא שני מסלולי חישוב
נפרדים שעלולים לסטות זה מזה.

**היקף מכוון (לא כל צירוף אפשרי) - תואם בדיוק למה שהמנוע תומך בו היום:**
- "section": תמיד זמין - מוסיף סעיף ראשי חדש אחרי הסעיף האב של הצומת
  הנוכחי (InsertSectionAfter, §7.12).
- "subsection": זמין כשהצומת הנוכחי הוא סעיף או סעיף קטן (לא פסקה/
  פסקת משנה) - סעיפים קטנים הם ילדים ישירים של סעיף (AddFirstSubsection
  אם עדיין אין; אחרת הוספה אחרי הסעיף הקטן העוגן, §7.10.6(ב)).
- "paragraph": זמין רק כשהצומת הנוכחי הוא פסקה שהיא ילד ישיר של סעיף
  (לא של סעיף קטן) - הכנסת פסקה לתוך סעיף קטן קיים אינה נתמכת עדיין
  (transform.InsertAfter מוצא רק node_type=="section", לא "subsection";
  זה פער אמיתי, לא הוסתר - ראו reason).
- "definition": זמין כשהצומת הנוכחי הוא הגדרה - מוסיף הגדרה חדשה
  אחריה, ללא מספור (הגדרות ממוינות א"ב, לא ממוספרות - ראו
  drafting-rules/validator בדיקה 11). משתמש ב-InsertAfter הקיים בדיוק
  כמו קייטנות סעיף 1 (מקרה זהב).
  **פער ידוע, לא מומש כאן:** הוספת סעיף-קטן/פסקה *בתוך* הגדרה ספציפית
  (כשכבר יש לה כאלה) אינה נתמכת - transform.InsertAfter.apply() מחפש
  את העוגן רק בין ילדיו הישירים של הסעיף עצמו, לא רקורסיבית בתוך ילד
  שהוא הגדרה. אין עדיין מקרה זהב שמדגים הגדרה עם ילדים כאלה - הרחבה
  אמיתית של transform.py, לא רק חיווט כאן, ותושאר לפעם הבאה שיהיה
  מקרה אמיתי לבדוק מולו.
- "subparagraph": לא נתמך בכלל כרגע - אין מקרה זהב.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
from node import LegislativeNode  # noqa: E402
from numbering import next_appended_label, next_inserted_label, sort_section_numbers  # noqa: E402
from transform import AddFirstSubsection, InsertAfter, InsertSectionAfter  # noqa: E402

_FRESH_ID_COUNTER = {"n": 0}


def _fresh_id(prefix: str) -> str:
    _FRESH_ID_COUNTER["n"] += 1
    return f"{prefix}/new-{_FRESH_ID_COUNTER['n']}"


@dataclass
class InsertPreview:
    supported: bool
    label: str | None = None  # התווית שתיווצר, אם supported
    reason: str | None = None  # למה לא נתמך, אם not supported


@dataclass
class _Resolution:
    supported: bool
    label: str | None = None
    reason: str | None = None
    kind: str | None = None  # "section" | "add_first_subsection" | "insert_after"
    section_number: str | None = None  # רלוונטי ל-add_first_subsection/insert_after
    anchor_number: str | None = None  # רלוונטי ל-section (InsertSectionAfter)
    anchor_id: str | None = None  # רלוונטי ל-insert_after (subsection/paragraph)
    node_type: str | None = None  # "subsection" | "paragraph" - סוג הילד החדש ב-insert_after


def _strip_parens(label: str) -> str:
    """מסירה סוגריים עוטפים ("(א)" -> "א") - numbering.next_inserted_label/
    next_appended_label עובדות על תוויות עירומות (בדיוק כמו מספרי סעיף
    ראשי, "5"/"6"), בעוד סעיפים קטנים/פסקאות תמיד נושאים סוגריים משלהם
    כחלק מ-number (ראו wikitext_parser._SUBSECTION_LABEL/_PARAGRAPH_LABEL -
    הארגומנט הגולמי בתבנית כבר כולל את הסוגריים). בלי ההסרה/העטיפה
    כאן, next_inserted_label מקבל "(א)" ומפרש את ")" כ"סיומת לא ספרתית"
    בטעות - באג אמיתי שנתפס רק כשנבדק מול חוק אמיתי, לא fixture סינתטי
    עם תוויות בלי סוגריים."""
    if label.startswith("(") and label.endswith(")"):
        return label[1:-1]
    return label


def _wrap_parens(label: str) -> str:
    return f"({label})"


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


def _resolve(root: LegislativeNode, node_id: str, level: str) -> _Resolution:
    if _find_by_id(root, node_id) is None:
        return _Resolution(supported=False, reason=f"צומת לא נמצא: {node_id!r}")

    if level == "section":
        anchor_section = _ancestor_of_type(root, node_id, "section")
        if anchor_section is None:
            return _Resolution(supported=False, reason="לא נמצא סעיף אב להוספה אחריו")
        siblings = [c for c in root.children if c.node_type == "section"]
        existing_numbers = [c.number for c in siblings]
        idx = next(i for i, c in enumerate(siblings) if c.id == anchor_section.id)
        if idx == len(siblings) - 1:
            label = next_appended_label(sort_section_numbers(existing_numbers))
        else:
            label = next_inserted_label(anchor_section.number, set(existing_numbers))
        return _Resolution(
            supported=True, label=label, kind="section", anchor_number=anchor_section.number
        )

    if level == "subsection":
        anchor_section = _ancestor_of_type(root, node_id, "section")
        if anchor_section is None:
            return _Resolution(supported=False, reason="לא נמצא סעיף אב")
        subsections = [c for c in anchor_section.children if c.is_normative and c.node_type == "subsection"]
        if not subsections:
            # עדיין אין סעיפים קטנים בסעיף הזה - AddFirstSubsection
            # תמיד קובע "(א)" לתוכן הקיים ו-"(ב)" לחדש (§7.10.6(ד)).
            return _Resolution(
                supported=True, label="(ב)", kind="add_first_subsection",
                section_number=anchor_section.number,
            )
        current_node = _find_by_id(root, node_id)
        anchor_subsection = current_node if current_node.node_type == "subsection" else subsections[-1]
        existing_numbers = [_strip_parens(c.number) for c in subsections]
        idx = next((i for i, c in enumerate(subsections) if c.id == anchor_subsection.id), len(subsections) - 1)
        if idx == len(subsections) - 1:
            label = _wrap_parens(next_appended_label(existing_numbers))
        else:
            label = _wrap_parens(
                next_inserted_label(_strip_parens(anchor_subsection.number), set(existing_numbers))
            )
        return _Resolution(
            supported=True, label=label, kind="insert_after",
            section_number=anchor_section.number, anchor_id=anchor_subsection.id,
            node_type="subsection",
        )

    if level == "paragraph":
        current_node = _find_by_id(root, node_id)
        parent = _find_parent(root, node_id)
        if current_node.node_type != "paragraph" or parent is None or parent.node_type != "section":
            return _Resolution(
                supported=False,
                reason=(
                    "הוספת פסקה נתמכת רק כשהיא ילד ישיר של סעיף (לא של סעיף "
                    "קטן) - אין עדיין תמיכה בהוספת פסקה בתוך סעיף קטן קיים"
                ),
            )
        paragraphs = [c for c in parent.children if c.is_normative and c.node_type == "paragraph" and c.number]
        if not paragraphs:
            return _Resolution(
                supported=False,
                reason="אין עדיין פסקאות ממוספרות בסעיף הזה להוסיף אחריהן",
            )
        existing_numbers = [_strip_parens(c.number) for c in paragraphs]
        idx = next((i for i, c in enumerate(paragraphs) if c.id == current_node.id), None)
        if idx is None:
            return _Resolution(supported=False, reason="הפסקה הנוכחית אינה ממוספרת")
        if idx == len(paragraphs) - 1:
            label = _wrap_parens(next_appended_label(existing_numbers))
        else:
            label = _wrap_parens(
                next_inserted_label(_strip_parens(current_node.number), set(existing_numbers))
            )
        return _Resolution(
            supported=True, label=label, kind="insert_after",
            section_number=parent.number, anchor_id=current_node.id, node_type="paragraph",
        )

    if level == "definition":
        current_node = _find_by_id(root, node_id)
        if current_node is None or current_node.node_type != "definition":
            return _Resolution(
                supported=False,
                reason="הוספת הגדרה זמינה רק כשעומדים על הגדרה קיימת",
            )
        section = _ancestor_of_type(root, node_id, "section")
        if section is None:
            return _Resolution(supported=False, reason="לא נמצא סעיף אב להגדרה")
        # הגדרות לא ממוספרות (ממוינות א"ב, לא מספור סידורי) - אין
        # תווית לחשב, בניגוד לסעיף קטן/פסקה.
        return _Resolution(
            supported=True, label="ללא מספור", kind="insert_after",
            section_number=section.number, anchor_id=current_node.id,
            node_type="definition",
        )

    return _Resolution(supported=False, reason=f"רמה לא נתמכת: {level!r}")


def preview_insertion_label(root: LegislativeNode, node_id: str, level: str) -> InsertPreview:
    r = _resolve(root, node_id, level)
    return InsertPreview(supported=r.supported, label=r.label, reason=r.reason)


def build_insertion_transform(
    root: LegislativeNode, node_id: str, level: str, *, text: str,
    margin_title: str | None = None, new_id: str | None = None,
):
    """בונה את אובייקט ה-transform.py המתאים, או מחזירה (None, reason) אם
    לא נתמך. margin_title חובה (ולא ריק) רק עבור level=='section' - המשתמש
    מקליד אותה, המערכת לא ממציאה (ראו transform.InsertSectionAfter).

    new_id: מזהה הצומת החדש. כשהלקוח מספק אחד (מזהה יציב שהוא עצמו
    יצר, ראו apps/api/apply_changes.py) - הוא נשמר כמו שהוא, כדי
    שהעץ המוחזר מ-/render יישא את אותו מזהה בכל קריאה חוזרת על אותה
    הוספה (הכרחי כדי שהלקוח יוכל למפות מחדש DOM<->צומת אחרי רינדור-מחדש
    מלא של העץ). בלי new_id (ברירת מחדל, לתאימות טסטים קיימים) -
    _fresh_id() הישן, שאינו יציב בין קריאות (מונה גלובלי מצטבר)."""
    r = _resolve(root, node_id, level)
    if not r.supported:
        return None, r.reason

    if r.kind == "section":
        if not margin_title or not margin_title.strip():
            return None, "סעיף ראשי חדש חייב כותרת שוליים - יש להקליד אותה"
        new_section = LegislativeNode(
            id=new_id or _fresh_id("section"), node_type="section", number="",
            margin_title=margin_title, text=text,
        )
        return InsertSectionAfter(after_section_number=r.anchor_number, new_section=new_section), None

    if r.kind == "add_first_subsection":
        new_child = LegislativeNode(
            id=new_id or _fresh_id("subsection"), node_type="paragraph", number="",
            margin_title=None, text=text,
        )
        return AddFirstSubsection(section_number=r.section_number, new_child=new_child), None

    if r.kind == "insert_after":
        # r.label כבר מחושב על ידי _resolve (numbering.next_inserted_label/
        # next_appended_label) - InsertAfter הקיים (מקרה זהב 4/6) לא מחשב
        # מספור בעצמו, אז חייבים להצמיד את התווית כאן ולא להשאיר ריק.
        # הגדרות הן חריגה: לא ממוספרות בכלל (r.label הוא רק טקסט תצוגה
        # "ללא מספור", לא ערך שמותר לשים ב-number בפועל).
        number = "" if r.node_type == "definition" else r.label
        new_child = LegislativeNode(
            id=new_id or _fresh_id(r.node_type), node_type=r.node_type, number=number,
            margin_title=None, text=text,
        )
        return (
            InsertAfter(section_number=r.section_number, anchor_id=r.anchor_id, new_child=new_child),
            None,
        )

    return None, "מקרה לא צפוי"
