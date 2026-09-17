"""תקציר הצעת חוק (משימה 2.1) - בלי רשת.

נבדק הקלט שנבנה ל-LLM, לא התשובה שלו: זה מה שקובע אם התקציר יכול
להיות נכון. הסכנה המרכזית כאן היא תקציר משכנע שנשען על חילוץ חלקי,
ולכן נבדק גם שהמידע על היקף החילוץ עובר הלאה.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "documents"))

from extract_docx import extract_bill  # noqa: E402
from summarize import _bill_as_prompt, summarize_bill  # noqa: E402


def main():
    ok = True
    bill = extract_bill(str(ROOT / "reference" / "skeleton-pshia.docx"))
    prompt = _bill_as_prompt(bill)

    captured = {}

    def fake_draft(*, instructions, content, max_tokens=900):
        captured["instructions"] = instructions
        captured["content"] = content
        return "  **מה ההצעה עושה**\nתיקון.\n"

    result = summarize_bill(bill, draft_fn=fake_draft)

    checks = [
        ("נוסח ההצעה" in prompt and "דברי הסבר" in prompt,
         "הקלט מפריד במפורש בין הנוסח לדברי ההסבר"),
        ("המאבק בארגוני פשיעה" in prompt, "שם ההצעה נכנס לקלט"),
        ("צביקה פוגל" in prompt, "המגיש נכנס לקלט"),
        ("4א." in prompt, "מספר הסעיף הפנימי נשמר בקלט"),
        ("תיקון סעיף 1" in prompt, "כותרת השוליים נשמרת בקלט"),
        (prompt.count("\n") > 15, "הקלט שומר על שורות נפרדות ולא נמעך לפסקה"),
        ("אל תמציא" in captured["instructions"], "ההנחיה אוסרת המצאת מספרים ושמות"),
        (result.text == "**מה ההצעה עושה**\nתיקון.", "התשובה מנוקה מרווחים"),
        (result.lines_used == len(bill.lines) and result.lines_used > 0,
         f"מדווח כמה שורות נוסח נכנסו ({result.lines_used})"),
        (result.explanatory_used == len(bill.explanatory),
         f"מדווח כמה פסקאות הסבר נכנסו ({result.explanatory_used})"),
        (result.initiators == bill.initiators, "המגישים עוברים הלאה"),
    ]

    # הצעה בלי נוסח: הקלט חייב לומר זאת במפורש ולא להשאיר חלל
    empty = extract_bill(str(ROOT / "reference" / "skeleton-pshia.docx"))
    empty.lines = []
    checks.append(("לא חולץ נוסח" in _bill_as_prompt(empty),
                   "נוסח ריק מסומן במפורש בקלט, כדי שה-LLM לא ימציא"))

    for passed, label in checks:
        ok = ok and passed
        print(("OK " if passed else "FAIL"), label)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
