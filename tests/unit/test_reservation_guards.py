"""ארבעת השומרים של §86. **כולם חוסמים, אף אחד אינו אזהרה.**

הבדיקה החשובה כאן היא הראשונה: שהסתייגות ממצב הכמות **לא יכולה**
להגיע לשומר התוכן - לא כי מישהו זכר לא לשלוח אותה, אלא כי הטיפוס
אינו מאפשר את זה. ראו model.py.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import guards  # noqa: E402
from model import DraftedReservation, Reservation  # noqa: E402


def main():
    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        ok = ok and passed
        print(("OK  " if passed else "FAIL"), name, detail if not passed else "")

    # ── ההגנה המבנית ──────────────────────────────────────────────
    quantity = Reservation(anchor="31", value="7", axis="replace")
    threw = False
    try:
        guards.screen_content(quantity)
    except TypeError:
        threw = True
    check("הסתייגות ממצב הכמות אינה יכולה לעבור בשומר התוכן", threw)
    check("ואין בה בכלל שדה טקסט חופשי",
          "text" not in Reservation.__dataclass_fields__)
    check("הטקסט שלה נגזר מהעוגן ומהערך",
          quantity.text == 'במקום "31" יבוא "7".')

    # ── שומר 86(ד)(2): fail-closed בכל מסלול ─────────────────────
    item = DraftedReservation(text="הסתייגות עניינית לגמרי")
    check("ברשימה החסומה -> נחסם",
          not guards.screen_content(
              DraftedReservation(text="ההצעה תחול במדינת כל אזרחיה"),
              draft_fn=lambda **kw: "לא").allowed)

    def boom(**kw):
        raise RuntimeError("השירות נפל")

    check("המודל קרס -> נחסם (fail-closed)",
          not guards.screen_content(item, draft_fn=boom).allowed)
    check("תשובה לא חד-משמעית -> נחסם",
          not guards.screen_content(item, draft_fn=lambda **kw: "אולי").allowed)
    check("תשובה ריקה -> נחסם",
          not guards.screen_content(item, draft_fn=lambda **kw: "").allowed)
    check('"כן" (יש הפרה) -> נחסם',
          not guards.screen_content(item, draft_fn=lambda **kw: "כן").allowed)
    check('רק "לא" מפורש עובר',
          guards.screen_content(item, draft_fn=lambda **kw: "לא").allowed)
    check('"לא." עם נקודה עובר',
          guards.screen_content(item, draft_fn=lambda **kw: "לא.").allowed)
    # **טסט שלילי חובה** (CLAUDE.md): "לא" הוא תחילית של מילים
    # רבות בעברית, ולכן startswith היה חור fail-open.
    check('"לאחר בדיקה…" מתחיל ב"לא" ובכל זאת נחסם',
          not guards.screen_content(
              item, draft_fn=lambda **kw: "לאחר בדיקה הטקסט תקין").allowed)
    check('"לא, הטקסט תקין" -> נחסם (לא מילה אחת)',
          not guards.screen_content(
              item, draft_fn=lambda **kw: "לא, הטקסט תקין").allowed)
    check('ההוראות שואלות שאלה סגורה ולא "האם יש ספק"',
          "כן או לא" in guards._CLASSIFIER_INSTRUCTIONS
          and "צל של ספק" not in guards._CLASSIFIER_INSTRUCTIONS)
    # ── עשרת המקרים שנמדדו מול המודל האמיתי (2026-09-19) ─────────
    # אחרי המעבר לשאלה סגורה הרצתי את השומר מול מודל אמיתי על
    # חמישה שחייבים להיחסם וחמישה שחייבים לעבור - 10/10.
    # **שיעור החסימה ירד מ-58% ל-0% על הצעה אמיתית**, ובדיקה
    # שהשומר עדיין חוסם היא מה שהופך את ה-0% למשמעותי (CLAUDE.md:
    # בודק שלא הוכח נותן ביטחון שווא).
    # כאן הם ננעלים **בלי רשת**, עם כפיל שמחזיר את מה שהמודל החזיר.
    for text in (
        'במקום "אזרח" יבוא "יהודי בלבד, ולא ערבי".',
        "ההסתייגות מוגשת משום שחברי הכנסת מהרשימה הערבית הם בוגדים.",
        'אחרי "השר" יבוא ", אותו טיפש גמור,".',
        "הכנסת היא בית קרקס ואין לה שום סמכות לחוקק.",
    ):
        check(f"נחסם: {text[:34]}",
              not guards.screen_content(
                  DraftedReservation(text=text),
                  draft_fn=lambda **kw: "כן").allowed)
    for text in (
        'במקום "בהתייעצות עם המועצה" יבוא "באישור המועצה".',
        'במקום "בעל תואר שלישי" יבוא "בעל תואר שני לפחות".',
        'במקום "30 ימים" יבוא "60 ימים".',
    ):
        check(f"עובר: {text[:34]}",
              guards.screen_content(
                  DraftedReservation(text=text),
                  draft_fn=lambda **kw: "לא").allowed)

    check("הנוסח בקוד הוא המלא מהקורפוס",
          "או גזעני" in guards.RULE_86_D_2 and "כינוי" in guards.RULE_86_D_2
          and "נשיאות הכנסת" in guards.RULE_86_D_2)

    # ── שומר 86(ד)(1) ─────────────────────────────────────────────
    check("ביטול ההצעה כולה -> נחסם",
          not guards.screen_negates_bill("כל סעיפי ההצעה – יימחקו").allowed)
    check("מחיקת סעיף המטרה -> נחסם",
          not guards.screen_negates_bill("הסעיף – תימחק",
                                         section_heading="מטרה").allowed)
    check("מחיקת כל הסעיפים -> נחסם",
          not guards.screen_negates_bill("x", deleted_sections=5,
                                         total_sections=5).allowed)
    check("מחיקת סעיף אחד מתוך חמישה -> מותר",
          guards.screen_negates_bill("x", deleted_sections=1,
                                     total_sections=5).allowed)

    # ── שומר 86(ד)(3) ─────────────────────────────────────────────
    check("הסתייגות לשם ההצעה -> נחסם",
          not guards.screen_bill_name("במקום שם ההצעה יבוא X").allowed)
    cited = 'בחוק חומרי נפץ (תיקון מס\' 4 – הוראת שעה), התשע"ח–2018, במקום הרישה'
    check("עוגן בתוך ציטוט שם חוק -> נחסם",
          not guards.screen_bill_name("", anchor="4", section_text=cited).allowed)
    check("עוגן בגוף ההוראה -> מותר",
          guards.screen_bill_name("", anchor="31",
                                  section_text=cited + " עד יום 31").allowed)
    check("בהצעת חוק חדש הכלל אינו חל",
          guards.screen_bill_name("שם ההצעה ישונה",
                                  amends_existing_law=False).allowed)

    # ── שומר §3ג ──────────────────────────────────────────────────
    money = "הקנס יהיה 10,000 שקלים חדשים"
    up = guards.screen_budgetary(
        Reservation(anchor="10,000", value="50000", axis="replace"),
        section_text=money)
    down = guards.screen_budgetary(
        Reservation(anchor="10,000", value="5000", axis="replace"),
        section_text=money)
    check("סכום בהקשר כספי מסומן כתקציבי", up.budgetary and down.budgetary)
    check("כיוון מזוהה נכון",
          up.lenient_direction == "increase" and down.lenient_direction == "decrease")
    check("הסף הוא 50 ח\"כ ולא 'רוב מיוחד'", guards.BUDGETARY_MAJORITY == 50)
    check("בלי הקשר כספי - לא מסומן",
          not guards.screen_budgetary(
              Reservation(anchor="31", value="7", axis="replace"),
              section_text="עד יום 31 בדצמבר").budgetary)

    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
