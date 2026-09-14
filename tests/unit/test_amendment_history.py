"""בדיקות ל-amendment_history.py (TASKS.md משימה 7א).

אימות צולב מול מקור עצמאי: כל הבדיקות שמפענחות טוקן "תיקון: ..." בפועל
מריצות אותן גם דרך resolve_amendment_tokens מול הרשימה הכרונולוגית
שבפתיח tests/fixtures/wikitext/penal.wikitext (חוק העונשין) - לא רק
בודקות שהפרסור "נראה סביר".

מקרה בוחן מרכזי: סעיף 34כד (ראו TASKS.md 7א) + שני סעיפים נוספים
(1, ו-15) עם טוקנים אחרים משנים אחרות.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from amendment_history import (  # noqa: E402
    parse_amendment_note,
    parse_citation_registry,
    resolve_amendment_tokens,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikitext"
_PENAL_WIKITEXT = (FIXTURES / "penal.wikitext").read_text(encoding="utf-8")
_REGISTRY = parse_citation_registry(_PENAL_WIKITEXT)


def main():
    checks = []

    # --- parse_amendment_note: מבנה טוקנים ---

    note_34kd = (
        "תיקון: [1939], [תשי״ז], [תשל״ה], תשמ״ח־3, תשנ״ד־3, תשנ״ה־4, "
        "תשנ״ו־6, תשנ״ח־2|אחר=[א/5]"
    )
    parsed_34kd = parse_amendment_note(note_34kd)
    checks.append(("34כד: 8 טוקני תיקון", len(parsed_34kd.tokens) == 8))
    checks.append(("34כד: שלושת הראשונים legacy (סוגריים)", all(t.is_legacy for t in parsed_34kd.tokens[:3])))
    checks.append(("34כד: חמשת האחרונים לא legacy", not any(t.is_legacy for t in parsed_34kd.tokens[3:])))
    checks.append(("34כד: אחר= נשמר גולמי בלי פענוח", parsed_34kd.other_raw == "[א/5]"))
    checks.append(
        (
            "34כד: תשנ״ד סיומת ־3 מזוהה במפורש",
            parsed_34kd.tokens[4].hebrew_year == "תשנ״ד"
            and parsed_34kd.tokens[4].ordinal_in_year == 3,
        )
    )

    note_bare_year = "תיקון: תשנ״ד־3, תשנ״ח־2, תשס״ג־6, תשס״ז, תש״ע־6"
    parsed_bare = parse_amendment_note(note_bare_year)
    checks.append(("סעיף 15: 5 טוקנים", len(parsed_bare.tokens) == 5))
    checks.append(
        (
            "סעיף 15: טוקן בלי סיומת (תשס״ז) -> ordinal_in_year=None, לא מנוחש",
            parsed_bare.tokens[3].hebrew_year == "תשס״ז"
            and parsed_bare.tokens[3].ordinal_in_year is None,
        )
    )

    checks.append(("None -> אין טוקנים, לא שגיאה", parse_amendment_note(None).tokens == ()))

    # --- parse_citation_registry + resolve_amendment_tokens: אימות צולב ---

    checks.append(("הרשימה הכרונולוגית לא ריקה", len(_REGISTRY) > 100))

    # המקרה המרכזי: תשנ״ד־3 -> "תיקון מס' 39 (חלק מקדמי וחלק כללי)" -
    # הרפורמה הגדולה הידועה בחלק המקדמי, תואמת את הטווח הרחב של סעיפים
    # שנושאים את אותו תיקון (1 עד 20+ ברצף בפועל בפיקסצ'ר).
    resolved_34kd = resolve_amendment_tokens(parsed_34kd.tokens, _REGISTRY)
    by_year = {tok.hebrew_year: cands for tok, cands in resolved_34kd if not tok.is_legacy}
    checks.append(
        (
            "תשנ״ד־3 נפתר חד-משמעית לתיקון מס' 39",
            len(by_year["תשנ״ד"]) == 1 and by_year["תשנ״ד"][0].amendment_number == "39",
        )
    )
    checks.append(
        (
            "תשנ״ו־6 נפתר חד-משמעית (ת\"ט, לא תיקון ממוספר - גם זה תקין)",
            len(by_year["תשנ״ו"]) == 1 and by_year["תשנ״ו"][0].amendment_number is None,
        )
    )
    checks.append(
        (
            "תשנ״ח־2 נפתר חד-משמעית לתיקון מס' 52",
            len(by_year["תשנ״ח"]) == 1 and by_year["תשנ״ח"][0].amendment_number == "52",
        )
    )

    # legacy (טרום-1977): לא תמיד חד-משמעי - התיקוני-מקור לא נושאים
    # סיומת מספרית, ולפעמים יש כמה ציטוטים לאותה שנה (תשי״ז: 5 מועמדים
    # בפועל). הפרסר לא ינחש - הוא מחזיר את כולם.
    legacy_by_year = {tok.hebrew_year: cands for tok, cands in resolved_34kd if tok.is_legacy}
    checks.append(("legacy [1939] נפתר חד-משמעית", len(legacy_by_year["1939"]) == 1))
    checks.append(
        (
            "legacy [תשי״ז] דו-משמעי במקור עצמו - לא מנוחש",
            len(legacy_by_year["תשי״ז"]) > 1,
        )
    )

    # סעיף 15: טוקן בלי סיומת (תשס״ז) לא מנוחש כציטוט ראשון - מוחזרים
    # כל מועמדי תשס״ז (יש בפועל יותר מאחד בפיקסצ'ר).
    resolved_bare = resolve_amendment_tokens(parsed_bare.tokens, _REGISTRY)
    bare_tsz_candidates = next(cands for tok, cands in resolved_bare if tok.hebrew_year == "תשס״ז")
    checks.append(
        (
            "סעיף 15 (תשס״ז בלי סיומת) לא נבחר מועמד יחיד בשקט",
            len(bare_tsz_candidates) > 1,
        )
    )

    # סעיף 1: כל החוק (חלק מקדמי) נושא תשנ״ד־3 - עוד אימות לאותו תיקון.
    note_section1 = "תיקון: תשנ״ד־3"
    parsed_1 = parse_amendment_note(note_section1)
    resolved_1 = resolve_amendment_tokens(parsed_1.tokens, _REGISTRY)
    checks.append(
        (
            "סעיף 1 (תשנ״ד־3) עקבי עם סעיף 34כד - אותו תיקון מס' 39",
            resolved_1[0][1][0].amendment_number == "39",
        )
    )

    # --- טוקן פגום (2026-09-14) - לא קורס, נשמר גולמי (חוק העמותות) ---
    note_malformed = "תיקון: תשנ״ו, תשס״ה־2, תשס״ה־3 תשע״ד"
    parsed_malformed = parse_amendment_note(note_malformed)
    checks.append(("טוקן פגום: לא קורס, 3 טוקנים", len(parsed_malformed.tokens) == 3))
    checks.append(("טוקן פגום: הטוקן השלישי מסומן unparsed", parsed_malformed.tokens[2].unparsed is True))
    checks.append(("טוקן פגום: hebrew_year=None (לא מנוחש)", parsed_malformed.tokens[2].hebrew_year is None))
    checks.append(("טוקן פגום: raw נשמר גולמי", parsed_malformed.tokens[2].raw == "תשס״ה־3 תשע״ד"))
    checks.append(("טוקן פגום: שני הטוקנים התקינים לא הושפעו", parsed_malformed.tokens[1].hebrew_year == "תשס״ה" and parsed_malformed.tokens[1].ordinal_in_year == 2))
    resolved_malformed = resolve_amendment_tokens(parsed_malformed.tokens, _REGISTRY)
    checks.append(("טוקן פגום: resolve לא קורס, 0 מועמדים", resolved_malformed[2][1] == ()))
    checks.append(("טוקן תקין: raw נשמר גם בהצלחה", parsed_malformed.tokens[0].raw == "תשנ״ו"))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
