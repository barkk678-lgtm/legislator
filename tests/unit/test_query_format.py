"""ב2 - מבנה השאילתה, מול שבע שאילתות אמיתיות (reference/sheiltot).

**הדפוס שנמדד:** שאילתה מוגשת בתבנית של הכנסת, והיא כותבת בעצמה
את הכותרת, המספר הסידורי, שורת "חבר הכנסת X שאל את השר Y ביום..."
ו"מועד אחרון למתן תשובה". מה שמחוללים הוא שלושה רכיבים בלבד:
פסקת רקע, השורה "רצוני לשאול:", ושאלות בשורות נפרדות.

**ארבעת ההבדלים שתוקנו**, מול השאילתה שהמערכת הפיקה קודם:
1. כותרת מזכר "אל:/מאת:/נושא:" שאינה קיימת באף שאילתה אמיתית
2. חוסר פסקת רקע
3. חוסר השורה "רצוני לשאול:"
4. שאלות רצופות בפסקה אחת במקום שורה לשאלה
"""

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))
sys.path.insert(0, str(ROOT / "packages" / "render"))

import query_tool as qt  # noqa: E402

MODEL_REPLY = (
    "נושא: חלוקת כוח האדם במשטרה בין המחוזות\n"
    "גוף: קיימים פערים בין מחוזות המשטרה במספר השוטרים המוקצים.\n"
    "רצוני לשאול:\n"
    "מהי מצבת כוח האדם הנוכחית במשטרה בחלוקה למחוזות?\n"
    "על סמך אילו קריטריונים נקבעת החלוקה?\n"
)


def draft():
    original = qt.draft_conversation
    qt.draft_conversation = lambda **kw: MODEL_REPLY
    try:
        return qt.draft_query(turns=[{"role": "user", "content": "כוח אדם במשטרה"}],
                              kind="רגילה", minister="לביטחון לאומי", mk_name="ברק")
    finally:
        qt.draft_conversation = original


def test_body_keeps_its_lines():
    """**הבדל 4.** חיתוך ברווח לבן היה מאחד את הרקע והשאלות לפסקה
    אחת - בדיוק מה שהשאילתה הגרועה עשתה."""
    body = draft()["body"]
    assert body.count("\n") >= 3, repr(body)


def test_retsoni_line_is_present_on_its_own_line():
    """**הבדל 3.** המילים "רצוני לשאול:" קבועות בכל שבע הדוגמאות."""
    lines = draft()["body"].split("\n")
    assert "רצוני לשאול:" in lines, lines


def test_background_comes_before_the_questions():
    """**הבדל 2.** פסקת רקע לפני "רצוני לשאול:", ושאלות אחריה."""
    lines = draft()["body"].split("\n")
    idx = lines.index("רצוני לשאול:")
    assert idx >= 1, "אין פסקת רקע"
    assert all(ln.rstrip().endswith("?") for ln in lines[idx + 1:]), lines[idx + 1:]


def test_instructions_forbid_the_memo_header():
    """**הבדל 1.** אל/מאת/נושא אינם קיימים באף שאילתה אמיתית."""
    text = qt._instructions("רגילה")
    assert '"אל:"' in text and '"מאת:"' in text
    assert "אל תכתוב" in text


def test_instructions_forbid_inventing_a_source():
    """מקור מומצא במסמך שמוגש לכנסת בשם חבר כנסת הוא תקלה חמורה."""
    text = qt._instructions("רגילה")
    assert "אל תמציא מקור" in text
    assert "על-פי פרסומים" in text


def test_docx_has_no_memo_header():
    out = Path("/tmp/_q_fmt.docx")
    qt.write_query_docx(draft(), skeleton=ROOT / "reference" / "skeleton-pshia.docx", out=out)
    with zipfile.ZipFile(out) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", "", xml)
    for forbidden in ("אל: השר", "מאת:", "חבר/ת הכנסת"):
        assert forbidden not in text, f"נמצאה שורת מזכר: {forbidden}"
    assert "רצוני לשאול:" in text
    out.unlink()


def test_real_examples_all_share_the_pattern():
    """המבנה נגזר מהקורפוס ולא הומצא - ראו CLAUDE.md."""
    found = 0
    for f in sorted((ROOT / "reference" / "sheiltot").glob("*.docx")):
        if "לא טובה" in f.name:
            continue   # זו השאילתה שהמערכת הפיקה, לא דוגמה אמיתית
        with zipfile.ZipFile(f) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        text = re.sub(r"<[^>]+>", " ", re.sub(r"</w:p>", "\n", xml))
        if "רצוני לשאול" in text:
            found += 1
        assert "אל: השר" not in text, f"{f.name}: כותרת מזכר בשאילתה אמיתית?"
    assert found >= 6, f"רק {found} דוגמאות עם 'רצוני לשאול'"


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_query_format: כל הבדיקות עברו")
