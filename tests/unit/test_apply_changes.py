"""בודק apply_changes.apply_pending_changes - הרכבת עץ "אחרי" אחד
מתוך רשימת עריכות + הוספות, כפי שהלקוח שולח בכל בקשה. ראו TASKS.md
משימה 10ב.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from apply_changes import apply_pending_changes  # noqa: E402
from engine import amend  # noqa: E402


@dataclass
class _Edit:
    node_id: str
    text: str


@dataclass
class _Insertion:
    kind: str
    anchor_node_id: str
    text: str
    margin_title: str | None = None
    client_id: str = "test-insertion-1"


def _tree() -> LegislativeNode:
    section1 = LegislativeNode(
        id="law/s1", node_type="section", number="1", margin_title="הגדרות", text="",
        children=[
            LegislativeNode(id="law/s1/p0", node_type="paragraph", number="",
                             margin_title=None, text="בחוק זה - קייטנה היא מקום נופש."),
        ],
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title='חוק לדוגמה, התש"ף–2020',
        children=[section1],
    )


def main():
    ok = True
    before = _tree()

    # שילוב: עריכת טקסט נתמכת + הוספת סעיף ראשי חדש, יחד באותה בקשה.
    edits = [_Edit(node_id="law/s1/p0", text="בחוק זה - קייטנה מפוקחת היא מקום נופש.")]
    insertions = [_Insertion(kind="section", anchor_node_id="law/s1", text="תוכן חדש.", margin_title="ביצוע")]

    result = apply_pending_changes(before, edits, insertions)

    passed_edit_ok = len(result.edit_statuses) == 1 and result.edit_statuses[0].ok
    ok = ok and passed_edit_ok
    print(("OK  " if passed_edit_ok else "FAIL"), "עריכת טקסט הצליחה",
          "" if passed_edit_ok else f"-> {result.edit_statuses}")

    passed_no_insertion_errors = len(result.insertion_errors) == 0
    ok = ok and passed_no_insertion_errors
    print(("OK  " if passed_no_insertion_errors else "FAIL"), "הוספת סעיף הצליחה",
          "" if passed_no_insertion_errors else f"-> {result.insertion_errors}")

    # סעיף 1 הוא היחיד, ואין סעיף אחריו - הוספה בסופו ממשיכה רצף פשוט
    # (next_appended_label) -> "2", לא תווית מורכבת ("1א" הייתה אמורה
    # להתרחש רק אם היה קיים כבר סעיף 2 אחריו).
    new_numbers = [c.number for c in result.after.children if c.node_type == "section"]
    passed_numbers = new_numbers == ["1", "2"]
    ok = ok and passed_numbers
    print(("OK  " if passed_numbers else "FAIL"), "מספרי הסעיפים אחרי -> 1, 2",
          "" if passed_numbers else f"-> {new_numbers}")

    lines = amend(before, result.after, result.annotations, law_footnote_key="fake")
    combined_text = " ".join(line.text for line in lines)
    combined_headings = " ".join(line.inner_heading for line in lines if line.inner_heading)
    passed_amend = '"מפוקחת"' in combined_text and "ביצוע" in combined_headings
    ok = ok and passed_amend
    print(("OK  " if passed_amend else "FAIL"), "amend() מייצר גם את שני התיקונים",
          "" if passed_amend else f"-> text={combined_text!r} headings={combined_headings!r}")

    # עריכה לא נתמכת (משפט חוזר על עצמו) - לא אמורה להפיל את שאר הבקשה,
    # רק להירשם כ-not-ok עם סיבה.
    before2 = _tree()
    before2.children[0].children[0].text = "קייטנה טובה. קייטנה טובה."
    edits2 = [_Edit(node_id="law/s1/p0", text="קייטנה טובה מאוד. קייטנה טובה.")]
    result2 = apply_pending_changes(before2, edits2, [])
    passed_unsupported = len(result2.edit_statuses) == 1 and not result2.edit_statuses[0].ok
    ok = ok and passed_unsupported
    print(("OK  " if passed_unsupported else "FAIL"), "עריכה לא נתמכת -> ok=False + סיבה, בלי קריסה")

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
