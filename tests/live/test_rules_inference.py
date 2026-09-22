"""בדיקה חיה (רשת + מודל): עשר שאלות שהתשובה להן **אינה כתובה
בסעיף אחד** ונובעת מצירוף של שניים או יותר. זו הבדיקה שברק הגדיר
כמוכיחה את ג1+ג2: לפני השינוי רובן נכשלו, כי שלב האחזור בחר
top-k סעיפים ולא ראה את השני.

מריצים ידנית: python3 tests/live/test_rules_inference.py
עולה כסף (קריאת מודל לכל שאלה, ~$0.04 במטמון חם).
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("apps/api", "packages/corpus", "packages/llm", "packages/config", "packages/knesset"):
    sys.path.insert(0, str(ROOT / p))
import rules_expert as rx  # noqa: E402

CASES = [
    ("האם אפשר להגיש הסתייגויות בקריאה ראשונה?", "86"),
    ("האם ועדה יכולה לדון בהצעת חוק פרטית לפני הקריאה הראשונה?", "דיון מוקדם"),
    ("מה קורה להצעת חוק פרטית אם היוזם שלה מפסיק לכהן?", "חבר הכנסת"),
    ("האם חבר כנסת יכול להצביע בוועדה שהוא אינו חבר בה?", "ועדה"),
    ("כמה חברי כנסת נדרשים כדי לכנס את הכנסת בפגרה?", "פגרה"),
    ("האם אפשר לקיים קריאה שנייה ושלישית באותה ישיבה?", "קריאה"),
    ("מי קובע לאיזו ועדה תועבר הצעת חוק אחרי קריאה ראשונה?", "ועדת הכנסת"),
    ("האם שר שאינו חבר כנסת יכול להשתתף בדיוני הכנסת?", "שר"),
    ("מה ההבדל בין הצעה לסדר היום לבין שאילתה מבחינת סדרי הדיון?", "שאילתה"),
    ("האם ניתן לערער על החלטת יושב ראש הכנסת בדבר סדר הדיון?", "יושב ראש"),
]


def main() -> int:
    passed = 0
    for question, must_contain in CASES:
        t0 = time.time()
        first, text, verdict = None, "", None
        for piece in rx.ask_stream(question):
            if isinstance(piece, str):
                if first is None:
                    first = time.time() - t0
                text += piece
            else:
                verdict = piece
        ok = verdict is not None and not verdict.refused and must_contain in (verdict.text or text)
        passed += ok
        ttft = f"{first:.1f}s" if first else "-"
        print(f"{'OK  ' if ok else 'FAIL'} [{ttft} למילה הראשונה, {time.time()-t0:.1f}s סה\"כ] {question}")
        if not ok and verdict is not None:
            print(f"     סורב={verdict.refused} סיבה={verdict.refusal_reason}")
            print(f"     תשובה: {(verdict.text or text)[:200]}")
        elif ok:
            print(f"     מקורות: {', '.join(rx.source_labels(verdict.cited_source_ids))[:150]}")
    print(f"\nעברו {passed} מתוך {len(CASES)}")
    return 0 if passed >= 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
