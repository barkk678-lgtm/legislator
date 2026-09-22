"""מקרה זהב חדש (ברק, 2026-09-16): הוכחה ש-amend() מנסח נכון תיקון
לסעיף שמקונן בתוך פרק, לא רק ילד ישיר של שורש החוק - זה בדיוק
התרחיש שהיה נכשל בשקט (lines=[]) לפני התיקון (ראו TASKS.md,
docstring של packages/corpus/node.find_sections).

**נקבע מראש, לפני המימוש (כמבוקש):** הפלט הצפוי נגזר מ-
_render_mutation הקיים (מוטציה בודדת, פעם ראשונה שהחוק מוזכר) ואומת
מול reference/ha-hoveret-ha-sgula.pdf §7.8 (עמ' 26) - שם המדריך
עצמו נותן דוגמה על חוק העונשין (מקונן: חלק/פרק/סימן) בניסוח
"בסעיף 14..." בלי שום אזכור של הפרק/הסימן. אם amend() אחרי התיקון
היה מנסח "בפרק ב', בסעיף 3" - זה היה טעות, לא שיפור.

**החוק:** "חוק הסדרים במשק המדינה (יצירת תנאים לצמיחה ולקליטת
העליה), התשנ"א–1991" - fixture אמיתי (wikitext חי מ-he.wikisource.org,
לא מומצא), 4 סעיפים, כולם מקוננים תחת פרק א'/פרק ב' - אפס ילדים
ישירים של השורש (בדיוק התרחיש שנכשל היום).

**העריכה:** סעיף 3 (בתוך פרק ב'), סעיף קטן (ב) - ReplaceWords יחיד
("המחאות חוב" -> "שטרי חוב"), אותו דפוס בדיוק כמו tests/unit/
test_amend_kaytanot.py (מוטציה בודדת מתלכדת לשורה אחת)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "amend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "render"))

from render_bill import Line  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402
from transform import ReplaceWords, apply  # noqa: E402
from engine import amend  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WIKITEXT_FIXTURE = ROOT / "tests" / "fixtures" / "wikitext" / "hesderim-1991.wikitext"
WIKITEXT_META = ROOT / "tests" / "fixtures" / "wikitext" / "hesderim-1991.meta.json"

_META = json.loads(WIKITEXT_META.read_text(encoding="utf-8"))
_AS_OF = _META["revision_timestamp"]
_LAW_ID = "hesderim-1991"
_TARGET_ID = f"{_LAW_ID}/פרק ב/s3/ב"


def load_before():
    text = WIKITEXT_FIXTURE.read_text(encoding="utf-8")
    return parse_wikitext(text, law_id=_LAW_ID, as_of=_AS_OF)


def build_after(before):
    return apply(before, [ReplaceWords(target_id=_TARGET_ID, old_phrase="המחאות חוב", new_phrase="שטרי חוב")])


EXPECTED_LINES = [
    Line(
        side_heading="תיקון סעיף 3",
        number="1.",
        text='בחוק הסדרים במשק המדינה (יצירת תנאים לצמיחה ולקליטת העליה), התשנ"א–1991',
        # המכולה (ב): השינוי יושב בתוך סעיף קטן (ב), ולכן הכתובת
        # היא "בסעיף 3(ב)" ולא "בסעיף 3" - drafting-rules.md §8.7
        # (עודכן במשימה 58; קודם לכן המכולה נשמטה).
        text_after=', בסעיף 3(ב), במקום "המחאות חוב" יבוא "שטרי חוב".',
        footnotes=["hesderim"],
        depth=0,
        source_node_id=_TARGET_ID,
        as_of=_AS_OF,
    ),
]


def main():
    before = load_before()
    after, annotations = build_after(before)
    got = amend(before, after, annotations, law_footnote_key="hesderim")
    want = EXPECTED_LINES

    # בדיקת-עזר מפורשת (לא רק amend() בסוף): מוכיחה שהסעיף העוגן אכן
    # נמצא ומקונן בתוך פרק, לא במקרה שטוח - כדי שהמבחן הזה לא "יעבור
    # במקרה" אם מישהו ישנה את המבנה בעתיד בלי לשים לב.
    section3 = next(c for c in before.children[1].children if c.number == "3")
    checks = [
        ("סעיף 3 מקונן בתוך פרק, לא ילד ישיר של השורש", section3 not in before.children),
        ("סעיף 3 הוא ילד של 'פרק ב'", before.children[1].node_type == "chapter" and section3.id.startswith(f"{_LAW_ID}/פרק ב")),
    ]

    print(f"שורות: נוצרו {len(got)}, במקור {len(want)}\n")
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else None
        w = want[i] if i < len(want) else None
        passed = g == w
        checks.append((f"line {i}", passed))
        if not passed:
            print(f"     got : {g}")
            print(f"     want: {w}")

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
