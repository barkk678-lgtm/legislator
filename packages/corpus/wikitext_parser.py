"""פרסור טהור של ויקיטקסט (מבנה "ספר החוקים הפתוח") לעץ LegislativeNode.

פונקציה טהורה בלבד: אין כאן רשת, אין I/O. הקלט הוא מחרוזת ויקיטקסט
(ראו tests/fixtures/wikitext/ ל-fixtures אמיתיים), הפלט הוא עץ.
שליפת הוויקיטקסט מהרשת חיה ב-wikitext_client.py, קובץ נפרד לגמרי.

היקף (TASKS.md משימה 3): חוק הקייטנות וחוק מאבק בארגוני פשיעה בלבד.
חוק העונשין (משימה 7) חושף מבנה עשיר יותר (חלק/פרק/סימן, קטע1/2/3) -
נתמך כעת (2026-09-14): שלוש הרמות ממופות ל-node_type=part/chapter/siman
(ראו _CONTAINER_TEMPLATES).

הכרעות עיצוב מרכזיות (ראו data-sources.md "תקלות ידועות בוויקיטקסט"):

- עומק הקינון (ת/תת/תתת/תתתת/תתתתת) קובע *מבנה עץ* (מי הילד של מי),
  אבל node_type (subsection/paragraph/definition) נקבע לפי *תווית
  התווית* עצמה - (א) הוא subsection, (1) הוא paragraph - בלי קשר לאיזו
  תבנית עוטפת אותם בפועל. זה תואם ממצא recon: אותו פורמט תווית הופיע
  תחת תת ותחת תתת בסעיפים שונים של חוק מאבק בארגוני פשיעה.
- תוכן שכולו {{ח:הערה|...}} מסומן is_normative=False ולא נכנס לנוסח.
- {{ח:קטע4}} (עוטף רק הערה, לא רמת מבנה אמיתית) - מדולג לגמרי, לא ממופה.
- {{ח:סעיף*|...}} (פרטי תוספת, כמו בחוק מאבק בארגוני פשיעה) מטופל כמו
  {{ח:סעיף}} רגיל, אבל עם numbering_space="schedule" - מספור הפרטים
  בתוספת הוא מרחב נפרד מסעיפי החוק עצמו (מתחיל מ-"1" בכל תוספת,
  לא המשך של מספור החוק).
- סעיף עם כותרת ריקה שכל תוכנו הערות (לא נוסח) מסומן status="merged"
  אם ההערה מכילה את המילה "שולב", אחרת status="repealed" (למשל "(נמחק)").
  זו קריאה של הניסוח שכבר קיים במקור, לא ניחוש של עובדה משפטית חדשה.
"""

import hashlib
import re
from typing import NamedTuple

from node import LegislativeNode
from text_normalize import normalize_text

_CONTENT_DEPTH = {
    "ח:ת": 0,
    "ח:תת": 1,
    "ח:תתת": 2,
    "ח:תתתת": 3,
    "ח:תתתתת": 4,
}
_STRUCTURAL_LEVEL_LAW = -5
_STRUCTURAL_LEVEL_PART = -4
_STRUCTURAL_LEVEL_CHAPTER = -3
_STRUCTURAL_LEVEL_SIMAN = -2
_STRUCTURAL_LEVEL_SECTION = -1

# {{ח:קטע1/2/3}} - שלוש רמות המכל בין חוק לסעיף: חלק (משימה 7, קיים
# בעונשין כ"חלק 0"/"חלק א"/"חלק ב") > פרק (היה היחיד שטופל עד עכשיו)
# > סימן (תת-פרק, למשל "פרק ג סימן א"). אותה צורת ארגומנטים בשלושתן:
# [עוגן, כותרת, תיקון-אופציונלי] - ראו tests/fixtures/wikitext/penal.wikitext.
_CONTAINER_TEMPLATES = {
    "ח:קטע1": (_STRUCTURAL_LEVEL_PART, "part"),
    "ח:קטע2": (_STRUCTURAL_LEVEL_CHAPTER, "chapter"),
    "ח:קטע3": (_STRUCTURAL_LEVEL_SIMAN, "siman"),
}

_SUBSECTION_LABEL = re.compile(r"^\([א-ת][א-ת0-9]*\)$")  # (א), (א1) - מתחיל באות
_PARAGRAPH_LABEL = re.compile(r"^\(\d+\)$")  # (1), (2) - ספרות בלבד


class _Call(NamedTuple):
    name: str
    args: list[str]
    end: int


def _find_template(text: str, start: int) -> _Call:
    """מפרסר קריאת תבנית {{...}} יחידה החל מ-start, בכיבוד קינון.
    מחזיר את שם התבנית, רשימת הארגומנטים (מחרוזות גולמיות, קינון פנימי
    לא מפורק), ואת המיקום מיד אחרי ה-'}}' הסוגר."""
    assert text[start : start + 2] == "{{"
    i = start + 2
    depth = 1
    parts: list[str] = []
    current: list[str] = []
    while depth > 0:
        if text[i : i + 2] == "{{":
            depth += 1
            current.append("{{")
            i += 2
        elif text[i : i + 2] == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                parts.append("".join(current))
            else:
                current.append("}}")
        elif text[i] == "|" and depth == 1:
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(text[i])
            i += 1
    return _Call(name=parts[0], args=parts[1:], end=i)


def _flatten(text: str) -> str:
    """מיישר תבניות הפניה מקוננות ({{ח:חיצוני}}/{{ח:פנימי}}/{{ח:הערה}})
    לטקסט תצוגה שטוח. תבניות לא-מוכרות נשארות כפי שהן (גולמי)."""
    out = []
    i = 0
    while i < len(text):
        if text[i : i + 2] == "{{":
            call = _find_template(text, i)
            if call.name in ("ח:חיצוני", "ח:פנימי"):
                display = call.args[-1] if len(call.args) > 1 else call.args[0]
                out.append(_flatten(display))
            elif call.name == "ח:הערה":
                out.append(_flatten(call.args[0]))
            else:
                out.append(text[i : call.end])
            i = call.end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _is_pure_note(remainder: str) -> str | None:
    """אם remainder (אחרי הסרת תבנית העומק המובילה) הוא במלואו קריאת
    {{ח:הערה|...}} אחת - מחזיר את תוכנה השטוח. אחרת None."""
    stripped = remainder.strip()
    if not stripped.startswith("{{"):
        return None
    call = _find_template(stripped, 0)
    if call.name == "ח:הערה" and call.end == len(stripped):
        return _flatten(call.args[0])
    return None


def _classify(depth_name: str, label: str | None, kind_attr: str | None) -> str:
    if kind_attr == "הגדרה":
        return "definition"
    if label:
        if _SUBSECTION_LABEL.match(label):
            return "subsection"
        if _PARAGRAPH_LABEL.match(label):
            return "paragraph"
    return "paragraph"


def _slug(label: str | None, fallback_index: int) -> str:
    if not label:
        return f"p{fallback_index}"
    return re.sub(r"[()]", "", label)


def _unique_child_id(parent_node: LegislativeNode, local_id: str, collisions: list[str]) -> str:
    """בונה id ילד ייחודי בין אחיו, בלי לנחש *למה* יש התנגשות.

    ההיוריסטיקה הטבעית (label/מספר-סעיף) לא תמיד ייחודית בפועל - ראו
    חוק החוזים (חלק כללי) סעיף 25, שבו תיקון עתידי (תוקף 7.1.2026)
    גורם לוויקיטקסט להציג שני {{ח:תת|(א)}} נפרדים באותו סעיף (נוסח
    ישן מול חדש, מובחנים רק ב-{{ח:הערה}} מוטבעת, לא בתווית עצמו).
    זו לא המשפחה של באג ה-id הישן (מספור-מחדש בתוספת, שתוקן ביחס
    ל-parent_node.id) - זו תופעה כללית: כל מקור עתידי של התנגשות,
    ידוע או לא, נתפס כאן באופן מבני, בלי לנחש על טקסט חופשי בעברית
    (ראו ההחלטה המקבילה לגבי התאמת שמות מול KNS_IsraelLaw -
    docs/strategy/decisions.md). אם אין התנגשות - מתנהג בדיוק כמו
    קודם. אם יש - מוסיף סיומת סידורית יציבה (-2, -3, ...), ומדווח
    לתוך collisions (נשמר על root.id_collisions - ראו node.py) כדי
    שכל השכיחות בקורפוס המלא תהיה ניתנת לספירה, לא רק לזיהוי אילם.
    check_unique_ids נשאר קו ההגנה האחרון גם ככה."""
    base_id = f"{parent_node.id}/{local_id}"
    existing = {child.id for child in parent_node.children}
    if base_id not in existing:
        return base_id
    n = 2
    while f"{base_id}-{n}" in existing:
        n += 1
    final_id = f"{base_id}-{n}"
    collisions.append(f"{base_id} -> {final_id}")
    return final_id


def _short_hash(text: str) -> str:
    """hash יציב בין ריצות/תהליכים - לא hash() המובנה של פייתון, שמלוח
    (PYTHONHASHSEED) ומשתנה בין תהליכים למחרוזות. ראו _lookahead_content."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def _lookahead_content(lines: list[str], from_index: int) -> str | None:
    """מציצה קדימה מ-lines[from_index+1] לתוכן {{ח:ת...}} הראשון (הבא,
    לא ריק) - בלי לשנות את מצב הפרסור הראשי, רק חלון קדימה מקומי (לא
    מעבר שני על העץ). משמשת אך ורק לגזירת id יציב-לפי-תוכן לסעיף בלי
    מספר טבעי (ראו {{ח:סעיף*}} ברשימות לא-ממוספרות, למשל חוק מועצת
    הצמחים - "אבטיח"/"אספרגוס"/וכו', כל אחד {{ח:ת}} יחיד מיד אחרי
    {{ח:סעיף*}} הריק). אם השורה הבאה (הלא-ריקה) אינה בדיוק תבנית עומק
    תוכן - מחזירה None (נופלים חזרה ל-_unique_child_id הרגיל, לפי
    מיקום+סיומת - לא מנחשים תוכן שלא ברור)."""
    for raw_line in lines[from_index + 1 :]:
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("{{"):
            return None
        call = _find_template(line, 0)
        if call.name not in _CONTENT_DEPTH:
            return None
        remainder = line[call.end :]
        note_text = _is_pure_note(remainder)
        flattened = note_text if note_text is not None else _flatten(remainder).strip()
        return flattened or None
    return None


def parse_wikitext(
    text: str, *, law_id: str, source_ref: str = "", as_of: str | None = None
) -> LegislativeNode:
    """מפרסר ויקיטקסט (מבנה ספר החוקים הפתוח) לעץ LegislativeNode.

    source_ref, אם ניתן, נשמר רק בשורש (ראו node.effective_source_ref) -
    הוא בדרך כלל מורכב חיצונית מ-{{ח:תיבה}} + תאריך ה-revision של הדף,
    ולא מפוענח כאן.

    as_of (משימה 5א), אם ניתן, נשמר גם הוא רק בשורש (ראו
    node.effective_as_of) - revision timestamp גולמי (למשל
    "2024-09-30T13:00:35Z"), כפי שנשלף על ידי
    wikitext_client.extract_revision_timestamp. לא מפוענח/מנוסח כאן -
    הניסוח "נוסח כפי שהופיע ביום X" הוא תפקיד שכבת התצוגה, לא של
    הפרסר.
    """
    root = LegislativeNode(
        id=law_id,
        node_type="law",
        number="",
        margin_title=None,
        text="",
        source_ref=source_ref,
        is_normative=False,  # השורש הוא מטא-דאטה של החוק, לא נוסח
        as_of=as_of,
    )
    collisions: list[str] = []
    content_derived_ids: list[str] = []

    # מחסנית של (רמה_מבנית, צומת, מרחב_מספור_נוכחי)
    stack: list[tuple[int, LegislativeNode, str]] = [
        (_STRUCTURAL_LEVEL_LAW, root, "law")
    ]

    lines = text.splitlines()
    for line_index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line.startswith("{{"):
            continue
        call = _find_template(line, 0)
        name = call.name

        if name == "ח:כותרת":
            if call.args:
                root.full_title = normalize_text(_flatten(call.args[0]))
            continue

        if name == "ח:קטע4":
            # קטע4 עצמו מכיל את כל תוכנו (הערה) כארגומנט מוטבע באותה
            # קריאה - אין שורה נפרדת לדלג עליה אחריו. לא ממופה כלל
            # (החלטה: מופע יחיד/בודד שעוטף הערה, לא רמת מבנה אמיתית).
            continue

        if name in _CONTAINER_TEMPLATES:
            structural_level, node_type = _CONTAINER_TEMPLATES[name]
            anchor = call.args[0] if call.args else ""
            title = _flatten(call.args[1]) if len(call.args) > 1 else ""
            if title == "תוכן עניינים":
                continue  # תוכן העניינים האוטומטי - לא רמת מבנה
            while stack[-1][0] >= structural_level:
                stack.pop()
            parent_node = stack[-1][1]
            # ברירת מחדל: לרשת את מרחב המספור מההורה (לא "law" קבוע) -
            # תוספת יכולה עקרונית להיפתח בכל רמת מכל, לא רק ב-קטע2.
            numbering_space = "schedule" if anchor.startswith("תוספת") else stack[-1][2]
            node = LegislativeNode(
                id=_unique_child_id(parent_node, _slug(anchor, len(parent_node.children)), collisions),
                node_type=node_type,
                number=anchor,
                margin_title=normalize_text(title),
                text="",
            )
            parent_node.children.append(node)
            stack.append((structural_level, node, numbering_space))
            continue

        if name in ("ח:סעיף", "ח:סעיף*"):
            number = call.args[0] if call.args else ""
            raw_title = call.args[1] if len(call.args) > 1 else ""
            title = _flatten(raw_title)
            title_raw = raw_title if "{{" in raw_title else None
            extra_args = call.args[2:]
            raw_amendment_note = "|".join(extra_args) if extra_args else None

            while stack[-1][0] >= _STRUCTURAL_LEVEL_SECTION:
                stack.pop()
            parent_node = stack[-1][1]
            numbering_space = stack[-1][2]
            if number:
                local_id = f"s{number}"
            else:
                # סעיף בלי מספר טבעי (רשימה לא-ממוספרת, ראו חוק מועצת
                # הצמחים) - id לפי מיקום היה "שובר את הבסיס" של יציבות
                # provenance בין גרסאות (ברק, 2026-09-14). לגזור מתוכן
                # הפריט עצמו (hash יציב) כשאפשר לזהות אותו בבירור.
                content_hint = _lookahead_content(lines, line_index)
                if content_hint is not None:
                    local_id = f"s-{_short_hash(content_hint)}"
                    content_derived_ids.append(f"{parent_node.id}/{local_id}")
                else:
                    local_id = "s"  # אין תוכן ברור לגזור ממנו - נופל
                    # חזרה למנגנון הרגיל (מיקום + סיומת סידורית).
            node = LegislativeNode(
                id=_unique_child_id(parent_node, local_id, collisions),
                node_type="section",
                number=number,
                margin_title=normalize_text(title),
                margin_title_raw=title_raw,
                text="",
                raw_amendment_note=raw_amendment_note,
                numbering_space=numbering_space,
            )
            parent_node.children.append(node)
            stack.append((_STRUCTURAL_LEVEL_SECTION, node, numbering_space))
            continue

        if name in _CONTENT_DEPTH:
            depth = _CONTENT_DEPTH[name]
            label = None
            kind_attr = None
            for arg in call.args:
                if arg.startswith("סוג="):
                    kind_attr = arg[len("סוג=") :]
                elif label is None and arg:
                    label = arg
            remainder = line[call.end :]

            note_text = _is_pure_note(remainder)
            is_normative = note_text is None
            flattened = note_text if note_text is not None else _flatten(remainder).strip()

            while stack[-1][0] >= depth:
                stack.pop()
            parent_node = stack[-1][1]
            numbering_space = stack[-1][2]
            node_type = _classify(name, label, kind_attr)
            node = LegislativeNode(
                id=_unique_child_id(parent_node, _slug(label, len(parent_node.children)), collisions),
                node_type=node_type,
                number=label or "",
                margin_title=None,
                text=normalize_text(flattened),
                text_raw=flattened,
                is_normative=is_normative,
                numbering_space=numbering_space,
            )
            parent_node.children.append(node)
            stack.append((depth, node, numbering_space))
            continue

        # תבנית לא-מוכרת ברמה העליונה (מאגר/תיבה/חתימות/וכו') - מדולגת.
        # {{ח:כותרת}} נלכד למעלה (למשימה 4); {{ח:מאגר}}/{{ח:תיבה}}/
        # {{ח:חתימות}} עדיין לא נדרשים להגדרת הסיום של משימה 3 ומתועדים
        # כפער פתוח.

    # סעיף עם כותרת ריקה שכל תוכנו לא-נורמטיבי (הערה בלבד) = לא בתוקף עוד.
    # מבחין בין "שולב" (merged, במפורש) ל"נמחק/בטל" (repealed, ברירת המחדל
    # לכל מקרה אחר) לפי המילה שמופיעה בהערה עצמה - זה לא ניחוש של עובדה
    # משפטית, רק קריאה של הניסוח שכבר קיים בהערת המקור.
    def _mark_status(node: LegislativeNode) -> None:
        for child in node.children:
            _mark_status(child)
        if (
            node.node_type == "section"
            and not node.margin_title
            and node.children
            and all(not c.is_normative for c in node.children)
        ):
            combined = " ".join(c.text for c in node.children)
            node.status = "merged" if "שולב" in combined else "repealed"

    _mark_status(root)
    root.id_collisions = collisions
    root.content_derived_ids = content_derived_ids
    return root
