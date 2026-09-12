"""ממיר LegislativeNode לעץ dict-ים פשוט, קריא ל-Jinja2/JSON - לא בונה
HTML בפייתון (זו עבודת הטמפלט/הלקוח). טהור: אין כאן לוגיקה משפטית,
רק תיוג type_label ומעבר רקורסיבי. ראו TASKS.md משימה 10.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
from node import LegislativeNode, effective_as_of  # noqa: E402

TYPE_HE = {
    "law": "חוק",
    "part": "חלק",
    "chapter": "פרק",
    "siman": "סימן",
    "section": "סעיף",
    "subsection": "סעיף קטן",
    "paragraph": "פסקה",
    "subparagraph": "פסקת משנה",
    "definition": "הגדרה",
}


def node_view(node: LegislativeNode) -> dict:
    return {
        "id": node.id,
        "node_type": node.node_type,
        "type_label": TYPE_HE.get(node.node_type, node.node_type),
        "number": node.number,
        "margin_title": node.margin_title,
        "full_title": node.full_title,  # משמעותי רק בשורש (node_type=="law")
        "text": node.text,
        "is_normative": node.is_normative,
        "status": node.status,
        "children": [node_view(c) for c in node.children],
    }


def _serialize(node: LegislativeNode) -> str:
    """ייצוג טקסטואלי שטוח של צומת+צאצאיו - לצורך השוואת לפני/אחרי
    בלבד (touched_section_numbers), לא לתצוגה."""
    parts = [node.text]
    parts.extend(_serialize(c) for c in node.children)
    return "␟".join(parts)  # מפריד בקרה שלא אמור להופיע בנוסח אמיתי


def touched_section_numbers(before: LegislativeNode, after: LegislativeNode) -> set[str]:
    """סעיפים שהטקסט שלהם (או של מי מצאצאיהם) שונה בין העצים - כדי
    להדגיש בתצוגת ה'אחרי' איפה יש שינוי, בלי תלות בפרטי amend()."""
    before_sections = {c.number: c for c in before.children if c.node_type == "section"}
    after_sections = {c.number: c for c in after.children if c.node_type == "section"}
    touched = set()
    for number, before_sec in before_sections.items():
        after_sec = after_sections.get(number)
        if after_sec is None or _serialize(before_sec) != _serialize(after_sec):
            touched.add(number)
    return touched


def as_of_display(root: LegislativeNode) -> str | None:
    """הניסוח הקבוע: 'נוסח כפי שהופיע בוויקיטקסט ביום X' - לא 'מעודכן
    ליום X' (ראו docs/data-sources.md). הניסוח הוא תפקיד שכבת התצוגה,
    לא של node.py/wikitext_parser.py עצמם."""
    value = effective_as_of(root, root)
    if value is None:
        return None
    date_part = value[:10] if len(value) >= 10 else value
    return f"נוסח כפי שהופיע בוויקיטקסט ביום {date_part}"
