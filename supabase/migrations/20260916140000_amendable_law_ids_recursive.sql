-- תוקן (2026-09-16, ברק: "42.3% מהקורפוס לא ניתן לעריכה... זה חור
-- בלב המוצר") - ההגדרה הישנה (parent_id = שורש החוק, כלומר ילד ישיר
-- בלבד) פסלה כל חוק עם מבנה חלק/פרק/סימן, כולל 20 החוקים הגדולים
-- בקורפוס. amend()/transform.py/insert_preview.py כבר תוקנו (Python)
-- למצוא סעיפים רקורסיבית בכל עומק (node.find_sections) - ה-view
-- הזה מתעדכן לתאום: "יש לחוק לפחות section אחד עם numbering_space
-- ='law', בכל עומק" - לא משנה אם ילד ישיר של השורש או מקונן.
--
-- נמדד בפועל אחרי העדכון: 42.3% -> 0.0% לא-amendable (כל 1,077
-- חוקי ה-DB האמיתיים). ראו TASKS.md §13 להרחבה מלאה.
create or replace view amendable_law_ids
with (security_invoker = true) as
select distinct l.id as law_id
from laws l
join law_versions lv on lv.id = l.current_version_id
join nodes n on n.law_version_id = lv.id
where n.node_type = 'section'
  and n.numbering_space = 'law';
