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
    """מוסיף inserted_text מיד אחרי anchor_substring בתוך הטקסט של הצומת
    עם target_id. anchor_substring חייב להופיע פעם אחת בדיוק בטקסט -
    אפס הופעות או יותר מאחת הן שגיאה, לא ניחוש איזו הופעה התכוונו אליה
    (אותו עיקרון כמו ReplaceWords למטה)."""

    target_id: str
    anchor_substring: str
    inserted_text: str


@dataclass
class ReplaceWords:
    """מחליף ביטוי קיים (old_phrase) בטקסט של הצומת עם target_id בביטוי
    חדש (new_phrase). שני הביטויים הם בחירה מפורשת של המנסח - גבול
    הביטוי נקבע לפי משמעות משפטית (מה ראוי לצטט לשם בהירות בהוראת
    התיקון), לא נגזר מדיף טקסטואלי אוטומטי בין לפני/אחרי. ראו
    packages/amend/engine.py (_diff_replace) ודיון ב-TASKS.md משימה 4א:
    דיף מינימלי (prefix/suffix משותפים) מנחש גבולות ביטוי, וזו בדיוק
    התקלה שכבר קרתה בשקט עבור _diff_text/הכנסה (סעיף 5 קייטנות: "מאסר
    ששה חדשים" -> "מאסר שנה" - דיף מינימלי היה משמיט את "מאסר" המשותף,
    בעוד שהניסוח המשפטי הרצוי כולל אותו).

    old_phrase חייב להופיע פעם אחת בדיוק בטקסט המקורי: אפס הופעות או
    יותר מאחת הן שגיאה, לא ניחוש. הופעה כפולה מכוונת (להחליף בכל
    המופעים) היא דפוס נפרד - "החלפה בכל מקום", drafting-rules.md §1.1
    שורה 3 - שלא ממומש עדיין."""

    target_id: str
    old_phrase: str
    new_phrase: str


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
    before: LegislativeNode,
    transformations: list[InsertAfter | InsertWordsAfter | ReplaceWords],
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
            count = target.text.count(t.anchor_substring)
            if count == 0:
                raise ValueError(f"'{t.anchor_substring}' לא נמצא בטקסט {t.target_id}")
            if count > 1:
                raise ValueError(
                    f"'{t.anchor_substring}' מופיע {count} פעמים בטקסט "
                    f"{t.target_id} - דו-משמעי, לא ניתן לקבוע עוגן יחיד "
                    "בלי לנחש."
                )
            pos = target.text.find(t.anchor_substring)
            insert_at = pos + len(t.anchor_substring)
            target.text = target.text[:insert_at] + t.inserted_text + target.text[insert_at:]
        elif isinstance(t, ReplaceWords):
            target = _find_by_id(after, t.target_id)
            if target is None:
                raise ValueError(f"צומת {t.target_id} לא נמצא")
            count = target.text.count(t.old_phrase)
            if count == 0:
                raise ValueError(f"'{t.old_phrase}' לא נמצא בטקסט {t.target_id}")
            if count > 1:
                raise ValueError(
                    f"'{t.old_phrase}' מופיע {count} פעמים בטקסט {t.target_id} "
                    "- דו-משמעי. אם הכוונה להחליף בכל המופעים, זה דפוס נפרד "
                    "('החלפה בכל מקום', drafting-rules.md §1.1 שורה 3) שלא "
                    "ממומש עדיין."
                )
            pos = target.text.find(t.old_phrase)
            # סמן פנימי בלבד (כמו ⟦footnote:key⟧) - מעביר את הביטויים
            # המפורשים ל-engine._diff_replace בלי שהיא תצטרך לנחש אותם
            # מתוך דיף. נקרא ונמחק שם; לא אמור להגיע לרינדור.
            target.text = (
                target.text[:pos]
                + f"⟦replaced-from:{t.old_phrase}⟧"
                + t.new_phrase
                + "⟦/replaced⟧"
                + target.text[pos + len(t.old_phrase) :]
            )
        else:
            raise TypeError(f"טרנספורמציה לא מוכרת: {t!r}")
    return after
