-- רגרסיית ביצועים שנחשפה בהרצת האינדוקס הסמנטי (2026-09-17):
-- ה-view amendable_law_ids סרק את nodes במלואה (246K שורות, מסונן
-- ל-node_type='section' AND numbering_space='law'). כל עוד הטבלה
-- ישבה במטמון של מופע ה-Free tier זה לקח שברירי שנייה - אבל אחרי
-- ש-search_chunks + אינדקס ה-HNSW (כ-118MB) דחקו אותה מהמטמון,
-- הסריקה ירדה לדיסק ולקחה 7.7 שניות (נמדד ב-EXPLAIN ANALYZE:
-- Parallel Seq Scan, read=4726 buffers).
--
-- התוצאה בפועל: /api/laws ו-/api/laws/search החזירו 500 - חריגה
-- מתקרת הזמן של פונקציית Vercel. כלומר: גדילת ה-DB הפילה מסלולים
-- שלא נגעתי בהם בכלל.
--
-- אינדקס חלקי שתואם בדיוק את תנאי ה-view: 7,679ms -> 43ms.
create index if not exists nodes_section_law_version_idx
  on public.nodes (law_version_id)
  where node_type = 'section' and numbering_space = 'law';
