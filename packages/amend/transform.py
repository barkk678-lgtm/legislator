"""apply(): בניית עץ "אחרי" כטרנספורמציה מפורשת על עץ "לפני". ראו TASKS.md משימה 4.

למה לא לכתוב את עץ ה"אחרי" ביד: זה מחזיר את בעיית המעגליות בדלת
האחורית - כתיבת עץ מתוך היכרות עם התשובה הרצויה במקום מהמקור. במקום
זה, רשימת טרנספורמציות מפורשת מתעדת בדיוק מה השתנה, ו-apply() בונה
את ה"אחרי" דטרמיניסטית מתוך ה"לפני" האמיתי (מ-ingest, משימה 3).

טהור: בלי רשת, בלי LLM (חוק ברזל 2).

**עיקרון (מ-2026-09, משימה 4א המשך):** LegislativeNode.text מכיל
תמיד נוסח חוק בלבד - בלי יוצא מן הכלל, גם בעץ "אחרי" הזמני שנבנה כאן.
מידע שעדיין "בתהליך" (ביטוי ישן/חדש של החלפה, מיקום הפניית הערת
שוליים) לא מוטבע בתוך .text כסמן טקסטואלי (⟦...⟧) - זה בעבר הוביל
לחשש ממשי (לא תקלה בפועל, אבל בלי מחסום מבני) שקוד עתידי שיקרא את
עץ ה"אחרי" ישירות (למשל משימה 11: הכיוון ההפוך, הצעת חוק ← נוסח
משולב) יציג את הסמן הגולמי כאילו הוא נוסח חוק אמיתי. במקום זה, apply()
מחזיר זוג: עץ נקי + רשימת אנוטציות (ReplacementAnnotation /
FootnoteAnnotation) שמצביעות על צמתים לפי id - ערוץ נפרד לגמרי מהעץ.
"""

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
from node import LegislativeNode  # noqa: E402


@dataclass
class InsertAfter:
    """מוסיף new_child כאח מיד אחרי הצומת עם anchor_id, בתוך הסעיף
    section_number. anchor_id מזהה צומת קיים ב"לפני" - יציב, לא תלוי
    במיקום, כדי שכמה טרנספורמציות ברצף לא יתבלבלו זו בזו.

    footnotes: רשימת (anchor_substring, key) - איפה בתוך new_child.text
    (הנקי, בלי שום סמן) ממוקמת הפניית הערת שוליים חיצונית: מיד אחרי
    anchor_substring. anchor_substring חייב להופיע פעם אחת בדיוק
    (אותו עיקרון-אי-ניחוש כמו InsertWordsAfter/ReplaceWords למטה)."""

    section_number: str
    anchor_id: str
    new_child: LegislativeNode
    footnotes: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class AddFirstSubsection:
    """הופך סעיף שאין בו עדיין סעיפים קטנים (תוכנו כולו ילד יחיד בלי
    תווית) לסעיף עם סעיף קטן (א) [תוכנו הקיים, ללא כל שינוי בטקסט
    עצמו] וסעיף קטן (ב) חדש - ha-hoveret-ha-sgula.pdf §7.10.6(ד).

    **אסור להשתמש בזה אם התוכן הקיים גם צריך להשתנות** (לא רק לקבל
    תווית) - למדריך יש דפוס נפרד לכך (פיצול לשתי הוראות ממוספרות,
    ראו התיעוד המצוטט ב-docs/drafting-rules.md), שלא ממומש כאן.

    section_number: הסעיף שיש לו כרגע ילד נורמטיבי יחיד בלי תווית.
    new_child: התוכן החדש - מקבל number="ב" אוטומטית (וגם node_type
    "subsection"); אסור לקבוע לו number/node_type מראש."""

    section_number: str
    new_child: LegislativeNode
    footnotes: list[tuple[str, str]] = field(default_factory=list)


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
    packages/amend/engine.py ודיון ב-TASKS.md משימה 4א: דיף מינימלי
    (prefix/suffix משותפים) מנחש גבולות ביטוי, וזו בדיוק התקלה שכבר
    קרתה בשקט עבור _diff_text/הכנסה (סעיף 5 קייטנות: "מאסר ששה חדשים"
    -> "מאסר שנה" - דיף מינימלי היה משמיט את "מאסר" המשותף, בעוד
    שהניסוח המשפטי הרצוי כולל אותו).

    old_phrase חייב להופיע פעם אחת בדיוק בטקסט המקורי: אפס הופעות או
    יותר מאחת הן שגיאה, לא ניחוש. הופעה כפולה מכוונת (להחליף בכל
    המופעים) היא דפוס נפרד - "החלפה בכל מקום", drafting-rules.md §1.1
    שורה 3 - שלא ממומש עדיין."""

    target_id: str
    old_phrase: str
    new_phrase: str


@dataclass
class ReplacementAnnotation:
    """מצביעה על צומת (node_id) שעבר ReplaceWords, עם שני הביטויים
    כפי שנבחרו במפורש - ערוץ נפרד מ-.text, לא סמן מוטבע בתוכו (ראו
    תיעוד המודול). engine.amend() קורא את זה ישירות, בלי לפרסר טקסט."""

    node_id: str
    old_phrase: str
    new_phrase: str


@dataclass
class FootnoteAnnotation:
    """מצביעה על מיקום הפניית הערת שוליים בתוך .text הנקי של צומת חדש
    (node_id) שהוכנס דרך InsertAfter. offset הוא מיקום התו (ב-.text
    הסופי, הנקי) שבו יש להציב את ההפניה."""

    node_id: str
    offset: int
    key: str


Annotation = ReplacementAnnotation | FootnoteAnnotation


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
    transformations: list[InsertAfter | AddFirstSubsection | InsertWordsAfter | ReplaceWords],
) -> tuple[LegislativeNode, list[Annotation]]:
    """מחזיר (עץ "אחרי" חדש, רשימת אנוטציות) - before לא משתנה. .text
    בעץ המוחזר מכיל תמיד נוסח חוק בלבד; כל מידע "בתהליך" עובר דרך
    האנוטציות, לא מוטבע בטקסט (ראו תיעוד המודול)."""
    after = copy.deepcopy(before)
    annotations: list[Annotation] = []
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
            new_child = copy.deepcopy(t.new_child)
            section.children.insert(idx + 1, new_child)
            for anchor_substring, key in t.footnotes:
                count = new_child.text.count(anchor_substring)
                if count == 0:
                    raise ValueError(f"'{anchor_substring}' לא נמצא בטקסט {new_child.id}")
                if count > 1:
                    raise ValueError(
                        f"'{anchor_substring}' מופיע {count} פעמים בטקסט "
                        f"{new_child.id} - דו-משמעי, לא ניתן לקבוע מיקום יחיד "
                        "בלי לנחש."
                    )
                pos = new_child.text.find(anchor_substring)
                annotations.append(
                    FootnoteAnnotation(
                        node_id=new_child.id, offset=pos + len(anchor_substring), key=key
                    )
                )
        elif isinstance(t, AddFirstSubsection):
            section = _find_section(after, t.section_number)
            if section is None:
                raise ValueError(f"סעיף {t.section_number} לא נמצא ב'לפני'")
            normative_children = [c for c in section.children if c.is_normative]
            if len(normative_children) != 1 or normative_children[0].number:
                raise ValueError(
                    f"AddFirstSubsection דורש סעיף עם תוכן נורמטיבי יחיד "
                    f"וללא סעיפים קטנים קיימים - סעיף {t.section_number} "
                    "לא עומד בכך."
                )
            existing = normative_children[0]
            existing.number = "א"
            existing.node_type = "subsection"
            new_child = copy.deepcopy(t.new_child)
            new_child.number = "ב"
            new_child.node_type = "subsection"
            idx = section.children.index(existing)
            section.children.insert(idx + 1, new_child)
            for anchor_substring, key in t.footnotes:
                count = new_child.text.count(anchor_substring)
                if count == 0:
                    raise ValueError(f"'{anchor_substring}' לא נמצא בטקסט {new_child.id}")
                if count > 1:
                    raise ValueError(
                        f"'{anchor_substring}' מופיע {count} פעמים בטקסט "
                        f"{new_child.id} - דו-משמעי, לא ניתן לקבוע מיקום יחיד "
                        "בלי לנחש."
                    )
                pos = new_child.text.find(anchor_substring)
                annotations.append(
                    FootnoteAnnotation(
                        node_id=new_child.id, offset=pos + len(anchor_substring), key=key
                    )
                )
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
            target.text = target.text[:pos] + t.new_phrase + target.text[pos + len(t.old_phrase) :]
            annotations.append(
                ReplacementAnnotation(
                    node_id=target.id, old_phrase=t.old_phrase, new_phrase=t.new_phrase
                )
            )
        else:
            raise TypeError(f"טרנספורמציה לא מוכרת: {t!r}")
    return after, annotations
