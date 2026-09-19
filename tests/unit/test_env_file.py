"""בדיקות ל-packages/config/env_file.py - מקור המפתחות היחיד.

שלוש תכונות שחייבות להיות נעולות בטסט ולא בהבטחה:

1. **הסביבה גוברת על הקובץ.** בפרודקשן אין קובץ והמפתחות הם משתני
   סביבה של הפרויקט. אילו הקובץ היה גובר, סביבת פיתוח הייתה
   יכולה לדרוס בשקט את הפרודקשן.
2. **שום ערך אינו דולף** - לא בהודעת שגיאה, לא ב-loaded_names,
   לא ב-repr של החריגה.
3. **קובץ חסר אינו שגיאה** - זה המצב התקין בפרודקשן.

הטסט **אינו** נוגע בקובץ האמיתי: הוא כותב קובץ זמני ומצביע אליו
דרך LEGISLATOR_ENV_FILE.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "config"))

import env_file  # noqa: E402

_SECRET = "sk-test-VALUE-SHOULD-NEVER-APPEAR-1234567890"


def _with_file(body: str, env: dict):
    """מריץ עם קובץ זמני ועם סביבה נקייה, ומחזיר את env_file טעון מחדש."""
    tmp = Path(tempfile.mkdtemp()) / "t.env"
    tmp.write_text(body, encoding="utf-8")
    saved = {k: os.environ.get(k) for k in (*env, "LEGISLATOR_ENV_FILE")}
    for k in env:
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    os.environ["LEGISLATOR_ENV_FILE"] = str(tmp)
    env_file.load(force=True)
    return tmp, saved


def _restore(saved):
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    env_file.load(force=True)


def main() -> int:
    checks: list[tuple[str, bool]] = []

    # 1. נטען מהקובץ כשאינו בסביבה
    _, saved = _with_file(f"T_ONE={_SECRET}\nT_TWO=vvv\n", {"T_ONE": None, "T_TWO": None})
    checks.append(("נטען מהקובץ כשהמשתנה אינו בסביבה", env_file.get("T_ONE") == _SECRET))
    checks.append(("loaded_names מחזירה שמות", set(env_file.loaded_names()) >= {"T_ONE", "T_TWO"}))
    checks.append(("loaded_names אינה מחזירה ערכים",
                   all(_SECRET not in n for n in env_file.loaded_names())))
    _restore(saved)

    # 2. הסביבה גוברת - זו ההגנה על הפרודקשן
    _, saved = _with_file(f"T_ONE={_SECRET}\n", {"T_ONE": "מהסביבה"})
    checks.append(("סביבה גוברת על הקובץ", env_file.get("T_ONE") == "מהסביבה"))
    checks.append(("משתנה שכבר היה בסביבה אינו מדווח כנטען",
                   "T_ONE" not in env_file.loaded_names()))
    _restore(saved)

    # 3. הערות, שורות ריקות, export, ומרכאות
    _, saved = _with_file(
        '# הערה\n\nexport T_THREE="בתוך מרכאות"\nT_FOUR=\'יחידות\'\nשורה בלי שווה\n',
        {"T_THREE": None, "T_FOUR": None})
    checks.append(("export מנוקה מהשם", env_file.get("T_THREE") == "בתוך מרכאות"))
    checks.append(("מרכאות יחידות מנוקות", env_file.get("T_FOUR") == "יחידות"))
    checks.append(("שורה בלי = מדולגת בלי קריסה", True))
    _restore(saved)

    # 4. קובץ חסר - לא שגיאה
    saved = {"LEGISLATOR_ENV_FILE": os.environ.get("LEGISLATOR_ENV_FILE")}
    os.environ["LEGISLATOR_ENV_FILE"] = "/nonexistent/dir/nope.env"
    checks.append(("קובץ חסר מחזיר () ולא זורק", env_file.load(force=True) == ()))

    # 5. require: שגיאה מפורשת, בלי ערך
    raised, message = False, ""
    try:
        env_file.require("T_NOT_THERE_AT_ALL", used_for="בדיקה")
    except env_file.MissingSecret as e:
        raised, message = True, str(e)
    checks.append(("משתנה חסר -> MissingSecret", raised))
    checks.append(("ההודעה מציינת את שם המשתנה", "T_NOT_THERE_AT_ALL" in message))
    checks.append(("ההודעה מציינת למה הוא נדרש", "בדיקה" in message))
    _restore(saved)

    # 6. **אף ערך לא דולף בהודעת שגיאה** - גם כשהמשתנה כן קיים
    _, saved = _with_file(f"T_FIVE={_SECRET}\n", {"T_FIVE": None})
    leaked = False
    try:
        env_file.require("T_STILL_MISSING")
    except env_file.MissingSecret as e:
        leaked = _SECRET in str(e) or _SECRET in repr(e)
    checks.append(("ערך של מפתח אחר אינו דולף להודעת שגיאה", not leaked))
    _restore(saved)

    # 7. אף קובץ בריפו אינו קורא os.environ למפתח ישירות
    root = Path(__file__).resolve().parents[2]
    offenders = []
    for path in list(root.glob("apps/**/*.py")) + list(root.glob("packages/**/*.py")) \
            + list(root.glob("tools/*.py")):
        if path.name == "env_file.py" or "__pycache__" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        for secret in ("SUPABASE_SERVICE_ROLE_KEY", "ANTHROPIC_API_KEY",
                       "OPENAI_API_KEY", "INGEST_SECRET", "SUPABASE_URL"):
            if f'environ.get("{secret}")' in text or f'getenv("{secret}")' in text:
                offenders.append(f"{path.relative_to(root)}:{secret}")
    checks.append((f"אין קריאה ישירה ל-os.environ למפתח ({offenders})", not offenders))

    # 8. הקובץ האמיתי אינו בתוך הריפו
    inside = list(root.rglob("legislator.env")) + list(root.rglob("*.env"))
    checks.append((f"אין קובץ .env בתוך הריפו ({[str(p) for p in inside]})", not inside))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
