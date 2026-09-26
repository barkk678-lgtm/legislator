"""הבנק נבנה מהמסמך (tools/build_reservations_bank.py) - **והבנייה אידמפוטנטית** (סבב
התיקונים על אישורי הבנק, 26.9.2026).

הבנייה קוראת את הבנק הקיים כדי לשמור מזהים. הרצה חוזרת על בנק שכבר נבנה שכפלה אותו:
חובה ורשות 264 במקום 104, ומזהים חדשים - שבלעדיהם פסקי השומר אבדו. עכשיו: build() על
הבנק שבריפו מחזיר אותו בדיוק. נכשל על הקוד הקודם.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_reservations_bank as build  # noqa: E402


def test_build_is_a_fixpoint():
    current = json.loads(build.BANK.read_text(encoding="utf-8"))
    again = build.build()
    assert again["lists"] == current["lists"]
    got = {r["id"]: r for r in again["records"]}
    have = {r["id"]: r for r in current["records"]}
    assert set(got) == set(have), (sorted(set(got) - set(have))[:5], sorted(set(have) - set(got))[:5])
    changed = [i for i in have if got[i] != have[i]]
    assert not changed, changed[:5]


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_bank_build_idempotent: כל הבדיקות עברו")
