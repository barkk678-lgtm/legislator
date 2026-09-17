-- אבטחה/הרצה-חוזרת ל-ingest ה-embeddings (ברק, 2026-09-17): endpoint
-- מוגן-טוקן (POST /api/admin/ingest-chunks) שרץ מ-Vercel (הרשת שלו
-- פתוחה ל-api.openai.com, בניגוד לסביבת ה-agent - ראו CLAUDE.md
-- "גבולות רשת" וnight-report.md). שתי טבלאות חדשות:
--
-- ingest_progress: מצב-התקדמות לכל חוק, ברמת חוק שלם - "done" רק
-- אחרי שכל ה-chunks שלו נכתבו בהצלחה. מאפשרת המשך מדויק אחרי הפסקה
-- (endpoint בוחר את החוקים הבאים שאינם "done", לא סורק הכול מחדש).
--
-- ingest_log: רשומה לכל הפעלה בפועל של ה-endpoint - זמן, כמה
-- chunks/טוקנים בפועל (מ-usage.total_tokens האמיתי של OpenAI, לא
-- הערכה), עלות מחושבת. משמש גם ללוג המבוקש וגם למגבלת הקצב (ספירת
-- הפעלות בשעה האחרונה) - טבלה אחת, שתי תכליות.

create table if not exists ingest_progress (
  law_id text primary key references laws(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'done', 'error')),
  chunks_count int not null default 0,
  error_detail text,
  updated_at timestamptz not null default now()
);

create table if not exists ingest_log (
  id bigint generated always as identity primary key,
  called_at timestamptz not null default now(),
  laws_processed int not null default 0,
  chunks_embedded int not null default 0,
  chunks_skipped_existing int not null default 0,
  chunks_skipped_too_long int not null default 0,
  total_tokens int not null default 0,
  estimated_cost_usd numeric(10, 6) not null default 0,
  duration_ms int
);

create index if not exists ingest_log_called_at_idx on ingest_log (called_at desc);

alter table ingest_progress enable row level security;
alter table ingest_log enable row level security;
-- בלי policies בכוונה, כמו שאר טבלאות התשתית - service_role בלבד
-- (ה-endpoint המוגן-טוקן הוא היחיד שנוגע בטבלאות האלה).
