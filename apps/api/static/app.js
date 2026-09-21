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
  return {
    title: document.getElementById("bill-title-input").value,
    initiator: document.getElementById("bill-initiator-input").value,
    explanatory: document
      .getElementById("explanatory-input")
      .value.split("\n")
      .map((s) => s.trim())
      .filter((s) => s),
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
    } else if (!law.freshness_checked_at) {
      const unknown = document.createElement("span");
      unknown.className = "law-result-note";
      unknown.textContent = "(עדכניות לא נבדקה)";
      item.appendChild(unknown);
    }
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

function selectLaw(law) {
  if (!law.amendable) return;
  document.getElementById("law-search-input").value = law.title;
  document.getElementById("law-search-results").hidden = true;
  onLawChange(law.id);
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
    buildOriginalIndex(law.tree);
    loadCitations(lawId);  // לא await: הפיד חיצוני, אסור שיעכב את הצגת החוק

    document.getElementById("law-panels").hidden = false;
    document.getElementById("as-of-note").textContent = law.as_of_display || "";
    document.getElementById("source-ref-note").textContent = law.known_source_ref
      ? `מראה מקום: ${law.known_source_ref}`
      : "מראה מקום: לא ידוע לחוק זה - הוולידטור יתריע (בדיקה 2).";

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
    header.appendChild(numberSpan);

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

    const notEditable = node.node_type === "section" && node.editable === false;
    if (notEditable) {
      wrapper.classList.add("not-editable");
      const badge = document.createElement("span");
      badge.className = "not-editable-badge";
      badge.textContent = "לא ניתן לעריכה";
      badge.title = "לסעיף הזה אין מספר במקור, ולכן המערכת אינה יכולה " +
        "לנסח עליו הוראת תיקון. הנוסח מוצג לקריאה בלבד.";
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

    wrapper.appendChild(header);

    const bodyRow = document.createElement("div");
    bodyRow.className = "node-body-row";

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
      addBtn.title = "הוספת תוכן חדש אחרי צומת זה";
      addBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        toggleInsertMenu(node, wrapper);
      });
      bodyRow.appendChild(addBtn);
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
  fieldElements = {};
  const treeContainer = document.getElementById("law-tree");
  treeContainer.innerHTML = "";
  treeContainer.appendChild(renderNode(tree, 0));
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

async function refreshPreview() {
  if (!currentLawId) return;
  const myGeneration = ++renderGeneration;
  const req = { edits: editsPayload(), insertions: insertionsPayload(), bill: billMeta() };
  const resp = await fetch(`/api/laws/${currentLawId}/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  const data = await resp.json();
  // תשובה ישנה שנחסמה על ידי בקשה מאוחרת יותר (למשל: המשתמש כבר
  // המשיך לערוך ושלח בקשה נוספת לפני שזו חזרה) - לא נוגעים ב-DOM.
  if (myGeneration !== renderGeneration) return;

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
  renderDocxApprox(data.lines);
  document.getElementById("download-hint").textContent = data.insertion_errors.length
    ? `שים לב: ${data.insertion_errors.length} הוספות לא בוצעו (ראו כרטיסי השגיאה בעץ)`
    : "";
}

function renderDocxApprox(lines) {
  document.getElementById("docx-title-line").textContent = billMeta().title;
  document.getElementById("docx-initiator-line").textContent = "יוזם: " + billMeta().initiator;
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
  submitBtn.onclick = async () => {
    if (level === "section" && !titleInput.value.trim()) {
      titleInput.focus();
      return;
    }
    if (!textInput.value.trim()) {
      textInput.focus();
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

for (const inputId of ["bill-title-input", "bill-initiator-input"]) {
  document.getElementById(inputId).addEventListener("blur", refreshPreview);
}
document.getElementById("explanatory-input").addEventListener("blur", refreshPreview);

initLawSearch();

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
function appendMsg(container, cls, html) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.innerHTML = html;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

function wordCountHtml(wordCount, wordLimit) {
  if (wordLimit == null) return `<div class="word-count">${wordCount} מילים (בלי הגבלה)</div>`;
  const over = wordCount > wordLimit;
  return `<div class="word-count${over ? " over" : ""}">${wordCount}/${wordLimit} מילים${over ? " - חורג מהמגבלה!" : ""}</div>`;
}

// --- שאילתות ---
let queryTopicHistory = [];
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
  queryTopicHistory.push(text);
  input.value = "";
  input.disabled = true;

  try {
    const resp = await fetch("/api/query/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic_description: queryTopicHistory.join("\n"),
        kind,
        minister,
        mk_name: mkName,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      appendMsg(chat, "err", escapeHtml(err.detail || "שגיאה בניסוח השאילתה."));
      return;
    }
    currentQueryDraft = await resp.json();
    document.getElementById("query-export-btn").disabled = false;
    appendMsg(
      chat,
      "a",
      `ניסחתי טיוטה לפי הפורמט המקובל.` +
        `<div class="draft"><div class="to">שאילתה ${escapeHtml(currentQueryDraft.kind)} ${escapeHtml(minister)}</div>` +
        `${escapeHtml(currentQueryDraft.body)}${wordCountHtml(currentQueryDraft.word_count, currentQueryDraft.word_limit)}${currentQueryDraft.removed_addressee ? `<div class="word-count">הוסרה פנייה לנמען מתחילת הגוף (${escapeHtml(currentQueryDraft.removed_addressee)}) — הנמען נקבע בשדה ומוזרק למסמך</div>` : ""}</div>`
    );
  } finally {
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("query-send-btn").addEventListener("click", sendQueryMessage);
document.getElementById("query-composer-input").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") sendQueryMessage();
});

document.getElementById("query-export-btn").addEventListener("click", async () => {
  if (!currentQueryDraft) return;
  const resp = await fetch("/api/query/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentQueryDraft),
  });
  if (!resp.ok) return;
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "שאילתה.docx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

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
    currentAgendaDraft = await resp.json();
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
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("agenda-send-btn").addEventListener("click", sendAgendaMessage);
document.getElementById("agenda-composer-input").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") sendAgendaMessage();
});

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

// --- מומחה התקנון (ברק, 2026-09-17) ---
async function sendRulesMessage() {
  const input = document.getElementById("rules-composer-input");
  const text = input.value.trim();
  if (!text) return;
  const chat = document.getElementById("rules-chat");

  appendMsg(chat, "u", escapeHtml(text));
  input.value = "";
  input.disabled = true;

  try {
    const resp = await fetch("/api/rules/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      appendMsg(chat, "err", escapeHtml(err.detail || "שגיאה במענה."));
      return;
    }
    const result = await resp.json();
    if (result.refused) {
      appendMsg(chat, "a", `לא ניתן לענות על סמך תקנון הכנסת/חוק הכנסת/חוק-יסוד: הכנסת בלבד.<br><span style="color:var(--soft);font-size:12.5px">${escapeHtml(result.refusal_reason || "")}</span>`);
      return;
    }
    const citedHtml = result.cited_source_ids.length
      ? `<div class="word-count">מקורות: ${result.cited_source_ids.map(escapeHtml).join(", ")}</div>`
      : "";
    appendMsg(chat, "a", `${escapeHtml(result.text)}${citedHtml}`);
  } finally {
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("rules-send-btn").addEventListener("click", sendRulesMessage);
document.getElementById("rules-composer-input").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") sendRulesMessage();
});

/* ═══ מחקר: חיפוש סמנטי בחקיקה ═══ (ברק, 2026-09-17)
 * הדרישה המרכזית כאן היא לא החיפוש עצמו אלא **ההבחנה**: משתמש
 * שמקבל מסך ריק חייב לדעת אם אין תוצאה, או שהחוק הרלוונטי פשוט לא
 * מאונדקס (67 מתוך 1,094 - מגבלת Free tier, ראו
 * docs/indexing-priority-250.md). השרת מחזיר coverage בכל תשובה
 * ואנחנו מרנדרים את ההבדל במפורש, לא כהערת-שוליים. */
function renderCoverageBadge(coverage) {
  const badge = document.getElementById("coverage-badge");
  badge.textContent = `מאונדקסים לחיפוש סמנטי: ${coverage.indexed_laws} מתוך ${coverage.total_laws} חוקים`;
  badge.hidden = false;
}

function unindexedNoticeHtml(coverage) {
  if (!coverage.unindexed_name_matches.length) return "";
  const items = coverage.unindexed_name_matches
    .map((m) => `<li>${escapeHtml(m.title)}</li>`)
    .join("");
  return `<div class="notice notice-coverage">
      <b>שימו לב - מגבלת כיסוי, לא היעדר תוצאה.</b>
      החוקים הבאים תואמים את החיפוש בשמם, אך אינם מאונדקסים לחיפוש סמנטי
      (${coverage.indexed_laws} מתוך ${coverage.total_laws} חוקים מאונדקסים בשלב זה):
      <ul>${items}</ul>
      אפשר לפתוח אותם ישירות בלשונית "הצעות חוק" ולעבוד על הנוסח המלא.
    </div>`;
}

async function runResearchSearch() {
  const input = document.getElementById("research-input");
  const out = document.getElementById("research-results");
  const text = input.value.trim();
  if (!text) return;

  input.disabled = true;
  out.innerHTML = `<div class="law-loading"><span class="spinner"></span>מחפש…</div>`;
  try {
    const resp = await fetch(`/api/semantic-search?q=${encodeURIComponent(text)}&limit=10`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      out.innerHTML = `<div class="msg err">${escapeHtml(err.detail || "שגיאה בחיפוש.")}</div>`;
      return;
    }
    const { results, coverage } = await resp.json();
    renderCoverageBadge(coverage);

    if (!results.length) {
      // שתי ההודעות השונות - זו כל הנקודה של הדרישה.
      out.innerHTML = coverage.unindexed_name_matches.length
        ? unindexedNoticeHtml(coverage)
        : `<div class="notice">לא נמצאו סעיפים מתאימים בקרב ${coverage.indexed_laws} החוקים המאונדקסים.
             לא נמצא גם חוק ששמו תואם את החיפוש - כלומר זו כנראה באמת היעדר תוצאה, לא מגבלת כיסוי.</div>`;
      return;
    }

    const cards = results
      .map(
        (r) => `<div class="result">
            <div class="result-head">${escapeHtml(r.context_prefix)}</div>
            <div class="result-body">${escapeHtml(r.body.slice(0, 600))}${r.body.length > 600 ? "…" : ""}</div>
            <div class="word-count">${escapeHtml(r.law_id)} · סעיף ${escapeHtml(r.section_number)} ·
              דמיון סמנטי ${(r.semantic_similarity ?? 0).toFixed(3)}${
                r.full_text_rank ? "" : " (התאמה לפי משמעות בלבד, בלי מילים משותפות)"
              }</div>
          </div>`
      )
      .join("");
    out.innerHTML = unindexedNoticeHtml(coverage) + cards;
  } finally {
    input.disabled = false;
    input.focus();
  }
}

document.getElementById("research-send-btn").addEventListener("click", runResearchSearch);
document.getElementById("research-input").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") runResearchSearch();
});

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
  body.innerHTML = `<div class="hint">טוען מראי מקום…</div>`;
  try {
    const resp = await fetch(`/api/laws/${encodeURIComponent(lawId)}/citations`);
    if (!resp.ok) throw new Error("feed");
    const data = await resp.json();
    const summary = box.querySelector("summary");
    if (!data.in_knesset_db) {
      // ההבחנה בין "אין תיקונים" ל"לא קיים במאגר" - ופתוח כברירת
      // מחדל, אחרת ההסבר חבוי מאחורי אקורדיון מקופל ונראה כמו כלום.
      summary.textContent = "מראי מקום מהכנסת — אין רשומה";
      box.open = true;
      body.innerHTML = `<div class="hint">${escapeHtml(data.note || "אין רשומה במאגר הכנסת.")}</div>`;
      return;
    }
    summary.textContent = `מראי מקום מהכנסת (${data.citations.length})`;
    box.open = false;
    const rows = data.citations
      .map((c) => `<div class="citation-row">
          <b>${c.is_original ? "הפרסום המקורי" : escapeHtml(c.kind || "תיקון")}</b>
          <span class="citation-ref">${escapeHtml(c.reference)}</span>
          <span class="citation-date">${escapeHtml(c.published_at || "")}</span>
          <div class="citation-title">${escapeHtml(c.title || "")}</div>
        </div>`)
      .join("");
    body.innerHTML = rows || `<div class="hint">לא נמצאו מראי מקום.</div>`;
  } catch {
    body.innerHTML = `<div class="hint">מאגר הכנסת אינו זמין כרגע.</div>`;
  }
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
      .map((b) => `<li>${escapeHtml(b.title)}
          <span class="citation-date">כנסת ${b.knesset}${b.became_law ? " · התקבל כחוק" : ""}</span></li>`)
      .join("");
    el.innerHTML = `<div class="notice notice-coverage">
        <b>נמצאו הצעות דומות בשמן (${data.results.length}).</b>
        החוברת הסגולה מחייבת לבדוק הצעות זהות או דומות לפני הנחה.
        <ul>${items}</ul>
        <span class="citation-date">${escapeHtml(data.note)}</span>
      </div>`;
  } catch {
    el.innerHTML = "";  // הפיד לא זמין - לא מציקים למשתמש, הכלי ממשיך לעבוד
  }
}

async function searchPastQueries() {
  const input = document.getElementById("past-queries-input");
  const out = document.getElementById("past-queries-results");
  const q = input.value.trim();
  if (!q) return;
  out.innerHTML = `<div class="hint">מחפש…</div>`;
  try {
    const resp = await fetch(`/api/queries/search?q=${encodeURIComponent(q)}&limit=12`);
    if (!resp.ok) throw new Error("feed");
    const data = await resp.json();
    if (!data.results.length) {
      out.innerHTML = `<div class="hint">לא נמצאו שאילתות קודמות בנושא הזה.</div>`;
      return;
    }
    out.innerHTML = data.results
      .map((r) => {
        // קישור לקובץ המקורי באתר הכנסת; לא מושכים אותו - ראו
        // knesset_queries.py. נפתח בלשונית חדשה כדי לא לאבד את הטיוטה.
        const title = r.document_url
          ? `<a href="${escapeHtml(r.document_url)}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a>`
          : escapeHtml(r.title);
        return `<div class="citation-row">
            <div class="citation-title">${title}</div>
            <span class="citation-date">${escapeHtml(r.kind || "")} · כנסת ${r.knesset} ·
              ${escapeHtml(r.submitted_at || "")} · ${escapeHtml(r.asked_by || "לא ידוע")}</span>
          </div>`;
      })
      .join("");
  } catch {
    out.innerHTML = `<div class="hint">מאגר הכנסת אינו זמין כרגע.</div>`;
  }
}

document.getElementById("past-queries-btn").addEventListener("click", searchPastQueries);
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
  out.innerHTML = `<div class="law-loading"><span class="spinner"></span>מנתח את השאלה…</div>`;
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
      const handoff = data.try_semantic_search
        ? `<button id="research-handoff-btn" class="primary" style="margin-top:10px">
             חפשו את זה בחיפוש הסמנטי</button>`
        : "";
      out.innerHTML = `<div class="notice notice-coverage">
          <b>אין לי תבנית שאילתה לשאלה הזו.</b> ${escapeHtml(data.reason)}
          <br>מה כן אפשר לשאול כאן:<ul>${list}</ul>${handoff}
        </div>`;
      const btn = document.getElementById("research-handoff-btn");
      if (btn) {
        btn.addEventListener("click", () => {
          document.getElementById("research-input").value = data.question;
          runResearchSearch();
          document.getElementById("research-input").scrollIntoView({ behavior: "smooth", block: "center" });
        });
      }
      return;
    }
    out.innerHTML = `<div class="research-title">${escapeHtml(data.title)}</div>
      ${data.summary ? `<div class="hint">${escapeHtml(data.summary)}</div>` : ""}
      ${renderResearchTable(data)}`;
  } finally {
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
      body = `<div class="msg ok" style="margin-top:12px">לא נמצאו ליקויים בבדיקות שהורצו
        (${d.checks_run.join(", ")}). זו קביעה של הקוד, לא של מודל.</div>`;
    } else {
      body = d.findings.map((f) => `
        <div class="critique-item critique-${f.status === "אזהרה" ? "warn" : "fail"}">
          <div class="critique-head">
            <span class="critique-badge">${escapeHtml(f.status)}</span>
            <b>${escapeHtml(f.what || f.description)}</b>
          </div>
          ${f.why ? `<div class="critique-why">${escapeHtml(f.why)}</div>` : ""}
          ${f.fix ? `<div class="critique-fix"><b>מה לעשות:</b> ${escapeHtml(f.fix)}</div>` : ""}
          <div class="critique-raw">בדיקה ${f.check} — ${escapeHtml(f.message)}</div>
        </div>`).join("");
      if (d.dropped_explanations && d.dropped_explanations.length) {
        body += `<div class="notice notice-coverage" style="margin-top:12px">
          ההסבר לבדיקות ${d.dropped_explanations.join(", ")} נדחה כי הצביע על מקום
          שהממצא עצמו לא נקב בו — הממצא הדטרמיניסטי מוצג בלעדיו.</div>`;
      }
      if (!d.explained) {
        body += `<div class="notice notice-coverage" style="margin-top:12px">
          ההסבר בשפה חופשית לא נוצר${d.explain_error ? ` (${escapeHtml(d.explain_error)})` : ""} —
          הממצאים עצמם מוצגים במלואם כפי שנקבעו בקוד.</div>`;
      }
    }

    const skipped = d.not_checked.length
      ? `<details class="critique-skipped"><summary>${d.not_checked.length} בדיקות לא הורצו על המסמך הזה</summary>
           <div class="hint">בדיקות ${d.not_checked.join(", ")} דורשות מידע שאין במסמך חיצוני
           (החוק המתוקן, הרפרנסים, ה-docx שהמערכת הפיקה) או שידוע שהן שגויות
           על הצעות אמיתיות וממתינות לתיקון.</div></details>`
      : "";

    const warn = d.warnings.length
      ? `<div class="notice notice-coverage" style="margin-top:12px"><b>אזהרות חילוץ:</b>
           <ul>${d.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul></div>`
      : "";

    out.innerHTML = head + body + skipped + warn;
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("critique-btn").addEventListener("click", runCritique);

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
