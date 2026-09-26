"""מקסימום ודוגמאות על טבריה (אישורי הבנק §7, ברק 26.9.2026).

- המקסימום לכל רמה ולכל משפחה - מההצעה האמיתית (reference/הצעת חוק טבריה.pdf),
  עם פסקי הסינון האמיתיים (data/reservations_bank_screen.json), בלי מוק.
- שלוש דוגמאות אמיתיות לכל משפחה ורמה - **Word אחד לכל רמה**
  (docs/reservations-samples/<רמה>.docx). הדוגמאות - מנקודות שונות בהצעה (תחילה,
  אמצע, סוף) ומרשומות בנק שונות; רק כשאין די נקודות - וריאציות באותה נקודה.

    python3 tools/reservations_tiberias_samples.py      # מדפיס טבלה (Markdown) וכותב את הקבצים
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "reservations"))

import bank  # noqa: E402
import families  # noqa: E402
import render_docx  # noqa: E402
from docx import Document  # noqa: E402
from docx.shared import Twips  # noqa: E402
from pdf_bill import parse_bill_pdf  # noqa: E402

PDF = ROOT / "reference" / "הצעת חוק טבריה.pdf"
OUT = ROOT / "docs" / "reservations-samples"
LEVEL_HE = bank.LEVELS                     # "רציני" / "מתחכם" / "הזוי" - השמות שבממשק


def _spread(members: list, k: int = 3) -> list:
    """עד k פריטים שונים ככל האפשר: קודם נקודות שונות בהצעה (תחילה, סוף, אמצע) ורשומות
    בנק שונות; אם אין די נקודות - וריאציות אחרות באותה נקודה."""
    by_group: dict[str, list] = {}
    for it in members:
        by_group.setdefault(it.group, []).append(it)
    heads = [g[0] for g in by_group.values()]
    if len(heads) > 2:                                   # תחילה, סוף, אמצע - ואז השאר
        heads = [heads[0], heads[-1], heads[len(heads) // 2]] + heads[1:len(heads) // 2] + heads[len(heads) // 2 + 1:-1]
    order = heads + [it for it in members if it not in heads]
    chosen, groups, rids = [], set(), set()
    for strict_group in (True, False):
        for it in order:
            if len(chosen) == k:
                break
            if it in chosen or (it.record_id and it.record_id in rids) or (strict_group and it.group in groups):
                continue
            chosen.append(it)
            groups.add(it.group)
            rids.add(it.record_id)
    for it in order:                                     # אם גם כך חסר - מה שיש
        if len(chosen) < k and it not in chosen:
            chosen.append(it)
    return sorted(chosen, key=lambda it: it.order)


def measure(bill) -> dict:
    fams = list(families.FAMILIES)
    out = {}
    for level in bank.LEVELS:
        pool, waiting = families.candidates(bill, level, fams)
        out[level] = {"total": len(pool), "groups": len({it.group for it in pool}), "waiting": waiting,
                      "per_family": {f: [it for it in pool if it.family == f] for f in fams}}
    return out


def write_docx(bill, level: str, per_family: dict) -> Path:
    doc = Document()
    for section in doc.sections:
        section.page_width, section.page_height = (Twips(v) for v in render_docx.A4_TWIPS)
    render_docx._set_default_font(doc)
    render_docx._rtl_paragraph(doc, f"{bill.title} – דוגמאות, רמה {LEVEL_HE[level]}")
    for f, members in per_family.items():
        render_docx._rtl_paragraph(doc, f"משפחה: {families.FAMILIES[f]} ({len(members)} אפשריות)")
        chosen = _spread(members)
        if not chosen:
            render_docx._rtl_paragraph(doc, "אין הסתייגויות מהמשפחה הזו ברמה הזו.")
        for n, it in enumerate(chosen, 1):
            first, *rest = it.lines
            render_docx._rtl_paragraph(doc, it.heading)
            render_docx._rtl_paragraph(doc, f"{n}. {first}")
            for line in rest:
                render_docx._rtl_paragraph(doc, line)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{level}.docx"
    doc.save(path)
    return path


def main() -> None:
    bill = parse_bill_pdf(PDF)
    m = measure(bill)
    fams = list(families.FAMILIES)
    print("| משפחה | " + " | ".join(LEVEL_HE[lv] for lv in bank.LEVELS) + " |")
    print("|---|" + "---|" * len(bank.LEVELS))
    for f in fams:
        print(f"| {families.FAMILIES[f]} | " + " | ".join(str(len(m[lv]["per_family"][f])) for lv in bank.LEVELS) + " |")
    print("| **סה\"כ** | " + " | ".join(f"**{m[lv]['total']}** ({m[lv]['groups']} נקודות)" for lv in bank.LEVELS) + " |")
    for lv in bank.LEVELS:
        if m[lv]["waiting"]:
            print(f"ממתינות ברמה {LEVEL_HE[lv]}: {m[lv]['waiting']}")
        print("נכתב:", write_docx(bill, lv, m[lv]["per_family"]).relative_to(ROOT))


if __name__ == "__main__":
    main()
