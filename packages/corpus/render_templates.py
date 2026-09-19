"""פירוק תבניות עיצוב של ויקיפדיה לטקסט קריא.

**ההכרעה (ברק, 2026-09-19): רנדר — לא פרסור ולא `raw_block`.**
תבניות עיצוב (`{{מוקטן}}`, `{{ממורכז}}`) מוסרות ומשאירות את
הטקסט; תבניות מבנה (`{{טורים שווים}}`, `{{ש}}`) מרונדרות כשורות.

**למה זה לא `_flatten`:** `_flatten` מיישרת את תבניות ה-`ח:`
של מרחב החקיקה (`ח:פנימי`, `ח:חיצוני`, `ח:הערה`) — קישורים
והערות שהפרסר מכיר. התבניות כאן הן תבניות **ויקיפדיה כלליות**
שדלפו לתוך נוסח החוק: 2,157 מופעים ב-133 חוקים. הן אינן חלק
ממרחב החקיקה ואין להן משמעות משפטית.

**מה לא נעשה כאן:** 68 מהמופעים במרחב `law` יושבים בתוך טבלת
HTML גולמית (`<table>`), שאינה עוברת ב-`_flatten` בכלל — ולכן
גם `{{ח:פנימי}}` שורדת שם. זו בעיה נפרדת ופתוחה; ראו open-gaps.
"""

from __future__ import annotations

import re

# עיצוב טהור: מסירים את המעטפת, משאירים את התוכן.
_FORMATTING = {"מוקטן", "מוגדל", "ממורכז", "קו תחתון", "הדגשה", "קטן", "גדול"}
# מבנה: כל ארגומנט הוא תא, ומופרדים ברווח מפריד.
_STRUCTURE = {"טורים שווים", "טורים שווים ממורכז", "עמודות"}
# מונח דו-לשוני: "עברית (English)". שני הערכים תוכן, לא עיצוב.
_BILINGUAL = {"דוכיווני", "דוכיווני שווה"}

_CELL_SEP = " | "
_TEMPLATE_START = "{{"


def _split_args(body: str) -> list[str]:
    """מפצל ארגומנטים ברמה העליונה בלבד - `|` בתוך תבנית מקוננת
    או בתוך תגית HTML אינו מפריד."""
    args, depth, cur = [], 0, []
    i = 0
    while i < len(body):
        two = body[i : i + 2]
        if two == "{{":
            depth += 1; cur.append(two); i += 2; continue
        if two == "}}":
            depth -= 1; cur.append(two); i += 2; continue
        ch = body[i]
        if ch == "|" and depth == 0:
            args.append("".join(cur)); cur = []
        else:
            cur.append(ch)
        i += 1
    args.append("".join(cur))
    return args


def render(text: str) -> str:
    """מחזיר את הטקסט אחרי פירוק תבניות העיצוב, רקורסיבית.

    תבנית שאינה מוכרת **נשארת כפי שהיא** - אותו עיקרון כמו
    `_flatten`: לא ממציאים רינדור למה שלא זיהינו."""
    out, i = [], 0
    while i < len(text):
        if text[i : i + 2] != _TEMPLATE_START:
            out.append(text[i]); i += 1
            continue
        end, depth = i, 0
        while end < len(text):
            if text[end : end + 2] == "{{":
                depth += 1; end += 2
            elif text[end : end + 2] == "}}":
                depth -= 1; end += 2
                if depth == 0:
                    break
            else:
                end += 1
        if depth != 0:                      # תבנית לא סגורה - גולמי
            out.append(text[i:]); break
        inner = text[i + 2 : end - 2]
        parts = _split_args(inner)
        name = parts[0].strip()
        args = [render(a).strip() for a in parts[1:]]

        if name == "ש":
            out.append("\n")
        elif name == "=":
            out.append("=")
        elif name in _FORMATTING:
            out.append(" ".join(a for a in args if a))
        elif name in _BILINGUAL:
            kept = [a for a in args if a]
            out.append(f"{kept[0]} ({kept[1]})" if len(kept) > 1
                       else (kept[0] if kept else ""))
        elif name in _STRUCTURE:
            # ב-{{עמודות}} הארגומנט הראשון הוא מספר העמודות.
            cells = args[1:] if name == "עמודות" and args and args[0].isdigit() else args
            out.append(_CELL_SEP.join(c for c in cells if c))
        else:
            out.append(text[i:end])         # לא מוכרת - כפי שהיא
        i = end
    return "".join(out)


def unrendered_templates(text: str) -> list[str]:
    """שמות התבניות שנשארו בטקסט אחרי `render` - לניטור."""
    return [m.group(1).strip() for m in re.finditer(r"\{\{([^|}]+)", render(text))]
