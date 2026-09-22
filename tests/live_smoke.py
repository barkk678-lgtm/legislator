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
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

DEFAULT_BASE = "https://legislator-tau.vercel.app"
TIMEOUT = 120


class Result:
    def __init__(self):
        self.failures: list[str] = []
        self.count = 0

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.count += 1
        if ok:
            print(f"  OK    {name}" + (f" — {detail}" if detail else ""))
        else:
            print(f"  כשל   {name}" + (f" — {detail}" if detail else ""))
            self.failures.append(f"{name}: {detail}" if detail else name)
        return ok


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=TIMEOUT) as r:
        return r.status, r.read()


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read()


def _find_section(node, number):
    if node.get("node_type") == "section" and node.get("number") == number:
        return node
    for child in node.get("children") or []:
        found = _find_section(child, number)
        if found:
            return found
    return None


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
    return law_id, payload


def journey_docx(base, res, law_id, payload):
    """הלקוח מוריד קובץ Word. אם הקובץ פגום - המוצר לא סיפק כלום."""
    print("\n[2] הורדת קובץ Word")
    req = urllib.request.Request(
        base + f"/api/laws/{law_id}/docx", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    ok_zip = raw[:2] == b"PK"
    res.check("הקובץ הוא docx תקין (ZIP)", ok_zip, f"{len(raw):,} בייטים")
    if not ok_zip:
        return
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        res.check("מכיל word/document.xml", "word/document.xml" in names)
        text = z.read("word/document.xml").decode("utf-8")
    res.check("הנוסח שנערך נמצא בקובץ", "ובכפוף לכל דין" in text)
    # **דברי ההסבר נוצרים אף שהשדה הוסר מהממשק** (ברק, 21.9) -
    # זו בדיוק הדרישה שאומתה אז, וכאן היא ננעלת מול האתר החי.
    res.check("דברי הסבר נוצרו אוטומטית", "דברי הסבר" in text)


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
            res.check("התאריכים בפורמט ISO (הממשק ממיר לעברי)",
                      all(len(d) == 10 and d[4] == "-" for d in dates),
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


def journey_research(base, res):
    """כלי המחקר. **הבדיקה החשובה כאן היא הסירוב** - שאלה עם
    מגבלה שאי אפשר להחיל חייבת לא לענות על שאלה אחרת (ברק,
    22.9). זו קריאת LLM, ולכן רק עם --with-llm."""
    print("\n[5] כלי המחקר - מגבלה שאי אפשר להחיל")
    status, body = _post(base, "/api/research/ask",
                         {"question": "מי היוזמים הפוריים ביותר בכנסת הנוכחית?"})
    data = json.loads(body)
    res.check("הכלי אינו עונה על שאלה אחרת", data.get("answered") is False,
              f"answered={data.get('answered')}")
    reason = data.get("reason") or ""
    res.check("הנימוק אינו חושף מזהה תבנית פנימי",
              not any(t in reason for t in ("top_initiators", "bills_on_topic", "pass_rates")),
              reason[:70])
    res.check("מוצעת שאלה חלופית", bool(data.get("answerable_instead")),
              data.get("answerable_instead", ""))

    status, body = _post(base, "/api/research/ask",
                         {"question": "מי היוזמים הפוריים ביותר?"})
    plain = json.loads(body)
    res.check("אותה שאלה בלי ההגבלה כן נענית", plain.get("answered") is True,
              f"{len(plain.get('rows') or [])} שורות")


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

    try:
        edited = journey_open_and_edit(base, res)
        journey_static(base, res)
        if edited:
            law_id, payload = edited
            journey_docx(base, res, law_id, payload)
            journey_citations(base, res, law_id)
        if args.with_llm:
            journey_research(base, res)
            journey_chat(base, res)
        else:
            print("\n(דילוג על כלי ה-LLM - הרץ עם --with-llm)")
    except urllib.error.HTTPError as e:
        res.check("הבקשה הושלמה", False, f"HTTP {e.code} on {e.url}")
    except Exception as e:  # noqa: BLE001
        res.check("הבדיקה רצה עד הסוף", False, f"{type(e).__name__}: {e}")

    print(f"\n{res.count} בדיקות ב-{time.time()-started:.1f} שניות")
    if res.failures:
        print(f"נכשלו {len(res.failures)}:")
        for f in res.failures:
            print(f"  - {f}")
        return 1
    print("הכול עבר.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
