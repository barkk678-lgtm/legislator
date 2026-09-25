"""ח16-ב (26.9): סימון שהגיע לנוסח החוק - מקרים אמיתיים מה-DB.

1,912 צמתים ב-392 חוקים הציגו למשתמש, ומכאן גם לקובץ ה-Word, סימון גולמי:
- תבניות עומק באמצע טקסט: "{{ח:ת}} יוצא מן הכלל:" (316 צמתים, 7 חוקים)
- תמונות: "[[Image:Uniform Organic Logo.jpg|150px|link=]]" (16, 14)
- תגי HTML: "<wbr>" ב-908 כותרות שוליים (339 חוקים), "<s>", "<sup>", "<span>"...

כל מקרה כאן לקוח מצומת אמיתי (המזהה בהערה). על הקוד הקודם - נכשל.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from wikitext_parser import _flatten, parse_wikitext  # noqa: E402

CASES = [
    # law-2000019/פרק 4/s16/p1 - שבר מעורב
    ('מ-1<sup>1</sup><span style="font-family: Arial;">⁄</span><sub>4</sub> מהשכר', "מ-1¹⁄₄ מהשכר"),
    # law-2000901 - שם כימי עם נקודות שבירה
    ("<i>N</i>-Benzyl<wbr>piper<wbr>azine", "N-Benzylpiperazine"),
    # <s> - נוסח שאינו בתוקף: יורד, בלי רווח כפול ובלי רווח לפני פסיק
    ("לפי העניין <s>של הכנסת</s>, הוראות בדבר –", "לפי העניין, הוראות בדבר –"),
    # כך זה במקור (law-2000002 s12(ב)) - המחיקה בתוך הערה; בלי רווח לפני הפסיק
    ("לפי העניין {{ח:הערה|<s>של הכנסת</s>}}, הוראות בדבר –", "לפי העניין, הוראות בדבר –"),
    ("לטיפול בפסולת <s>בפסולת</s> לפי הוראות", "לטיפול בפסולת לפי הוראות"),               # law-2000017
    ("על האמור בפרט <s>(</s>5<s>)</s>, לדון", "על האמור בפרט 5, לדון"),                    # law-2000117
    # "<" שאינו תג - נשאר
    ('(55 מ"מ < LVEDD בבדיקת אקו)', '(55 מ"מ < LVEDD בבדיקת אקו)'),                       # law-2000111
    ("חומציות נמוכה 4.5 < PH – כל אלה:", "חומציות נמוכה 4.5 < PH – כל אלה:"),              # law-2000839
    # תמונה - מקום שמור עם השם, לא סימון ויקי
    ("[[Image:Uniform Organic Logo.jpg|150px|link=]]", "[תמונה: Uniform Organic Logo]"),   # law-2000743
    ("[[Image:אישור ייצור נאות כחול.png link=]]", "[תמונה: אישור ייצור נאות כחול]"),       # law-2000839
    # סוגריים שבורים במקור - לא "מתקנים" נוסח מקור
    ("מהוראות [[סעיפים 10 עד 12], 20א(א)", "מהוראות [[סעיפים 10 עד 12], 20א(א)"),          # law-2000204
    # <math> - אין לו ייצוג טקסט נאמן; נשאר
    ("<math>x</math> = כמות", "<math>x</math> = כמות"),
    # תבניות עומק באמצע טקסט (law-2000924, law-2000933)
    ("{{ח:ת}} יוצא מן הכלל:\n{{ח:תת}} פלואוריד הסידן", "יוצא מן הכלל:\nפלואוריד הסידן"),
    ("קצין בטיחות\n{{ח:תת|(1)}} פרטי רישיון", "קצין בטיחות\n(1) פרטי רישיון"),
]


def test_cases():
    bad = [(raw, want, _flatten(raw)) for raw, want in CASES if _flatten(raw) != want]
    assert not bad, "\n".join(f"{r!r}\n  want {w!r}\n  got  {g!r}" for r, w, g in bad)


def test_margin_title_wbr():
    """908 כותרות שוליים ב-339 חוקים נשאו "<wbr>" - הכותרת עוברת באותו מסלול."""
    wt = "{{ח:כותרת|חוק בדיקה, התשפ\"ו–2026}}\n{{ח:סעיף|1|אי-<wbr>תחולה}}\n{{ח:ת}} נוסח."
    tree = parse_wikitext(wt, law_id="t", as_of="2026-09-26T00:00:00Z")
    s1 = tree.children[0]
    assert s1.margin_title == "אי-תחולה", repr(s1.margin_title)



def test_content_derived_id_is_stable():
    """מזהה של פריט בלי מספר נגזר מתוכנו. ניקוי התצוגה לא ישנה אותו - בהרצת
    הבדיקה מול המאגר, 377 מזהים ב-42 חוקים היו מתחלפים (provenance, טיוטות)."""
    import hashlib
    wt = "{{ח:כותרת|חוק בדיקה}}\n{{ח:סעיף*}}\n{{ח:ת}} Benzyl<wbr>piperazine\n"
    tree = parse_wikitext(wt, law_id="t", as_of="2026-09-26T00:00:00Z")
    item = tree.children[0]
    old_hash = hashlib.sha1("Benzyl<wbr>piperazine".encode("utf-8")).hexdigest()[:8]
    assert item.id == f"t/s-{old_hash}", item.id
    assert item.children[0].text == "Benzylpiperazine", item.children[0].text

if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("test_inline_markup: כל הבדיקות עברו")
