"""דף הבית (27.9.2026) - מה שאפשר לבדוק בלי דפדפן. הבדיקה בדפדפן:
tests/browser/test_home.py.

1. **כולם נוחתים בדף הבית** - הלשונית הפעילה בטעינה, ו"דף הבית" ראשון בתפריט.
2. **שמונת הכרטיסים בנוסח של ברק**, מילה במילה.
3. יצירת קשר בתחתית התפריט, עם השדה הנסתר; הרשמה/כניסה - למקום השמור.
4. **באג 186**: CONV_LIMIT/CONV_SHOWN הוגדרו אחרי שהרכיב הראשון של ההיסטוריה
   נטען. const שנקרא לפני ההגדרה זורק - שיחה שמורה אחת בהצעה לסדר הפילה את
   כל app.js בטעינה (שוחזר באתר החי, 27.9).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "apps" / "api" / "templates" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "apps" / "api" / "static" / "app.js").read_text(encoding="utf-8")

CARDS = {
    "bills": ("הצעות חוק", "עורכים את החוק כמו טקסט רגיל, והוראות התיקון נכתבות לבד — לפי כללי הניסוח."),
    "merge": ("נוסח משולב", "מעלים הצעת חוק, ורואים את החוק כפי שייראה אם תתקבל."),
    "query": ("שאילתות", "שאילתה לשר בפורמט המקובל, ולצדה שאילתות קודמות באותו נושא."),
    "agenda": ("הצעה לסדר", 'הצעה לסדר היום ליו"ר הכנסת, בטופס של הכנסת.'),
    "rules": ("מומחה התקנון", "שאלות על התקנון בשפה פשוטה, עם הפניה לסעיף בכל תשובה."),
    "proto": ("תקציר הצעה", "מעלים הצעת חוק, ומקבלים תקציר של מה שהיא מבקשת לשנות."),
    "critique": ("בודק הניסוח", "כתבת הצעת חוק בעצמך? בדיקה מול כללי ניסוח החקיקה, תוך שניות."),
    "reservations": ("הסתייגויות", "מעלים את ההצעה לקריאה שנייה ושלישית, ומקבלים הסתייגויות מוכנות להגשה."),
}


def test_everyone_lands_on_home():
    assert '<div class="tab on" id="home">' in HTML
    assert len(re.findall(r'class="tab on"', HTML)) == 1, "רק לשונית אחת פעילה בטעינה"
    first = re.search(r'<div class="nav" id="nav">\s*<button class="on" data-t="(\w+)"', HTML)
    assert first and first.group(1) == "home", "דף הבית - הפריט הראשון בתפריט, והפעיל"
    assert '<div class="topbar" data-bar="bills" hidden>' in HTML
    assert JS.rstrip().endswith('switchTab("home");')


def test_tool_cards_text():
    cards = re.findall(r'<button type="button" class="tool-card" data-tool="(\w+)">.*?<b>(.*?)</b><span>(.*?)</span>',
                       HTML, re.S)
    got = {tool: (name, line) for tool, name, line in cards}
    assert list(got) == list(CARDS), list(got)
    for tool, want in CARDS.items():
        assert got[tool] == want, (tool, got[tool])
    # כל כרטיס מוביל ללשונית שקיימת
    for tool in CARDS:
        assert f'<div class="tab" id="{tool}">' in HTML, tool


def test_signup_and_contact_markup():
    for href in ('href="/auth/signup"', 'href="/auth/login"'):
        assert href in HTML, href
    assert "הרשמה עם חשבון Google" in HTML and "כל העבודה הפרלמנטרית, בארגז כלים אחד" in HTML
    assert "מנוי חודשי אישי. נרשמים עם חשבון Google, ומתחילים לעבוד." in HTML
    foot = HTML[HTML.index('<div class="rail-foot">'):HTML.index("</nav>")]
    assert 'id="contact-open"' in foot and "יצירת קשר" in foot
    assert 'id="contact-website"' in HTML and 'tabindex="-1"' in HTML   # השדה הנסתר
    assert "הפנייה נשלחה" in HTML


def test_no_payment_or_password_fields():
    for word in ("cc-number", "credit", "cvv", "password", "כרטיס אשראי"):
        assert word not in HTML.lower(), word


def test_conv_constants_before_first_use():
    """באג 186 - נכשל על הקוד שלפני התיקון (ההגדרה אחרי agendaHistory)."""
    first_mount = JS.index("= mountConvHistory({")
    for name in ("CONV_LIMIT", "CONV_SHOWN"):
        m = re.search(rf"^const {name} = ", JS, re.M)
        assert m and m.start() < first_mount, f"{name} מוגדר אחרי שהרכיב הראשון כבר נטען"


def test_recent_uses_existing_history_only():
    """'המשך מאיפה שעצרת' - מההיסטוריה שכבר נשמרת, לא ממקור נתונים חדש."""
    body = JS[JS.index("function recentItems()"):JS.index("function openRecent(")]
    assert "readDrafts()" in body and "history.list()" in body
    assert "localStorage" not in body and "fetch(" not in body


for name, fn in sorted(list(globals().items())):
    if name.startswith("test_"):
        fn()
        print(f"  ✓ {name}")
print("test_home_page: כל הבדיקות עברו")
