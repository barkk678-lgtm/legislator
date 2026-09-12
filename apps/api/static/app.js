"use strict";
/* לקוח משימה 10ב: עריכה חופשית. אין כאן שום לוגיקה משפטית - כל
 * החלטה (מה נתמך, איזו הוראת תיקון נגזרת, איזו תווית תיווצר) מגיעה
 * מהשרת (diff_translate.py/insert_preview.py/apply_changes.py). ה-JS
 * רק שולח את מלוא המצב הנוכחי (edits+insertions) בכל בקשה, ומציג את
 * מה שהשרת מחזיר.
 */

const LEVEL_ORDER = ["section", "subsection", "paragraph", "subparagraph"];
const LEVEL_LABELS = {
  section: "סעיף ראשי",
  subsection: "סעיף קטן",
  paragraph: "פסקה",
  subparagraph: "פסקת משנה",
};

let currentLawId = null;
let originalTextById = {}; // node_id -> טקסט מקורי (מהעץ שנטען מהשרת)
let everEditedNodeIds = new Set(); // כל node_id שנערך אי-פעם (גם אם חזר למקור)
let edits = {}; // node_id -> טקסט נוכחי (רק לצמתים ששונים מהמקור)
let insertions = []; // [{clientId, kind, anchor_node_id, text, margin_title?, label}]
let insertionCounter = 0;
let nodeElements = {}; // node_id -> אלמנט ה-DOM של node-text
let insertPreviewSeq = 0; // מונע עדכון תפריט הוספה שכבר נסגר

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function billMeta() {
  return {
    title: document.getElementById("bill-title-input").value,
    initiator: document.getElementById("bill-initiator-input").value,
    submitted_date: document.getElementById("bill-date-input").value,
    source_ref: document.querySelector("#source-ref-field input").value,
    explanatory: document
      .getElementById("explanatory-input")
      .value.split("\n")
      .map((s) => s.trim())
      .filter((s) => s),
  };
}

function editsPayload() {
  return Object.entries(edits).map(([node_id, text]) => ({ node_id, text }));
}

function insertionsPayload() {
  return insertions.map((ins) => {
    const item = { kind: ins.kind, anchor_node_id: ins.anchor_node_id, text: ins.text };
    if (ins.kind === "section") item.margin_title = ins.margin_title;
    return item;
  });
}

async function loadLawList() {
  const laws = await (await fetch("/api/laws")).json();
  const select = document.getElementById("law-select");
  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.textContent = "— בחר/י חוק —";
  placeholder.value = "";
  select.appendChild(placeholder);
  for (const law of laws) {
    const opt = document.createElement("option");
    opt.value = law.id;
    opt.textContent = law.title + (law.amendable ? "" : " (לא נתמך לעריכה)");
    if (!law.amendable) opt.disabled = true;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => {
    if (select.value) onLawChange(select.value);
  });
}

function buildOriginalTextIndex(node) {
  originalTextById[node.id] = node.text;
  for (const child of node.children) buildOriginalTextIndex(child);
}

async function onLawChange(lawId) {
  currentLawId = lawId;
  edits = {};
  insertions = [];
  everEditedNodeIds = new Set();
  nodeElements = {};
  originalTextById = {};

  const law = await (await fetch(`/api/laws/${lawId}`)).json();
  buildOriginalTextIndex(law.tree);

  document.getElementById("law-panels").hidden = false;
  document.getElementById("as-of-note").textContent = law.as_of_display || "";

  const sourceRefInput = document.querySelector("#source-ref-field input");
  sourceRefInput.value = law.known_source_ref || "";

  const billTitleInput = document.getElementById("bill-title-input");
  if (!billTitleInput.value) billTitleInput.value = `הצעת חוק ${law.title} (תיקון), התש"ף–2024`;

  const treeContainer = document.getElementById("law-tree");
  treeContainer.innerHTML = "";
  treeContainer.appendChild(renderNode(law.tree, 0));

  await refreshPreview();
}

function levelsForNodeType(nodeType) {
  let idx = LEVEL_ORDER.indexOf(nodeType);
  if (idx === -1) idx = 2; // סוגים אחרים (למשל "הגדרה"): מתנהגים כמו פסקה - ברירת מחדל תצוגתית, לא ניחוש משפטי
  const upTo = Math.min(idx + 1, LEVEL_ORDER.length - 1);
  return LEVEL_ORDER.slice(0, upTo + 1);
}

function renderNode(node, depth) {
  const wrapper = document.createElement("div");
  wrapper.className = "node";
  wrapper.style.marginInlineStart = `${depth * 14}px`;

  if (node.node_type === "law") {
    const heading = document.createElement("div");
    heading.className = "law-heading";
    heading.textContent = node.full_title || "";
    wrapper.appendChild(heading);
  } else {
    const header = document.createElement("div");
    header.className = "node-header";
    const label = [node.margin_title, node.number].filter(Boolean).join(" ");
    header.textContent = label;
    if (node.node_type === "section" || node.node_type === "subsection" || node.node_type === "paragraph") {
      const addBtn = document.createElement("button");
      addBtn.className = "node-add-btn subtle";
      addBtn.textContent = "+";
      addBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        toggleInsertMenu(node, wrapper);
      });
      header.appendChild(addBtn);
    }
    wrapper.appendChild(header);

    if (node.text) {
      const textEl = document.createElement("div");
      textEl.className = "node-text";
      textEl.contentEditable = "true";
      textEl.dataset.nodeId = node.id;
      textEl.textContent = node.text;
      textEl.addEventListener("focus", onNodeFocus);
      textEl.addEventListener("blur", onNodeBlur);
      wrapper.appendChild(textEl);
      nodeElements[node.id] = textEl;
    }

    const insertHost = document.createElement("div");
    insertHost.className = "insert-host";
    wrapper.appendChild(insertHost);
  }

  for (const child of node.children) {
    wrapper.appendChild(renderNode(child, depth + 1));
  }
  return wrapper;
}

function onNodeFocus(ev) {
  const el = ev.target;
  const nodeId = el.dataset.nodeId;
  // מסירים דקורציה (del/ins) רק אם היא בפועל קיימת (יש אלמנטי ילד) -
  // el.textContent = ... מחליף את צומת הטקסט הפנימי גם כשהתוכן זהה
  // בייטים, מה שהורס את מיקום הסמן שהקליק כבר קבע (הבאג המקורי: כל
  // פוקוס, כולל קליק רגיל בלי דקורציה בכלל, איפס את הסמן להתחלה).
  // בלי דקורציה - לא נוגעים ב-DOM בכלל, נותנים לדפדפן למקם את הסמן
  // איפה שהמשתמש לחץ.
  if (el.childElementCount > 0) {
    el.textContent = edits[nodeId] ?? originalTextById[nodeId];
  }
  el.classList.remove("edit-unsupported");
}

async function onNodeBlur(ev) {
  const el = ev.target;
  const nodeId = el.dataset.nodeId;
  const currentText = el.textContent;
  const original = originalTextById[nodeId];
  if (currentText === original) {
    delete edits[nodeId];
  } else {
    edits[nodeId] = currentText;
    everEditedNodeIds.add(nodeId);
  }
  await refreshPreview();
}

function applyDecoration(nodeId, status) {
  const el = nodeElements[nodeId];
  if (!el) return;
  const original = originalTextById[nodeId];
  if (!(nodeId in edits)) {
    el.textContent = original;
    el.classList.remove("edit-unsupported");
    el.removeAttribute("title");
    return;
  }
  if (!status || !status.ok) {
    el.textContent = edits[nodeId];
    el.classList.add("edit-unsupported");
    el.title = (status && status.reason) || "לא ניתן לבטא את השינוי הזה כהוראת תיקון";
    return;
  }
  el.classList.remove("edit-unsupported");
  el.removeAttribute("title");
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

async function refreshPreview() {
  if (!currentLawId) return;
  const req = { edits: editsPayload(), insertions: insertionsPayload(), bill: billMeta() };
  const resp = await fetch(`/api/laws/${currentLawId}/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  const data = await resp.json();

  const statusByNodeId = {};
  for (const s of data.edit_statuses) statusByNodeId[s.node_id] = s;
  for (const nodeId of everEditedNodeIds) applyDecoration(nodeId, statusByNodeId[nodeId]);

  renderDocxApprox(data.lines);
  renderFindings(data.findings);
  document.getElementById("download-hint").textContent = data.insertion_errors.length
    ? `שים לב: ${data.insertion_errors.length} הוספות לא בוצעו (ראו כרטיסי ההוספה)`
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

function renderFindings(findings) {
  const tbody = document.getElementById("findings-body");
  tbody.innerHTML = "";
  const statusClass = { "עבר": "pass", "נכשל": "fail", "אזהרה": "warn", "לא נבדק": "skip" };
  let passCount = 0;
  let failCount = 0;
  for (const f of findings) {
    const tr = document.createElement("tr");
    const cls = statusClass[f.status] || "skip";
    if (f.status === "עבר") passCount++;
    if (f.status === "נכשל") failCount++;
    tr.innerHTML = `
      <td>${f.check_number}</td>
      <td><span class="status-badge ${cls}">${f.status}</span></td>
      <td>${escapeHtml(f.description)}</td>
      <td>${escapeHtml(f.message || "")}</td>`;
    tbody.appendChild(tr);
  }
  document.getElementById("validator-summary").textContent =
    `(${passCount} עברו, ${failCount} נכשלו, מתוך ${findings.length})`;
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
    insertions.push({
      clientId: ++insertionCounter,
      kind: level,
      anchor_node_id: node.id,
      text: textInput.value,
      margin_title: level === "section" ? titleInput.value : undefined,
      label,
    });
    menu.remove();
    await refreshPreview();
    renderPendingInsertionCard(node);
  };
  menu.querySelector(".insert-cancel-btn").onclick = () => menu.remove();
}

function renderPendingInsertionCard(anchorNode) {
  const el = nodeElements[anchorNode.id];
  const wrapper = el ? el.closest(".node") : null;
  const host = wrapper ? wrapper.querySelector(":scope > .insert-host") : null;
  if (!host) return;
  const mine = insertions.filter((i) => i.anchor_node_id === anchorNode.id);
  host.querySelectorAll(".pending-insertion-card").forEach((c) => c.remove());
  for (const ins of mine) {
    const card = document.createElement("div");
    card.className = "pending-insertion-card";
    card.textContent = `+ ${LEVEL_LABELS[ins.kind]} חדש (${ins.label}): ${ins.text.slice(0, 40)}`;
    const removeBtn = document.createElement("button");
    removeBtn.className = "subtle";
    removeBtn.textContent = "הסר";
    removeBtn.addEventListener("click", async () => {
      insertions = insertions.filter((i) => i.clientId !== ins.clientId);
      card.remove();
      await refreshPreview();
    });
    card.appendChild(removeBtn);
    host.appendChild(card);
  }
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

document.getElementById("validator-toggle").addEventListener("click", () => {
  const table = document.getElementById("findings-table");
  table.hidden = !table.hidden;
});

for (const inputId of ["bill-title-input", "bill-initiator-input", "bill-date-input"]) {
  document.getElementById(inputId).addEventListener("blur", refreshPreview);
}
document.querySelector("#source-ref-field input").addEventListener("blur", refreshPreview);
document.getElementById("explanatory-input").addEventListener("blur", refreshPreview);

loadLawList();
