"""מספרים במילים בעברית - קריאה וכתיבה, עם התאמת מין (הסתייגויות 2, 26.9).

**למה זה נדרש:** העוגן המרכזי לשינוי ערך בטבריה כתוב במילים - "בתוך שלושים
ימים" (הסתייגויות 48, 56, 65) - ובחקיקה כך נכתבות תקופות וכמויות. מנוע
שמכיר רק ספרות היה מפספס את רוב הערכים.

**מין:** "ימים", "חודשים", "שבועות", "שקלים" - זכר ("שלושה ימים", "עשרים
ואחד ימים"); "שנים", "שעות", "דקות" - נקבה ("שלוש שנים", "עשרים ואחת שנים").
2 - צורת הזוגי: "יומיים", "חודשיים", "שבועיים", "שנתיים", "שעתיים".
1 - שם היחידה לבדו ("יום", "שנה") - כמו בחקיקה ("בתוך שנה").
"""

from __future__ import annotations

import re

_ONES_M = ["", "אחד", "שניים", "שלושה", "ארבעה", "חמישה", "שישה", "שבעה", "שמונה", "תשעה"]
_ONES_F = ["", "אחת", "שתיים", "שלוש", "ארבע", "חמש", "שש", "שבע", "שמונה", "תשע"]
_TEENS_M = ["עשרה", "אחד עשר", "שנים עשר", "שלושה עשר", "ארבעה עשר", "חמישה עשר",
            "שישה עשר", "שבעה עשר", "שמונה עשר", "תשעה עשר"]
_TEENS_F = ["עשר", "אחת עשרה", "שתים עשרה", "שלוש עשרה", "ארבע עשרה", "חמש עשרה",
            "שש עשרה", "שבע עשרה", "שמונה עשרה", "תשע עשרה"]
_TENS = ["", "", "עשרים", "שלושים", "ארבעים", "חמישים", "שישים", "שבעים", "שמונים", "תשעים"]
_HUNDREDS = ["", "מאה", "מאתיים", "שלוש מאות", "ארבע מאות", "חמש מאות", "שש מאות",
             "שבע מאות", "שמונה מאות", "תשע מאות"]
_THOUSANDS = {1: "אלף", 2: "אלפיים", 3: "שלושת אלפים", 4: "ארבעת אלפים", 5: "חמשת אלפים",
              6: "ששת אלפים", 7: "שבעת אלפים", 8: "שמונת אלפים", 9: "תשעת אלפים", 10: "עשרת אלפים"}

# יחידה -> (יחיד, רבים, זוגי, מין)
UNITS = {
    "ימים": ("יום", "ימים", "יומיים", "m"),
    "חודשים": ("חודש", "חודשים", "חודשיים", "m"),
    "שבועות": ("שבוע", "שבועות", "שבועיים", "m"),
    "שנים": ("שנה", "שנים", "שנתיים", "f"),
    "שעות": ("שעה", "שעות", "שעתיים", "f"),
    "דקות": ("דקה", "דקות", "", "f"),
    # כסף - שינוי ערך כאן מסומן כעלות תקציבית (§3ג לחוק-יסוד: משק המדינה).
    "שקלים": ("שקל", "שקלים", "", "m"),
    "אחוזים": ("אחוז", "אחוזים", "", "m"),
}
MONEY_UNITS = {"שקלים"}
_UNIT_BY_FORM = {form: plural for plural, forms in UNITS.items() for form in forms[:3] if form}


def _below_thousand(n: int, gender: str) -> str:
    ones, teens = (_ONES_M, _TEENS_M) if gender == "m" else (_ONES_F, _TEENS_F)
    h, rest = divmod(n, 100)
    parts = [_HUNDREDS[h]] if h else []
    if rest:
        if rest < 10:
            words = ones[rest]
        elif rest < 20:
            words = teens[rest - 10]
        else:
            t, o = divmod(rest, 10)
            words = _TENS[t] + (f" ו{ones[o]}" if o else "")
        parts.append(words)
    if len(parts) == 2:
        # "מאה ועשרים", "שלוש מאות שישים וחמישה" - ו' לפני האיבר האחרון בלבד
        last = parts[1]
        return parts[0] + (" " + last if " ו" in last else " ו" + last)
    return parts[0] if parts else ""


def number_words(n: int, gender: str) -> str:
    """0 < n < 100,000 -> מילים. "שניים"/"שתיים" לבדם - לא לפני שם עצם."""
    if n <= 0 or n >= 100_000:
        raise ValueError(n)
    th, rest = divmod(n, 1000)
    parts = []
    if th:
        parts.append(_THOUSANDS.get(th) or f"{_below_thousand(th, 'm')} אלף")
    if rest:
        parts.append(_below_thousand(rest, gender))
    if len(parts) == 2 and " ו" not in parts[1]:
        return parts[0] + " ו" + parts[1]
    return " ".join(parts)


def quantity(n: int, unit_plural: str) -> str:
    """מספר + יחידה: "יום", "יומיים", "שלושה ימים", "עשרים ואחת שנים"."""
    singular, plural, dual, gender = UNITS[unit_plural]
    if n == 1:
        return singular
    if n == 2 and dual:
        return dual
    words = number_words(n, gender)
    if n == 2:
        words = "שני" if gender == "m" else "שתי"
    return f"{words} {plural}"


# ── קריאה ─────────────────────────────────────────────────────────────

_WORD_VALUES: dict[str, int] = {}
for _i, (_m, _f) in enumerate(zip(_ONES_M, _ONES_F)):
    if _i:
        _WORD_VALUES[_m] = _i
        _WORD_VALUES[_f] = _i
_WORD_VALUES.update({"שני": 2, "שתי": 2, "עשרה": 10, "עשר": 10})
for _i, _w in enumerate(_TENS):
    if _w:
        _WORD_VALUES[_w] = _i * 10
for _i, _w in enumerate(_HUNDREDS):
    if _w:
        _WORD_VALUES[_w] = _i * 100
for _i, _w in _THOUSANDS.items():
    _WORD_VALUES[_w] = _i * 1000
_WORD_VALUES["אלף"] = 1000

_TOKENS = sorted(_WORD_VALUES, key=len, reverse=True)
_NUM_WORD = "|".join(re.escape(t) for t in _TOKENS)
# רצף מילות מספר, כל אחת אולי עם ו' מוצמדת, ואחריו יחידה.
_QTY_RE = re.compile(
    rf"(?<![א-ת])((?:ו?(?:{_NUM_WORD})(?:\s+(?:ו?(?:{_NUM_WORD})|עשרה?|עשר))*))\s+"
    rf"({'|'.join(sorted(_UNIT_BY_FORM, key=len, reverse=True))})(?![א-ת])")
_DIGIT_QTY_RE = re.compile(
    rf"(?<![\d,.])(\d{{1,3}}(?:,\d{{3}})*|\d+)\s+({'|'.join(sorted(_UNIT_BY_FORM, key=len, reverse=True))})(?![א-ת])")
_DUAL_RE = re.compile(rf"(?<![א-ת])({'|'.join(u[2] for u in UNITS.values() if u[2])})(?![א-ת])")


def parse_words(text: str) -> int | None:
    """"שלושים" -> 30, "מאה ועשרים" -> 120, "שלושה עשר" -> 13."""
    total, current = 0, 0
    rest = text
    while rest.strip():
        rest = rest.strip()
        if rest.startswith("ו") and not any(rest.startswith(t) for t in _TOKENS):
            rest = rest[1:]
        tok = next((t for t in _TOKENS if rest.startswith(t) and
                    (len(rest) == len(t) or not "א" <= rest[len(t)] <= "ת")), None)
        if tok is None:
            return None
        value = _WORD_VALUES[tok]
        if tok in ("עשר", "עשרה") and 0 < current < 10:
            current += 10
        elif value >= 1000:
            total += (current or 1) * value if value == 1000 else value
            current = 0
        else:
            current += value
        rest = rest[len(tok):]
    return total + current or None


class Quantity:
    """ערך שנמצא בנוסח: הטקסט המדויק, הערך, היחידה."""

    def __init__(self, text: str, value: int, unit: str, digits: bool):
        self.text, self.value, self.unit, self.digits = text, value, unit, digits

    def __repr__(self):
        return f"Quantity({self.text!r}={self.value} {self.unit})"


def find_quantities(text: str) -> list[Quantity]:
    """כל "<מספר> <יחידה>" בנוסח - במילים, בספרות, או בזוגי ("שנתיים")."""
    out: list[Quantity] = []
    for m in _QTY_RE.finditer(text):
        words, full = m.group(1), m.group(0)
        # ו' החיבור אינה חלק מהערך: "וחמישה אחוזים" -> העוגן "חמישה אחוזים".
        if words.startswith("ו") and parse_words(words[1:]):
            words, full = words[1:], full[1:]
        value = parse_words(words)
        if value:
            out.append(Quantity(full, value, _UNIT_BY_FORM[m.group(2)], False))
    for m in _DIGIT_QTY_RE.finditer(text):
        out.append(Quantity(m.group(0), int(m.group(1).replace(",", "")), _UNIT_BY_FORM[m.group(2)], True))
    for m in _DUAL_RE.finditer(text):
        unit = next(p for p, f in UNITS.items() if f[2] == m.group(1))
        out.append(Quantity(m.group(0), 2, unit, False))
    return out


__all__ = ["MONEY_UNITS", "Quantity", "UNITS", "find_quantities", "number_words", "parse_words", "quantity"]
