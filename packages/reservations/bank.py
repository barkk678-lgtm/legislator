"""בנק התוכן של כלי ההסתייגויות (הסתייגויות 3, 26.9).

**המודל לעולם לא כותב טקסט שמגיע לפלט.** כל מילה בהסתייגות מגיעה מהצעת
החוק, מתבנית קבועה, או מבנק שברק אישר - זו ההגנה על סעיף 86(ד)(2) לתקנון,
והיא נשארת מבנית גם ברמת "הזוי".

**קובץ נתונים, לא קוד:** data/reservations_bank.json. כל רשומה: רמה, משפחה,
תבנית, ערך, סטטוס אישור, מקור. **רק `approved` מגיעה לפלט.** המשפחות שתלויות
בבנק לא מייצרות דבר עד שברק מאשר; השאר (שינוי ערך, מחיקה) עובדות.

**שלושה מחסומים בטעינה, כולם חוסמים (לא מסמנים):**
1. סטטוס - רק `approved`.
2. קווים אדומים (data/reservations_redlines.json) - אנשים אמיתיים, מפלגות,
   כלי תקשורת, קבוצות דתיות/אתניות, ערים ויישובים, עלבונות. בכל הרמות.
3. שומר 86(ד)(2) - הסינון (guards.screen_text, רשימה + מודל) רץ **מראש**, בכלי
   הסקירה (tools/reservations_bank_review.py), והפסק נשמר לפי גיבוב הנוסח
   (data/reservations_bank_screen.json). רשומה בלי פסק "עבר" לנוסח הנוכחי שלה -
   נחסמת. כך הטעינה דטרמיניסטית, ורשומה ששונתה אחרי הסינון לא עוברת בשקט.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANK_PATH = ROOT / "data" / "reservations_bank.json"
REDLINES_PATH = ROOT / "data" / "reservations_redlines.json"
SCREEN_PATH = ROOT / "data" / "reservations_bank_screen.json"

LEVELS = {"serious": "רציני", "clever": "מתחכם", "absurd": "הזוי"}

# §0.2 (אישורי ברק, 26.9): שנה מחושבת - ממועד הייצור, לפי Asia/Jerusalem, כמספר
# ("ביום 1 בינואר 2027"). לעולם לא "של השנה הבאה". בזמן הרינדור - הגיבוב של
# הרשומה (ופסק השומר) לא משתנה משנה לשנה.
JERUSALEM = ZoneInfo("Asia/Jerusalem")


def _now() -> datetime:
    return datetime.now(JERUSALEM)


def _years(text: str) -> str:
    if "{השנה" not in text:
        return text
    year = _now().astimezone(JERUSALEM).year
    return text.replace("{השנה שאחרי הבאה}", str(year + 2)).replace("{השנה הבאה}", str(year + 1))
BANK_FAMILIES = ("actor_swap", "approval", "duty", "conditions", "after_last")


@dataclass(frozen=True)
class Record:
    id: str
    level: str
    family: str
    template: str
    value: str
    status: str
    source: str = ""

    def text(self, committee: str = "") -> str:
        """הנוסח שהרשומה מוסיפה (בלי ההצעה). {committee} - מעמוד השער."""
        value = _join(self.value, "{committee}", committee or "{committee}")
        return _years(_join(self.template, "{value}", value))

    @property
    def screen_key(self) -> str:
        return hashlib.sha1(f"{self.template}\x1f{self.value}".encode("utf-8")).hexdigest()[:16]


# אות שימוש לפני מילה שמתחילה ב-ו' - הוו' מוכפלת: "ל" + "ועדת" = "לוועדת" (כך בטבריה:
# "בוועדת הפנים", הסתייגות 47/ב). בלי זה יצא "לועדת הפנים" (נמצא בבדיקת הצורות, 26.9).
_PREFIX_BEFORE = re.compile(r"(?:^|(?<=[^א-ת]))[ובלמכשה]{1,2}$")


def _join(template: str, placeholder: str, value: str) -> str:
    out, rest = [], template
    while placeholder in rest:
        head, rest = rest.split(placeholder, 1)
        if value.startswith("ו") and not value.startswith("וו") and _PREFIX_BEFORE.search(head):
            head += "ו"
        out += [head, value]
    return "".join(out) + rest


@dataclass(frozen=True)
class Blocked:
    record: Record
    reason: str


def _word_re(phrase: str) -> re.Pattern:
    # מילה שלמה, עם אותיות שימוש אופציונליות לפניה ("ולליכוד", "בטבריה").
    return re.compile(rf"(?<![א-ת])(?:[ובלמכשה]{{0,2}}){re.escape(phrase)}(?![א-ת])")


@lru_cache(maxsize=1)
def _redlines() -> list[tuple[str, re.Pattern, str]]:
    data = json.loads(REDLINES_PATH.read_text(encoding="utf-8"))
    rules = []
    for category in ("people", "parties", "media", "groups", "places", "insults"):
        for phrase in data.get(category, []):
            rules.append((category, _word_re(phrase), phrase))
    for pattern in data.get("place_patterns", []):
        rules.append(("places", re.compile(pattern), pattern))
    return rules


_CATEGORY_HE = {"people": "אדם אמיתי", "parties": "מפלגה", "media": "כלי תקשורת",
                "groups": "קבוצה דתית או אתנית", "places": "עיר או יישוב", "insults": "עלבון"}


def redline_violation(text: str) -> str:
    """הסיבה, או "" אם אין הפרה."""
    for category, rx, phrase in _redlines():
        if rx.search(text):
            return f"קו אדום - {_CATEGORY_HE[category]}: {phrase!r}"
    return ""


def _screen_verdicts() -> dict:
    if not SCREEN_PATH.exists():
        return {}
    return json.loads(SCREEN_PATH.read_text(encoding="utf-8")).get("verdicts", {})


def load_all() -> list[Record]:
    data = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    return [Record(**{k: r.get(k, "") for k in Record.__dataclass_fields__}) for r in data["records"]]


def check(record: Record, verdicts: dict | None = None) -> str:
    """"" - הרשומה מותרת לפלט; אחרת - הסיבה שהיא חסומה."""
    if record.level not in LEVELS:
        return f"רמה לא מוכרת: {record.level!r}"
    if record.family not in BANK_FAMILIES:
        return f"משפחה לא מוכרת: {record.family!r}"
    if record.status != "approved":
        return "ממתינה לאישור" if record.status == "pending" else f"סטטוס: {record.status}"
    red = redline_violation(record.text("ועדה"))
    if red:
        return red
    verdicts = _screen_verdicts() if verdicts is None else verdicts
    verdict = verdicts.get(record.id) or {}
    if verdict.get("key") != record.screen_key:
        return "לא עבר את שומר 86(ד)(2) על הנוסח הנוכחי (הריצו tools/reservations_bank_review.py)"
    if not verdict.get("allowed"):
        return f"נחסם בשומר 86(ד)(2): {verdict.get('reason', '')}"
    return ""


def load(level: str) -> tuple[list[Record], list[Blocked]]:
    """הרשומות המותרות לרמה, ואלה שנחסמו (עם הסיבה)."""
    verdicts = _screen_verdicts()
    allowed, blocked = [], []
    for record in load_all():
        if record.level != level:
            continue
        reason = check(record, verdicts)
        (blocked.append(Blocked(record, reason)) if reason else allowed.append(record))
    return allowed, blocked


__all__ = ["BANK_FAMILIES", "Blocked", "LEVELS", "Record", "check", "load", "load_all", "redline_violation"]
