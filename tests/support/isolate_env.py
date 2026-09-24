"""בידוד הטסטים ממפתחות אמיתיים. **מיובא ראשון, לפני כל ייבוא אחר.**

**למה זה נדרש דווקא עכשיו:** עד 2026-09-19 הסביבה שבה רצו הטסטים
במקרה לא הכילה מפתחות, ולכן בדיקות כמו "בלי SUPABASE_URL -> 503"
עברו במקרה. מרגע שהמפתחות נטענים מ-`/root/.claude/legislator.env`,
אותן בדיקות התחילו להיכשל - לא כי משהו נשבר, אלא כי הן **מעולם לא
היו הרמטיות**: התוצאה שלהן הייתה תלויה במה שמוגדר במכונה.

`isolate()` מנתקת את התהליך גם מהסביבה וגם מקובץ המפתחות, כך
שהטסט בודק את ההתנהגות שהוא טוען לבדוק - בכל מכונה, עם מפתחות או
בלעדיהם. טסט שצריך מפתח אמיתי אינו טסט יחידה.
"""

from __future__ import annotations

import os

SECRET_NAMES = (
    "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "INGEST_SECRET",
    # כינוי ל-ANTHROPIC_API_KEY (env_file.ALIASES). בלעדיו כל בדיקה
    # שמניחה "אין מפתח" קוראת למודל האמיתי בסביבת הענן, שבה הוא מוגדר.
    "LEGISLATOR_ANTHROPIC_API_KEY",
)

_NO_FILE = "/nonexistent/legislator-tests/never.env"


def isolate(*, keep: tuple[str, ...] = ()) -> None:
    """מסירה את כל המפתחות מהסביבה ומצביעה את טוען הקובץ לנתיב שאינו
    קיים. `keep` לשמות שהטסט דווקא רוצה להשאיר."""
    os.environ["LEGISLATOR_ENV_FILE"] = _NO_FILE
    for name in SECRET_NAMES:
        if name not in keep:
            os.environ.pop(name, None)


def set_secret(name: str, value: str) -> None:
    """קובעת מפתח מדומה לטסט שצריך ש"יש מפתח", בלי לגעת באמיתי."""
    os.environ["LEGISLATOR_ENV_FILE"] = _NO_FILE
    os.environ[name] = value


def clear_secret(name: str) -> None:
    os.environ.pop(name, None)
