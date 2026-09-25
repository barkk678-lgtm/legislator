"""ח11-ב (26.9): "(א) הופך ל-(א)(1)" כפריט בהוראה של כמה פריטים באותו סעיף.

§7.10.8 (עמ' 30): כמה תיקונים באותו סעיף - שורת פתיח "בסעיף N לחוק העיקרי –"
ואחריה פריטים ממוספרים, כל אחד עם היחידה שלו. כאן: פסקה ראשונה ב-6(א),
והחלפת מילים ב-6(ב). הצפוי:

    בסעיף 6 לחוק העיקרי –
    (1) בסעיף קטן (א), האמור בו יסומן "(1)" ואחריו יבוא:
    "(2) ...";
    (2) בסעיף קטן (ב), במקום "רואים אותו" יבוא "יראו אותו".

על הקוד הקודם - הפריט הראשון לא היה קיים בכלל (התפריט לא הציע אותו).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("packages/corpus", "packages/render", "packages/amend", "apps/api"):
    sys.path.insert(0, str(ROOT / p))

from wikitext_parser import parse_wikitext  # noqa: E402
from engine import amend  # noqa: E402
from transform import ReplaceWords, apply  # noqa: E402
from insert_preview import build_insertion_transform  # noqa: E402

NEW_TEXT = "על אף האמור בפסקה (1), תקנות לפי סעיף קטן זה טעונות אישור ועדת החינוך של הכנסת."


def _load():
    fx = ROOT / "tests/fixtures/wikitext"
    meta = json.loads((fx / "kaytanot.meta.json").read_text(encoding="utf-8"))
    return parse_wikitext((fx / "kaytanot.wikitext").read_text(encoding="utf-8"),
                          law_id="kaytanot-1990", as_of=meta["revision_timestamp"])


def test_relabel_as_an_item_among_others():
    before = _load()
    first, reason = build_insertion_transform(before, "kaytanot-1990/s6/א", "paragraph",
                                              text=NEW_TEXT, new_id="kaytanot-1990/s6/א/2")
    assert first is not None, reason
    swap = ReplaceWords(target_id="kaytanot-1990/s6/ב", old_phrase="רואים אותו", new_phrase="יראו אותו")
    after, annotations = apply(before, [first, swap])
    lines = amend(before, after, annotations, law_footnote_key="kaytanot")
    texts = [(ln.marker or "", ln.text + ln.text_after) for ln in lines]
    assert texts[0][1].endswith("בסעיף 6 – "), texts[0]
    assert texts[1] == ("(1)", 'בסעיף קטן (א), האמור בו יסומן "(1)" ואחריו יבוא:'), texts[1]
    assert texts[2][1] == f'"(2) {NEW_TEXT}";', texts[2]
    assert texts[3][0] == "(2)" and texts[3][1].startswith("בסעיף קטן (ב), במקום \"רואים אותו\" יבוא \"יראו אותו\""), texts[3]


def test_changed_text_is_not_silently_relabeled():
    """הנוסח עבר ל-(1) וגם השתנה - החוברת מפצלת לשתי הוראות; לא מנוסח כ"יסומן"."""
    before = _load()
    first, _ = build_insertion_transform(before, "kaytanot-1990/s6/א", "paragraph",
                                         text=NEW_TEXT, new_id="kaytanot-1990/s6/א/2")
    after, annotations = apply(before, [first])
    import engine
    unit = next(c for c in engine._find_by_id(after, "kaytanot-1990/s6/א").children if c.number == "(1)")
    unit.text = unit.text.replace("השר", "השרה", 1)
    try:
        amend(before, after, annotations, law_footnote_key="kaytanot")
    except NotImplementedError:
        return
    raise AssertionError("צפוי NotImplementedError")


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("test_first_paragraph_multi_item: כל הבדיקות עברו")
