-- מנסח החקיקה — סכמת קורפוס ראשונית (1.1), אחרי 4 תיקוני ברק:
-- 1) law_versions.law_id: ON DELETE RESTRICT (לא cascade) - מחיקת חוק
--    לא תהרוס גרסאות בשקט. ניקוי גרסאות ישנות הוא מדיניות נפרדת,
--    שטרם נבנתה, ותחייב בדיקה מפורשת שאין טיוטה מצביעה על הגרסה
--    לפני שמותר למחוק אותה.
-- 2) source_ref עבר מ-laws ל-law_versions (as_of כבר היה שם). אומת
--    בקורפוס עצמו: פתיח חוק העונשין מוכיח שזה קרה בפועל בהיסטוריה -
--    ציטוטי טרום-1977 מול "נוסח מאוחד: ס״ח תשל״ז, 226" - קונסולידציה
--    חדשה עתידית תשנה את הציטוט שוב.
-- 3) position -> raw_order (שינוי שם, לא רק הערה): המיון המשפטי
--    לתצוגה נגזר תמיד מ-parse_section_number על number
--    (packages/corpus/numbering.py), לעולם לא מ-raw_order. השם
--    המפורש נועד למנוע ORDER BY raw_order בשוגג בקוד עתידי - אין
--    עדיין קוד שקורא מהטבלאות האלה שאפשר להוסיף לו בדיקת ריצה.
-- 4) סדר ה-insert מוגדר, לא מקרי (ראו סוף הקובץ) - laws נוצר עם
--    current_version_id=NULL, law_versions מצטרף רק אחרי ש-laws כבר
--    קיים, וה-UPDATE שמצביע current_version_id על הגרסה קורה רק
--    בסוף, בתוך אותה טרנזקציה - גרסה חלקית לעולם לא נראית "נוכחית".
--
-- הורץ בפועל ב-2026-09-13 על פרויקט Supabase legislator
-- (aamxwjmmlsqkinrzirdz) דרך mcp__Supabase__apply_migration, אומת
-- via list_tables. ראו docs/strategy/decisions.md לתהליך המלא.
--
-- דגל פתוח: Supabase החזירה אזהרת אבטחה אוטומטית - RLS כבוי על כל
-- 5 הטבלאות. לא הופעל (עלול לחסום גישה לגיטימית בלי policies) -
-- ממתין להקשר ה-ingest/חיבור ה-API. ראו decisions.md.

create table laws (
    id                        text primary key,
    full_title                text not null,
    wikitext_title            text not null,
    current_version_id        bigint,                    -- FK מתווסף למטה, אחרי שה-טבלה השנייה קיימת
    latest_known_revision_id  bigint,
    latest_checked_at         timestamptz,
    created_at                timestamptz not null default now()
);

create table law_versions (
    id                    bigint generated always as identity primary key,
    law_id                text not null references laws(id) on delete restrict,
    wikitext_revision_id  bigint not null,
    source_ref            text not null,
    as_of                 timestamptz not null,
    ingested_at           timestamptz not null default now(),
    unique (law_id, wikitext_revision_id)
);

alter table laws add constraint laws_current_version_fk
    foreign key (current_version_id) references law_versions(id);

-- nodes: immutable per גרסה - תמיד INSERT בלבד, לעולם לא UPDATE על
-- גרסה קיימת. id יכול לחזור על עצמו בין גרסאות (אותו צומת לוגי,
-- גרסה אחרת) - ולכן ה-PK הוא הזוג (law_version_id, id), לא id לבד.
create table nodes (
    law_version_id    bigint not null references law_versions(id) on delete cascade,
    id                text not null,
    parent_id         text,
    raw_order         integer not null,   -- סדר הופעה גולמי במקור - fallback בלבד, ראו הערה (3) למעלה
    node_type         text not null,      -- בלי CHECK בכוונה - הוולידציה ב-packages/validate
    number            text not null default '',
    margin_title      text,
    margin_title_raw  text,
    text              text not null default '',
    text_raw          text not null default '',
    is_normative      boolean not null default true,
    status            text not null default 'active',
    numbering_space   text not null default 'law',
    raw_amendment_note text,

    primary key (law_version_id, id),
    foreign key (law_version_id, parent_id) references nodes(law_version_id, id) on delete cascade,
    unique (law_version_id, parent_id, raw_order)
);

create index nodes_law_version_id_idx on nodes(law_version_id);
create index nodes_parent_idx on nodes(law_version_id, parent_id);

-- הגנה נוספת אמיתית (לא no-op כמו unique(law_id,id) היה): נכשלת
-- ברעש אם id יתנגש בין שני חוקים שונים (למשל תקלת slug) - לא
-- אמורה לקרות במבנה insert-only, אבל רשת ביטחון בכל זאת.
create or replace function nodes_prevent_cross_law_id_reuse() returns trigger as $$
begin
    if exists (
        select 1
        from nodes n
        join law_versions v_existing on v_existing.id = n.law_version_id
        join law_versions v_new on v_new.id = new.law_version_id
        where n.id = new.id
          and v_existing.law_id <> v_new.law_id
    ) then
        raise exception 'node id % כבר בשימוש תחת חוק אחר (לא %)',
            new.id, (select law_id from law_versions where id = new.law_version_id);
    end if;
    return new;
end;
$$ language plpgsql;

create trigger nodes_prevent_cross_law_id_reuse_trg
before insert on nodes
for each row execute function nodes_prevent_cross_law_id_reuse();

-- law_citations: רשימת הציטוטים הכרונולוגית מפתיח דף החוק, פר-גרסה.
-- עובדה נגזרת דטרמיניסטית (parse_citation_registry), לא פרשנות.
create table law_citations (
    id                bigint generated always as identity primary key,
    law_version_id    bigint not null references law_versions(id) on delete cascade,
    hebrew_year       text not null,
    ordinal_in_year   integer not null,
    page              text not null,
    name              text not null,
    amendment_number  text,

    unique (law_version_id, hebrew_year, ordinal_in_year)
);

create index law_citations_year_idx on law_citations(law_version_id, hebrew_year, ordinal_in_year);

-- section_amendment_tokens: הפרסור המבני של raw_amendment_note
-- (parse_amendment_note) - דטרמיניסטי, נבנה מחדש תמיד מ-
-- nodes.raw_amendment_note בלי רשת.
create table section_amendment_tokens (
    id                bigint generated always as identity primary key,
    law_version_id    bigint not null,
    node_id           text not null,
    token_order       integer not null,
    hebrew_year       text not null,
    ordinal_in_year   integer,           -- null = לא ידוע (ראו TASKS.md 7א) - לא ברירת מחדל
    is_legacy         boolean not null default false,

    foreign key (law_version_id, node_id) references nodes(law_version_id, id) on delete cascade,
    unique (law_version_id, node_id, token_order)
);

create index section_amendment_tokens_year_idx on section_amendment_tokens(law_version_id, hebrew_year, ordinal_in_year);

-- resolved_amendments: VIEW, לא טבלה (CLAUDE.md "ה-ingest שומר
-- עובדות, לא פרשנויות"). ordinal_in_year null -> מתאים לפי שנה
-- בלבד, יכול להחזיר 0/1/הרבה שורות.
create view resolved_amendments as
select
    t.id  as token_id, t.law_version_id, t.node_id, t.hebrew_year, t.ordinal_in_year, t.is_legacy,
    c.id  as citation_id, c.page, c.name, c.amendment_number
from section_amendment_tokens t
join law_citations c
    on c.law_version_id = t.law_version_id
   and c.hebrew_year = t.hebrew_year
   and (t.ordinal_in_year is null or c.ordinal_in_year = t.ordinal_in_year);

-- סדר ה-INSERT המוגדר ל-ingest (תיקון 4) - הכול בטרנזקציה אחת:
--   1. INSERT INTO laws (..., current_version_id) VALUES (..., NULL)
--      [רק אם החוק חדש - אם כבר קיים, מדלגים]
--   2. INSERT INTO law_versions (law_id, ...) - laws.id כבר קיים, ה-FK מתקיים
--   3. INSERT INTO nodes (law_version_id, ...) לכל העץ
--   4. INSERT INTO law_citations, section_amendment_tokens
--   5. UPDATE laws SET current_version_id = <id מ-2> WHERE id = law_id
--      (האחרון, ורק אם 1-4 הצליחו - גרסה חלקית לעולם לא הופכת "נוכחית")
