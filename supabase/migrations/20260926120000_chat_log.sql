-- צ7 (26.9.2026): רשומה של כל הודעה בכל שיחה, לפי כלי - לניטור טעויות
-- נפוצות, שאלות שהצ'אט לא יודע לענות עליהן וסירובים (ממשק ניהול - בהמשך).
-- **רק השרת כותב וקורא** (service role): RLS מופעל בלי אף policy, והרשאות
-- anon/authenticated נשללות - הדפדפן לא ניגש לטבלה בשום מסלול.
-- אין הרשמה: user_id הוא מזהה אנונימי שנוצר בדפדפן.
-- לפני השקה: תנאי השימוש חייבים לומר שהשיחות נשמרות (docs/open-gaps.md).

create table if not exists public.chat_log (
    id              bigint generated always as identity primary key,
    created_at      timestamptz not null default now(),
    tool            text not null check (tool in ('query', 'agenda', 'rules')),
    conversation_id text,
    user_id         text,
    user_message    text not null,
    reply           text,
    kind            text not null check (kind in (
                        'chitchat', 'insult', 'substantive', 'refused',
                        'not_found', 'guard_replaced', 'error')),
    meta            jsonb not null default '{}'::jsonb
);

create index if not exists chat_log_created_at_idx on public.chat_log (created_at desc);
create index if not exists chat_log_tool_kind_idx on public.chat_log (tool, kind);

alter table public.chat_log enable row level security;
revoke all on table public.chat_log from anon, authenticated;
