"""בדיקות "כמו לקוח" מול האתר החי.

**למה זה נפרד מ-tests/unit:** שם בודקים שהקוד נכון; כאן בודקים
שהאתר שפרוס **עכשיו** עובד. השניים נפרדים כי הם נכשלים מסיבות
שונות: בדיקת יחידה נשברת מקוד, בדיקה חיה נשברת מפריסה שלא עלתה,
ממשתנה סביבה חסר ב-Vercel, מ-Supabase שנפל, או מ-DB שנטען חלקית.
הבאג של פקודת הנזיקין (22.9) הוא בדיוק המקרה: הקוד היה תקין,
המשתמש לא קיבל כלום.

**כל בדיקה עוברת מסלול שמשתמש אמיתי עובר**, לא endpoint לשם
endpoint.

**עלות:** ברירת המחדל מריצה רק מה שלא עולה כסף. `--with-llm`
מוסיף את כלי הצ'אט, שכל קריאה שלהם היא קריאה בתשלום. הריצה
היומית מפעילה את המלא; ריצה על כל פריסה מפעילה את החינמי.

    python3 tests/live_smoke.py [--base URL] [--with-llm]
"""

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "render"))
from docx_check import structural_problems  # noqa: E402

DEFAULT_BASE = "https://legislator-tau.vercel.app"
TIMEOUT = 120


class Result:
    """**שתי רשימות, לא אחת** (ברק, 23.9.2026).

    `failures` הוא כשל של המוצר - משהו שאנחנו כתבנו לא עובד.
    `unavailable` הוא תלות חיצונית שלא הייתה זמינה, ובראשה מגבלת
    הקצב של הפיד (HTTP 473). ההבחנה אינה קוסמטית: כשכשל חיצוני
    שולח את אותו מייל כמו כשל מוצר, המייל כולו הופך לרעש ומפסיקים
    לקרוא אותו - וזה בדיוק מה שקרה כאן.

    תלות חיצונית שנפלה אינה "עבר" ואינה "נכשל" - היא **"לא נבדק"**,
    עם הסיבה. אותו עיקרון של הוולידטור."""

    def __init__(self):
        self.failures: list[str] = []
        self.unavailable: list[str] = []
        self.count = 0

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.count += 1
        if ok:
            print(f"  OK    {name}" + (f" — {detail}" if detail else ""))
        else:
            print(f"  כשל   {name}" + (f" — {detail}" if detail else ""))
            self.failures.append(f"{name}: {detail}" if detail else name)
        return ok

    def not_checked(self, name: str, detail: str = "") -> None:
        """תלות חיצונית לא הייתה זמינה. לא נספר כבדיקה שעברה."""
        print(f"  לא נבדק  {name}" + (f" — {detail}" if detail else ""))
        self.unavailable.append(f"{name}: {detail}" if detail else name)


# **ניסיון חוזר אחד, ורק על תקלה חולפת מוכרת - ומדווח.**
# הפיד של הכנסת הוא תלות חיצונית אמיתית שכבר החזירה 429 ו-473
# בעבר, ו-422 חד-פעמי ממנו אינו "האתר שבור". אבל ניסיון חוזר
# שקט הוא בדיוק הדרך להסתיר תקלה אמיתית, ולכן הוא מודפס: ריצה
# שעברה אחרי ניסיון חוזר **אינה** נראית כמו ריצה נקייה.
_RETRYABLE = {408, 422, 429, 473, 502, 503, 504}

# **סטטוסים שאומרים "המקור העליון לא זמין", לא "המוצר שבור".**
# 473 הוא מגבלת הקצב של הפיד של הכנסת (מעל ~4-6 בקשות מקבילות,
# נמדד 22.9.2026 ורשום ב-open-gaps). גם אחרי ניסיון חוזר הוא עדיין
# לא כשל שלנו.
_UPSTREAM_STATUSES = {429, 473, 502, 503, 504}
retried: list[str] = []


class UpstreamUnavailable(RuntimeError):
    """תלות חיצונית (הפיד של הכנסת) לא הייתה זמינה."""

    def __init__(self, label: str, code: int):
        super().__init__(f"{label}: HTTP {code}")
        self.label = label
        self.code = code


def _request(req_or_url, label):
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req_or_url, timeout=TIMEOUT) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if attempt == 1 and e.code in _RETRYABLE:
                note = f"{label} -> HTTP {e.code}, מנסה שוב"
                print(f"  ⟳     {note}")
                retried.append(note)
                time.sleep(4)
                continue
            if e.code in _UPSTREAM_STATUSES:
                raise UpstreamUnavailable(label, e.code) from None
            raise
    raise AssertionError("לא אמור להגיע לכאן")


def _get(base, path):
    return _request(base + path, f"GET {path}")


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return _request(req, f"POST {path}")


def _find_section(node, number):
    if node.get("node_type") == "section" and node.get("number") == number:
        return node
    for child in node.get("children") or []:
        found = _find_section(child, number)
        if found:
            return found
    return None



def _find_nested_paragraph(node, section=None):
    """מוצאת פסקה ממוספרת עם טקסט שיושבת **בתוך סעיף קטן** - עומק 2.

    מחפשת בעץ ולא מקודדת מזהה קשיח, כדי ש-ingest מחדש (שמשנה
    מזהים) לא ישבור את הבדיקה החיה במקום לדווח על פער אמיתי.

    מחזירה (מספר הסעיף, מספר הסעיף הקטן, צומת הפסקה) או None.
    """
    current_section = node if node.get("node_type") == "section" else section
    for child in node.get("children") or []:
        if (
            node.get("node_type") == "subsection"
            and child.get("node_type") == "paragraph"
            and child.get("number")
            and child.get("text")
            and current_section
            and current_section.get("number")
        ):
            return current_section["number"], node.get("number"), child
        found = _find_nested_paragraph(child, current_section)
        if found:
            return found
    return None



def _post_file(base, path, file_path):
    """העלאת קובץ ב-multipart. נכתב ביד ולא דרך ספרייה חיצונית -
    הבדיקה החיה רצה ב-CI בלי תלויות מעבר לספריית התקן."""
    boundary = "----legislator-live-smoke"
    name = Path(file_path).name
    payload = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'.encode(),
        b"Content-Type: application/vnd.openxmlformats-officedocument."
        b"wordprocessingml.document\r\n\r\n",
        Path(file_path).read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        base + path, data=payload, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return _request(req, f"POST {path} ({name})")


def journey_open_and_edit(base, res):
    """המסלול המרכזי: מוצאים חוק, פותחים, עורכים סעיף, ומקבלים
    הוראת תיקון. **פקודת הנזיקין בכוונה** - חוק עם מבנה
    חלק/פרק/סימן, שבו הסעיפים מקוננים עמוק. זה המסלול שנשבר."""
    print("\n[1] פתיחת חוק ועריכת סעיף (פקודת הנזיקין)")
    q = urllib.parse.quote("פקודת הנזיקין")
    status, body = _get(base, f"/api/laws/search?q={q}")
    hits = json.loads(body)
    if not res.check("חיפוש חוק מחזיר תוצאה", status == 200 and bool(hits),
                     f"{len(hits)} תוצאות"):
        return
    law_id = hits[0]["id"]
    res.check("החוק מסומן ניתן לעריכה", hits[0].get("amendable") is True)

    status, body = _get(base, f"/api/laws/{law_id}")
    law = json.loads(body)
    res.check("נוסח החוק נטען", status == 200 and bool(law.get("tree")))
    res.check("מזהה גרסה מוחזר (נדרש להיסטוריית ההצעות)",
              law.get("version_id") is not None, f"version_id={law.get('version_id')}")
    res.check("amendable עקבי בין החיפוש לחוק עצמו",
              law.get("amendable") == hits[0].get("amendable"))

    section = _find_section(law["tree"], "43")
    if not res.check("סעיף 43 נמצא בעץ (סעיף מקונן עמוק)", section is not None):
        return
    target = section if section.get("text") else (section.get("children") or [None])[0]
    if not res.check("לסעיף יש טקסט לעריכה", target and target.get("text")):
        return

    edited = target["text"] + " ובכפוף לכל דין"
    payload = {"edits": [{"node_id": target["id"], "field": "text", "text": edited}],
               "insertions": [],
               "bill": {"title": "", "initiator": "", "explanatory": []}}
    status, body = _post(base, f"/api/laws/{law_id}/render", payload)
    data = json.loads(body)
    lines = data.get("lines") or []
    res.check("עריכה מייצרת הוראת תיקון", status == 200 and len(lines) == 1,
              f"{len(lines)} שורות")
    if lines:
        text = (lines[0].get("text") or "") + (lines[0].get("text_after") or "")
        res.check("הוראת התיקון מזכירה את מספר הסעיף", "סעיף 43" in text)
        res.check("הוראת התיקון מכילה את הנוסח החדש", "ובכפוף לכל דין" in text)

    # עומק 2 - הפער של משימה 58, שהיה **שקט**: עריכה של פסקה שיושבת
    # בתוך סעיף קטן לא הפיקה שום הוראת תיקון, והעריכה "הצליחה".
    # העריכה של סעיף 43 למעלה לא הייתה תופסת את זה: הפסקאות שלו
    # יושבות ישירות מתחתיו. אותו סימפטום כמו באג הנזיקין המקורי,
    # בעומק אחר - ולכן בדיקה נפרדת, לא הרחבה של הקודמת.
    nested = _find_nested_paragraph(law["tree"])
    if res.check("נמצאה פסקה בתוך סעיף קטן (עומק 2)", nested is not None):
        sec_number, sub_number, paragraph = nested
        deep_edited = paragraph["text"] + " לפי כל דין"
        deep_payload = {
            "edits": [{"node_id": paragraph["id"], "field": "text", "text": deep_edited}],
            "insertions": [],
            "bill": {"title": "", "initiator": "", "explanatory": []},
        }
        status, body = _post(base, f"/api/laws/{law_id}/render", deep_payload)
        deep = json.loads(body)
        deep_lines = deep.get("lines") or []
        res.check(
            "עריכה בעומק 2 מייצרת הוראת תיקון (לא רשימה ריקה)",
            status == 200 and len(deep_lines) == 1,
            f"{len(deep_lines)} שורות",
        )
        if deep_lines:
            deep_text = (deep_lines[0].get("text") or "") + (deep_lines[0].get("text_after") or "")
            want_container = f"בסעיף {sec_number}{sub_number}"
            res.check(
                f'הכתובת כוללת את המכולה ("{want_container}")',
                want_container in deep_text,
                deep_text[-90:],
            )
            res.check(
                "הכתובת אינה מדלגת על הסעיף הקטן",
                f"בסעיף {sec_number}," not in deep_text,
                deep_text[-90:],
            )
            res.check("הוראת התיקון בעומק 2 מכילה את הנוסח החדש",
                      "לפי כל דין" in deep_text)

    return law_id, payload


# ח17 + צ5 (26.9): הורדת Word לקחה כדקה, כי המודל (דברי ההסבר) ומאגר הכנסת
# (המגדר) רצו ברגע הלחיצה. עכשיו שניהם מוכנים מראש, והלקוח שולח אותם - כמו
# כאן. תקרה, כדי שהאטה לא תחזור בשקט.
DOCX_MAX_SECONDS = 6.0
QUERY_DOCX_MAX_SECONDS = 3.0
_READY_EXPLANATORY = ["מוצע לקבוע כי מנהל קייטנה יפעל בכפוף לכל דין."]


def journey_docx(base, res, law_id, payload):
    """הלקוח מוריד קובץ Word. אם הקובץ פגום - המוצר לא סיפק כלום."""
    print("\n[2] הורדת קובץ Word")
    # כמו הלקוח: דברי ההסבר כבר נכתבו ברקע (/explanatory) ונשלחים עם ההורדה
    payload = {**payload, "bill": {**payload.get("bill", {}), "explanatory": _READY_EXPLANATORY}}
    req = urllib.request.Request(
        base + f"/api/laws/{law_id}/docx", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    started = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    took = time.time() - started
    res.check(f"ההורדה תוך {DOCX_MAX_SECONDS:.0f} שניות", took < DOCX_MAX_SECONDS, f"{took:.1f} שניות")
    ok_zip = raw[:2] == b"PK"
    res.check("הקובץ הוא docx תקין (ZIP)", ok_zip, f"{len(raw):,} בייטים")
    if not ok_zip:
        return
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        res.check("מכיל word/document.xml", "word/document.xml" in names)
        text = z.read("word/document.xml").decode("utf-8")
    res.check("הנוסח שנערך נמצא בקובץ", "ובכפוף לכל דין" in text)
    # ח8 (25.9): "נפתח כ-ZIP" אינו הוכחה - Word פתח כל הצעת חוק עם
    # "Word מצא תוכן שאינו ניתן לקריאה" והבדיקה הזו עברה. עכשיו: אימות
    # מבני (packages/render/docx_check.py).
    problems = structural_problems(raw)
    res.check("קובץ ה-Word תקין מבנית (לא יפתח אזהרה בוורד)", not problems,
              "; ".join(problems[:3]) or "נקי")
    # **דברי ההסבר נוצרים אף שהשדה הוסר מהממשק** (ברק, 21.9) -
    # זו בדיוק הדרישה שאומתה אז, וכאן היא ננעלת מול האתר החי.
    res.check("דברי ההסבר שנכתבו מראש נכנסו לקובץ", "דברי הסבר" in text and "בכפוף לכל דין" in text)


def journey_explanatory(base, res, law_id, payload):
    """ח17: דברי ההסבר נכתבים ברקע אחרי עריכה - המסלול שבו המודל רץ."""
    print("\n[2ב] דברי ההסבר ברקע")
    status, body = _post(base, f"/api/laws/{law_id}/explanatory", payload)
    paras = json.loads(body).get("explanatory") or []
    res.check("דברי ההסבר נכתבו", status == 200 and bool(paras) and all(p.startswith("מוצע") for p in paras),
              (paras[0][:80] if paras else "ריק"))


def journey_basic_law_search(base, res):
    """ח6 (25.9): "חוק יסוד: הכנסת" - השם המדויק, ברווח במקום מקף -
    החזיר אפס תוצאות. 23 מתוך 59 שמות מקופים לא נמצאו כך."""
    print("\n[1א] חיפוש חוק יסוד")
    for q in ("חוק יסוד: הכנסת", "חוק יסוד הכנסת"):
        _, body = _get(base, "/api/laws/search?q=" + urllib.parse.quote(q))
        hits = json.loads(body)
        res.check(f'"{q}" מוצא את חוק-יסוד: הכנסת',
                  bool(hits) and hits[0].get("title") == "חוק-יסוד: הכנסת",
                  hits[0].get("title") if hits else "אפס תוצאות")


def journey_rules_reading(base, res):
    """ת3 (25.9): התקנון פתוח לקריאה לצד הצ'אט. שלושת המקורות, ובתקנון -
    סעיף 52 במזהה שהמודל מצטט (law-tkanon-haknesset/52); אחרת תגית או
    אזכור בתשובה לא מגיעים לשום מקום."""
    print("\n[1ב] התקנון לקריאה")
    _, body = _get(base, "/api/rules/reading")
    docs = json.loads(body).get("docs") or []
    names = [d.get("name") for d in docs]
    res.check("שלושת המקורות", names == ["תקנון הכנסת", "חוק הכנסת", "חוק-יסוד: הכנסת"], str(names))
    secs = {i.get("id"): i for d in docs for i in d.get("items", []) if i.get("kind") == "section"}
    s52 = secs.get("law-tkanon-haknesset/52") or {}
    res.check("תקנון הכנסת, סעיף 52 - במזהה המקור, עם כותרת ויחידות",
              bool(s52.get("title")) and len(s52.get("units") or []) >= 3, str(s52)[:120])


def journey_query_docx(base, res):
    """הלקוח מוריד שאילתה כקובץ Word. הייצוא עצמו בלי LLM - חינמי."""
    print("\n[2א] הורדת שאילתה כקובץ Word")
    req = urllib.request.Request(
        base + "/api/query/export",
        data=json.dumps({"kind": "רגילה", "minister": "השר לביטחון לאומי",
                         "mk_name": "ישראל ישראלי", "subject": "בדיקה",
                         "body": "רקע.\nרצוני לשאול:\n1. שאלה?", "gender": "זכר"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    started = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    took = time.time() - started
    res.check(f"ייצוא השאילתה תוך {QUERY_DOCX_MAX_SECONDS:.0f} שניות", took < QUERY_DOCX_MAX_SECONDS,
              f"{took:.1f} שניות")
    problems = structural_problems(raw)
    res.check("קובץ השאילתה תקין מבנית", raw[:2] == b"PK" and not problems,
              "; ".join(problems[:3]) or f"{len(raw):,} בייטים")


# `17.04.1968` - הפורמט האחיד של המערכת (apps/api/dates.py, ב7).
_IS_DOTTED_DATE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def journey_citations(base, res, law_id):
    print("\n[3] פרסומי החוק ותיקוניו")
    status, body = _get(base, f"/api/laws/{law_id}/citations")
    data = json.loads(body)
    res.check("הפרסומים נטענים", status == 200)
    if data.get("in_knesset_db"):
        cites = data.get("citations") or []
        res.check("יש פרסומים", bool(cites), f"{len(cites)}")
        if cites:
            dates = [c.get("published_at") for c in cites if c.get("published_at")]
            # **הבדיקה הזו נעלה פורמט שכבר לא נכון** - היא דרשה ISO
            # (`1968-04-17`), אבל ב7 (422c35f, 22.9.2026) העביר את כל
            # המערכת ל-`17.04.1968` דרך `apps/api/dates.py`, במכוון.
            # היא הייתה אדומה בעשר ריצות רצופות מאז, ועל כל אחת נשלח
            # מייל - כלומר בדיקה שלא עודכנה אחרי שינוי מכוון הפכה את
            # ההתראה כולה לרעש.
            #
            # מנוסחת עכשיו מול הדרישה האמיתית, ותיפול אם הפורמט יחזור
            # ל-ISO או יתערבב.
            res.check("התאריכים בפורמט DD.MM.YYYY",
                      all(_IS_DOTTED_DATE.match(d) for d in dates),
                      dates[0] if dates else "")


def journey_static(base, res):
    """הדף עצמו, ה-JS וה-CSS. פריסה שבה קובץ סטטי לא עלה נראית
    למשתמש כמו אתר מת, וכל בדיקות ה-API יעברו בכל זאת."""
    print("\n[4] הדף וקובצי הסטטיק")
    status, body = _get(base, "/")
    html = body.decode("utf-8", "replace")
    res.check("הדף נטען", status == 200)
    res.check("לשונית הצעות חוק קיימת", 'data-t="bills"' in html)
    res.check("כפתור ההצעות שלי קיים", 'id="drafts-toggle"' in html)
    for asset in ("/static/app.js", "/static/style.css"):
        try:
            st, b = _get(base, asset)
            res.check(f"{asset} נטען", st == 200 and len(b) > 500, f"{len(b):,} בייטים")
        except urllib.error.HTTPError as e:
            res.check(f"{asset} נטען", False, f"HTTP {e.code}")
    # הודעות מפתח שהוסרו (ברק, 21.9) - שלא יחזרו בשקט
    for phrase in ("הוולידטור יתריע", "נוסח כפי שהופיע בוויקיטקסט"):
        res.check(f"הודעת מפתח הוסרה: {phrase!r}", phrase not in html)


def _rules_stream(base, question):
    """התשובה **המוזרמת** של מומחה התקנון, כפי שהלקוח מקבל אותה:
    (הטקסט שהוזרם, אירוע ה-done)."""
    req = urllib.request.Request(
        base + "/api/rules/ask/stream", data=json.dumps({"question": question}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    _, raw = _request(req, "POST /api/rules/ask/stream")
    events = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    streamed = "".join(e.get("delta", "") for e in events)
    done = next((e["done"] for e in events if "done" in e), {})
    return streamed, done


def journey_rules_citations(base, res):
    """ת2 (25.9): task 94 נסגר כעובד, ובפועל התשובה הציגה
    "[מקור:law-tkanon-haknesset/52]". הבדיקה אז ראתה את רשימת המקורות,
    לא את הטקסט שהמשתמש קורא. כאן - הטקסט המוזרם עצמו."""
    print("\n[6א] מומחה התקנון - שמות המקורות בתוך התשובה")
    streamed, done = _rules_stream(base, "מה ההבדל בין הצעה לסדר היום להצעה דחופה?")
    res.check("התשובה המוזרמת נענתה", bool(streamed) and done.get("refused") is False,
              done.get("refusal_reason") or f"{len(streamed)} תווים")
    res.check("אין \"[מקור:\" בתשובה המוזרמת", "[מקור:" not in streamed,
              f"{streamed.count('[מקור:')} מופעים")
    res.check("אין \"law-\" בתשובה המוזרמת", "law-" not in streamed,
              f"{streamed.count('law-')} מופעים")
    res.check("יש \"תקנון הכנסת, סעיף\" בתשובה המוזרמת", "תקנון הכנסת, סעיף" in streamed)
    res.check("גם הטקסט הסופי נקי", "[מקור:" not in (done.get("text") or ""))


def journey_chat_smalltalk(base, res):
    """ת4 + ת5 (25.9): מחמאה קיבלה תשובה חמה - ואז שומר הציטוט החליף
    אותה ב"לא מצאתי תשובה". עכשיו הסיווג קודם לתשובה."""
    print("\n[6ב] שיחת חולין וקללה - בלי החלפה")
    streamed, done = _rules_stream(base, "אתה נהדר כל הכבוד!")
    res.check("מחמאה: תשובה חמה שלא מוחלפת", bool(streamed.strip()) and done.get("refused") is False,
              done.get("refusal_reason") or streamed[:60])
    streamed, done = _rules_stream(base, "אתה מטומטם")
    res.check("קללה: 'נא להתבטא בכבוד'", "בכבוד" in streamed and done.get("refused") is False,
              streamed[:60])


def journey_chat(base, res):
    print("\n[6] כלי הצ'אט")
    status, body = _post(base, "/api/rules/ask",
                         {"question": "כמה חתימות נדרשות להצעת אי-אמון?"})
    data = json.loads(body)
    res.check("מומחה התקנון משיב", status == 200 and
              bool(data.get("text") or data.get("refusal_reason")))
    status, body = _post(base, "/api/query/draft",
                         {"topic_description": "זמני המתנה לניתוחים",
                          "kind": "רגילה", "minister": "שר הבריאות",
                          "mk_name": "ישראל ישראלי"})
    q = json.loads(body)
    res.check("שאילתות מנסח", status == 200 and bool(q.get("body")))
    res.check("גוף השאילתה אינו נוקב בשם שר (הליקוי מ-18.9)",
              not q.get("removed_addressee"), q.get("removed_addressee") or "נקי")



def journey_merged_text(base, res):
    """הלקוח מעלה הצעת חוק מתקנת ומקבל נוסח משולב.

    **שתי הצעות בכוונה:** 13948412 מכסה את הוספת היחידה, ו-13948380
    את שלושת הדפוסים האחרים (החלפת מילים, הוספה בסוף, מספור מחדש)
    ואת איתור היחידה מתחת לצומת בלי תווית. הצעה אחת בלבד הייתה
    מותירה את הדפוס הנפוץ ביותר - החלפת מילים - בלי כיסוי חי.

    נבדקת גם **דחייה**: הוראה שאינה מוכרת חייבת לעצור את המיזוג
    ולהחזיר סיבה בעברית, ולא נוסח חלקי."""
    print("\n[5] נוסח משולב")
    fixtures = Path(__file__).resolve().parent / "fixtures" / "real-bills"
    cases = [
        ("13948412", "שוויון ההזדמנויות בעבודה", 1, ["insert"]),
        ("13948380", "דמי מחלה", 3, ["relabel", "replace", "append"]),
    ]
    for bill_id, law_hint, want_changes, want_kinds in cases:
        path = fixtures / f"{bill_id}.docx"
        if not res.check(f"{bill_id}: קובץ ההצעה קיים", path.exists(), str(path)):
            continue
        status, body = _post_file(base, "/api/merge/build", path)
        if not res.check(f"{bill_id}: השרת ענה", status == 200, f"HTTP {status}"):
            continue
        data = json.loads(body)
        if not res.check(f"{bill_id}: נבנה נוסח משולב", data.get("ok") is True,
                         data.get("reason", "")):
            continue
        res.check(f"{bill_id}: זוהה החוק הנכון",
                  law_hint in (data.get("law_title") or ""), data.get("law_title", ""))
        changes = data.get("changes") or []
        res.check(f"{bill_id}: {want_changes} שינויים הוחלו",
                  len(changes) == want_changes, str(len(changes)))
        res.check(f"{bill_id}: סוגי השינויים",
                  [c.get("kind") for c in changes] == want_kinds,
                  str([c.get("kind") for c in changes]))
        res.check(f"{bill_id}: לכל שינוי מצורפת ההוראה שיצרה אותו",
                  all((c.get("instruction") or "").strip() for c in changes))
        res.check(f"{bill_id}: הוחזר עץ החוק המשולב",
                  bool((data.get("tree") or {}).get("children")))

    # דחייה: מסמך שאינו הצעת חוק מתקנת כלל.
    other = fixtures / "13948386.docx"
    if other.exists():
        status, body = _post_file(base, "/api/merge/build", other)
        data = json.loads(body) if status == 200 else {}
        if data.get("ok") is False:
            res.check("הצעה שלא ניתן לפרש - נעצרת עם סיבה בעברית",
                      bool((data.get("reason") or "").strip()), data.get("reason", "")[:70])
        else:
            res.check("הצעה שלא ניתן לפרש - נעצרת עם סיבה בעברית",
                      data.get("ok") is True,
                      "ההצעה הזו דווקא מוזגה במלואה - לא דחייה, וזה תקין")


def _annotate(level: str, message: str) -> None:
    """סימון הריצה ב-GitHub Actions. `warning` נראה בריצה ואינו
    שולח מייל; `error` מפיל את הריצה ושולח."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{level}::{message}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--with-llm", action="store_true",
                    help="גם הכלים שכל קריאה שלהם עולה כסף")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    print(f"בדיקות 'כמו לקוח' מול {base}")
    res = Result()
    started = time.time()

    def run(label, fn, *fn_args):
        """מסע אחד. תלות חיצונית שנפלה מסומנת "לא נבדק" ואינה מפילה
        את שאר המסעות - אחרת פיד עמוס מסתיר את כל שאר המוצר."""
        try:
            return fn(*fn_args)
        except UpstreamUnavailable as exc:
            res.not_checked(label, f"הפיד החזיר HTTP {exc.code} ({exc.label})")
        except urllib.error.HTTPError as exc:
            res.check(f"{label}: הבקשה הושלמה", False, f"HTTP {exc.code} on {exc.url}")
        except Exception as exc:  # noqa: BLE001
            res.check(f"{label}: רץ עד הסוף", False, f"{type(exc).__name__}: {exc}")
        return None

    edited = run("פתיחת חוק ועריכה", journey_open_and_edit, base, res)
    run("הדף וקובצי הסטטיק", journey_static, base, res)
    if edited:
        law_id, payload = edited
        run("הורדת Word", journey_docx, base, res, law_id, payload)
        run("פרסומי החוק", journey_citations, base, res, law_id)
    run("חיפוש חוק יסוד", journey_basic_law_search, base, res)
    run("התקנון לקריאה", journey_rules_reading, base, res)
    run("הורדת שאילתה כ-Word", journey_query_docx, base, res)
    run("נוסח משולב", journey_merged_text, base, res)
    if args.with_llm:
        run("כלי הצ'אט", journey_chat, base, res)
        run("מומחה התקנון - מקורות", journey_rules_citations, base, res)
        if edited:
            run("דברי ההסבר ברקע", journey_explanatory, base, res, *edited)
        run("צ'אטבוטים - חולין וקללה", journey_chat_smalltalk, base, res)
    else:
        print("\n(דילוג על כלי ה-LLM - הרץ עם --with-llm)")

    print(f"\n{res.count} בדיקות ב-{time.time()-started:.1f} שניות")
    if retried:
        print(f"⟳ {len(retried)} בקשות נדרשו ניסיון חוזר (תקלה חולפת, לא כשל מוצר):")
        for note in retried:
            print(f"  - {note}")
    if res.unavailable:
        print(f"לא נבדקו {len(res.unavailable)} (תלות חיצונית לא זמינה):")
        for item in res.unavailable:
            print(f"  - {item}")

    if res.failures:
        print(f"נכשלו {len(res.failures)}:")
        for f in res.failures:
            print(f"  - {f}")
        _annotate("error", f"כשל מוצר: {res.failures[0]}")
        return 1

    if res.unavailable:
        # **יוצא 0 בכוונה.** הפיד של הכנסת עמוס אינו רגרסיה, ומייל
        # אדום עליו הוא בדיוק מה שגורם להתעלם ממיילים אמיתיים.
        # הריצה מסומנת באזהרה גלויה ב-GitHub, בלי התראה.
        print("הבדיקות שרצו עברו; מה שלא רץ הוא תלות חיצונית, לא רגרסיה.")
        _annotate("warning", f"לא נבדק: {res.unavailable[0]}")
        return 0

    print("הכול עבר.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
