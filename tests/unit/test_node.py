"""בדיקת שפיות ל-LegislativeNode. ראו TASKS.md משימה 2."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from node import LegislativeNode, effective_source_ref  # noqa: E402


def main():
    child = LegislativeNode(
        id="kaytanot-1990/s1/a/1",
        node_type="definition",
        number="(1)",
        margin_title=None,
        text='"ארגון נוער או תנועת נוער" – ...',
    )
    root = LegislativeNode(
        id="kaytanot-1990/s1",
        node_type="section",
        number="1",
        margin_title="הגדרות",
        text="",
        children=[child],
        source_ref='ס"ח התש"ן, עמ\' 155',
    )
    note = LegislativeNode(
        id="kaytanot-1990/s6/note1",
        node_type="subsection",
        number="",
        margin_title=None,
        text="ראו תקנות הקייטנות (רישוי ופיקוח), התשנ\"ד–1994.",
        is_normative=False,
    )
    merged_section = LegislativeNode(
        id="kaytanot-1990/s7",
        node_type="section",
        number="7",
        margin_title="",
        text="",
        status="merged",
    )
    section_34kd = LegislativeNode(
        id="penal-1977/s34kd",
        node_type="section",
        number="34כד",
        margin_title="הגדרות",
        margin_title_raw=None,
        text="",
        raw_amendment_note=(
            "תיקון: [1939], [תשי״ז], [תשל״ה], תשמ״ח־3, תשנ״ד־3, "
            "תשנ״ה־4, תשנ״ו־6, תשנ״ח־2|אחר=[א/5]"
        ),
    )
    comparison_table_item = LegislativeNode(
        id="penal-1977/comparison-table/a",
        node_type="section",
        number="א",
        margin_title="",
        text="",
        numbering_space="comparison-table",
    )
    chapter = LegislativeNode(
        id="penal-1977/part-a",
        node_type="part",
        number="א",
        margin_title="חלק א׳: כללי",
        text="",
    )
    siman = LegislativeNode(
        id="penal-1977/ch-c/siman-a",
        node_type="siman",
        number="א",
        margin_title="סימן א׳: הוראות כלליות",
        text="",
    )
    section_with_nested_title = LegislativeNode(
        id="penal-1977/s34kg",
        node_type="section",
        number="34כג",
        margin_title="כלליות החלק המקדמי והחלק הכללי",
        margin_title_raw=(
            "כלליות {{ח:פנימי|חלק 0|החלק המקדמי}} {{ח:פנימי|חלק א|והחלק הכללי}}"
        ),
        text="",
    )

    # עץ קטן לבדיקת effective_source_ref: law -> chapter -> section
    leaf = LegislativeNode(
        id="kaytanot-1990/s1/def1", node_type="definition", number="(1)",
        margin_title=None, text="", text_raw='”ילד“ – ...',
    )
    section = LegislativeNode(
        id="kaytanot-1990/s1", node_type="section", number="1",
        margin_title="הגדרות", text="", children=[leaf],
    )
    law_root = LegislativeNode(
        id="kaytanot-1990", node_type="law", number="", margin_title=None,
        text="", children=[section],
        source_ref='ס"ח התש"ן, עמ\' 155 (נוסח כפי שהופיע בוויקיטקסט ביום 2024-09-30)',
        is_normative=False,
    )

    checks = [
        ("root.number הוא מספר החוק, לא מספר הצעת החוק", root.number == "1"),
        ("children מכיל את הבן", root.children == [child]),
        ("source_ref ברירת מחדל ריקה", child.source_ref == ""),
        ("is_normative ברירת מחדל True", child.is_normative is True),
        ("הערת עורך מסומנת is_normative=False", note.is_normative is False),
        ("status ברירת מחדל active", child.status == "active"),
        ("סעיף ששולב מסומן status=merged", merged_section.status == "merged"),
        ("raw_amendment_note ברירת מחדל None", child.raw_amendment_note is None),
        (
            "raw_amendment_note נשמר גולמית בלי פענוח",
            section_34kd.raw_amendment_note is not None
            and "34כד" not in section_34kd.raw_amendment_note
            and "תשנ״ח־2" in section_34kd.raw_amendment_note,
        ),
        ("numbering_space ברירת מחדל law", child.numbering_space == "law"),
        (
            "פריט בלוח השוואה מסומן numbering_space=comparison-table",
            comparison_table_item.numbering_space == "comparison-table",
        ),
        ("node_type תומך ב-part", chapter.node_type == "part"),
        ("node_type תומך ב-siman", siman.node_type == "siman"),
        (
            "margin_title_raw שומר את הוויקיטקסט הגולמי כשיש תבניות מקוננות",
            section_with_nested_title.margin_title == "כלליות החלק המקדמי והחלק הכללי"
            and "{{ח:פנימי" in section_with_nested_title.margin_title_raw,
        ),
        ("margin_title_raw ברירת מחדל None", child.margin_title_raw is None),
        ("text_raw ברירת מחדל ריק", child.text_raw == ""),
        ("text_raw שומר את הטקסט לפני נרמול", leaf.text_raw == '”ילד“ – ...'),
        ("שורש ה-law מסומן is_normative=False", law_root.is_normative is False),
        (
            "effective_source_ref על השורש עצמו מחזיר את המחרוזת שהוגדרה בו",
            effective_source_ref(law_root, law_root) == law_root.source_ref,
        ),
        (
            "effective_source_ref על נכד ירושה מהשורש, בלי להעתיק אליו",
            section.source_ref == "" and leaf.source_ref == ""
            and effective_source_ref(law_root, leaf) == law_root.source_ref
            and effective_source_ref(law_root, section) == law_root.source_ref,
        ),
    ]
    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
