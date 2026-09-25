"""ס4 (26.9.2026) - יו"ר הכנסת, שאליו ממוענת הצעה לסדר היום.

היו"ר מתחלף (הבחירות לכנסת ה-26 בפתח), ולכן השם אינו קבוע בקוד. **שליפה
ממאגר הכנסת**: KNS_PersonToPosition במשרה 122 ("יושב–ראש הכנסת") או 123
("יושבת–ראש הכנסת") עם IsCurrent, ואז KNS_Person לשם ולמגדר. נבדק מול
המאגר (26.9): רשומה אחת, PersonID 30300 - אמיר אוחנה, זכר, מ-29.12.2022.

**במטמון, לא בכל הודעה:** הצלחה - 12 שעות; כישלון - 10 דקות, ובינתיים
הגיבוי הידני (speaker_fallback.json), עם רישום ביומן. המקור מוחזר תמיד
("feed" / "fallback"), כדי שהממשק והבדיקות ידעו מה נכתב בקובץ.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "knesset"))
from odata import OdataError, fetch  # noqa: E402

log = logging.getLogger(__name__)

SPEAKER_POSITION_IDS = (122, 123)      # יושב–ראש / יושבת–ראש הכנסת
_OK_TTL = 12 * 3600
_FAIL_TTL = 600
FALLBACK_PATH = Path(__file__).resolve().parent / "speaker_fallback.json"

_cache: tuple[float, dict] | None = None
_failed_at = 0.0


def _fallback() -> dict:
    data = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
    return {"name": data["name"], "gender": data.get("gender"), "source": "fallback"}


def _from_feed() -> dict:
    ids = ",".join(str(i) for i in SPEAKER_POSITION_IDS)
    rows = fetch("KNS_PersonToPosition", filter=f"PositionID in ({ids}) and IsCurrent eq true",
                 select="PersonID,PositionID")
    people = {r["PersonID"] for r in rows if r.get("PersonID")}
    if len(people) != 1:
        raise OdataError(f"ציפיתי ליו\"ר מכהן אחד, נמצאו {len(people)}")
    person_id = people.pop()
    person = fetch("KNS_Person", filter=f"Id eq {person_id}", select="FirstName,LastName,GenderDesc")
    if not person:
        raise OdataError(f"אין רשומת אדם {person_id}")
    p = person[0]
    name = " ".join(f"{p.get('FirstName') or ''} {p.get('LastName') or ''}".split())
    if not name:
        raise OdataError(f"רשומת אדם {person_id} בלי שם")
    gender = p.get("GenderDesc") if p.get("GenderDesc") in ("זכר", "נקבה") else None
    return {"name": name, "gender": gender, "source": "feed"}


def current_speaker() -> dict:
    """{"name", "gender" ("זכר"/"נקבה"/None), "source" ("feed"/"fallback")}."""
    global _cache, _failed_at
    now = time.time()
    if _cache and now - _cache[0] < _OK_TTL:
        return _cache[1]
    if now - _failed_at < _FAIL_TTL:
        return _fallback()
    try:
        found = _from_feed()
    except (OdataError, KeyError, ValueError) as e:
        _failed_at = now
        log.warning("שליפת יו\"ר הכנסת מהמאגר נכשלה - משתמש בגיבוי הידני: %s", e)
        return _fallback()
    _cache = (now, found)
    return found
