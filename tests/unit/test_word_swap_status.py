"""ח19 (26.9.2026) - החלפת סדר של שתי מילים הפילה את השרת.

שוחזר בדפדפן על חוק הקייטנות: "לא ינהל אדם קייטנה" -> "לא ינהל קייטנה אדם"
החזיר 500 מ-/render, והמשתמש ראה "השרת לא הצליח לעדכן את הצעת החוק". הסיבה:
ה-diff מתרגם את ההחלפה למחיקה ולהוספה, והמחיקה של "אדם" (או "קייטנה") אינה
ייחודית אחרי ההוספה - transform זורק ValueError, ו-apply_pending_changes לא
תפס אותו. עכשיו זו עריכה שלא נקלטה: EditStatus עם ok=False וסיבה, העץ לא
משתנה, ושאר העריכות באותה בקשה ממשיכות.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("apps/api", "packages/corpus", "packages/amend", "packages/render", "tests/golden"):
    sys.path.insert(0, str(ROOT / sub))

from apply_changes import apply_pending_changes  # noqa: E402
from test_kaytanot import load_before  # noqa: E402


@dataclass
class _Edit:
    node_id: str
    text: str
    field: str = "text"


def _node(tree, node_id):
    stack = [tree]
    while stack:
        n = stack.pop()
        if n.id == node_id:
            return n
        stack.extend(n.children)
    return None


def _s2_and_s4(tree):
    s2 = next(n for n in tree.children if n.number == "2")
    s4 = next(n for n in tree.children if n.number == "4")
    return s2.children[0], s4.children[0]


def test_word_swap_is_a_failed_edit_not_a_crash():
    before = load_before()
    p2, p4 = _s2_and_s4(before)
    assert "אדם קייטנה" in p2.text, p2.text
    edits = [_Edit(p2.id, p2.text.replace("אדם קייטנה", "קייטנה אדם")),
             _Edit(p4.id, p4.text.rstrip(".") + " בלבד.")]
    result = apply_pending_changes(before, edits, [])   # לפני התיקון: ValueError
    by_node = {s.node_id: s for s in result.edit_statuses}
    assert by_node[p2.id].ok is False, result.edit_statuses
    assert "יותר מפעם אחת" in by_node[p2.id].reason, by_node[p2.id]
    assert _node(result.after, p2.id).text == p2.text, "העריכה שנכשלה לא נוגעת בעץ"
    assert by_node[p4.id].ok is True, result.edit_statuses
    assert _node(result.after, p4.id).text.endswith("בלבד."), _node(result.after, p4.id).text


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_word_swap_status: כל הבדיקות עברו")
