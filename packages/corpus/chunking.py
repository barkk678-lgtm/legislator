"""חלוקה ל-chunks לצורך embeddings (משימה א, 1.3 - חיפוש סמנטי,
2026-09-16). **טהורה** - בלי רשת, בלי LLM (כמו packages/amend) - רק
בונה את יחידות הטקסט; `packages/llm/embeddings.py` הוא שקורא בפועל
למודל, בנפרד לגמרי.

עיצוב לפי בקשת ברק המדויקת: "chunk ברמת סעיף, פיצול מעל 2,000
תווים על גבולות סעיפי משנה, הקשר מצורף לכל chunk (שם החוק, מספר
סעיף, כותרת שוליים). raw_block לא מתפצל".

**"לא מתפצל" נאכף מבנית, לא בבדיקה נפרדת:** הפיצול (כשנדרש) הוא
תמיד *ברמת הילדים הישירים של הסעיף* (subsection/paragraph/definition/
raw_block) - לעולם לא נכנסים לתוך תוכן של ילד כדי לחתוך אותו. לכן
raw_block, שהוא תמיד עלה בעץ (`packages/corpus/node.py`: "לא ניתן
לעריכה תכנותית", תוכן אטום), אף פעם לא יכול להיחתך - הוא תמיד שלם
בתוך ה-chunk שמכיל אותו, גם אם זה עושה את ה-chunk גדול.

**"חורג ממגבלת המודל -> דלג ורשום" לא מיושם כאן בכלל, בכוונה:**
המודול הזה לא מכיר את המגבלה של text-embedding-3-large (8,192 טוקן -
תלוי-מודל, לא עניין של פיצול טקסט). `packages/llm/embeddings.
EmbeddingTooLongError` היא שמזהה את זה בפועל (מהתשובה האמיתית של
ה-API), וקוד ה-ingest (לא כאן) הוא שמדלג ורושם - הפרדת אחריות בין
"מה הצורה הנכונה של chunk" (כאן) ל"האם הוא נכנס במודל" (ingest+API).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from node import LegislativeNode, find_sections  # noqa: E402

DEFAULT_MAX_CHARS = 2000


@dataclass
class Chunk:
    law_id: str
    section_number: str
    chunk_index: int  # 0 = הסעיף כולו כ-chunk יחיד; אחרת אינדקס בתוך הסעיף המפוצל
    node_ids: list[str]  # ה-id-ים (ברמת ילד ישיר של הסעיף) שמרכיבים את ה-chunk - provenance
    context_prefix: str
    body: str  # התוכן עצמו, בלי context_prefix
    contains_raw_block: bool

    @property
    def text(self) -> str:
        """מה שנשלח בפועל ל-embedding - הקשר + תוכן, ראו embeddings.py."""
        return f"{self.context_prefix}\n{self.body}" if self.body else self.context_prefix

    @property
    def char_length(self) -> int:
        return len(self.text)


def collect_text(node: LegislativeNode) -> str:
    """טקסט הצומת עצמו + כל צאצאיו, בסדר מסמך, כל אחד בשורה נפרדת.
    raw_block.text הוא HTML גולמי (node.py) - נכלל כמו שהוא, לא
    מנורמל שוב כאן."""
    parts = [node.text] if node.text else []
    for child in node.children:
        child_text = collect_text(child)
        if child_text:
            parts.append(child_text)
    return "\n".join(parts)


def _contains_raw_block(node: LegislativeNode) -> bool:
    if node.node_type == "raw_block":
        return True
    return any(_contains_raw_block(c) for c in node.children)


def _context_prefix(law_title: str, section_number: str, margin_title: str | None) -> str:
    base = f"{law_title} — סעיף {section_number}"
    return f"{base} ({margin_title})" if margin_title else base


def chunk_section(
    law_id: str, law_title: str, section: LegislativeNode, *, max_chars: int = DEFAULT_MAX_CHARS
) -> list[Chunk]:
    """סעיף בודד -> chunk אחד (אם קצר מספיק/בלי ילדים לפצל לפיהם) או
    chunk אחד לכל ילד ישיר (אם ארוך מדי) - ראו דוקסטרינג המודול."""
    prefix = _context_prefix(law_title, section.number, section.margin_title)
    full_text = collect_text(section)

    if len(full_text) <= max_chars or not section.children:
        return [
            Chunk(
                law_id=law_id,
                section_number=section.number,
                chunk_index=0,
                node_ids=[section.id],
                context_prefix=prefix,
                body=full_text,
                contains_raw_block=_contains_raw_block(section),
            )
        ]

    chunks = []
    for i, child in enumerate(section.children):
        child_text = collect_text(child)
        if not child_text:
            continue
        chunks.append(
            Chunk(
                law_id=law_id,
                section_number=section.number,
                chunk_index=i,
                node_ids=[child.id],
                context_prefix=prefix,
                body=child_text,
                contains_raw_block=_contains_raw_block(child),
            )
        )
    return chunks


def chunk_law(root: LegislativeNode, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """כל החוק -> רשימת chunks, סעיף אחר סעיף. משתמשת ב-node.
    find_sections (רקורסיבית, בכל עומק חלק/פרק/סימן - אותה תשתית
    שתוקנה 2026-09-16 ל-amend) - לא בונה מחדש הליכת-עץ נפרדת."""
    law_title = root.full_title or root.id
    sections = find_sections(root)
    chunks: list[Chunk] = []
    for number in sorted(sections):
        chunks.extend(chunk_section(root.id, law_title, sections[number], max_chars=max_chars))
    return chunks
