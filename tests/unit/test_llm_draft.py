"""בדיקות ל-apps/api/llm_draft.py (משימה ה, 2026-09-16) - בלי רשת.

שני נתיבים נבדקים: (1) נפילה חזרה לדטרמיניסטי כש-ANTHROPIC_API_KEY
חסר (המצב האמיתי בסביבת הבדיקות - לא מדומה) - מוכיח ש-/draft לעולם
לא קורס/נתקע כש-LLM לא זמין. (2) בניית ההקשר ופרסור הפסקאות כשה-LLM
כן עונה - נבדק בהזרקה ישירה של llm_draft.draft (monkeypatch של
המודול, לא complete_fn - הפונקציות הציבוריות כאן לא מקבלות אותו
כפרמטר, בכוונה: הן שכבת אפליקציה, לא שכבת llm עצמה).
"""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "support"))
from isolate_env import clear_secret, isolate, set_secret  # noqa: E402

# **הרמטיות.** עד 2026-09-19 הטסט הזה הסתמך על כך שבמקרה אין מפתחות
# בסביבה. מרגע שהם נטענים מקובץ, ההסתמכות הזו נשברה - ראו
# tests/support/isolate_env.py.
isolate()


import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))

import llm_draft  # noqa: E402
from bill_title import PLACEHOLDER  # noqa: E402
from explanatory_draft import draft_explanatory_notes  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from node import LegislativeNode  # noqa: E402
from render_bill import Line  # noqa: E402

client = TestClient(app)

_EMPTY_DRAFT_REQ = {"edits": [], "insertions": []}
_EMPTY_TREE = LegislativeNode(id="law-x", node_type="law", number="", margin_title=None, text="")


def main():
    ok = True

    # --- בלי ANTHROPIC_API_KEY (המצב האמיתי כאן) - /draft לא קורס,
    #     נופל בחזרה לדטרמיניסטי (PLACEHOLDER בשם, אין דברי הסבר על
    #     "לא נגעו בכלום") ---
    assert os.environ.get("ANTHROPIC_API_KEY") is None, "הבדיקה מניחה שאין מפתח בסביבה - אחרת היא בודקת משהו אחר"
    resp = client.post("/api/laws/kaytanot-1990/draft", json=_EMPTY_DRAFT_REQ)
    passed = resp.status_code == 200 and PLACEHOLDER in resp.json()["title"]
    ok = ok and passed
    print(("OK " if passed else "FAIL"), "/draft בלי מפתח -> 200 + נופל ל-PLACEHOLDER הדטרמיניסטי, לא קורס")

    # --- draft_bill_title_llm: LLM מחזיר 'מהות' -> משולב בתבנית הקבועה נכון ---
    original_draft = llm_draft.draft
    llm_draft.draft = lambda **kw: "  החמרת הענישה  "
    try:
        title = llm_draft.draft_bill_title_llm('חוק הקייטנות (רישוי ופיקוח), התש"ן–1990', [])
        passed = title.startswith('הצעת חוק הקייטנות (רישוי ופיקוח) (תיקון – החמרת הענישה), ') and PLACEHOLDER not in title
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "draft_bill_title_llm משלבת מהות מה-LLM בתבנית הקבועה, לא PLACEHOLDER ->", title if not passed else "")
    finally:
        llm_draft.draft = original_draft

    # --- draft_bill_title_llm: LLM מחזיר מחרוזת ריקה -> נופלת חזרה ל-PLACEHOLDER, לא כותרת שבורה ---
    llm_draft.draft = lambda **kw: "   "
    try:
        title = llm_draft.draft_bill_title_llm('חוק הקייטנות (רישוי ופיקוח), התש"ן–1990', [])
        passed = PLACEHOLDER in title
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "draft_bill_title_llm עם תשובה ריקה -> נופלת ל-PLACEHOLDER")
    finally:
        llm_draft.draft = original_draft

    # --- draft_explanatory_llm: מפצלת לפסקאות לפי שורה ריקה, מחתכת רווחים ---
    llm_draft.draft = lambda **kw: "פסקה ראשונה.\n\nפסקה שניה עם עוד טקסט.\n\n  פסקה שלישית.  "
    try:
        paras = llm_draft.draft_explanatory_llm([], _EMPTY_TREE, _EMPTY_TREE, set())
        passed = paras == ["פסקה ראשונה.", "פסקה שניה עם עוד טקסט.", "פסקה שלישית."]
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "draft_explanatory_llm מפצלת לפסקאות נכון ->", paras if not passed else "")
    finally:
        llm_draft.draft = original_draft

    # --- draft_explanatory_llm: תשובת LLM ריקה -> נופלת חזרה לדטרמיניסטי (לא [] ריק) ---
    fake_lines = [Line(side_heading="תיקון סעיף 1", number="1.", text="טקסט.", text_after="")]
    llm_draft.draft = lambda **kw: "   "
    try:
        paras = llm_draft.draft_explanatory_llm(fake_lines, _EMPTY_TREE, _EMPTY_TREE, set())
        expected = draft_explanatory_notes(fake_lines)
        passed = paras == expected and paras != []
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "draft_explanatory_llm עם תשובה ריקה -> נופלת לדטרמיניסטי, לא []")
    finally:
        llm_draft.draft = original_draft

    # ── ח9 (25.9.2026): מהות השינוי, בלי נימוק מומצא ──────────────
    def tree(section_text, title="מקום המושב", full="חוק-יסוד: הכנסת"):
        root = LegislativeNode(id="law-y", node_type="law", number="", margin_title=None, text="",
                               full_title=full)
        sec = LegislativeNode(id="law-y/s2", node_type="section", number="2", margin_title=title, text="")
        sec.children.append(LegislativeNode(id="law-y/s2/p0", node_type="subsection", number="",
                                            margin_title=None, text=section_text))
        root.children.append(sec)
        return root
    before_t, after_t = tree("מקום מושבה של הכנסת הוא ירושלים."), tree("מקום מושבה של הכנסת הוא תל אביב.")
    one_line = [Line(side_heading="תיקון סעיף 2", number="1.",
                     text='בחוק-יסוד: הכנסת, בסעיף 2, במקום "ירושלים" יבוא "תל אביב".', text_after="")]

    seen = []
    def capture(**kw):
        seen.append(kw["content"])
        return "מוצע לקבוע כי מקום מושבה של הכנסת יהיה תל אביב."
    llm_draft.draft = capture
    try:
        llm_draft.draft_explanatory_llm(one_line, before_t, after_t, {"2"})
        c = seen[0]
        passed = ("חוק-יסוד: הכנסת" in c and "מקום המושב" in c and "ירושלים" in c
                  and "תל אביב" in c and 'במקום "ירושלים"' in c)
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "ח9: ההקשר כולל שם חוק, כותרת שוליים, נוסח מלא (גם סעיף קטן) והוראת התיקון", "" if passed else c)
    finally:
        llm_draft.draft = original_draft

    calls = []
    def invents_then_clean(**kw):
        calls.append(kw["content"])
        if len(calls) == 1:
            return "מוצע לקבוע כי מקום מושבה של הכנסת יהיה תל אביב, על מנת לקרב את הכנסת לציבור."
        return "מוצע לקבוע כי מקום מושבה של הכנסת יהיה תל אביב, במקום ירושלים."
    llm_draft.draft = invents_then_clean
    try:
        paras = llm_draft.draft_explanatory_llm(one_line, before_t, after_t, {"2"})
        passed = len(calls) == 2 and "על מנת" in calls[1] and paras == [
            "מוצע לקבוע כי מקום מושבה של הכנסת יהיה תל אביב, במקום ירושלים."]
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "ח9: נימוק מומצא ('על מנת') -> ניסוח מחדש בלעדיו", "" if passed else paras)
    finally:
        llm_draft.draft = original_draft

    llm_draft.draft = lambda **kw: ("מוצע לקבוע כי מקום מושבה של הכנסת יהיה תל אביב. "
                                    "זאת בשל הצורך בקירוב הכנסת למרכז הכלכלי.")
    try:
        paras = llm_draft.draft_explanatory_llm(one_line, before_t, after_t, {"2"})
        passed = paras == ["מוצע לקבוע כי מקום מושבה של הכנסת יהיה תל אביב."]
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "ח9: נימוק שחזר גם בניסוח השני -> המשפט יורד, המהות נשארת", "" if passed else paras)
    finally:
        llm_draft.draft = original_draft

    b2, a2 = tree("יש לפנות לשר כדי לקבל היתר."), tree("יש לפנות לשר או לממונה כדי לקבל היתר.")
    calls.clear()
    def content_phrase(**kw):
        calls.append(1)
        return "מוצע לקבוע כי ניתן לפנות גם לממונה, ולא רק לשר, כדי לקבל היתר."
    llm_draft.draft = content_phrase
    try:
        paras = llm_draft.draft_explanatory_llm(one_line, b2, a2, {"2"})
        passed = len(calls) == 1 and paras == ["מוצע לקבוע כי ניתן לפנות גם לממונה, ולא רק לשר, כדי לקבל היתר."]
        ok = ok and passed
        print(("OK " if passed else "FAIL"), "ח9: 'כדי ל' שמופיע בנוסח החוק עצמו - תוכן, לא נימוק", "" if passed else paras)
    finally:
        llm_draft.draft = original_draft

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
