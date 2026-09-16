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

    if (node.node_type === "section") {
      const titleSpan = document.createElement("span");
      titleSpan.className = "node-margin-title";
      titleSpan.contentEditable = "true";
      titleSpan.dataset.nodeId = node.id;
      titleSpan.dataset.field = "margin_title";
      titleSpan.textContent = node.margin_title || "";
      titleSpan.dataset.plainValue = node.margin_title || "";
      titleSpan.addEventListener("focus", onFieldFocus);
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

async function onFieldBlur(ev) {
  const el = ev.target;
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
    await refreshPreview();
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
