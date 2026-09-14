-- טוקן "תיקון: ..." שלא הצלחנו לפענח (למשל "תשס״ה־3 תשע״ד" בחוק
-- העמותות - כנראה פסיק חסר במקור) לא קורס יותר את ה-ingest ולא
-- מנוחש - נשמר גולמי ומסומן. ראו packages/corpus/amendment_history.py
-- (AmendmentToken.raw/unparsed) ו-docs/strategy/decisions.md (2026-09-14).
-- raw_token: הטקסט הגולמי של הטוקן, תמיד נשמר (גם כשהפענוח הצליח).
-- is_unparsed: True רק כשלא הצלחנו לפענח בכלל - hebrew_year/ordinal_in_year
-- אז NULL, ואין להסתמך עליהם.
alter table section_amendment_tokens add column raw_token text;
alter table section_amendment_tokens add column is_unparsed boolean not null default false;
