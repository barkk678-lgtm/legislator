"""באג (סבב התיקונים על אישורי הבנק, ברק 26.9.2026): תואר שר מהמאגר יוצא משובש.

בטבריה, ברציני, 30 הסתייגויות יצאו כך:
    במקום "שר הפנים" יבוא "שר הפנים לביטחון לאומי".
    אחרי "שר הפנים" יבוא "באישור שר הפנים לשוויון חברתי וקידום מעמד האישה".
הסיבה: {השר} הפך ל"השר", ואז **כל** "השר" בטקסט הוחלף בשר מההצעה - גם בתואר שהגיע
מרשימת השרים ("השר לביטחון לאומי"). התיקון: מחליפים רק את המציין {השר} שבתבנית.

1. לכל תואר ברשימת השרים (קובץ הגיבוי, וממשלה אחרת במוק) - הפלט על טבריה מכיל את
   התואר מילה במילה, בהחלפת גורם ובאישור.
2. על טבריה, על 573919 (Word) ועל ה-fixtures מהכנסת: אין בפלט "שר ה<X> ל..." שאינו
   תואר מהרשימה ואינו מופיע בנוסח ההצעה עצמה.
נכשל על הקוד הקודם (30 רשומות בטבריה).
"""

import os
import re
import sys
from pathlib import Path

os.environ["LEGISLATOR_MINISTERS_SOURCE"] = "fallback"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402
import families  # noqa: E402
import ministers  # noqa: E402
from bill_input import read_bill  # noqa: E402
from pdf_bill import parse_bill_pdf  # noqa: E402

TIBERIAS = parse_bill_pdf(ROOT / "reference" / "הצעת חוק טבריה.pdf")
FIX = ROOT / "tests" / "fixtures" / "reservations"
OTHER_GOVERNMENT = ["השר לענייני מבחן", "השר לפיתוח הפריפריה והנגב", "שר האוצר", "שר המדע",
                    "השר לביטחון לאומי", "השר לשירותי דת"]
# "שר הפנים לביטחון" - שר בשמו ומיד אחריו מילה שמתחילה ב-ל: הצורה המשובשת
_GLUED_RE = re.compile(r"(?<![א-ת])שר\s+ה[א-ת]+(?:\s+וה[א-ת]+)?\s+ל[א-ת]+")


def _all_allowed():
    return {r.id: {"key": r.screen_key, "allowed": True} for r in bank.load_all()}


def _texts(bill, titles=None):
    orig_verdicts, orig_titles = bank._screen_verdicts, ministers.titles
    verdicts = _all_allowed()
    bank._screen_verdicts = lambda: verdicts
    if titles is not None:
        ministers.titles = lambda: list(titles)
    try:
        out = []
        for level in bank.LEVELS:
            out += [" ".join(it.lines) for it in families.candidates(bill, level, list(families.FAMILIES))[0]]
        return out
    finally:
        bank._screen_verdicts, ministers.titles = orig_verdicts, orig_titles


def _bill_text(bill):
    return " ".join(families._section_text(s) for s in bill.sections)


def _expected_titles(titles):
    """כל תואר שאינו נחסם בקו אדום (הקווים האדומים - סעיף ב1, בנפרד)."""
    return [t for t in titles if not bank.redline_violation(f"במקום \"שר הפנים\" יבוא \"{t}\".")]


def _check_verbatim(titles):
    texts = _texts(TIBERIAS, titles)
    missing = []
    for t in _expected_titles(titles):
        if f'במקום "שר הפנים" יבוא "{t}".' not in texts:
            missing.append(("החלפת גורם", t))
        if f'אחרי "שר הפנים" יבוא "באישור {t}".' not in texts:
            missing.append(("אישור", t))
    return missing


def _glued(texts, bill, titles):
    """הסתייגויות שיש בהן "שר ה<X> ל<Y>" שאינו חלק מתואר ברשימה ואינו בנוסח ההצעה."""
    source = re.sub(r"\s+", " ", _bill_text(bill))
    bad = []
    for t in texts:
        for m in _GLUED_RE.finditer(t):
            span = re.sub(r"\s+", " ", m.group(0))
            if any(span in x for x in titles) or span in source:
                continue
            bad.append(t)
            break
    return bad


def test_every_fallback_title_verbatim_in_tiberias():
    missing = _check_verbatim(ministers.titles())
    assert not missing, missing


def test_other_government_titles_verbatim_in_tiberias():
    """ממשלה אחרת (במוק) - אותו דבר, בלי שינוי קוד."""
    missing = _check_verbatim(OTHER_GOVERNMENT)
    assert not missing, missing


def test_no_glued_title_in_tiberias():
    titles = ministers.titles()
    bad = _glued(_texts(TIBERIAS), TIBERIAS, titles)
    assert not bad, (len(bad), bad[:5])


def test_no_glued_title_in_573919_and_fixtures():
    titles = ministers.titles()
    bills = [read_bill("573919.docx", (FIX / "573919.docx").read_bytes())]
    bills += [parse_bill_pdf(p) for p in sorted((FIX / "pdf").glob("*.pdf"))]
    bad = []
    for bill in bills:
        bad += [(bill.title[:40], t) for t in _glued(_texts(bill), bill, titles)]
    assert not bad, (len(bad), bad[:5])


def test_placeholder_is_the_only_thing_replaced():
    """{השר} מוחלף; "השר ל..." שבא מהרשימה או מהבנק - לא נגעים בו."""
    sec = TIBERIAS.sections[-1]
    out = families._resolve("ובלבד ש{השר} ידווח ל-השר לביטחון לאומי", TIBERIAS, sec)
    assert out == "ובלבד ששר הפנים ידווח ל-השר לביטחון לאומי", out
    assert families._resolve("באישור השר לשירותי דת", TIBERIAS, sec) == "באישור השר לשירותי דת"


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("test_minister_titles_verbatim: כל הבדיקות עברו")
