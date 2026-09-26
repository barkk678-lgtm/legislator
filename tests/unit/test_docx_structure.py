"""ח8 (25.9.2026): כל קובץ Word שהמערכת מייצרת נפתח בלי אזהרת
"Word מצא תוכן שאינו ניתן לקריאה".

הבדיקה רצה על **כל** יצרני ה-docx: הצעת חוק (עם ובלי שורות, עם ובלי
הערות שוליים, בכל עומק, ובדפוס הסעיף הפנימי), שאילתה, הסתייגויות.

שני הפגמים שנמצאו בפועל בקובץ שהורד מהאתר (law-2000167):
1. settings.xml מכריז על הערת שוליים מיוחדת id=1 (continuationNotice),
   ו-render_footnotes מחק אותה. בכל הורדה של הצעת חוק.
2. <w:tbl> בלי אף <w:tr> - כשאין בהצעה אף שורה.

ובקרה: הבודק עצמו לא מתריע על 54 קובצי Word אמיתיים שנשמרו בוורד
(הצעות חוק, שאילתות הכנסת, מסמכי הסתייגויות) - כדי שממצא שלו יהיה
פגם אמיתי ולא רעש.
"""

import glob
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("render", "reservations"):
    sys.path.insert(0, str(ROOT / "packages" / sub))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from docx_check import structural_problems  # noqa: E402
from render_bill import Bill, Line, write_docx  # noqa: E402

SKELETON = ROOT / "reference" / "skeleton-pshia.docx"


def _bill_bytes(lines, refs) -> bytes:
    bill = Bill(knesset="הכנסת העשרים וחמש", title="הצעת חוק בדיקה", initiator="בדיקה",
                lines=lines, explanatory=["הסבר"])
    out = Path(tempfile.mkstemp(suffix=".docx")[1])
    write_docx(bill, refs, SKELETON, out)
    return out.read_bytes()


def main() -> int:
    checks: list[tuple[str, bool, list[str]]] = []

    def check(name, data):
        p = structural_problems(data)
        checks.append((name, not p, p))

    one = [Line(text="בחוק הבדיקה", side_heading="תיקון סעיף 2", number="1.",
                text_after=" (להלן – החוק העיקרי), בסעיף 2, במקום \"שלושה\" יבוא \"חמישה\".",
                footnotes=["main"])]
    refs = {"main": "ס\"ח התשכ\"א, עמ' 1."}

    check("הצעת חוק: שורה אחת עם הערת שוליים", _bill_bytes(one, refs))
    one_nofn = [Line(**{**one[0].__dict__, "footnotes": []})]
    check("הצעת חוק: בלי הערות שוליים", _bill_bytes(one_nofn, {}))
    check("הצעת חוק: בלי אף שורה", _bill_bytes([], {}))
    deep = [Line(text="א", number="1."), Line(text="ב", marker="(א)", depth=1),
            Line(text="ג", marker="(1)", depth=2), Line(text="ד", marker="(א)", depth=3),
            Line(text="ה", marker="(1)", depth=4)]
    check("הצעת חוק: חמש רמות עומק", _bill_bytes(deep, {}))
    inner = [Line(text="אחרי סעיף 5 יבוא:", number="1.", side_heading="הוספת סעיף 5א"),
             Line(text="נוסח הסעיף החדש", inner_heading="כותרת", inner_number="5א.")]
    check("הצעת חוק: דפוס הסעיף הפנימי", _bill_bytes(inner, {}))

    # טקסט שהודבק מוורד: ירידת שורה ידנית היא \x0b, אסור ב-XML 1.0
    pasted = [Line(text="שורה ראשונה\x0bשורה שנייה\x07", number="1.")]
    check("הצעת חוק: טקסט עם \\x0b שהודבק מוורד", _bill_bytes(pasted, {}))

    from simple_doc import write_simple_docx  # noqa: PLC0415
    out = Path(tempfile.mkstemp(suffix=".docx")[1])
    write_simple_docx(title="שאילתה", meta_lines=["נושא: בדיקה"], paragraphs=["רקע\x0bהמשך", "שאלה?"],
                      skeleton=SKELETON, out=out)
    check("שאילתה", out.read_bytes())

    from render_docx import build_document  # noqa: PLC0415
    buf = io.BytesIO()
    build_document(bill_title="הצעת חוק בדיקה", items=[]).save(buf)
    check("הסתייגויות (python-docx), ריק", buf.getvalue())
    from types import SimpleNamespace as NS  # noqa: PLC0415
    buf = io.BytesIO()
    build_document(bill_title="הצעת חוק בדיקה", items=[
        NS(heading="לסעיף 1", lines=['בפסקה (1), במקום "שלושים ימים" יבוא "שישים ימים".']),
        NS(heading="לאחרי סעיף 1", lines=["אחרי הסעיף יבוא:", '"תחילה 2. תחילתו של חוק זה\x0b שנה."'])]).save(buf)
    check("הסתייגויות (python-docx), עם נוסח מצוטט", buf.getvalue())

    # בקרה: אפס ממצאים על קבצים שוורד עצמו שמר
    real = sorted(glob.glob(str(ROOT / "tests/fixtures/**/*.docx"), recursive=True)
                  + glob.glob(str(ROOT / "reference/**/*.docx"), recursive=True))
    noisy = [(Path(f).name, structural_problems(Path(f).read_bytes())) for f in real]
    noisy = [(n, p) for n, p in noisy if p]
    checks.append((f"בקרה: {len(real)} קובצי Word אמיתיים - אפס ממצאים",
                   len(real) >= 40 and not noisy, [f"{n}: {p[0]}" for n, p in noisy]))

    # בקרה שלילית: הבודק תופס את שני הפגמים שנמצאו, כל אחד לבד
    import zipfile  # noqa: PLC0415
    good = _bill_bytes(one, refs)
    zin = zipfile.ZipFile(io.BytesIO(good))
    def mutate(part, fn):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                zout.writestr(item.filename, fn(data) if item.filename == part else data)
        return b.getvalue()
    no_notice = mutate("word/footnotes.xml",
                       lambda d: d.replace(b'<w:footnote w:type="continuationNotice" w:id="1">'
                                           b'<w:p/></w:footnote>', b""))
    # המוטציה חייבת לשנות משהו - אחרת "נתפס" היה מתקיים גם על קובץ
    # שממילא חסרה בו ההערה, ולא מוכיח דבר
    checks.append(("בקרה שלילית: הערת continuationNotice חסרה - נתפס",
                   no_notice != good
                   and any("footnote 1" in p for p in structural_problems(no_notice)),
                   structural_problems(no_notice)))
    ctrl = mutate("word/document.xml", lambda d: d.replace("בדיקה".encode(), b"\x0b", 1))
    checks.append(("בקרה שלילית: תו בקרה בתוך w:t - נתפס",
                   any("XML לא תקין" in p for p in structural_problems(ctrl)), []))

    failed = 0
    for name, ok, detail in checks:
        print(("✓" if ok else "✗"), name)
        if not ok:
            failed += 1
            for d in detail[:8]:
                print("     ", d)
    print(f"\n{len(checks) - failed}/{len(checks)} עברו")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
