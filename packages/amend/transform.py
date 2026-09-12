"""apply(): בניית עץ "אחרי" כטרנספורמציה מפורשת על עץ "לפני". ראו TASKS.md משימה 4.

למה לא לכתוב את עץ ה"אחרי" ביד: זה מחזיר את בעיית המעגליות בדלת
האחורית - כתיבת עץ מתוך היכרות עם התשובה הרצויה במקום מהמקור. במקום
זה, רשימת טרנספורמציות מפורשת מתעדת בדיוק מה השתנה, ו-apply() בונה
את ה"אחרי" דטרמיניסטית מתוך ה"לפני" האמיתי (מ-ingest, משימה 3).

טהור: בלי רשת, בלי LLM (חוק ברזל 2).
"""

import copy
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
from node import LegislativeNode  # noqa: E402


@dataclass
class InsertAfter:
    """מוסיף new_child כאח מיד אחרי הצומת עם anchor_id, בתוך הסעיף
    section_number. anchor_id מזהה צומת קיים ב"לפני" - יציב, לא תלוי
    במיקום, כדי שכמה טרנספורמציות ברצף לא יתבלבלו זו בזו."""

    section_number: str
    anchor_id: str
    new_child: LegislativeNode


@dataclass
class InsertWordsAfter:
    """מוסיף inserted_text מיד אחרי המופע הראשון של anchor_substring
    בתוך הטקסט של הצומת עם target_id."""

    target_id: str
    anchor_substring: str
    inserted_text: str


def _find_section(node: LegislativeNode, number: str) -> LegislativeNode | None:
    for child in node.children:
        if child.node_type == "section" and child.number == number:
            return child
        found = _find_section(child, number)
        if found:
            return found
    return None


def _find_by_id(node: LegislativeNode, node_id: str) -> LegislativeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find_by_id(child, node_id)
        if found:
            return found
    return None


def apply(
    before: LegislativeNode, transformations: list[InsertAfter | InsertWordsAfter]
) -> LegislativeNode:
    """מחזיר עץ "אחרי" חדש (before לא משתנה), אחרי החלת כל הטרנספורמציות
    בסדר שבו הן מופיעות ברשימה."""
    after = copy.deepcopy(before)
    for t in transformations:
        if isinstance(t, InsertAfter):
            section = _find_section(after, t.section_number)
            if section is None:
                raise ValueError(f"סעיף {t.section_number} לא נמצא ב'לפני'")
            idx = next(
                (i for i, c in enumerate(section.children) if c.id == t.anchor_id),
                None,
            )
            if idx is None:
                raise ValueError(f"עוגן {t.anchor_id} לא נמצא בסעיף {t.section_number}")
            section.children.insert(idx + 1, copy.deepcopy(t.new_child))
        elif isinstance(t, InsertWordsAfter):
            target = _find_by_id(after, t.target_id)
            if target is None:
                raise ValueError(f"צומת {t.target_id} לא נמצא")
            pos = target.text.find(t.anchor_substring)
            if pos < 0:
                raise ValueError(f"'{t.anchor_substring}' לא נמצא בטקסט {t.target_id}")
            insert_at = pos + len(t.anchor_substring)
            target.text = target.text[:insert_at] + t.inserted_text + target.text[insert_at:]
        else:
            raise TypeError(f"טרנספורמציה לא מוכרת: {t!r}")
    return after
