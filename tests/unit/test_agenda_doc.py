"""ס3 + ס4 (26.9.2026) - קובץ Word של הצעה לסדר היום, ויו"ר הכנסת.

ס3: הקובץ נבנה מהטופס של הכנסת (reference/הצעה לסדר יום (8).docx) והקוד
ממלא רק את הסימניות. הבדיקה המרכזית: ממלאים אותו בתוכן של הדוגמה **השנייה**
((10).docx) ומשווים ברמת ה-XML - document.xml זהה, פרט לתאריך ולמספר
(ריקים בכוונה - הכנסת מוסיפה אותם). ובנוסף: הצעה רגילה בלי רווח כפול,
פנייה ליו"ר לפי מגדר, חתימה לפי מגדר, מטא-דאטה בלי שמות, ובלי פגם מבני.
ס4: יו"ר הכנסת מהמאגר, במטמון; כישלון - הגיבוי הידני, ונרשם.
"""

import difflib
import html
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "render"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from agenda_doc import _bookmark_span, write_agenda_docx  # noqa: E402
from docx_check import structural_problems  # noqa: E402

EX10 = ROOT / "reference" / "הצעה לסדר יום (10).docx"
TMP = ROOT / "tests" / "_agenda.docx"


def _doc(path) -> str:
    return zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")


def _texts(doc: str) -> list[str]:
    paras = re.findall(r"<w:p[ >].*?</w:p>", doc, re.S)
    return [html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))) for p in paras]


def _write(**kw) -> str:
    fields = dict(kind="דחופה", subject="נושא", explanation=["הסבר."], speaker_name="אמיר אוחנה",
                  speaker_gender="זכר", mk_name="פלונית אלמונית", mk_gender="נקבה")
    fields.update(kw)
    write_agenda_docx(out=TMP, **fields)
    return _doc(TMP)


def test_identical_to_second_example_except_date_and_number():
    ref = _doc(EX10)

    def bm(name):
        s, e, _ = _bookmark_span(ref, name)
        return [html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)))
                for p in re.split(r"<w:br\s*/>", ref[s:e])]
    ours = _write(kind=bm("AGN_Type")[0].strip(), subject=bm("AGN_Subject")[0], explanation=bm("AGN_Description"),
                  speaker_name=bm("AGN_Yor_Name")[0], mk_name=bm("PM_Name")[0])

    def norm(x):
        x = re.sub(r' w:rsid\w*="[^"]*"', "", x)
        x = re.sub(r' w14:(paraId|textId)="[^"]*"', "", x)
        x = re.sub(r'<w:t( xml:space="preserve")?>', "<w:t>", x)
        return re.sub(r"(<w:p[ >]|<w:r[ >]|<w:bookmark)", r"\n\1", x).split("\n")
    removed = [l for l in difflib.unified_diff(norm(ref), norm(ours), n=0, lineterm="")
               if l.startswith("-") and not l.startswith("---")]
    added = [l for l in difflib.unified_diff(norm(ref), norm(ours), n=0, lineterm="")
             if l.startswith("+") and not l.startswith("+++")]
    assert not added, added
    gone = [re.findall(r"<w:t>([^<]*)</w:t>", l) for l in removed]
    # רק התאריך העברי, הלועזי, המספר - ושבירת שורה ריקה שבסוף דברי ההסבר בדוגמה
    assert [g for g in gone if g and g != [""]] == [["ד' בתמוז התשפ\"ה"], ["30 ביוני, 2025"], ["5487"]], gone


def test_no_date_no_number_and_form_text():
    t = [x for x in _texts(_write()) if x.strip()]
    assert t == ["הכנסת", "לכבוד", 'יו"ר הכנסת, ח"כ אמיר אוחנה', "אדוני היושב ראש,",
                 "אבקש להעלות על סדר יומה של הכנסת הצעה דחופה בנושא:", "נושא", "דברי הסבר:", "הסבר.",
                 "בכבוד רב,", "חברת הכנסת פלונית אלמונית"], t


def test_regular_kind_has_no_double_space():
    t = _texts(_write(kind="רגילה"))
    assert "אבקש להעלות על סדר יומה של הכנסת הצעה בנושא:" in t, t


def test_gendered_salutation_and_signature():
    t = _texts(_write(speaker_gender="נקבה", mk_gender=None))
    assert "גבירתי היושבת ראש," in t and "חבר/ת הכנסת פלונית אלמונית" in t, t


def test_explanation_paragraphs_as_line_breaks_like_the_example():
    doc = _write(explanation=["א.", "ב.", "ג."])
    s, e, _ = _bookmark_span(doc, "AGN_Description")
    assert doc[s:e].count("<w:br />") == 2, doc[s:e]


def test_metadata_and_structure():
    _write()
    data = TMP.read_bytes()
    core = zipfile.ZipFile(io.BytesIO(data)).read("docProps/core.xml").decode()
    assert "Yafa" not in core and "Robin" not in core, core
    assert not [n for n in zipfile.ZipFile(io.BytesIO(data)).namelist() if n.startswith("[trash]")]
    assert structural_problems(data) == [], structural_problems(data)


def test_speaker_cache_and_fallback():
    import knesset_speaker as ks
    from odata import OdataError
    calls = []

    def ok(entity, **kw):
        calls.append(entity)
        if entity == "KNS_PersonToPosition":
            return [{"PersonID": 1, "PositionID": 123}]
        return [{"FirstName": "דנה", "LastName": "כהן", "GenderDesc": "נקבה"}]

    def boom(entity, **kw):
        calls.append(entity)
        raise OdataError("474")
    saved = ks.fetch
    try:
        ks._cache, ks._failed_at = None, 0.0
        ks.fetch = ok
        assert ks.current_speaker() == {"name": "דנה כהן", "gender": "נקבה", "source": "feed"}
        ks.current_speaker()
        assert calls == ["KNS_PersonToPosition", "KNS_Person"], calls   # במטמון - בלי קריאה שנייה
        ks._cache, ks._failed_at, calls[:] = None, 0.0, []
        ks.fetch = boom
        fb = ks.current_speaker()
        assert fb["source"] == "fallback" and fb["name"] == "אמיר אוחנה", fb
        ks.current_speaker()
        assert calls == ["KNS_PersonToPosition"], calls   # כישלון במטמון 10 דקות
    finally:
        ks.fetch = saved
        ks._cache, ks._failed_at = None, 0.0


try:
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
finally:
    TMP.unlink(missing_ok=True)
print("test_agenda_doc: כל הבדיקות עברו")
