#!/usr/bin/env python3
"""הודעת SessionStart: האם קובץ המפתחות קיים, ואילו משתנים בו.

**שמות בלבד. לעולם לא ערכים** - הפלט של ההוק נכנס להקשר של הסשן,
ומה שנכנס להקשר נכנס גם לתמליל.

קיים כדי שדרישה 6 של ברק ("ודא שהקובץ שורד ונקרא") תתקיים מעצמה
ולא תהיה תלויה בזיכרון של מי שקורא את CLAUDE.md.
"""

import json
import os
import pathlib

path = pathlib.Path(os.environ.get("LEGISLATOR_ENV_FILE",
                                   "/root/.claude/legislator.env"))
try:
    names = [line.split("=", 1)[0].strip()
             for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#") and "=" in line]
    mode = oct(path.stat().st_mode & 0o777)[2:]
    message = (f"מפתחות: {path} קיים ({mode}), {len(names)} משתנים: "
               f"{', '.join(names)}. הקוד טוען אותם דרך "
               "packages/config/env_file.py. אל תבקש מברק להדביק מפתח.")
    if mode != "600":
        message += f" **אזהרה: ההרשאות {mode} ולא 600.**"
except OSError:
    message = (f"מפתחות: {path} אינו קיים (קונטיינר חדש?). אם נדרש מפתח - "
               "בקש מברק ליצור את הקובץ מחדש, ראו CLAUDE.md. אל תדפיס ערכים.")

print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": message}},
                 ensure_ascii=False))
