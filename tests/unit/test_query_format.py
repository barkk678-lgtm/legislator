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


# ── שומר המקורות (ברק, 23.9.2026) ──────────────────────────────────
# **הנחיה אינה שומר.** בהרצה הראשונה אחרי תיקון ב2 המודל כתב
# "נושא זה עלה גם בדיונים בוועדת הפנים והגנת הסביבה" על נושא
# שלא נמסר לו שום מקור - למרות הנחיה מפורשת לא להמציא. אותו
# דפוס בדיוק כמו שם השר, ואותו פתרון: שומר דטרמיניסטי.

from query_tool import unsupported_source_claims  # noqa: E402


def test_invented_committee_is_caught():
    found = unsupported_source_claims(
        "נושא זה עלה בדיון בוועדת הפנים והגנת הסביבה.", "מצבת כוח אדם במשטרה")
    assert "ועד" in found and "דיון" in found, found


def test_source_the_user_supplied_is_allowed():
    """**מקור ברקע לגיטימי ורצוי** - השאילתות האמיתיות פותחות כך.
    מה שאסור הוא מקור שהמודל המציא."""
    assert unsupported_source_claims(
        "בדיון בוועדת הפנים עלה הנושא.",
        "תשאל על מה שעלה בוועדת הפנים בדיון האחרון") == []


def test_prefixed_form_counts_as_supported():
    """"בוועדת" אצל המודל נתמך על ידי "ועדת" אצל המשתמש."""
    assert unsupported_source_claims("עלה בוועדת החינוך.",
                                     "ועדת החינוך דנה בזה") == []


def test_generic_background_without_a_source_passes():
    assert unsupported_source_claims(
        "קיימים פערים בין מחוזות המשטרה במספר השוטרים המוקצים.",
        "מצבת כוח אדם במשטרה") == []


def test_invented_number_is_a_source_too():
    """"על-פי נתוני 2024" הוא מקור לכל דבר."""
    assert "2024" in unsupported_source_claims("על-פי נתוני 2024 חלה עלייה.",
                                               "מצבת כוח אדם")


def test_number_the_user_gave_is_allowed():
    assert unsupported_source_claims("על-פי נתוני 2024 חלה עלייה.",
                                     "מה קרה ב-2024 במשטרה") == []


def test_draft_query_raises_instead_of_returning_an_invented_source():
    """**זורקת ולא מנקה בשקט.** מסמך שמוגש לכנסת ובו דיון שלא
    היה הוא תקלה שאין ממנה דרך חזרה."""
    import query_tool as q
    original = q.draft_conversation
    q.draft_conversation = lambda **kw: (
        "נושא: כוח אדם במשטרה\n"
        "גוף: הנושא עלה בדיון בוועדת הפנים והגנת הסביבה.\n"
        "רצוני לשאול:\n"
        "מהי מצבת כוח האדם?\n")
    try:
        q.draft_query(turns=[{"role": "user", "content": "מצבת כוח אדם במשטרה"}],
                      kind="רגילה", minister="לביטחון לאומי", mk_name="ברק")
    except q.QueryDraftError as e:
        assert "לא מופיעים בדבריכם" in str(e), str(e)
        return
    finally:
        q.draft_conversation = original
    raise AssertionError("מקור מומצא עבר בלי שגיאה")


def test_guard_does_not_block_a_clean_draft():
    import query_tool as q
    original = q.draft_conversation
    q.draft_conversation = lambda **kw: MODEL_REPLY
    try:
        out = q.draft_query(turns=[{"role": "user", "content": "כוח אדם במשטרה"}],
                            kind="רגילה", minister="לביטחון לאומי", mk_name="ברק")
        assert out["body"].startswith("קיימים פערים")
    finally:
        q.draft_conversation = original


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_query_format: כל הבדיקות עברו")
