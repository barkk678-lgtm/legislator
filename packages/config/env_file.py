"""מקור יחיד למפתחות ולתצורה. **כל קריאה למשתנה סביבה עוברת כאן.**

**הבעיה שזה פותר (ברק, 2026-09-19):** המפתחות אבדו בכל דחיסת שיחה,
וברק הדביק אותם שוב ושוב. עכשיו הם יושבים בקובץ אחד
(`/root/.claude/legislator.env`, הרשאות 600, **מחוץ לריפו**),
והפונקציות כאן טוענות אותו לפי הצורך.

**סדר העדיפויות, ולמה דווקא הוא:** משתנה שכבר קיים בסביבה **גובר
תמיד** על הקובץ. בפרודקשן (Vercel) אין את הקובץ בכלל והמפתחות
מוגדרים כמשתני סביבה של הפרויקט; אילו הקובץ היה גובר, סביבת
הפיתוח הייתה יכולה לדרוס בשקט את הפרודקשן. לכן: סביבה ואז קובץ,
אף פעם להפך.

**הקובץ אינו קיים בפרודקשן וזה תקין** - היעדרו אינו שגיאה.
שגיאה היא רק משתנה שנדרש ואינו נמצא באף אחד מהשניים, ואז
`require` זורקת `MissingSecret` עם שם המשתנה בלבד.

**אף פונקציה כאן לא מחזירה ולא מדפיסה ערך של מפתח בהודעת שגיאה,
בלוג או ב-repr.** `loaded_names()` מחזירה שמות בלבד. זה נבדק
ב-tests/unit/test_env_file.py.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PATH = Path("/root/.claude/legislator.env")
PATH_OVERRIDE = "LEGISLATOR_ENV_FILE"

_loaded_from: Path | None = None
_names: tuple[str, ...] = ()


class MissingSecret(Exception):
    """משתנה נדרש אינו בסביבה ואינו בקובץ. **בלי ערכים בהודעה.**"""


def env_path() -> Path:
    """נתיב הקובץ. ניתן לעקיפה ב-LEGISLATOR_ENV_FILE (לטסטים)."""
    override = os.environ.get(PATH_OVERRIDE)
    return Path(override) if override else DEFAULT_PATH


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name:
            out[name] = value
    return out


def load(*, force: bool = False) -> tuple[str, ...]:
    """טוענת את הקובץ לתוך `os.environ`, **בלי לדרוס** מה שכבר שם.

    מחזירה את שמות המשתנים שנטענו מהקובץ (שמות בלבד). קריאה חוזרת
    אינה טוענת שוב אלא אם `force`. קובץ חסר מחזיר `()` בשקט."""
    global _loaded_from, _names
    path = env_path()
    if _loaded_from == path and not force:
        return _names
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        _loaded_from, _names = path, ()
        return _names
    applied = []
    for name, value in _parse(text).items():
        if os.environ.get(name):
            continue  # הסביבה גוברת - ראו ה-docstring למעלה
        os.environ[name] = value
        applied.append(name)
    _loaded_from, _names = path, tuple(applied)
    return _names


def get(name: str, default: str | None = None) -> str | None:
    """הערך מהסביבה, ואם אינו שם - מהקובץ. `None` אם אין בשניהם."""
    value = os.environ.get(name)
    if value:
        return value
    load()
    return os.environ.get(name) or default


def require(name: str, *, used_for: str = "") -> str:
    """כמו `get`, אבל זורקת `MissingSecret` במקום להחזיר `None`.

    `used_for` נכנס להודעה כדי שהשגיאה תגיד מה לא יעבוד - **בלי
    שום ערך**."""
    value = get(name)
    if value:
        return value
    suffix = f" נדרש ל{used_for}." if used_for else ""
    raise MissingSecret(
        f"חסר {name}.{suffix} הוא נקרא מהסביבה, ואם אינו שם - מ-"
        f"{env_path()} (הרשאות 600, מחוץ לריפו). ראו CLAUDE.md."
    )


def require_supabase() -> tuple[str, str]:
    """(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) - הצמד שחוזר בכל
    נתיב שניגש ל-DB, כדי שלא ייכתב שוב בכל קובץ."""
    return (require("SUPABASE_URL", used_for="חיבור ל-Supabase"),
            require("SUPABASE_SERVICE_ROLE_KEY", used_for="חיבור ל-Supabase"))


def loaded_names() -> tuple[str, ...]:
    """שמות המשתנים שנטענו מהקובץ. **שמות בלבד, לעולם לא ערכים.**"""
    load()
    return _names
