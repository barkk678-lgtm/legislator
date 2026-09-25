"""תמחור ההסתייגויות (הסתייגויות 4, 26.9) - הערכים בהגדרות, לא בקוד.

config/reservations.json: 50 כלולות בכל הצעה; מעבר לזה $10 לכל 100 נוספות
(או חלק מהן). **המחיר זמני** - משנים את הקובץ.

**התשלום מדומה, ובבטחה.** אין בשום מקום שדה של כרטיס אשראי או פרטי תשלום -
אסור לאסוף אותם לפני שיש חברת סליקה. payment_mode:
- "demo" - הכפתור ממשיך ישר, עם סימון גלוי שזה מצב הדגמה;
- "live" - יום שתהיה סליקה. עד אז: ייצור מעבר לכלול נחסם, עם הודעה.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "reservations.json"


def config() -> dict:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def price_usd(count: int, cfg: dict | None = None) -> int:
    cfg = cfg or config()
    extra = max(0, int(count) - int(cfg["included"]))
    return math.ceil(extra / int(cfg["block_size"])) * int(cfg["price_per_block_usd"])


__all__ = ["config", "price_usd"]
