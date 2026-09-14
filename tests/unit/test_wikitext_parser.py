"""טסטים ל-parse_wikitext, על fixtures אמיתיים. ראו TASKS.md משימה 3.

היקף: חוק הקייטנות (רישוי ופיקוח) וחוק מאבק בארגוני פשיעה בלבד.
חוק העונשין נשאר ב-fixtures לצורך משימה 7 ואינו נבדק כאן.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from ingest_checks import check_unique_ids  # noqa: E402
from node import effective_source_ref  # noqa: E402
from wikitext_parser import parse_wikitext  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikitext"


def load(slug: str, law_id: str):
    text = (FIXTURES / f"{slug}.wikitext").read_text(encoding="utf-8")
    meta = json.loads((FIXTURES / f"{slug}.meta.json").read_text(encoding="utf-8"))
    source_ref = (
        f"נוסח כפי שהופיע בוויקיטקסט ביום {meta['revision_timestamp'][:10]}"
    )
    return parse_wikitext(text, law_id=law_id, source_ref=source_ref), meta


def find_section(root, number):
    for child in root.children:
        if child.node_type == "section" and child.number == number:
            return child
        found = find_section(child, number)
        if found:
            return found
    return None


def main():
    checks = []

    # --- חוק הקייטנות ---
    kaytanot, kaytanot_meta = load("kaytanot", "kaytanot-1990")
    checks.append(("קייטנות: כל ה-id-ים בעץ ייחודיים", check_unique_ids(kaytanot) == []))
    checks.append(("שורש הקייטנות הוא law, לא נורמטיבי", kaytanot.node_type == "law" and not kaytanot.is_normative))
    checks.append(("8 סעיפים ישירות תחת השורש (אין פרקים)", len(kaytanot.children) == 8))
    checks.append(
        (
            "full_title נלכד מ-{{ח:כותרת}} כולל שנה (en-dash)",
            kaytanot.full_title == 'חוק הקייטנות (רישוי ופיקוח), התש"ן–1990',
        )
    )

    s1 = find_section(kaytanot, "1")
    checks.append(("סעיף 1 כותרת שוליים 'הגדרות'", s1.margin_title == "הגדרות"))
    checks.append(("סעיף 1: רישה + 4 הגדרות = 5 ילדים", len(s1.children) == 5))
    checks.append(("סעיף 1: הילד הראשון הוא paragraph (הרישה)", s1.children[0].node_type == "paragraph"))
    checks.append(
        ("סעיף 1: 4 ההגדרות מסווגות definition לפי סוג=הגדרה", all(c.node_type == "definition" for c in s1.children[1:]))
    )

    s2 = find_section(kaytanot, "2")
    checks.append(("סעיף 2: 3 ילדים (נוסח + 2 הערות)", len(s2.children) == 3))
    checks.append(("סעיף 2: הילד הראשון נורמטיבי", s2.children[0].is_normative is True))
    checks.append(("סעיף 2: שתי ההערות אינן נורמטיביות", all(not c.is_normative for c in s2.children[1:])))

    s6 = find_section(kaytanot, "6")
    checks.append(
        ("סעיף 6: (א), 2 הערות, (ב) - 4 ילדים", len(s6.children) == 4)
    )
    checks.append(("סעיף 6: (א) הוא subsection", s6.children[0].node_type == "subsection" and s6.children[0].number == "(א)"))
    checks.append(("סעיף 6: (ב) הוא subsection", s6.children[3].node_type == "subsection" and s6.children[3].number == "(ב)"))

    s7 = find_section(kaytanot, "7")
    checks.append(("סעיף 7: כותרת שוליים ריקה", not s7.margin_title))
    checks.append(("סעיף 7: status=merged (שולב בחוק אחר)", s7.status == "merged"))
    checks.append(("סעיף 7: תוכנו לא נורמטיבי", all(not c.is_normative for c in s7.children)))

    checks.append(
        (
            "source_ref יושב בשורש בלבד, נכד יורש דרך effective_source_ref",
            s1.source_ref == ""
            and effective_source_ref(kaytanot, s1) == kaytanot.source_ref
            and "2024-09-30" in kaytanot.source_ref,
        )
    )

    # --- חוק מאבק בארגוני פשיעה ---
    crime, crime_meta = load("maavak-birgunei-plisha", "maavak-2003")
    checks.append(("מאבק: כל ה-id-ים בעץ ייחודיים (כולל שתי התוספות)", check_unique_ids(crime) == []))
    chapters = [c for c in crime.children if c.node_type == "chapter"]
    checks.append(("8 פרקים + 2 תוספות = 10 קטע2", len(chapters) == 10))

    section_numbers = []

    def collect_sections(node):
        for c in node.children:
            if c.node_type == "section" and c.numbering_space == "law":
                section_numbers.append(int(c.number))
            collect_sections(c)

    collect_sections(crime)
    checks.append(
        ("מספור סעיפים רץ 1..38 ברצף, לא מתאפס בכל פרק", section_numbers == list(range(1, 39)))
    )

    s1_crime = find_section(crime, "1")
    def1 = s1_crime.children[1]  # ”ארגון פשיעה“
    checks.append(("הגדרת 'ארגון פשיעה' יש לה 4 תת-סעיפי (1)-(4) מקוננים", len(def1.children) == 4))
    checks.append(
        ("תווית (1) מסווגת paragraph למרות קינון תחת definition", all(c.node_type == "paragraph" for c in def1.children))
    )

    s18 = find_section(crime, "18")
    a = s18.children[0]
    a2 = a.children[1]  # (2), פסקה שמכילה עוד רמת (א)/(ב) מקוננת מתחתיה
    checks.append(
        ("סעיף 18: קינון תלת-רמתי (א)->(2)->(א)/(ב), התווית קובעת לא העומק",
         a.node_type == "subsection" and a.number == "(א)"
         and a2.node_type == "paragraph" and a2.number == "(2)"
         and all(c.node_type == "subsection" for c in a2.children)),
    )

    for n in ("36", "37", "38"):
        sec = find_section(crime, n)
        checks.append((f"סעיף {n}: status=merged (שולב בחוק אחר)", sec.status == "merged"))

    schedule1 = next(c for c in chapters if c.number == "תוספת 1")
    item1 = schedule1.children[0]
    item3 = schedule1.children[2]
    checks.append(("תוספת ראשונה, פרט 1: numbering_space=schedule", item1.numbering_space == "schedule"))
    checks.append(("תוספת ראשונה, פרט 1: תוכן נורמטיבי משוחזר (לא ריק)", len(item1.children) == 1))
    checks.append(
        ("תוספת ראשונה, פרט 3 ('(נמחק)'): status=repealed, לא merged", item3.status == "repealed")
    )
    checks.append(
        ("raw_amendment_note נשמר גולמית עבור סעיף עם תיקון", find_section(crime, "19").raw_amendment_note == "תיקון: תשס״ט")
    )

    # id כפול מובנה (2026-09-14) - שחזור סינטטי של הדפוס האמיתי בחוק
    # החוזים (חלק כללי) סעיף 25: תיקון עתידי (תוקף 7.1.2026) גורם
    # לשני {{ח:תת|(א)}} נפרדים באותו סעיף, מובחנים רק ב-{{ח:הערה}}
    # מוטבעת, לא בתווית. ראו _unique_child_id ב-wikitext_parser.py.
    dual_label_wikitext = """{{ח:כותרת|חוק לדוגמה}}
{{ח:סעיף|25|פירוש}}
{{ח:תת|(א)}} {{ח:הערה|(נוסח ישן):}} נוסח א.
{{ח:תת|(א)}} {{ח:הערה|(נוסח חדש):}} נוסח ב.
{{ח:תתת|(1)}} פירוט.
"""
    dual_label_tree = parse_wikitext(dual_label_wikitext, law_id="test-law")
    s25 = dual_label_tree.children[0]
    checks.append(("id כפול מובנה: שני ילדי סעיף 25", len(s25.children) == 2))
    checks.append(("id כפול מובנה: ה-id-ים שונים זה מזה", s25.children[0].id != s25.children[1].id))
    checks.append(("id כפול מובנה: הראשון נשאר בלי סיומת", s25.children[0].id == "test-law/s25/א"))
    checks.append(("id כפול מובנה: השני מקבל סיומת סידורית", s25.children[1].id == "test-law/s25/א-2"))
    checks.append(("id כפול מובנה: check_unique_ids נקי", check_unique_ids(dual_label_tree) == []))
    checks.append(("id כפול מובנה: id_collisions נרשם", dual_label_tree.id_collisions == ["test-law/s25/א -> test-law/s25/א-2"]))
    checks.append(("קייטנות: id_collisions ריק (אין התנגשות אמיתית)", load("kaytanot", "kaytanot-1990")[0].id_collisions == []))
    checks.append(("מאבק: id_collisions ריק (אחרי תיקון ה-id, לא רק אחרי סיומת)", crime.id_collisions == []))

    # id לפי תוכן לרשימה לא-ממוספרת (2026-09-14) - שחזור סינתטי של הדפוס
    # האמיתי בחוק מועצת הצמחים: {{ח:סעיף*}} בלי מספר, {{ח:ת}} יחיד אחריו.
    # כולל שני פריטים עם תוכן זהה ("(נמחק)") - fallback ל-_unique_child_id.
    unnumbered_list_wikitext = """{{ח:כותרת|חוק לדוגמה}}
{{ח:קטע3|תוספת פרק ג|ענף הירקות}}
{{ח:סעיף*}}
{{ח:ת}} אבטיח

{{ח:סעיף*}}
{{ח:ת}} אספרגוס

{{ח:סעיף*}}
{{ח:ת}} {{ח:הערה|(נמחק)}}

{{ח:סעיף*}}
{{ח:ת}} {{ח:הערה|(נמחק)}}
"""
    list_tree = parse_wikitext(unnumbered_list_wikitext, law_id="test-list")
    siman = list_tree.children[0]
    checks.append(("רשימה לא-ממוספרת: 4 סעיפים", len(siman.children) == 4))
    checks.append(("רשימה לא-ממוספרת: id לפי תוכן (לא s/s-2/...)", all(c.id.startswith("test-list/תוספת פרק ג/s-") for c in siman.children)))
    checks.append(("רשימה לא-ממוספרת: אבטיח ≠ אספרגוס (תוכן שונה)", siman.children[0].id != siman.children[1].id))
    checks.append(("רשימה לא-ממוספרת: אותו תוכן ('(נמחק)') -> אותו hash בסיסי, fallback לסיומת", siman.children[3].id.startswith(siman.children[2].id + "-")))
    checks.append(("רשימה לא-ממוספרת: check_unique_ids נקי (fallback עבד)", check_unique_ids(list_tree) == []))
    checks.append(("רשימה לא-ממוספרת: 4 ids נגזרו מתוכן", len(list_tree.content_derived_ids) == 4))
    # יציבות: פרסור שוב מאותו טקסט חייב לתת בדיוק אותם ids (לא hash() מלוח)
    list_tree_again = parse_wikitext(unnumbered_list_wikitext, law_id="test-list")
    checks.append(("רשימה לא-ממוספרת: יציב בין ריצות פרסור", [c.id for c in siman.children] == [c.id for c in list_tree_again.children[0].children]))

    # השלמת תוכן בלי תבנית פותחת (2026-09-14) - שחזור סינתטי של 7 המקרים
    # האמיתיים שנמצאו בסריקת הקורפוס השלם (TASKS.md משימה 7): משפט
    # שנשבר לשתי שורות פיזיות (חוק התחשבנות/הגבלת שכר טרחה/עונש מוות
    # למחבלים), הגדרה/פסקה נוספת בלי תבנית משלה (מכוני כושר/הסכמים
    # קיבוציים/איסור הונאה בכשרות), ותבנית פגומה במקור (מוסדות חינוך
    # תרבותיים ייחודיים - ":ף (4)" במקום "{{ח:תתת|(4)}}"). ברק: "שורה
    # שאינה מתחילה ב-{{ ואינה באזור מוכר מצורפת לצומת הקודם, בלי לנחש
    # מבנה... אבל היא חייבת להיות מסומנת."
    continuation_wikitext = """{{ח:כותרת|חוק לדוגמה}}
{{ח:סעיף|1||}}
{{ח:תת|(א)}} על אף האמור, נדרש אישור לפי סעיף
47א1 למפגש עם שני עורכי דין לכל היותר.
"""
    continuation_tree = parse_wikitext(continuation_wikitext, law_id="test-continuation")
    s1a = continuation_tree.children[0].children[0]
    checks.append(("השלמת נוסח: הטקסט המושלם מחובר (בלי לאבד את השורה השנייה)", "47א1" in s1a.text))
    checks.append(("השלמת נוסח: completed_by_continuation=True", s1a.completed_by_continuation is True))
    checks.append(("השלמת נוסח: root.continuation_completions מכיל את ה-id", continuation_tree.continuation_completions == [s1a.id]))
    checks.append(("השלמת נוסח: text_raw מכיל את שתי השורות", s1a.text_raw.count("\n") == 1))

    # תו פיסוק בודד בשורה נפרדת - רעש עריכה (חוק הנוער), לא תוכן.
    stray_punct_wikitext = """{{ח:כותרת|חוק לדוגמה}}
{{ח:סעיף|1||}}
{{ח:ת}} משפט שכבר הסתיים.
.
"""
    stray_punct_tree = parse_wikitext(stray_punct_wikitext, law_id="test-punct")
    s1_punct = stray_punct_tree.children[0].children[0]
    checks.append(("תו פיסוק בודד: לא מצורף לטקסט", s1_punct.text == "משפט שכבר הסתיים."))
    checks.append(("תו פיסוק בודד: לא מסומן completed_by_continuation", s1_punct.completed_by_continuation is False))

    # קטגוריה עטופה ב-<includeonly> (חוק הרשות לפיתוח ירושלים) - אותה
    # משפחה בדיוק כמו [[קטגוריה:...]] הרגיל, לא תוכן.
    includeonly_wikitext = (
        "{{ח:כותרת|חוק לדוגמה}}\n"
        "{{ח:סעיף|1||}}\n"
        "{{ח:ת}} משפט תקין.\n"
        '<includeonly>{{#ifeq:{{NAMESPACENUMBER}}|0|[[קטגוריה:שלטון מקומי]]}}</includeonly>\n'
    )
    includeonly_tree = parse_wikitext(includeonly_wikitext, law_id="test-includeonly")
    s1_inc = includeonly_tree.children[0].children[0]
    checks.append(("includeonly קטגוריה: לא מצורף לטקסט", s1_inc.text == "משפט תקין."))
    checks.append(("includeonly קטגוריה: לא מסומן completed_by_continuation", s1_inc.completed_by_continuation is False))

    # אזור דילוג (חתימות) לא נדבק בטעות לצומת התוכן שלפניו - זה בדיוק
    # הסיכון שנבדק מול tests/fixtures/wikitext/kaytanot.wikitext ו-maavak
    # (שני fixtures האמת מכילים {{ח:חתימות}} עם שורות חתימה שלא מתחילות
    # ב-{{, ושניהם עדיין עוברים run_sanity_checks נקי - ראו למעלה).
    signatures_wikitext = (
        "{{ח:כותרת|חוק לדוגמה}}\n"
        "{{ח:סעיף|1||}}\n"
        "{{ח:ת}} משפט תקין.\n\n"
        "{{ח:חתימות|התקבל בכנסת.}}\n"
        "* '''ראש הממשלה'''<br>חתימה\n"
        "{{ח:סוגר}}\n"
    )
    signatures_tree = parse_wikitext(signatures_wikitext, law_id="test-signatures")
    s1_sig = signatures_tree.children[0].children[0]
    checks.append(("אזור חתימות: לא נדבק לצומת התוכן שלפניו", s1_sig.text == "משפט תקין."))
    checks.append(("אזור חתימות: לא מסומן completed_by_continuation", s1_sig.completed_by_continuation is False))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
