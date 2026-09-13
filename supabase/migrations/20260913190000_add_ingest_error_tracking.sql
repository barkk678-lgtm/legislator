-- נרשם ב-סטטמנט נפרד, מחוץ לטרנזקציה שנכשלה/rollback-ה (ראו
-- docs/strategy/decisions.md, "התובנה שהתיעוד נכתב אחרי ה-rollback
-- ולא בתוכה היא בדיוק הפרט שנשכח ואז חסר כשצריך אותו").
-- category: 'network' (חולף, retry) | 'sanity' (פרסור/בדיקת שפיות, לא retry).
alter table laws add column last_ingest_error text;
alter table laws add column last_ingest_attempted_at timestamptz;
