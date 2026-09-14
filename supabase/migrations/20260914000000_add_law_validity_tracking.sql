-- זיהוי תוקף מול KNS_IsraelLaw (OData v4 של הכנסת) - ראו
-- docs/strategy/decisions.md (2026-09-14) ו-packages/corpus/knesset_odata.py.
-- law_validity_desc: הערך הגולמי מ-LawValidityDesc ("תקף"/"בטל"/"פקע"/"נושן"),
-- NULL אם לא נמצאה התאמה חד-משמעית (לא אומר "תקף" - אומר "לא ידוע").
-- validity_match_method: על מה מבוסס הסיווג - 'exact' | 'normalized' |
-- 'ambiguous' | 'not_found' (ראו knesset_odata.classify_validity) - כדי
-- שאפשר יהיה תמיד לדעת אם ערך law_validity_desc בא מהתאמה ודאית או לא.
-- עקרון (ברק, 2026-09-14): "שום חוק לא נזרק בגלל שלא הצלחנו לבדוק אותו" -
-- העמודות האלה נשמרות תמיד, גם לחוקים שנטענו וגם (בעתיד) לרשומות שסוננו,
-- כדי שהחלטת הסינון תהיה הפיכה בלי לאבד את הנתון הגולמי.
alter table laws add column law_validity_desc text;
alter table laws add column validity_match_method text;
