-- מטמון לצבירות של כל-הקורפוס מ-OData של הכנסת.
--
-- הסיבה אינה מהירות אלא סיכון חסימה: ה-WAF של הכנסת כבר החזיר 473
-- ("access denied" עם ה-IP) על תבנית שאילתה אחת, וכל משתמש שישאל
-- שאלה מייצר בקשות מ-IP של Vercel. נמדד: שאלה על יוזמים מובילים =
-- 11 בקשות ו-12 שניות; עשרה משתמשים במקביל = 110 בקשות בפרץ אחד.
--
-- שתי התבניות שנשמרות כאן הן צבירות על כל הקורפוס - התשובה זהה לכל
-- משתמש ומשתנה בקצב של שבועות, ולכן אין שום סיבה לשאול מחדש.
-- חיפוש לפי נושא אינו נשמר: הוא תלוי-שאילתה ועולה בקשה אחת בלבד.
create table if not exists public.knesset_agg_cache (
  template_id text primary key,
  payload jsonb not null,
  knesset_requests integer not null default 0,  -- כמה בקשות נחסכות בכל פגיעה
  refreshed_at timestamptz not null default now()
);

alter table public.knesset_agg_cache enable row level security;

comment on table public.knesset_agg_cache is
  'מטמון צבירות OData - ראו apps/api/research.py. קיים כדי לא להעמיס על שרת הכנסת ולא להסתכן בחסימת WAF.';
