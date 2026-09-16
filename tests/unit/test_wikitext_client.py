"""בדיקות ל-extract_revision_timestamp (wikitext_client.py). ראו TASKS.md
משימה 5א.

ה-XML הסינתטי כאן בנוי לפי סכימת Special:Export התקנית של MediaWiki,
עם הערכים האמיתיים ששמורים ב-tests/fixtures/wikitext/kaytanot.meta.json
(page_id, revision_id, revision_timestamp, contributor) - כדי שהבדיקה
תהיה מעוגנת בנתון אמיתי שכבר נשלף בעבר, לא במספרים מומצאים. אין כאן
קריאת רשת - זו בדיוק הסיבה שהפונקציה מקבלת מחרוזת XML, לא URL.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "corpus"))

from wikitext_client import (  # noqa: E402
    extract_revision_id,
    extract_revision_timestamp,
    extract_wikitext_body,
    is_primary_legislation_title,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikitext"

_KAYTANOT_META = json.loads((FIXTURES / "kaytanot.meta.json").read_text(encoding="utf-8"))

_EXPORT_XML = f"""<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">
  <page>
    <title>{_KAYTANOT_META['title']}</title>
    <ns>0</ns>
    <id>{_KAYTANOT_META['page_id']}</id>
    <revision>
      <id>{_KAYTANOT_META['revision_id']}</id>
      <timestamp>{_KAYTANOT_META['revision_timestamp']}</timestamp>
      <contributor>
        <username>{_KAYTANOT_META['contributor']}</username>
      </contributor>
      <text bytes="100" xml:space="preserve">תוכן כלשהו</text>
    </revision>
  </page>
</mediawiki>"""


def main():
    checks = []

    checks.append(
        (
            "שולפת timestamp נכון מתוך export XML אמיתי (namespace מוצהר)",
            extract_revision_timestamp(_EXPORT_XML) == _KAYTANOT_META["revision_timestamp"],
        )
    )

    no_namespace_xml = _EXPORT_XML.replace(
        ' xmlns="http://www.mediawiki.org/xml/export-0.11/"', ""
    )
    checks.append(
        (
            "עובד גם בלי namespace מוצהר (לא תלוי בגרסת export-X.XX)",
            extract_revision_timestamp(no_namespace_xml) == _KAYTANOT_META["revision_timestamp"],
        )
    )

    no_revision_xml = "<mediawiki><page><title>x</title></page></mediawiki>"
    try:
        extract_revision_timestamp(no_revision_xml)
        checks.append(("אין revision -> שגיאה, לא ניחוש", False))
    except ValueError:
        checks.append(("אין revision -> שגיאה, לא ניחוש", True))

    no_timestamp_xml = "<mediawiki><page><revision><id>1</id></revision></page></mediawiki>"
    try:
        extract_revision_timestamp(no_timestamp_xml)
        checks.append(("יש revision אבל אין timestamp -> שגיאה", False))
    except ValueError:
        checks.append(("יש revision אבל אין timestamp -> שגיאה", True))

    checks.append(
        (
            "שולפת revision id נכון",
            extract_revision_id(_EXPORT_XML) == int(_KAYTANOT_META["revision_id"]),
        )
    )
    try:
        extract_revision_id(no_timestamp_xml.replace("<id>1</id>", ""))
        checks.append(("אין id ב-revision -> שגיאה", False))
    except ValueError:
        checks.append(("אין id ב-revision -> שגיאה", True))

    checks.append(
        (
            "שולפת את גוף הוויקיטקסט עצמו, לא ה-XML",
            extract_wikitext_body(_EXPORT_XML) == "תוכן כלשהו",
        )
    )
    no_text_xml = "<mediawiki><page><revision><id>1</id></revision></page></mediawiki>"
    try:
        extract_wikitext_body(no_text_xml)
        checks.append(("אין text ב-revision -> שגיאה", False))
    except ValueError:
        checks.append(("אין text ב-revision -> שגיאה", True))

    # is_primary_legislation_title: חוק/חוק-יסוד/פקודה/דבר המלך - לא
    # תקנות/צווים/כללים (חקיקת משנה). פקודות/דברי המלך נכנסו ב-2026-09-16
    # אחרי שההחלטה המקורית להוציא אותן (2026-09-13, לפי צורת שם) התבררה
    # כשגויה - ראו decisions.md ל-post-mortem המלא.
    checks.append(("חוק רגיל -> True", is_primary_legislation_title("חוק המחשבים")))
    checks.append(("חוק-יסוד -> True", is_primary_legislation_title("חוק-יסוד: הכנסת")))
    checks.append(("תקנות -> False", not is_primary_legislation_title("תקנות שמאי מקרקעין (אגרות)")))
    checks.append(("צו -> False", not is_primary_legislation_title("צו המועצות המקומיות")))
    checks.append(("כללי -> False", not is_primary_legislation_title("כללי הרשות השנייה")))
    checks.append(("פקודת -> True (תוקן 2026-09-16)", is_primary_legislation_title("פקודת המסים (גביה)")))
    checks.append(("פקודה (בלי ת') -> True", is_primary_legislation_title("פקודה לפרשנות [נוסח חדש]")))
    checks.append(("דבר המלך -> True", is_primary_legislation_title("דבר המלך על הטיס במושבות (הטלת חוקים), 1937")))
    checks.append(("'חוקת' (בלי רווח) -> False, לא false positive", not is_primary_legislation_title("חוקת העבודה")))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(("OK  " if passed else "FAIL"), name)
    print("\nתוצאה:", "עבר" if ok else "נכשל")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
