"""רשימת השרים - משתנה, לא רשימה קבועה (אישורי הבנק §0.1, ברק 26.9.2026).

**ממאגר הכנסת:** משרדים פעילים (`KNS_GovMinistry`, IsActive) שיש להם שר או שרה מכהנים
(`KNS_PersonToPosition`, IsCurrent, משרה 39 "שר" / 57 "שרה"). אותו דפוס כמו יו"ר
הכנסת בהצעה לסדר (apps/api/knesset_speaker.py): מטמון 12 שעות, קובץ גיבוי
(data/ministers_fallback.json - **מהמאגר**, לא מהרשימה שבמסמך), ורישום ביומן כשנופלים
לגיבוי. עימוד - דרך `@odata.nextLink` (odata.fetch). **כשתושבע ממשלה חדשה או ישתנה
שם משרד - הרשימה מתעדכנת מעצמה**, בלי שינוי קוד.

**התואר נגזר דטרמיניסטית משם המשרד**, ובחזרה:
    "משרד X"            <-> "שר X"
    "המשרד ל-X"          <-> "השר ל-X"
    "משרד ראש הממשלה"   <-> "ראש הממשלה"   (ברשימה הקבועה ממילא - בלי כפילות)
צורה אחרת - אין תואר (None). התואר תמיד בלשון זכר, כמו בחקיקה; מין דקדוקי: זכר.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "knesset"))
from odata import OdataError, fetch  # noqa: E402

log = logging.getLogger(__name__)

MINISTER_POSITION_IDS = (39, 57)          # שר / שרה
PRIME_MINISTER = "ראש הממשלה"
PM_OFFICE = "משרד ראש הממשלה"
_OK_TTL = 12 * 3600
_FAIL_TTL = 600
FALLBACK_PATH = ROOT / "data" / "ministers_fallback.json"

_cache: tuple[float, dict] | None = None
_failed_at = 0.0


def minister_title(ministry: str) -> str | None:
    """"משרד הפנים" -> "שר הפנים"; "המשרד לביטחון לאומי" -> "השר לביטחון לאומי";
    "משרד ראש הממשלה" -> "ראש הממשלה". אחרת - None."""
    name = " ".join((ministry or "").split())
    if name == PM_OFFICE:
        return PRIME_MINISTER
    if name.startswith("המשרד ל") and len(name) > len("המשרד ל"):
        return "השר ל" + name[len("המשרד ל"):]
    if name.startswith("משרד ") and len(name) > len("משרד "):
        return "שר " + name[len("משרד "):]
    return None


def ministry_of(title: str) -> str | None:
    """הכיוון ההפוך (ל-{משרד}): "שר הפנים" -> "משרד הפנים"; "השר לביטחון לאומי" ->
    "המשרד לביטחון לאומי"; "ראש הממשלה" -> "משרד ראש הממשלה". אחרת - None
    ("השר" לבדו, "סגן שר הפנים", "שרת הפנים" - אין משרד)."""
    name = " ".join((title or "").split())
    if name == PRIME_MINISTER:
        return PM_OFFICE
    if name.startswith("השר ל") and len(name) > len("השר ל"):
        return "המשרד ל" + name[len("השר ל"):]
    if name.startswith("שר ") and len(name) > len("שר "):
        return "משרד " + name[len("שר "):]
    return None


def _titles(ministries: list[str]) -> list[str]:
    out = []
    for m in ministries:
        t = minister_title(m)
        if t and t != PRIME_MINISTER and t not in out:     # ראש הממשלה - ברשימה הקבועה
            out.append(t)
    return sorted(out)


def _from_feed() -> dict:
    ids = " or ".join(f"PositionID eq {i}" for i in MINISTER_POSITION_IDS)
    rows = fetch("KNS_PersonToPosition", filter=f"IsCurrent eq true and GovMinistryID ne null and ({ids})",
                 select="GovMinistryID")
    with_minister = {r["GovMinistryID"] for r in rows if r.get("GovMinistryID")}
    active = fetch("KNS_GovMinistry", filter="IsActive eq true", select="Id,Name")
    ministries = sorted(a["Name"] for a in active if a.get("Id") in with_minister and a.get("Name"))
    if not ministries:
        raise OdataError("לא נמצא אף משרד פעיל עם שר מכהן")
    return {"ministries": ministries, "titles": _titles(ministries), "source": "feed"}


def _fallback() -> dict:
    data = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
    return {"ministries": data["ministries"], "titles": _titles(data["ministries"]), "source": "fallback"}


def current_ministers() -> dict:
    """{"ministries": [...], "titles": ["שר הפנים", ...], "source": "feed"/"fallback"}."""
    global _cache, _failed_at
    if os.environ.get("LEGISLATOR_MINISTERS_SOURCE") == "fallback":
        return _fallback()           # בדיקות: רשימה קבועה מקובץ הגיבוי, בלי רשת
    now = time.time()
    if _cache and now - _cache[0] < _OK_TTL:
        return _cache[1]
    if now - _failed_at < _FAIL_TTL:
        return _fallback()
    try:
        found = _from_feed()
    except (OdataError, KeyError, ValueError, OSError) as e:
        _failed_at = now
        log.warning("שליפת רשימת השרים מהמאגר נכשלה - משתמש בגיבוי: %s", e)
        return _fallback()
    _cache = (now, found)
    return found


def titles() -> list[str]:
    return current_ministers()["titles"]


def refresh_fallback() -> dict:
    """בונה את קובץ הגיבוי מהמאגר (לא מהרשימה שבמסמך)."""
    found = _from_feed()
    FALLBACK_PATH.write_text(json.dumps({
        "_doc": "גיבוי לרשימת השרים (אישורי הבנק §0.1) - משרדים פעילים עם שר מכהן, ממאגר הכנסת. "
                "נבנה ב-packages/reservations/ministers.refresh_fallback; משמש רק כשהמאגר לא זמין.",
        "fetched_at": datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d"),
        "ministries": found["ministries"]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return found


__all__ = ["current_ministers", "minister_title", "ministry_of", "refresh_fallback", "titles"]
