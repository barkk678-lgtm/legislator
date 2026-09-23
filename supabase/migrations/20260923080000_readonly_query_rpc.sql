-- ערוץ הקריאה של הסוכן ל-DB (ברק, 2026-09-23).
--
-- **למה זה קיים:** כל שאילתת חקירה עברה דרך `mcp execute_sql`, וכל
-- אחת מהן ביקשה אישור. הערוץ שדרכו נטענו 1,092 החוקים - REST עם
-- service_role - אינו מבקש אישור, ו-PostgREST יודע לקרוא לפונקציה
-- דרך `/rest/v1/rpc/<שם>`. הפונקציה הזו היא הקצה הזה, והעוטף בצד
-- הלקוח הוא `tools/sql.py`.
--
-- **לקריאה בלבד, והאכיפה כאן ולא בקוד.** הפונקציה מעבירה את
-- הטרנזקציה ל-`transaction_read_only`, ולכן כל INSERT/UPDATE/DELETE/
-- DDL נכשל ב-25006 מהמנוע עצמו. **לא** בדיקת מחרוזת מסוג "האם
-- מתחיל ב-SELECT" - זו בדיקה שאפשר לעקוף (CTE, פונקציה שכותבת).
--
-- **הבקרות השליליות ב-`tests/live/test_readonly_query.py`**, ויש
-- להריץ אותן אחרי כל שינוי כאן. שים לב לאחת מהן במיוחד: INSERT
-- ישיר דרך הפונקציה נכשל ב**שגיאת תחביר** (הוא נעטף ב-
-- `select ... from (%s) t`, ושם אינו חוקי) - כלומר אינו מוכיח
-- שהאכיפה עובדת. ההוכחה היא `select nextval(...)`, שהוא SELECT
-- תקין לחלוטין, מגיע להרצה, ונחסם.
--
-- **statement_timeout אינו נקבע כאן.** התקרה בפועל היא 8 שניות
-- מ-`authenticator` (rolconfig), ונאכפת בפלטפורמה. נמדד שניסיון
-- להנמיך אותה מתוך הפונקציה אינו עובד: `current_setting` מחזיר את
-- הערך החדש, אבל `statement_timeout` נתפס כשההצהרה העליונה מתחילה
-- והקריאה לפונקציה כבר רצה - גם 2 שניות וגם 5 נקטעו ב-8.6.

create or replace function public.readonly_query(q text)
returns jsonb
language plpgsql
-- **לא** security definer: רץ בהרשאות הקורא, ולכן אינו מעניק שום
-- גישה מעבר למה של-service_role כבר יש.
as $$
declare
    result jsonb;
begin
    set local transaction_read_only = on;
    execute format('select coalesce(jsonb_agg(t), ''[]''::jsonb) from (%s) t', q)
        into result;
    return result;
end;
$$;

-- הפונקציה חשופה דרך PostgREST. בלי ההסרה הזו כל מי שמחזיק את
-- המפתח הציבורי (anon) יכול להריץ שאילתות על הדאטהבייס.
revoke all on function public.readonly_query(text) from public;
revoke all on function public.readonly_query(text) from anon;
revoke all on function public.readonly_query(text) from authenticated;
grant execute on function public.readonly_query(text) to service_role;

notify pgrst, 'reload schema';
