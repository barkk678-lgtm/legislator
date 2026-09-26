"""אישורי הבנק של ברק (docs/bank-approvals-2026-09-26.md, 26.9.2026) - הבנק תואם את המסמך.

- **ספירה לכל משפחה ולכל רמה - בדיוק המספרים שבמסמך.**
- כל רשומה: status approved, מקור "ברק 26.9 (סשן הבנק)". מה שהמסמך מוחק - אינו.
- **רשימה אחת** לגורמים ההזויים (106), לשני השימושים; לכל גורם מין דקדוקי.
- בתנאים - אין רמה רצינית ואין "החל מיום"; אין "של השנה הבאה" בשום מקום.
- לאחרי הסעיף האחרון - לא סעיף מתנגש בכותרת השוליים.
- §0.4: אישור אנושי מפורש גובר על פסק השומר רק ברשומה המסומנת; השומר לא משתנה.
נכשל על הקוד הקודם (115 רשומות ממתינות, בלי תוספת לפועל).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))
sys.path.insert(0, str(ROOT / "tools"))

import bank  # noqa: E402
import build_reservations_bank as builder  # noqa: E402
import families  # noqa: E402
from pdf_bill import BillSection, BillUnit, ParsedBill  # noqa: E402

DOC = re.sub(r"\s+", " ", (ROOT / "docs" / "bank-approvals-2026-09-26.md").read_text(encoding="utf-8"))
RAW = json.loads((ROOT / "data" / "reservations_bank.json").read_text(encoding="utf-8"))
RECORDS = bank.load_all()


DUTY_INF = {r["value"].split("=>")[1].split(" ", 1)[1] for r in RAW["records"]
            if r["family"] == "duty" and not r["value"].startswith(("רשאי", "חייב"))}


def _count(family, level):
    return sum(1 for r in RECORDS if r.family == family and r.level == level)


def _raw(family, level, **kw):
    return [r for r in RAW["records"] if r["family"] == family and r["level"] == level
            and all(r.get(k) == v for k, v in kw.items())]


def test_counts_match_the_document():
    # §2 תנאים: "מתחכם — 30", "הזוי — 116"; רציני - אין
    assert (_count("conditions", "serious"), _count("conditions", "clever"), _count("conditions", "absurd")) == (0, 30, 116)
    # §3 אחרי הסעיף האחרון: 20 / 50 / 100
    assert tuple(_count("after_last", lv) for lv in bank.LEVELS) == (20, 50, 100)
    # §6 תוספת לפועל: 20 / 50 / 100
    assert tuple(_count("verb_modifier", lv) for lv in bank.LEVELS) == (20, 50, 100)
    # §1 החלפת גורם: רציני - 4 קבועים + רשימת השרים; מתחכם - 3 נגזרות + 2 קבועים; הזוי - 106
    assert len(_raw("actor_swap", "serious")) == 5 and len(_raw("actor_swap", "serious", value_list="ministers")) == 1
    assert _count("actor_swap", "clever") == 5 and _count("actor_swap", "absurd") == 106
    # §4 אישור או התייעצות: 5 צורות × גופים - רציני 5 קבועים + השרים, מתחכם 22, הזוי 2 + 106
    assert _count("approval", "serious") == 5 * 6 and len(_raw("approval", "serious", value_list="ministers")) == 5
    assert _count("approval", "clever") == 5 * 22
    assert _count("approval", "absurd") == 5 * (2 + 106)
    forms = {r["template"] for r in RAW["records"] if r["family"] == "approval"}
    assert forms == set(builder.APPROVAL_FORMS) and len(forms) == 5
    # §5 חובה ורשות - רציני בלבד: 24 הקיימות + 14 פעלים בשני הכיוונים (28), ו"חייב" <-> "רשאי" לכל 26 הפעלים
    duty = [r.value for r in RECORDS if r.family == "duty"]
    assert {r.level for r in RECORDS if r.family == "duty"} == {"serious"}
    assert len([d for d in duty if not d.startswith("חייב") and "=>חייב" not in d]) == 24 + 28
    assert len([d for d in duty if d.startswith("חייב") or "=>חייב" in d]) == 2 * 26


def test_all_approved_from_the_session():
    assert all(r["status"] == "approved" and r["source"] == builder.SOURCE for r in RAW["records"])


def test_deleted_records_are_gone():
    ids = {r["id"] for r in RAW["records"]}
    gone = ["actor_swap-001", "actor_swap-002", "actor_swap-007", "actor_swap-008", "actor_swap-009",
            "actor_swap-010", "actor_swap-012", "conditions-001", "conditions-002", "conditions-003",
            "conditions-004", "conditions-013", "conditions-014", "conditions-015",
            "approval-010", "approval-022", "approval-034", "approval-046"]
    assert not ids & set(gone), ids & set(gone)
    for kept in ("actor_swap-003", "actor_swap-006", "conditions-005", "conditions-012", "after_last-001",
                 "after_last-014", "duty-001", "duty-024"):
        assert kept in ids, kept
    values = " ".join(r["value"] for r in RAW["records"]) + json.dumps(RAW["lists"], ensure_ascii=False)
    assert "מועצת הזקנים של השבט הסנאי" not in values


def test_one_shared_list_with_grammatical_gender():
    actors = RAW["lists"]["absurd_actors"]
    assert len(actors) == 106 and len({a["value"] for a in actors}) == 106
    assert all(a["gender"] in ("m", "f") for a in actors)
    # הרשימה לא מועתקת לרשומות - הרשומות מפנות אליה
    listed = {a["value"] for a in actors}
    assert not [r for r in RAW["records"] if r["value"] in listed], "גורם הזוי כרשומה מפורשת - העתק שני"
    users = {r["family"] for r in RAW["records"] if r.get("value_list") == "absurd_actors"}
    assert users == {"actor_swap", "approval"}, users
    # המין מהמסמך: "ועד הדולפינים של הים התיכון (ז)", "מלכת הדבורים (נ)", "הירח המלא (ז)"
    g = {a["value"]: a["gender"] for a in actors}
    assert (g["ועד הדולפינים של הים התיכון"], g["מלכת הדבורים"], g["הירח המלא"], g["הרוח הצפונית"]) == ("m", "f", "m", "f")
    assert [a["value"] for a in actors[25:28]] == ["דמבלדור", "הוועד המנהל של הוגוורטס", "הקוסם הראשי של הממלכה"]
    fixed = {r.value: r.gender for r in RECORDS if r.family == "actor_swap" and r.level != "absurd"}
    assert fixed["הממשלה"] == "f" and fixed["מבקר המדינה"] == "m" and fixed["ועדה ציבורית שימנה {שר}"] == "f"


def test_values_are_verbatim_from_the_document():
    """כל ערך חדש - מופיע במסמך כמו שהוא (הבונה קורא אותו מהמסמך, לא מעתיק ביד)."""
    kept = {f"{f}-{n:03d}" for f, ns in {
        "actor_swap": (3, 4, 5, 6), "conditions": (5, 6, 7, 8, 9, 10, 11, 12),
        "after_last": range(1, 15), "approval": range(1, 49), "duty": range(1, 25)}.items() for n in ns}
    checked = 0
    for r in RAW["records"]:
        if r["id"] in kept or r.get("value_list"):
            continue
        if r["family"] == "duty":
            src, dst = r["value"].split("=>")
            if src.startswith("חייב ") or dst.startswith("חייב "):   # "חייב ל..." - לכל פועל בטבלה
                assert {src.split(" ", 1)[1], dst.split(" ", 1)[1]} <= DUTY_INF, r
            else:
                assert f"{src}↔{dst}" in DOC or f"{dst}↔{src}" in DOC, r
            continue
        text = r["value"] or r["template"]
        if "{committee}" in text:
            continue
        assert text in DOC, (r["id"], text)
        checked += 1
    assert checked > 500, checked
    for a in RAW["lists"]["absurd_actors"]:
        assert f"{a['value']} ({'ז' if a['gender'] == 'm' else 'נ'})" in DOC, a


def test_conditions_rules():
    texts = [r.text("ועדה") for r in RECORDS]
    assert not [t for t in texts if "החל מיום" in t]
    assert not [t for t in texts if "של השנה הבאה" in t or "השנה הבאה" in t]
    first = next(r for r in RECORDS if r.id == "after_last-001")
    assert re.fullmatch(r"תחילה\|תחילתו של חוק זה ביום 1 בינואר 20\d\d\.", first.text()), first.text()


def _approve_all(fn):
    verdicts = {r.id: {"key": r.screen_key, "allowed": True} for r in RECORDS}
    orig = bank._screen_verdicts
    bank._screen_verdicts = lambda: verdicts
    try:
        return fn()
    finally:
        bank._screen_verdicts = orig


def _bill(*sections):
    return ParsedBill(title="חוק הבדיקה", committee="ועדת הכלכלה", warnings=[], sections=[
        BillSection(str(i + 1), margin, BillUnit("lead", "", text), []) for i, (margin, text) in enumerate(sections)])


def test_after_last_no_conflicting_margin():
    bill = _bill(("הגדרות", "בחוק זה, השר - שר הכלכלה."), ("תחילה", "תחילתו של חוק זה ביום פרסומו."))
    items = _approve_all(lambda: families.candidates(bill, "serious", ["after_last"])[0])
    margins = {it.group.split("|", 1)[1] for it in items}
    assert items and "תחילה" not in margins, margins
    assert {"תחולה", "הוראת שעה", "הוראת מעבר"} <= margins, margins


def test_after_last_resolves_minister_and_committee():
    bill = _bill(("סמכות", "שר הכלכלה רשאי להורות על כך."))
    texts = [it.text for it in _approve_all(lambda: families.candidates(bill, "serious", ["after_last"])[0])]
    assert any("שר הכלכלה ידווח לוועדת הכלכלה של הכנסת על יישום חוק זה אחת לשנה." in t for t in texts), texts[:3]
    assert not any("{" in t for t in texts)
    no_committee = ParsedBill(title="חוק", committee="", warnings=[], sections=bill.sections)
    texts = [it.text for it in _approve_all(lambda: families.candidates(no_committee, "serious", ["after_last"])[0])]
    assert texts and not any("ועדת" in t or "{" in t for t in texts)      # {הוועדה} לא נפתרה - לא מופעלת


def test_no_serious_conditions_and_not_waiting():
    bill = _bill(("סמכות", "שר הכלכלה רשאי להורות על כך."))
    items, waiting = _approve_all(lambda: families.candidates(bill, "serious", list(families.FAMILIES)))
    assert not [it for it in items if it.family == "conditions"]
    assert "conditions" not in waiting and "duty" not in waiting, waiting
    items, waiting = _approve_all(lambda: families.candidates(bill, "absurd", list(families.FAMILIES)))
    assert not [it for it in items if it.family == "duty"] and "duty" not in waiting


def test_human_approval_overrides_guard_only_where_marked():
    dolphins = [r for r in RECORDS if "ועד הדולפינים של הים התיכון" in r.text("ועדה")]
    assert len(dolphins) >= 1 + 5 + 3, len(dolphins)             # החלפה, 5 צורות, תנאי/סעיף/תוספת
    assert all(bank.human_approved(r) for r in dolphins)
    # מעבר לדולפינים - רק שתי הרשומות שברק אישר בסבב התיקונים (ב2), ורק לביטוי שבקו האדום
    others = sorted(r.id for r in RECORDS if bank.human_approved(r) and r not in dolphins)
    assert others == ["conditions-128", "verb_modifier-059"], others
    r = dolphins[0]
    blocked = {r.id: {"key": r.screen_key, "allowed": False, "reason": "גוף אמיתי"}}
    assert bank.check(r, blocked) == ""                                  # האישור האנושי גובר
    plain = bank.Record(**{**r.__dict__, "human_approval": None})
    assert bank.check(plain, blocked).startswith("נחסם בשומר 86(ד)(2)")   # בלי סימון - נשאר חסום
    partial = bank.Record(**{**r.__dict__, "human_approval": {"by": "ברק", "at": "2026-09-26"}})
    assert bank.check(partial, blocked).startswith("נחסם")                # בלי "למה" - אינו אישור
    stale = {r.id: {"key": "0" * 16, "allowed": True}}
    assert bank.check(r, stale).startswith("לא עבר")                       # השומר חייב לרוץ על הנוסח
    red = bank.Record(**{**r.__dict__, "value": "ועד הדולפינים של הליכוד"})
    assert bank.check(red, {red.id: {"key": red.screen_key, "allowed": False}}).startswith("קו אדום")
    guards_src = (ROOT / "packages" / "reservations" / "guards.py").read_text(encoding="utf-8")
    assert "human_approval" not in guards_src and "הדולפינים" not in guards_src   # השומר עצמו לא משתנה


def test_blocked_records_stay_blocked():
    """קו אדום - חסום גם כשמאושר, ואינו מגיע לפלט (אישורי הבנק §0.3). שתי הרשומות האלה
    שוחררו רק באישור אנושי מפורש של ברק (סבב התיקונים, ב2 - tests/unit/
    test_human_approval_redline.py); **בלי האישור - חסומות, כמו קודם**."""
    for rid in ("conditions-128", "verb_modifier-059"):
        r = next(r for r in RECORDS if r.id == rid)
        plain = bank.Record(**{**r.__dict__, "human_approval": None})
        assert plain.status == "approved"
        assert bank.check(plain, {r.id: {"key": r.screen_key, "allowed": True}}).startswith("קו אדום"), rid


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_bank_approvals: כל הבדיקות עברו")
