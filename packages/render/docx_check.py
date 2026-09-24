"""בודק מבני לקובצי Word שהמערכת מייצרת (ח8, 25.9.2026).

Word מחמיר בהרבה מ-python-docx ומ-LibreOffice: קובץ שנפתח בשניהם
יכול עדיין לפתוח בוורד "Word מצא תוכן שאינו ניתן לקריאה". לכן
"נפתח ב-python-docx" אינו הוכחה, והבודק הזה מחפש את הגורמים
הקונקרטיים שוורד מסמן כפגם:

- חלק שאינו XML תקין (כולל תווי בקרה אסורים בתוך w:t)
- חלק בלי content type, או Override שמפנה לחלק שאינו קיים
- relationship שמפנה לחלק שאינו קיים, או r:id שאינו מוגדר ב-rels
- הפניה להערת שוליים/סיום שאינה קיימת - כולל ההערות המיוחדות
  ש-settings.xml מכריז עליהן ב-footnotePr/endnotePr. **זה הפגם
  שנמצא בפועל ב-25.9**: הרנדרר מחק את הערת ה-continuationNotice
  (id=1) וההגדרות המשיכו להפנות אליה.
- מזהים כפולים (הערות שוליים, סימניות)
- טבלה בלי שורה, תא בלי פסקה, תא שהאלמנט האחרון בו אינו פסקה
- ילדי w:pPr / w:rPr שלא בסדר שהסכמה של OOXML קובעת

זה לא מאמת מלא מול ה-XSD - הסכמות אינן בריפו. זו רשימת הגורמים
הנפוצים, וכל אחד מהם נבדק מול סכמה שנכתבה כאן במפורש.
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


# סדר הילדים לפי ECMA-376 חלק 1, CT_PPrBase (+ rPr, sectPr, pPrChange
# בסוף) ו-CT_RPr. אלמנט שאינו ברשימה - לא נבדק (לא נחשב שגיאה).
_PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
    "pPrChange",
]
_RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof",
    "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern",
    "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd",
    "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
    "specVanish", "oMath",
]


def _order_problems(parent: ET.Element, order: list[str], where: str) -> list[str]:
    rank = {name: i for i, name in enumerate(order)}
    last, last_name, out = -1, "", []
    for child in parent:
        if not child.tag.startswith(f"{{{W}}}"):
            continue
        name = child.tag.split("}", 1)[1]
        if name not in rank:
            continue
        if rank[name] < last:
            out.append(f"{where}: <w:{name}> אחרי <w:{last_name}> - סדר שגוי")
        else:
            last, last_name = rank[name], name
    return out


def _rels_path(part: str) -> str:
    d, f = posixpath.split(part)
    return posixpath.join(d, "_rels", f + ".rels")


def structural_problems(data: bytes) -> list[str]:
    """רשימת פגמים מבניים בקובץ docx. רשימה ריקה = לא נמצא פגם מהסוגים
    שנבדקים (לא הוכחה שוורד יפתח בלי אזהרה, אבל כל פגם שנמצא כאן
    הוא פגם אמיתי)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        return [f"לא קובץ zip: {exc}"]
    names = set(z.namelist())
    problems: list[str] = []

    if "[Content_Types].xml" not in names:
        return ["חסר [Content_Types].xml"]

    trees: dict[str, ET.Element] = {}
    for name in sorted(names):
        if name.endswith((".xml", ".rels")):
            try:
                trees[name] = ET.fromstring(z.read(name))
            except ET.ParseError as exc:
                problems.append(f"{name}: XML לא תקין ({exc})")

    # ── content types ──
    ct = trees.get("[Content_Types].xml")
    if ct is not None:
        defaults = {e.get("Extension", "").lower() for e in ct.iter(f"{{{CT}}}Default")}
        overrides = {e.get("PartName", "").lstrip("/") for e in ct.iter(f"{{{CT}}}Override")}
        for part in sorted(overrides - names):
            problems.append(f"[Content_Types].xml: Override לחלק שאינו קיים - {part}")
        for part in sorted(names):
            # [trash]/ - תיקייה ש-Word עצמו כותב לחבילה ואינו מצפה לה content type
            if part == "[Content_Types].xml" or part.endswith("/") or part.startswith("[trash]/"):
                continue
            ext = part.rsplit(".", 1)[-1].lower() if "." in part else ""
            if part not in overrides and ext not in defaults:
                problems.append(f"{part}: אין לו content type")

    # ── relationships ──
    rel_ids: dict[str, set[str]] = {}
    for name, root in trees.items():
        if not name.endswith(".rels"):
            continue
        src_dir = posixpath.dirname(posixpath.dirname(name))  # word/_rels/x.rels -> word
        ids: set[str] = set()
        for rel in root.iter(f"{{{PR}}}Relationship"):
            rid = rel.get("Id", "")
            if rid in ids:
                problems.append(f"{name}: Id כפול {rid}")
            ids.add(rid)
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target", "")
            resolved = (target.lstrip("/") if target.startswith("/")
                        else posixpath.normpath(posixpath.join(src_dir, target)))
            if resolved not in names:
                problems.append(f"{name}: {rid} מפנה לחלק שאינו קיים - {resolved}")
        owner = posixpath.join(src_dir, posixpath.basename(name)[: -len(".rels")])
        rel_ids[owner] = ids

    for name, root in trees.items():
        if name.endswith(".rels") or name == "[Content_Types].xml":
            continue
        defined = rel_ids.get(name, set())
        for el in root.iter():
            for attr in (f"{{{R}}}id", f"{{{R}}}embed", f"{{{R}}}link"):
                rid = el.get(attr)
                if rid and rid not in defined:
                    problems.append(f"{name}: {rid} אינו מוגדר ב-{_rels_path(name)}")

    # ── הערות שוליים והערות סיום ──
    for kind in ("footnote", "endnote"):
        part = f"word/{kind}s.xml"
        existing: set[str] = set()
        if part in trees:
            for note in trees[part].findall(_w(kind)):
                nid = note.get(_w("id"))
                if nid in existing:
                    problems.append(f"{part}: מזהה כפול {nid}")
                existing.add(nid)
        settings = trees.get("word/settings.xml")
        if settings is not None:
            for pr in settings.iter(_w(f"{kind}Pr")):
                for ref in pr.findall(_w(kind)):
                    nid = ref.get(_w("id"))
                    if nid not in existing:
                        problems.append(
                            f"word/settings.xml: {kind}Pr מפנה ל-{kind} {nid} שאינו קיים ב-{part}")
        for name, root in trees.items():
            for ref in root.iter(_w(f"{kind}Reference")):
                nid = ref.get(_w("id"))
                if nid not in existing:
                    problems.append(f"{name}: {kind}Reference {nid} שאינו קיים ב-{part}")

    # ── תוכן גוף: סימניות, טבלאות, סדר ילדים ──
    body_parts = [n for n in trees if n.startswith("word/") and n.endswith(".xml")
                  and posixpath.basename(n).split(".")[0].rstrip("0123456789")
                  in ("document", "footnotes", "endnotes", "header", "footer")]
    for name in body_parts:
        root = trees[name]
        seen: set[str] = set()
        for bm in root.iter(_w("bookmarkStart")):
            bid = bm.get(_w("id"))
            if bid in seen:
                problems.append(f"{name}: bookmark id כפול {bid}")
            seen.add(bid)
        for i, tbl in enumerate(root.iter(_w("tbl")), start=1):
            if tbl.find(_w("tr")) is None:
                problems.append(f"{name}: טבלה {i} בלי אף שורה (w:tr)")
            grid = tbl.find(_w("tblGrid"))
            n_cols = len(grid.findall(_w("gridCol"))) if grid is not None else 0
            for j, tr in enumerate(tbl.findall(_w("tr")), start=1):
                spans = 0
                for edge in ("gridBefore", "gridAfter"):
                    el = tr.find(f"{_w('trPr')}/{_w(edge)}")
                    spans += int(el.get(_w("val"))) if el is not None else 0
                for tc in tr.findall(_w("tc")):
                    gs = tc.find(f"{_w('tcPr')}/{_w('gridSpan')}")
                    spans += int(gs.get(_w("val"))) if gs is not None else 1
                if n_cols and spans != n_cols:
                    problems.append(
                        f"{name}: טבלה {i} שורה {j} - {spans} עמודות מול {n_cols} ברשת")
        for i, tc in enumerate(root.iter(_w("tc")), start=1):
            blocks = [c for c in tc if c.tag in (_w("p"), _w("tbl"), _w("sdt"))]
            if not blocks:
                problems.append(f"{name}: תא {i} בלי פסקה (w:p)")
            elif blocks[-1].tag != _w("p"):
                problems.append(f"{name}: תא {i} - האלמנט האחרון אינו פסקה")
        for ppr in root.iter(_w("pPr")):
            problems.extend(_order_problems(ppr, _PPR_ORDER, f"{name} w:pPr"))
        for rpr in root.iter(_w("rPr")):
            problems.extend(_order_problems(rpr, _RPR_ORDER, f"{name} w:rPr"))

    # כפילויות זהות (למשל אותה שגיאת סדר ב-300 runs) - פעם אחת עם מונה
    counted: dict[str, int] = {}
    for p in problems:
        counted[p] = counted.get(p, 0) + 1
    return [p if n == 1 else f"{p} (×{n})" for p, n in counted.items()]
