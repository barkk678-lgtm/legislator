"""הכיוון ההפוך: הוראת תיקון כתובה -> פעולה מובנית.

**מה זה נותן למשתמש:** הוא מעלה קובץ Word של הצעת חוק מתקנת,
והמערכת מציגה את נוסח החוק **אחרי** שההצעה התקבלה. זו העבודה
שמתנדבי "ספר החוקים הפתוח" עושים היום ביד.

**המיזוג עצמו כבר פתור.** `apply_changes.apply_pending_changes`
מקבלת עץ חוק ורשימת שינויים ומחזירה עץ "אחרי" נקי - `.text` מכיל
נוסח חוק בלבד בכל צומת. העץ הזה **הוא** הנוסח המשולב, והוא כבר
מיוצר בכל מסך עריכה. מה שחסר היה רק התרגום מטקסט לפעולה, וזה מה
שהמודול הזה עושה.

**דטרמיניסטי לחלוטין - אין כאן LLM ואין רשת.** חוק ברזל 2 מחייב
שהוראות התיקון ייווצרו דטרמיניסטית; הכיוון ההפוך מחויב מאותה
סיבה בדיוק, ואף ביתר שאת: נוסח משולב שגוי הוא **נוסח חוק שגוי
שנראה אמין**. מה שלא מתאים לדפוס מוכר נרשם ב-`unparsed` ומוצג
למשתמש כ"לא הצלחתי לפרש", ולעולם לא מנוחש.

**היקף מוצהר (שלב ראשון, ברק 22.9.2026):** הצעה שמתקנת **חוק
אחד**. הצעה שמתקנת כמה חוקים מזוהה ונדחית בהודעה ברורה, לא
מפורשת חלקית.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── זיהוי החוק המתוקן ────────────────────────────────────────────
# "בחוק שוויון ההזדמנויות בעבודה, התשמ״ח–1988, בסעיף 4(א)..."
# "בפקודת הנזיקין [נוסח חדש], בסעיף 43..."
# הפסיק שלפני השנה העברית הוא הגבול; "(להלן – החוק העיקרי)"
# אופציונלי ונחתך.
_LAW_RE = re.compile(
    r"^ב(?P<kind>חוק|פקודת)\s+(?P<name>.+?)"
    r"(?:,\s*(?P<year>הת[^,]*?\d{4}))?"
    r"\s*(?:\(להלן\s*[–־-]\s*החוק העיקרי\))?\s*,"
)

# "בסעיף 4(א)" / "בסעיף 43" / "בסעיף 3(1)"
_SECTION_RE = re.compile(
    r"בסעיף\s+(?P<section>[^\s,(]+)"
    r"(?:\((?P<sub>[^)]+)\))?"
    r"(?:\((?P<para>[^)]+)\))?")

# "אחרי פסקה (2) יבוא:"
_INSERT_AFTER_RE = re.compile(
    r"אחרי\s+(?P<kind>פסקה|סעיף קטן|פסקת משנה|סעיף)\s+"
    r"\((?P<label>[^)]+)\)\s+יבוא\s*:?\s*$")

# '"(3)\tהילד נמצא..."' - התווית בפתח הנוסח החדש
_NEW_UNIT_RE = re.compile(r'^\s*[״"”]\s*\((?P<label>[^)]+)\)\s*(?P<text>.+?)\s*[״"”]?\s*$', re.S)

# 'במקום "לחלוטין" יבוא "במידה רבה"' - הדפוס הנפוץ ביותר בהצעות
# אמיתיות. בלי "המילים" (מדריך משפטים §7.10.2, ראו drafting-rules
# §8.7.1), אבל מקבלים גם אותו בקריאה - הצעות אמיתיות כותבות את שתי
# הצורות, והכיוון הזה רק **קורא** ולכן סלחני יותר מהכיוון שכותב.
_REPLACE_RE = re.compile(
    r'במקום\s+(?:המיל(?:ה|ים)\s+)?[״"”](?P<old>[^״"”]+)[״"”]\s+'
    r'יבוא\s+[״"”](?P<new>[^״"”]+)[״"”]')

# 'ובסופו יבוא "או שזקוק..."' / 'בסופו יבוא "..."'
_APPEND_RE = re.compile(
    r'\bו?בסופו\s+יבוא\s+[״"”](?P<text>[^״"”]+)[״"”]')

# 'האמור בו יסומן "(א)" ואחריו יבוא:' - מספור מחדש. מזיז את העוגנים
# של כל מה שאחריו בסעיף, ולכן ההחלה חייבת להיות לפי הסדר.
_RELABEL_RE = re.compile(
    r'האמור\s+בו\s+יסומן\s+[״"”]\((?P<label>[^)]+)\)[״"”]\s+'
    r'ואחריו\s+יבוא\s*:?\s*$')

_KIND_TO_LEVEL = {
    "סעיף": "section",
    "סעיף קטן": "subsection",
    "פסקה": "paragraph",
    "פסקת משנה": "subparagraph",
}


@dataclass(frozen=True)
class LawReference:
    """החוק שההצעה מתקנת, כפי שנכתב בהוראה."""
    kind: str      # "חוק" | "פקודת"
    name: str      # "שוויון ההזדמנויות בעבודה"
    year: str      # "התשמ״ח–1988" (ריק אם לא נכתבה)

    @property
    def full(self) -> str:
        base = f"{self.kind} {self.name}".strip()
        return f"{base}, {self.year}" if self.year else base


@dataclass(frozen=True)
class InsertUnit:
    """הוספת יחידה חדשה אחרי יחידה קיימת."""
    section: str            # "4"
    subsection: str | None  # "א"
    after_kind: str         # "paragraph"
    after_label: str        # "2"
    new_label: str          # "3"
    new_text: str
    source_line: int


@dataclass(frozen=True)
class ReplaceWords:
    """החלפת מילים בתוך יחידה קיימת - הדפוס הנפוץ ביותר."""
    section: str
    container: str | None   # "(1)" / "(א)" - היחידה שבתוכה מחליפים
    old_phrase: str
    new_phrase: str
    source_line: int


@dataclass(frozen=True)
class AppendAtEnd:
    """'ובסופו יבוא "X"' - הוספת מילים בסוף יחידה קיימת."""
    section: str
    container: str | None
    text: str
    source_line: int


@dataclass(frozen=True)
class RelabelAndInsert:
    """'האמור בו יסומן "(א)" ואחריו יבוא: "(ב) ..."' - סעיף שאין בו
    עדיין סעיפים קטנים מקבל את הראשון שלו, ותוכנו הקיים מקבל תווית."""
    section: str
    relabeled_label: str    # "א"
    new_label: str          # "ב"
    new_text: str
    source_line: int


@dataclass
class AmendmentPlan:
    law: LawReference | None = None
    operations: list = field(default_factory=list)
    # **שורות שלא זוהו נרשמות ואינן מנוחשות.** זה הלב של המודול:
    # הצעה שמפורשת חלקית ומוצגת כמלאה היא בדיוק הכשל שהמוצר קיים
    # כדי למנוע.
    unparsed: list[tuple[int, str]] = field(default_factory=list)
    extra_laws: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        # **extra_laws נספר כאן, לא רק ב-blocking_reason.** הגרסה
        # הראשונה החזירה True להצעה שמתקנת שני חוקים, כי שתי
        # ההוראות התפרשו יפה ו-unparsed נשאר ריק - `ok` ו-
        # `blocking_reason` סתרו זו את זו, והקורא שבודק רק `ok`
        # היה מחיל את שתי ההוראות על החוק הראשון. נתפס בבדיקה.
        return (bool(self.law) and bool(self.operations)
                and not self.unparsed and not self.extra_laws)

    @property
    def blocking_reason(self) -> str:
        if self.extra_laws:
            others = "، ".join(self.extra_laws)
            return (f"ההצעה מתקנת יותר מחוק אחד ({others}). בשלב זה "
                    f"נתמכת הצעה שמתקנת חוק אחד בלבד.")
        if not self.law:
            return "לא זוהה החוק שההצעה מתקנת."
        if not self.operations:
            return "לא זוהתה אף הוראת תיקון שאני יודע להחיל."
        if self.unparsed:
            return (f"{len(self.unparsed)} הוראות לא זוהו. "
                    f"נוסח משולב חלקי גרוע מכלום, ולכן לא מוצג.")
        return ""


def _strip_quotes(text: str) -> str:
    return text.strip().strip('״"”“').strip()


def parse_instructions(lines: list[tuple[str, str]]) -> AmendmentPlan:
    """lines: [(מספר הוראה, טקסט)] כפי ש-extract_docx מחזיר.

    מחזירה תוכנית. **אינה נוגעת בעץ החוק** - הפרדה מכוונת: כאן
    קוראים מה ההוראה אומרת, ובשלב נפרד מחפשים את הצומת בפועל.
    """
    plan = AmendmentPlan()
    index = 0
    while index < len(lines):
        _, text = lines[index]
        stripped = text.strip()
        if not stripped:
            index += 1
            continue

        law_match = _LAW_RE.match(stripped)
        if law_match:
            ref = LawReference(law_match.group("kind"),
                               law_match.group("name").strip(),
                               (law_match.group("year") or "").strip())
            if plan.law is None:
                plan.law = ref
            elif ref.full != plan.law.full:
                plan.extra_laws.append(ref.full)

        section_match = _SECTION_RE.search(stripped)
        insert_match = _INSERT_AFTER_RE.search(stripped)

        # מספור מחדש: הנוסח החדש יושב בשורה הבאה, כמו בהוספת יחידה.
        relabel_match = _RELABEL_RE.search(stripped)
        if section_match and relabel_match:
            unit = (_NEW_UNIT_RE.match(lines[index + 1][1].strip())
                    if index + 1 < len(lines) else None)
            if unit is None:
                plan.unparsed.append((index, stripped))
                index += 1
                continue
            plan.operations.append(RelabelAndInsert(
                section=section_match.group("section"),
                relabeled_label=relabel_match.group("label").strip(),
                new_label=unit.group("label").strip(),
                new_text=_strip_quotes(unit.group("text")),
                source_line=index,
            ))
            index += 2
            continue

        # **כמה פעולות בשורה אחת.** ההוראה האמיתית
        # 'בסעיף 3(1) ..., במקום "א" יבוא "ב" ובסופו יבוא "ג"' מכילה
        # שתי פעולות נפרדות על אותה יחידה. כל אחת נרשמת בנפרד ומוחלת
        # בנפרד - ולא מפורשת כפעולה אחת שאיש לא הגדיר.
        if section_match:
            container = section_match.group("para") or section_match.group("sub")
            word_ops = []
            for match in _REPLACE_RE.finditer(stripped):
                word_ops.append(ReplaceWords(
                    section=section_match.group("section"), container=container,
                    old_phrase=match.group("old").strip(),
                    new_phrase=match.group("new").strip(), source_line=index,
                ))
            for match in _APPEND_RE.finditer(stripped):
                word_ops.append(AppendAtEnd(
                    section=section_match.group("section"), container=container,
                    text=match.group("text").strip(), source_line=index,
                ))
            if word_ops:
                # **מחסום נגד פירוש חלקי של שורה.** אם הוסרו מהשורה כל
                # הקטעים שזוהו ונשאר בה עוד "יבוא" - יש בה פעולה נוספת
                # שאיני מכיר, והשורה כולה נרשמת כלא-מזוהה. עדיף להודיע
                # שלא הבנתי מאשר להחיל שתיים מתוך שלוש.
                remainder = _REPLACE_RE.sub("", stripped)
                remainder = _APPEND_RE.sub("", remainder)
                if "יבוא" in remainder or "יימחק" in remainder or "תימחק" in remainder:
                    plan.unparsed.append((index, stripped))
                    index += 1
                    continue
                plan.operations.extend(word_ops)
                index += 1
                continue

        if section_match and insert_match:
            # הנוסח החדש יושב בשורה הבאה, במרכאות.
            new_label, new_text = "", ""
            if index + 1 < len(lines):
                unit = _NEW_UNIT_RE.match(lines[index + 1][1].strip())
                if unit:
                    new_label = unit.group("label").strip()
                    new_text = _strip_quotes(unit.group("text"))
            if not new_text:
                plan.unparsed.append((index, stripped))
                index += 1
                continue
            plan.operations.append(InsertUnit(
                section=section_match.group("section"),
                subsection=section_match.group("sub"),
                after_kind=_KIND_TO_LEVEL[insert_match.group("kind")],
                after_label=insert_match.group("label").strip(),
                new_label=new_label,
                new_text=new_text,
                source_line=index,
            ))
            index += 2
            continue

        # שורה שהיא כולה הנוסח החדש של הוראה קודמת - כבר נצרכה.
        if _NEW_UNIT_RE.match(stripped) and plan.operations \
                and plan.operations[-1].source_line == index - 1:
            index += 1
            continue

        # שורה שרק מזהה את החוק, בלי הוראה בגוף - תקינה.
        if law_match and not section_match:
            index += 1
            continue

        plan.unparsed.append((index, stripped))
        index += 1

    return plan


__all__ = ["AmendmentPlan", "AppendAtEnd", "InsertUnit", "LawReference",
           "RelabelAndInsert", "ReplaceWords", "parse_instructions"]
