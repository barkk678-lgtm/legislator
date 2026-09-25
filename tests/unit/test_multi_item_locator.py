"""ח13 (26.9.2026) - תיקון בסעיף קטן או בפסקה מפנה ליחידה שהשתנתה.

שוחזר מהקובץ שהמערכת ייצאה לברק (reference/law-2000037-הצעת-חוק (2).docx):
שתי עריכות בסעיף 6 של חוק-יסוד: הכנסת - בסעיף קטן (ג) ובסעיף קטן (ד) - יצאו

    בסעיף 6 לחוק העיקרי –
    בסעיף 6 לחוק העיקרי, במקום "הורשע" יבוא "נאשם".
    בסעיף 6 לחוק העיקרי, אחרי "המרכזית" יבוא "או סגנו".

בלי היחידה, בלי מספור ועם "בסעיף 6 לחוק העיקרי" חוזר. עריכה **יחידה** בסעיף
קטן כבר קיבלה את המכולה ("בסעיף 6(ג), במקום...") - הבאג הוא בענף של כמה
הוראות באותו סעיף. המבנה הנכון - מדריך משפטים §7.10.8, עמ' 30:

    בסעיף 40 לחוק העיקרי –
    (1) בסעיף קטן (א)(5), המילים "כפי שרצה" – יימחקו;
    (2) סעיף קטן (ב) – בטל.

נבדקים כל סוגי העריכה בענף הזה: החלפה, מחיקה, הוספה אחרי, הוספה בסוף, ביטול
יחידה, כותרת שוליים ורישה.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("apps/api", "packages/corpus", "packages/amend", "packages/render"):
    sys.path.insert(0, str(ROOT / sub))

from node import LegislativeNode  # noqa: E402
from apply_changes import apply_pending_changes  # noqa: E402
from engine import amend  # noqa: E402


@dataclass
class _Edit:
    node_id: str
    text: str
    field: str = "text"


@dataclass
class _Ins:
    anchor_node_id: str
    kind: str
    text: str
    margin_title: str | None = None
    client_id: str = "c1"


def N(id_, typ, number, text="", *children, title=None):
    return LegislativeNode(id=id_, node_type=typ, number=number, margin_title=title,
                           text=text, children=list(children))


def _tree() -> LegislativeNode:
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title='חוק לדוגמה, התש"ף–2020',
        children=[
            N("law/s1", "section", "1", "", N("law/s1/p0", "paragraph", "", "הוראה כללית."), title="כללי"),
            N("law/s6", "section", "6", "",
              N("law/s6/p0", "paragraph", "", "לענין הבחירות –"),
              N("law/s6/a", "subsection", "(א)", "כל אזרח זכאי להיבחר, למעט –",
                N("law/s6/a/1", "paragraph", "(1)", "מי שהורשע בעבירה;"),
                N("law/s6/a/8", "paragraph", "(8)", "מי שנידון למאסר בפועל.")),
              N("law/s6/c", "subsection", "(ג)", "מועמד שהורשע לא יהיה חבר."),
              N("law/s6/d", "subsection", "(ד)", "קביעת יושב ראש הוועדה המרכזית לא תידרש."),
              title="זכות להיבחר"),
        ],
    )


def _lines(edits, insertions=()):
    before = _tree()
    result = apply_pending_changes(before, list(edits), list(insertions))
    return amend(before, result.after, result.annotations, law_footnote_key="law")


def _sec6(lines):
    """השורות של הוראת סעיף 6 (אחרי הכותרת), כמחרוזות."""
    out, inside = [], False
    for ln in lines:
        if ln.side_heading and "6" in ln.side_heading:
            inside = True
            out.append(("HEAD", ln.text + ln.text_after))
            continue
        if inside and ln.side_heading:
            break
        if inside:
            out.append((ln.marker, ln.text + (ln.text_after or "")))
    return out


def test_barak_case_two_subsections():
    rows = _sec6(_lines([
        _Edit("law/s1/p0", "הוראה כללית חדשה."),
        _Edit("law/s6/c", "מועמד שנאשם לא יהיה חבר."),
        _Edit("law/s6/d", "קביעת יושב ראש הוועדה המרכזית או סגנו לא תידרש."),
    ]))
    assert rows[0][1].startswith("בסעיף 6 לחוק העיקרי –"), rows
    assert rows[1] == ("(1)", 'בסעיף קטן (ג), במקום "שהורשע" יבוא "שנאשם";'), rows
    assert rows[2] == ("(2)", 'בסעיף קטן (ד), אחרי "המרכזית" יבוא "או סגנו".'), rows


def test_paragraph_inside_subsection_gets_full_chain():
    rows = _sec6(_lines([
        _Edit("law/s6/a/8", "מי שנידון למאסר בפועל של שנה."),
        _Edit("law/s6/c", "מועמד שנאשם לא יהיה חבר."),
    ]))
    assert rows[1] == ("(1)", 'בסעיף קטן (א)(8), בסופו יבוא "של שנה";'), rows
    assert rows[2][0] == "(2)" and rows[2][1].startswith("בסעיף קטן (ג), "), rows


def test_word_deletion_and_intro():
    rows = _sec6(_lines([
        _Edit("law/s6/p0", "לענין –"),
        _Edit("law/s6/d", "קביעת יושב ראש המרכזית לא תידרש."),
    ]))
    assert rows[1] == ("(1)", 'ברישה, המילה "הבחירות" – תימחק;'), rows
    assert rows[2][0] == "(2)" and rows[2][1].startswith("בסעיף קטן (ד), ") and rows[2][1].endswith("."), rows


def test_removal_and_mutation_together():
    rows = _sec6(_lines([
        _Edit("law/s6/a/1", ""),
        _Edit("law/s6/d", "קביעת יושב ראש הוועדה המרכזית או סגנו לא תידרש."),
    ]))
    assert rows[1] == ("(1)", "בסעיף קטן (א), פסקה (1) – תימחק;"), rows
    assert rows[2] == ("(2)", 'בסעיף קטן (ד), אחרי "המרכזית" יבוא "או סגנו".'), rows


def test_insertion_after_and_at_end_are_numbered_with_container():
    rows = _sec6(_lines(
        [_Edit("law/s6/c", "מועמד שנאשם לא יהיה חבר.")],
        [_Ins("law/s6/a/1", "paragraph", "מי שהוא עובד מדינה;", client_id="i1"),
         _Ins("law/s6/a/8", "paragraph", "מי שהוא שופט.", client_id="i2")]))
    markers = [m for m, _ in rows[1:] if m]
    assert markers == ["(1)", "(2)", "(3)"], rows
    phrases = [t for m, t in rows[1:] if m]
    assert phrases[0].startswith("בסעיף קטן (א), אחרי פסקה (1) יבוא:"), rows
    assert phrases[1].startswith("בסעיף קטן (א), בסופו יבוא:") or \
        phrases[1].startswith("בסעיף קטן (א), אחרי פסקה (8) יבוא:"), rows
    assert phrases[2].startswith("בסעיף קטן (ג), "), rows


def test_margin_title_item():
    rows = _sec6(_lines([
        _Edit("law/s6", "זכות להיבחר לכנסת", field="margin_title"),
        _Edit("law/s6/c", "מועמד שנאשם לא יהיה חבר."),
    ]))
    items = [r for r in rows[1:] if r[0]]
    assert items[0] == ("(1)", 'בכותרת השוליים, אחרי "להיבחר" יבוא "לכנסת";') or \
        items[0][1].startswith("בכותרת השוליים,"), rows
    assert items[-1][1].endswith("."), rows


def test_single_edit_unchanged():
    """הוראה יחידה בסעיף - כבר הייתה נכונה, ונשארת: שורה אחת עם המכולה."""
    lines = _lines([_Edit("law/s6/c", "מועמד שנאשם לא יהיה חבר.")])
    text = lines[0].text + lines[0].text_after
    assert 'בסעיף 6(ג), במקום "שהורשע" יבוא "שנאשם".' in text, text


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_multi_item_locator: כל הבדיקות עברו")
