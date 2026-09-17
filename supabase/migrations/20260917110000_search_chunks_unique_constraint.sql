-- נדרש לתמיכה ב-upsert (POST .../search_chunks?on_conflict=law_id,
-- section_number,chunk_index, Prefer: resolution=merge-duplicates) -
-- ה-endpoint המוגן-טוקן (apps/api/admin_ingest.py) כותב כך כדי
-- שקריאה חוזרת/נופלת-בחלקה לא תיצור שורות כפולות לאותו chunk.

alter table search_chunks
  add constraint search_chunks_law_section_chunk_key
  unique (law_id, section_number, chunk_index);
