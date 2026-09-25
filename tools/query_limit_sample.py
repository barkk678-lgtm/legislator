"""ש14 (26.9.2026): כמה טיוטות שאילתה נכנסות למגבלת המילים - מול האתר.

עשרה נושאים, שאילתה דחופה (40 מילים), ניסוח ראשון בלבד (בלי "התכנס"):
הספירה היא של השרת (query_tool.body_word_count), כמו שהממשק מציג.

    SSL_CERT_FILE=... python3 tools/query_limit_sample.py --base https://legislator-tau.vercel.app
"""

import argparse
import json
import time
import urllib.request

TOPICS = [
    "מחסור בשוטרים בערי הנגב",
    "זמני המתנה לניתוחים בבתי החולים בפריפריה",
    "עליית מחירי הדירות להשכרה בתל אביב",
    "מחסור במורים למתמטיקה בבתי הספר התיכוניים",
    "תחבורה ציבורית בשבת בחיפה",
    "זיהום אוויר ממפעלים במפרץ חיפה",
    "קיצוץ בתקציב מרכזי הסיוע לנפגעות תקיפה מינית",
    "עיכובים בתשלום קצבאות נכות בביטוח הלאומי",
    "מחסור בחדרי ממ\"ד בגני ילדים בצפון",
    "סגירת סניפי דואר ביישובים קטנים",
]


def draft(base, topic, kind):
    body = json.dumps({"topic_description": topic, "kind": kind,
                       "minister": "השר הממונה", "mk_name": "ישראל ישראלי"}).encode()
    req = urllib.request.Request(base + "/api/query/draft", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as exc:  # noqa: BLE001 - פרוקסי לא יציב
            if attempt == 2:
                return {"error": str(exc)}
            time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--kind", default="דחופה")
    args = ap.parse_args()
    inside = 0
    for topic in TOPICS:
        d = draft(args.base, topic, args.kind)
        wc, limit = d.get("word_count"), d.get("word_limit")
        ok = d.get("within_limit") is True
        inside += ok
        print(f"{'✓' if ok else '✗'} {wc}/{limit}  {topic}" if wc is not None else f"? {topic}: {d}")
    print(f"\nנכנסו למגבלה: {inside} מתוך {len(TOPICS)}")


if __name__ == "__main__":
    main()
