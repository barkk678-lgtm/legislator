"""ח9: שלוש דוגמאות לפני/אחרי - דברי ההסבר הישנים (הדטרמיניסטיים, מה שנכנס לקובץ עד היום) מול החדשים."""
import sys, json
sys.path[:0]=["apps/api","packages/corpus","packages/config","packages/amend","packages/render","packages/llm"]
import env_file; env_file.load()
from law_registry import load_law, get_law_config
from schemas import TextEditIn, InsertSectionIn
from apply_changes import apply_pending_changes
from engine import amend
from tree_view import touched_section_numbers
from explanatory_draft import draft_explanatory_notes
from llm_draft import draft_explanatory_llm
from node import find_sections

def run(label, law_id, edits=(), insertions=()):
    before = load_law(law_id)
    cfg = get_law_config(law_id, before)
    res = apply_pending_changes(before, list(edits), list(insertions))
    lines = amend(before, res.after, res.annotations, law_footnote_key=cfg.footnote_key)
    touched = touched_section_numbers(before, res.after)
    print(f"\n===== {label} ({before.full_title})")
    for ln in lines: print("  הוראה:", ln.side_heading, "|", ln.text + ln.text_after)
    print("  --- ישן:"); [print("   ", p) for p in draft_explanatory_notes(lines)]
    print("  --- חדש:"); [print("   ", p) for p in draft_explanatory_llm(lines, before, res.after, touched)]

k = load_law("law-2000037"); s2 = find_sections(k)["2"]
t2 = s2.children[0].text
print("סעיף 2:", t2)
_r1 = run("החלפת מילה", "law-2000037", edits=[TextEditIn(node_id=s2.children[0].id, text=t2.replace("ירושלים", "תל אביב"))])
ky = load_law("kaytanot-1990"); secs = find_sections(ky)
for n in ("2","3","4","5"):
    print("קייטנות", n, secs[n].margin_title, "|", " / ".join(c.text[:90] for c in secs[n].children[:2]))

p5 = secs["5"].children[0]
run("מחיקה", "kaytanot-1990", edits=[TextEditIn(node_id=p5.id, text=p5.text.replace(" או 4", ""))])
run("הוספת סעיף", "kaytanot-1990", insertions=[InsertSectionIn(
    kind="section", anchor_node_id=secs["4"].id, margin_title="חובת ביטוח",
    text="מנהל קייטנה יבטח את המשתתפים בה בביטוח תאונות אישיות.", client_id="c1")])
