-- view זול לחישוב "amendable" ל-law_summaries() (ברק, 2026-09-16) -
-- בלי זה, apps/api היה צריך לשלוף parent_id של כל 45K+ צמתי section
-- דרך REST (עימוד ב-1000/עמוד = ~46 round-trips), נמדד בפועל ב-~30
-- שניות ל-GET /api/laws - לא סביר לרשימת חוקים. ה-DISTINCT מחושב
-- פעם אחת בתוך Postgres, לא דרך HTTP.
--
-- מוגבל במפורש ל-parent_id שהוא שורש חוק בעצמו (exists נגד laws) -
-- לא כל parent אפשרי של צומת section (שכולל הורים מקוננים עמוק, כמו
-- "פרק א סימן ג") - amendable מוגדר צר בכוונה (ילד ישיר של השורש
-- בלבד, ראו apps/api/law_registry.py), אז ה-view הזה מחזיר לכל
-- היותר כמה מאות שורות (אחת לכל חוק amendable), לא אלפים.
--
-- security_invoker=true (לא ברירת המחדל של view) - אותו נימוק כמו
-- resolved_amendments (ראו migration קודמת): רץ בהרשאות הקורא, לא
-- הבעלים - אין סיבה לעקוף RLS כאן.
create view amendable_law_ids
with (security_invoker = true) as
select distinct n.parent_id as law_id
from nodes n
where n.node_type = 'section'
  and exists (select 1 from laws l where l.id = n.parent_id);
