-- ברק, 2026-09-17: "הרץ על 67 החוקים המדורגים ביותר, שמור מרווח של 50MB"
-- + "הממשק חייב להבדיל בין 'לא נמצא' לבין 'החוק לא מאונדקס'".
--
-- שלושה דברים, כולם בשירות שתי הדרישות האלה:

-- 1. מדידת גודל ה-DB בפועל. המרווח של 50MB נשמר מול המספר האמיתי
--    ולא מול ההערכה שלי - הערכה יכולה לסטות, pg_database_size לא.
--    PostgREST לא חושף פונקציות מערכת, ולכן RPC ייעודי.
create or replace function public.db_size_bytes()
returns bigint
language sql
security invoker
set search_path = public
as $$ select pg_database_size(current_database()); $$;

-- 2. אילו חוקים באמת מאונדקסים - מקור האמת לתשובה "החוק הזה לא
--    מאונדקס" בממשק. נגזר מ-search_chunks עצמה (ולא מ-ingest_progress)
--    כדי שחוק שאונדקס חלקית ייספר לפי מה שקיים בפועל.
create or replace view public.indexed_laws
with (security_invoker = true) as
select law_id, count(*) as chunk_count
from public.search_chunks
where embedding is not null
group by law_id;

-- 3. תיעוד מסלול ההרצה היזומה בלוג. המסלול עוקף את מגבלת הקצב
--    (דרישה 1) - ולכן חייב להיות מסומן בלוג, אחרת אי אפשר להבדיל
--    בדיעבד בין קריאה רגילה לקריאה שעקפה את המגבלה.
alter table public.ingest_log
  add column if not exists rate_limit_bypassed boolean not null default false;
