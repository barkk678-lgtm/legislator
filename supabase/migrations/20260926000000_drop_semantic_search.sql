-- task 130 (ברק, 26.9.2026 - מאושר): החיפוש הסמנטי הוסר ב-25.9 (task 129,
-- e0f1c95); כאן יורד כל מה שקיים בדאטהבייס **רק** בשבילו.
--
-- נבדק לפני המחיקה, בפועל ולא מהקוד בלבד:
--   * אף קוד פעיל לא קורא מהם: /api/semantic-search, /api/admin/openai-check
--     ו-/api/admin/ingest-chunks מחזירים 410 לפני כל גישה ל-DB; מומחה התקנון
--     משתמש ב-chunking.collect_text בלבד (פונקציה בקוד, לא הטבלה).
--   * מוני הגישה (pg_stat_user_tables) של search_chunks, ingest_progress
--     ו-ingest_log לא זזו לאורך בדיקה חיה מלאה (47 בדיקות, כל הכלים, כולל
--     ה-LLM).
--   * תלויות ב-DB: ה-view indexed_laws, הפונקציה hybrid_search_chunks,
--     חמשת האינדקסים של הטבלה, וההרחבה vector (עמודת vector יחידה:
--     search_chunks.embedding). אין FK אל ingest_progress/ingest_log, אין
--     view או פונקציה שקוראים מהן, אין pg_cron.
--
-- **נשאר בכוונה:** nodes_section_law_version_idx - נבנה בזמן האינדוקס, אבל
-- משרת את amendable_law_ids (7.7s -> 43ms).
--
-- חזרה: הקוד שמור בענף archive/semantic-search-v1 (3f9a440), והמיגרציות
-- 20260917000000..20260917120000 בונות הכול מחדש. האינדוקס עצמו (embeddings)
-- - $0.98 לפי ingest_log. ראו DECISION_HISTORY "חיפוש סמנטי ולשונית מחקר".

drop view if exists public.indexed_laws;
drop function if exists public.hybrid_search_chunks(
  text, vector, integer, double precision, double precision);
drop table if exists public.search_chunks;
drop table if exists public.ingest_progress;
drop table if exists public.ingest_log;
drop extension if exists vector;
