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
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
from node import LegislativeNode, find_parent, find_sections  # noqa: E402
from numbering import next_appended_label, next_inserted_label, sort_section_numbers  # noqa: E402


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
class InsertSectionAfter:
    """מוסיף סעיף ראשי חדש (לא סעיף קטן/פסקה בתוך סעיף קיים, אלא ילד
    חדש ברמת שורש החוק עצמו) מיד אחרי הסעיף עם after_section_number -
    ha-hoveret-ha-sgula.pdf §7.12, עמ' 31 [PDF 60]: "בחוק [שם החוק],
    אחרי סעיף [מספר הסעיף] לחוק העיקרי יבוא: 'כותרת שוליים [מספר הסעיף
    החדש] [תוכן הסעיף].'"

    new_section.number **אסור** להיקבע מראש - מחושב אוטומטית כאן
    (next_inserted_label/next_appended_label, §8.1 ב-docs/drafting-rules.md)
    לפי מיקום ההוספה, בדיוק כמו סעיף קטן/פסקה חדשים - כדי לא לפגוע
    בהפניות קיימות לסעיפים שאחרי נקודת ההוספה (אותו נימוק בדיוק כמו
    §7.10.6(א)).

    היקף מכוון, לא כללי (drafting-rules.md §8.5): הוספה בודדת בלבד.
    הוספת כמה סעיפים ראשיים חדשים רצופים זה אחרי זה (או פרק שלם) לא
    נתמכת כאן - transform.apply() עצמו לא חוסם את זה (אפשר לצרף כמה
    InsertSectionAfter ברשימה אחת), אבל engine.amend() (שממנו מגיעה
    ההבחנה בין סעיף קיים לסעיף חדש) חוסם זאת במפורש - ראו שם.

    footnotes: אותה משמעות בדיוק כמו ב-InsertAfter - (anchor_substring,
    key) בתוך new_section.text (הנקי), חייב להופיע פעם אחת בדיוק."""

    after_section_number: str
    new_section: LegislativeNode
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
class ReplaceMarginTitleWords:
    """מחליף ביטוי בכותרת השוליים של סעיף (לא בגוף הטקסט שלו) -
    ha-hoveret-ha-sgula.pdf §7.8, עמ' 26 [PDF 55]: 'בסעיף מס' הסעיף
    לחוק העיקרי, בכותרת השוליים, במקום "טקסט קיים" יבוא "טקסט חדש"'.
    אותו עיקרון בדיוק כמו ReplaceWords (גבול הביטוי הוא בחירה מפורשת,
    לא ניחוש מדיף) - פשוט פועל על section.margin_title, לא section.text
    (לסעיף עצמו אין .text משל עצמו - התוכן שלו הוא הילדים)."""

    section_number: str
    old_phrase: str
    new_phrase: str


@dataclass
class DeleteWords:
    """מוחק ביטוי מתוך הטקסט של הצומת - `המילים "X" – יימחקו`
    (מדריך משפטים §7.10.3, עמ' 28). **דפוס נפרד מהחלפה בריק**:
    עד שנוסף, מחיקה יצאה כ-`במקום "X" יבוא ""` - ניסוח שאינו קיים.

    phrase חייב להופיע פעם אחת בדיוק, כמו בכל שאר פעולות המילים."""

    target_id: str
    phrase: str


@dataclass
class InsertWordsBefore:
    """מוסיף מילים **לפני** ביטוי קיים - `לפני "X" יבוא "Y"`
    (§7.10.2, "בתחילת הסעיף")."""

    target_id: str
    before_phrase: str
    inserted_text: str


@dataclass
class AppendWordsAtEnd:
    """מוסיף מילים בסוף היחידה - `בסופו יבוא "Y"` (§7.10.2).

    **לא עוגן על המילה האחרונה**: זה היה מייצר טקסט אחרי הנקודה
    הסוגרת. התוספת נכנסת לפני סימן הפיסוק הסוגר, מאותו טעם
    שמתועד ב-merge._apply_append."""

    target_id: str
    inserted_text: str


@dataclass
class ReplacementAnnotation:
    """מצביעה על צומת (node_id) שעבר ReplaceWords, עם שני הביטויים
    כפי שנבחרו במפורש - ערוץ נפרד מ-.text, לא סמן מוטבע בתוכו (ראו
    תיעוד המודול). engine.amend() קורא את זה ישירות, בלי לפרסר טקסט."""

    node_id: str
    old_phrase: str
    new_phrase: str
    # "replace" (ברירת מחדל, תאימות לאחור) | "delete" | "before" | "append".
    # engine._render_mutation בוחר לפי זה את הניסוח; בלי השדה הזה כל
    # פעולת-מילים הייתה מנוסחת כהחלפה.
    kind: str = "replace"


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
    transformations: list[
        InsertAfter
        | InsertSectionAfter
        | DeleteWords
        | InsertWordsBefore
        | AppendWordsAtEnd
        | AddFirstSubsection
        | InsertWordsAfter
        | ReplaceWords
        | ReplaceMarginTitleWords
    ],
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
            # תוקן (משימה 58): העוגן עשוי לשבת בכל עומק בתוך הסעיף -
            # פסקה בתוך סעיף קטן היא הדפוס הנפוץ ביותר. עד לתיקון זה
            # החיפוש היה רק ב-section.children (ילדים ישירים), כך
            # שהוספת פסקה לתוך סעיף קטן קיים נכשלה ב-ValueError.
            # אותו תיקון בדיוק שכבר נעשה ב-InsertSectionAfter למטה:
            # מוצאים את העוגן בכל עומק, ומכניסים אל **ההורה בפועל**
            # שלו - לא אל section.children, אחרת הצומת החדש "יברח"
            # מהסעיף הקטן אל הסעיף.
            container = find_parent(section, t.anchor_id)
            if container is None:
                if section.id == t.anchor_id:
                    raise ValueError(
                        f"עוגן {t.anchor_id} הוא הסעיף {t.section_number} עצמו - "
                        "אי אפשר להוסיף אח לסעיף דרך InsertAfter "
                        "(זו InsertSectionAfter)."
                    )
                raise ValueError(f"עוגן {t.anchor_id} לא נמצא בסעיף {t.section_number}")
            idx = next(i for i, c in enumerate(container.children) if c.id == t.anchor_id)
            new_child = copy.deepcopy(t.new_child)
            container.children.insert(idx + 1, new_child)
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
        elif isinstance(t, InsertSectionAfter):
            # תוקן (2026-09-16): הסעיף העוגן עשוי לשבת בכל עומק (חלק/
            # פרק/סימן), לא רק ילד ישיר של השורש - find_sections
            # (node.py) מוצאת אותו בכל מקרה. אבל *ההכנסה בעץ* חייבת
            # להיות אח בתוך אותו פרק/סימן שהעוגן נמצא בו (find_parent),
            # לא root.children - אחרת הסעיף החדש "יברח" לפרק הלא נכון.
            # המספור עצמו נשאר גלובלי (אומת בפועל: מספור סעיפים לא
            # מתאפס בכל פרק/סימן) - "האם זה הסעיף האחרון" נבדק מול כל
            # מספרי הסעיפים בחוק, לא רק אחים מקומיים.
            existing_sections = find_sections(after)
            anchor_section = existing_sections.get(t.after_section_number)
            if anchor_section is None:
                raise ValueError(f"סעיף {t.after_section_number} לא נמצא ב'לפני'")
            if t.new_section.number:
                raise ValueError(
                    "InsertSectionAfter.new_section.number חייב להישאר ריק - "
                    "המספור מחושב אוטומטית (drafting-rules.md §8.1), לא נקבע מראש."
                )
            existing_numbers = list(existing_sections.keys())
            sorted_numbers = sort_section_numbers(existing_numbers)
            is_last = sorted_numbers[-1] == t.after_section_number
            if is_last:
                label = next_appended_label(sorted_numbers)
            else:
                label = next_inserted_label(t.after_section_number, set(existing_numbers))
            parent = find_parent(after, anchor_section.id)
            if parent is None:
                raise ValueError(
                    f"לא נמצא הורה לסעיף {t.after_section_number} - לא אמור לקרות "
                    "(סעיף הוא תמיד צומת עלה-ביניים, לא השורש עצמו)."
                )
            idx = next(i for i, c in enumerate(parent.children) if c.id == anchor_section.id)
            new_section = copy.deepcopy(t.new_section)
            new_section.number = label
            new_section.node_type = "section"
            parent.children.insert(idx + 1, new_section)
            for anchor_substring, key in t.footnotes:
                count = new_section.text.count(anchor_substring)
                if count == 0:
                    raise ValueError(f"'{anchor_substring}' לא נמצא בטקסט {new_section.id}")
                if count > 1:
                    raise ValueError(
                        f"'{anchor_substring}' מופיע {count} פעמים בטקסט "
                        f"{new_section.id} - דו-משמעי, לא ניתן לקבוע מיקום יחיד "
                        "בלי לנחש."
                    )
                pos = new_section.text.find(anchor_substring)
                annotations.append(
                    FootnoteAnnotation(
                        node_id=new_section.id, offset=pos + len(anchor_substring), key=key
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
            # מספור סעיפים קטנים כולל תמיד סוגריים כחלק מ-number עצמו
            # (כך הם מגיעים מ-wikitext_parser: הארגומנט הגולמי הוא "(א)",
            # "(ב)" עם הסוגריים - ראו _SUBSECTION_LABEL ב-wikitext_parser.py).
            # לפני התיקון הזה number נקבע כאן בלי סוגריים ("א"/"ב") -
            # חוסר עקביות אמיתי עם נתוני wikitext אמיתיים, שנתפס רק
            # כשמשתמש אמיתי בדק את זה מול עץ אמיתי (לא רק fixture סינתטי).
            existing = normative_children[0]
            existing.number = "(א)"
            existing.node_type = "subsection"
            new_child = copy.deepcopy(t.new_child)
            new_child.number = "(ב)"
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
            # **האנוטציה נדרשת כדי לשמור את העוגן המינימלי.** בלעדיה
            # engine.amend() נופל ל-_diff_text, שמחשב את העוגן מחדש
            # כ*כל* הטקסט שלפני נקודת ההוספה - ומייצר
            # `אחרי "לא ינהל אדם קייטנה אלא אם כן יש בידו" יבוא "כדין"`
            # במקום `אחרי "בידו" יבוא "כדין"`. diff_translate כבר
            # חישב עוגן ייחודי מינימלי, והוא נזרק.
            annotations.append(ReplacementAnnotation(
                node_id=target.id, old_phrase=t.anchor_substring.strip(),
                new_phrase=t.inserted_text.strip(), kind="after"))
        elif isinstance(t, DeleteWords):
            target = _find_by_id(after, t.target_id)
            if target is None:
                raise ValueError(f"צומת {t.target_id} לא נמצא")
            count = target.text.count(t.phrase)
            if count != 1:
                raise ValueError(
                    f"'{t.phrase}' מופיע {count} פעמים בטקסט {t.target_id} - "
                    "מחיקה דורשת הופעה אחת בדיוק, בלי ניחוש."
                )
            # תיקון הרווחים אחרי ההסרה הוא מכני: רווח כפול או רווח
            # שנשאר לפני סימן פיסוק אינם נוסח חוק.
            remaining = target.text.replace(t.phrase, "", 1)
            remaining = re.sub(r"\s{2,}", " ", remaining)
            remaining = re.sub(r"\s+([.,;:])", r"\1", remaining)
            target.text = remaining.strip()
            annotations.append(ReplacementAnnotation(
                node_id=target.id, old_phrase=t.phrase, new_phrase="", kind="delete"))
        elif isinstance(t, InsertWordsBefore):
            target = _find_by_id(after, t.target_id)
            if target is None:
                raise ValueError(f"צומת {t.target_id} לא נמצא")
            count = target.text.count(t.before_phrase)
            if count != 1:
                raise ValueError(
                    f"'{t.before_phrase}' מופיע {count} פעמים בטקסט "
                    f"{t.target_id} - דו-משמעי, בלי ניחוש."
                )
            pos = target.text.find(t.before_phrase)
            target.text = target.text[:pos] + t.inserted_text + " " + target.text[pos:]
            annotations.append(ReplacementAnnotation(
                node_id=target.id, old_phrase=t.before_phrase,
                new_phrase=t.inserted_text, kind="before"))
        elif isinstance(t, AppendWordsAtEnd):
            target = _find_by_id(after, t.target_id)
            if target is None:
                raise ValueError(f"צומת {t.target_id} לא נמצא")
            existing = target.text.rstrip()
            if existing and existing[-1] in ".;,:":
                target.text = f"{existing[:-1].rstrip()} {t.inserted_text}{existing[-1]}"
            else:
                target.text = f"{existing} {t.inserted_text}"
            annotations.append(ReplacementAnnotation(
                node_id=target.id, old_phrase="", new_phrase=t.inserted_text,
                kind="append"))
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
        elif isinstance(t, ReplaceMarginTitleWords):
            section = _find_section(after, t.section_number)
            if section is None:
                raise ValueError(f"סעיף {t.section_number} לא נמצא ב'לפני'")
            title = section.margin_title or ""
            count = title.count(t.old_phrase)
            if count == 0:
                raise ValueError(f"'{t.old_phrase}' לא נמצא בכותרת השוליים של סעיף {t.section_number}")
            if count > 1:
                raise ValueError(
                    f"'{t.old_phrase}' מופיע {count} פעמים בכותרת השוליים של סעיף "
                    f"{t.section_number} - דו-משמעי, לא ניתן לקבוע מיקום יחיד בלי לנחש."
                )
            pos = title.find(t.old_phrase)
            section.margin_title = title[:pos] + t.new_phrase + title[pos + len(t.old_phrase) :]
            # מצביעה על הסעיף עצמו (לא ילד) - engine.amend() מזהה שינוי
            # בכותרת שוליים בהשוואת before_section.margin_title/after
            # ומחפש ReplacementAnnotation לפי node_id של הסעיף עצמו.
            annotations.append(
                ReplacementAnnotation(
                    node_id=section.id, old_phrase=t.old_phrase, new_phrase=t.new_phrase
                )
            )
        else:
            raise TypeError(f"טרנספורמציה לא מוכרת: {t!r}")
    return after, annotations
