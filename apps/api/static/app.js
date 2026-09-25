"use strict";
/* לקוח משימה 10ב: עריכה חופשית. אין כאן שום לוגיקה משפטית - כל
 * החלטה (מה נתמך, איזו הוראת תיקון נגזרת, איזו תווית תיווצר) מגיעה
 * מהשרת (diff_translate.py/insert_preview.py/apply_changes.py). ה-JS
 * רק שולח את מלוא המצב הנוכחי (edits+insertions) בכל בקשה, ומרנדר
 * מחדש את מלוא העץ מתוך "tree" שחוזר מהשרת - כך שתוכן שהוסף הופך
 * לצומת אמיתי, ניתן לעריכה, לא לתקציר סטטי (ראו TASKS.md 10ב, משוב
 * המשתמש אחרי בדיקה ידנית).
 */

const LEVEL_ORDER = ["section", "subsection", "paragraph", "subparagraph"];
const LEVEL_LABELS = {
  section: "סעיף ראשי",
  subsection: "סעיף קטן",
  paragraph: "פסקה",
  subparagraph: "פסקת משנה",
  definition: "הגדרה",
};

let currentLawId = null;
let originalTextById = {}; // node_id -> טקסט מקורי (מהעץ הפריסטיני, נטען פעם אחת)
let originalMarginTitleById = {}; // node_id -> כותרת שוליים מקורית
let everEditedFieldKeys = new Set(); // "node_id:field" שנערך אי-פעם (גם אם חזר למקור)
let edits = {}; // "node_id:field" -> {node_id, field, text}
let insertions = []; // [{clientId, kind, anchor_node_id, text, margin_title?, label}]

/* **תאריך בעברית: 30.12.2026, עם נקודות.** ISO עם מקפים
 * ("2026-12-30") בתוך משפט עברי נשבר בכיוון הקריאה של הדפדפן -
 * המקף הוא תו ניטרלי, והשנה קופצת לצד השני. הנקודה אינה מפרידה
 * כיוון, ולכן הפורמט הזה נקרא נכון בלי לעטוף ב-LRM/RLM.
 *
 * מחזירה את המחרוזת כפי שהיא אם אינה תאריך ISO - לא ממציאה. */
function formatHebrewDate(value) {
  if (!value) return "";
  const m = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return String(value);
  return `${Number(m[3])}.${Number(m[2])}.${m[1]}`;
}


/* הערות "צריך להיות" (צ״ל) - תיקוני נוסח שמנסחי ויקיטקסט סימנו בגוף
 * החוק, למשל {{ח:סעיף|27|תקנות {{ח:הערה|[צ״ל: עונשין]}}}} בחוק
 * השימוש בהיפנוזה, שם כותרות השוליים של סעיפים 27 ו-28 הוחלפו במקור.
 * 219 מופעים ב-102 חוקים (נמדד 21.9.2026, זהות מול ה-DB).
 *
 * **אזהרה ולא שינוי טקסט:** הנוסח עצמו נשאר בדיוק כפי שהוא. הוא
 * contentEditable ונקרא על ידי צינור העריכה וה-diff, ולכן עטיפת חלק
 * ממנו ב-<span> הייתה נכנסת להוראת התיקון. החיווי יושב בכותרת הצומת,
 * מחוץ לשדות הנערכים.
 *
 * שלוש הצורות שקיימות בקורפוס: "[צ״ל: X]" (236), "[צ״ל X]" (9)
 * ו-"[צ״ל, X]" (1). הסוגר הפותח **חובה** - בלעדיו נתפסים גם אצ״ל,
 * זצ״ל ודצ״ל, שאינם הערות; הם נבדקו במפורש ואינם נתפסים.
 *
 * **בלי תקרת אורך, והסוגר הסוגר אופציונלי.** בחוק מס מינימלי גלובלי
 * (law-2238756) יש שבע הערות שבהן ההערה היא כל הצומת - עד 670 תווים,
 * ואחת בלי "]" כלל. תקרה של 200 תווים החמיצה את כולן. מה שמדייק כאן
 * הוא העוגן הפותח, לא האורך. */
const SCRIVENER_NOTE_RE = /\[\s*צ["\u05f4\u2033\u201d']ל[:,\s][^\]]*\]?/g;

function scrivenerNotes(node) {
  const found = [];
  for (const field of [node.margin_title, node.text]) {
    if (!field) continue;
    const matches = field.match(SCRIVENER_NOTE_RE);
    if (matches) found.push(...matches);
  }
  return found;
}

let insertionCounter = 0;
let insertionClientIds = new Set(); // clientId-ים של הוספות ממתינות/שהתבצעו
let fieldElements = {}; // "node_id:field" -> אלמנט ה-DOM הניתן לעריכה
let insertPreviewSeq = 0; // מונע עדכון תפריט הוספה שכבר נסגר
let renderGeneration = 0; // מונע rebuild מתוך תשובה ישנה שנדחתה על ידי בקשה מאוחרת יותר

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function billMeta() {
  // **אין עוד שדות "שם היוזם" ו"דברי הסבר" בממשק** (ברק,
  // 2026-09-21): סנהדרין ממלאת את היוזם בעצמה, ודברי ההסבר
  // נכתבים על ידי המערכת לתוך קובץ הוורד לפי השינויים בפועל -
  // מי שירוצה לערוך, יערוך בקובץ. הסכימה בשרת לא השתנתה; שולחים
  // ערכים ריקים, והשרת בונה את שניהם כשהם ריקים.
  return {
    title: document.getElementById("bill-title-input").value,
    initiator: "",
    explanatory: [],
  };
}

function editsPayload() {
  return Object.values(edits).map(({ node_id, field, text }) => ({ node_id, field, text }));
}

function insertionsPayload() {
  return insertions.map((ins) => {
    const item = {
      kind: ins.kind, anchor_node_id: ins.anchor_node_id, text: ins.text,
      client_id: ins.clientId,
    };
    if (ins.kind === "section") item.margin_title = ins.margin_title;
    return item;
  });
}

/* חיפוש חוק (autocomplete) - החליף <select> יחיד שהיה סביר לשני
 * חוקי fixture אבל לא ל-1,093 חוקי הקורפוס האמיתי (ברק, 2026-09-16:
 * "תפריט נגלל לא עובד... הבחירה היא הדבר הראשון שהמשתמש עושה").
 * לא טוען מראש את כל 1,093 - שולח /api/laws/search עם debounce, כמו
 * GitHub/Google. השרת כבר מדרג (התאמה מדויקת -> prefix -> substring ->
 * ריבוי-טוקנים, ראו law_search.py) ומגביל ל-20 תוצאות.
 */
let lawSearchDebounceTimer = null;
let lawSearchResults = [];
let lawSearchHighlightIndex = -1;
let lawSearchGeneration = 0; // מונע תשובה-מאוחרת-שהגיעה-מוקדם מלדרוס תוצאה
// טרייה יותר (ברק, 2026-09-16: "ע" לבד - בקשה ראשונה, איטית - דרס
// את "עבודת נשים" שהגיע אחריה ומהר יותר). אותו דפוס בדיוק כמו
// renderGeneration ב-refreshPreview.

function debounceLawSearch(query) {
  clearTimeout(lawSearchDebounceTimer);
  lawSearchDebounceTimer = setTimeout(() => runLawSearch(query), 180);
}

async function runLawSearch(query) {
  const resultsEl = document.getElementById("law-search-results");
  const trimmed = query.trim();
  if (!trimmed) {
    lawSearchGeneration += 1; // מבטל גם תשובות-בדרך קודמות, לא רק את הבאה
    lawSearchResults = [];
    resultsEl.hidden = true;
    resultsEl.innerHTML = "";
    return;
  }
  const myGeneration = ++lawSearchGeneration;
  const laws = await (await fetch(`/api/laws/search?q=${encodeURIComponent(trimmed)}`)).json();
  if (myGeneration !== lawSearchGeneration) return; // תשובה ישנה - נדחית, לא נוגעים ב-DOM
  lawSearchResults = laws;
  lawSearchHighlightIndex = laws.length ? 0 : -1;
  renderLawSearchResults();
}

function renderLawSearchResults() {
  const resultsEl = document.getElementById("law-search-results");
  resultsEl.innerHTML = "";
  if (!lawSearchResults.length) {
    const empty = document.createElement("div");
    empty.className = "law-result-empty";
    empty.textContent = "לא נמצאו חוקים תואמים.";
    resultsEl.appendChild(empty);
    resultsEl.hidden = false;
    return;
  }
  lawSearchResults.forEach((law, idx) => {
    const item = document.createElement("div");
    item.className =
      "law-result-item" +
      (law.amendable ? "" : " unsupported") +
      (idx === lawSearchHighlightIndex ? " highlighted" : "");
    const title = document.createElement("span");
    title.textContent = law.title;
    item.appendChild(title);
    if (!law.amendable) {
      const note = document.createElement("span");
      note.className = "law-result-note";
      note.textContent = "(לא נתמך לעריכה)";
      item.appendChild(note);
    }
    // **חיווי עדכניות, לא רענון.** plan.md §1.2: אם חוק התעדכן
    // אין לשנות את הנוסח תחת המשתמש - רק להודיע. נכתב מהריצה
    // היומית (tools/check_for_update.py).
    if (law.outdated) {
      const stale = document.createElement("span");
      stale.className = "law-result-stale";
      stale.textContent = "● נוסח חדש יותר בוויקיטקסט";
      stale.title = "הנוסח הטעון אינו העדכני. פנו לברק לרענון.";
      item.appendChild(stale);
    }
    // **החיווי על עדכניות שלא נבדקה הוסר** (ברק, 22.9): הוא לא אמר
    // למשתמש דבר שהוא יכול לפעול לפיו. מה שנשאר הוא רק המקרה שבו
    // **ידוע** שיש נוסח חדש יותר - שם יש מה לעשות.
    // הטקסט עצמו אינו מופיע כאן אפילו בהערה: בדיקה נועלת את זה
    // על המקור (tests/unit/test_corpus_freshness.py).
    // mousedown לא click - כדי שהבחירה תתפוס לפני שה-blur של השדה
    // סוגר את תיבת התוצאות (מרוץ אירועים סטנדרטי ב-autocomplete).
    item.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      selectLaw(law);
    });
    resultsEl.appendChild(item);
  });
  resultsEl.hidden = false;
}

let currentLawTitle = null;

async function selectLaw(law) {
  if (law.amendable === false) return;
  clearSimilarBills();   // ההצעות הדומות שייכות להצעה הקודמת
  flushDraftSave();      // לשמור לפני שהמצב מתאפס
  currentLawTitle = law.title;
  document.getElementById("law-search-input").value = law.title;
  document.getElementById("law-search-results").hidden = true;
  await onLawChange(law.id);
}

function initLawSearch() {
  const input = document.getElementById("law-search-input");
  const resultsEl = document.getElementById("law-search-results");
  input.addEventListener("input", () => debounceLawSearch(input.value));
  input.addEventListener("focus", () => {
    if (lawSearchResults.length) renderLawSearchResults();
  });
  input.addEventListener("keydown", (ev) => {
    if (resultsEl.hidden || !lawSearchResults.length) return;
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      lawSearchHighlightIndex = Math.min(lawSearchHighlightIndex + 1, lawSearchResults.length - 1);
      renderLawSearchResults();
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      lawSearchHighlightIndex = Math.max(lawSearchHighlightIndex - 1, 0);
      renderLawSearchResults();
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      const chosen = lawSearchResults[lawSearchHighlightIndex];
      if (chosen) selectLaw(chosen);
    } else if (ev.key === "Escape") {
      resultsEl.hidden = true;
    }
  });
  document.addEventListener("click", (ev) => {
    if (!document.querySelector(".law-picker").contains(ev.target)) resultsEl.hidden = true;
  });
}

function buildOriginalIndex(node) {
  originalTextById[node.id] = node.text;
  originalMarginTitleById[node.id] = node.margin_title || "";
  for (const child of node.children) buildOriginalIndex(child);
}

async function onLawChange(lawId) {
  // חיווי טעינה (ברק, 2026-09-16): פתיחת חוק גדול מה-DB יכולה לקחת
  // כמה שניות (נמדד: חוק העונשין ~2.8s) - בלי החיווי הזה זה נראה
  // תקוע, לא רק "איטי".
  const loadingEl = document.getElementById("law-loading");
  loadingEl.hidden = false;
  try {
    currentLawId = lawId;
    edits = {};
    insertions = [];
    insertionClientIds = new Set();
    everEditedFieldKeys = new Set();
    fieldElements = {};
    originalTextById = {};
    originalMarginTitleById = {};

    const law = await (await fetch(`/api/laws/${lawId}`)).json();
    // מזהה הגרסה נשמר לצד הטיוטה - ראו היסטוריית ההצעות למטה.
    currentLawVersionId = law.version_id ?? null;
    currentLawTitle = law.title || currentLawTitle;
    buildOriginalIndex(law.tree);
    loadCitations(lawId);  // לא await: הפיד חיצוני, אסור שיעכב את הצגת החוק

    document.getElementById("law-panels").hidden = false;
    // הפריסה מוצגת כבר מהכניסה ללשונית (ברק, 2026-09-21: "המסך צריך
    // להיראות כאילו כבר נבחר חוק"). כאן רק מסתירים את הודעת הריק.
    const emptyHint = document.getElementById("law-tree-empty");
    if (emptyHint) emptyHint.hidden = true;
    // **אין כאן עוד "נוסח כפי שהופיע בוויקיטקסט ביום X" ואין "מראה
    // מקום: לא ידוע... (בדיקה 2)"** (ברק, 2026-09-21). הראשון הוא
    // פרט פנימי, והשני הודעה למפתח. `as_of` ו-`known_source_ref`
    // ממשיכים לחזור מה-API ולהישמר ב-DB - הם נדרשים לבדיקה היומית,
    // להערות השוליים ולשחזור; רק התצוגה הוסרה.

    const billTitleInput = document.getElementById("bill-title-input");
    if (!billTitleInput.value) billTitleInput.value = "";

    rebuildTree(law.tree);
    await refreshPreview();
  } finally {
    loadingEl.hidden = true;
  }
}

function levelsForNodeType(nodeType) {
  if (nodeType === "definition") {
    // הגדרות הן היררכיה נפרדת מסעיף/סעיף קטן/פסקה, לא חלק מהשרשרת -
    // כרגע נתמכת רק הוספת הגדרה נוספת אחריה (ראו insert_preview.py:
    // סעיף קטן/פסקה *בתוך* הגדרה ספציפית הוא פער ידוע, לא ממומש עדיין,
    // ולכן לא מוצע כאן בכלל - לא רק מוסתר אחרי בדיקה, לא מוצג מלכתחילה).
    return ["definition"];
  }
  let idx = LEVEL_ORDER.indexOf(nodeType);
  if (idx === -1) idx = 2; // סוגים אחרים: מתנהגים כמו פסקה - ברירת מחדל תצוגתית, לא ניחוש משפטי
  const upTo = Math.min(idx + 1, LEVEL_ORDER.length - 1);
  return LEVEL_ORDER.slice(0, upTo + 1);
}

function renderNode(node, depth) {
  const wrapper = document.createElement("div");
  wrapper.className = "node";
  wrapper.dataset.nodeId = node.id;
  wrapper.style.marginInlineStart = `${depth * 14}px`;

  if (node.node_type === "law") {
    const heading = document.createElement("div");
    heading.className = "law-heading";
    heading.textContent = node.full_title || "";
    wrapper.appendChild(heading);
  } else {
    const isInserted = insertionClientIds.has(node.id);
    if (isInserted) wrapper.classList.add("inserted");

    const header = document.createElement("div");
    header.className = "node-header";

    // מספר לפני כותרת שוליים (סדר קריאה נכון מימין לשמאל) - לא ההפך.
    const numberSpan = document.createElement("span");
    numberSpan.className = "node-number";
    numberSpan.textContent = node.number || "";

    /* **תווית של סעיף קטן/פסקה צמודה לטקסט שלה, לא בשורה נפרדת
     * מעליו** (ברק, 2026-09-21: "התווית (1), (2) מופיעה בשורה
     * נפרדת מעל הטקסט שלה, במקום צמודה אליו כמו בנוסח החוק").
     *
     * ההבחנה: בסעיף, המספר וכותרת השוליים הם כותרת בפני עצמה -
     * כך זה גם בספר החוקים. אבל "(א)" או "(1)" הם פתיח של השורה
     * עצמה, ולכן הם נכנסים לשורת הגוף ולא לכותרת. */
    const inlineLabel = node.node_type !== "section" && Boolean(node.number);
    if (inlineLabel) numberSpan.classList.add("node-number-inline");
    else header.appendChild(numberSpan);

    /* סעיף שאי אפשר לערוך - חייב להיראות אחרת (ברק, 2026-09-18).
     * עד כאן הוא נראה תקין ופשוט לא הגיב: הכישלון השקט הגרוע ביותר
     * בממשק. הסיבה היא סעיף בלי מספר, ש-find_sections לא מוצאת
     * ו-amend() לא רואה - 429 בקורפוס, 111 בפקודת מס הכנסה לבדה. */
    /* חיווי הערת צ״ל - ראו scrivenerNotes למעלה. */
    const notes = scrivenerNotes(node);
    if (notes.length) {
      const noteBadge = document.createElement("span");
      noteBadge.className = "scrivener-note-badge";
      noteBadge.textContent = notes.length > 1 ? `צ״ל ×${notes.length}` : "צ״ל";
      noteBadge.title = "הערת נוסח בגוף החוק (\"צריך להיות\"):\n" +
        notes.join("\n") +
        "\n\nההערה היא חלק מהנוסח המוצג ואינה תיקון שבוצע.";
      header.appendChild(noteBadge);
    }

    // **לכל סיבת-חסימה ההסבר שלה.** עד 23.9.2026 ההסבר היה תמיד
    // "אין מספר במקור" - גם על סעיף שנחסם מסיבה אחרת לגמרי, כלומר
    // המשתמש קיבל הסבר שגוי בביטחון מלא.
    const notEditable =
      (node.node_type === "section" || node.node_type === "raw_block") &&
      node.editable === false;
    if (notEditable) {
      wrapper.classList.add("not-editable");
      const badge = document.createElement("span");
      badge.className = "not-editable-badge";
      if (node.deferred_note) {
        // **ההוראה הזו בתוקף** - רק תחולתה מתחילה במועד הנקוב.
        // לכן התווית היא מועד התחולה, ולעולם לא "לא בתוקף".
        badge.textContent = node.deferred_note;
        badge.title = `ההוראה הזו נחקקה והיא בתוקף; תחולתה — ${node.deferred_note}. ` +
          "הנוסח שבתוקף עכשיו מוצג לצידה וניתן לעריכה. תיקון בהצעת " +
          "חוק נכתב על גבי הנוסח שבתוקף עכשיו, ולכן ההוראה הזו מוצגת " +
          "לקריאה בלבד.";
      } else if (node.ambiguous_number) {
        badge.textContent = "מספר כפול";
        badge.title = `בחוק הזה יש יותר מסעיף אחד שמספרו ${node.number}. ` +
          `הוראת תיקון נוסחה "בסעיף ${node.number} לחוק העיקרי", ` +
          "והיא הייתה מפנה לשניהם — ולכן אי אפשר לנסח אותה. זו עובדה " +
          "על נוסח החוק במקור (לרוב נוסח עתידי, הוראת שעה או טעות " +
          "מספור), לא תקלה. הנוסח מוצג לקריאה בלבד.";
      } else if (node.node_type === "raw_block") {
        badge.textContent = "טבלה גולמית";
        badge.title = "הבלוק הזה נשמר כפי שהוא מהמקור (טבלה או מילון " +
          "מונחים) ואין תקדים לניסוח הוראת תיקון עליו. מוצג לקריאה בלבד.";
      } else {
        badge.textContent = "לא ניתן לעריכה";
        badge.title = "לסעיף הזה אין מספר במקור, ולכן המערכת אינה יכולה " +
          "לנסח עליו הוראת תיקון. הנוסח מוצג לקריאה בלבד.";
      }
      header.appendChild(badge);
    }

    if (node.node_type === "section" && !notEditable) {
      const titleSpan = document.createElement("span");
      titleSpan.className = "node-margin-title";
      titleSpan.contentEditable = "true";
      titleSpan.dataset.nodeId = node.id;
      titleSpan.dataset.field = "margin_title";
      titleSpan.textContent = node.margin_title || "";
      titleSpan.dataset.plainValue = node.margin_title || "";
      titleSpan.addEventListener("focus", onFieldFocus);
      titleSpan.addEventListener("input", onFieldInput);
      titleSpan.addEventListener("blur", onFieldBlur);
      header.appendChild(titleSpan);
      fieldElements[`${node.id}:margin_title`] = titleSpan;
    } else if (node.margin_title) {
      const titleSpan = document.createElement("span");
      titleSpan.className = "node-margin-title readonly";
      titleSpan.textContent = node.margin_title;
      header.appendChild(titleSpan);
    }

    if (isInserted) {
      const removeBtn = document.createElement("button");
      removeBtn.className = "subtle remove-insertion-btn";
      removeBtn.textContent = "✕ הסר הוספה";
      removeBtn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        insertions = insertions.filter((i) => i.clientId !== node.id);
        insertionClientIds.delete(node.id);
        await refreshPreview();
      });
      header.appendChild(removeBtn);
    }

    // כותרת נפרדת רק כשיש בה משהו - אחרת נשארת שורה ריקה מעל הטקסט.
    if (header.childElementCount > 0) wrapper.appendChild(header);

    const bodyRow = document.createElement("div");
    bodyRow.className = "node-body-row";
    if (inlineLabel) bodyRow.appendChild(numberSpan);

    if (node.text) {
      const textEl = document.createElement("div");
      textEl.className = "node-text";
      textEl.contentEditable = "true";
      textEl.dataset.nodeId = node.id;
      textEl.dataset.field = "text";
      textEl.textContent = node.text;
      textEl.dataset.plainValue = node.text;
      textEl.addEventListener("focus", onFieldFocus);
      textEl.addEventListener("input", onFieldInput);
      textEl.addEventListener("blur", onFieldBlur);
      bodyRow.appendChild(textEl);
      fieldElements[`${node.id}:text`] = textEl;
    } else {
      const spacer = document.createElement("div");
      spacer.className = "node-text-empty";
      bodyRow.appendChild(spacer);
    }

    // כפתור "+" בסוף שורת הטקסט של הצומת עצמו (לא ליד הכותרת) - ראו
    // משוב המשתמש: המקום להוסיף סעיף/סעיף קטן חדש הוא איפה שנגמר
    // התוכן של הצומת הנוכחי, בכל היררכיה.
    if (
      node.node_type === "section" || node.node_type === "subsection" ||
      node.node_type === "paragraph" || node.node_type === "definition"
    ) {
      const addBtn = document.createElement("button");
      addBtn.className = "node-add-btn subtle";
      addBtn.textContent = "+";
      addBtn.title = "הוספת סעיף, סעיף קטן או פסקה מתחת לכאן";
      addBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        toggleInsertMenu(node, wrapper);
      });
      bodyRow.appendChild(addBtn);

      // ח4: פח ליד הפלוס - מוחק את היחידה שהוא עומד עליה (סעיף, סעיף
      // קטן, פסקה, הגדרה). **אותו מסלול כמו מחיקה ידנית של כל הטקסט**:
      // השדות של היחידה ושל כל צאצאיה מתרוקנים ונרשמים כעריכות, והשרת
      // מתרגם ל"סעיף 5 – בטל" / "סעיף קטן (ב) – בטל" / "פסקה (1) – תימחק"
      // (apply_changes._apply_section_repeals / _apply_unit_removals).
      if (node.status !== "repealed" && hasDeletableText(node)) {
        const delBtn = document.createElement("button");
        delBtn.className = "node-del-btn subtle";
        delBtn.type = "button";
        delBtn.innerHTML = TRASH_ICON;
        delBtn.title = `מחיקת ה${UNIT_NAME[node.node_type] || "יחידה"}`;
        delBtn.setAttribute("aria-label", delBtn.title);
        delBtn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          deleteUnit(node);
        });
        bodyRow.appendChild(delBtn);
      }
    }

    wrapper.appendChild(bodyRow);

    const insertHost = document.createElement("div");
    insertHost.className = "insert-host";
    wrapper.appendChild(insertHost);
  }

  for (const child of node.children) {
    wrapper.appendChild(renderNode(child, depth + 1));
  }
  return wrapper;
}

function rebuildTree(tree) {
  // ח2 (25.9.2026): **תפריט הוספה פתוח שורד את הבנייה מחדש.** עד כאן
  // תשובת רענון שחזרה כשהתפריט פתוח (עריכה ואז "+" מיד - באתר החי
  // התשובה לוקחת שניות) מחקה אותו עם כל מה שהוקלד בו, והמשתמש לחץ
  // "הוסף" על כלום. אחרי רענון הדף אין עדכון בדרך - ולכן "זה עבד".
  // מזיזים את אותו אלמנט (עם המטפלים והטקסט שלו) לעוגן בעץ החדש.
  const treeContainer = document.getElementById("law-tree");
  const openMenu = treeContainer.querySelector(".insert-menu");
  const anchorId = openMenu ? openMenu.closest(".node")?.dataset.nodeId : null;
  const focused = openMenu && openMenu.contains(document.activeElement) ? document.activeElement : null;
  const caret = focused && "selectionStart" in focused
    ? [focused.selectionStart, focused.selectionEnd] : null;

  fieldElements = {};
  treeContainer.innerHTML = "";
  treeContainer.appendChild(renderNode(tree, 0));

  if (openMenu && anchorId) {
    const host = findNodeWrapperById(anchorId)?.querySelector(":scope > .insert-host");
    if (host) {
      host.appendChild(openMenu);
      if (focused) {
        focused.focus();
        if (caret) focused.setSelectionRange(caret[0], caret[1]);
      }
    }
  }
}

function onFieldFocus(ev) {
  const el = ev.target;
  // מסירים דקורציה (del/ins) רק אם היא בפועל קיימת (יש אלמנטי ילד) -
  // el.textContent = ... מחליף את צומת הטקסט הפנימי גם כשהתוכן זהה
  // בייטים, מה שהורס את מיקום הסמן שהקליק כבר קבע (הבאג המקורי: כל
  // פוקוס, כולל קליק רגיל בלי דקורציה בכלל, איפס את הסמן להתחלה).
  // בלי דקורציה - לא נוגעים ב-DOM בכלל, נותנים לדפדפן למקם את הסמן
  // איפה שהמשתמש לחץ.
  if (el.childElementCount > 0) {
    el.textContent = el.dataset.plainValue ?? "";
  }
  el.classList.remove("edit-unsupported");
}

/* רושם את מצב השדה ב-edits/insertions. מופרד מ-onFieldBlur כדי
 * שגם הקלדה חיה תוכל לקרוא לו, לא רק יציאה מהשדה. */
const TRASH_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16"/>' +
  '<path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/><path d="M10 11v6M14 11v6"/></svg>';
const UNIT_NAME = { section: "סעיף", subsection: "סעיף הקטן", paragraph: "פסקה", definition: "הגדרה" };

function hasDeletableText(node) {
  if ((node.text || "").trim()) return true;
  return (node.children || []).some(hasDeletableText);
}

// ח4: מרוקן את כל שדות הטקסט של היחידה ושל צאצאיה, ורושם אותם כעריכות.
function deleteUnit(node) {
  const walk = (n) => {
    const el = fieldElements[`${n.id}:text`];
    if (el) { el.textContent = ""; recordField(el); }
    (n.children || []).forEach(walk);
  };
  walk(node);
  setPreviewPending(true);
  refreshPreview();
}

function recordField(el) {
  const nodeId = el.dataset.nodeId;
  const field = el.dataset.field;
  const currentText = el.textContent;

  // צומת שהוא עצמו הוספה ממתינה: אין "מקור" להשוות אליו - עריכת
  // התוכן החדש מעדכנת ישירות את ההוספה הממתינה, לא נכנסת למנגנון
  // ה-diff מול טקסט קיים.
  const ins = insertions.find((i) => i.clientId === nodeId);
  if (ins) {
    if (field === "margin_title") ins.margin_title = currentText;
    else ins.text = currentText;
    return;
  }

  const key = `${nodeId}:${field}`;
  const original = field === "margin_title" ? originalMarginTitleById[nodeId] : originalTextById[nodeId];
  if (currentText === original) {
    delete edits[key];
  } else {
    edits[key] = { node_id: nodeId, field, text: currentText };
    everEditedFieldKeys.add(key);
  }
}

/* **הצעת החוק מתעדכנת תוך כדי הקלדה** (ברק, 2026-09-21: "ערכתי שני
 * סעיפים ובמשך דקות ארוכות לא הופיע כלום").
 *
 * עד כאן refreshPreview() רצה אך ורק ב-blur. מי שהקליד והסתכל על צד
 * ההצעה בלי ללחוץ מחוץ לשדה לא ראה דבר - לנצח. שוחזר בפרודקשן: 15
 * שניות הקלדה, אפס בקשות, והצד עדיין "אין עדיין שינויים".
 *
 * **למה זה בטוח:** refreshPreview כבר מדלגת על rebuildTree ועל
 * applyDecoration כשהפוקוס בתוך שדה ניתן-לעריכה (המנגנון נבנה בדיוק
 * מפני שרינדור-מחדש מוחק את התו שהמשתמש הרגע הקליד), ומעדכנת רק את
 * צד ההצעה. כלומר הסמן אינו זז.
 *
 * ההשהיה קיימת כדי לא לשלוח בקשה לכל תו. renderGeneration כבר מבטל
 * תשובות שהוקדמו על ידי בקשה מאוחרת יותר. */
const LIVE_PREVIEW_DELAY_MS = 600;
let livePreviewTimer = null;

function setPreviewPending(on) {
  // חיווי קטן בראש צד ההצעה. בלעדיו יש כשתי שניות (השהיה + הבקשה)
  // שבהן המשתמש מקליד ולא קורה כלום על המסך - וזו בדיוק התחושה
  // שדווחה כ"תקוע".
  const el = document.getElementById("preview-pending");
  if (el) el.hidden = !on;
  const box = document.getElementById("docx-approx");
  if (box) box.classList.toggle("is-pending", !!on);
}

function onFieldInput(ev) {
  recordField(ev.target);
  setPreviewPending(true);
  clearTimeout(livePreviewTimer);
  livePreviewTimer = setTimeout(() => { refreshPreview(); }, LIVE_PREVIEW_DELAY_MS);
}

async function onFieldBlur(ev) {
  // יציאה מהשדה מרעננת מיד - אין טעם להמתין להשהיה שכבר לא רלוונטית.
  clearTimeout(livePreviewTimer);
  recordField(ev.target);
  await refreshPreview();
}

function applyDecoration(key, status) {
  const el = fieldElements[key];
  if (!el) return;
  const [nodeId, field] = key.split(":");
  const original = field === "margin_title" ? originalMarginTitleById[nodeId] : originalTextById[nodeId];
  if (!(key in edits)) {
    el.textContent = original;
    el.dataset.plainValue = original;
    el.classList.remove("edit-unsupported");
    el.removeAttribute("title");
    return;
  }
  const editedText = edits[key].text;
  if (!status || !status.ok) {
    el.textContent = editedText;
    el.dataset.plainValue = editedText;
    el.classList.add("edit-unsupported");
    el.title = (status && status.reason) || "לא ניתן לבטא את השינוי הזה כהוראת תיקון";
    return;
  }
  el.classList.remove("edit-unsupported");
  el.removeAttribute("title");
  el.dataset.plainValue = editedText;
  if (status.old_phrase) {
    const idx = original.indexOf(status.old_phrase);
    const before = original.slice(0, idx);
    const after = original.slice(idx + status.old_phrase.length);
    el.innerHTML =
      escapeHtml(before) +
      "<del>" + escapeHtml(status.old_phrase) + "</del>" +
      "<ins>" + escapeHtml(status.new_phrase) + "</ins>" +
      escapeHtml(after);
  } else if (status.anchor_substring) {
    const cut = original.indexOf(status.anchor_substring) + status.anchor_substring.length;
    const before = original.slice(0, cut);
    const after = original.slice(cut);
    el.innerHTML = escapeHtml(before) + "<ins>" + escapeHtml(status.inserted_text) + "</ins>" + escapeHtml(after);
  }
}

function findNodeWrapperById(nodeId) {
  for (const wrapper of document.querySelectorAll("#law-tree .node")) {
    if (wrapper.dataset.nodeId === nodeId) return wrapper;
  }
  return null;
}

function renderInsertionErrors(errors) {
  document.querySelectorAll(".insertion-error-card").forEach((c) => c.remove());
  for (const err of errors) {
    const anchorWrapper = findNodeWrapperById(err.anchor_node_id);
    const host = anchorWrapper ? anchorWrapper.querySelector(":scope > .insert-host") : null;
    if (!host) continue;
    const card = document.createElement("div");
    card.className = "insertion-error-card";
    card.textContent = `הוספת ${LEVEL_LABELS[err.kind] || err.kind} נכשלה: ${err.reason}`;
    const removeBtn = document.createElement("button");
    removeBtn.className = "subtle";
    removeBtn.textContent = "הסר";
    removeBtn.addEventListener("click", async () => {
      insertions = insertions.filter((i) => i.clientId !== err.client_id);
      insertionClientIds.delete(err.client_id);
      card.remove();
      await refreshPreview();
    });
    card.appendChild(removeBtn);
    host.appendChild(card);
  }
}

// ח3 (25.9.2026): **"מעדכן..." שנתקע לנצח הוא כשל בפני עצמו.** עד כאן
// refreshPreview לא טיפלה בשום שגיאה: 500 מהשרת, 504 של Vercel (דף
// HTML, לא JSON), ניתוק רשת - כל אחד מהם זרק לפני setPreviewPending
// (false), והחיווי נשאר על המסך בלי הודעה. שוחזר בשלושת המצבים
// (tests/browser/test_preview_failure.py). עכשיו: תקרת זמן, בדיקת
// הסטטוס, והודעה גלויה שאומרת מה קרה ומה לעשות.
const RENDER_TIMEOUT_MS = 45000;

function setPreviewError(message) {
  const el = document.getElementById("preview-error");
  if (!el) return;
  el.textContent = message || "";
  el.hidden = !message;
}

async function fetchRender(req) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), RENDER_TIMEOUT_MS);
  try {
    const resp = await fetch(`/api/laws/${currentLawId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: ctrl.signal,
    });
    let data = null;
    try { data = await resp.json(); } catch { data = null; }
    if (!resp.ok || !data || !data.tree) {
      // הודעת השרת מוצגת רק כשהיא שלנו - בעברית (HTTPException).
      // "Internal Server Error" או דף שגיאה של Vercel אינם הודעה למשתמש.
      const detail = data && typeof data.detail === "string" ? data.detail : "";
      const hebrew = /[\u0590-\u05FF]/.test(detail);
      throw new Error(hebrew ? detail : "השרת לא הצליח לעדכן את הצעת החוק.");
    }
    return data;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("העדכון לקח יותר מדי זמן.");
    if (e instanceof TypeError) throw new Error("החיבור לשרת נקטע.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function refreshPreview() {
  if (!currentLawId) return;
  const myGeneration = ++renderGeneration;
  const req = { edits: editsPayload(), insertions: insertionsPayload(), bill: billMeta() };
  let data;
  try {
    data = await fetchRender(req);
  } catch (e) {
    if (myGeneration !== renderGeneration) return;  // בקשה חדשה כבר בדרך
    setPreviewPending(false);
    setPreviewError(`${e.message} העריכות שלך נשמרו - נסו לערוך שוב או לרענן את הדף.`);
    return;
  }
  // תשובה ישנה שנחסמה על ידי בקשה מאוחרת יותר (למשל: המשתמש כבר
  // המשיך לערוך ושלח בקשה נוספת לפני שזו חזרה) - לא נוגעים ב-DOM.
  if (myGeneration !== renderGeneration) return;
  setPreviewError("");

  // בונים מחדש את כל עץ העריכה רק אם המשתמש לא ממש עכשיו בתוך שדה
  // ניתן-לעריכה - אחרת רינדור-מחדש היה מוחק את התו שהוא הרגע הקליד
  // (מרוץ בין תשובת render איטית לבין פוקוס חדש שכבר הוזז).
  const activeIsField = document.activeElement && document.activeElement.isContentEditable;
  if (!activeIsField) {
    rebuildTree(data.tree);
    const statusByKey = {};
    for (const s of data.edit_statuses) statusByKey[`${s.node_id}:${s.field}`] = s;
    for (const key of everEditedFieldKeys) applyDecoration(key, statusByKey[key]);
  }

  setPreviewPending(false);
  renderInsertionErrors(data.insertion_errors);
  scheduleDraftSave();
  renderDocxApprox(data.lines);
  // ח10: כל כשל בשורה משלו, בגוף ראשון ובמונחים של המשתמש - לא "1 הוספות
  // לא בוצעו (ראו כרטיסי השגיאה בעץ)".
  const failures = failureLines(data);
  document.getElementById("download-hint").innerHTML =
    failures.map((ln) => `<div class="failure-line">${escapeHtml(ln)}</div>`).join("");
  return data;
}

// המספר של הסעיף שהצומת יושב בו (הצומת עצמו, או האב הקרוב שהוא סעיף).
function sectionNumberOf(tree, nodeId) {
  const walk = (node, sec) => {
    const here = node.node_type === "section" ? node.number : sec;
    if (node.id === nodeId) return here;
    for (const c of node.children || []) {
      const found = walk(c, here);
      if (found !== undefined) return found;
    }
    return undefined;
  };
  return tree ? walk(tree, null) : null;
}

const FAILURE_KIND = {
  subsection: "סעיף קטן", paragraph: "פסקה", subparagraph: "פסקת משנה", definition: "הגדרה",
};

function failureLines(data) {
  const lines = [];
  for (const st of data.edit_statuses || []) {
    if (st.ok) continue;
    const sec = sectionNumberOf(data.tree, st.node_id);
    lines.push(st.field === "margin_title"
      ? `לא הצלחתי לקלוט את התיקון שביקשת בכותרת השוליים${sec ? ` של סעיף ${sec}` : ""}`
      : `לא הצלחתי לקלוט את התיקון שביקשת לעשות${sec ? ` בסעיף ${sec}` : ""}`);
  }
  for (const err of data.insertion_errors || []) {
    const ins = insertions.find((i) => i.clientId === err.client_id) || {};
    const label = ins.label ? ` ${ins.label}` : "";
    const sec = sectionNumberOf(data.tree, err.anchor_node_id);
    if (err.kind === "section") {
      lines.push(label ? `לא הצלחתי לקלוט את הוספת סעיף${label} כפי שביקשת`
        : `לא הצלחתי לקלוט את הוספת הסעיף החדש${sec ? ` אחרי סעיף ${sec}` : ""} כפי שביקשת`);
    } else {
      const kind = FAILURE_KIND[err.kind] || "ההוספה";
      lines.push(`לא הצלחתי לקלוט את הוספת ${kind}${label}${sec ? ` לסעיף ${sec}` : ""} כפי שביקשת`);
    }
  }
  return [...new Set(lines)];
}

function renderDocxApprox(lines) {
  document.getElementById("docx-title-line").textContent = billMeta().title;
  const container = document.getElementById("docx-lines");
  container.innerHTML = "";
  if (!lines.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "אין עדיין שינויים - התחילו לערוך את הנוסח מימין.";
    container.appendChild(empty);
    return;
  }
  for (const line of lines) {
    const row = document.createElement("div");
    row.className = "line-row";
    if (line.side_heading) {
      const h = document.createElement("div");
      h.className = "line-side-heading";
      h.textContent = line.side_heading;
      row.appendChild(h);
    }
    const body = document.createElement("div");
    if (line.inner_heading || line.inner_number) {
      body.className = "line-quoted";
      body.textContent = `${line.inner_heading || ""}  ${line.inner_number || ""}  ${line.text}`;
    } else {
      body.className = line.style === "TableBlockOutdent" ? "line-quoted" : "";
      const marker = line.marker ? `${line.marker}  ` : "";
      body.textContent = marker + line.text + (line.text_after || "");
    }
    row.appendChild(body);
    container.appendChild(row);
  }
}

/* ---------- תפריט הוספה ---------- */

function toggleInsertMenu(node, wrapper) {
  const host = wrapper.querySelector(":scope > .insert-host");
  const existing = host.querySelector(".insert-menu");
  if (existing) {
    existing.remove();
    return;
  }
  const template = document.getElementById("insert-menu-template");
  const menu = template.content.firstElementChild.cloneNode(true);
  menu.hidden = false;
  host.appendChild(menu);

  const levelsContainer = menu.querySelector(".insert-menu-levels");
  const levels = levelsForNodeType(node.node_type);
  insertPreviewSeq += 1;

  for (const level of levels) {
    const btn = document.createElement("button");
    btn.className = "subtle insert-level-btn";
    btn.textContent = `הוסף ${LEVEL_LABELS[level]} (בודק...)`;
    btn.disabled = true;
    levelsContainer.appendChild(btn);

    fetchInsertPreview(node.id, level).then((preview) => {
      if (!menu.isConnected) return; // התפריט נסגר בינתיים - לא נוגעים בו
      if (preview.supported) {
        btn.textContent = `הוסף ${LEVEL_LABELS[level]} (יהיה ${preview.label})`;
        btn.disabled = false;
        btn.addEventListener("click", () => showInsertForm(menu, node, level, preview.label));
      } else {
        btn.textContent = `הוסף ${LEVEL_LABELS[level]} - לא נתמך`;
        btn.title = preview.reason || "";
      }
    });
  }
}

async function fetchInsertPreview(anchorNodeId, level) {
  const req = {
    edits: editsPayload(), insertions: insertionsPayload(),
    anchor_node_id: anchorNodeId, level,
  };
  const resp = await fetch(`/api/laws/${currentLawId}/insert-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return resp.json();
}

function showInsertForm(menu, node, level, label) {
  const form = menu.querySelector(".insert-menu-form");
  form.hidden = false;
  const titleField = menu.querySelector(".insert-margin-title-field");
  titleField.hidden = level !== "section";
  const titleInput = menu.querySelector(".insert-margin-title-input");
  const textInput = menu.querySelector(".insert-text-input");
  textInput.value = "";
  titleInput.value = "";

  const submitBtn = menu.querySelector(".insert-submit-btn");
  const formError = menu.querySelector(".insert-form-error");
  const showFormError = (msg, field) => {
    // ח2: עד כאן שדה חובה ריק רק העביר פוקוס, בלי שום הודעה - הלחיצה
    // על "הוסף" נראתה כאילו לא קרה כלום.
    formError.textContent = msg;
    formError.hidden = false;
    field.focus();
  };
  formError.hidden = true;
  submitBtn.onclick = async () => {
    if (level === "section" && !titleInput.value.trim()) {
      showFormError("נא למלא כותרת שוליים לסעיף החדש.", titleInput);
      return;
    }
    if (!textInput.value.trim()) {
      showFormError("נא למלא את תוכן ההוספה.", textInput);
      return;
    }
    const clientId = `ins-${++insertionCounter}`;
    insertions.push({
      clientId,
      kind: level,
      anchor_node_id: node.id,
      text: textInput.value,
      margin_title: level === "section" ? titleInput.value : undefined,
      label,
    });
    insertionClientIds.add(clientId);
    menu.remove();
    await refreshPreview();
  };
  menu.querySelector(".insert-cancel-btn").onclick = () => menu.remove();
}

document.getElementById("download-btn").addEventListener("click", async () => {
  if (!currentLawId) return;
  const req = { edits: editsPayload(), insertions: insertionsPayload(), bill: billMeta() };
  const resp = await fetch(`/api/laws/${currentLawId}/docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!resp.ok) {
    document.getElementById("download-hint").textContent = "שגיאה בהפקת docx";
    return;
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${currentLawId}-הצעת-חוק.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

document.getElementById("bill-title-input").addEventListener("blur", refreshPreview);

/* ===================================================================
 * היסטוריית הצעות (ברק, 2026-09-21, משימה 11)
 *
 * **למה בדפדפן ולא בדאטהבייס:** אין עדיין הרשמה. טבלה משותפת
 * בלי מזהה משתמש הייתה מערבבת בין אנשים. כשההרשמה תגיע, המבנה
 * כאן (draft_id, law_id, version_id, edits, insertions) עובר
 * לטבלה כמו שהוא.
 *
 * **מה שחייב להישמר עם הטיוטה: על איזו גרסת חוק היא נבנתה.**
 * הריצה היומית (tools/check_for_update.py) טוענת חוקים מחדש
 * אוטומטית, וגם תיקון פרסור מחליף גרסה. `version_id` הוא
 * law_versions.id ומשתנה בשני המקרים - כלומר בדיוק כשהטקסט
 * שמתחת לטיוטה זז. כשפותחים טיוטה והמזהה שונה, המשתמש מקבל
 * אזהרה.
 *
 * **אין דריסה של העריכות.** העריכות נטענות כפי שהן גם כשהחוק
 * התעדכן. עריכה שהעוגן שלה נעלם מהנוסח החדש מדווחת בנפרד -
 * השרת מחזיר edit_statuses, ואנחנו סופרים כמה לא התקבלו.
 *
 * **הגנת הטיוטות של הריצה היומית לא רואה את אלה** - היא מחפשת
 * טבלת drafts בדאטהבייס, וטיוטה בדפדפן אינה שם. זה מתועד
 * ב-open-gaps ונפתר עם המעבר ל-DB.
 * =================================================================== */

let draftsUnreadable = false;   // ראו readDrafts
const DRAFTS_KEY = "legislator.drafts.v1";
const DRAFTS_LIMIT = 40;
let currentDraftId = null;
let currentLawVersionId = null;
let draftSaveTimer = null;

function readDrafts() {
  // אחסון הדפדפן יכול לזרוק (מצב פרטי, חסימת אתר) או להחזיר זבל.
  // כישלון כאן לא ישבור את המסך - פשוט אין היסטוריה.
  try {
    const raw = localStorage.getItem(DRAFTS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    draftsUnreadable = false;
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // **אחסון פגום אינו "אין הצעות שמורות".** עד לתיקון הזה
    // JSON.parse שנכשל החזיר רשימה ריקה, והמשתמש ראה בדיוק את
    // אותו מסך כמו מי שלא שמר מעולם - בזמן שההצעות שלו קיימות
    // ופשוט לא נקראו.
    draftsUnreadable = true;
    return [];
  }
}

function writeDrafts(list) {
  try {
    localStorage.setItem(DRAFTS_KEY, JSON.stringify(list.slice(0, DRAFTS_LIMIT)));
    return true;
  } catch {
    // **מחזירה false, והקורא חייב לבדוק.** עד לתיקון הזה איש לא
    // בדק, והחיווי "נשמר אוטומטית" הוצג גם כשהכתיבה נכשלה - למשל
    // כשמכסת האחסון מלאה. חיווי שמשקר גרוע מהיעדר חיווי, ובמיוחד
    // זה: הוא נוסף כדי לפתור איבוד עבודה ועלול להסתיר אותו.
    return false;
  }
}

function draftHasContent() {
  return Object.keys(edits).length > 0 || insertions.length > 0;
}

function saveCurrentDraft() {
  // מחזירה האם נשמר בפועל - החיווי לא יכול להסתמך על "נקראה".
  if (!currentLawId || !draftHasContent()) return false;
  if (!currentDraftId) currentDraftId = `d${Date.now()}${Math.random().toString(36).slice(2, 7)}`;
  const list = readDrafts().filter((d) => d.id !== currentDraftId);
  list.unshift({
    id: currentDraftId,
    law_id: currentLawId,
    law_title: currentLawTitle || currentLawId,
    version_id: currentLawVersionId,
    saved_at: new Date().toISOString(),
    title: document.getElementById("bill-title-input").value || "",
    edits: Object.values(edits),
    insertions: insertionsPayload(),
  });
  const stored = writeDrafts(list);
  renderDraftList();
  return stored;
}

function scheduleDraftSave() {
  clearTimeout(draftSaveTimer);
  setSaveStatus("saving");
  draftSaveTimer = setTimeout(() => {
    draftSaveTimer = null;
    // שלושה מצבים, לא שניים: נשמר / לא היה מה לשמור / **נכשל**.
    // "שומר…" שנתקע הוא שקר, ו"נשמר" על כתיבה שנכשלה גרוע ממנו.
    setSaveStatus(reportSave(saveCurrentDraft()));
  }, 900);
}

/** שומרת **מיד** אם יש שמירה ממתינה.
 *
 *  **זו אבדן-העבודה שברק דיווח עליו (22.9):** השמירה האוטומטית
 *  הייתה בהשהיה של 900ms, ומעבר לחוק אחר מאפס את `edits` לפני
 *  שהטיימר נורה. כשהוא כן נורה, `draftHasContent()` כבר החזיר
 *  false - ולא נשמר דבר, בלי שום סימן. כל מעבר חייב להקדים
 *  flush, ולא רק לבטל את הטיימר. */
function flushDraftSave() {
  if (!draftSaveTimer) return;
  clearTimeout(draftSaveTimer);
  draftSaveTimer = null;
  setSaveStatus(reportSave(saveCurrentDraft()));
}

/** ממירה את תוצאת השמירה למצב חיווי. `false` פירושו **כישלון
 *  כתיבה**, ולא "לא היה מה לשמור" - את זה `saveCurrentDraft`
 *  מבדילה בעצמה לפני שהיא מנסה לכתוב. */
function reportSave(result) {
  if (result === true) return "saved";
  return draftHasContent() && currentLawId ? "failed" : "";
}

/** חיווי השמירה. **בלעדיו המשתמש לא יכול לדעת שנשמר** - וזו
 *  הייתה התלונה: "לא ברור מתי הצעה נשמרת". */
function setSaveStatus(state) {
  const el = document.getElementById("draft-save-status");
  if (!el) return;
  if (state === "saving") {
    if (!currentLawId || !draftHasContent()) { el.textContent = ""; return; }
    el.textContent = "שומר…";
    el.className = "draft-save-status is-saving";
    return;
  }
  if (state === "saved" && currentDraftId) {
    el.textContent = "נשמר אוטומטית";
    el.className = "draft-save-status is-saved";
    el.title = "";
    return;
  }
  if (state === "failed") {
    // לא "לא נשמר" בשקט - הודעה מפורשת, כי זו בדיוק העבודה
    // שהמשתמש עלול לאבד.
    el.textContent = "⚠ השמירה נכשלה - העבודה אינה שמורה";
    el.className = "draft-save-status is-failed";
    el.title = "האחסון המקומי של הדפדפן מלא או חסום. ייצא את ההצעה ל-Word כדי לא לאבד אותה.";
    return;
  }
  el.textContent = "";
  el.className = "draft-save-status";
}

function deleteDraft(id) {
  writeDrafts(readDrafts().filter((d) => d.id !== id));
  if (currentDraftId === id) currentDraftId = null;
  renderDraftList();
}

function draftSummary(d) {
  const n = (d.edits || []).length + (d.insertions || []).length;
  return `${n} ${n === 1 ? "שינוי" : "שינויים"}`;
}

function renderDraftList() {
  const box = document.getElementById("drafts-list");
  if (!box) return;
  if (draftsUnreadable) {
    box.innerHTML = `<div class="msg err">לא הצלחתי לקרוא את ההצעות השמורות —
      האחסון המקומי של הדפדפן פגום או חסום. <b>ההצעות לא נמחקו</b>,
      אבל אי אפשר להציג אותן כאן.</div>`;
    return;
  }
  const list = readDrafts();
  document.getElementById("drafts-count").textContent = list.length ? `(${list.length})` : "";
  if (!list.length) {
    box.innerHTML = '<div class="hint">עוד לא שמרתם הצעות. כל עריכה נשמרת כאן אוטומטית.</div>';
    return;
  }
  box.innerHTML = list
    .map((d) => `<div class="draft-row${d.id === currentDraftId ? " current" : ""}">
        <button class="draft-open" data-draft="${escapeHtml(d.id)}">
          <span class="draft-title">${escapeHtml(d.title || d.law_title)}</span>
          <span class="draft-meta">${escapeHtml(d.law_title)} · ${draftSummary(d)} ·
            ${escapeHtml(formatHebrewDate(d.saved_at))}</span>
        </button>
        <button class="subtle draft-delete" data-draft="${escapeHtml(d.id)}"
                title="מחיקת ההצעה מההיסטוריה">✕</button>
      </div>`)
    .join("");
  for (const b of box.querySelectorAll(".draft-open")) {
    b.addEventListener("click", () => openDraft(b.dataset.draft));
  }
  for (const b of box.querySelectorAll(".draft-delete")) {
    b.addEventListener("click", (ev) => { ev.stopPropagation(); deleteDraft(b.dataset.draft); });
  }
}

function showDraftNotice(html, kind) {
  const el = document.getElementById("draft-notice");
  if (!el) return;
  el.className = `draft-notice ${kind}`;
  el.innerHTML = html;
  el.hidden = !html;
}

async function openDraft(draftId) {
  const draft = readDrafts().find((d) => d.id === draftId);
  if (!draft) return;
  clearSimilarBills();   // ההצעות הדומות שייכות להצעה הקודמת
  flushDraftSave();      // לשמור לפני שהמצב מתאפס
  showDraftNotice("", "");

  // טוענים את החוק מחדש - תמיד את הנוסח **הנוכחי**, לא נוסח שמור.
  // טיוטה אינה מקפיאה חוק; היא מחזיקה את העריכות ואת המזהה שעליו
  // הן נעשו.
  await selectLaw({ id: draft.law_id, title: draft.law_title });

  currentDraftId = draft.id;
  document.getElementById("bill-title-input").value = draft.title || "";

  edits = {};
  for (const e of draft.edits || []) {
    const key = `${e.node_id}:${e.field}`;
    edits[key] = e;
    everEditedFieldKeys.add(key);
  }
  insertions = (draft.insertions || []).map((i) => ({ ...i }));
  insertionClientIds = new Set(insertions.map((i) => i.clientId));

  const data = await refreshPreview();
  const failed = (data && data.edit_statuses || []).filter((s) => !s.ok).length;

  if (draft.version_id && currentLawVersionId && draft.version_id !== currentLawVersionId) {
    showDraftNotice(
      "<b>נוסח החוק התעדכן מאז ששמרתם את ההצעה.</b> העריכות שלכם נטענו " +
      "כפי שהן ולא נדרסו — אבל הן מנוסחות מול הנוסח הקודם. כדאי לעבור " +
      "עליהן מול הנוסח שמוצג עכשיו." +
      (failed ? ` <b>${failed} מהעריכות לא ניתנות ליישום על הנוסח הנוכחי</b> ` +
                "(הטקסט שעליו הן נשענו השתנה); הן מסומנות בעץ." : ""),
      "warn");
  } else if (failed) {
    showDraftNotice(
      `<b>${failed} מהעריכות לא ניתנות ליישום</b> — הן מסומנות בעץ.`, "warn");
  }
  renderDraftList();
}

function newDraft() {
  clearSimilarBills();   // ההצעות הדומות שייכות להצעה הקודמת
  flushDraftSave();      // לשמור לפני שהמצב מתאפס
  currentDraftId = null;
  edits = {};
  insertions = [];
  insertionClientIds = new Set();
  everEditedFieldKeys = new Set();
  document.getElementById("bill-title-input").value = "";
  showDraftNotice("", "");
  if (currentLawId) refreshPreview();
  renderDraftList();
}

initLawSearch();
renderDraftList();
document.getElementById("drafts-toggle").addEventListener("click", () => {
  const panel = document.getElementById("drafts-panel");
  panel.hidden = !panel.hidden;
  if (!panel.hidden) renderDraftList();
});
document.getElementById("draft-new-btn").addEventListener("click", newDraft);
// גם יציאה מהדף היא "מעבר" - שמירה ממתינה חייבת להיסגר לפניה.
window.addEventListener("beforeunload", flushDraftSave);

/* ═══ ניווט לשוניות (משימה ח, 2026-09-16) - בלי state בשרת, כל
 * לשונית מסתירה/מציגה DOM בלבד. bills נשארת ברירת המחדל. ═══ */
function switchTab(tabName) {
  for (const btn of document.querySelectorAll(".nav button[data-t]")) {
    btn.classList.toggle("on", btn.dataset.t === tabName);
  }
  for (const bar of document.querySelectorAll(".topbar[data-bar]")) {
    bar.hidden = bar.dataset.bar !== tabName;
  }
  for (const tab of document.querySelectorAll(".tab[id]")) {
    tab.classList.toggle("on", tab.id === tabName);
  }
}

for (const btn of document.querySelectorAll(".nav button[data-t]")) {
  btn.addEventListener("click", () => switchTab(btn.dataset.t));
}

/* ═══ כלי שאילתא/הצעה לסדר - קומפוננטת צ'אט אחת ═══ (משימה ח)
 * כל הודעת משתמש נוספת ל-topicHistory ונשלחת מחדש כמכלול (השרת אינו
 * שומר state, ראו 10ב) - כך ש"קצר את זה"/"שנה ניסוח" עובדים כהמשך
 * שיחה טבעי, לא רק כפנייה ראשונה. */

/* **אנימציית המתנה בכלי הצ'אט** (ברק, 2026-09-21: "כרגע זה מרגיש
 * תקוע... משהו שקשור לנושא של המערכת").
 *
 * שלוש אפשרויות נשקלו:
 *   א. פטיש יושב-ראש שמקיש - מזוהה, אבל שייך לבית משפט יותר
 *      מאשר לכנסת, ומרמז על הכרעה שלא התקבלה.
 *   ב. ארבע הקריאות (טרומית → ראשונה → שנייה → שלישית) נדלקות
 *      בזו אחר זו - הכי "כנסת" שיש, אבל **מטעה**: זה נראה כמו
 *      מעקב אחרי שלב אמיתי בהליך, והבוט אינו נמצא בשום שלב כזה.
 *   ג. **סעיף חוק שנכתב** - סימן § שפועם, ושלוש שורות נוסח
 *      שמתמלאות אחת אחרי השנייה. מה שהמערכת באמת עושה, בלי
 *      להתחזות למצב שאינו קיים.
 *
 * נבחרה ג'. מכובדת ל-prefers-reduced-motion (ראו style.css). */
function appendThinking(container, label) {
  const div = document.createElement("div");
  div.className = "msg a thinking";
  div.innerHTML =
    '<span class="thinking-mark">§</span>' +
    '<span class="thinking-lines"><i></i><i></i><i></i></span>' +
    `<span class="thinking-label">${escapeHtml(label)}</span>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

/* ═══ שכבה משותפת לכל הצ'אטבוטים (ברק, 25.9.2026) ═══
 * כל חלון צ'אט - תקנון, שאילתות, הצעות לסדר, ומה שיתווסף - עובר דרך
 * appendMsg / followStream / bindComposer. צ'אטבוט חדש מקבל את כל
 * ההתנהגות הזו אוטומטית, בלי להעתיק אותה.
 *
 * צ2 - אייקון העתקה בפינה הימנית העליונה של כל תשובה, sticky: בהודעה
 *      ארוכה שגוללים בה הוא נשאר גלוי. אייקון הוורד (ש3) בפינה השמאלית.
 * צ1 - גלילה: תשובה שארוכה מהחלון נעצרת על **ראש** ההודעה. הקורא לא
 *      קורא בקצב שהמודל כותב. רק אם המשתמש גלל למטה בעצמו - ממשיכים
 *      לעקוב אחרי הסוף.
 * צ3 - Shift+Enter יורד שורה, Enter לבד שולח. */

const COPY_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/>' +
  '<path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>';
const COPIED_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>';

function messageText(bubble) {
  const clone = bubble.cloneNode(true);
  clone.querySelectorAll(".msg-copy, .msg-action").forEach((b) => b.remove());
  return clone.innerText.trim();
}

function addCopyAction(bubble) {
  const btn = document.createElement("button");
  btn.className = "msg-copy";
  btn.type = "button";
  btn.title = "העתקה";
  btn.setAttribute("aria-label", "העתקת ההודעה");
  btn.innerHTML = COPY_ICON;
  btn.addEventListener("click", async () => {
    const text = messageText(bubble);
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // clipboard API חסום (http, הרשאה) - נסיגה ל-execCommand
      const ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); ta.remove();
    }
    btn.innerHTML = COPIED_ICON; btn.title = "הועתק";
    setTimeout(() => { btn.innerHTML = COPY_ICON; btn.title = "העתקה"; }, 1500);
  });
  bubble.prepend(btn);
}

function scrollToBottom(container) {
  container.scrollTop = container.scrollHeight;
  container._lastAutoScroll = container.scrollTop;
}

// מציג הודעה שהגיעה בשלמותה: אם היא נכנסת בחלון - לתחתית; אם היא
// ארוכה ממנו - ראש ההודעה בראש החלון (צ1).
function revealMessage(container, bubble) {
  if (bubble.offsetHeight <= container.clientHeight - 24) {
    scrollToBottom(container);
    return;
  }
  const delta = bubble.getBoundingClientRect().top - container.getBoundingClientRect().top - 12;
  container.scrollTop += delta;
  container._lastAutoScroll = container.scrollTop;
}

// מעקב אחרי הודעה מוזרמת (צ1). update() אחרי כל קטע.
function followStream(container, bubble) {
  let follow = false;           // המשתמש גלל לתחתית בעצמו
  let userMoved = false;        // המשתמש גלל - לא זזים עד שיחזור לתחתית
  const onScroll = () => {
    if (Math.abs(container.scrollTop - (container._lastAutoScroll ?? -1)) <= 2) return; // אנחנו גללנו
    userMoved = true;
    follow = container.scrollHeight - container.scrollTop - container.clientHeight < 40;
  };
  container.addEventListener("scroll", onScroll);
  return {
    update() {
      if (follow) { scrollToBottom(container); return; }
      if (userMoved) return;
      revealMessage(container, bubble);
    },
    stop() { container.removeEventListener("scroll", onScroll); },
  };
}

function appendMsg(container, cls, html) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.innerHTML = html;
  container.appendChild(div);
  if (cls === "a") {
    addCopyAction(div);
    revealMessage(container, div);
  } else {
    scrollToBottom(container);
  }
  return div;
}

// צ3: Enter שולח, Shift+Enter יורד שורה. השדה גדל עם הטקסט עד 6 שורות.
function bindComposer(input, send) {
  const grow = () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  };
  input.addEventListener("input", grow);
  input.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" || ev.shiftKey || ev.isComposing) return;
    ev.preventDefault();
    send();
  });
  // אחרי שליחה הקוד מרוקן את value ומנטרל/מפעיל את השדה - מחזירים גובה
  new MutationObserver(grow).observe(input, { attributes: true, attributeFilter: ["disabled"] });
}

function wordCountHtml(wordCount, wordLimit) {
  if (wordLimit == null) return `<div class="word-count">${wordCount} מילים (בלי הגבלה)</div>`;
  const over = wordCount > wordLimit;
  return `<div class="word-count${over ? " over" : ""}">${wordCount}/${wordLimit} מילים${over ? " - חורג מהמגבלה!" : ""}</div>`;
}

// --- שאילתות ---
// **שיחה אמיתית, לא הדבקה.** עד 2026-09-22 כל הודעות המשתמש
// הודבקו ב-"\n" ונשלחו כתיאור אחד - ולכן סירוב על שאלה אחת נדבק
// לכל הבאות: המודל קיבל גוש שעדיין הכיל את השאלה שנדחתה, וסירב
// שוב בצדק. עכשיו כל הודעה היא תור, כולל תשובות המודל - מה שגם
// מאפשר "תקצר את זה" לעבוד על הטיוטה הקודמת ולא על הנושא מחדש.
let queryTurns = [];
let currentQueryDraft = null;

async function sendQueryMessage() {
  const input = document.getElementById("query-composer-input");
  const text = input.value.trim();
  if (!text) return;
  const minister = document.getElementById("query-minister-input").value.trim();
  const mkName = document.getElementById("query-mk-input").value.trim();
  const kind = document.getElementById("query-kind-input").value;
  const chat = document.getElementById("query-chat");

  if (!minister || !mkName) {
    appendMsg(chat, "err", "יש למלא \"אל השר/ה\" ו\"מאת\" לפני ניסוח השאילתה.");
    return;
  }

  appendMsg(chat, "u", escapeHtml(text));
  queryTurns.push({ role: "user", content: text });
  input.value = "";
  input.disabled = true;

  const thinking = appendThinking(chat, "מנסח את השאילתה…");
  try {
    const resp = await fetch("/api/query/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        turns: queryTurns,
        kind,
        minister,
        mk_name: mkName,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      const detail = err.detail || "שגיאה בניסוח השאילתה.";
      // **הסירוב נכנס להיסטוריה כתור של המודל.** כך הוא נשאר חלק
      // מהשיחה - המודל יודע שכבר סירב - בלי להיות חלק מהשאלה הבאה.
      if (String(detail).startsWith("לא ניתן לנסח שאילתה")) {
        queryTurns.push({ role: "assistant", content: detail });
      } else {
        // תקלת תשתית אינה חלק מהשיחה. משאירים אותה בהיסטוריה
        // היה גורם למודל להתייחס אליה כאילו אמר אותה.
        queryTurns.pop();
      }
      appendMsg(chat, "err", escapeHtml(detail));
      return;
    }
    const data = await resp.json();
    // ת4+ת5: חולין או עלבון - תשובה רגילה, בלי טיוטה ובלי אייקון וורד.
    // היא נכנסת להיסטוריה כתור של המודל, כמו כל תשובה.
    if (data.chat_reply) {
      queryTurns.push({ role: "assistant", content: data.chat_reply });
      appendMsg(chat, "a", escapeHtml(data.chat_reply));
      saveCurrentConv();
      return;
    }
    currentQueryDraft = data;
    // ש3: הטיוטה נשמרת עם התור - כדי ששיחה שנפתחת מחדש תציג אותה
    // בדיוק כמו עכשיו, כולל אייקון הוורד.
    queryTurns.push({
      role: "assistant",
      content: `נושא: ${currentQueryDraft.subject}\nגוף: ${currentQueryDraft.body}`,
      draft: { ...currentQueryDraft },
    });
    renderQueryDraft(chat, currentQueryDraft);
    // ב5 - **החיפוש רץ מעצמו, ואינו מעכב את הניסוח.** הטיוטה כבר
    // על המסך; זה יוצא לדרך אחריה ומופיע כשהוא מוכן.
    autoSearchPastQueries(currentQueryDraft.subject || text);
    saveCurrentConv();
  } finally {
    thinking.remove();
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("query-send-btn").addEventListener("click", sendQueryMessage);
bindComposer(document.getElementById("query-composer-input"), sendQueryMessage);

async function exportQueryDraft(draft, btn) {
  const original = btn ? btn.getAttribute("title") : "";
  try {
    if (btn) { btn.disabled = true; btn.setAttribute("title", "מייצא…"); }
    const resp = await fetch("/api/query/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    // **כשל ייצוא לא נבלע.** לחיצה שלא עושה כלום נראית כמו תקלה
    // בכפתור, והמשתמש לוחץ שוב ושוב.
    if (!resp.ok) throw new Error("export");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "שאילתה.docx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch {
    appendMsg(document.getElementById("query-chat"), "err",
              "הייצוא לוורד נכשל. הטיוטה עצמה נשארה כאן - אפשר להעתיק אותה ידנית.");
  } finally {
    if (btn) { btn.disabled = false; btn.setAttribute("title", original || "ייצוא לוורד"); }
  }
}

// ב3 - אייקון הייצוא יושב **על ההודעה עצמה**, ורק על הודעה שהיא
// שאילתה מנוסחת. הודעת שגיאה, סירוב או הודעה רגילה אינן מקבלות אותו -
// אין מה לייצא מהן. **פונקציה אחת לטיוטה חיה ולטיוטה משיחה שנפתחה
// מחדש** (ש3): עד כאן openConv הציג את התור כטקסט גולמי, בלי אייקון -
// ומכאן "לפעמים האייקון לא מופיע".
// ש6: "נושא", "גוף" ו"רצוני לשאול" בבולד - בצ'אט בלבד. קובץ הוורד נבנה
// מהנתונים (query_doc.py) ולא מה-HTML הזה, ונשאר כמו בדוגמאות.
function queryBodyHtml(body) {
  return String(body || "").split("\n").map((ln) =>
    ln.trim() === "רצוני לשאול:" ? `<b>${escapeHtml(ln)}</b>` : escapeHtml(ln)).join("\n");
}

function renderQueryDraft(chat, draft) {
  const bubble = appendMsg(
    chat,
    "a",
    `ניסחתי טיוטה לפי הפורמט המקובל.` +
      `<div class="draft"><div class="to">שאילתה ${escapeHtml(draft.kind || "")} ${escapeHtml(draft.minister || "")}</div>` +
      `<div class="draft-field"><b>נושא:</b> ${escapeHtml(draft.subject || "")}</div>` +
      `<div class="draft-field"><b>גוף:</b></div>` +
      `${queryBodyHtml(draft.body)}${draft.word_count != null ? wordCountHtml(draft.word_count, draft.word_limit) : ""}${draft.removed_addressee ? `<div class="word-count">הוסרה פנייה לנמען מתחילת הגוף (${escapeHtml(draft.removed_addressee)}) — הנמען נקבע בשדה ומוזרק למסמך</div>` : ""}</div>`
  );
  attachQueryExport(bubble, { ...draft });
  return bubble;
}

// שיחה ששמורה מלפני ש3 - התור של הטיוטה בלי השדה draft. טיוטה, ורק
// טיוטה, נשמרה בצורה "נושא: ...\nגוף: ..." (סירוב וחולין נשמרים כטקסט).
function draftFromTurn(turn, conv) {
  if (turn.draft) return turn.draft;
  const m = /^נושא: ([^\n]*)\nגוף: ([\s\S]*)$/.exec(turn.content || "");
  if (!m) return null;
  return { kind: conv.kind || "רגילה", minister: conv.minister || "", mk_name: conv.mk || "",
           subject: m[1], body: m[2] };
}

function attachQueryExport(bubble, draft) {
  const btn = document.createElement("button");
  btn.className = "msg-action";
  btn.type = "button";
  btn.title = "ייצוא לוורד";
  btn.setAttribute("aria-label", "ייצוא השאילתה לקובץ Word");
  btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' +
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>' +
    '<path d="M14 3v5h5"/><path d="M9 13l1.5 4L12 13l1.5 4L15 13"/></svg>';
  btn.addEventListener("click", () => exportQueryDraft(draft, btn));
  bubble.classList.add("has-action");
  // **בראש הבועה, ליד אייקון ההעתקה** (ש3). float משמאל עובד רק על מה
  // שבא לפני הטקסט: appendChild שם אותו אחרי תיבת הטיוטה - משמאל, אבל
  // 231px מתחת לראש ההודעה (נמדד בדפדפן).
  const copy = bubble.querySelector(":scope > .msg-copy");
  if (copy) copy.after(btn); else bubble.prepend(btn);
}

// --- הצעות לסדר ---
let agendaTopicHistory = [];
let currentAgendaDraft = null;

async function sendAgendaMessage() {
  const input = document.getElementById("agenda-composer-input");
  const text = input.value.trim();
  if (!text) return;
  const mkName = document.getElementById("agenda-mk-input").value.trim();
  const chat = document.getElementById("agenda-chat");

  if (!mkName) {
    appendMsg(chat, "err", "יש למלא \"מאת\" לפני ניסוח ההצעה.");
    return;
  }

  appendMsg(chat, "u", escapeHtml(text));
  agendaTopicHistory.push(text);
  input.value = "";
  input.disabled = true;

  const thinking = appendThinking(chat, "מנסח את ההצעה לסדר…");
  try {
    const resp = await fetch("/api/agenda/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic_description: agendaTopicHistory.join("\n"), mk_name: mkName }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      appendMsg(chat, "err", escapeHtml(err.detail || "שגיאה בניסוח ההצעה."));
      return;
    }
    const data = await resp.json();
    // ת4+ת5: חולין/עלבון אינם נושא להצעה - יוצאים מההיסטוריה שנשלחת
    // בפעם הבאה, אחרת "תודה" הייתה נדבקת לנושא ההצעה הבאה.
    if (data.chat_reply) {
      agendaTopicHistory.pop();
      appendMsg(chat, "a", escapeHtml(data.chat_reply));
      return;
    }
    currentAgendaDraft = data;
    document.getElementById("agenda-copy-btn").disabled = false;
    appendMsg(
      chat,
      "a",
      `הנה נוסח מוצע.` +
        `<div class="draft"><div class="to">הצעה לסדר היום</div>` +
        `<b>הנושא:</b> ${escapeHtml(currentAgendaDraft.subject)}<br><br>` +
        `${escapeHtml(currentAgendaDraft.reasoning)}<br><br>${escapeHtml(currentAgendaDraft.request_text)}</div>`
    );
  } finally {
    thinking.remove();
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("agenda-send-btn").addEventListener("click", sendAgendaMessage);
bindComposer(document.getElementById("agenda-composer-input"), sendAgendaMessage);

document.getElementById("agenda-copy-btn").addEventListener("click", async () => {
  if (!currentAgendaDraft) return;
  const text =
    `הצעה לסדר היום - ${currentAgendaDraft.subject}\n\n` +
    `${currentAgendaDraft.reasoning}\n\n${currentAgendaDraft.request_text}\n\n${currentAgendaDraft.mk_name}`;
  try {
    await navigator.clipboard.writeText(text);
    const btn = document.getElementById("agenda-copy-btn");
    const original = btn.textContent;
    btn.textContent = "הועתק!";
    setTimeout(() => { btn.textContent = original; }, 1500);
  } catch (e) {
    appendMsg(document.getElementById("agenda-chat"), "err", "ההעתקה נכשלה - יש להעתיק ידנית.");
  }
});

/* ═══ ב4 - שיחות שאילתא קודמות ═══
 * אותו דפוס בדיוק כמו "ההצעות שלי" (DRAFTS_KEY): localStorage,
 * מכסה, וכישלון קריאה **שאינו מוצג כ"אין שיחות"** - ראו readDrafts
 * והלקח שנלמד שם. שיחה נשמרת אחרי כל תור, כך שסגירת לשונית
 * באמצע אינה מאבדת אותה. */
const QCONV_KEY = "legislator.queryConversations.v1";
const QCONV_LIMIT = 30;
let currentConvId = null;
let qconvUnreadable = false;

function readConvs() {
  try {
    const raw = localStorage.getItem(QCONV_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    qconvUnreadable = false;
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // **אחסון פגום אינו "אין שיחות".** המשתמש יראה הודעה שאומרת
    // שלא הצלחנו לקרוא, ולא מסך ריק שנראה כמו מי שלא שמר מעולם.
    qconvUnreadable = true;
    return [];
  }
}

function writeConvs(list) {
  try {
    localStorage.setItem(QCONV_KEY, JSON.stringify(list.slice(0, QCONV_LIMIT)));
    return true;
  } catch {
    return false;   // הקורא חייב לבדוק - ראו writeDrafts
  }
}

function saveCurrentConv() {
  if (!queryTurns.length) return;
  const list = readConvs().filter((c) => c.id !== currentConvId);
  currentConvId = currentConvId || `c${Date.now()}`;
  const firstUser = queryTurns.find((t) => t.role === "user");
  list.unshift({
    id: currentConvId,
    title: (currentQueryDraft && currentQueryDraft.subject)
      || (firstUser ? firstUser.content.slice(0, 60) : "שיחה"),
    at: Date.now(),
    turns: queryTurns,
    minister: document.getElementById("query-minister-input").value.trim(),
    mk: document.getElementById("query-mk-input").value.trim(),
    kind: document.getElementById("query-kind-input").value,
  });
  const ok = writeConvs(list);
  renderConvs(ok);
}

function renderConvs(saveOk = true) {
  const el = document.getElementById("qconv-list");
  if (!el) return;
  const list = readConvs();
  if (qconvUnreadable) {
    el.innerHTML = `<div class="notice notice-coverage"><b>לא הצלחתי לקרוא את
      השיחות השמורות.</b> <b>זו אינה תשובה שאין כאלה</b> — ייתכן שהן קיימות
      ולא נקראו.</div>`;
    return;
  }
  if (saveOk === false) {
    el.innerHTML = `<div class="notice notice-coverage">⚠ שמירת השיחה נכשלה —
      השיחה אינה שמורה.</div>` + el.innerHTML;
    return;
  }
  if (!list.length) {
    el.innerHTML = `<div class="hint">אין עדיין שיחות שמורות.</div>`;
    return;
  }
  el.innerHTML = list.map((c) => `
    <button type="button" class="qconv-item${c.id === currentConvId ? " on" : ""}"
            data-id="${escapeHtml(c.id)}">
      <span class="qconv-title">${escapeHtml(c.title)}</span>
      <span class="qconv-date">${new Date(c.at).toLocaleDateString("he-IL")}</span>
    </button>`).join("");
  el.querySelectorAll(".qconv-item").forEach((b) =>
    b.addEventListener("click", () => openConv(b.dataset.id)));
}

function openConv(id) {
  const conv = readConvs().find((c) => c.id === id);
  if (!conv) return;
  currentConvId = id;
  queryTurns = conv.turns || [];
  currentQueryDraft = null;
  document.getElementById("query-minister-input").value = conv.minister || "";
  document.getElementById("query-mk-input").value = conv.mk || "";
  if (conv.kind) document.getElementById("query-kind-input").value = conv.kind;
  const chat = document.getElementById("query-chat");
  chat.innerHTML = "";
  for (const t of queryTurns) {
    if (t.role === "user") { appendMsg(chat, "u", escapeHtml(t.content)); continue; }
    const draft = draftFromTurn(t, conv);
    if (draft) { currentQueryDraft = draft; renderQueryDraft(chat, draft); }
    else appendMsg(chat, "a", escapeHtml(t.content).replace(/\n/g, "<br>"));
  }
  renderConvs();
}

function newConv() {
  saveCurrentConv();
  currentConvId = null;
  queryTurns = [];
  currentQueryDraft = null;
  document.getElementById("query-chat").innerHTML = "";
  document.getElementById("past-queries-results").innerHTML = "";
  document.getElementById("query-composer-input").focus();
  renderConvs();
}

document.getElementById("qconv-new").addEventListener("click", newConv);
renderConvs();

// --- מומחה התקנון: עזרי ניסוח ---
// השאלה לדוגמה היא ה-placeholder של תיבת הקלט, ולכן היא **חוזרת
// אחרי כל שליחה** כשהתיבה מתרוקנת - וכך היא הופיעה באמצע שיחה.
// אחרי ההודעה הראשונה היא מוחלפת בניסוח ניטרלי.
function hideRulesExamples() {
  const input = document.getElementById("rules-composer-input");
  input.placeholder = "שאלה נוספת על התקנון…";
}

// **ניסוח הסירוב הוא מה שהמשתמש רואה, לא מה שהמערכת חשבה.**
// "נדחתה כהפרת-עיגון" ו"לא-מעוגנת" הן הודעות פנימיות שדלפו.
// המודל מסמן את המצב בתחילת ההסבר ([דעה] / [מחוץ לתחום]), ולכן
// אין כאן רשימת מילות-מפתח שמנחשת מה נשאל.
function rulesRefusalText(question, reason) {
  const r = reason || "";
  if (r.includes("[דעה]")) {
    return "דעות זה לא המחלקה שלי — אני לא בן אדם, ואין לי העדפות. " +
      "מה שכן יש לי זה את תקנון הכנסת, חוק הכנסת וחוק-יסוד: הכנסת, " +
      "ואת אלה אני מכיר היטב. שאלו אותי עליהם.";
  }
  if (r.includes("[מחוץ לתחום]")) {
    return "השאלה הזו מחוץ למה שהכלי מכסה. אני עונה רק על סמך תקנון " +
      "הכנסת, חוק הכנסת וחוק-יסוד: הכנסת — סדרי הדיון והישיבות, הליך " +
      "החקיקה, ועדות, הצבעות, הסתייגויות, חסינות וכהונת חברי הכנסת.";
  }
  return "לא מצאתי תשובה חד-משמעית ואני לא רוצה להטעות — אולי תנסה " +
    "לדייק את השאלה.";
}

// --- מומחה התקנון (ברק, 2026-09-17) ---
// **התשובה מוזרמת, וזה תנאי ולא נוחות.** כל מאגר התקנון (154K
// טוקנים) נכנס לכל שאלה, ולכן התשובה המלאה לוקחת ~17 שניות. בלי
// הזרמה זה 17 שניות של מסך ריק - גרוע מהמצב שהוחלף. עם הזרמה
// ומטמון חם המילה הראשונה מגיעה ב-0.6 שניות, ולכן אין כאן גם
// אנימציית המתנה אחרי התו הראשון: הטקסט עצמו הוא החיווי.
//
// **ושומר הציטוט מגיע בסוף, אחרי שהטקסט כבר על המסך.** זה ההבדל
// היחיד מהמצב הקודם, והוא מטופל במפורש: כשהפסק הוא refused,
// הבועה שהוזרמה **מוחלפת** בהודעה - אסור להשאיר על המסך תשובה
// שהשומר פסל.
// ת1 - **הצגת התשובה, לא סימני Markdown.** עד כאן body.textContent: כל
// "#" ו-"**" מהמודל הופיעו כמות שהם. קודם מבריחים את כל ה-HTML, ורק אז
// ממירים: **x** -> בולד אמיתי, __x__ -> קו תחתון; "#" בראש שורה - נמחק
// (בלי כותרות, ברק); "* " / "- " בראש שורה -> "•". "**" שנשאר בלי זוג
// (באמצע הזרמה, או סתם) - נמחק, כדי שלא יהבהב על המסך.
function rulesAnswerHtml(text) {
  return String(text || "").split("\n").map((line) => {
    let h = escapeHtml(line.replace(/^\s*#{1,6}\s*/, "").replace(/^(\s*)[*-]\s+/, "$1• "));
    h = h.replace(/\*\*(\S(?:[^*]*?\S)?)\*\*/g, "<b>$1</b>")
         .replace(/__(\S(?:[^_]*?\S)?)__/g, "<u>$1</u>")
         .replace(/\*\*/g, "");
    return h;
  }).join("\n");
}

async function sendRulesMessage() {
  const input = document.getElementById("rules-composer-input");
  const text = input.value.trim();
  if (!text) return;
  const chat = document.getElementById("rules-chat");

  appendMsg(chat, "u", escapeHtml(text));
  input.value = "";
  input.disabled = true;
  hideRulesExamples();

  const thinking = appendThinking(chat, "קורא את התקנון…");
  let bubble = null, body = null, acc = "", follower = null;
  const ensureBubble = () => {
    if (bubble) return;
    thinking.remove();
    bubble = appendMsg(chat, "a", "");
    body = document.createElement("span");
    bubble.appendChild(body);
    follower = followStream(chat, bubble);
  };

  try {
    const resp = await fetch("/api/rules/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text }),
    });
    if (!resp.ok || !resp.body) {
      const err = await resp.json().catch(() => ({}));
      appendMsg(chat, "err", escapeHtml(err.detail || "שגיאה במענה."));
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "", done = null, streamError = null;
    for (;;) {
      const { value, done: finished } = await reader.read();
      if (finished) break;
      buf += decoder.decode(value, { stream: true });
      // NDJSON: שורה שלמה בלבד. שורה חלקית נשארת בחוצץ - פענוח
      // שלה היה זורק, ומאבד את שאר התשובה.
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        let ev;
        try { ev = JSON.parse(line); } catch { continue; }
        if (ev.delta) {
          ensureBubble();
          acc += ev.delta;
          body.innerHTML = rulesAnswerHtml(acc);
          follower.update();   // צ1 - לא scrollHeight בכל קטע
        } else if (ev.done) {
          done = ev.done;
        } else if (ev.error) {
          streamError = ev.error;
        }
      }
    }

    if (streamError) {
      // כשל שהתרחש אחרי שה-200 כבר יצא. אם כבר הוזרם טקסט - הוא
      // חלקי, ואסור להשאיר אותו כאילו הוא תשובה שלמה.
      if (bubble) bubble.remove();
      appendMsg(chat, "err", escapeHtml(streamError));
      return;
    }
    if (!done) {
      if (bubble) bubble.remove();
      appendMsg(chat, "err", "התשובה נקטעה באמצע ואינה שלמה. נסו שוב.");
      return;
    }
    if (done.refused) {
      if (bubble) bubble.remove();
      appendMsg(chat, "a", escapeHtml(rulesRefusalText(text, done.refusal_reason)));
      return;
    }
    ensureBubble();
    body.innerHTML = rulesAnswerHtml(done.text || acc);
    if ((done.cited_sources || []).length) {
      const cites = document.createElement("div");
      cites.className = "word-count";
      cites.textContent = `מקורות: ${done.cited_sources.join(" · ")}`;
      bubble.appendChild(cites);
    }
  } catch {
    if (bubble) bubble.remove();
    appendMsg(chat, "err", "החיבור נקטע לפני שהתשובה הושלמה. נסו שוב.");
  } finally {
    if (follower) follower.stop();
    thinking.remove();
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("rules-send-btn").addEventListener("click", sendRulesMessage);
bindComposer(document.getElementById("rules-composer-input"), sendRulesMessage);

/* החיפוש הסמנטי הוסר (ברק, 25.9.2026 - ביצועים, ערך למשתמש).
 * הקוד בענף archive/semantic-search-v1; ראו DECISION_HISTORY. */

/* ═══ OData של הכנסת ═══ (משימה 1.4)
 * שלושה חיבורים לפיד של הכנסת, כל אחד במקום שבו הוא באמת נחוץ:
 * מראי מקום ליד תצוגת הוורד, אזהרת הצעות דומות מעל עורך החוק,
 * ומאגר השאילתות בתוך כלי השאילתא. כולם "נכשלים רכות" - הפיד
 * חיצוני, ואם הוא לא זמין הכלי עצמו חייב להמשיך לעבוד. */

async function loadCitations(lawId) {
  const box = document.getElementById("citations-box");
  const body = document.getElementById("citations-body");
  if (!box || !lawId) return;
  box.hidden = false;
  body.innerHTML = `<div class="hint">טוען את פרסומי החוק…</div>`;
  try {
    const resp = await fetch(`/api/laws/${encodeURIComponent(lawId)}/citations`);
    if (!resp.ok) throw new Error("feed");
    const data = await resp.json();
    const summary = box.querySelector("summary");
    if (!data.in_knesset_db) {
      // ההבחנה בין "אין תיקונים" ל"לא קיים במאגר" - ופתוח כברירת
      // מחדל, אחרת ההסבר חבוי מאחורי אקורדיון מקופל ונראה כמו כלום.
      summary.textContent = "פרסומי החוק ותיקוניו — אין רשומה";
      box.open = true;
      body.innerHTML = `<div class="hint">${escapeHtml(data.note || "אין רשומה במאגר הכנסת.")}</div>`;
      return;
    }
    summary.textContent = `פרסומי החוק ותיקוניו (${data.citations.length})`;
    box.open = false;
    const rows = data.citations
      .map((c) => `<div class="citation-row">
          <b>${c.is_original ? "הפרסום המקורי" : escapeHtml(c.kind || "תיקון")}</b>
          <span class="citation-ref">${escapeHtml(c.reference)}</span>
          <span class="citation-date">${escapeHtml(formatHebrewDate(c.published_at))}</span>
          <div class="citation-title">${escapeHtml(c.title || "")}</div>
        </div>`)
      .join("");
    body.innerHTML = rows || `<div class="hint">לא נמצאו פרסומים.</div>`;
  } catch {
    body.innerHTML = `<div class="hint">מאגר הכנסת אינו זמין כרגע.</div>`;
  }
}

const SIMILAR_COLLAPSED_KEY = "legislator.similar.collapsed";
const KNESSET_BILL_URL =
  "https://main.knesset.gov.il/Activity/Legislation/Laws/Pages/LawBill.aspx" +
  "?t=lawsuggestionssearch&lawitemid=";

/** מנקה את חלון ההצעות הדומות. נקרא בכל מעבר בין הצעות/חוקים -
 *  בלעדיו נשארות על המסך ההצעות הדומות של ההצעה **הקודמת**, מצב
 *  ישן שמוצג כאילו הוא של הנוכחית (ברק, 22.9). */
function clearSimilarBills() {
  const el = document.getElementById("similar-bills-notice");
  if (el) el.innerHTML = "";
}

async function checkSimilarBills(title) {
  const el = document.getElementById("similar-bills-notice");
  if (!el) return;
  if (!title || title.trim().length < 6) {
    el.innerHTML = "";
    return;
  }
  try {
    const resp = await fetch(`/api/bills/similar?title=${encodeURIComponent(title)}&limit=5`);
    if (!resp.ok) throw new Error("feed");
    const data = await resp.json();
    if (!data.results.length) {
      el.innerHTML = "";
      return;
    }
    const items = data.results
      .map((b) => {
        const link = b.bill_id
          ? `<a href="${KNESSET_BILL_URL}${encodeURIComponent(b.bill_id)}"
                target="_blank" rel="noopener">${escapeHtml(b.bill_label || "דף ההצעה")}</a>`
          : escapeHtml(b.bill_label || "");
        // הצעות ממשלתיות אינן מופיעות ב-KNS_BillInitiator כלל -
        // היוזמת היא הממשלה, לא חברי כנסת. אומת מול הפיד. במקרה
        // כזה מוצג סוג ההצעה, כדי שהשורה לא תישאר חסרת הקשר.
        const who = b.initiators_unavailable
          ? ' · <span class="similar-unknown">שמות היוזמים לא נטענו</span>'
          : (b.initiators || []).length
            ? ` · ${escapeHtml(b.initiators.slice(0, 3).join(", "))}` +
              (b.initiators.length > 3 ? ` ועוד ${b.initiators.length - 3}` : "")
            : (b.kind ? ` · ${escapeHtml(b.kind)}` : "");
        return `<li>${escapeHtml(b.title)}
          <span class="citation-date">${link ? link + " · " : ""}כנסת ${b.knesset}${
            b.became_law ? " · התקבל כחוק" : ""}${who}</span></li>`;
      })
      .join("");
    // מצב הקיפול נשמר בין הצעות: מי שסגר את החלון לא רוצה שייפתח
    // מחדש בכל שינוי שם.
    let collapsed = false;
    try { collapsed = localStorage.getItem(SIMILAR_COLLAPSED_KEY) === "1"; } catch { /* ignore */ }
    el.innerHTML = `<div class="notice notice-coverage similar-notice${collapsed ? " is-collapsed" : ""}">
        <button type="button" class="similar-toggle" aria-expanded="${!collapsed}">
          <span class="similar-caret">${collapsed ? "▸" : "▾"}</span>
          <b>נמצאו הצעות דומות בשמן (${data.results.length}).</b>
        </button>
        <div class="similar-body">
          החוברת הסגולה מחייבת לבדוק הצעות זהות או דומות לפני הנחה.
          <ul>${items}</ul>
          <span class="citation-date">${escapeHtml(data.note)}</span>
        </div>
      </div>`;
    const box = el.querySelector(".similar-notice");
    el.querySelector(".similar-toggle").addEventListener("click", () => {
      const nowCollapsed = !box.classList.contains("is-collapsed");
      box.classList.toggle("is-collapsed", nowCollapsed);
      box.querySelector(".similar-caret").textContent = nowCollapsed ? "▸" : "▾";
      box.querySelector(".similar-toggle").setAttribute("aria-expanded", String(!nowCollapsed));
      try { localStorage.setItem(SIMILAR_COLLAPSED_KEY, nowCollapsed ? "1" : "0"); } catch { /* ignore */ }
    });
  } catch {
    // **כשל פיד אינו "לא נמצאו הצעות דומות".** מסך ריק נראה בדיוק
    // כמו בדיקה שהסתיימה בלא-כלום - וזו הבדיקה שהחוברת הסגולה
    // מחייבת לפני הנחה. המשתמש חייב לדעת שהיא **לא רצה**.
    el.innerHTML = `<div class="notice notice-coverage">
        <b>לא הצלחתי לבדוק אם קיימות הצעות דומות.</b>
        מאגר הכנסת אינו זמין כרגע. <b>זו אינה תשובה ש"אין" הצעות דומות</b> —
        הבדיקה לא רצה. נסו שוב, או בדקו ידנית באתר הכנסת לפני ההנחה.
      </div>`;
  }
}

// ── שאילתות קודמות: חיפוש הדרגתי ────────────────────────────────
// החיפוש אינו קריאה אחת אלא כמה (יחידה = צירוף = קריאה אחת לפיד),
// וכל אחת מסתיימת בזמן אחר. אין סיבה לחכות שכולן יחזרו: כל תשובה
// מוצגת ברגע שהיא חוזרת.
//
// **שתי מגבלות שמכתיבות את כל המבנה כאן:**
// 1. שורה נוספת **למטה בלבד** ולעולם לא זזה ולא נעלמת - מי שקורא
//    שורה שלישית לא ימצא שורה אחרת במקומה. ולכן גם אין סידור מחדש
//    בסוף: הדירוג מוצג כתווית שמתעדכנת במקום, לא כשינוי סדר.
// 2. כדי לא *להסיר* שורות חלשות בסוף (שזו קפיצה גרועה מסידור מחדש),
//    תוצאה שהגיעה מיחידה של מילה בודדת **נעצרת בצד** עד סוף החיפוש,
//    ורק ארבע הטובות שבהן נוספות בסוף, למטה. זה המימוש של "דירוג 1
//    נחתך לארבעה מקומות" בלי ששום שורה תיעלם מהמסך.
// ב5 - סינון לפי כנסת. **ברירת המחדל נגזרת ולא קבועה:** הכנסת
// הנוכחית והקודמת, לפי KNS_KnessetDates.IsCurrent - היום 25 ו-24,
// ובעוד חודשיים 26 ו-25. null = "לא הצלחנו לקבוע", ואז מחפשים בכל
// הכנסות ואומרים זאת, במקום להציג 25 כאילו הוא ידוע.
let pqKnessetInfo = { current: null, default: [], available: [] };
let pqKnessetChoice = null;   // null = ברירת המחדל; [] = כל הכנסות

async function loadKnessetInfo() {
  try {
    const r = await fetch("/api/queries/knessets");
    if (r.ok) pqKnessetInfo = await r.json();
  } catch { /* נשאר null - הממשק יאמר שלא ידוע */ }
  renderKnessetPicker();
}

function pqActiveKnessets() {
  return pqKnessetChoice !== null ? pqKnessetChoice : (pqKnessetInfo.default || []);
}

function pqKnessetParams(list) {
  return (list || pqActiveKnessets()).map((n) => `&knesset=${n}`).join("");
}

// ש7 - **שינוי בכנסות מעדכן את התוצאות מיד, בלי לבנות אותן מחדש.**
// הסרה: השורות של הכנסת שהוסרה יורדות, בלי בקשה. הוספה: החיפוש רץ רק
// על הכנסות החדשות (עם הפירוק ששמור מהחיפוש הקודם - בלי קריאה למודל),
// ומה שנמצא מתווסף למטה. [] = כל הכנסות.
let pqLast = null;      // {q, plan} של החיפוש האחרון שהסתיים
let pqRunning = false;

function pqAllowed(knesset, list) {
  return !list.length || list.includes(Number(knesset));
}

function onKnessetChange(before, after) {
  const rowsEl = document.getElementById("pq-rows");
  if (!pqLast || !rowsEl) return;              // עוד לא היה חיפוש
  if (pqRunning) { searchPastQueries(); return; }   // באמצע חיפוש - מתחילים מחדש
  rowsEl.querySelectorAll("[data-qid]").forEach((el) => {
    if (!pqAllowed(el.dataset.knesset, after)) el.remove();
  });
  const added = !after.length ? (before.length ? [] : null)   // [] = הכול
    : after.filter((n) => before.length && !before.includes(n));
  pqUpdateDoneCount();
  if (added === null || (added && !added.length && after.length)) return;   // הסרה בלבד
  searchPastQueries({ append: true, knessets: added });
}

function pqUpdateDoneCount() {
  const rowsEl = document.getElementById("pq-rows");
  const line = document.querySelector("#pq-done .pq-done-count");
  if (rowsEl && line) line.textContent = `${rowsEl.querySelectorAll("[data-qid]").length} תוצאות.`;
}

function renderKnessetPicker() {
  const el = document.getElementById("pq-knesset");
  if (!el) return;
  const active = pqActiveKnessets();
  const all = active.length === 0;
  if (!pqKnessetInfo.current) {
    el.innerHTML = `<span class="pq-knesset-note">לא הצלחתי לקבוע מהי הכנסת
      הנוכחית — החיפוש רץ על כל הכנסות.</span>`;
    return;
  }
  const opts = (pqKnessetInfo.available || []).slice(-8).reverse();
  el.innerHTML =
    `<span class="pq-knesset-note">כנסות:</span>` +
    `<button type="button" class="pq-chip${all ? " on" : ""}" data-k="all">הכול</button>` +
    opts.map((n) => `<button type="button" class="pq-chip${
      active.includes(n) ? " on" : ""}" data-k="${n}">${n}</button>`).join("");
  el.querySelectorAll(".pq-chip").forEach((b) => b.addEventListener("click", () => {
    const k = b.dataset.k;
    const before = pqActiveKnessets();
    if (k === "all") { pqKnessetChoice = []; }
    else {
      const n = Number(k);
      const cur = new Set(pqActiveKnessets());
      cur.has(n) ? cur.delete(n) : cur.add(n);
      pqKnessetChoice = [...cur].sort((a, z) => z - a);
    }
    renderKnessetPicker();
    onKnessetChange(before, pqActiveKnessets());
  }));
}
loadKnessetInfo();

const PQ_MAX_STRONG_ROWS = 12;   // שורות מיחידות רב-מיליות
const PQ_MAX_RANK1_ROWS = 4;     // "דירוג 1" - הזנב, נחתך לארבעה

// **צירוף רחב מוחזק עד סוף החיפוש.** זה הכלל היחיד שסוגר את הפער
// בין 89% ל-96% דיוק, והוא יקר: צירוף שמתאים ליותר מ-60 כותרות
// אינו מציג שורות בזמן אמת - בסוף החיפוש מוצג ממנו רק מה שהצטלב
// עם צירוף אחר. נמדד (2026-09-22) שכל הרעש היה שורות כאלה שנכנסו
// ב-2.8 שניות, לפני שידענו מה מצטלב: "זיהום אוויר" (116 תוצאות)
// הכניסה זיהום אוויר בתל אביב ובאשקלון לפני ש"מפרץ חיפה" (13)
// חזרה בכלל. המחיר: בנושא שבו הצירוף הפותח רחב, השורה הראשונה
// ב-5.5 שניות במקום 2.8. החלטת ברק: "הראש הוא מה שנקרא".
// חייב להיות זהה ל-knesset_queries.unit_budget/HOLD_ABOVE.
const PQ_HOLD_ABOVE = 60;
function pqUnitBudget(count) {
  if (count <= 25) return PQ_MAX_STRONG_ROWS;
  if (count <= PQ_HOLD_ABOVE) return 6;
  return 0;                      // רחב - מוחזק לסוף, רק ההצלבה מוצגת
}
// ש2 (25.9.2026): **4 בקשות בו-זמנית, סך הכול** - בדיקות הפתיחה בתוך
// אותו תור, לא בנוסף לו (עד כאן יצאו עד 7). אבל **המקביליות לא הייתה
// הסיבה** ל"4 מתוך 11 מקורות נבדקו": ה-WAF של הכנסת חוסם כל סינון עם
// 4 תנאי contains() ומעלה, תמיד (ראו knesset_queries.run_unit). נמדד
// על עשרה חיפושים: 2 בו-זמנית בלי תיקון ה-WAF - 86/94, אותם כשלים;
// עם התיקון - 2 בו-זמנית 89/89 ב-154 שניות, 4 בו-זמנית 93/93 ב-99.
const PQ_CONCURRENCY = 4;
const PQ_CACHE_KEY = "legislator.pq-units.v1";
const PQ_CACHE_MAX = 150;

// מטמון יומי לפי צירוף + כנסות. מאגר השאילתות משתנה לאט - אין סיבה
// לשאול את הפיד את אותו דבר פעמיים באותו יום.
function pqCacheGet(key) {
  try {
    const all = JSON.parse(localStorage.getItem(PQ_CACHE_KEY) || "{}");
    const hit = all[key];
    return hit && hit.day === new Date().toDateString() ? hit.data : null;
  } catch { return null; }
}
function pqCachePut(key, data) {
  try {
    const all = JSON.parse(localStorage.getItem(PQ_CACHE_KEY) || "{}");
    all[key] = { day: new Date().toDateString(), data };
    const keys = Object.keys(all);
    for (const k of keys.slice(0, Math.max(0, keys.length - PQ_CACHE_MAX))) delete all[k];
    localStorage.setItem(PQ_CACHE_KEY, JSON.stringify(all));
  } catch { /* אחסון מלא/חסום - בלי מטמון, לא בלי תוצאות */ }
}
let pqToken = 0;

// ש4 - **התחום**: כל שורה חייבת להכיל מונח מהגוף או התחום שבנושא
// (משטרה, חינוך, מקום). נמדד לפני: "מחסור בכוח אדם במשטרת ישראל" ->
// שלוש שורות, שלושתן על בריאות. חייב להיות זהה ל-
// knesset_queries.domain_match. תחום ריק = אין סינון.
function pqNorm(text) {
  return String(text || "").replace(/[״”“]/g, '"').replace(/[׳’]/g, "'")
    .replace(/[-־]/g, " ").split(/\s+/).filter(Boolean).join(" ");
}
// מונח מופיע בכותרת - בתחילת מילה, אחרי עד 3 אותיות שימוש, ומילה-מילה
// (knesset_queries.term_in): "מורה" לא ב"החמורה"; "תקן" (עד 3 אותיות -
// מילה שלמה) ב"בתקן" ולא ב"התקנת"; "בתי ספר" ב"בבתי הספר".
function pqWordMatches(word, token) {
  for (let cut = 0; cut <= Math.min(3, token.length - 1); cut += 1) {
    if (cut && !"והבלמשכ".includes(token[cut - 1])) break;
    const rest = token.slice(cut);
    if (word.length <= 3 ? rest === word : rest.startsWith(word)) return true;
  }
  return false;
}
function pqTermIn(term, title) {
  const words = (x) => pqNorm(x).match(/[א-ת]+|[^\sא-ת]+/g) || [];
  const tokens = words(title);
  return words(term).every((w) => tokens.some((tok) => pqWordMatches(w, tok)));
}
// domain = היבטים (הגוף/התחום, ומקום אם נקבו בו): מונח אחד לפחות מכל היבט.
function pqDomainMatch(title, domain) {
  if (!domain || !domain.length) return true;
  return domain.every((facet) => facet.some((term) => pqTermIn(term, title)));
}

function pqRowHtml(row) {
  // שורות ישנות במאגר חסרות תאריך או סוג. מרכיבים את שורת המידע
  // מהחלקים שקיימים בלבד - מפריד ריק בין שני שדות חסרים נראה כמו
  // תקלה בתצוגה.
  const meta = [row.kind, row.knesset ? `כנסת ${row.knesset}` : "", row.submitted_at]
    .filter(Boolean).map(escapeHtml).join(" · ");
  // תווית הדירוג מופיעה רק מ-2 ומעלה: "1" אינו מידע, הוא רעש על כל שורה.
  const rank = `<span class="pq-rank" title="מספר צירופי החיפוש שהתאימו"${
    row.matched >= 2 ? "" : " hidden"}>${row.matched}</span>`;
  // ב6 - הכותרת מקשרת ל**דף השאילתה** באתר הכנסת, לא מורידה את
  // קובץ ה-Word. הקישור ידוע בזמן הרינדור (הוא נגזר מהמזהה), ולכן
  // אינו ממתין לשלב ההשלמה.
  const title = escapeHtml(row.title || "");
  const titleHtml = row.page_url
    ? `<a href="${escapeHtml(row.page_url)}" target="_blank" rel="noopener">${title}</a>`
    : title;
  return `<div class="citation-row" data-qid="${row.query_id}" data-person="${row.person_id || ""}" data-knesset="${row.knesset || ""}">
      <div class="citation-title"><span class="pq-title">${titleHtml}</span>${rank}</div>
      <span class="citation-date">${meta}${meta ? " · " : ""}<span class="pq-asked">…</span></span>
    </div>`;
}

// ב5 - מריץ את חיפוש השאילתות הקודמות מעצמו אחרי שנוסחה שאילתה.
// אותו מנגנון בדיוק כמו חיפוש ידני (כולל התצוגה ההדרגתית), רק
// שהקלט מגיע מהנושא שנוסח ולא מהקלדה.
// "נסה שוב" (ש2) - מריץ את אותו חיפוש שוב. מה שכבר נטען מגיע מהמטמון
// היומי מיד; רק מה שנכשל חוזר לפיד.
function bindPqRetry(q) {
  const btn = document.getElementById("pq-retry");
  if (!btn) return;
  btn.addEventListener("click", () => {
    document.getElementById("past-queries-input").value = q;
    searchPastQueries();
  });
}

function autoSearchPastQueries(topic) {
  const input = document.getElementById("past-queries-input");
  if (!input || !topic) return;
  input.value = topic;
  searchPastQueries();
}

async function searchPastQueries(opts = {}) {
  const mine = pqToken + 1;   // הטוקן שהחיפוש הזה יקבל
  try {
    await pqSearch(opts && opts.append ? opts : {});
  } finally {
    if (pqToken === mine) pqRunning = false;
  }
}

async function pqSearch(opts) {
  const input = document.getElementById("past-queries-input");
  const out = document.getElementById("past-queries-results");
  const append = !!opts.append && pqLast && document.getElementById("pq-rows");
  const q = append ? pqLast.q : input.value.trim();
  if (!q) return;
  const knessets = append ? opts.knessets : pqActiveKnessets();
  const token = ++pqToken;
  pqRunning = true;

  if (!append) {
    pqLast = null;
    out.innerHTML = `<div class="pq-status" id="pq-status">
        <span class="spinner"></span><span>מחפש…</span></div>
      <div id="pq-rows"></div><div id="pq-done"></div>`;
  } else {
    // ש7: התוצאות הקיימות נשארות; רק שורת הסיום מתחלפת בחיווי.
    document.getElementById("pq-done").innerHTML = `<div class="pq-status" id="pq-status">
        <span class="spinner"></span><span>מחפש…</span></div>`;
  }
  const statusEl = document.getElementById("pq-status");
  const rowsEl = document.getElementById("pq-rows");
  const doneEl = document.getElementById("pq-done");

  const rank = new Map();    // query_id -> כמה יחידות התאימו
  const shown = new Set();   // query_id שכבר על המסך
  const newIds = new Set();  // מה שנוסף בחיפוש הזה - רק הן עוברות השלמה
  const held = new Map();    // query_id -> שורה שנדחתה במכסה, מועמדת לשלב ההצלבה
  let strongRows = 0, done = 0, failed = 0, total = 0, planReady = false;
  let domain = [], blocked = false;
  // ש4: תשובות שהגיעו לפני הפירוק ממתינות לו. עד כאן בדיקת הפתיחה
  // "מחסור בכוח" הציגה מיד "מחסור בכוח אדם רפואי" - לפני שהיה ידוע
  // שהנושא הוא משטרה. השורה הראשונה מגיעה עכשיו עם הפירוק (~2.5
  // שניות), וזה אותו זמן בערך, כי שתי הקריאות יוצאות יחד.
  const early = [];

  const setStatus = () => {
    if (token !== pqToken || !statusEl.isConnected) return;
    // לפני שהפירוק חזר עוד לא ידוע כמה מקורות יהיו - ואומרים "מחפש…"
    // במקום להציג מכנה שעוד ישתנה.
    // בלי "מקורות" - מונח פנימי. ההתקדמות נראית בשורות שנכנסות.
    statusEl.querySelector("span:last-child").textContent = "מחפש…";
  };
  const appendRow = (row) => {
    if (shown.has(row.query_id)) return;
    shown.add(row.query_id);
    newIds.add(row.query_id);
    rowsEl.insertAdjacentHTML("beforeend", pqRowHtml(row));
  };
  // בהוספה (ש7) - מה שכבר על המסך נחשב "הוצג", כדי שלא יוכפל.
  if (append) rowsEl.querySelectorAll("[data-qid]").forEach((el) => shown.add(Number(el.dataset.qid)));
  const bumpBadge = (qid, n) => {
    const b = rowsEl.querySelector(`[data-qid="${qid}"] .pq-rank`);
    if (!b) return;
    b.textContent = n;
    if (n >= 2) b.removeAttribute("hidden");
  };

  const absorb = (unit, data) => {
    // **יחידה של מילה בודדת מדרגת ואינה שולפת.** נמדד (2026-09-22):
    // "פריפריה" לבדה הכניסה למסך זמני המתנה לרופאים, התחסנות ילדים
    // לשפעת והנחה בתחבורה ציבורית - ארבע שורות רעש מתוך שש-עשרה.
    // מילה אחת אינה מזהה נושא, גם כשהיא נושאית בפני עצמה.
    // מילה בודדת = איבר אחד בלי רווח בתוכו. ["מצוקת הדיור"] הוא
    // צירוף שנשלח כרצף אחד, לא מילה בודדת.
    // רחב ומילה בודדת מדרגים בלבד - אלא אם יש שני היבטים ומעלה (ש4):
    // אז כל שורה נבדקת על תופעה + גוף, ו"שוטר" לבדה רשאית לספק את
    // כותרות המשטרה שיש בהן מחסור. חייב להיות זהה ל-search_queries.
    const strict = domain.length >= 2;
    const single = unit.words.length === 1 && !unit.words[0].trim().includes(" ");
    const rankOnly = unit.rankOnly ||
      (!strict && ((data.too_broad && !domain.length) || single));
    // המכסה לפי מה שנשאר אחרי התחום: "זיהום אוויר" (116) אחרי סינון
    // לחיפה הוא צירוף צר, לא רחב.
    const rows = (data.rows || []).filter((r) => pqDomainMatch(r.title, domain));
    const count = domain.length ? rows.length : data.count;
    const budget = pqUnitBudget(count);
    let used = 0;
    for (const row of rows) {
      const id = row.query_id;
      const n = (rank.get(id) || 0) + 1;
      rank.set(id, n);
      if (shown.has(id)) { bumpBadge(id, n); continue; }
      const waiting = held.get(id);
      if (waiting) {
        waiting.matched = n;
        // התאמה שנייה מוכיחה שהשורה אינה מקרית - עולה למסך מיד,
        // ובכל זאת נוספת למטה בלבד.
        if (n >= 2 && strongRows < PQ_MAX_STRONG_ROWS) {
          held.delete(id);
          strongRows += 1;
          appendRow(waiting);
        }
        continue;
      }
      if (rankOnly) continue;
      const candidate = { ...row, matched: n, matched_by: unit.words.join(" "),
                          unit_count: count, broad: count > PQ_HOLD_ABOVE };
      if (used < budget && strongRows < PQ_MAX_STRONG_ROWS) {
        used += 1; strongRows += 1;
        appendRow(candidate);
      } else {
        held.set(id, candidate);   // מחכה להצלבה בסוף
      }
    }
  };

  const failedUnits = [];
  const runUnit = async (unit) => {
    const qs = unit.words.map((w) => `w=${encodeURIComponent(w)}`).join("&")
      + pqKnessetParams(knessets);
    try {
      let data = pqCacheGet(qs);
      if (!data) {
        // הפיד חוסם את השרת - לא שולחים עוד בקשות שייכשלו (ש4).
        if (blocked) throw new Error("blocked");
        const r = await fetch(`/api/queries/unit?${qs}`);
        if (r.status === 503) blocked = true;
        if (!r.ok) throw new Error("unit");
        data = await r.json();
        pqCachePut(qs, data);
      }
      if (token !== pqToken) return;
      done += 1;
      if (planReady) absorb(unit, data); else early.push([unit, data]);
    } catch {
      if (token !== pqToken) return;
      failed += 1;   // **לא נבלע:** נספר, מנוסה שוב, ונאמר אם נשאר
      failedUnits.push(unit);
    }
    setStatus();
  };

  // שלב א' - **צירופי המשתמש עצמו, יוצאים מיד ולא ממתינים למודל.**
  // קריאת ה-LLM לוקחת ~2.5 שניות, ואחריה עוד ~2.5 לקריאה הראשונה
  // לפיד - כלומר שורה ראשונה רק ב-5.5 שניות. כל צמד מילים סמוכות
  // בנושא שהמשתמש הקליד הוא צירוף מועמד ("מצוקת הדיור", "הדיור
  // בפריפריה"), והוא נשלח כרצף אחד ברגע הלחיצה. אין כאן רשימת
  // מילים ואין ניחוש שעולה משהו: צירוף שאינו קיים בשום כותרת חוזר
  // ריק ולא נראה. זה גם מה שמבטיח שהמגביל של הנושא ("במפרץ חיפה")
  // ייבדק גם כשהמודל לא החזיר אותו כיחידה.
  //
  // **רק הצמד הראשון שולף; שאר הצמדים מדרגים.** נמדד: ב"אלימות
  // במערכת החינוך" הצמד השני ("במערכת החינוך") הציף את ראש הרשימה
  // במחסור במורים, בפערים טכנולוגיים ובהיערכות למיגון - שישה מתוך
  // שש-עשרה. הצירוף הפותח של הנושא הוא הנושא; מה שבא אחריו מסייג
  // אותו ("במפרץ חיפה", "בפריפריה", "בנגב"), וסייג מצמצם - הוא לא
  // אמור להביא שורות משל עצמו.
  const qWords = q.split(/\s+/).filter(Boolean);
  const probeUnits = qWords.slice(0, -1)
    .map((w, i) => ({ words: [`${w} ${qWords[i + 1]}`], kind: "probe",
                      probe: true, rankOnly: i > 0 }))
    .slice(0, 4);
  total = probeUnits.length;
  // בדיקות הפתיחה יוצאות מיד - אבל דרך אותו תור של PQ_CONCURRENCY,
  // לא כולן בבת אחת (ש2).
  const queue = [...probeUnits];
  let active = 0;
  const pump = () => new Promise((resolve) => {
    const tick = () => {
      if (!queue.length && active === 0) return resolve();
      while (active < PQ_CONCURRENCY && queue.length) {
        active += 1;
        runUnit(queue.shift()).finally(() => { active -= 1; tick(); });
      }
    };
    pump.tick = tick;
    tick();
  });
  const probeRuns = [pump()];

  // שלב ב - פירוק הנושא. כשל כאן אינו עוצר את החיפוש: נופלים חזרה
  // לחיפוש המילולי בדיוק כפי שהיה, ואומרים שההרחבה לא רצה.
  // ניסיון חוזר אחד (ש4): באתר החי נמדד פירוק שנכשל פעם אחת מתוך
  // שמונה, ובלעדיו אין תחום - והרעש חוזר ("זיהום אוויר בתל אביב" לנושא
  // על מפרץ חיפה). מקומית, אותו פירוק: 8/8.
  let plan = append ? pqLast.plan : null;
  for (let attempt = 0; attempt < 2 && !plan; attempt += 1) {
    try {
      const r = await fetch(`/api/queries/plan?q=${encodeURIComponent(q)}`);
      if (!r.ok) throw new Error("plan");
      const data = await r.json();
      if (data.expanded === false && data.expansion_error && attempt === 0) throw new Error("plan");
      plan = data;
    } catch { /* ננסה שוב, ואחר כך הניסוח המדויק */ }
  }
  if (!plan) plan = { units: [{ words: [q], kind: "literal" }], expanded: false };
  if (token !== pqToken) return;
  domain = plan.domain || [];
  planReady = true;
  for (const [u, d] of early.splice(0)) absorb(u, d);
  const probeKeys = new Set(probeUnits.map((u) => u.words.join(" ")));
  const units = (plan.units || []).filter((u) => !probeKeys.has(u.words.join(" ")));
  total += units.length;
  setStatus();
  if (!total) {
    statusEl.remove();
    doneEl.innerHTML = `<div class="hint">מונח חיפוש קצר מדי.</div>`;
    return;
  }

  // שלב ג - יחידה אחת = קריאה אחת, דרך אותו תור (2 בו-זמנית), ונקלטות
  // לפי סדר ההגעה. היחידות ממוינות לפי סגוליות - הצרות יוצאות ראשונות.
  // **ממתינים לתור מחדש, לא להבטחה של בדיקות הפתיחה.** זו נפתרה
  // כשהתור התרוקן בפעם הראשונה - ואם בדיקות הפתיחה הסתיימו לפני
  // שהפירוק חזר, החיפוש "הסתיים" בזמן שיחידות הפירוק עוד רצו: שורות
  // נוספו אחרי שורת הסיום, בלי שם מגיש ובלי שלב ההצלבה (נמצא ב-ש4).
  queue.push(...units);
  await Promise.all(probeRuns);
  await pump();
  if (token !== pqToken) return;
  // מקור שנכשל מנוסה שוב פעם אחת, לבד, אחרי שהעומס ירד.
  if (failedUnits.length && !blocked) {
    const retry = failedUnits.splice(0);
    failed -= retry.length;
    for (const u of retry) {
      await new Promise((r) => setTimeout(r, 400));
      await runUnit(u);
    }
    if (token !== pqToken) return;
  }

  // שלב ד' - ההצלבה. עכשיו ידוע לכמה צירופים כל שורה התאימה, ושורה
  // שהתאימה ליותר מאחד היא התוצאה המדויקת ביותר שיש. אם היא נדחתה
  // קודם במכסה של יחידה רחבה - היא נכנסת עכשיו, ותמיד למטה.
  [...held.values()]
    .filter((r) => r.matched >= 2)
    .sort((a, b) => b.matched - a.matched || a.unit_count - b.unit_count)
    .slice(0, Math.max(0, PQ_MAX_STRONG_ROWS - strongRows))
    .forEach((r) => { strongRows += 1; held.delete(r.query_id); appendRow(r); });

  // ואז הזנב: עד ארבע שורות שהתאימו לצירוף אחד בלבד, מהצירוף הצר
  // ביותר. **שורה של צירוף רחב אינה נכנסת לזנב** - מצירוף רחב מוצג
  // רק מה שהצטלב.
  [...held.values()]
    .filter((r) => !r.broad && r.matched < 2 && !shown.has(r.query_id))
    .sort((a, b) => a.unit_count - b.unit_count)
    .slice(0, PQ_MAX_RANK1_ROWS)
    .forEach(appendRow);

  statusEl.remove();
  pqLast = { q, plan };
  const foundRows = rowsEl.querySelectorAll("[data-qid]").length;
  const parts = [];
  // ש2: בלי הקופסה הצהובה ובלי "מקורות"/"פיד". אם אחרי כל הניסיונות
  // עדיין חסר משהו - שורה שקטה עם "נסה שוב". **לא מוסתר לגמרי:** זה
  // בדיוק "לא נמצא" במקום "לא בדקתי" (CLAUDE.md).
  const retryLink = failed
    ? ` <span class="pq-partial">חלק מהתוצאות לא נטענו — <button type="button" class="dz-link" id="pq-retry">נסה שוב</button></span>`
    : "";
  if (!plan.expanded) {
    parts.push(`החיפוש נעשה על הניסוח המדויק בלבד.`);
  }
  if (foundRows === 0 && done === 0 && failed) {
    // **שום דבר לא נבדק** - אסור להגיד "לא נמצא" (CLAUDE.md).
    doneEl.innerHTML = `<div class="notice notice-coverage">
        <b>מאגר השאילתות של הכנסת לא זמין כרגע.</b>
        לא נבדק דבר — זו אינה תשובה שהנושא לא נשאל.
        <button type="button" class="dz-link" id="pq-retry">נסה שוב</button> בעוד כמה דקות.
      </div>`;
    bindPqRetry(q);
    return;
  }
  if (foundRows === 0) {
    // **"לא נמצא" אינו "אין".** ראו CLAUDE.md.
    doneEl.innerHTML = `<div class="notice notice-coverage">
        <b>החיפוש לא מצא כותרת שמכילה את הצירופים האלה.</b>
        החיפוש רץ על כותרות השאילתות בלבד — שאילתה שעוסקת באותו נושא
        בניסוח אחר לא תיתפס בו. <b>זו אינה תשובה שהנושא לא נשאל</b>.
        ${parts.join(" ")}${retryLink}
      </div>`;
    bindPqRetry(q);
    return;
  }
  doneEl.innerHTML = `<div class="pq-done"><span class="pq-done-count">${foundRows} תוצאות.</span> ${parts.join(" ")}${retryLink}</div>`;
  bindPqRetry(q);

  // שלב ה' - מי שאל וקישור לקובץ. רץ אחרי התצוגה וממלא שדות במקום:
  // לא מוסיף שורה, לא מזיז שורה, ולכן אינו יכול לגרום לקפיצה.
  const ids = [...newIds];
  if (!ids.length) return;
  const persons = ids.map((id) => pqPersonOf(rowsEl, id)).filter(Boolean);
  try {
    const r = await fetch(`/api/queries/enrich?ids=${ids.join(",")}&persons=${persons.join(",")}`);
    if (!r.ok) throw new Error("enrich");
    const extra = await r.json();
    if (token !== pqToken) return;
    for (const id of ids) {
      const el = rowsEl.querySelector(`[data-qid="${id}"]`);
      if (!el) continue;
      const pid = el.dataset.person;
      const name = extra.names[pid];
      el.querySelector(".pq-asked").textContent =
        name || (extra.names_unavailable ? "שם המגיש לא נשלף" : "המגיש אינו רשום במאגר");
    }
  } catch {
    if (token !== pqToken) return;
    // כשל בהשלמה אינו "אין מגיש" - נאמר שלא נשלף.
    ids.forEach((id) => {
      const el = rowsEl.querySelector(`[data-qid="${id}"] .pq-asked`);
      if (el) el.textContent = "שם המגיש לא נשלף";
    });
  }
}

function pqPersonOf(rowsEl, id) {
  const el = rowsEl.querySelector(`[data-qid="${id}"]`);
  return el ? el.dataset.person : null;
}

document.getElementById("past-queries-btn").addEventListener("click", () => searchPastQueries());
document.getElementById("past-queries-input").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") searchPastQueries();
});
document.getElementById("bill-title-input").addEventListener("blur", (ev) => checkSimilarBills(ev.target.value));

/* ═══ שאלת מחקר ═══ (משימה 1.4)
 * מציג תמיד את המספרים הגולמיים ולא רק ניסוח, כדי שאפשר יהיה
 * לאמת. וכששאלה נופלת מחוץ לרפרטואר - אומרים את זה ומראים מה כן
 * אפשר לשאול, במקום להחזיר תשובה שנשמעת טוב ואינה נשענת על כלום. */
function renderResearchTable(data) {
  const headers = {
    knesset: "כנסת", total: "סה״כ הצעות", passed: "התקבלו", pass_rate_pct: "שיעור הצלחה",
    name: "שם", bills: "הצעות", title: "כותרת", kind: "סוג",
    became_law: "התקבל כחוק", published_at: "פורסם",
  };
  const cells = (r) =>
    data.columns
      .map((c) => {
        let v = r[c];
        if (typeof v === "boolean") v = v ? "כן" : "—";
        if (c === "pass_rate_pct") v = `${v}%`;
        if (c === "published_at" && v) v = formatHebrewDate(v);
        return `<td>${escapeHtml(String(v ?? "—"))}</td>`;
      })
      .join("");
  return `<table class="research-table">
      <thead><tr>${data.columns.map((c) => `<th>${escapeHtml(headers[c] || c)}</th>`).join("")}</tr></thead>
      <tbody>${data.rows.map((r) => `<tr>${cells(r)}</tr>`).join("")}</tbody>
    </table>`;
}

async function askResearch() {
  const input = document.getElementById("research-ask-input");
  const out = document.getElementById("research-ask-results");
  const question = input.value.trim();
  if (!question) return;

  input.disabled = true;
  out.innerHTML = "";
  const thinking = appendThinking(out, "מחפש בנתוני הכנסת…");
  try {
    const resp = await fetch("/api/research/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה בשאלה.")}</div>`;
      return;
    }
    const data = await resp.json();
    if (!data.answered) {
      const list = data.available.map((t) => `<li>${escapeHtml(t.title)}</li>`).join("");
      // שאלת תוכן שייכת לחיפוש הסמנטי שבאותה לשונית - מציעים מעבר
      // ישיר במקום להשאיר את המשתמש להבין לבד שיש שם תיבה שנייה.
      // מעבר לחיפוש הסמנטי הוסר יחד איתו (25.9.2026)
      const handoff = "";
      // **שתי סיבות שונות לאי-מענה, ולכן שתי הודעות שונות** (ברק,
      // 21.9.2026): "אין תבנית לנושא" לעומת "יש תבנית, אבל היא לא
      // יודעת להחיל את ההגבלה שביקשת". השנייה מציעה בכפתור את אותה
      // שאלה בלי ההגבלה - התשובה שהכלי כן יכול לתת באמת.
      const retry = data.answerable_instead
        ? `<button id="research-retry-btn" class="primary" style="margin-top:10px">
             שאל בלי ההגבלה: ${escapeHtml(data.answerable_instead)}</button>`
        : "";
      const headline = (data.unapplicable || []).length
        ? "לא אענה על שאלה אחרת מזו ששאלת."
        : "אין לי תבנית שאילתה לשאלה הזו.";
      out.innerHTML = `<div class="notice notice-coverage">
          <b>${headline}</b> ${escapeHtml(data.reason)}
          <br>מה כן אפשר לשאול כאן:<ul>${list}</ul>${retry}${retry && handoff ? " " : ""}${handoff}
        </div>`;
      const retryBtn = document.getElementById("research-retry-btn");
      if (retryBtn) {
        retryBtn.addEventListener("click", () => {
          const input = document.getElementById("research-ask-input");
          input.value = data.answerable_instead;
          askResearch();
        });
      }
      return;
    }
    out.innerHTML = `<div class="research-title">${escapeHtml(data.title)}</div>
      ${data.summary ? `<div class="hint">${escapeHtml(data.summary)}</div>` : ""}
      ${renderResearchTable(data)}`;
  } finally {
    thinking.remove();
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("research-ask-btn").addEventListener("click", askResearch);
document.getElementById("research-ask-input").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") askResearch();
});

/* ═══ תקציר הצעת חוק ═══ (משימה 2.1, המוצר הראשון)
 * מציג תמיד כמה שורות נוסח וכמה פסקאות הסבר נכנסו לתקציר, ואת
 * אזהרות החילוץ - כדי שיהיה אפשר להבחין בין "ההצעה קצרה" לבין
 * "החילוץ פספס". תקציר משכנע על חילוץ חלקי הוא התקלה המסוכנת כאן. */
async function generateSummary() {
  const input = document.getElementById("summary-file");
  const out = document.getElementById("summary-result");
  const file = input.files && input.files[0];
  if (!file) {
    out.innerHTML = `<div class="hint">בחרו קובץ Word תחילה.</div>`;
    return;
  }
  const btn = document.getElementById("summary-btn");
  btn.disabled = true;
  out.innerHTML = `<div class="law-loading"><span class="spinner"></span>קורא את המסמך ומסכם…</div>`;
  try {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch("/api/documents/summarize", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה בהפקת התקציר.")}</div>`;
      return;
    }
    const d = await resp.json();
    // א7 - **שינויים שטרם התקבלו הם פגם בקובץ, לא הערת חילוץ.**
    // Word מוסר ל-python-docx את ההוספות שטרם אושרו כאילו הן חלק
    // מהנוסח, ומשמיט את המחיקות שטרם אושרו כאילו כבר בוצעו - כלומר
    // המסמך נבדק כאילו כל השינויים התקבלו. הקובץ כן נקלט; השגיאה
    // מוצגת בראש, לפני הממצאים.
    const tc = d.tracked_changes || {};
    let tracked = "";
    if (tc.unknown) {
      tracked = `<div class="notice notice-coverage" style="margin-top:12px">
        <b>לא הצלחתי לבדוק אם יש במסמך שינויים שטרם התקבלו.</b>
        <b>זו אינה תשובה שאין כאלה</b> — הבדיקה לא רצה.</div>`;
    } else if (tc.total) {
      const kinds = Object.entries(tc.by_kind || {})
        .map(([k, n]) => `${k}: ${n}`).join(" · ");
      tracked = `<div class="notice notice-coverage" style="margin-top:12px">
        <b>זוהו שינויים שטרם התקבלו בפורמט עבודה של "עקוב אחר שינויים".</b>
        יש לקבל את כל השינויים בטרם הגשת הצעת החוק.
        <div class="hint" style="margin-top:6px">${escapeHtml(kinds)} —
        הבדיקה שלהלן רצה על הנוסח <b>כאילו כל השינויים כבר התקבלו</b>,
        וייתכן שהוא אינו הנוסח שבכוונתכם להגיש.</div></div>`;
    }

    const warn = d.warnings.length
      ? `<div class="notice notice-coverage" style="margin-top:12px"><b>אזהרות חילוץ:</b>
           <ul>${d.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul></div>`
      : "";
    out.innerHTML = `
      <div class="research-title">${escapeHtml(d.title || "(שם ההצעה לא זוהה)")}</div>
      <div class="citation-date">${escapeHtml(d.initiators.join(", ") || "מגיש לא זוהה")} ·
        ${d.lines_used} שורות נוסח · ${d.explanatory_used} פסקאות הסבר</div>
      <div class="summary-body">${escapeHtml(d.summary).replace(/\n/g, "<br>")}</div>
      ${warn}`;
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("summary-btn").addEventListener("click", generateSummary);

/* ═══ ביקורת ניסוח ═══ (משימה 2.2)
 * אזור נפרד מהתקציר בכוונה: התקציר אומר *מה ההצעה עושה*, הביקורת
 * אומרת *מה לא בסדר בניסוח*. ערבוב השניים היה קובר את הממצאים בתוך
 * פסקה - וזה בדיוק מה שהפיצ'ר הזה נועד למנוע.
 *
 * הממצא הדטרמיניסטי (message) מוצג תמיד, גם כשההסבר של המודל נכשל
 * או חסר. ליקוי אמיתי לא נעלם בגלל שהניסוח שלו לא חזר. */
async function runCritique() {
  const input = document.getElementById("critique-file");
  const out = document.getElementById("critique-result");
  const file = input.files && input.files[0];
  if (!file) {
    out.innerHTML = `<div class="hint">בחרו קובץ Word תחילה.</div>`;
    return;
  }
  const btn = document.getElementById("critique-btn");
  btn.disabled = true;
  out.innerHTML = `<div class="law-loading"><span class="spinner"></span>בודק את הניסוח…</div>`;
  try {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch("/api/documents/critique", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה בבדיקת הניסוח.")}</div>`;
      return;
    }
    const d = await resp.json();
    const head = `<div class="research-title">${escapeHtml(d.title || "(שם ההצעה לא זוהה)")}</div>
      <div class="citation-date">${d.checks_run.length} בדיקות הורצו ·
        ${d.passed.length} עברו · ${d.not_checked.length} לא נבדקו</div>`;

    let body;
    if (!d.findings.length) {
      body = `<div class="msg ok" style="margin-top:12px">לא נמצאו ליקויי ניסוח
        ב-${d.checks_run.length} הבדיקות שהורצו. זו קביעה של הקוד, לא של מודל.</div>`;
    } else {
      body = d.findings.map((f) => `
        <div class="critique-item critique-${f.status === "אזהרה" ? "warn" : "fail"}">
          <div class="critique-head">
            <span class="critique-badge">${escapeHtml(critiqueStatusLabel(f.status))}</span>
            <b>${escapeHtml(f.what || f.description)}</b>
          </div>
          ${f.why ? `<div class="critique-why">${escapeHtml(f.why)}</div>` : ""}
          ${f.fix ? `<div class="critique-fix"><b>מה לעשות:</b> ${escapeHtml(f.fix)}</div>` : ""}
          <div class="critique-raw">${escapeHtml(f.message)}</div>
        </div>`).join("");
      if (d.dropped_explanations && d.dropped_explanations.length) {
        body += `<div class="notice notice-coverage" style="margin-top:12px">
          ההסבר ל-${d.dropped_explanations.length} ממצאים נדחה כי הצביע על מקום
          שהממצא עצמו לא נקב בו — הממצא עצמו מוצג בלעדיו.</div>`;
      }
      if (!d.explained) {
        body += `<div class="notice notice-coverage" style="margin-top:12px">
          ההסבר בשפה חופשית לא נוצר${d.explain_error ? ` (${escapeHtml(d.explain_error)})` : ""} —
          הממצאים עצמם מוצגים במלואם כפי שנקבעו בקוד.</div>`;
      }
    }

    // **הסיבה לכל בדיקה שלא הורצה מוצגת, לא רק כמה היו.** מאז
    // שבדיקת מספרי הסעיפים רצה מול החוק שבמאגר, הסיבה תלויה במסמך
    // ("החוק X אינו במאגר") - ובלעדיה המשתמש לא יודע מה חסר.
    const reasons = d.not_checked_reasons || [];
    const skipped = d.not_checked.length
      ? `<details class="critique-skipped"><summary>${d.not_checked.length} בדיקות לא הורצו על המסמך הזה</summary>
           ${reasons.length
             ? `<ul class="hint">${reasons.map((r) =>
                 `<li>${escapeHtml(r.description)} — ${escapeHtml(r.message)}</li>`).join("")}</ul>`
             : `<div class="hint">חלקן דורשות מידע שאינו נמצא במסמך עצמו, וחלקן
                אינן רלוונטיות לסוג ההצעה.</div>`}
         </details>`
      : "";

    // א7 - **שינויים שטרם התקבלו הם פגם בקובץ, לא הערת חילוץ.**
    // Word מוסר ל-python-docx את ההוספות שטרם אושרו כאילו הן חלק
    // מהנוסח, ומשמיט את המחיקות שטרם אושרו כאילו כבר בוצעו - כלומר
    // המסמך נבדק כאילו כל השינויים התקבלו. הקובץ כן נקלט; השגיאה
    // מוצגת בראש, לפני הממצאים.
    const tc = d.tracked_changes || {};
    let tracked = "";
    if (tc.unknown) {
      tracked = `<div class="notice notice-coverage" style="margin-top:12px">
        <b>לא הצלחתי לבדוק אם יש במסמך שינויים שטרם התקבלו.</b>
        <b>זו אינה תשובה שאין כאלה</b> — הבדיקה לא רצה.</div>`;
    } else if (tc.total) {
      const kinds = Object.entries(tc.by_kind || {})
        .map(([k, n]) => `${k}: ${n}`).join(" · ");
      tracked = `<div class="notice notice-coverage" style="margin-top:12px">
        <b>זוהו שינויים שטרם התקבלו בפורמט עבודה של "עקוב אחר שינויים".</b>
        יש לקבל את כל השינויים בטרם הגשת הצעת החוק.
        <div class="hint" style="margin-top:6px">${escapeHtml(kinds)} —
        הבדיקה שלהלן רצה על הנוסח <b>כאילו כל השינויים כבר התקבלו</b>,
        וייתכן שהוא אינו הנוסח שבכוונתכם להגיש.</div></div>`;
    }

    const warn = d.warnings.length
      ? `<div class="notice notice-coverage" style="margin-top:12px"><b>אזהרות חילוץ:</b>
           <ul>${d.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul></div>`
      : "";

    // התראת 'עקוב אחר שינויים' לפני הממצאים: היא משנה את
    // המשמעות של כל מה שמתחתיה.
    out.innerHTML = head + tracked + body + skipped + warn;
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("critique-btn").addEventListener("click", runCritique);

// א8 - אזור גרירה במקום כפתור "בחר קובץ" האפור. אותו אזור בתקציר
// ובבודק הניסוח; ה-input נשאר (גרירה לבדה אינה נגישה במקלדת).
function wireDropzone(zoneId, inputId, pickId, nameId) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;
  const nameEl = document.getElementById(nameId);
  const show = () => {
    const f = input.files && input.files[0];
    nameEl.textContent = f ? f.name : ".docx בלבד";
    zone.classList.toggle("has-file", Boolean(f));
  };
  document.getElementById(pickId).addEventListener("click", () => input.click());
  zone.addEventListener("click", (ev) => { if (ev.target === zone) input.click(); });
  input.addEventListener("change", show);
  ["dragenter", "dragover"].forEach((e) =>
    zone.addEventListener(e, (ev) => { ev.preventDefault(); zone.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((e) =>
    zone.addEventListener(e, (ev) => { ev.preventDefault(); zone.classList.remove("is-over"); }));
  zone.addEventListener("drop", (ev) => {
    const f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
    if (!f) return;
    // **הסוג נבדק כאן ולא רק בשרת** - גרירת PDF והמתנה לשגיאה
    // מהשרת היא מסע מיותר.
    if (!f.name.toLowerCase().endsWith(".docx")) {
      nameEl.textContent = `${f.name} — נתמך .docx בלבד`;
      zone.classList.add("has-error");
      return;
    }
    zone.classList.remove("has-error");
    const dt = new DataTransfer();
    dt.items.add(f);
    input.files = dt.files;
    show();
  });
  show();
}
wireDropzone("summary-drop", "summary-file", "summary-pick", "summary-name");
wireDropzone("critique-drop", "critique-file", "critique-pick", "critique-name");

// א4 - **"נכשל" הוא מונח של מריץ בדיקות, לא של מי שכתב הצעת חוק.**
// החיווי האדום נשאר; רק המילה משתנה.
function critiqueStatusLabel(status) {
  if (status === "נכשל") return "זוהתה שגיאת ניסוח";
  return status;
}

/* ═══ הסתייגויות ═══ (2026-09-18)
 * שני המספרים מוצגים תמיד יחד ולעולם לא לחוד: "עד N הסתייגויות,
 * מתוכן כ-M מובחנות". N לבדו מטעה - 400 וריאציות על אותו תאריך
 * נראות כמו 400 רעיונות. ראו generate.measure להגדרת "מובחן". */
function resSections(d) {
  return d.per_section.map((s) => `
    <tr><td>${escapeHtml(s.section)}</td><td>${s.anchors}</td>
    <td>${escapeHtml((s.anchor_values || []).join(", "))}</td></tr>`).join("");
}

// אזהרות חילוץ, בראש התוצאה ולא בתחתיתה. **הן קריטיות בלשונית
// הזו:** ההצעה 13948363 איבדה חצי מעצמה בשקט לפני התיקון של
// 2026-09-19, ומה שהמשתמש ראה היה תוצאה שנראית תקינה לגמרי.
function extractionWarnings(d) {
  if (!d.warnings || !d.warnings.length) return "";
  return `<div class="notice notice-coverage" style="margin-bottom:12px">
    <b>שימו לב — החילוץ מהמסמך אינו ודאי:</b>
    <ul>${d.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul></div>`;
}

async function measureReservations() {
  const input = document.getElementById("res-file");
  const out = document.getElementById("res-result");
  const file = input.files && input.files[0];
  if (!file) { out.innerHTML = `<div class="hint">בחרו קובץ Word תחילה.</div>`; return; }
  const btn = document.getElementById("res-measure-btn");
  btn.disabled = true;
  out.innerHTML = `<div class="law-loading"><span class="spinner"></span>מודד…</div>`;
  try {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch("/api/reservations/analyze", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה במדידה.")}</div>`;
      return;
    }
    const d = await resp.json();
    out.innerHTML = `
      ${extractionWarnings(d)}
      <div class="research-title">${escapeHtml(d.title || "(שם ההצעה לא זוהה)")}</div>
      <div class="res-headline"><b>${d.distinct}</b> עוגנים מובחנים</div>
      <div class="hint">${d.sections_found} סעיפים נמדדו. "עוגן מובחן" = ערך
        בהצעה שאפשר לשנות. אין כאן "כמה הסתייגויות אפשר לייצר" - המספר הזה
        תלוי בתקרה שתבחרו ואינו מדידה של ההצעה.</div>
      <div class="hint" style="margin-top:8px">מצב האיכות על ההצעה הזו:
        <b>${d.quality_calls}</b> קריאות למודל (אחת לסעיף),
        <b>${d.quality_points}</b> נקודות עיגון.</div>
      <table class="res-table"><thead><tr><th>סעיף</th><th>עוגנים מובחנים</th>
        <th>הערכים</th></tr></thead><tbody>${resSections(d)}</tbody></table>`;
  } finally { btn.disabled = false; }
}

async function generateReservations() {
  const input = document.getElementById("res-file");
  const out = document.getElementById("res-result");
  const file = input.files && input.files[0];
  if (!file) { out.innerHTML = `<div class="hint">בחרו קובץ Word תחילה.</div>`; return; }
  const btn = document.getElementById("res-generate-btn");
  btn.disabled = true;
  try {
    const form = new FormData();
    form.append("file", file);
    form.append("proposers", document.getElementById("res-proposers").value || "");
    const resp = await fetch("/api/reservations/generate", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה בהפקה.")}</div>`;
      return;
    }
    const warnCount = parseInt(resp.headers.get("X-Extraction-Warnings") || "0", 10);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "הסתייגויות.docx"; a.click();
    URL.revokeObjectURL(url);
    // הורדה שקטה מסתירה אזהרת חילוץ. אם יש - אומרים, ומפנים למדידה.
    out.innerHTML = warnCount
      ? `<div class="notice notice-coverage"><b>המסמך הופק, אבל החילוץ אינו ודאי
           (${warnCount} אזהרות).</b> לחצו "מדידה" כדי לראות אותן לפני ההגשה.</div>`
      : `<div class="hint">המסמך הופק.</div>`;
  } finally { btn.disabled = false; }
}

async function qualityReservations() {
  const input = document.getElementById("res-file");
  const out = document.getElementById("res-result");
  const file = input.files && input.files[0];
  if (!file) { out.innerHTML = `<div class="hint">בחרו קובץ Word תחילה.</div>`; return; }
  const btn = document.getElementById("res-quality-btn");
  const limit = parseInt(document.getElementById("res-quality-limit").value, 10) || 0;
  btn.disabled = true;
  out.innerHTML = `<div class="law-loading"><span class="spinner"></span>מנסח…</div>`;
  try {
    const form = new FormData();
    form.append("file", file);
    form.append("sections_limit", String(limit));
    const resp = await fetch("/api/reservations/quality", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה בניסוח.")}</div>`;
      return;
    }
    const d = await resp.json();
    const u = d.usage || {};
    // מה שנחסם אינו מוצג - רק נספר. ראו CLAUDE.md חוק ברזל 7.
    const blocked = d.blocked_count
      ? `<div class="hint">${d.blocked_count} ניסוחים נחסמו בשומרים ואינם מוצגים.</div>`
      : "";
    out.innerHTML = `
      ${extractionWarnings(d)}
      <div class="research-title">${escapeHtml(d.title || "(שם ההצעה לא זוהה)")}</div>
      <div class="res-headline"><b>${d.passed.length}</b> הסתייגויות מהותיות,
        מתוך ${d.sections_used} סעיפים</div>
      ${blocked}
      <div class="hint">עלות בפועל: ${u.drafting_calls} קריאות ניסוח +
        ${u.screening_calls} קריאות סינון,
        ${(u.input_tokens || 0).toLocaleString()} טוקני קלט,
        ${(u.output_tokens || 0).toLocaleString()} טוקני פלט (${escapeHtml(u.model || "")}).</div>
      <table class="res-table"><thead><tr><th>סעיף</th><th>ההסתייגות</th>
        <th>נימוק</th></tr></thead><tbody>${d.passed.map((r) => `
        <tr><td>${escapeHtml(r.section_number)}</td>
            <td>${escapeHtml(r.text)}</td>
            <td>${escapeHtml(r.rationale || "")}</td></tr>`).join("")}</tbody></table>`;
  } finally { btn.disabled = false; }
}
document.getElementById("res-measure-btn").addEventListener("click", measureReservations);
document.getElementById("res-generate-btn").addEventListener("click", generateReservations);
document.getElementById("res-quality-btn").addEventListener("click", qualityReservations);

/* ── נוסח משולב ─────────────────────────────────────────────────
   מעלים הצעת חוק מתקנת, ורואים את נוסח החוק אחרי שהיא התקבלה.
   הכול דטרמיניסטי בצד השרת; כאן רק תצוגה.

   **הצגה של דחייה חשובה כמו הצגה של הצלחה**: כשהשרת עוצר, הסיבה
   שלו מוצגת כלשונה ולא מוחלפת בהודעה כללית - היא נוסחה בדיוק כדי
   שהמשתמש יבין מה למד המערכת ולמה לא המשיכה. */
const MERGE_KIND_LABEL = {
  insert: "יחידה חדשה",
  replace: "החלפת מילים",
  append: "הוספה בסוף",
  relabel: "מספור מחדש",
};

function mergeNodeHtml(node, changesById) {
  const change = changesById.get(node.id);
  const label = node.number ? `<span class="merge-label">${escapeHtml(node.number)}</span> ` : "";
  const text = escapeHtml(node.text || "");
  let body = "";
  if (node.number || (node.text || "").trim()) {
    const cls = change ? ` merge-added` : "";
    const attr = change ? ` data-change="${escapeHtml(node.id)}" role="button" tabindex="0"` : "";
    body = `<div class="merge-line${cls}"${attr}>${label}${text}</div>`;
  }
  const kids = (node.children || []).map((c) => mergeNodeHtml(c, changesById)).join("");
  return body + (kids ? `<div class="merge-children">${kids}</div>` : "");
}

async function buildMergedText() {
  const out = document.getElementById("merge-result");
  const input = document.getElementById("merge-file");
  const file = input.files && input.files[0];
  if (!file) {
    out.innerHTML = `<div class="msg err">בחר קובץ Word של הצעת חוק מתקנת.</div>`;
    return;
  }
  const btn = document.getElementById("merge-btn");
  btn.disabled = true;
  out.innerHTML = `<div class="law-loading"><span class="spinner"></span>בונה נוסח משולב…</div>`;
  try {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch("/api/merge/build", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה בבניית הנוסח המשולב.")}</div>`;
      return;
    }
    const d = await resp.json();
    const head = `<div class="research-title">${escapeHtml(d.bill_title || "(שם ההצעה לא זוהה)")}</div>`;

    if (!d.ok) {
      // הסיבה כלשונה מהשרת. "כמה חוקים" מקבל גם את רשימת החוקים,
      // ו"הוראות שלא זוהו" מקבל את השורות עצמן - כדי שהמשתמש יראה
      // בדיוק איפה נעצרתי ולא רק שנעצרתי.
      let extra = "";
      if ((d.extra_laws || []).length) {
        extra = `<div class="merge-detail"><b>החוקים שזוהו בהצעה:</b><ul>` +
          d.extra_laws.map((n) => `<li>${escapeHtml(n)}</li>`).join("") + `</ul></div>`;
      }
      if ((d.unparsed || []).length) {
        extra += `<div class="merge-detail"><b>ההוראות שלא זוהו:</b><ul>` +
          d.unparsed.map((t) => `<li>${escapeHtml(t)}</li>`).join("") + `</ul></div>`;
      }
      out.innerHTML = head +
        `<div class="msg err" style="margin-top:12px">${escapeHtml(d.reason || "המיזוג נעצר.")}</div>` +
        extra;
      return;
    }

    const changesById = new Map((d.changes || []).map((c) => [c.node_id, c]));
    const summary = (d.changes || []).map((c, i) => `
      <li data-jump="${escapeHtml(c.node_id)}">
        <b>${escapeHtml(MERGE_KIND_LABEL[c.kind] || c.kind)}</b>
        ${c.label ? `<span class="merge-label">${escapeHtml(c.label)}</span>` : ""}
        <div class="merge-instruction">${escapeHtml(c.instruction_number || "")} ${escapeHtml(c.instruction)}</div>
      </li>`).join("");

    out.innerHTML = head +
      `<div class="citation-date">${escapeHtml(d.law_title || "")}${d.as_of ? " · " + escapeHtml(d.as_of) : ""}</div>
       <div class="msg ok" style="margin-top:12px">${d.changes.length} שינויים הוחלו. כל ההוראות בהצעה זוהו והוחלו — אין מיזוג חלקי.</div>
       <div class="merge-legend"><span class="merge-swatch"></span> נוסף על ידי ההצעה · לחיצה על שינוי מציגה את ההוראה שיצרה אותו</div>
       <ol class="merge-changes">${summary}</ol>
       <div class="merge-tree" id="merge-tree">${mergeNodeHtml(d.tree, changesById)}</div>`;

    const showChange = (nodeId) => {
      const c = changesById.get(nodeId);
      if (!c) return;
      document.querySelectorAll("#merge-result .merge-line.is-open").forEach((el) => {
        el.classList.remove("is-open");
        const note = el.querySelector(".merge-source");
        if (note) note.remove();
      });
      const line = document.querySelector(`#merge-result [data-change="${CSS.escape(nodeId)}"]`);
      if (!line) return;
      line.classList.add("is-open");
      const note = document.createElement("div");
      note.className = "merge-source";
      note.innerHTML = `<b>ההוראה שיצרה את השינוי:</b> ${escapeHtml(c.instruction_number || "")} ${escapeHtml(c.instruction)}`;
      line.appendChild(note);
      line.scrollIntoView({ behavior: "smooth", block: "center" });
    };

    out.querySelectorAll("[data-change]").forEach((el) => {
      el.addEventListener("click", () => showChange(el.dataset.change));
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); showChange(el.dataset.change); }
      });
    });
    out.querySelectorAll("[data-jump]").forEach((el) => {
      el.addEventListener("click", () => showChange(el.dataset.jump));
    });
  } catch (e) {
    out.innerHTML = `<div class="msg err">שגיאת רשת: ${escapeHtml(String(e))}</div>`;
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("merge-btn").addEventListener("click", buildMergedText);
