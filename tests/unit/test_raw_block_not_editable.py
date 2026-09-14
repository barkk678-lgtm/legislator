"""בודק ש-amend.engine מסרבת במפורש לעריכה תכנותית של צומת raw_block
(בלוק <table> גולמי - ראו node.py, wikitext_parser._consume_html_table).

ברק (2026-09-14): "הוראת תיקון על טבלה = NotImplementedError מפורש,
לא ניסיון." - לא בדיקה של פענוח מבנה טבלה (זה לא נעשה בכוונה), אלא
בדיקה שהמנוע לא מנחש הוראת "החלפה"/"תיקון" כשהתוכן הגולמי השתנה.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))

from node import LegislativeNode  # noqa: E402
from engine import amend  # noqa: E402


def _law_with_raw_block(table_html: str) -> LegislativeNode:
    table_node = LegislativeNode(
        id="law/s1/table-abc123",
        node_type="raw_block",
        number="",
        margin_title=None,
        text=table_html,
        text_raw=table_html,
        is_normative=True,
    )
    section = LegislativeNode(
        id="law/s1", node_type="section", number="1", margin_title="כותרת", text="", children=[table_node]
    )
    return LegislativeNode(
        id="law", node_type="law", number="", margin_title=None, text="",
        is_normative=False, full_title='חוק לדוגמה, התש"ף–2020',
        children=[section],
    )


def main():
    checks = []

    html_before = "<table><tr><td>10%</td></tr></table>"
    html_after = "<table><tr><td>12%</td></tr></table>"

    before = _law_with_raw_block(html_before)
    after = _law_with_raw_block(html_after)  # אותו id, טקסט גולמי שונה - "מישהו ניסה לערוך את הטבלה"

    try:
        amend(before, after, [], law_footnote_key="fake")
        checks.append(("שינוי טקסט ב-raw_block -> NotImplementedError", False))
    except NotImplementedError as exc:
        checks.append(("שינוי טקסט ב-raw_block -> NotImplementedError", "raw_block" in str(exc)))

    # ודאות: אותו טקסט (אין שינוי בפועל) לא אמור לזרוק כלום - amend()
    # לא מייצרת אף הוראת תיקון על raw_block שלא השתנה.
    before_same = _law_with_raw_block(html_before)
    after_same = _law_with_raw_block(html_before)
    lines = amend(before_same, after_same, [], law_footnote_key="fake")
    checks.append(("raw_block זהה (בלי שינוי) -> לא זורק, אין הוראות", lines == []))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
