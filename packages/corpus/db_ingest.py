"""אורקסטרציית ingest: שליפה (עם retry לרשת), פרסור, בדיקות שפיות,
ובניית תוכנית SQL לכתיבה ל-DB. ראו docs/strategy/decisions.md
לתוכנית המלאה שאושרה (2026-09-13), ו-CLAUDE.md "ה-ingest שומר עובדות".

מפריד לגמרי בין שני סוגי כשל, כפי שהוחלט - לא מנחש/מאחד ביניהם:
- כשל רשת (NetworkIngestError) - חולף מטבעו, עד 3 ניסיונות שליפה
  עם השהיה גדלה (ראו fetch_with_retry).
- כשל פרסור/בדיקת שפיות (SanityIngestError) - לא חולף (תבנית לא
  מוכרת/תוכן חלקי/עץ ריק), אפס ניסיונות חוזרים.

לא מבצעת שום כתיבה בפועל ל-DB - בונה טקסט SQL בלבד (כמו
packages/render בונה docx בלי לדעת איך הוא יישלח הלאה). מי שמריץ
את ה-SQL בפועל הוא ריכוז נפרד ומכוון - היום (2026-09-13) דרך
mcp Supabase, כי הסביבה הזו לא מחזיקה credentials/חיבור Postgres
ישיר; בעתיד (ingest מתוזמן, משימה 7) דרך psycopg + DATABASE_URL
אמיתי בסביבת ריצה שכן יש לה את זה.

סדר ה-INSERT קבוע ומכוון (ראו supabase/migrations/..._corpus_schema_v1.sql):
1. laws (רק אם חדש, current_version_id=NULL)
2. law_versions
3. nodes (pre-order - הורה תמיד לפני ילד, כדי שה-FK העצמי יתקיים)
4. law_citations, section_amendment_tokens
5. UPDATE laws SET current_version_id - אחרון, בתוך אותה טרנזקציה.
כל זה עטוף ב-BEGIN/COMMIT יחיד - כשל בכל שלב = rollback מלא, לא
מצב ביניים.
"""

import time
from dataclasses import dataclass

from amendment_history import (
    CitationEntry,
    parse_amendment_note,
    parse_citation_registry,
)
from ingest_checks import run_sanity_checks
from node import LegislativeNode
from wikitext_client import extract_revision_id, extract_revision_timestamp, extract_wikitext_body, fetch_wikitext
from wikitext_parser import parse_wikitext


class NetworkIngestError(Exception):
    """כשל שליפה מהרשת אחרי מיצוי הניסיונות - קטגוריית retry."""


class SanityIngestError(Exception):
    """כשל פרסור/בדיקת שפיות - קטגוריית no-retry. הודעת החריגה היא
    רשימת הבעיות המחוברת מ-ingest_checks.run_sanity_checks."""


@dataclass
class IngestPlan:
    law_id: str
    wikitext_revision_id: int
    as_of: str
    source_ref: str
    sql: str
    section_count: int
    node_count: int
    citation_count: int
    token_count: int
    total_text_chars: int  # סכום len(node.text) על כל העץ - בסיס אמיתי להערכת עלות embeddings
    id_collisions: list[str]  # ראו node.LegislativeNode.id_collisions - לא שגיאה (העץ
    # תקין), אבל שכיחות גבוהה בקורפוס המלא היא סימן לדפוס לא-מזוהה (ברק, 2026-09-14)


def fetch_with_retry(
    wikitext_title: str,
    *,
    max_attempts: int = 3,
    backoff_seconds: tuple = (5, 15, 45),
    fetch=fetch_wikitext,
) -> dict:
    """שולפת עם עד max_attempts ניסיונות, השהיה גדלה בין ניסיונות -
    כשל רשת (timeout/חיבור/HTTP) הוא חולף מטבעו, בניגוד לכשל פרסור.
    fetch ניתן להזרקה (ברירת מחדל: wikitext_client.fetch_wikitext
    האמיתי) כדי לאפשר בדיקות בלי רשת - ראו tests/unit/test_db_ingest.py."""
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fetch(wikitext_title)
        except (OSError, RuntimeError) as exc:
            # OSError מכסה urllib.error.URLError/HTTPError (תתי-מחלקות
            # שלו) וטיימאאוטים; RuntimeError הוא מה ש-wikitext_client._get
            # זורקת אחרי מיצוי ניסיונות ה-429 הפנימיים שלה. שתיהן חולפות
            # מטבען - כשל פרסור נזרק כ-ValueError/SanityIngestError,
            # לא נתפס כאן ולא מקבל retry.
            last_error = exc
            if attempt < max_attempts - 1:
                time.sleep(backoff_seconds[attempt])
    raise NetworkIngestError(
        f"נכשל אחרי {max_attempts} ניסיונות שליפה של {wikitext_title!r}: {last_error}"
    ) from last_error


def build_ingest_plan(
    law_id: str,
    wikitext_title: str,
    *,
    source_ref: str,
    law_is_new: bool,
    fetch=fetch_with_retry,
    validity: "ValidityMatch | None" = None,
) -> IngestPlan:
    """בונה תוכנית ingest מלאה (SQL, לא מבוצע) לחוק בודד. זורקת
    NetworkIngestError או SanityIngestError לפי הקטגוריה - שתיהן לא
    כותבות שום דבר ל-DB (הבנייה כולה בזיכרון, לפני שנפתחת טרנזקציה).

    validity (אופציונלי, ראו knesset_odata.ValidityMatch) - הסיווג
    מול KNS_IsraelLaw, אם קיים. לא נשלף כאן (הפרדת מקורות רשת - ראו
    knesset_odata.py) - האחריות על הקורא לבדוק should_ingest *לפני*
    קריאה לפונקציה הזו (סינון, לא רק תיעוד); הפרמטר הזה קובע רק מה
    נכתב ל-laws.law_validity_desc/validity_match_method בפועל."""
    export = fetch(wikitext_title)
    export_xml = export["export_xml"]
    wikitext = extract_wikitext_body(export_xml)
    as_of = extract_revision_timestamp(export_xml)
    revision_id = extract_revision_id(export_xml)

    tree = parse_wikitext(wikitext, law_id=law_id, source_ref=source_ref, as_of=as_of)

    problems = run_sanity_checks(wikitext, tree)
    if problems:
        raise SanityIngestError("; ".join(problems))

    citations = parse_citation_registry(wikitext)

    sql = _render_transaction_sql(
        law_id=law_id,
        wikitext_title=wikitext_title,
        revision_id=revision_id,
        source_ref=source_ref,
        as_of=as_of,
        tree=tree,
        citations=citations,
        law_is_new=law_is_new,
        validity=validity,
    )

    return IngestPlan(
        law_id=law_id,
        wikitext_revision_id=revision_id,
        as_of=as_of,
        source_ref=source_ref,
        sql=sql,
        section_count=_count_node_type(tree, "section"),
        node_count=_count_all(tree),
        citation_count=len(citations),
        token_count=sum(
            len(parse_amendment_note(n.raw_amendment_note).tokens)
            for n in _walk(tree)
            if n.raw_amendment_note
        ),
        total_text_chars=sum(len(n.text) for n in _walk(tree)),
        id_collisions=tree.id_collisions,
    )


def record_failure_sql(law_id: str, category: str, message: str) -> str:
    """סטטמנט עדכון נפרד, לא בתוך הטרנזקציה שנכשלה - מריצים אותו
    *אחרי* ה-rollback, כדי שהתיעוד עצמו לא יימחק יחד עם הכשל."""
    return (
        f"update laws set "
        f"last_ingest_error = {_lit(f'[{category}] {message}')}, "
        f"last_ingest_attempted_at = now() "
        f"where id = {_lit(law_id)};"
    )


# --- בניית ה-SQL ---


def _render_transaction_sql(
    *,
    law_id: str,
    wikitext_title: str,
    revision_id: int,
    source_ref: str,
    as_of: str,
    tree: LegislativeNode,
    citations: list[CitationEntry],
    law_is_new: bool,
    validity: "ValidityMatch | None" = None,
) -> str:
    statements: list[str] = ["begin;"]

    if law_is_new:
        if validity is not None:
            statements.append(
                "insert into laws (id, full_title, wikitext_title, law_validity_desc, validity_match_method) values "
                f"({_lit(law_id)}, {_lit(tree.full_title or law_id)}, {_lit(wikitext_title)}, "
                f"{_lit(validity.law_validity_desc)}, {_lit(validity.match_method)});"
            )
        else:
            statements.append(
                "insert into laws (id, full_title, wikitext_title) values "
                f"({_lit(law_id)}, {_lit(tree.full_title or law_id)}, {_lit(wikitext_title)});"
            )

    # אין RETURNING/\gset בכוונה - execute_sql (mcp Supabase) מריצה
    # מחרוזת SQL אחת כטקסט, לא psql אינטראקטיבי, ואין לנו משתנה session
    # לשמור בו את ה-id. כל שאר הסטטמנטים בטרנזקציה הזו מוצאים את
    # הגרסה מחדש דרך (select max(id) from law_versions where law_id=...)
    # - תקין כי id הוא IDENTITY עולה, ואין ingest מקבילי לאותו חוק
    # בתוך אותה טרנזקציה (הנחה מפורשת, לא נאכפת ב-DB - ingest של אותו
    # law_id לא רץ פעמיים בו-זמנית).
    statements.append(
        "insert into law_versions (law_id, wikitext_revision_id, source_ref, as_of) "
        f"values ({_lit(law_id)}, {revision_id}, {_lit(source_ref)}, {_lit(as_of)});"
    )

    statements += _render_nodes_sql(law_id, tree)
    statements += _render_citations_sql(law_id, citations)
    statements += _render_tokens_sql(law_id, tree)

    statements.append(
        "update laws set current_version_id = (select max(id) from law_versions where law_id = "
        f"{_lit(law_id)}) where id = {_lit(law_id)};"
    )
    statements.append("commit;")
    return "\n".join(statements)


def _render_nodes_sql(law_id: str, tree: LegislativeNode) -> list[str]:
    statements = []

    def walk(node: LegislativeNode, parent_id: str | None, order: int):
        statements.append(
            "insert into nodes (law_version_id, id, parent_id, raw_order, node_type, number, "
            "margin_title, margin_title_raw, text, text_raw, is_normative, status, "
            "numbering_space, raw_amendment_note) values ("
            f"(select max(id) from law_versions where law_id = {_lit(law_id)}), "
            f"{_lit(node.id)}, {_lit(parent_id)}, {order}, {_lit(node.node_type)}, "
            f"{_lit(node.number)}, {_lit(node.margin_title)}, {_lit(node.margin_title_raw)}, "
            f"{_lit(node.text)}, {_lit(node.text_raw)}, {_bool(node.is_normative)}, "
            f"{_lit(node.status)}, {_lit(node.numbering_space)}, {_lit(node.raw_amendment_note)});"
        )
        for i, child in enumerate(node.children):
            walk(child, node.id, i)

    walk(tree, None, 0)
    return statements


def _render_citations_sql(law_id: str, citations: list[CitationEntry]) -> list[str]:
    statements = []
    for c in citations:
        statements.append(
            "insert into law_citations (law_version_id, hebrew_year, ordinal_in_year, page, "
            "name, amendment_number) values ("
            f"(select max(id) from law_versions where law_id = {_lit(law_id)}), "
            f"{_lit(c.hebrew_year)}, {c.ordinal_in_year}, {_lit(c.page)}, {_lit(c.name)}, "
            f"{_lit(c.amendment_number)});"
        )
    return statements


def _render_tokens_sql(law_id: str, tree: LegislativeNode) -> list[str]:
    statements = []
    for node in _walk(tree):
        if not node.raw_amendment_note:
            continue
        parsed = parse_amendment_note(node.raw_amendment_note)
        for order, token in enumerate(parsed.tokens):
            statements.append(
                "insert into section_amendment_tokens (law_version_id, node_id, token_order, "
                "hebrew_year, ordinal_in_year, is_legacy) values ("
                f"(select max(id) from law_versions where law_id = {_lit(law_id)}), "
                f"{_lit(node.id)}, {order}, {_lit(token.hebrew_year)}, "
                f"{token.ordinal_in_year if token.ordinal_in_year is not None else 'NULL'}, "
                f"{_bool(token.is_legacy)});"
            )
    return statements


def _walk(node: LegislativeNode):
    yield node
    for child in node.children:
        yield from _walk(child)


def _count_node_type(node: LegislativeNode, node_type: str) -> int:
    return sum(1 for n in _walk(node) if n.node_type == node_type)


def _count_all(node: LegislativeNode) -> int:
    return sum(1 for _ in _walk(node))


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _lit(value) -> str:
    """מייצרת literal SQL בטוח לערך טקסט/None - dollar-quoting במקום
    escaping של גרשיים, כי הטקסט המשפטי מכיל גרשיים/גרשי-כפולות (״/׳)
    בשפע ו-escaping ידני הוא מקור שגיאות. בוחרת תג שלא מופיע בתוכן."""
    if value is None:
        return "NULL"
    text = str(value)
    tag = "$q$"
    suffix = 0
    while tag in text:
        suffix += 1
        tag = f"$q{suffix}$"
        if suffix > 100:
            raise ValueError("לא נמצא תג dollar-quote פנוי - תוכן חריג")
    return f"{tag}{text}{tag}"
