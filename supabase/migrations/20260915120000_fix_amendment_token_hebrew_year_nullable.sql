-- תיקון סתירה במיגרציה הקודמת (20260914010000): התיעוד שם קובע במפורש
-- שטוקן לא-ניתן-לפענוח (is_unparsed=true, למשל "תשס״ה־3 תשע״ד" בחוק
-- העמותות - הדוגמה המדויקת שהמיגרציה ההיא נתנה) משאיר hebrew_year NULL,
-- אבל העמודה נשארה not null מה-CREATE TABLE המקורי (20260913173000) -
-- לא תוקנה בפועל. התגלה ב-2026-09-15 בטעינת הקורפוס המלא: insert נכשל
-- (23502 not-null violation) בדיוק על אותו חוק שהמיגרציה חזתה.
alter table section_amendment_tokens alter column hebrew_year drop not null;
