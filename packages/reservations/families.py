"""משפחות ההסתייגויות והמתכנן (הסתייגויות 2, 26.9).

**הכלי נוגע רק בהצעת החוק.** כל עוגן ("X" שאחרי "במקום"/"אחרי") הוא ביטוי
שמופיע ביחידה של ההצעה - פעם אחת בדיוק, בקריאה ודאית. לא מסתכלים על החוק
העיקרי ולא על מאגר החוקים.

**המודל לעולם לא כותב טקסט שמגיע לפלט.** מקור כל מילה:

| משפחה | העוגן | הנוסח החדש | תלוי בבנק |
|---|---|---|---|
| value_change - שינוי ערך | כמות מההצעה ("שלושים ימים") | וריאציה דטרמיניסטית לפי הרמה | לא |
| deletion - מחיקה | יחידה / ביטוי מההצעה | - | לא |
| actor_swap - החלפת גורם | גורם מההצעה ("שר הפנים") | הבנק | כן |
| approval - אישור / התייעצות | גורם מההצעה | הבנק (+ הוועדה מעמוד השער) | כן |
| duty - חובה ורשות | הפועל מההצעה ("יתקן") | צמד מהבנק ("רשאי לתקן") | כן |
| conditions - תנאים | סוף היחידה | הבנק ("ובלבד ש...") | כן |
| after_last - אחרי הסעיף האחרון | - | תבנית + ערך מהבנק (תחילה, תחולה, הוראת שעה, הוראת מעבר) | כן |

**הסייגים (סעיף 86 לתקנון; §3ג לחוק-יסוד: משק המדינה):**
- 86(ד)(1) - לא לשלול את עצם ההצעה: מחיקת יחידה רק כשבסעיף יש שתיים לפחות
  (כמו טבריה 18-20: כל פסקה בנפרד), מחיקת ביטוי רק כשנשארות ביחידה 4 מילים
  לפחות, ואין מחיקה של סעיף שלם.
- 86(ד)(3) - לא לשנות את שם ההצעה: הכלי לא נוגע בשם, ולא מעגן בתוך ציטוט שם
  חוק ("התשכ"ה–1965") - anchors.law_citation_spans. בטבריה (4-6) הוספות באות
  אחרי הציטוט, לא בתוכו.
- §3ג - שינוי סכום כסף מסומן `budget=True` (דורש 50 ח"כ).
- 86(ד)(2) - ראו bank.py: כל רשומה בבנק עוברת את השומר לפני שהיא זמינה.

**פיזור לפני עומק** (ברק): היועצים המשפטיים מקבצים וריאציות על אותה נקודה
לחלופות, והן נספרות כאחת. לכן המתכנן ממלא קודם עוגן אחד מכל נקודה, ורק אז
מוסיף וריאציה שנייה על אותה נקודה. **"לפחות X" ייספרו בנפרד** - מספר הנקודות
(עוגן + פעולה) השונות. שמרני: בטבריה 4, 5 ו-6 הן אותה נקודה ונשארו נפרדות.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import agreement
import bank as bank_mod
import forms
from anchors import find_anchors, law_citation_spans
from numbers_he import MONEY_UNITS, find_quantities, quantity
from pdf_bill import BillSection, BillUnit, ParsedBill

FAMILIES = {
    "value_change": "שינוי ערך",
    "actor_swap": "החלפת גורם",
    "approval": "הוספת אישור או התייעצות",
    "duty": "חובה ורשות",
    "deletion": "מחיקה",
    "after_last": "סעיפים אחרי הסעיף האחרון",
    "conditions": "תנאים",
}
_FAMILY_ORDER = list(FAMILIES)


@dataclass
class Item:
    heading: str             # "לסעיף 1" / "לאחרי סעיף 3"
    lines: list[str]         # השורה הראשונה - ההוראה; השאר - נוסח מצוטט
    family: str
    group: str               # הנקודה (עוגן + פעולה) - לפיזור ולהערכה
    order: tuple
    budget: bool = False
    record_id: str = ""

    @property
    def text(self) -> str:
        return " ".join(self.lines)


@dataclass
class _Scope:
    """יחידה אחת שאפשר לעגן בה: הטקסט שלה, הכתובת, והסוג."""
    section: BillSection
    section_index: int
    unit_index: int
    kind: str                 # lead / paragraph / subsection / subparagraph / section
    labels: list[str]
    text: str
    addr: str
    leaf: bool                # אפשר להוסיף "בסופה"
    certain: bool


def _scopes(bill: ParsedBill) -> list[_Scope]:
    out: list[_Scope] = []
    for si, s in enumerate(bill.sections):
        has_units = bool(s.units)
        counter = [0]

        def add(kind, labels, text, leaf, certain):
            counter[0] += 1
            addr = forms.address(kind if has_units else "lead", labels, section_has_units=has_units)
            out.append(_Scope(s, si, counter[0], kind if has_units else "section", labels, text,
                              addr, leaf, certain and s.certain))

        if s.lead.text:
            add("lead", [], s.lead.text, not has_units, s.lead.certain)

        def walk(units: list[BillUnit], parents: list[str]):
            for u in units:
                labels = parents + [u.label]
                if u.text:
                    add(u.kind if not parents else "paragraph" if u.label[1].isdigit() else "subparagraph",
                        labels, u.text, not u.children, u.certain)
                walk(u.children, labels)

        walk(s.units, [])
    return out


def _occurrences(phrase: str, text: str) -> list[re.Match]:
    # גבול של אות **או ספרה**: "1" אינו מופיע בתוך "31" או "2018" (באג - עד כאן
    # נבדק רק גבול של אות עברית, ו-"1" שב-"(1)" נפסל כלא-ייחודי).
    return list(re.finditer(rf"(?<![\wא-ת]){re.escape(phrase)}(?![\wא-ת])", text))


def _unique(phrase: str, text: str) -> bool:
    return len(_occurrences(phrase, text)) == 1


def _in_citation(phrase: str, text: str) -> bool:
    """המופע **הזה** בתוך ציטוט שם חוק? (לא text.find - שמוצא את ה-"1" שבתוך
    "2018" שבציטוט, ופוסל את ה-"1" שב-"(1)".)"""
    spans = law_citation_spans(text)
    return any(any(s < m.end() and m.start() < e for s, e in spans) for m in _occurrences(phrase, text))


def _ok_anchor(phrase: str, scope: _Scope) -> bool:
    return (scope.certain and bool(phrase.strip()) and _unique(phrase, scope.text)
            and not _in_citation(phrase, scope.text) and '"' not in phrase)


# ── שינוי ערך ────────────────────────────────────────────────────────

# הווריאציות לכל רמה - פונקציה של הערך הקיים (דטרמיניסטי, בלי מודל).
# רציני: פי 2, 3, 4 וחצי; מתחכם: +1, פי 10, שבוע, אחד; הזוי: פי 100, פי 1000.
_LEVEL_VALUES = {
    "serious": lambda v: [v * 2, v * 3, v * 4] + ([v // 2] if v % 2 == 0 and v >= 2 else []),
    "clever": lambda v: [v + 1, v * 10, 7, 1],
    "absurd": lambda v: [v * 100, v * 1000],
}
# הזוי: גם היחידה עצמה מתחלפת (טבריה 65/ה: במקום "ימים" יבוא "שנים").
_BIGGER_UNIT = {"ימים": "שנים", "שבועות": "שנים", "חודשים": "שנים", "שעות": "ימים", "דקות": "שנים"}


def _fmt(n: int, unit: str, digits: bool, original: str) -> str:
    if digits:
        # הכרעה ב (ברק, 26.9): מ-1,000 ומעלה - עם מפריד אלפים ("3,000 ימים")
        num = f"{n:,}" if ("," in original or n >= 1000) else str(n)
        return f"{num} {original.split()[-1] if unit != 'שקלים' else original.split(maxsplit=1)[1]}"
    return quantity(n, unit)


# ערכים בלי יחידה - "כמו היום" (ברק): המספר והשנה שבנוסח - **לא הפניה** (הכרעה א). בהצעה
# 573919 (484 הסתייגויות שהוגשו) 146 מהן מחליפות בדיוק אלה: "31", "2020", "22ב".
_BARE_VALUES = {
    "number": {"serious": lambda n: [n + 1, n - 1, n + 2, n - 2], "clever": lambda n: [1, 7, 10, 100],
               "absurd": lambda n: [365, 1000, 10_000]},
    "gregorian_year": {"serious": lambda y: [y + 1, y + 2, y - 1], "clever": lambda y: [y + 10, 1948],
                       "absurd": lambda y: [2100, 3000]},
}


_DAY_RE = re.compile(r"^\s+ב(?:ינואר|פברואר|מרץ|מרס|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)(?![א-ת])")


def _bare_values(sc, level, taken: list[tuple[int, int]]):
    for a in find_anchors(sc.text):
        # הכרעה א (ברק, 26.9): מספר שהוא הפניה - לסעיף, פסקה, תקנה, פרט, תוספת,
        # בכל חוק - לא משתנה אף פעם, בכל הרמות. anchors.reference_spans.
        if (a.in_law_citation or a.in_reference or a.kind == "hebrew_year"
                or any(s < a.end and a.start < e for s, e in taken)):
            continue
        if not _ok_anchor(a.text, sc):
            continue
        if a.kind == "number" and _DAY_RE.match(sc.text[a.end:]):
            # יום בחודש: "31 בדצמבר" - לא "32 בדצמבר". רק ימים קיימים.
            n = int(a.text)
            news = {"serious": [n - 1, n - 2, n - 3], "clever": [1, 15], "absurd": []}[level]
            news = [str(v) for v in news if 1 <= v <= 28 or (v <= 31 and v < n)]
            news = [v for v in dict.fromkeys(news) if v != a.text]
        else:
            n = int(a.text)
            # מספר - עם מפריד אלפים מ-1,000 (הכרעה ב); שנה ("3000") - בלי
            fmt = (lambda v: str(v)) if a.kind == "gregorian_year" else (lambda v: f"{v:,}")
            news = [fmt(v) for v in dict.fromkeys(_BARE_VALUES[a.kind][level](n)) if v > 0 and v != n]
        for new in news:
            yield sc, ("replace", a.text), forms.replace(sc.addr, a.text, new), False


def _value_change(scopes, level, **_):
    for sc in scopes:
        taken = []
        for q in find_quantities(sc.text):
            pos = sc.text.find(q.text)
            taken.append((pos, pos + len(q.text)))
        yield from _bare_values(sc, level, taken)
        for q in find_quantities(sc.text):
            if not _ok_anchor(q.text, sc):
                continue
            seen = {q.value}
            news = []
            for n in _LEVEL_VALUES[level](q.value):
                if n in seen or not 0 < n < 100_000:
                    continue
                seen.add(n)
                news.append(_fmt(n, q.unit, q.digits, q.text))
            if level == "absurd" and q.unit in _BIGGER_UNIT and not q.digits:
                unit_word = q.text.split()[-1]
                if _ok_anchor(unit_word, sc):
                    yield sc, ("replace", unit_word), forms.replace(sc.addr, unit_word, _BIGGER_UNIT[q.unit]), False
            for new in news:
                yield sc, ("replace", q.text), forms.replace(sc.addr, q.text, new), q.unit in MONEY_UNITS


# ── מחיקה ────────────────────────────────────────────────────────────

# ביטויים שבטבריה נמחקו כמו שהם (46, 50, 64: "ובשינויים המחויבים"; 52: "כנוסחו בחוק זה").
_DELETABLE = ("ובשינויים המחויבים", "בשינויים המחויבים", "כנוסחו בחוק זה", "לפי העניין",
              "בשינויים המחויבים לפי העניין")


def _deletion(scopes, level, bill, **_):
    by_section: dict[int, list[_Scope]] = {}
    for sc in scopes:
        by_section.setdefault(sc.section_index, []).append(sc)
    for si, section_scopes in by_section.items():
        top_units = bill.sections[si].units
        for sc in section_scopes:
            words = len(sc.text.split())
            phrases = [p for p in _DELETABLE if p in sc.text]
            # "בתוך שלושים ימים" (טבריה 48/ג)
            for q in find_quantities(sc.text):
                for prefix in ("בתוך ", "תוך "):
                    if prefix + q.text in sc.text:
                        phrases.append(prefix + q.text)
                        break
            for phrase in dict.fromkeys(phrases):
                if _ok_anchor(phrase, sc) and words - len(phrase.split()) >= 4:
                    yield sc, ("delete", phrase), forms.delete_words(sc.addr, phrase), False
            # 86(ד)(1): מחיקת יחידה רק כשיש בסעיף שתיים לפחות (טבריה 18-20)
            if (sc.labels and len(sc.labels) == 1 and len(top_units) >= 2 and sc.certain
                    and sc.kind in ("paragraph", "subsection")):
                yield sc, ("delete_unit", sc.labels[0]), forms.delete_unit(sc.kind, sc.labels), False


# ── משפחות הבנק ──────────────────────────────────────────────────────

_ACTOR_RE = re.compile(
    r"(?<![א-ת])(?:שר\s+ה[א-ת]+(?:\s+וה[א-ת]+)?|ראש\s+הממשלה|היועץ\s+המשפטי\s+לממשלה|"
    r"הממשלה|השר|המנהל\s+הכללי|המנהל|הממונה|הרשם|המפקח|הנגיד|המועצה|הרשות)(?![א-ת])")


# **גורם = נושא המשפט**: אחריו פועל בעתיד או "רשאי"/"חייב" ("שר הפנים יתקן", טבריה
# סעיף 3). בלי זה "למילוי תפקידי המועצה" (טבריה, סעיף 2) נקרא כגורם, ויצא
# `במקום "המועצה" יבוא "סגן השר"` - הסתייגות בלי משמעות.
_SUBJECT_NEXT_RE = re.compile(r"^\s+(?:[יתנא][א-ת]{2,}|רשאי|רשאית|רשאים|חייב|חייבת|ממונה)(?![א-ת])")


# ── "השר" בתבניות הבנק (הכרעה ד, ברק 26.9) ─────────────────────────
# כותבים את השר המפורש מתוך ההצעה עצמה, דטרמיניסטית - המודל לא בוחר שר:
# 1. שר אחד בשמו בסעיף - הוא; 2. אחרת, שר אחד בשמו בהצעה כולה - הוא;
# 3. אחרת, ההצעה משתמשת ב"השר" - נשאר "השר"; 4. אחרת - התבנית לא מופעלת.
# סעיף שמופיעים בו שני שרים שונים - לא מנחשים: התבנית לא מופעלת עליו.
# ההחלפה בזמן הרינדור (כמו {committee}) - הרשומה עצמה, ופסק הסינון שלה, לא משתנים.
_NAMED_MINISTER_RE = re.compile(r"(?<![א-ת])[ובלמכשה]{0,2}(שר\s+ה[א-ת]+(?:\s+וה(?!שר(?![א-ת]))[א-ת]+)?)(?![א-ת])")
_HASAR_RE = re.compile(r"(?<![א-ת])([ובלמכש]{0,2})השר(?![א-ת])")


def _section_text(s: BillSection) -> str:
    parts = [s.lead.text]

    def walk(units):
        for u in units:
            parts.append(u.text)
            walk(u.children)

    walk(s.units)
    return " ".join(p for p in parts if p)


def _named_ministers(text: str) -> list[str]:
    out = []
    for m in _NAMED_MINISTER_RE.finditer(text):
        name = re.sub(r"\s+", " ", m.group(1))
        if name not in out:
            out.append(name)
    return out


def _minister(bill: ParsedBill, section: BillSection | None) -> str | None:
    """השר שנכתב במקום "השר" בתבנית, או None - התבנית לא מופעלת."""
    if section is not None:
        named = _named_ministers(_section_text(section))
        if len(named) == 1:
            return named[0]
        if len(named) > 1:
            return None
    whole = " ".join(_section_text(s) for s in bill.sections)
    named = _named_ministers(whole)
    if len(named) == 1:
        return named[0]
    return "השר" if _HASAR_RE.search(whole) else None


def _with_minister(text: str, bill: ParsedBill, section: BillSection | None) -> str | None:
    """`text` עם השר המפורש במקום "השר"; None - התבנית לא מופעלת על ההצעה הזו."""
    if not _HASAR_RE.search(text):
        return text
    minister = _minister(bill, section)
    if minister is None:
        return None
    return _HASAR_RE.sub(lambda m: m.group(1) + minister, text)


def _actors_with_next(sc: _Scope) -> list[tuple[str, str]]:
    """(הגורם, המילה שצמודה אחריו - הפועל או התואר)."""
    found = []
    for m in _ACTOR_RE.finditer(sc.text):
        a = m.group(0)
        nxt = _SUBJECT_NEXT_RE.match(sc.text[m.end():])
        if any(a == f for f, _ in found) or not nxt:
            continue
        if _ok_anchor(a, sc):
            found.append((a, nxt.group(0).strip()))
    return found


def _actors(sc: _Scope) -> list[str]:
    return [a for a, _ in _actors_with_next(sc)]


def _actor_swap(scopes, records, bill, **_):
    """הכרעה ג (ברק, 26.9): גורם מאותו מין - מחליפים רק אותו. מין אחר - מחליפים את
    הגורם **ואת המילה שצמודה אחריו**, בצורה המותאמת מהטבלה הסגורה (agreement.py):
    `במקום "שר הפנים יתקן" יבוא "הממשלה תתקן"`. מילה שאינה בטבלה, או מין לא ידוע -
    הרשומה לא מופעלת על הגורם הזה. הנקודה (לפיזור ולהערכה) - הגורם."""
    for sc in scopes:
        for actor, next_word in _actors_with_next(sc):
            old_g = agreement.gender(actor)
            for r in records.get("actor_swap", []):
                new = _with_minister(r.text(), bill, sc.section)
                new_g = agreement.gender(new) if new else None
                if new == actor or old_g is None or new_g is None:
                    continue
                if new_g == old_g:
                    line = forms.replace(sc.addr, actor, new)
                else:
                    inflected = agreement.inflect(next_word, new_g)
                    phrase = f"{actor} {next_word}"
                    if inflected is None or not _ok_anchor(phrase, sc):
                        continue
                    line = forms.replace(sc.addr, phrase, f"{new} {inflected}")
                yield sc, ("replace", actor), line, False, r.id


def _approval(scopes, records, committee, bill, **_):
    for sc in scopes:
        for actor in _actors(sc):
            for r in records.get("approval", []):
                if "{committee}" in r.value and not committee:
                    continue
                text = _with_minister(r.text(committee), bill, sc.section)
                if text is None:
                    continue
                yield sc, ("after", actor), forms.after(sc.addr, actor, text), False, r.id


def _duty(scopes, records, bill, **_):
    for sc in scopes:
        for r in records.get("duty", []):
            src, _, dst = r.value.partition("=>")
            dst = _with_minister(dst, bill, sc.section) if dst else dst
            if src and dst and _ok_anchor(src, sc):
                yield sc, ("replace", src), forms.replace(sc.addr, src, dst), False, r.id


def _conditions(scopes, records, committee, bill, **_):
    for sc in scopes:
        if not sc.leaf or not sc.certain:
            continue
        for r in records.get("conditions", []):
            if "{committee}" in r.value and not committee:
                continue
            text = _with_minister(r.text(committee), bill, sc.section)
            if text is None:
                continue
            yield sc, ("append", ""), forms.append(sc.addr, sc.kind, text), False, r.id


def _after_last(bill, records, committee, **_):
    last = bill.sections[-1]
    m = re.match(r"\d+", last.number)
    if not m:
        return
    new_number = str(int(m.group(0)) + 1)
    for r in records.get("after_last", []):
        if "{committee}" in r.value and not committee:
            continue
        text = _with_minister(r.text(committee), bill, None)
        if text is None:
            continue
        margin, _, body = text.partition("|")
        yield margin, forms.new_section_after(margin, new_number, body), r.id


# ── המתכנן ───────────────────────────────────────────────────────────


@dataclass
class Plan:
    items: list[Item]
    available: int                          # כמה אפשר לייצר מההצעה, ברמה ובמשפחות שנבחרו
    groups: int                             # נקודות שונות בכל מה שאפשר
    at_least_separate: int                  # "לפחות X ייספרו בנפרד" - בפלט שנבחר
    families_waiting: list[str] = field(default_factory=list)  # משפחות שממתינות לאישור הבנק
    requested: int = 0

    @property
    def short(self) -> bool:
        return self.requested > self.available


def candidates(bill: ParsedBill, level: str, families: list[str]) -> tuple[list[Item], list[str]]:
    """כל ההסתייגויות האפשריות, לפי סדר המסמך."""
    if level not in bank_mod.LEVELS:
        raise ValueError(f"רמה לא מוכרת: {level}")
    allowed, _blocked = bank_mod.load(level)
    records: dict[str, list] = {}
    for r in allowed:
        records.setdefault(r.family, []).append(r)
    waiting = [f for f in families if f in bank_mod.BANK_FAMILIES and not records.get(f)]
    scopes = _scopes(bill)
    ctx = dict(scopes=scopes, level=level, bill=bill, records=records, committee=bill.committee)
    items: list[Item] = []
    seen_text: set[str] = set()

    def push(item: Item):
        if item.text not in seen_text:
            seen_text.add(item.text)
            items.append(item)

    generators = {"value_change": _value_change, "deletion": _deletion, "actor_swap": _actor_swap,
                  "approval": _approval, "duty": _duty, "conditions": _conditions}
    for family in families:
        gen = generators.get(family)
        if gen is None:
            continue
        for k, produced in enumerate(gen(**ctx)):
            sc, (op, anchor), line, budget, *rid = produced
            push(Item(heading=f"לסעיף {sc.section.number}", lines=[line], family=family,
                      group=f"{sc.section.number}|{'/'.join(sc.labels) or sc.kind}|{op}|{anchor}",
                      order=(sc.section_index, 0, sc.unit_index, _FAMILY_ORDER.index(family), k),
                      budget=budget, record_id=rid[0] if rid else ""))
    if "after_last" in families and bill.sections:
        last = bill.sections[-1]
        for k, (margin, lines, rid) in enumerate(_after_last(**ctx)):
            push(Item(heading=f"לאחרי סעיף {last.number}", lines=lines, family="after_last",
                      group=f"after|{margin}", order=(len(bill.sections), 1, 0, 0, k), record_id=rid))
    items.sort(key=lambda it: it.order)
    return items, waiting


def plan(bill: ParsedBill, level: str, families: list[str], count: int) -> Plan:
    pool, waiting = candidates(bill, level, families)
    groups: dict[str, list[Item]] = {}
    for it in pool:
        groups.setdefault(it.group, []).append(it)
    # פיזור לפני עומק: סיבוב אחד = וריאציה אחת מכל נקודה, לפי סדר המסמך.
    chosen: list[Item] = []
    depth = 0
    while len(chosen) < min(count, len(pool)):
        added = False
        for members in groups.values():
            if depth < len(members) and len(chosen) < count:
                chosen.append(members[depth])
                added = True
        if not added:
            break
        depth += 1
    chosen.sort(key=lambda it: it.order)
    return Plan(items=chosen, available=len(pool), groups=len(groups),
                at_least_separate=len({it.group for it in chosen}), families_waiting=waiting,
                requested=count)


def availability(bill: ParsedBill, families: list[str]) -> dict:
    """לכל רמה: כמה אפשר לייצר לכל היותר, כמה נקודות שונות - בסך הכול ולכל
    משפחה (הממשק מחשב מחדש כשמסירים משפחה, בלי לקרוא שוב את הקובץ)."""
    out = {}
    for level in bank_mod.LEVELS:
        pool, waiting = candidates(bill, level, families)
        per_family = {}
        for f in families:
            members = [it for it in pool if it.family == f]
            per_family[f] = {"available": len(members), "groups": len({it.group for it in members})}
        out[level] = {"available": len(pool), "groups": len({it.group for it in pool}),
                      "families_waiting": waiting, "per_family": per_family}
    return out


__all__ = ["FAMILIES", "Item", "Plan", "availability", "candidates", "plan"]
