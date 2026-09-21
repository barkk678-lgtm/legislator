"""הכלי החמישי: מצב האיכות בהסתייגויות, בפרודקשן.

עשרה סעיפים אמיתיים מקובץ הצעת חוק שהועלה - המקבילה ל"עשר שאלות"
בכלים האחרים: כל סעיף הוא קריאה אחת לניסוח ואחת לסינון 86(ד)(2).
"""
import json, mimetypes, time, urllib.request, uuid
from pathlib import Path

BASE = "https://legislator-tau.vercel.app"
HERE = Path(__file__).parent
DOC = HERE / "bill-13821884.docx"
OUT = HERE / "qual10.json"


def multipart(fields, file_field, filename, content):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(
        f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n".encode()
        + content + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


def post(path, fields):
    body, ctype = multipart(fields, "file", DOC.name, DOC.read_bytes())
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={"Content-Type": ctype}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return {"ok": True, "ms": int((time.time()-t0)*1000),
                    "warnings_header": r.headers.get("X-Extraction-Warnings"),
                    "body": json.loads(r.read())}
    except Exception as e:
        raw = ""
        if hasattr(e, "read"):
            try: raw = e.read().decode()[:600]
            except Exception: pass
        return {"ok": False, "ms": int((time.time()-t0)*1000),
                "error": f"{type(e).__name__}: {e}", "body": raw}


res = {}
res["analyze"] = post("/api/reservations/analyze", {})
print("analyze", res["analyze"]["ok"], res["analyze"]["ms"], flush=True)
if res["analyze"]["ok"]:
    print(json.dumps({k: v for k, v in res["analyze"]["body"].items()
                      if k != "per_section"}, ensure_ascii=False)[:500], flush=True)

res["quality"] = post("/api/reservations/quality",
                      {"proposers": "ישראל ישראלי", "sections_limit": "10", "download": "false"})
print("quality", res["quality"]["ok"], res["quality"]["ms"], flush=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print("DONE ->", OUT)
