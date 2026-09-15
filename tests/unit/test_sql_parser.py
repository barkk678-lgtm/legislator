"""בדיקות ל-packages/corpus/sql_parser.py - פרסר מכני ל-SQL שכבר
נוצר ע"י tools/load_corpus.py, נבנה 2026-09-15 לטעינת הקורפוס
המלא ל-Supabase דרך REST (ראו tools/load_corpus_to_supabase_rest.py).

הבדיקה הקריטית האמיתית (round-trip על כל 998 קבצי הקורפוס בפועל,
0 אי-התאמות) רצה חד-פעמית מחוץ ל-CI (הקבצים לא נשמרים בריפו - 187MB).
הבדיקות כאן מכסות את הדקדוק על דוגמאות קטנות: dollar-quote רגיל
ומדורג ($q1$ כשהתוכן מכיל $q$), טקסט עם ; מוטבע, NULL/bool/int,
וה-subquery של law_version_id."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from sql_parser import ParseError, parse_law_file, rerender_law_file  # noqa: E402

CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn

    return deco


SIMPLE_LAW_SQL = (
    "begin;\n"
    'insert into laws (id, full_title, wikitext_title, law_validity_desc, validity_match_method) values ($q$law-1$q$, $q$שם; עם נקודה-פסיק$q$, $q$שם$q$, $q$תקף$q$, $q$exact$q$);\n'
    "insert into law_versions (law_id, wikitext_revision_id, source_ref, as_of) values ($q$law-1$q$, 100, $q$$q$, $q$2026-01-01T00:00:00Z$q$);\n"
    "insert into nodes (law_version_id, id, parent_id, raw_order, node_type, number, margin_title, margin_title_raw, text, text_raw, is_normative, status, numbering_space, raw_amendment_note) values ((select max(id) from law_versions where law_id = $q$law-1$q$), $q$law-1$q$, NULL, 0, $q$law$q$, $q$$q$, NULL, NULL, $q$$q$, $q$$q$, false, $q$active$q$, $q$law$q$, NULL);\n"
    "update laws set current_version_id = (select max(id) from law_versions where law_id = $q$law-1$q$) where id = $q$law-1$q$;\n"
    "commit;"
)


@check("round-trip: חוק פשוט עם ; מוטבע בטקסט")
def _(_):
    parsed = parse_law_file(SIMPLE_LAW_SQL)
    assert parsed["update_law_id"] == "law-1"
    assert len(parsed["nodes"]) == 1
    assert rerender_law_file(parsed) == SIMPLE_LAW_SQL


@check("dollar-quote מדורג: תוכן שמכיל $q$ עצמו")
def _(_):
    sql = (
        "begin;\n"
        "insert into law_versions (law_id, wikitext_revision_id, source_ref, as_of) values "
        "($q1$מכיל $q$ בפנים$q1$, 1, $q$$q$, $q$2026-01-01T00:00:00Z$q$);\n"
        "insert into nodes (law_version_id, id, parent_id, raw_order, node_type, number, margin_title, margin_title_raw, text, text_raw, is_normative, status, numbering_space, raw_amendment_note) values ((select max(id) from law_versions where law_id = $q1$מכיל $q$ בפנים$q1$), $q$n$q$, NULL, 0, $q$law$q$, $q$$q$, NULL, NULL, $q$$q$, $q$$q$, false, $q$active$q$, $q$law$q$, NULL);\n"
        "update laws set current_version_id = (select max(id) from law_versions where law_id = $q1$מכיל $q$ בפנים$q1$) where id = $q1$מכיל $q$ בפנים$q1$;\n"
        "commit;"
    )
    parsed = parse_law_file(sql)
    assert parsed["law_version_row"]["law_id"].value == "מכיל $q$ בפנים"
    assert rerender_law_file(parsed) == sql


@check("NULL/int/bool מפורסרים לערכי Python נכונים")
def _(_):
    parsed = parse_law_file(SIMPLE_LAW_SQL)
    node = parsed["nodes"][0]
    assert node["parent_id"].value is None
    assert node["raw_order"].value == 0
    assert node["is_normative"].value is False


@check("קובץ שלא מתחיל ב-begin; נכשל עם ParseError")
def _(_):
    try:
        parse_law_file("insert into laws (id) values ($q$x$q$);\ncommit;")
        raise AssertionError("היה אמור להיכשל")
    except ParseError:
        pass


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
