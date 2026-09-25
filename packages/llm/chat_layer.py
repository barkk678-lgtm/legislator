"""שכבה משותפת לכל הצ'אטבוטים באפליקציה (ת4 + ת5, ברק 25.9.2026).

**סיווג לפני תשובה, לא בדיקה אחרי.** עד כאן כל הודעה הלכה ישר לכלי.
"אתה נהדר כל הכבוד!" קיבלה ממומחה התקנון תשובה חמה עם אימוג'י - ואז
שומר הציטוט, שלא מצא בה מקור, החליף אותה ב"לא מצאתי תשובה חד-משמעית".
לתשובה על מחמאה אין מקור, ולא צריך להיות. שוחזר על האתר החי: מחמאה,
תודה וקללה - שלושתן הוזרמו ואז נמחקו.

שלושה סוגים (שאלת דעה נשארת בתוך המסלול הענייני, כמו שהייתה):
- **חולין** - תודה, מחמאה, ברכה, שאלה על הבוט עצמו: תשובה חמה וקצרה,
  בלי מקור ובלי שומר ציטוט. ברק: "אני רוצה יותר תשובות חמודות כאלה".
- **עלבון** - קללה או עלבון כלפי הבוט: "אני מזכיר, כאן זו לא מליאת
  הכנסת – נא להתבטא בכבוד 😉" ווריאציות באותה רוח. **טקסט קבוע, לא
  מודל** - אין מה לנסח, ואין סיבה לשלם או לחכות.
- **עניינית** - כל השאר: הכלי עצמו, עם שומר הציטוט בדיוק כפי שהוא.

**ברירת המחדל בכל ספק היא "עניינית".** סיווג שנכשל (רשת, מפתח, פלט
לא צפוי) לא מוריד אף שאלה מהמסלול המוגן - הוא רק מחזיר את ההתנהגות
הקודמת. ותשובת חולין לא מכילה אף עובדה: ההנחיה אוסרת זאת במפורש, כי
היא לא עוברת דרך שומר הציטוט.

צ'אטבוט חדש מקבל את כל זה על ידי קריאה ל-`preflight()` לפני הכלי שלו.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from client import DEFAULT_MODEL, LLMConfigError, LLMRequestError, complete, complete_stream

Kind = Literal["chitchat", "insult", "substantive"]

# מהיר וזול - סיווג של מילה אחת לפני כל הודעה. ראו CLAUDE.md, מזהי מודלים.
CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
# צ4 (26.9.2026): **התשובה עצמה - המודל הראשי, לא הקטן.** על המודל הקטן
# נמדדו 30 תשובות (tools/chitchat_sample.py) ורובן בעברית מביכה: "מה כולך
# חושב?" (ברק), "בעצם בחרתי!", "אני כאן וחדשפני", "אתה גם בהנאה", "טוב
# לשמוע מך", "בפרלמנט". הסיווג על המודל הקטן היה נכון ב-30 מתוך 30 - נשאר.
REPLY_MODEL = DEFAULT_MODEL

_CLASSIFIER_SYSTEM = (
    "אתה מסווג הודעות שנשלחות לצ'אטבוט בכלי עבודה פרלמנטרי (ניסוח שאילתות, "
    "הצעות לסדר, שאלות על תקנון הכנסת). החזר מילה אחת בלבד, בלי שום דבר נוסף:\n"
    "חולין - תודה, מחמאה, ברכה, שלום, שאלה על הבוט עצמו (מי אתה, מה אתה יודע "
    "לעשות), או תגובה רגשית בלי בקשה.\n"
    "עלבון - קללה, גידוף או עלבון כלפי הבוט.\n"
    "עניינית - כל בקשה או שאלה לגופו של עניין, כולל שאלת דעה, כולל בקשה "
    "לנסח/לשנות/לקצר, וכולל כל הודעה שיש בה גם בקשה וגם נימוס "
    "(\"תודה, ועכשיו תקצר\" היא עניינית).\n"
    "בכל ספק - עניינית."
)
_LABELS: dict[str, Kind] = {"חולין": "chitchat", "עלבון": "insult", "עניינית": "substantive"}

_INSULT_REPLIES = (
    "אני מזכיר, כאן זו לא מליאת הכנסת – נא להתבטא בכבוד 😉",
    "רגע, רגע – זו לא הצבעת אי-אמון. בואו נדבר בכבוד 😉",
    "יושב הראש מזכיר: קריאות ביניים לא נרשמות בפרוטוקול כאן 😉 נא להתבטא בכבוד.",
    "את הסערות נשאיר למליאה – כאן מתבטאים בכבוד 😉",
)

_CHITCHAT_SYSTEM = (
    "אתה {tool} בארגז הכלים הפרלמנטרי. המשתמש כתב הודעת חולין - תודה, מחמאה, "
    "ברכה או שאלה עליך. ענה בעברית, בחום ובקצרה (משפט או שניים), בגוף ראשון, "
    "ומותר אימוג'י אחד. אפשר להזכיר במשפט אחד במה אתה יכול לעזור: {can_do}.\n"
    "**עברית תקנית וטבעית**, כמו שדובר עברית כותב להודעה - לא תרגום מאנגלית "
    "ובלי צירופים מומצאים. סלנג יומיומי מותר, שגיאות לא. \"הכנסת\", לא "
    "\"הפרלמנט\". בלי שאלות המשך מאולצות.\n"
    "**אסור לציין שום עובדה** על חוקים, תקנון, נתונים או הליכים - התשובה הזו "
    "אינה עוברת בדיקת מקורות. בלי כותרות, בלי כוכביות ובלי סימני markdown."
)


@dataclass
class Preflight:
    kind: Kind
    # לעלבון - הטקסט המוכן. לחולין - None: הקורא מזרים/מבקש את התשובה
    # דרך chitchat_reply / chitchat_reply_stream.
    reply: str | None = None


def classify(text: str, *, complete_fn=complete) -> Kind:
    """"chitchat" / "insult" / "substantive". כל כשל -> "substantive"."""
    text = (text or "").strip()
    if not text:
        return "substantive"
    try:
        result = complete_fn(system=_CLASSIFIER_SYSTEM, user_message=text[:2000],
                             max_tokens=10, model=CLASSIFIER_MODEL)
    except (LLMConfigError, LLMRequestError):
        return "substantive"
    word = (result.text or "").strip().strip(".:\"'׳ ")
    return _LABELS.get(word.split()[0] if word else "", "substantive")


def insult_reply(rng: random.Random | None = None) -> str:
    return (rng or random).choice(_INSULT_REPLIES)


def preflight(text: str, *, complete_fn=complete) -> Preflight:
    kind = classify(text, complete_fn=complete_fn)
    if kind == "insult":
        return Preflight(kind, insult_reply())
    return Preflight(kind)


def _chitchat_system(tool: str, can_do: str) -> str:
    return _CHITCHAT_SYSTEM.format(tool=tool, can_do=can_do)


def chitchat_reply(text: str, *, tool: str, can_do: str, complete_fn=complete) -> str:
    try:
        result = complete_fn(system=_chitchat_system(tool, can_do), user_message=text,
                             max_tokens=200, model=REPLY_MODEL)
        return result.text.strip() or "תודה! 😊"
    except (LLMConfigError, LLMRequestError):
        return "תודה! 😊"


def chitchat_reply_stream(text: str, *, tool: str, can_do: str, stream_fn=complete_stream):
    """מניב מחרוזות. בלי RawCompletion בסוף - אין כאן פסק דין לבדוק."""
    from client import RawCompletion  # noqa: PLC0415
    try:
        for piece in stream_fn(system=_chitchat_system(tool, can_do), user_message=text,
                               max_tokens=200, model=REPLY_MODEL):
            if not isinstance(piece, RawCompletion):
                yield piece
    except (LLMConfigError, LLMRequestError):
        yield "תודה! 😊"
