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
- {{ח:קטע4}} - שני דפוסים שונים לגמרי, מובחנים לפי הארגומנט הראשון
  (ברק, 2026-09-16, אחרי סריקת קורפוס-שלם - 1,008 כותרות, לא רק
  998 שנטענו - 927 מופעים, 90 מהם "מבנה"): ארגומנט ראשון ריק - עוטף
  רק הערה, מדולג לגמרי (ההנחה המקורית, נכונה ל-90.3% מהמופעים).
  ארגומנט ראשון לא ריק (עוגן, בדיוק כמו קטע1/2/3) - "סימן משנה",
  רמת מבנה אמיתית מתחת לסימן ומעל סעיף, ממופה כמו קטע3. {{ח:קטע5}}
  זהה מילה-במילה ל-קטע4 בוויקי אבל **תמיד** מבנה (10/10 מופעים
  בקורפוס-שלם) - לא נבדק כ"הערה" בכלל.
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
    "ח:תתתתתת": 5,  # עומק 6 - נמצא בפועל (חוק התכנון והבניה ועוד) - אותה
    # משפחה בדיוק, אותו תבנית ארגומנטים (תווית + "סוג=" אופציונלי), רק
    # קינון עמוק יותר (ברק, 2026-09-14, אחרי סריקת קורפוס-שלם - TASKS.md
    # משימה 7).
    "ח:תתתתתתת": 6,  # עומק 7 - נמצא בפועל (חוק מיסוי רווחים ממשאבי טבע ועוד).
}
_STRUCTURAL_LEVEL_LAW = -5
_STRUCTURAL_LEVEL_PART = -4
_STRUCTURAL_LEVEL_CHAPTER = -3
_STRUCTURAL_LEVEL_SIMAN = -2
_STRUCTURAL_LEVEL_SUB_SIMAN = -1.5  # "סימן משנה" - בין סימן לסעיף (ראו קטע4/5 למטה)
_STRUCTURAL_LEVEL_SECTION = -1

# {{ח:קטע1/2/3}} - שלוש רמות המכל בין חוק לסעיף: חלק (משימה 7, קיים
# בעונשין כ"חלק 0"/"חלק א"/"חלק ב") > פרק (היה היחיד שטופל עד עכשיו)
# > סימן (תת-פרק, למשל "פרק ג סימן א"). אותה צורת ארגומנטים בשלושתן:
# [עוגן, כותרת, תיקון-אופציונלי] - ראו tests/fixtures/wikitext/penal.wikitext.
_CONTAINER_TEMPLATES = {
    "ח:קטע1": (_STRUCTURAL_LEVEL_PART, "part"),
    "ח:קטע2": (_STRUCTURAL_LEVEL_CHAPTER, "chapter"),
    "ח:קטע3": (_STRUCTURAL_LEVEL_SIMAN, "siman"),
    # קטע4 מגיע לכאן רק כשהארגומנט הראשון לא ריק (ראו הבדיקה המפורשת
    # למעלה בלולאה הראשית) - אחרת מדולג כהערה. קטע5 תמיד כאן.
    "ח:קטע4": (_STRUCTURAL_LEVEL_SUB_SIMAN, "sub_siman"),
    "ח:קטע5": (_STRUCTURAL_LEVEL_SUB_SIMAN, "sub_siman"),
}

_SUBSECTION_LABEL = re.compile(r"^\([א-ת][א-ת0-9]*\)$")  # (א), (א1) - מתחיל באות
_PARAGRAPH_LABEL = re.compile(r"^\(\d+\)$")  # (1), (2) - ספרות בלבד


class _Call(NamedTuple):
    name: str
    args: list[str]
    end: int


def _brace_depth(text: str) -> int:
    """כמה קריאות תבנית נשארו פתוחות בסוף המחרוזת (0 = מאוזנת)."""
    depth = i = 0
    while i < len(text):
        if text[i : i + 2] == "{{":
            depth += 1
            i += 2
        elif text[i : i + 2] == "}}":
            depth -= 1
            i += 2
        else:
            i += 1
    return depth


def _is_zone_boundary(raw_line: str) -> bool:
    """שורה שהלולאה הראשית חייבת לראות בפני עצמה: פותח/סוגר של אזור
    דילוג או של בלוק תוכן העניינים. ראו ההסבר ב-_join_unclosed_templates."""
    line = raw_line.strip()
    if line == _TOC_DIV_CLOSE_LINE or _TOC_DIV_OPEN_RE.match(line):
        return True
    if not line.startswith("{{") or _brace_depth(line) != 0:
        return False
    name = _find_template(line, 0).name
    return name in _SKIP_ZONE_OPENERS or name == _SKIP_ZONE_CLOSER


def _join_unclosed_templates(lines: list[str]) -> list[str]:
    """מאחדת שורה שנפתחת בה קריאת תבנית שאינה נסגרת באותה שורה עם
    השורות שאחריה, עד לאיזון - כך שהלולאה הראשית תמיד מקבלת "שורה
    לוגית" שלמה.

    **למה זה כאן ולא בלולאה:** `_find_template` עצמה כבר עיוורת
    לשורות (היא סופרת תווים, `\n` הוא תו כמו כל אחר). ההנחה היחידה
    שנשברה הייתה של הלולאה הראשית - "כל קריאת תבנית שלמה בשורה אחת".
    איחוד מוקדם פותר בדיוק את ההנחה הזו בלי לגעת באף ענף בלולאה,
    ובלי לעבור למודל היסט-תו בכל הפרסר (הניתוח המקורי ב-TASKS.md
    משימה 7 העריך שיידרש מעבר כזה - בפועל לא נדרש).

    **15 חוקים בקורפוס קרסו בגלל זה ב-IndexError, ובהם פקודת מס
    הכנסה, פקודת התעבורה ופקודת החברות** - החוק כולו לא נטען, לא
    רק הבלוק. שלוש התבניות שנמצאו בפועל: `{{עמודות|2|...}}` (מילון
    מונחים עברי-אנגלי, 8 חוקים), `{{דוכיווני שווה|...}}` (פקודת
    הרוקחים, 221 מופעים) ו-`{{טורים שווים|...}}` (פקודת התעבורה).

    בלוק שאינו נסגר עד סוף הדף מוחזר כפי שהוא, בלי איחוד - הוא ייפול
    בהמשך על השגיאה המתוארת ב-`_find_template`, לא בשקט."""
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip().startswith("{{") or _brace_depth(line) <= 0:
            out.append(line)
            index += 1
            continue
        block = [line]
        depth = _brace_depth(line)
        cursor = index + 1
        while cursor < len(lines) and depth > 0:
            if _is_zone_boundary(lines[cursor]):
                # **הגנה, לא זהירות-יתר:** הלולאה הראשית מנהלת שני
                # אזורי-דילוג לפי *שורות* שלמות (in_skip_zone מול
                # {{ח:סוגר}}, in_toc_zone מול </div>). אם שורת הגבול
                # הייתה נבלעת לתוך בלוק מאוחד, האזור לא היה נסגר לעולם
                # והחוק כולו היה אובד בשקט - כישלון חמור בהרבה מזה
                # שאנחנו מתקנים. במקרה כזה פשוט לא מאחדים.
                depth = 1
                break
            block.append(lines[cursor])
            depth += _brace_depth(lines[cursor])
            cursor += 1
        if depth > 0:  # לא נסגר עד סוף הדף, או נעצר בגבול אזור
            out.append(line)
            index += 1
            continue
        out.append("\n".join(block))
        index = cursor
    return out


class StarredSectionAmbiguity(Exception):
    """שני המבחינים של {{ח:סעיף*}} אינם מסכימים - **לא מנחשים**.

    ברק (2026-09-19): "אם המבחין הכפול נכשל על מופע כלשהו - עצור
    ברעש ואל תנחש לפי סימן יחיד." מופע כזה הוא צורה שלא ראינו,
    והנחה לפי סימן אחד תייצר מבנה שגוי שייראה תקין."""


# `עוגן=סעיף 30.ב` מול `עוגן=סעיף 57ג` - **הנקודה היא הסימן.**
# הקבוצה הראשונה היא מספר סעיף ואחריה מזהה סעיף קטן; השנייה היא
# מספר סעיף רגיל שיכול לכלול אותיות. ראו _starred_section_use.
_DOTTED_SECTION_ANCHOR_RE = re.compile(r"^סעיף\s+[^\s.]+\.")
_LIST_ANCHOR_WORDS = ("תוספת", "לוח", "טופס", "פרט", "חלק")


def _next_template_name(lines: list[str], line_index: int) -> str:
    """שם התבנית בשורה הלא-ריקה הבאה, או "" אם אין."""
    for j in range(line_index + 1, min(line_index + 5, len(lines))):
        nxt = lines[j].strip()
        if not nxt:
            continue
        match = re.match(r"\{\{([^|}]+)", nxt)
        return match.group(1).strip() if match else ""
    return ""


def _starred_section_use(call: _Call, lines: list[str], line_index: int,
                         numbering_space: str = "law") -> str:
    """מכריע מהו {{ח:סעיף*}}: "subsection", "list_item", "section"
    או **"unknown"**.

    **הסימן הוא הנקודה בעוגן** (ברק אישר, 2026-09-19, על בסיס פילוח
    של 7,760 מופעים ב-256 חוקים):

    - `עוגן=סעיף 30.ב` - מנוקד. מספר סעיף, נקודה, מזהה סעיף קטן.
      **294 מופעים בקורפוס, ובכל 294 הארגומנט המיקומי ריק או חסר.**
      אפס מקרים של עוגן מנוקד עם מספר מיקומי מלא. זו הראיה.
    - `עוגן=סעיף 57ג` - בלי נקודה. סעיף רגיל לכל דבר, שנכתב
      ב-`ח:סעיף*` ולא ב-`ח:סעיף`.
    - עוגן שמזכיר תוספת/לוח/טופס/פרט/חלק - פריט, גם כשהוא מתחיל
      במילה "סעיף" (`עוגן=סעיף פרק כא תוספת פרט 1`).

    **מה שבוטל, ולמה:** הגרסה הקודמת השתמשה ב"ארגומנט מיקומי ראשון
    ריק ⇒ סעיף קטן" כמבחין שני עצמאי. הקורפוס הפריך אותו על 11
    חוקים: `{{ח:סעיף*|||תיקון: ק״ת תשפ״ו|עוגן=תוספת 1 חלק 1}}` -
    המשבצת הריקה קיימת רק כדי לפנות מקום להערת התיקון, לא כדי
    לסמן שאין מספר. הארגומנט המיקומי נשאר כאן **רק כבדיקת
    סתירה** לכיוון אחד: סעיף קטן אינו יכול לשאת מספר סעיף משלו.

    **ומה קורה כשאין עוגן בכלל: "unknown", ולא ניחוש.** 278 מופעים
    בקורפוס. אין לנו ראיה שהם סעיפים קטנים, ויש ראיה נסיבתית הפוכה
    (האחים שלהם שכן נושאים עוגן אומרים "תוספת"). הם נשארים בדיוק
    כפי שהיו לפני התיקון ומסומנים ב-`unrecognized_starred`.

    **הערה על חוק הברזל "מבחין יחיד הוא הנחה":** ההכרעה היחידה
    שמשנה התנהגות היא "subsection", ולה **שני** סימנים שמסכימים על
    294 מתוך 294. "list_item"/"section"/"unknown" כולם משמרים את
    ההתנהגות שהייתה, ולכן אינם טענה חדשה שדורשת ראיה."""
    anchor_arg = next((a for a in call.args if a.startswith("עוגן=")), None)
    positional = [a for a in call.args if "=" not in a]
    has_number = bool(positional) and bool(positional[0].strip())

    if anchor_arg is None:
        # **בלי עוגן: התבנית הבאה מכריעה, ורק במרחב החוק** (ברק
        # אישר 2026-09-19 אחרי שעבר על כל 34 המקרים בעין).
        #
        # שתי משפחות, כל אחת עם סימן מאשר משלה:
        #   {{ח:סעיף*||ויתור על חובות האוחז}} ואז {{ח:תתת|(2)}}
        #   {{ח:סעיף*|אחר=[(ז)]}}            ואז {{ח:תתת|(2)}}
        # הראשונה זהה למקרה השטרות פחות העוגן; בשנייה ערך ה-`אחר=`
        # הוא **בעצמו** תווית של סעיף קטן. `אחר=` **מאשר ואינו
        # מגדיר** - ההכרעה היא התבנית הבאה, והתווית נלקחת ממנה.
        #
        # **רק במרחב `law`.** אותה צורה במרחב `schedule` היא פריט
        # בתוספת שיש לו מבנה פנימי - 34 מופעים נוספים - וההכרעה
        # שם נשארת "לא מזוהה".
        if (numbering_space == "law"
                and _next_template_name(lines, line_index) in ("ח:תת", "ח:תתת")):
            return "subsection"
        return "unknown"

    value = anchor_arg[len("עוגן=") :].strip()
    if any(word in value for word in _LIST_ANCHOR_WORDS):
        use = "list_item"
    elif _DOTTED_SECTION_ANCHOR_RE.match(value):
        use = "subsection"
    elif value.startswith("סעיף"):
        use = "section"
    else:
        return "unknown"

    # בדיקת הסתירה היחידה שיש לה משמעות: סעיף קטן אינו נושא מספר
    # סעיף משלו. אפס מופעים כאלה בקורפוס - אם יופיע אחד, זו צורה
    # שלא ראינו ולא מנחשים עליה.
    if use == "subsection" and has_number:
        raise StarredSectionAmbiguity(
            f"{{{{ח:סעיף*}}}} בשורה {line_index}: העוגן {value!r} מנוקד "
            f"ולכן סעיף קטן, אבל יש ארגומנט מיקומי {positional[0]!r}. "
            f"צורה שלא נצפתה - לא מנחשים. "
            f"המקור: {lines[line_index].strip()[:120]!r}"
        )
    return use


def _find_template(text: str, start: int) -> _Call:
    """מפרסר קריאת תבנית {{...}} יחידה החל מ-start, בכיבוד קינון.
    מחזיר את שם התבנית, רשימת הארגומנטים (מחרוזות גולמיות, קינון פנימי
    לא מפורק), ואת המיקום מיד אחרי ה-'}}' הסוגר."""
    assert text[start : start + 2] == "{{"
    if _brace_depth(text[start:]) != 0:
        # "תוכנה שקורסת על קלט פגום היא באג בתוכנה" (CLAUDE.md). עד
        # 2026-09-17 המקרה הזה נתן IndexError עירום מתוך הלולאה למטה -
        # שגיאה שלא אומרת דבר על מה קרה. עכשיו היא מתוארת. הקורא
        # (_join_unclosed_templates) כבר מאחד שורות לפני שמגיעים לכאן,
        # ולכן זה נותר רק למקרה שהתבנית באמת אינה נסגרת עד סוף הדף.
        raise ValueError(
            f"קריאת תבנית שאינה נסגרת: {text[start : start + 60]!r}"
        )
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


_TABLE_OPEN_RE = re.compile(r"(?i)^<table\b")
_TABLE_CLOSE_RE = re.compile(r"(?i)</table\s*>")

# אזורי דילוג/תוכן-בוט שאינם נוסח - אותה לוגיקה בדיוק כמו
# ingest_checks.py (_SKIP_ZONE_OPENERS/_TOC_DIV_OPEN_RE/וכו') - שוכפלה
# במכוון, לא יובאה (שני המודולים נשארים עצמאיים, כמו _TABLE_OPEN_RE
# למעלה). קריטי שהפרסר יזהה את אלה *לפני* שקטע "מצורף לצומת הקודם"
# (ראו הלולאה הראשית) - אחרת שורות חתימה/תוכן-עניינים-אוטומטי/קטגוריה
# היו נדבקות בטעות כהשלמת נוסח לצומת הלא-נכון (ברק, 2026-09-14: נבדק
# בפועל מול tests/fixtures/wikitext/kaytanot.wikitext ו-maavak, ששניהם
# מכילים בדיוק את התבניות האלה).
_SKIP_ZONE_OPENERS = {"ח:פתיח-התחלה", "ח:חתימות", "ח:מבוא"}
_SKIP_ZONE_CLOSER = "ח:סוגר"
_CATEGORY_LINE_RE = re.compile(r"^\[\[קטגוריה:")
_TOC_DIV_OPEN_RE = re.compile(r'^<div class="law-toc">$')
_TOC_DIV_CLOSE_LINE = "</div>"
_INCLUDEONLY_CATEGORY_RE = re.compile(r"(?i)^<includeonly>.*קטגוריה.*</includeonly>$")
# זריקת קטגוריה אוטומטית עטופה ב-<includeonly> (למשל חוק הרשות לפיתוח
# ירושלים) - אותה משפחת תוכן-בוט בדיוק כמו [[קטגוריה:...]] הרגיל, רק
# עטופה (ברק, 2026-09-14, אחרי סריקת הקורפוס השלם - TASKS.md משימה 7).
_STRAY_PUNCTUATION_RE = re.compile(r"^[.,;:]$")
# תו פיסוק בודד בשורה נפרדת (למשל "." בחוק הנוער) - רעש עריכה במקור,
# לא תוכן (אותה סריקה, אותה החלטה).


def _consume_html_table(first_chunk: str, lines: list[str], next_index: int) -> tuple[str, int]:
    """אוספת בלוק <table>...</table> גולמי (HTML, לא MediaWiki) - ראו
    TASKS.md משימה 7: 97/1,021 חוקים בקורפוס, ולא רק "לוח השוואה"
    עיטורי - חוק הביטוח הלאומי (תקרות שכר טרחה) וחוק מיסוי מקרקעין
    (מדרגות מס צמודות) הם דוגמאות אמיתיות לתוכן מהותי בתוך טבלה.
    ברק (2026-09-14): "לא מפרסרים אותן, כן טוענים את החוקים" - נשמר
    כצומת raw_block שלם, בלי ניסיון לפרק את מבנה הטבלה הפנימי.

    first_chunk כבר ידוע כמתחיל ב-<table (לא רגיש לרישיות - הבדיקה
    נעשית לפני הקריאה לפונקציה הזו). lines[next_index:] הן שורות
    המשך אפשריות. מחזירה (html_raw, אינדקס השורה האחרונה שנצרכה
    מ-lines - next_index-1 אם לא נצרכה אף שורה נוספת מעבר ל-first_chunk).
    לא מטפלת בטבלאות מקוננות (לא נצפו בפועל בקורפוס); אם </table>
    לא נמצא עד סוף הטקסט - מחזירה את כל מה שיש, לא קורסת ולא ממציאה
    סגירה שלא קיימת במקור."""
    block = [first_chunk]
    if _TABLE_CLOSE_RE.search(first_chunk):
        return first_chunk, next_index - 1
    idx = next_index
    while idx < len(lines):
        block.append(lines[idx])
        if _TABLE_CLOSE_RE.search(lines[idx]):
            return "\n".join(block), idx
        idx += 1
    return "\n".join(block), idx - 1


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
    unrecognized_starred_ids: list[str] = []
    starred_as_subsection: list[str] = []
    continuation_completions: list[str] = []

    # מחסנית של (רמה_מבנית, צומת, מרחב_מספור_נוכחי)
    stack: list[tuple[int, LegislativeNode, str]] = [
        (_STRUCTURAL_LEVEL_LAW, root, "law")
    ]

    in_skip_zone = False  # בין {{ח:פתיח-התחלה}}/{{ח:חתימות}}/{{ח:מבוא}}
    # ל-{{ח:סוגר}} התואם - ציטוטים/חתימות, לא נוסח (ראו _SKIP_ZONE_OPENERS).
    in_toc_zone = False  # בתוך <div class="law-toc">...</div> - תוכן
    # עניינים אוטומטי, עודף לגמרי מול העץ שכבר נבנה (ראו _TOC_DIV_OPEN_RE).

    pending_margin_title = ""  # ראו הענף של {{ח:סעיף*}} למטה
    lines = _join_unclosed_templates(text.splitlines())
    line_index = 0
    while line_index < len(lines):
        raw_line = lines[line_index]
        line = raw_line.strip()

        if in_toc_zone:
            if line == _TOC_DIV_CLOSE_LINE:
                in_toc_zone = False
            line_index += 1
            continue
        if _TOC_DIV_OPEN_RE.match(line):
            in_toc_zone = True
            line_index += 1
            continue

        if not line.startswith("{{"):
            if _TABLE_OPEN_RE.match(line):
                # בלוק <table> גולמי "יתום" - לא מקושר לשום {{ח:ת...}}
                # (למשל "לוח השוואה" בעונשין). מצורף כילד לצומת הפתוח
                # הנוכחי - נשמר גולמי, לא מפורסר (ראו _consume_html_table).
                parent_node = stack[-1][1]
                numbering_space = stack[-1][2]
                html, last_consumed = _consume_html_table(line, lines, line_index + 1)
                node = LegislativeNode(
                    id=_unique_child_id(parent_node, f"table-{_short_hash(html)}", collisions),
                    node_type="raw_block",
                    number="",
                    margin_title=None,
                    text=html,
                    text_raw=html,
                    is_normative=True,
                    numbering_space=numbering_space,
                )
                parent_node.children.append(node)
                line_index = last_consumed + 1
                continue
            if in_skip_zone:
                line_index += 1
                continue
            if (
                not line
                or _CATEGORY_LINE_RE.match(line)
                or _INCLUDEONLY_CATEGORY_RE.match(line)
                or _STRAY_PUNCTUATION_RE.match(line)
            ):
                line_index += 1
                continue
            # תוכן אמיתי שלא מתחיל ב-{{ ואינו באחד האזורים המוכרים
            # למעלה - ברק (2026-09-14, אחרי סריקת קורפוס-שלם שחשפה 7
            # מקרים אמיתיים מתוך 1,021 חוקים - TASKS.md משימה 7):
            # "שורה שאינה מתחילה ב-{{ ואינה באזור מוכר מצורפת לצומת
            # הקודם, בלי לנחש מבנה. זה שומר את הנוסח... אבל היא חייבת
            # להיות מסומנת." מצורף כהשלמה לצומת האחרון שנפתח (stack[-1]) -
            # לא בונה מבנה חדש, לא מנחש לאיזה תת-סעיף/הגדרה זה שייך
            # באמת (למשל חוק מוסדות חינוך תרבותיים ייחודיים, שבו התבנית
            # עצמה פגומה במקור - לא רק חסרה; אותו טיפול, בלי ניסיון שחזור).
            target_node = stack[-1][1]
            appended = _flatten(line).strip()
            if appended:
                target_node.text = normalize_text(f"{target_node.text} {appended}".strip())
                target_node.text_raw = f"{target_node.text_raw}\n{line}" if target_node.text_raw else line
                if not target_node.completed_by_continuation:
                    target_node.completed_by_continuation = True
                    continuation_completions.append(target_node.id)
            line_index += 1
            continue
        call = _find_template(line, 0)
        name = call.name

        if name in _SKIP_ZONE_OPENERS:
            in_skip_zone = True
            line_index += 1
            continue
        if name == _SKIP_ZONE_CLOSER:
            in_skip_zone = False
            line_index += 1
            continue

        if name == "ח:כותרת":
            if call.args:
                root.full_title = normalize_text(_flatten(call.args[0]))
            line_index += 1
            continue

        if name == "ח:קטע4" and not (call.args and call.args[0].strip()):
            # קטע4 עם ארגומנט ראשון ריק - עוטף רק הערה (לא עוגן),
            # מכיל את כל תוכנו כארגומנט מוטבע באותה קריאה - אין שורה
            # נפרדת לדלג עליה אחריו. מדולג לגמרי, לא ממופה (ברק,
            # 2026-09-16: 90.3% מהמופעים בקורפוס-שלם). ארגומנט ראשון
            # לא ריק (עוגן אמיתי) נופל דרך ל-_CONTAINER_TEMPLATES למטה.
            line_index += 1
            continue

        if name in _CONTAINER_TEMPLATES:
            structural_level, node_type = _CONTAINER_TEMPLATES[name]
            anchor = call.args[0] if call.args else ""
            title = _flatten(call.args[1]) if len(call.args) > 1 else ""
            if title == "תוכן עניינים":
                line_index += 1
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
            line_index += 1
            continue

        # מרחב המספור שיחול על הצומת הזה, בלי לשנות את המחסנית:
        # הרשומה העמוקה ביותר שאינה ברמת סעיף או מתחתיה.
        pending_space = next(
            (entry[2] for entry in reversed(stack)
             if entry[0] < _STRUCTURAL_LEVEL_SECTION),
            "law")
        starred_use = (_starred_section_use(call, lines, line_index, pending_space)
                       if name == "ח:סעיף*" else "")
        if starred_use == "subsection":
            # **סעיף קטן שקיבל כותרת שוליים משלו** - תופעה אמיתית
            # בחקיקה מנדטורית, לא אנומליה. "שטר למוכ״ז" מתארת את
            # סעיף קטן (ב), לא את סעיף 30.
            #
            # עד 2026-09-19 נוצר כאן צומת section בלי מספר ובלי תוכן,
            # **אח** של הסעיף האמיתי - כך שסעיף 30 בפקודת השטרות הוצג
            # למשתמש בלי תוכן כלל וחמישה "סעיפים" רפאים לצדו. לא
            # "בלי מספר": בלי כלום.
            #
            # עכשיו: אין צומת. כותרת השוליים נשמרת, ותבנית העומק
            # שבשורה הבאה ({{ח:תת|(ב)}}) היא שיוצרת את הצומת - עם
            # המספר שלה, תחת הסעיף הפתוח, ועם הכותרת הזו.
            # **אין מספר סעיף חדש**, ולכן amend() ינסח "בסעיף 30,
            # בסעיף קטן (ב)" ולא "בסעיף 30(ב) לחוק העיקרי".
            pending_margin_title = _flatten(call.args[1]) if len(call.args) > 1 else ""
            starred_as_subsection.append(str(line_index))
            line_index += 1
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
                # {{ח:סעיף*}} שאין לו עוגן, ולכן אין סימן חד-משמעי מה
                # הוא. **נשאר בדיוק כפי שהיה לפני התיקון ומסומן** -
                # ראו _starred_section_use ו-node.unrecognized_starred.
                unrecognized_starred=(starred_use == "unknown"),
            )
            if node.unrecognized_starred:
                unrecognized_starred_ids.append(node.id)
            parent_node.children.append(node)
            stack.append((_STRUCTURAL_LEVEL_SECTION, node, numbering_space))
            line_index += 1
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
            remainder_stripped = remainder.strip()

            while stack[-1][0] >= depth:
                stack.pop()
            parent_node = stack[-1][1]
            numbering_space = stack[-1][2]

            if _TABLE_OPEN_RE.match(remainder_stripped):
                # טבלה מוטבעת מיד אחרי תבנית עומק (למשל {{ח:תת}}
                # <table...> בחוק הביטוח הלאומי - תקרת שכר טרחה, תוכן
                # מהותי, לא רק עיטור). נשמרת גולמית, לא ניתנת לעריכה.
                html, last_consumed = _consume_html_table(remainder_stripped, lines, line_index + 1)
                node = LegislativeNode(
                    id=_unique_child_id(parent_node, f"table-{_short_hash(html)}", collisions),
                    node_type="raw_block",
                    number=label or "",
                    margin_title=None,
                    text=html,
                    text_raw=html,
                    is_normative=True,
                    numbering_space=numbering_space,
                )
                parent_node.children.append(node)
                stack.append((depth, node, numbering_space))
                line_index = last_consumed + 1
                continue

            note_text = _is_pure_note(remainder)
            is_normative = note_text is None
            flattened = note_text if note_text is not None else _flatten(remainder).strip()
            node_type = _classify(name, label, kind_attr)
            node = LegislativeNode(
                id=_unique_child_id(parent_node, _slug(label, len(parent_node.children)), collisions),
                node_type=node_type,
                number=label or "",
                # כותרת שוליים שהגיעה מ-{{ח:סעיף*}} שקדם לשורה הזו.
                # נצרכת פעם אחת בלבד ואז מתאפסת.
                margin_title=normalize_text(pending_margin_title) or None,
                text=normalize_text(flattened),
                text_raw=flattened,
                is_normative=is_normative,
                numbering_space=numbering_space,
            )
            pending_margin_title = ""
            parent_node.children.append(node)
            stack.append((depth, node, numbering_space))
            line_index += 1
            continue

        if "\n" in line:
            # **בלוק רב-שורתי שאף ענף לא הכיר.** line מכיל "\n" אך ורק
            # אם _join_unclosed_templates איחדה אותו - splitlines()
            # לעולם אינה מחזירה תו כזה בתוך שורה. כלומר התנאי הזה נכון
            # בדיוק במקומות שבהם הפרסר קרס עד 2026-09-17, ולא באף מקום
            # אחר: אפס סיכון לחוקים שכבר נטענים.
            #
            # נשמר כ-raw_block, באותו דפוס בדיוק כמו בלוק <table> יתום
            # למעלה - **לא מדולג**. ההכרעה (ברק, 2026-09-18): "מילון
            # מונחים הוא תוכן, לא עיטור". שמונה פקודות (מס הכנסה,
            # החברות, המכס, הנמלים, הרוקחים, השטרות, הבטיחות בעבודה,
            # הנזיקין) נושאות נספח מילון עברי-אנגלי בתוך {{עמודות}} /
            # {{דוכיווני}} - תוכן משפטי אמיתי. החלופה שנשקלה ונדחתה
            # הייתה allowlist, שהייתה זורקת אותו בשקט.
            parent_node = stack[-1][1]
            node = LegislativeNode(
                id=_unique_child_id(parent_node, f"block-{_short_hash(line)}", collisions),
                node_type="raw_block",
                number="",
                margin_title=None,
                text=line,
                text_raw=line,
                is_normative=True,
                numbering_space=stack[-1][2],
            )
            parent_node.children.append(node)
            line_index += 1
            continue

        # תבנית לא-מוכרת ברמה העליונה (מאגר/תיבה/וכו') - מדולגת.
        # {{ח:כותרת}} נלכד למעלה (למשימה 4); {{ח:פתיח-התחלה}}/
        # {{ח:חתימות}}/{{ח:מבוא}}/{{ח:סוגר}} מטופלות למעלה כאזור דילוג
        # (_SKIP_ZONE_OPENERS/_SKIP_ZONE_CLOSER) - {{ח:מאגר}}/{{ח:תיבה}}
        # עדיין לא נדרשות להגדרת הסיום של משימה 3 ומתועדות כפער פתוח.
        line_index += 1

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
    root.unrecognized_starred_ids = unrecognized_starred_ids
    root.starred_as_subsection = starred_as_subsection
    root.continuation_completions = continuation_completions
    return root
