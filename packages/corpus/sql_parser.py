#!/usr/bin/env python3
"""פרסר מכני (לא LLM) לקבצי ה-SQL שכבר נוצרו ע"י tools/load_corpus.py
(פורמט קבוע לגמרי - ראו packages/corpus/db_ingest.py:_lit/_render_*).
נבנה 2026-09-15 כדי לטעון את הקורפוס המלא (187MB) ל-Supabase בלי
להעביר את התוכן דרך קונטקסט LLM - ראו tools/load_corpus_to_supabase_rest.py.

בטיחות: יש בקובץ הזה גם rerender_law_file שממיר בחזרה למחרוזת SQL
זהה - משמש לבדיקת round-trip (parse -> rerender -> diff מול המקור).
לפני כל שימוש בפרסר הזה לטעינה אמיתית, יש להריץ אותה על כל הקבצים
ולוודא 0 כשלים/אי-התאמות (ראו הפונקציה test_roundtrip_all_files
בתחתית הקובץ, או tests/unit/test_sql_parser.py).
"""

import re

NULL_RE = re.compile(r"^-?\d+$")
_TAG_RE = re.compile(r"\$q\d*\$")


class ParseError(Exception):
    pass


def split_top_level_statements(sql_text: str) -> list[str]:
    """מפצל טקסט SQL למשפטים (מסתיימים ב-;), תוך התעלמות מ-; בתוך
    dollar-quote. מחזיר משפטים כולל ה-; הסוגר, בלי שורות ריקות."""
    statements = []
    buf = []
    i = 0
    n = len(sql_text)
    in_quote_tag = None  # e.g. "$q$" or "$q1$"
    while i < n:
        ch = sql_text[i]
        if in_quote_tag is not None:
            if sql_text.startswith(in_quote_tag, i):
                buf.append(in_quote_tag)
                i += len(in_quote_tag)
                in_quote_tag = None
                continue
            buf.append(ch)
            i += 1
            continue
        m = _TAG_RE.match(sql_text, i)
        if m:
            tag = m.group(0)
            in_quote_tag = tag
            buf.append(tag)
            i += len(tag)
            continue
        if ch == ";":
            buf.append(ch)
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        if tail not in ("begin", "commit"):
            raise ParseError(f"שארית לא צפויה בסוף הקובץ (בלי ;): {tail!r}")
        statements.append(tail + ";")
    return statements


def _split_top_level_commas(s: str) -> list[str]:
    parts = []
    buf = []
    depth = 0
    i = 0
    n = len(s)
    in_quote_tag = None
    while i < n:
        ch = s[i]
        if in_quote_tag is not None:
            if s.startswith(in_quote_tag, i):
                buf.append(in_quote_tag)
                i += len(in_quote_tag)
                in_quote_tag = None
                continue
            buf.append(ch)
            i += 1
            continue
        m = _TAG_RE.match(s, i)
        if m:
            tag = m.group(0)
            in_quote_tag = tag
            buf.append(tag)
            i += len(tag)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth -= 1
            buf.append(ch)
            i += 1
            continue
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    last = "".join(buf).strip()
    if last:
        parts.append(last)
    return parts


class Value:
    """עוטף ערך מפורסר + הטקסט הגולמי המקורי שלו (לצורך round-trip
    ולזיהוי is_current_version_subquery בלי לאבד מידע)."""

    __slots__ = ("kind", "value", "raw")

    def __init__(self, kind, value, raw):
        self.kind = kind  # "null" | "bool" | "int" | "str" | "subquery_version_id"
        self.value = value
        self.raw = raw

    def __repr__(self):
        return f"Value({self.kind}, {self.value!r})"


def parse_value(raw: str) -> Value:
    raw = raw.strip()
    if raw == "NULL":
        return Value("null", None, raw)
    if raw == "true":
        return Value("bool", True, raw)
    if raw == "false":
        return Value("bool", False, raw)
    if NULL_RE.match(raw):
        return Value("int", int(raw), raw)
    if raw.startswith("(select max(id) from law_versions where law_id"):
        return Value("subquery_version_id", None, raw)
    m = re.match(r"^(\$q\d*\$)(.*)$", raw, re.DOTALL)
    if m and raw.endswith(m.group(1)):
        tag = m.group(1)
        inner = raw[len(tag) : -len(tag)]
        return Value("str", inner, raw)
    raise ParseError(f"ערך לא מזוהה: {raw!r}")


class ParsedInsert:
    __slots__ = ("table", "columns", "values")

    def __init__(self, table, columns, values):
        self.table = table
        self.columns = columns
        self.values = values  # list[Value]

    def as_dict(self):
        return {col: v for col, v in zip(self.columns, self.values)}


def parse_insert(stmt: str) -> ParsedInsert:
    m = re.match(r"^insert into (\w+) \(([^)]*)\) values \((.*)\);$", stmt, re.DOTALL)
    if not m:
        raise ParseError(f"לא זוהה כ-insert תקני: {stmt[:120]!r}")
    table = m.group(1)
    columns = [c.strip() for c in m.group(2).split(",")]
    values_raw = _split_top_level_commas(m.group(3))
    if len(values_raw) != len(columns):
        raise ParseError(
            f"מספר עמודות ({len(columns)}) != מספר ערכים ({len(values_raw)}) ב-{table}: {stmt[:200]!r}"
        )
    values = [parse_value(v) for v in values_raw]
    return ParsedInsert(table, columns, values)


def parse_update_current_version(stmt: str) -> str:
    """מחזירה את law_id מתוך 'update laws set current_version_id = (...) where id = $q$...$q$;'"""
    m = re.match(
        r"^update laws set current_version_id = \(select max\(id\) from law_versions where law_id = (\$q\d*\$.*?\$q\d*\$)\) where id = (\$q\d*\$.*?\$q\d*\$);$",
        stmt,
    )
    if not m:
        raise ParseError(f"לא זוהה כ-update current_version_id תקני: {stmt[:200]!r}")
    v1 = parse_value(m.group(1))
    v2 = parse_value(m.group(2))
    if v1.value != v2.value:
        raise ParseError(f"law_id לא תואם ב-update: {v1.value!r} != {v2.value!r}")
    return v1.value


def parse_law_file(sql_text: str) -> dict:
    """מפרסת קובץ .sql שלם לחוק אחד. מחזירה dict עם:
    laws_row (dict|None), law_version_row (dict), nodes (list[dict]),
    citations (list[dict]), tokens (list[dict]), update_law_id (str)."""
    statements = split_top_level_statements(sql_text)
    if statements[0] != "begin;":
        raise ParseError(f"הקובץ לא מתחיל ב-begin;: {statements[0]!r}")
    if statements[-1] != "commit;":
        raise ParseError(f"הקובץ לא מסתיים ב-commit;: {statements[-1]!r}")

    laws_row = None
    law_version_row = None
    nodes = []
    citations = []
    tokens = []
    update_law_id = None

    for stmt in statements[1:-1]:
        if stmt.startswith("insert into laws "):
            if laws_row is not None:
                raise ParseError("יותר מ-insert into laws אחד בקובץ")
            parsed = parse_insert(stmt)
            laws_row = parsed.as_dict()
        elif stmt.startswith("insert into law_versions "):
            if law_version_row is not None:
                raise ParseError("יותר מ-insert into law_versions אחד בקובץ")
            parsed = parse_insert(stmt)
            law_version_row = parsed.as_dict()
        elif stmt.startswith("insert into nodes "):
            parsed = parse_insert(stmt)
            nodes.append(parsed.as_dict())
        elif stmt.startswith("insert into law_citations "):
            parsed = parse_insert(stmt)
            citations.append(parsed.as_dict())
        elif stmt.startswith("insert into section_amendment_tokens "):
            parsed = parse_insert(stmt)
            tokens.append(parsed.as_dict())
        elif stmt.startswith("update laws set current_version_id"):
            update_law_id = parse_update_current_version(stmt)
        else:
            raise ParseError(f"סוג statement לא מוכר: {stmt[:120]!r}")

    if law_version_row is None:
        raise ParseError("אין insert into law_versions בקובץ")
    if not nodes:
        raise ParseError("אין שום node בקובץ")
    if update_law_id is None:
        raise ParseError("אין update current_version_id בקובץ")

    return {
        "laws_row": laws_row,
        "law_version_row": law_version_row,
        "nodes": nodes,
        "citations": citations,
        "tokens": tokens,
        "update_law_id": update_law_id,
    }


# --- round-trip (רק לבדיקה עצמית, לא לטעינה) ---


def _rerender_value(v: Value) -> str:
    if v.kind == "subquery_version_id":
        return v.raw
    if v.kind == "null":
        return "NULL"
    if v.kind == "bool":
        return "true" if v.value else "false"
    if v.kind == "int":
        return str(v.value)
    if v.kind == "str":
        return v.raw
    raise ParseError(f"kind לא ידוע: {v.kind}")


def rerender_law_file(parsed: dict) -> str:
    """ההופכי של parse_law_file - לבדיקת round-trip בלבד."""
    lines = ["begin;"]

    def rerender_insert(table, row_dict):
        cols = list(row_dict.keys())
        vals = [_rerender_value(row_dict[c]) for c in cols]
        return f"insert into {table} ({', '.join(cols)}) values ({', '.join(vals)});"

    if parsed["laws_row"] is not None:
        lines.append(rerender_insert("laws", parsed["laws_row"]))
    lines.append(rerender_insert("law_versions", parsed["law_version_row"]))
    for n in parsed["nodes"]:
        lines.append(rerender_insert("nodes", n))
    for c in parsed["citations"]:
        lines.append(rerender_insert("law_citations", c))
    for t in parsed["tokens"]:
        lines.append(rerender_insert("section_amendment_tokens", t))
    # law_id עצמו לא נשמר כ-Value - נשלוף מחדש את המחרוזת dollar-quoted
    # התקנית (זהה תמיד לזו שב-laws_row['id'] או law_version_row['law_id'])
    if parsed["laws_row"] is not None:
        id_raw = parsed["laws_row"]["id"].raw
    else:
        id_raw = parsed["law_version_row"]["law_id"].raw
    lines.append(
        f"update laws set current_version_id = (select max(id) from law_versions where law_id = {id_raw}) where id = {id_raw};"
    )
    lines.append("commit;")
    return "\n".join(lines)
