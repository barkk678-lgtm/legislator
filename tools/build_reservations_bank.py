#!/usr/bin/env python3
"""בונה את data/reservations_bank.json מתוך אישורי ברק (docs/bank-approvals-2026-09-26.md).

    python3 tools/build_reservations_bank.py

**המסמך הוא המקור, מילה במילה** - הערכים נקראים ממנו (הרשימות הממוספרות), לא מועתקים
ביד. רשומה קיימת שהמסמך משאיר - נשארת עם המזהה שלה (ופסק השומר שלה, אם הנוסח לא
השתנה); רשומה שהמסמך מוחק - נמחקת; כל השאר - חדשות. כל הרשומות: status "approved",
source "ברק 26.9 (סשן הבנק)".

**רשימה אחת לגורמים ההזויים** (lists.absurd_actors) - גם להחלפת גורם וגם לאישור או
התייעצות; רשומה שמפנה לרשימה (value_list) נפרשת בטעינה לרשומה לכל ערך. **רשימת השרים**
(value_list "ministers") נפרשת בזמן הייצור, מהמאגר (packages/reservations/ministers.py).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "bank-approvals-2026-09-26.md"
BANK = ROOT / "data" / "reservations_bank.json"
SOURCE = "ברק 26.9 (סשן הבנק)"
DOLPHINS = "ועד הדולפינים של הים התיכון"
HUMAN_APPROVAL = {
    "by": "ברק",
    "at": "2026-09-26",
    "why": "אישור מפורש בסשן הבנק (docs/bank-approvals-2026-09-26.md §0.4): approval-047, וכן "
           "\"ועד הדולפינים של הים התיכון\" בכל מקום בבנק. גובר על פסק שומר 86(ד)(2) רק ברשומות "
           "שמסומנות כך; השומר עצמו לא משתנה (חריג לחוק ברזל 7, בהחלטת ברק).",
}
# סבב התיקונים על אישורי הבנק (ברק 26.9.2026, ב2): אותו מנגנון כמו §0.4, לשתי רשומות
# שנחסמו בקו אדום. האישור - **רק לביטוי שהוא מאשר** (redline); קו אדום אחר - עדיין חוסם.
REDLINE_APPROVALS = {
    "verb_modifier-059": "העבודה",      # "בשעות העבודה בלבד" - לא המפלגה
    "conditions-128": "זבל",            # "מי מוריד את הזבל" - לא עלבון
}


def _redline_approval(phrase: str) -> dict:
    return {"by": "ברק", "at": "2026-09-26", "redline": [phrase],
            "why": f"אישור מפורש בסבב התיקונים על אישורי הבנק (ב2): \"{phrase}\" ברשומה הזו אינו "
                   "הפרת קו אדום. אותו מנגנון כמו §0.4; גובר רק על הביטוי הזה ורק ברשומה הזו."}


APPROVAL_FORMS = ["באישור {value}", "בכפוף לאישור {value}", "בהתייעצות עם {value}",
                  "לאחר התייעצות עם {value}", "בהסכמת {value}"]
GENDER = {"ז": "m", "נ": "f"}


def _lines(text: str, start: str, end: str) -> list[str]:
    """השורות שבין כותרת `start` לכותרת `end` (לא כולל)."""
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j].splitlines()


def _numbered(lines: list[str]) -> list[str]:
    """פריטים ממוספרים ("12. ..."), כולל שורות המשך. אימות: 1, 2, 3... ברצף."""
    items, n = [], 0
    for line in lines:
        m = re.match(r"^(\d+)\. (.+)$", line.strip())
        if m:
            n += 1
            if int(m.group(1)) != n:
                raise SystemExit(f"מספור שבור אחרי {n - 1}: {line!r}")
            items.append(m.group(2).strip())
        elif items and line.startswith("   ") and line.strip():
            items[-1] += " " + line.strip()
    return items


def parse(doc: str) -> dict:
    out = {}
    # §1 הזוי - 106, עם מין דקדוקי
    actors = []
    for item in _numbered(_lines(doc, "### הזוי — 106", "## 2. תנאים")):
        m = re.match(r"^(.+?) \((ז|נ)\)$", item)
        if not m:
            raise SystemExit(f"גורם בלי מין דקדוקי: {item!r}")
        actors.append((m.group(1), GENDER[m.group(2)]))
    out["absurd_actors"] = actors
    out["conditions_clever"] = _numbered(_lines(doc, "### מתחכם — 30", "### הזוי — 116"))
    out["conditions_absurd"] = _numbered(_lines(doc, "### הזוי — 116", "## 3. סעיפים"))
    out["after_serious"] = _numbered(_lines(doc, "### רציני — 20\nקיימות", "### מתחכם — 50\nקיימות"))
    out["after_clever"] = _numbered(_lines(doc, "### מתחכם — 50\nקיימות", "### הזוי — 100\nקיימות"))
    out["after_absurd"] = _numbered(_lines(doc, "### הזוי — 100\nקיימות", "## 4. אישור"))
    out["approval_clever"] = _numbered(_lines(doc, "### מתחכם — 22 גופים", "### הזוי — גופים"))
    duty_block = "\n".join(_lines(doc, "## 5. חובה ורשות", "**ועוד צמד:**"))
    out["duty_pairs"] = re.findall(r"(\S+)↔(רשאי \S+)", duty_block)
    out["vm_serious"] = _numbered(_lines(doc, "### רציני — 20\n1. בכתב", "### מתחכם — 50\n1. בהקדם"))
    out["vm_clever"] = _numbered(_lines(doc, "### מתחכם — 50\n1. בהקדם", "### הזוי — 100\n1. בעמידה"))
    out["vm_absurd"] = _numbered(doc[doc.index("### הזוי — 100\n1. בעמידה"):].splitlines())
    return out


def build() -> dict:
    doc = DOC.read_text(encoding="utf-8")
    p = parse(doc)
    old = {r["id"]: r for r in json.loads(BANK.read_text(encoding="utf-8"))["records"]}
    records: list[dict] = []
    counters: dict[str, int] = {}

    used: set[str] = set()

    def keep(rid: str, **changes):
        used.add(rid)
        r = dict(old[rid])
        r.update(status="approved", source=SOURCE, **changes)
        records.append(r)

    # **אידמפוטנטי** (סבב התיקונים, 26.9): רשומה שכבר קיימת באותו תוכן (משפחה, רמה, תבנית,
    # ערך, רשימה) - שומרת את המזהה שלה; רק תוכן חדש מקבל מזהה חדש. בלי זה, הרצה חוזרת על
    # הבנק שכבר נבנה שכפלה אותו (חובה ורשות: 264 במקום 104) - ופסקי השומר אבדו.
    by_content = {(r["family"], r["level"], r["template"], r["value"], r.get("value_list", "")): rid
                  for rid, r in old.items()}

    def new(family: str, level: str, template: str, value: str, **extra):
        rid = by_content.get((family, level, template, value, extra.get("value_list", "")))
        if rid is None or rid in used:
            counters[family] = counters.get(family, max(
                [int(k.rsplit("-", 1)[1]) for k in old if k.startswith(family + "-")] or [0]))
            counters[family] += 1
            rid = f"{family}-{counters[family]:03d}"
        used.add(rid)
        r = {"id": rid, "level": level, "family": family,
             "template": template, "value": value, "status": "approved", "source": SOURCE, **extra}
        records.append(r)

    # ── §1 החלפת גורם ──────────────────────────────────────────────
    for rid, g in (("actor_swap-003", "m"), ("actor_swap-004", "f"), ("actor_swap-005", "m"),
                   ("actor_swap-006", "m")):
        keep(rid, gender=g)
    new("actor_swap", "serious", "{value}", "", value_list="ministers", gender="m")
    for value, g in (("סגן {שר}", "m"), ("המנהל הכללי של {משרד}", "m"), ("ועדה ציבורית שימנה {שר}", "f"),
                     ("נציב שירות המדינה", "m"), ("רשם העמותות", "m")):
        new("actor_swap", "clever", "{value}", value, gender=g)
    new("actor_swap", "absurd", "{value}", "", value_list="absurd_actors")

    # ── §2 תנאים ──────────────────────────────────────────────────
    for rid in ("conditions-005", "conditions-006", "conditions-007", "conditions-008"):
        keep(rid)
    for v in p["conditions_clever"]:
        new("conditions", "clever", "ובלבד ש{value}", v)
    for rid in ("conditions-009", "conditions-010", "conditions-011", "conditions-012"):
        keep(rid)
    for v in p["conditions_absurd"]:
        new("conditions", "absurd", "ובלבד ש{value}", v)

    # ── §3 סעיפים אחרי הסעיף האחרון ───────────────────────────────
    keep("after_last-001", value="ביום 1 בינואר {השנה הבאה}")         # התיקון: שנה מחושבת (0.2)
    for rid in ("after_last-002", "after_last-005", "after_last-008", "after_last-009", "after_last-012"):
        keep(rid)
    for v in p["after_serious"]:
        new("after_last", "serious", v, "")
    for rid in ("after_last-003", "after_last-006", "after_last-010", "after_last-013"):
        keep(rid)
    for v in p["after_clever"]:
        new("after_last", "clever", v, "")
    for rid in ("after_last-004", "after_last-007", "after_last-011", "after_last-014"):
        keep(rid)
    for v in p["after_absurd"]:
        new("after_last", "absurd", v, "")

    # ── §4 אישור או התייעצות - גופים × 5 צורות ─────────────────────
    existing = {(r["template"], r["value"]): rid for rid, r in old.items() if r["family"] == "approval"}
    deleted_bodies = {"מועצת הזקנים של השבט הסנאי בפארק הירקון",     # נמחקות 010/022/034/046
                      "שר האוצר",                                    # נבלע ברשימת השרים
                      DOLPHINS}                                      # פעם אחת - ברשימה המשותפת
    bodies = {
        "serious": ["{committee} של הכנסת", "ועדת הכספים של הכנסת", "היועץ המשפטי לממשלה",
                    "מבקר המדינה", "הממשלה"],
        "clever": ["80% מבעלי המסעדות בישראל", "כלל מדריכי היוגה בישראל",
                   "רוב מוחלט של ועד ההורים הארצי", "60% ממורי ומורות ישראל"] + p["approval_clever"],
        "absurd": ["דמבלדור והוועד המנהל של הוגוורטס", "איגוד שומרי הגמדים הלאומי"],
    }
    for level, names in bodies.items():
        for form in APPROVAL_FORMS:
            for body in names:
                rid = existing.get((form, body))
                if rid:
                    keep(rid)
                else:
                    new("approval", level, form, body)
            if level == "serious":
                new("approval", level, form, "", value_list="ministers")
            if level == "absurd":
                new("approval", level, form, "", value_list="absurd_actors")
    assert not any(r["value"] in deleted_bodies for r in records if r["family"] == "approval")

    # ── §5 חובה ורשות - 24 הקיימות, 14 פעלים בשני הכיוונים, והצמד "חייב" ─────
    for rid in (f"duty-{i:03d}" for i in range(1, 25)):             # 24 הקיימות (לפני אישורי הבנק)
        keep(rid)
    for verb, permitted in p["duty_pairs"]:
        new("duty", "serious", "{value}", f"{verb}=>{permitted}")
        new("duty", "serious", "{value}", f"{permitted}=>{verb}")
    duty_verbs = [r["value"].split("=>")[1] for r in records
                  if r["family"] == "duty" and r["value"].split("=>")[0][:1] != "ר"]
    for permitted in duty_verbs:                                  # "רשאי לתקן" -> "חייב לתקן"
        must = "חייב " + permitted.split(" ", 1)[1]
        new("duty", "serious", "{value}", f"{must}=>{permitted}")
        new("duty", "serious", "{value}", f"{permitted}=>{must}")

    # ── §6 תוספת לפועל ────────────────────────────────────────────
    for level, key in (("serious", "vm_serious"), ("clever", "vm_clever"), ("absurd", "vm_absurd")):
        for v in p[key]:
            new("verb_modifier", level, "{value}", v)

    # ── §0.4 ועד הדולפינים - אישור אנושי מפורש ──────────────────────
    for r in records:
        if DOLPHINS in r["template"] + r["value"]:
            r["human_approval"] = HUMAN_APPROVAL
    for r in records:
        if r["id"] in REDLINE_APPROVALS:
            r["human_approval"] = _redline_approval(REDLINE_APPROVALS[r["id"]])
    actors = [{"id": f"actor-{i:03d}", "value": v, "gender": g,
               **({"human_approval": HUMAN_APPROVAL} if v == DOLPHINS else {})}
              for i, (v, g) in enumerate(p["absurd_actors"], 1)]
    return {
        "_doc": "בנק התוכן של כלי ההסתייגויות. המקור: docs/bank-approvals-2026-09-26.md (אישורי ברק, "
                "26.9) - נבנה ב-tools/build_reservations_bank.py. רק status 'approved' מגיע לפלט. "
                "{committee} / {הוועדה} - הוועדה מעמוד השער; {השר} - לפי הכרעה ד; {שר} / {משרד} "
                "(בהחלפת גורם, מתחכם) - השר שבהצעה ומשרדו; {השנה הבאה} / {השנה שאחרי הבאה} - "
                "ממועד הייצור. value_list: 'absurd_actors' - הרשימה המשותפת כאן; 'ministers' - "
                "רשימת השרים מהמאגר. gender: m/f - מין דקדוקי של הגורם. human_approval - אישור אנושי "
                "מפורש (§0.4). בחובה/רשות הערך הוא 'מ=>אל'. בסעיף אחרי הסעיף האחרון התבנית היא "
                "'כותרת שוליים|נוסח'. levels: serious=רציני, clever=מתחכם, absurd=הזוי.",
        "lists": {"absurd_actors": actors},
        "records": records,
    }


def main() -> int:
    data = build()
    BANK.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter  # noqa: PLC0415
    print(Counter((r["family"], r["level"]) for r in data["records"]))
    print(len(data["lists"]["absurd_actors"]), "גורמים הזויים")
    return 0


if __name__ == "__main__":
    sys.exit(main())
