#!/usr/bin/env python3
"""כלי הסקירה של בנק ההסתייגויות (הסתייגויות 3, 26.9).

    python3 tools/reservations_bank_review.py            # שומר 86(ד)(2) + קובץ הסקירה
    python3 tools/reservations_bank_review.py --no-screen # רק קובץ הסקירה

1. **שומר 86(ד)(2)** (guards.screen_text - רשימה + מודל, fail-closed) על כל רשומה
   שאין לה פסק לנוסח הנוכחי. הפסק נשמר ב-data/reservations_bank_screen.json לפי
   גיבוב התבנית והערך - רשומה ששונתה אחרי הסינון נחסמת עד שתסונן שוב.
2. **קובץ הסקירה** - docs/reservations-bank-review.md: כל הרשומות, לפי משפחה
   ורמה, עם הנוסח כפי שייראה, הסטטוס, המקור, והחסימות (קו אדום / שומר).
   ברק מאשר - וה-status של הרשומה ב-data/reservations_bank.json הופך ל-"approved".

הוועדה בתבנית ({committee}) מוצגת כאן כ"ועדת הפנים והגנת הסביבה" - הדוגמה
מטבריה. בפועל היא נלקחת מעמוד השער של כל הצעה.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))
sys.path.insert(0, str(ROOT / "packages" / "config"))

import agreement  # noqa: E402
import bank  # noqa: E402
import guards  # noqa: E402

SAMPLE_COMMITTEE = "ועדת הפנים והגנת הסביבה"
REVIEW = ROOT / "docs" / "reservations-bank-review.md"
FAMILY_HE = {"actor_swap": "החלפת גורם", "approval": "הוספת אישור או התייעצות", "duty": "חובה ורשות",
             "conditions": "תנאים", "after_last": "סעיפים אחרי הסעיף האחרון", "verb_modifier": "תוספת לפועל"}
FAMILY_EXAMPLE = {
    "actor_swap": 'במקום "שר הפנים" יבוא "{text}".',
    "approval": 'אחרי "שר הפנים" יבוא "{text}".',
    "duty": 'במקום "{src}" יבוא "{dst}".',
    "conditions": 'בפסקה (2), בסופה יבוא "{text}".',
    "after_last": 'אחרי הסעיף יבוא: "{margin} 4. {body}"',
    "verb_modifier": 'במקום "יתקן" יבוא "יתקן {text}".',
}
SAMPLE_MINISTER, SAMPLE_MINISTRY = "שר הפנים", "משרד הפנים"


def _sample(text: str) -> str:
    """המשתנים כפי שייראו בטבריה: {השר}/{שר} - שר הפנים, {משרד} - משרד הפנים."""
    return (text.replace("{השר}", SAMPLE_MINISTER).replace("{שר}", SAMPLE_MINISTER)
            .replace("{משרד}", SAMPLE_MINISTRY))


SCREEN_MINISTER = "שר האוצר"          # רשימת השרים בסינון - תואר אמיתי אחד (התארים עצמם - קווים אדומים)


def screened_text(r: bank.Record) -> str:
    """**מה שהשומר קורא: ההסתייגות המלאה, כמו שתופיע בפלט** (סבב התיקונים, 26.9.2026) -
    ולא הקטע החשוף ("בחלום", "הדוור של הקוטב הצפוני"), שבלי הקשר נקרא כפנייה בצ'אט."""
    return _example(r).replace("{כל שר מרשימת השרים במאגר}", SCREEN_MINISTER)


def _example(r: bank.Record) -> str:
    text = r.text(SAMPLE_COMMITTEE)
    if r.value_list == "ministers":
        text = text.replace(bank.MINISTER_PLACEHOLDER, "{כל שר מרשימת השרים במאגר}")
    text = _sample(text)
    if r.family == "duty":
        src, _, dst = r.value.partition("=>")
        return FAMILY_EXAMPLE["duty"].format(src=src, dst=dst)
    if r.family == "actor_swap" and (r.gender or agreement.gender(text)) == "f":
        # הכרעה ג: גורם בלשון נקבה - גם הפועל שאחריו מותאם (טבריה, סעיף 3: "שר הפנים יתקן")
        return f'במקום "שר הפנים יתקן" יבוא "{text} {agreement.inflect("יתקן", "f")}".'
    if r.family == "after_last":
        margin, _, body = text.partition("|")
        return FAMILY_EXAMPLE["after_last"].format(margin=margin, body=body)
    return FAMILY_EXAMPLE[r.family].format(text=text)


def _save(verdicts: dict) -> None:
    bank.SCREEN_PATH.write_text(json.dumps(
        {"_doc": "פסקי שומר 86(ד)(2) על רשומות הבנק - tools/reservations_bank_review.py. "
                 "key = גיבוב התבנית והערך; רשומה ששונתה נחסמת עד סינון חוזר.",
         "verdicts": dict(sorted(verdicts.items()))}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


_SERVICE_FAILURE = ("הסינון נכשל", "שכבת הסינון אינה זמינה")


def screen(records: list[bank.Record], workers: int = 8, rescreen_all: bool = False) -> dict:
    """**כל רשומה חדשה או ששונתה** (אין לה פסק לגיבוב הנוכחי) - דרך השומר. פסקים של
    רשומות שלא השתנו - נשמרים. נשמר כל 100 פסקים (ריצה ארוכה). rescreen_all - **כל**
    הבנק מחדש, מאפס (קריאה חדשה של השומר - סבב הסגירה, 26.9.2026).

    **כשל שירות אינו פסק:** קריאה שנכשלה (רשת, מכסה) לא נשמרת כפסק - הרשומה נשארת בלי
    פסק (ולכן חסומה, fail-closed) ומנוסה פעם אחת נוספת בסוף."""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
    data = json.loads(bank.SCREEN_PATH.read_text(encoding="utf-8")) if bank.SCREEN_PATH.exists() else {}
    verdicts = {} if rescreen_all else data.get("verdicts", {})
    todo = [r for r in records if verdicts.get(r.id, {}).get("key") != r.screen_key]
    print(f"לסינון: {len(todo)} מתוך {len(records)}", flush=True)

    def one(r):
        return r, guards.screen_text(screened_text(r))

    for attempt in (1, 2):
        failed = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for n, (r, v) in enumerate(pool.map(one, todo), 1):
                if not v.allowed and v.reason.startswith(_SERVICE_FAILURE):
                    failed.append(r)
                    continue
                verdicts[r.id] = {"key": r.screen_key, "allowed": v.allowed, "reason": v.reason}
                if not v.allowed:
                    print(f"  {r.id}: נחסם - {v.reason}", flush=True)
                if n % 100 == 0:
                    _save(verdicts)
                    print(f"  ... {n}/{len(todo)}", flush=True)
        if not failed:
            break
        print(f"  כשל שירות ב-{len(failed)} רשומות (ניסיון {attempt}) - לא נשמר כפסק", flush=True)
        todo = failed
    live = {r.id for r in records}
    verdicts = {k: v for k, v in verdicts.items() if k in live}    # רשומות שנמחקו - בלי פסק
    _save(verdicts)
    return verdicts


def write_review(records: list[bank.Record], verdicts: dict) -> None:
    lines = ["# בנק ההסתייגויות - קובץ סקירה", "",
             "נוצר אוטומטית: `python3 tools/reservations_bank_review.py`. **הקובץ הזה אינו",
             "מקור האמת** - הבנק עצמו ב-`data/reservations_bank.json`, שנבנה מאישורי ברק",
             "(`docs/bank-approvals-2026-09-26.md`) ב-`tools/build_reservations_bank.py`.", "",
             "**רק רשומה מאושרת ושעברה את הסינון מגיעה לפלט.** \"דוגמה\" - איך הרשומה נראית",
             "בהסתייגות, על ההצעה של טבריה (הוועדה - מעמוד השער; {השר} - שר הפנים). **חסימה** -",
             "קו אדום או שומר 86(ד)(2): רשומה חסומה **נשארת חסומה** ומופיעה ברשימה למטה, עם",
             "הסיבה. החריג היחיד - אישור אנושי מפורש של ברק ברשומה עצמה (§0.4, ועד הדולפינים",
             "של הים התיכון).", ""]
    counts = {}
    for r in records:
        counts.setdefault((r.family, r.level), 0)
        counts[(r.family, r.level)] += 1
    lines += ["| משפחה | " + " | ".join(bank.LEVELS.values()) + " |", "|---|---|---|---|"]
    for fam, fam_he in FAMILY_HE.items():
        lines.append(f"| {fam_he} | " + " | ".join(str(counts.get((fam, lv), 0)) for lv in bank.LEVELS) + " |")
    lines.append("")

    def raw_block(r):
        """מה היה חוסם בלי אישור אנושי: קו אדום, או פסק השומר."""
        red = bank.redline_violation(r.text(SAMPLE_COMMITTEE))
        v = verdicts.get(r.id, {})
        screen_note = "" if v.get("key") == r.screen_key and v.get("allowed") else (
            f"86(ד)(2): {v.get('reason') or 'לא סונן'}")
        return red or screen_note

    # **ההכרעה עצמה - bank.check**, אותה פונקציה שמחליטה מה מגיע לפלט; כך הרשימה כאן לא
    # יכולה לסטות מהפלט (אישור אנושי, פטור לתארים רשמיים).
    blocked, overridden = [], []
    for r in records:
        raw, final = raw_block(r), bank.check(r, verdicts)
        if final:
            blocked.append((r, final))
        elif raw:
            overridden.append((r, raw))
    # רשימת השרים (מהמאגר) - התארים נבדקים בקווים האדומים בזמן הייצור; אלה שנחסמים היום:
    import ministers  # noqa: PLC0415
    for r in [r for r in records if r.value_list == "ministers"]:
        for t in ministers.titles():
            red = bank.redline_violation(r.text(SAMPLE_COMMITTEE).replace(bank.MINISTER_PLACEHOLDER, t),
                                         official_titles=[t])
            if red:
                blocked.append((bank.Record(**{**r.__dict__, "id": f"{r.id}/{t}", "value": t,
                                               "value_list": ""}), red))
    stays = blocked
    lines += [f"## רשומות חסומות - {len(stays)} (נשארות חסומות)", ""]
    if stays:
        lines += ["| מזהה | דוגמה | הסיבה |", "|---|---|---|"]
        lines += [f"| `{r.id}` | {_example(r).replace('|', chr(92) + '|')} | {b} |" for r, b in stays]
    else:
        lines.append("אין.")
    lines += ["", f"## חסומות, ויוצאות לפלט באישור אנושי מפורש של ברק (§0.4; סבב התיקונים ב2) - "
                  f"{len(overridden)}", ""]
    if overridden:
        lines += ["| מזהה | דוגמה | מה חסם | האישור |", "|---|---|---|---|"]
        for r, b in overridden:
            a = r.human_approval
            lines.append(f"| `{r.id}` | {_example(r).replace('|', chr(92) + '|')} | {b} | {a['by']}, {a['at']} |")
    else:
        lines.append("אין.")
    lines.append("")
    for fam, fam_he in FAMILY_HE.items():
        lines += [f"## {fam_he}", ""]
        for level, level_he in bank.LEVELS.items():
            rows = [r for r in records if r.family == fam and r.level == level]
            if not rows:
                continue
            lines += [f"### {level_he}", "", "| אשר | מזהה | דוגמה | סטטוס | מקור | חסימה |", "|---|---|---|---|---|---|"]
            for r in rows:
                block = bank.check(r, verdicts)
                if not block and raw_block(r):
                    block = raw_block(r) + " - **יוצאת באישור אנושי של ברק**"
                status = {"pending": "ממתינה", "approved": "מאושרת", "rejected": "נדחתה"}.get(r.status, r.status)
                box = "[x]" if r.status == "approved" else "[ ]"
                example = _example(r).replace("|", "\\|")
                lines.append(f"| {box} | `{r.id}` | {example} | {status} | {r.source} | {block} |")
            lines.append("")
    REVIEW.write_text("\n".join(lines), encoding="utf-8")
    print(f"נכתב {REVIEW.relative_to(ROOT)}: {len(records)} רשומות")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-screen", action="store_true")
    ap.add_argument("--all", action="store_true", help="לסנן מחדש את כל הבנק, מאפס")
    args = ap.parse_args()
    records = bank.load_all()
    if args.no_screen:
        verdicts = json.loads(bank.SCREEN_PATH.read_text(encoding="utf-8")).get("verdicts", {}) \
            if bank.SCREEN_PATH.exists() else {}
    else:
        import env_file  # noqa: PLC0415
        env_file.load()
        verdicts = screen(records, rescreen_all=args.all)
    write_review(records, verdicts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
