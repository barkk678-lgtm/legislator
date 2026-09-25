"""צ4 (26.9.2026) - עשר הודעות חולין על כל אחד משלושת הצ'אטבוטים.

בדיקה אוטומטית לא יודעת לזהות עברית מביכה ("מה כולך חושב?") - הכלי הזה
מריץ את אותו מסלול שהאתר מריץ (chat_layer.preflight ואז chitchat_reply,
עם השם ו"מה אני יודע לעשות" של כל צ'אטבוט, מ-main._CHAT_TOOLS) ומדפיס את
התשובות לקריאה אנושית. קורא למודל (עולה כסף, ~30 קריאות קצרות).

    python3 tools/chitchat_sample.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))

import chat_layer  # noqa: E402

TOOLS = {  # זהה ל-apps/api/main.py _CHAT_TOOLS
    "rules": ("מומחה התקנון", "שאלות על תקנון הכנסת, חוק הכנסת וחוק-יסוד: הכנסת"),
    "query": ("מנסח השאילתות", "ניסוח שאילתה לשר בפורמט המקובל"),
    "agenda": ("מנסח ההצעות לסדר", "ניסוח הצעה לסדר היום"),
}
MESSAGES = [
    "היי",
    "שלום, מה נשמע?",
    "תודה רבה!",
    "אתה מדהים, כל הכבוד",
    "מי אתה?",
    "מה אתה יודע לעשות?",
    "בוקר טוב",
    "אתה בוט או בן אדם?",
    "סופ\"ש נעים",
    "איך אתה מרגיש היום?",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()
    out = []
    for key, (name, can_do) in TOOLS.items():
        print(f"\n=== {name} ===")
        for msg in MESSAGES:
            pf = chat_layer.preflight(msg)
            if pf.kind == "chitchat":
                reply = chat_layer.chitchat_reply(msg, tool=name, can_do=can_do)
            elif pf.kind == "insult":
                reply = pf.reply
            else:
                reply = "(סווג כעניינית - הולך לכלי עצמו)"
            print(f"- {msg}\n  [{pf.kind}] {reply}")
            out.append({"tool": name, "message": msg, "kind": pf.kind, "reply": reply})
    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
