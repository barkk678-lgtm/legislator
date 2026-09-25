"""ש1 (25.9.2026) - קובץ הוורד של השאילתה מול שאילתה אמיתית, ברמת ה-XML.

לכל שורה במסמך שלנו נבדק שהתכונות שלה - סגנון, יישור, ריווח, מספור,
גופן עברי, קו תחתון - **זהות לשורה המקבילה בשאילתה אמיתית** של הכנסת
(reference/sheiltot/25_pq_13836979.docx). לא "דומה", זהה.
"""
import sys
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "render"))
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "llm"))
sys.path.insert(0, str(ROOT / "packages" / "config"))

from docx_check import structural_problems  # noqa: E402
from query_doc import asker_line, split_body, write_query_docx_knesset  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SAMPLE = ROOT / "reference" / "sheiltot" / "25_pq_13836979.docx"
BODY = ("על-פי פרסומה של הכתבת ורד פלמן מ\"כאן 11\", אתר \"סקס אדיר\" שנסגר בשנת 2018, חזר לפעול.\n"
        "רצוני לשאול:\n"
        "1. מדוע משטרת ישראל לא פועלת לסגירת האתר?\n"
        "האם בעל האתר נחקר? היכן עומדת החקירה כעת?")


def _paragraphs(data: bytes) -> list[dict]:
    doc = etree.fromstring(zipfile.ZipFile(__import__("io").BytesIO(data)).read("word/document.xml"))
    out = []
    for p in doc.iter(W + "p"):
        ppr = p.find(W + "pPr")
        def val(path, attr="val"):
            el = ppr.find(path) if ppr is not None else None
            return None if el is None else el.get(W + attr)
        runs = [r for r in p.iter(W + "r") if "".join(t.text or "" for t in r.iter(W + "t")).strip()]
        rpr = runs[-1].find(W + "rPr") if runs else None
        fonts = rpr.find(W + "rFonts") if rpr is not None else None
        out.append({
            "text": "".join(t.text or "" for t in p.iter(W + "t")).strip(),
            "style": val(W + "pStyle"),
            "jc": val(W + "jc"),
            "before": val(W + "spacing", "before"),
            "line": val(W + "spacing", "line"),
            "num": val(f"{W}numPr/{W}numId"),
            "cs_font": fonts.get(W + "cs") if fonts is not None else None,
            "underline": rpr is not None and rpr.find(W + "u") is not None,
        })
    return out


def _find(paras, pred):
    hits = [p for p in paras if pred(p)]
    assert hits, "לא נמצאה שורה"
    return hits[0]


def _ours(kind="רגילה", gender="נקבה"):
    out = Path("/tmp/_s1_query.docx")
    write_query_docx_knesset(kind=kind, subject="צורך דחוף בסגירת אתר המשמש לפרסום מודעות זנות",
                             asker=asker_line("עדי עזוז", "איתמר בן גביר - השר לביטחון לאומי", gender),
                             body=BODY, out=out)
    data = out.read_bytes()
    out.unlink()
    return data


def _key(p):
    return {k: v for k, v in p.items() if k != "text"}


ROLES = {
    "הכנסת": lambda p: p["text"] == "הכנסת",
    "כותרת": lambda p: p["text"].startswith("שאילתה"),
    "נושא": lambda p: "צורך דחוף בסגירת אתר" in p["text"],
    "השואל": lambda p: "עדי עזוז" in p["text"],
    "רקע": lambda p: p["text"].startswith("על-פי פרסומה"),
    "רצוני לשאול": lambda p: p["text"] == "רצוני לשאול:",
    "שאלה": lambda p: p["text"].startswith("מדוע משטרת ישראל"),
}


def test_every_line_matches_the_real_query_exactly():
    ours, real = _paragraphs(_ours()), _paragraphs(SAMPLE.read_bytes())
    for role, pred in ROLES.items():
        a, b = _key(_find(ours, pred)), _key(_find(real, pred))
        assert a == b, f"{role}: שלנו {a} / אמיתית {b}"


def test_asker_line_is_the_real_text():
    ours = _paragraphs(_ours())
    assert _find(ours, ROLES["השואל"])["text"] == \
        "חברת הכנסת עדי עזוז שאלה את איתמר בן גביר - השר לביטחון לאומי"


def test_questions_are_word_numbered_not_typed():
    """המספור של וורד (numId 3), ו"1." שהמודל כתב בעצמו - מוסר."""
    ours = _paragraphs(_ours())
    qs = [p for p in ours if p["num"] == "3"]
    assert [p["text"] for p in qs] == ["מדוע משטרת ישראל לא פועלת לסגירת האתר?",
                                       "האם בעל האתר נחקר? היכן עומדת החקירה כעת?"], qs


def test_kind_in_heading_only_when_not_regular():
    """ב-app.xml של הדוגמה: הסימנייה QUR_Type = "<סוג שאילתה (אם לא רגילה)>"."""
    for kind, expected in (("רגילה", "שאילתה"), ("דחופה", "שאילתה דחופה"), ("ישירה", "שאילתה ישירה")):
        got = _find(_paragraphs(_ours(kind=kind)), ROLES["כותרת"])["text"]
        assert got == expected, (kind, got)


def test_what_the_knesset_adds_is_not_in_our_file():
    text = " ".join(p["text"] for p in _paragraphs(_ours()))
    for absent in ("4822", "ביום ", "מועד אחרון למתן תשובה"):
        assert absent not in text, absent


def test_unknown_gender_is_the_double_form_not_a_guess():
    assert asker_line("נועם כהן", "שר הפנים", None) == "חבר/ת הכנסת נועם כהן שאל/ה את שר הפנים"
    assert asker_line("נועם כהן", "שר הפנים", "זכר") == "חבר הכנסת נועם כהן שאל את שר הפנים"


def test_file_is_structurally_valid_and_has_the_emblem():
    data = _ours()
    assert structural_problems(data) == []
    names = zipfile.ZipFile(__import__("io").BytesIO(data)).namelist()
    assert "word/media/image1.png" in names
    assert not any(n.startswith("customXml/") for n in names), "מטא-נתונים של SharePoint"


def test_split_body_without_retsoni_keeps_everything_as_background():
    assert split_body("שורה אחת\nשורה שתיים") == (["שורה אחת", "שורה שתיים"], [])


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_query_docx_knesset: כל הבדיקות עברו")
