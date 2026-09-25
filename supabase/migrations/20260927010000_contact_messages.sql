-- דף הבית 3 (27.9.2026): פניות "יצירת קשר". אותו דפוס כמו chat_log:
-- **רק השרת כותב וקורא** (service role). RLS מופעל בלי אף policy, והרשאות
-- anon/authenticated נשללות - הדפדפן לא ניגש לטבלה בשום מסלול.
-- ip_hash: HMAC של כתובת ה-IP (לא הכתובת עצמה) - להגבלת קצב השליחה בלבד.
-- מייל לברק והצגה בממשק הניהול - עוד לא (docs/open-gaps.md).

create table if not exists public.contact_messages (
    id          bigint generated always as identity primary key,
    created_at  timestamptz not null default now(),
    is_guest    boolean not null,
    name        text not null,
    email       text not null,
    message     text not null,
    user_id     text,
    ip_hash     text not null,
    is_test     boolean not null default false
);

create index if not exists contact_messages_ip_time_idx
    on public.contact_messages (ip_hash, created_at desc);

alter table public.contact_messages enable row level security;
revoke all on table public.contact_messages from anon, authenticated;
