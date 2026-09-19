"""חילוץ טקסט מקובץ Word 97-2003 בינארי (`.doc`).

**למה בכלל:** `libreoffice` מותקן בסביבה אבל בלי `libreoffice-writer`,
ולכן הוא לא מסוגל לטעון `.doc` כלל ("source file could not be
loaded"). `antiword`/`catdoc` אינם מותקנים. הפורמט עצמו מתועד
(MS-DOC), והחלק שנדרש כאן - טבלת החתיכות - קצר ויציב.

**מה הקובץ הזה עושה ומה לא:**

- **כן:** מחלץ את הטקסט לפי טבלת החתיכות (piece table), כולל שני
  הקידודים ש-Word מערבב באותו מסמך - UTF-16LE ו-cp1255 דחוס.
- **כן:** משמר את מבני הטבלה ברמת התא (`\\x07` הוא סימן תא ב-MS-DOC),
  ולכן אפשר לקרוא "עמודה 0 = כותרת שוליים, עמודה 1 = מספר הסעיף".
- **לא:** אינו משחזר את **עומק ההזחה**. ב-`.docx` העומק נגזר
  מ-`gridSpan` של התא (ראו extract_docx), וב-`.doc` הוא יושב
  ב-SPRM-ים של מאפייני הטבלה שאינם מפורסרים כאן. `depth` יוצא 0
  תמיד, ולכן הפלט מתאים לנתיב שאינו משתמש בעומק (הסתייגויות) ולא
  לנתיב שכן (חילוץ הצעה מלאה, ביקורת טיוטה).

**קידוד עברי:** החתיכות ה"דחוסות" אינן cp1252 כפי שנהוג לכתוב אלא
דף הקוד של המסמך; בקבצים עבריים מהכנסת זה cp1255. פענוח ב-cp1252
היה מחזיר ג'יבריש לטיני קריא-למראה - כלומר טקסט שנראה תקין ואינו.
"""

from __future__ import annotations

import struct

_FIB_FLAGS = 0x000A      # ה-bit שקובע איזה table stream בשימוש
_FIB_FC_CLX = 0x01A2     # fcClx, ואחריו lcbClx - מיקום קבוע ב-Word97+
_WHICH_TABLE_BIT = 0x0200
_PIECE_COMPRESSED = 0x40000000

CELL_MARK = "\x07"
_CONTROL = dict.fromkeys(
    # סימני שדה, מעברי עמוד/עמודה, סימני הערת שוליים ועוגני אובייקט -
    # תווי בקרה שאינם טקסט. 0x07 (תא) ו-0x0B (שורה בתוך תא) נשמרים.
    [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x08, 0x0C,
     0x13, 0x14, 0x15, 0x1E, 0x1F],
    None,
)


class DocBinaryError(Exception):
    """הקובץ אינו `.doc` בינארי תקין, או שמבנהו אינו נתמך."""


def extract_text(data: bytes, *, codepage: str = "cp1255") -> str:
    """הטקסט המלא של המסמך, לפי טבלת החתיכות.

    `\\r` נשאר סימן סוף פסקה ו-`\\x07` סימן תא, כדי ש-`extract_rows`
    תוכל לשחזר את הטבלה. לניקוי מלא ראו `plain_text`."""
    try:
        import olefile  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover
        raise DocBinaryError("חסרה הספרייה olefile לקריאת .doc") from e

    import io  # noqa: PLC0415

    if not olefile.isOleFile(io.BytesIO(data)):
        raise DocBinaryError("הקובץ אינו מסמך Word בינארי (אינו OLE).")
    ole = olefile.OleFileIO(io.BytesIO(data))
    if not ole.exists("WordDocument"):
        raise DocBinaryError("חסר זרם WordDocument - זה אינו מסמך Word.")

    wd = ole.openstream("WordDocument").read()
    if len(wd) < _FIB_FC_CLX + 8:
        raise DocBinaryError("ה-FIB קצר מדי - הקובץ פגום.")
    flags = struct.unpack_from("<H", wd, _FIB_FLAGS)[0]
    table_name = "1Table" if flags & _WHICH_TABLE_BIT else "0Table"
    if not ole.exists(table_name):
        raise DocBinaryError(f"חסר זרם {table_name}.")
    table = ole.openstream(table_name).read()

    fc_clx, lcb_clx = struct.unpack_from("<II", wd, _FIB_FC_CLX)
    clx = table[fc_clx:fc_clx + lcb_clx]
    if not clx:
        raise DocBinaryError("טבלת החתיכות (CLX) ריקה.")

    i = 0
    while i < len(clx) and clx[i] == 1:  # Prc - מדלגים, לא נדרש לטקסט
        i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
    if i >= len(clx) or clx[i] != 2:
        raise DocBinaryError("לא נמצא Pcdt בטבלת החתיכות.")

    lcb = struct.unpack_from("<I", clx, i + 1)[0]
    pcdt = clx[i + 5:i + 5 + lcb]
    count = (len(pcdt) - 4) // 12
    if count <= 0:
        raise DocBinaryError("טבלת החתיכות אינה מכילה אף חתיכה.")
    cps = struct.unpack_from(f"<{count + 1}I", pcdt, 0)

    out = []
    for k in range(count):
        fc = struct.unpack_from("<I", pcdt, 4 * (count + 1) + 8 * k + 2)[0]
        length = cps[k + 1] - cps[k]
        if fc & _PIECE_COMPRESSED:
            start = (fc & ~_PIECE_COMPRESSED) // 2
            out.append(wd[start:start + length].decode(codepage, "replace"))
        else:
            out.append(wd[fc:fc + length * 2].decode("utf-16-le", "replace"))
    return "".join(out)


def plain_text(data: bytes, *, codepage: str = "cp1255") -> str:
    """הטקסט בלי תווי בקרה: תא ופסקה הופכים לשורה חדשה."""
    text = extract_text(data, codepage=codepage)
    text = text.translate(_CONTROL).replace("\x0b", "\n")
    lines = [ln.strip() for ln in text.replace(CELL_MARK, "\n").split("\r")]
    return "\n".join(ln for ln in ("\n".join(lines)).split("\n") if ln.strip())


def extract_rows(data: bytes, *, codepage: str = "cp1255") -> list[list[str]]:
    """שורות הטבלה, כל שורה כרשימת תאים.

    ב-MS-DOC כל תא מסתיים ב-`\\x07` והשורה מסתיימת ב-`\\x07` נוסף,
    ולכן התא האחרון ברשימה ריק תמיד ומושמט. פסקה שאינה בטבלה כלל
    מוחזרת כשורה בת תא יחיד."""
    text = extract_text(data, codepage=codepage).translate(_CONTROL)
    rows: list[list[str]] = []
    for para in text.split("\r"):
        if CELL_MARK not in para:
            stripped = para.replace("\x0b", " ").strip()
            if stripped:
                rows.append([stripped])
            continue
        cells = [c.replace("\x0b", " ").strip() for c in para.split(CELL_MARK)]
        while cells and not cells[-1]:
            cells.pop()
        if any(cells):
            rows.append(cells)
    return rows
