# בדיקות בארכיון - לא רצות ב-CI

הבדיקות של **לשונית "מחקר"** ושל **החיפוש הסמנטי**, שהוסרו מהמוצר
ב-25.9.2026 (ברק: ביצועים, ערך למשתמש). ראו `docs/DECISION_HISTORY.md`
"חיפוש סמנטי ולשונית מחקר".

- `test_semantic_search.py`, `test_embeddings_errors.py`,
  `test_admin_ingest.py`, `test_chunking.py` - החיפוש הסמנטי והאינדוקס.
- `test_research.py`, `test_research_constraints.py` - השאלות
  הסטטיסטיות על נתוני הכנסת. **הקוד שלהן עדיין בריפו**
  (`apps/api/research.py`), רק לא מוצג בממשק.

הן נשמרות כאן ולא נמחקו: מי שמחזיר את הפיצ'ר מחזיר אותן ל-`tests/unit/`.
`packages/corpus/chunking.py` **נשאר** - `collect_text` שבו משמש את
מומחה התקנון.

הריצה: `python3 tests/archived/<file>.py`. אין הבטחה שהן עדיין עוברות -
נקודות הקצה מחזירות 410 מ-25.9.
