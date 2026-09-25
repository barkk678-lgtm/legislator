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
- "paragraph": זמין כשהצומת הנוכחי הוא פסקה ממוספרת - בין אם היא ילד
  ישיר של סעיף ובין אם היא בתוך סעיף קטן (הורחב במשימה 58; קודם לכן
  רק ילד ישיר של סעיף, כי transform.InsertAfter חיפש את העוגן רק בין
  הילדים הישירים של הסעיף). המספור נגזר מאחיה של הפסקה בתוך ההורה
  בפועל, כי מספור פסקאות מתאפס בכל סעיף קטן.
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
from node import LegislativeNode, find_parent, find_sections  # noqa: E402
from numbering import next_appended_label, next_inserted_label, sort_section_numbers  # noqa: E402
from transform import AddFirstParagraph, AddFirstSubsection, InsertAfter, InsertSectionAfter  # noqa: E402

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


def _ancestor_of_type(root: LegislativeNode, node_id: str, node_type: str) -> LegislativeNode | None:
    """מוצאת את האב מהסוג המבוקש (כולל הצומת עצמו אם הוא כבר מהסוג הזה) -
    מטפסת מהצומת כלפי מעלה עד השורש. משתמשת ב-find_parent המשותפת
    (node.py) - הועברה לשם (2026-09-16) כדי שלא תשוכפל גם ב-
    packages/amend/transform.py, שזקוקה לאותה פונקציה בדיוק כדי
    להכניס InsertSectionAfter לפרק/סימן הנכון."""
    node = _find_by_id(root, node_id)
    if node is None:
        return None
    if node.node_type == node_type:
        return node
    current_id = node.id
    while True:
        parent = find_parent(root, current_id)
        if parent is None:
            return None
        if parent.node_type == node_type:
            return parent
        current_id = parent.id



def _unnumbered_ancestor(root: LegislativeNode, node_id: str) -> str | None:
    """מחזירה את סוג הצומת הראשון **בלי מספר** בשרשרת שבין הסעיף לצומת
    (לא כולל הצומת עצמו ולא כולל הסעיף), או None אם כל השרשרת ממוספרת.

    זה המחסום שמונע כתובת שגויה בשקט: `engine._container_suffix` בונה
    את המכולה מהמספרים בלבד, ולכן צומת בלי מספר פשוט נעלם מהכתובת -
    "בסעיף 1, אחרי פסקה (1)" במקום כתובת שמזהה את המקום הנכון."""
    parent = find_parent(root, node_id)
    while parent is not None and parent.node_type not in ("section", "law"):
        # הגדרה אינה "צומת בלי מספר" לעניין הזה: היא מזוהה בכתובת
        # לפי המונח המוגדר, במילים (engine._definition_clause), ולכן
        # אינה נעלמת ממנה - ראו §7.9.1.
        if not parent.number and parent.node_type != "definition":
            return parent.node_type
        parent = find_parent(root, parent.id)
    return None


def _resolve(root: LegislativeNode, node_id: str, level: str) -> _Resolution:
    if _find_by_id(root, node_id) is None:
        return _Resolution(supported=False, reason=f"צומת לא נמצא: {node_id!r}")

    if level == "section":
        anchor_section = _ancestor_of_type(root, node_id, "section")
        if anchor_section is None:
            return _Resolution(supported=False, reason="לא נמצא סעיף אב להוספה אחריו")
        # תוקן (2026-09-16): רשימה גלובלית של כל מספרי הסעיפים בחוק
        # (find_sections, לא רק root.children) - "האם זה הסעיף האחרון"
        # נבדק מול מספור גלובלי, בדיוק כמו transform.InsertSectionAfter
        # (אותו נימוק - ראו שם).
        existing_numbers = list(find_sections(root).keys())
        sorted_numbers = sort_section_numbers(existing_numbers)
        if sorted_numbers[-1] == anchor_section.number:
            label = next_appended_label(sorted_numbers)
        else:
            label = next_inserted_label(anchor_section.number, set(existing_numbers))
        return _Resolution(
            supported=True, label=label, kind="section", anchor_number=anchor_section.number
        )

    if level == "subsection":
        anchor_section = _ancestor_of_type(root, node_id, "section")
        if anchor_section is None:
            return _Resolution(supported=False, reason="לא נמצא סעיף אב")
        current_node = _find_by_id(root, node_id)
        # תוקן (משימה 61): המספור נגזר מ**האחים בפועל** של העוגן, לא
        # מהסעיפים הקטנים שברמת הסעיף. סעיף קטן יכול לשבת בעומק - למשל
        # (א)/(ב) בתוך פסקה (2) בתוך סעיף קטן (א) (30 מופעים בקורפוס
        # בחוק העונשין לבדו). עד לתיקון, עמידה על סעיף קטן כזה הציעה
        # תווית שנגזרה מהאחים הלא-נכונים: במאבק בארגוני פשיעה, סעיף
        # 18(א)(2), האחים בפועל הם (א) ו-(ב) והתווית הנכונה היא (א1),
        # אבל המערכת הציעה **(ד)** - המשך המספור של (א),(ב),(ג) שברמת
        # הסעיף. זה לא היה חסום, אלא הוצע בשקט כתווית תקינה - חמור
        # יותר מחסימה, כי המשתמש לא יכול לדעת שהמספר שגוי.
        if current_node is not None and current_node.node_type == "subsection":
            sibling_parent = find_parent(root, node_id)
        else:
            sibling_parent = anchor_section
        if sibling_parent is None:
            return _Resolution(supported=False, reason="לא נמצא הורה לצומת")
        subsections = [
            c for c in sibling_parent.children if c.is_normative and c.node_type == "subsection"
        ]
        if not subsections:
            # עדיין אין סעיפים קטנים בסעיף הזה - AddFirstSubsection
            # תמיד קובע "(א)" לתוכן הקיים ו-"(ב)" לחדש (§7.10.6(ד)).
            return _Resolution(
                supported=True, label="(ב)", kind="add_first_subsection",
                section_number=anchor_section.number,
            )
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
        parent = find_parent(root, node_id)
        # הורחב (משימה 58): פסקה בתוך סעיף קטן קיים נתמכת מעכשיו -
        # transform.InsertAfter מוצא את העוגן בכל עומק בתוך הסעיף
        # ומכניס אל ההורה בפועל. המספור נגזר מ**אחיה של הפסקה** (ילדי
        # אותו סעיף קטן), לא מכל פסקאות הסעיף: מספור פסקאות מתאפס בכל
        # סעיף קטן, ולכן "אחרי פסקה (2)" בתוך סעיף קטן (א) מתייחס
        # לפסקאות של (א) בלבד.
        if (current_node is not None and current_node.node_type == "subsection"
                and current_node.number and current_node.text.strip()
                and not any(c.is_normative for c in current_node.children)):
            # ח11-ב (26.9): סעיף קטן בלי פסקאות - "(א) הופך ל-(א)(1)": הנוסח
            # הקיים הופך לפסקה (1), והחדש - (2). transform.AddFirstParagraph.
            anchor_section = _ancestor_of_type(root, node_id, "section")
            if anchor_section is None:
                return _Resolution(supported=False, reason="לא נמצא סעיף אב")
            if _unnumbered_ancestor(root, node_id) is not None:
                return _Resolution(supported=False, reason="בשרשרת שמעל הסעיף הקטן יש יחידה בלי מספר")
            return _Resolution(
                supported=True, label="(2)", kind="add_first_paragraph",
                section_number=anchor_section.number, anchor_id=current_node.id,
            )
        if current_node is None or current_node.node_type != "paragraph" or parent is None:
            return _Resolution(
                supported=False,
                reason="הוספת פסקה זמינה רק כשעומדים על פסקה ממוספרת קיימת",
            )
        # הורחב (משימה 61): גם פסקה בתוך פסקה נתמכת - 234 מופעים
        # בקורפוס, והניסוח קיים ונמדד: `בסעיף 3(1) לחוק העיקרי, במקום
        # "לחלוטין" יבוא` (13948380.docx). מה שנשאר חסום הוא פסקה בתוך
        # **הגדרה**, ומטעם מהותי ולא טכני: כתובת ההוראה חייבת לנקוב
        # בהגדרה עצמה - `בסעיף N, בהגדרה "X", ...` (מדריך משפטים
        # §7.9.1, עמ' 26) - וזו צורה במילים, לא מכולה בסוגריים.
        # להגדרה אין מספר, ולכן _container_suffix פשוט מדלגת עליה:
        # ההוראה שהייתה יוצאת היא `בסעיף 1, אחרי פסקה (1) יבוא:`, בלי
        # שום אזכור של ההגדרה - הוראת תיקון **שגויה**, לא רק חלקית.
        # חסימה מוצהרת עדיפה על ניסוח שקט ושגוי.
        # **נפתח (משימה 62).** עד אז הדפוס הזה היה חסום כי המכולה
        # בסוגריים מדלגת על ההגדרה (אין לה מספר), וההוראה שהייתה
        # יוצאת - `בסעיף 1, אחרי פסקה (1) יבוא:` - הצביעה על מקום
        # אחר בחוק. עכשיו `engine._definition_clause` מנסחת את
        # ההגדרה **במילים**, כפי שהמדריך קובע: `בסעיף N לחוק
        # העיקרי, בהגדרה "X", ...` (§7.9.1, עמ' 26). תיקון הגדרות
        # הוא מהדפוסים הנפוצים ביותר בהצעות אמיתיות - 69 מופעים
        # של פסקה בתוך הגדרה בארבעת הפיקסצ'רים לבדם.
        if parent.node_type not in ("section", "subsection", "paragraph", "definition"):
            return _Resolution(
                supported=False,
                reason=(
                    f"פסקה בתוך {parent.node_type!r} אינה נתמכת - נתמכות פסקאות "
                    "בתוך סעיף, סעיף קטן, פסקה או הגדרה"
                ),
            )
        # מחסום כללי: אם יש בשרשרת שבין הסעיף לעוגן צומת בלי מספר,
        # הכתובת שתיווצר תדלג עליו בשקט ותצביע על מקום אחר בחוק. אין
        # ניחוש - חוסמים ואומרים למה.
        unnumbered = _unnumbered_ancestor(root, node_id)
        if unnumbered is not None:
            return _Resolution(
                supported=False,
                reason=(
                    f"בשרשרת שמעל הפסקה יש {unnumbered!r} בלי מספר - כתובת "
                    "ההוראה הייתה מדלגת עליו ומצביעה על מקום אחר בחוק"
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
        # section_number חייב להיות מספר ה**סעיף**, גם כשההורה הישיר
        # הוא סעיף קטן - transform.InsertAfter מאתר לפיו את הסעיף,
        # ומשם יורד אל ההורה בפועל.
        anchor_section = _ancestor_of_type(root, node_id, "section")
        if anchor_section is None:
            return _Resolution(supported=False, reason="לא נמצא סעיף אב לפסקה")
        return _Resolution(
            supported=True, label=label, kind="insert_after",
            section_number=anchor_section.number, anchor_id=current_node.id,
            node_type="paragraph",
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

    if r.kind == "add_first_paragraph":
        new_child = LegislativeNode(
            id=new_id or _fresh_id("paragraph"), node_type="paragraph", number="",
            margin_title=None, text=text,
        )
        return AddFirstParagraph(section_number=r.section_number, unit_id=r.anchor_id,
                                 new_child=new_child), None

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
