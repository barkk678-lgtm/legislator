"""מודלי בקשה/תשובה ל-API. ראו TASKS.md משימה 10.

אין כאן לוגיקה - רק צורת הנתונים שעוברים בין הלקוח ל-packages/amend
הקיימים. transform_in_to_dataclass() היא המרה מכנית 1:1, לא החלטה.
"""

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
from transform import InsertAfter, InsertWordsAfter, ReplaceWords  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
from node import LegislativeNode  # noqa: E402


class InsertWordsAfterIn(BaseModel):
    kind: Literal["insert_words"]
    target_id: str
    anchor_substring: str
    inserted_text: str


class ReplaceWordsIn(BaseModel):
    kind: Literal["replace_words"]
    target_id: str
    old_phrase: str
    new_phrase: str


class InsertNewChildIn(BaseModel):
    kind: Literal["insert_new_child"]
    section_number: str
    anchor_id: str
    node_type: Literal["definition", "paragraph", "subsection", "subparagraph"]
    text: str


TransformationIn = InsertWordsAfterIn | ReplaceWordsIn | InsertNewChildIn


class BillMetaIn(BaseModel):
    title: str
    initiator: str
    submitted_date: str
    source_ref: str  # מראה מקום - שדה חובה (ראו law_registry.LawConfig)


class PreviewRequest(BaseModel):
    transformations: list[TransformationIn]
    bill: BillMetaIn


_NEW_CHILD_COUNTER = {"n": 0}


def _fresh_new_child_id(anchor_id: str) -> str:
    _NEW_CHILD_COUNTER["n"] += 1
    return f"{anchor_id}/new-{_NEW_CHILD_COUNTER['n']}"


def transformation_in_to_dataclass(item: TransformationIn):
    """המרה מכנית 1:1 מ-schema ל-transform.py dataclass - לא לוגיקה
    משפטית. מזהה הצומת החדש (InsertAfter) הוא פרט טכני פנימי, לא נוסח
    חוק - מותר לייצר אותו כאן בלי קלט מהמשתמש."""
    if isinstance(item, InsertWordsAfterIn):
        return InsertWordsAfter(
            target_id=item.target_id,
            anchor_substring=item.anchor_substring,
            inserted_text=item.inserted_text,
        )
    if isinstance(item, ReplaceWordsIn):
        return ReplaceWords(
            target_id=item.target_id, old_phrase=item.old_phrase, new_phrase=item.new_phrase
        )
    if isinstance(item, InsertNewChildIn):
        new_child = LegislativeNode(
            id=_fresh_new_child_id(item.anchor_id),
            node_type=item.node_type,
            number="",
            margin_title=None,
            text=item.text,
        )
        return InsertAfter(section_number=item.section_number, anchor_id=item.anchor_id, new_child=new_child)
    raise TypeError(f"סוג טרנספורמציה לא מוכר: {item!r}")
