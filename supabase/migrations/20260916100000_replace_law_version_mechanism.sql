-- מנגנון replace_law_version (ברק, 2026-09-16) - להחלפת גרסה שהפרסור
-- שלה הוכח שגוי (לא עדכון תוכן חדש מהכנסת). לא פקודה חד-פעמית -
-- מנגנון מוגדר עם בדיקת בטיחות, לוג, והשוואת מספר צמתים.
--
-- הפיצול לשני שלבים (מחיקה מאובטחת כאן ב-DB, הכנסה מחדש דרך
-- rest_loader.py הקיים שכבר הוכיח עצמו על 998 חוקים) הוא מכוון:
-- ה-DELETE הוא הפעולה הבלתי-הפיכה היחידה כאן - היא עטופה בפונקציה
-- אחת (=טרנזקציה אחת אמיתית), עם בדיקת בטיחות לפני. ה-INSERT שאחריה
-- הוא אותו נתיב טעינה רגיל כמו כל חוק אחר הלילה - לא קוד כתיבה חדש.
-- קריאה ל-RPC דרך REST היא קריאת HTTP אחת (לא execute_sql) - נמנעת
-- מבעיית האישורים שכבר גילינו (SESSION_ATTENDED).

create table law_version_replacement_log (
    id                bigint generated always as identity primary key,
    law_id            text not null references laws(id),
    old_version_id    bigint,
    new_version_id    bigint,
    old_node_count    integer,
    new_node_count    integer,
    reason            text not null,
    replaced_at       timestamptz not null default now(),
    new_version_recorded_at timestamptz
);

create or replace function replace_law_version_delete(p_law_id text, p_reason text)
returns table(log_id bigint, old_version_id bigint, old_node_count integer)
language plpgsql
as $$
declare
    v_old_version_id bigint;
    v_old_node_count integer;
    v_blocking_refs integer;
    v_log_id bigint;
begin
    select current_version_id into v_old_version_id from laws where id = p_law_id;
    if v_old_version_id is null then
        raise exception 'law % has no current_version_id - this is a fresh ingest, not a replacement; use the normal loader', p_law_id;
    end if;

    select count(*) into v_old_node_count from nodes where law_version_id = v_old_version_id;

    -- בדיקת "טיוטות מצביעות" - כל טבלה עם FK ל-law_versions מעבר
    -- לשלושת הילדים הידועים (nodes/law_citations/section_amendment_tokens)
    -- ו-laws עצמה (current_version_id - הפניה ידועה ומטופלת, מאופסת
    -- למטה לפני המחיקה, לא "טיוטה"). אין היום טבלת טיוטות - הבדיקה
    -- נכתבת כך שכשתהיה, זה לא יישכח (ברק, 2026-09-16).
    select count(*) into v_blocking_refs
    from pg_constraint c
    join pg_class referenced on referenced.oid = c.confrelid
    join pg_class referencing on referencing.oid = c.conrelid
    where referenced.relname = 'law_versions'
      and c.contype = 'f'
      and referencing.relname not in ('nodes', 'law_citations', 'section_amendment_tokens', 'laws');
    if v_blocking_refs > 0 then
        raise exception 'קיימת טבלה שמפנה ל-law_versions מעבר לילדים הידועים - בדיקה ידנית נדרשת לפני מחיקה (ייתכן שטיוטה מצביעה על הגרסה)';
    end if;

    insert into law_version_replacement_log (law_id, old_version_id, old_node_count, reason)
    values (p_law_id, v_old_version_id, v_old_node_count, p_reason)
    returning id into v_log_id;

    -- current_version_id מצביע על הגרסה - חייב לאפס לפני מחיקתה (FK).
    -- laws.current_version_id נשאר NULL עד שהטעינה החדשה תסיים -
    -- בדיוק אותו invariant "לא הושלם" שכבר קיים בכל שאר המערכת.
    update laws set current_version_id = null where id = p_law_id;
    delete from law_versions where id = v_old_version_id;  -- cascade ל-nodes/citations/tokens

    return query select v_log_id, v_old_version_id, v_old_node_count;
end;
$$;

create or replace function record_law_version_replacement(
    p_log_id bigint, p_new_version_id bigint, p_new_node_count integer
) returns void
language sql
as $$
    update law_version_replacement_log
    set new_version_id = p_new_version_id,
        new_node_count = p_new_node_count,
        new_version_recorded_at = now()
    where id = p_log_id;
$$;

grant execute on function replace_law_version_delete(text, text) to service_role;
grant execute on function record_law_version_replacement(bigint, bigint, integer) to service_role;
