"""ש2: כמה מקורות נבדקו מתוך כמה - משחזר את תזמור הלקוח (app.js runPastQueries):
בדיקות פתיחה (צמדי מילים, עד 4) יוצאות מיד + פירוק הנושא + יחידות, במקביליות נתונה."""
import json, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
BASE = sys.argv[1]; CONC = int(sys.argv[2]); LABEL = sys.argv[3] if len(sys.argv) > 3 else ""
RETRY = len(sys.argv) > 4 and sys.argv[4] == "retry"
TOPICS = ["מחסור בכוח אדם במשטרת ישראל", "מחסור במורים בבתי ספר תיכוניים", "מצוקת הדיור בפריפריה",
          "אלימות במערכת החינוך", "זמני המתנה לניתוחים בפריפריה", "זיהום אוויר במפרץ חיפה",
          "תחבורה ציבורית בנגב", "יוקר המחיה", "הגנה על עובדים בשעת חירום", "הנגשת שירותי בריאות הנפש"]
def get(path):
    with urllib.request.urlopen(BASE + path, timeout=90) as r:
        return json.loads(r.read())
def unit(words):
    qs = "&".join("w=" + urllib.parse.quote(w) for w in words)
    try:
        get("/api/queries/unit?" + qs); return True
    except Exception:
        return False
tot_ok = tot = 0; t0 = time.time(); per = []
for q in TOPICS:
    ws = q.split()
    probes = [[f"{ws[i]} {ws[i+1]}"] for i in range(len(ws) - 1)][:4]
    try:
        plan = get("/api/queries/plan?q=" + urllib.parse.quote(q))
    except Exception:
        plan = {"units": [{"words": [q]}]}
    keys = {" ".join(p) for p in probes}
    units = probes + [u["words"] for u in plan.get("units", []) if " ".join(u["words"]) not in keys]
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        res = list(ex.map(unit, units))
    if RETRY and not all(res):          # הלקוח החדש: סבב חוזר, אחד-אחד
        for i, ok in enumerate(res):
            if not ok:
                time.sleep(0.4); res[i] = unit(units[i])
    per.append((q, sum(res), len(res))); tot_ok += sum(res); tot += len(res)
    print(f"  {q:34} {sum(res):2}/{len(res)}")
print(f"{LABEL} concurrency={CONC}: {tot_ok}/{tot} מקורות נבדקו ({100*tot_ok/tot:.0f}%), {sum(1 for _,a,b in per if a<b)}/10 חיפושים חלקיים, {time.time()-t0:.0f}s")
