"""שכבת גישור לפריסת Vercel בלבד.

Vercel מזהה פונקציות Python אוטומטית (zero-config) לפי קבצים תחת
תיקייה בשם api/ בשורש הריפו - לא apps/api/, שם יושב היישום האמיתי
(ראו TASKS.md משימה 10). הקובץ הזה רק מייבא ומחשוף מחדש את app
האמיתי - אין כאן שום לוגיקה, ולא רץ בהרצה מקומית (uvicorn ממשיך
להצביע ישירות על apps/api/main.py כרגיל).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from main import app  # noqa: E402,F401
