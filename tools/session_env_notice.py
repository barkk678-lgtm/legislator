#!/usr/bin/env python3
"""הודעת SessionStart על קובץ המפתחות.

**שמות בלבד. לעולם לא ערכים** - הפלט נכנס להקשר של הסשן, ומה
שנכנס להקשר נכנס גם לתמליל.

קיים כדי שדרישה 6 של ברק ("ודא שהקובץ שורד ונקרא") תתקיים מעצמה
ולא תהיה תלויה בזיכרון של מי שקורא את CLAUDE.md.

**רשום ב-`/root/.claude/settings.json` (רמת המשתמש) ולא בהגדרות
הריפו** - ה-cwd של הסשן אינו בהכרח `legislator` (בסשן שבו נכתב
הקובץ הזה הוא היה `hasomer_mifalim`), ואז הגדרות הריפו אינן
נטענות כלל וההוק לא היה יורה. ראו docs/strategy/decisions.md.
"""

import json
import os
import pathlib

REQUIRED = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY", "INGEST_SECRET")

path = pathlib.Path(os.environ.get("LEGISLATOR_ENV_FILE",
                                   "/root/.claude/legislator.env"))
try:
    names = [line.split("=", 1)[0].strip()
             for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#") and "=" in line]
    mode = oct(path.stat().st_mode & 0o777)[2:]
    message = (f"מפתחות: {path} קיים ({mode}), {len(names)} משתנים: "
               f"{', '.join(names)}. הקוד טוען אותם דרך "
               "packages/config/env_file.py - אל תבקש מברק להדביק מפתח.")
    missing = [n for n in REQUIRED if n not in names]
    if missing:
        message += f" **חסרים בקובץ: {', '.join(missing)}.**"
    if mode != "600":
        message += f" **אזהרה: ההרשאות {mode} ולא 600 - תקן ב-chmod 600.**"
except OSError:
    # קונטיינר חדש. ההודעה חייבת להיות מספיקה כדי שברק ידביק פעם
    # אחת ויסיים - שמות בלבד, הפורמט המדויק, והפקודה שיוצרת.
    template = "\n".join(f"{n}=" for n in REQUIRED)
    message = (
        f"מפתחות: {path} אינו קיים (קונטיינר חדש). בקש מברק להדביק פעם "
        "אחת, והרץ עבורו את הפקודה הזו כלשונה (עם הערכים שיתן, ובלי "
        "להדפיס אותם בחזרה):\n"
        "umask 077 && mkdir -p /root/.claude && cat > "
        f"{path} <<'ENVEOF'\n{template}\nENVEOF\n"
        f"chmod 600 {path}\n"
        "כל משתנה בשורה משלו, בלי מרכאות ובלי רווחים סביב ה-=. "
        "אל תדפיס ערכים בשום פלט. ראו CLAUDE.md."
    )

print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": message}},
                 ensure_ascii=False))
