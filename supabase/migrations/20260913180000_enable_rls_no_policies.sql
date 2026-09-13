-- RLS על כל 5 הטבלאות, בלי policies בשלב הזה (ראו TASKS.md/decisions.md).
-- Postgres ב-Supabase חשוף לאינטרנט דרך PostgREST כברירת מחדל - זו
-- סיבה מספקת לבד, לא תלויה בכך שיש היום backend שמתחבר (ואין -
-- אומת: אין שום קוד ב-apps/api שמתחבר ל-Supabase/Postgres כלל היום).
--
-- אומת מראש מול pg_roles, לא הונח: service_role/postgres
-- rolbypassrls=true, anon/authenticated=false. אומת בפועל אחרי
-- ההרצה: שורת בדיקה זמנית הוכנסה, anon/authenticated ראו 0 שורות,
-- service_role ראה 1 - ואז השורה נמחקה.
--
-- אין policies בכוונה - הקורפוס נגיש רק דרך ה-backend (שיחובר
-- דרך service_role או חיבור Postgres ישיר, לא anon - אין עדיין
-- קוד ingest/API שמתחבר בכלל). policies ייכתבו בשלב 7 (Supabase
-- Auth, משתמשים/תפקידים אמיתיים).

alter table laws enable row level security;
alter table law_versions enable row level security;
alter table nodes enable row level security;
alter table law_citations enable row level security;
alter table section_amendment_tokens enable row level security;
