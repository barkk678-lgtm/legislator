"""בדיקת שפיות ל-LegislativeNode. ראו TASKS.md משימה 2."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from node import LegislativeNode  # noqa: E402


def main():
    child = LegislativeNode(
        id="kaytanot-1990/s1/a/1",
        node_type="definition",
        number="(1)",
        margin_title=None,
        text='"ארגון נוער או תנועת נוער" – ...',
    )
    root = LegislativeNode(
        id="kaytanot-1990/s1",
        node_type="section",
        number="1",
        margin_title="הגדרות",
        text="",
        children=[child],
        source_ref='ס"ח התש"ן, עמ\' 155',
    )
    checks = [
        ("root.number הוא מספר החוק, לא מספר הצעת החוק", root.number == "1"),
        ("children מכיל את הבן", root.children == [child]),
        ("source_ref ברירת מחדל ריקה", child.source_ref == ""),
    ]
    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
