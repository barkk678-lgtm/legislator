"""טסטים ל-ח:קטע4/ח:קטע5 (ברק, 2026-09-16 - ראו TASKS.md).

סריקת קורפוס-שלם (1,008 כותרות מועמדות) חשפה שני דפוסים שונים:
ח:קטע4 עם ארגומנט ראשון ריק = הערה (90.3% מהמופעים, ההנחה המקורית
הנכונה לרובם) - מדולג. ח:קטע4 עם ארגומנט ראשון לא ריק = "סימן משנה",
רמת מבנה אמיתית (9.7% מהמופעים) - היה מדולג בטעות, עכשיו ממופה.
ח:קטע5 (זהה מילה-במילה ל-קטע4 בוויקי) הוא **תמיד** מבנה (10/10
מופעים בקורפוס-שלם) - לא היה ממופה בכלל, עכשיו ממופה תמיד."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from ingest_checks import run_sanity_checks  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402

CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn

    return deco


NOTE_WIKITEXT = """{{ח:סעיף|1|כותרת}}
נוסח כלשהו.
{{ח:קטע4||(הערה כלשהי על סעיף 1)}}
{{ח:סעיף|2|כותרת שנייה}}
נוסח נוסף.
"""


@check("ח:קטע4 עם ארגומנט ראשון ריק - מדולג (דפוס הערה, ללא שינוי מהתנהגות קודמת)")
def _(_):
    tree = parse_wikitext(NOTE_WIKITEXT, law_id="test-note")
    types = [c.node_type for c in tree.children]
    assert "sub_siman" not in types, f"לא אמור להיות sub_siman: {types}"
    assert len(tree.children) == 2, f"רק 2 סעיפים, בלי צומת לקטע4: {types}"


STRUCTURAL_WIKITEXT = """{{ח:קטע3|סימן א|סימן א׳: כללי}}
{{ח:סעיף|1|כותרת}}
נוסח כלשהו.
{{ח:קטע4|סימן א משנה א|סימן משנה א׳: פרטים}}
{{ח:סעיף|2|כותרת שנייה}}
נוסח נוסף.
{{ח:קטע5|סימן א משנה ב|תת-סימן משנה ב׳}}
{{ח:סעיף|3|כותרת שלישית}}
נוסח שלישי.
"""


@check("ח:קטע4 עם עוגן לא ריק - נהיה sub_siman, מקנן נכון תחת סימן")
def _(_):
    tree = parse_wikitext(STRUCTURAL_WIKITEXT, law_id="test-struct")
    siman = tree.children[0]
    assert siman.node_type == "siman"
    section_1 = [c for c in siman.children if c.node_type == "section" and c.number == "1"]
    assert len(section_1) == 1, "סעיף 1 (לפני קטע4) אמור להיות ילד ישיר של הסימן"
    sub_simans = [c for c in siman.children if c.node_type == "sub_siman"]
    assert len(sub_simans) == 2, f"שני sub_siman כאחים תחת הסימן (קטע4 וקטע5 באותה רמה): {[c.node_type for c in siman.children]}"
    assert sub_simans[0].margin_title == "סימן משנה א׳: פרטים"
    section_2 = [c for c in sub_simans[0].children if c.node_type == "section" and c.number == "2"]
    assert len(section_2) == 1, "סעיף 2 אמור להיות ילד של ה-sub_siman (קטע4), לא אח שלו"


@check("ח:קטע5 - sub_siman כאח של קטע4 הקודם (אותה רמה מבנית, לא ילד שלו) - תואם למבנה שנמצא בחוק אמיתי")
def _(_):
    tree = parse_wikitext(STRUCTURAL_WIKITEXT, law_id="test-struct2")
    siman = tree.children[0]
    sub_simans = [c for c in siman.children if c.node_type == "sub_siman"]
    assert sub_simans[1].margin_title == "תת-סימן משנה ב׳"
    section_3 = [c for c in sub_simans[1].children if c.node_type == "section" and c.number == "3"]
    assert len(section_3) == 1, "סעיף 3 אמור להיות ילד של קטע5, לא של קטע4 הקודם"


@check("run_sanity_checks לא מתלונן על ח:קטע5 (היה 'תבנית לא מוכרת' לפני התיקון)")
def _(_):
    tree = parse_wikitext(STRUCTURAL_WIKITEXT, law_id="test-sanity")
    problems = run_sanity_checks(STRUCTURAL_WIKITEXT, tree)
    assert problems == [], f"לא אמורות להיות בעיות שפיות: {problems}"


def main():
    failed = 0
    for name, fn in CHECKS:
        try:
            fn(None)
            print(f"OK   {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
