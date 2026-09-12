"use strict";

/* ממשק מינימלי - משימה 10. כל הלוגיקה כאן היא תצוגה/אינטראקציה בלבד:
 * כל "האם זה תקין" נקבע בשרת (transform.apply / validate), לא כאן.
 * שום כשל בבחירת טקסט לא יכול לייצר docx שגוי - במקרה הגרוע נקבל
 * שגיאה מהשרת ("הביטוי לא נמצא"/"נמצא יותר מפעם אחת") ונציג אותה. */

const state = {
  lawId: null,
  law: null, // תשובת /api/laws/{id}
  transformations: [], // {kind, ...} - נשלח לשרת בכל preview, לא נשמר בשרת
  bill: { title: "", initiator: "", submitted_date: "", source_ref: "" },
};

const el = (id) => document.getElementById(id);

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok && res.status !== 400) {
    throw new Error(`שגיאת שרת (${res.status})`);
  }
  return res.json();
}

/* ---------- טעינת רשימת חוקים ---------- */

async function loadLaws() {
  const laws = await api("/api/laws");
  const select = el("law-select");
  select.innerHTML = '<option value="">— בחר/י חוק —</option>';
  for (const law of laws) {
    const opt = document.createElement("option");
    opt.value = law.id;
    opt.textContent = law.title + (law.amendable ? "" : " (קריאה בלבד — מבנה לא נתמך)");
    select.appendChild(opt);
  }
  select.addEventListener("change", () => {
    if (select.value) selectLaw(select.value);
  });
}

async function selectLaw(lawId) {
  const data = await api(`/api/laws/${encodeURIComponent(lawId)}`);
  state.lawId = lawId;
  state.law = data;
  state.transformations = [];
  state.bill.source_ref = data.known_source_ref || "";

  el("law-panels").hidden = false;
  el("as-of-note").textContent = data.as_of_display || "אין תאריך נוסח ידוע למקור זה";

  if (!data.amendable) {
    el("amend-blocked-note").hidden = false;
    el("amend-blocked-note").textContent =
      "החוק הזה בנוי בפרקים (סעיפים מקוננים תחת פרק/סימן) - מנוע התיקונים " +
      "כרגע תומך רק במבנה שטוח כמו חוק הקייטנות. לא נתמך עדיין - אין אפשרות " +
      "לבצע כאן שינוי, רק לקרוא את הנוסח.";
    el("bill-form").hidden = true;
    el("add-change-controls").hidden = true;
  } else {
    el("amend-blocked-note").hidden = true;
    el("bill-form").hidden = false;
    el("add-change-controls").hidden = false;
  }

  el("source-ref-field").querySelector("input").value = state.bill.source_ref;

  renderTree(el("before-tree"), data.tree, { touched: new Set(), selectable: data.amendable });
  el("after-tree").innerHTML = "";
  renderPending();
  clearPreviewOutputs();
  if (data.amendable) refreshPreview();
}

/* ---------- רינדור עץ (לפני/אחרי, אותה פונקציה לשניהם) ---------- */

function renderTree(container, node, ctx, sectionNumber) {
  container.innerHTML = "";
  container.appendChild(renderNode(node, ctx, sectionNumber));
}

function renderNode(node, ctx, sectionNumber) {
  const currentSection = node.node_type === "section" ? node.number : sectionNumber;

  const wrap = document.createElement("div");
  wrap.className = "node status-" + node.status;
  if (currentSection && ctx.touched.has(currentSection) && node.node_type === "section") {
    wrap.classList.add("touched");
  }

  const header = document.createElement("div");
  header.className = "node-header";
  const label = document.createElement("span");

  if (node.node_type === "law") {
    // השורש הוא מטא-דאטה של החוק (שם, לא נוסח) - לא הערת עורך, ולכן
    // לא מקבל את תווית "הערת עורך" למטה. מציג את שם החוק המלא, לא
    // תווית טכנית גנרית.
    label.textContent = node.full_title || node.type_label;
  } else {
    let labelText = node.type_label;
    if (node.number) labelText += " " + node.number;
    if (node.margin_title) labelText += " — " + node.margin_title;
    label.textContent = labelText;
  }
  header.appendChild(label);

  if (node.node_type !== "law" && !node.is_normative) {
    const flag = document.createElement("span");
    flag.className = "editor-note-flag";
    flag.textContent = "הערת עורך — אינה חלק מהחוק";
    header.appendChild(flag);
  }

  // "+ הוסף אחרי" מותר רק על עוגן שהוא ילד בתוך סעיף (InsertAfter דורש
  // anchor_id בתוך רשימת הילדים של הסעיף) - לא על הסעיף/החוק עצמם,
  // שאינם חברים ברשימת הילדים של עצמם. נתפס בבדיקה ידנית בדפדפן.
  const canAnchorInsert = node.node_type !== "law" && node.node_type !== "section";
  if (ctx.selectable && currentSection && canAnchorInsert) {
    const addBtn = document.createElement("button");
    addBtn.className = "node-add-btn subtle";
    addBtn.textContent = "+ הוסף אחרי";
    addBtn.addEventListener("click", () => showInsertNewChildForm(node.id, currentSection, wrap));
    header.appendChild(addBtn);
  }
  wrap.appendChild(header);

  if (node.text) {
    const textEl = document.createElement("div");
    textEl.className = "node-text";
    textEl.dataset.id = node.id;
    textEl.dataset.section = currentSection || "";
    textEl.textContent = node.text;
    wrap.appendChild(textEl);
  }

  if (node.children && node.children.length) {
    const childrenEl = document.createElement("div");
    childrenEl.className = "node-children";
    for (const child of node.children) {
      childrenEl.appendChild(renderNode(child, ctx, currentSection));
    }
    wrap.appendChild(childrenEl);
  }

  return wrap;
}

/* ---------- בחירת טקסט -> ReplaceWords / InsertWordsAfter ---------- */

function visualizeWhitespace(str) {
  const esc = str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc.replace(/ /g, '<span class="ws-mark">·</span>');
}

document.addEventListener("mouseup", (event) => {
  if (!event.target.closest("#before-tree")) return;
  const sel = window.getSelection();
  const text = sel ? sel.toString() : "";
  if (!text || sel.isCollapsed) return;

  const anchorEl = sel.anchorNode && sel.anchorNode.parentElement && sel.anchorNode.parentElement.closest(".node-text");
  const focusEl = sel.focusNode && sel.focusNode.parentElement && sel.focusNode.parentElement.closest(".node-text");
  if (!anchorEl || anchorEl !== focusEl) {
    showSelectionError("בחר/י טקסט בתוך פסקה אחת בלבד (לא לחצות בין סעיפים/פסקאות).");
    return;
  }
  showSelectionBox(anchorEl.dataset.id, anchorEl.dataset.section, text);
});

function showSelectionError(message) {
  const box = el("selection-box");
  box.hidden = false;
  box.innerHTML = `<div class="hint">${message}</div>`;
}

function showSelectionBox(targetId, sectionNumber, phrase) {
  const box = el("selection-box");
  box.hidden = false;
  box.innerHTML = `
    <div>הביטוי שנבחר (רווח מסומן כ-<span class="ws-mark">·</span>):</div>
    <div class="selection-preview">${visualizeWhitespace(phrase)}</div>
    <div class="row">
      <button id="btn-replace" class="primary">החלף ביטוי זה (במקום ... יבוא ...)</button>
      <button id="btn-insert-after">הוסף מילים מיד אחרי הביטוי הזה</button>
      <button id="btn-cancel-sel" class="subtle">בטל</button>
    </div>
    <div id="selection-action-form"></div>
  `;

  el("btn-cancel-sel").addEventListener("click", () => {
    box.hidden = true;
    box.innerHTML = "";
  });

  el("btn-replace").addEventListener("click", () => {
    el("selection-action-form").innerHTML = `
      <div class="field">
        <label>הביטוי החדש שיבוא במקומו</label>
        <input id="replace-new-phrase" type="text" />
      </div>
      <button id="confirm-replace" class="primary">הוסף שינוי</button>
    `;
    el("confirm-replace").addEventListener("click", () => {
      const newPhrase = el("replace-new-phrase").value;
      if (!newPhrase) return;
      state.transformations.push({
        kind: "replace_words",
        target_id: targetId,
        old_phrase: phrase,
        new_phrase: newPhrase,
        _label: `בסעיף ${sectionNumber}: במקום "${phrase}" יבוא "${newPhrase}"`,
      });
      box.hidden = true;
      box.innerHTML = "";
      renderPending();
      refreshPreview();
    });
  });

  el("btn-insert-after").addEventListener("click", () => {
    el("selection-action-form").innerHTML = `
      <div class="field">
        <label>המילים שיוכנסו מיד אחרי הביטוי שנבחר</label>
        <input id="insert-new-text" type="text" />
      </div>
      <button id="confirm-insert" class="primary">הוסף שינוי</button>
    `;
    el("confirm-insert").addEventListener("click", () => {
      const insertedText = el("insert-new-text").value;
      if (!insertedText) return;
      state.transformations.push({
        kind: "insert_words",
        target_id: targetId,
        anchor_substring: phrase,
        inserted_text: insertedText,
        _label: `בסעיף ${sectionNumber}: אחרי "${phrase}" יבוא "${insertedText}"`,
      });
      box.hidden = true;
      box.innerHTML = "";
      renderPending();
      refreshPreview();
    });
  });
}

/* ---------- הוספת צומת חדש (הגדרה/פסקה) ---------- */

function showInsertNewChildForm(anchorId, sectionNumber, wrapEl) {
  let form = wrapEl.querySelector(".selection-box.inline-add");
  if (form) { form.remove(); return; }
  form = document.createElement("div");
  form.className = "selection-box inline-add";
  form.innerHTML = `
    <div class="row">
      <div class="field">
        <label>סוג התוכן החדש</label>
        <select class="new-child-type">
          <option value="definition">הגדרה</option>
          <option value="paragraph">פסקה</option>
          <option value="subsection">סעיף קטן</option>
        </select>
      </div>
    </div>
    <div class="field">
      <label>הנוסח החדש (מוקלד על ידך - לא נוסח חוק אוטומטי)</label>
      <textarea class="new-child-text" rows="2"></textarea>
    </div>
    <button class="primary confirm-new-child">הוסף שינוי</button>
    <button class="subtle cancel-new-child">בטל</button>
  `;
  wrapEl.querySelector(".node-header").after(form);

  form.querySelector(".cancel-new-child").addEventListener("click", () => form.remove());
  form.querySelector(".confirm-new-child").addEventListener("click", () => {
    const nodeType = form.querySelector(".new-child-type").value;
    const text = form.querySelector(".new-child-text").value;
    if (!text) return;
    state.transformations.push({
      kind: "insert_new_child",
      section_number: sectionNumber,
      anchor_id: anchorId,
      node_type: nodeType,
      text: text,
      _label: `בסעיף ${sectionNumber}: הוספת ${nodeType === "definition" ? "הגדרה" : "תוכן"} חדש/ה`,
    });
    form.remove();
    renderPending();
    refreshPreview();
  });
}

/* ---------- רשימת שינויים ממתינים ---------- */

function renderPending() {
  const list = el("pending-list");
  list.innerHTML = "";
  state.transformations.forEach((t, i) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = t._label;
    const btn = document.createElement("button");
    btn.className = "danger";
    btn.textContent = "הסר";
    btn.addEventListener("click", () => {
      state.transformations.splice(i, 1);
      renderPending();
      refreshPreview();
    });
    li.appendChild(span);
    li.appendChild(btn);
    list.appendChild(li);
  });
  el("pending-empty-hint").hidden = state.transformations.length > 0;
}

/* ---------- תצוגה מקדימה: preview -> lines + findings + after-tree ---------- */

function clearPreviewOutputs() {
  el("lines-preview").innerHTML = "";
  el("findings-body").innerHTML = "";
  el("error-banner").hidden = true;
}

function currentPreviewBody() {
  return {
    transformations: state.transformations.map(({ _label, ...t }) => t),
    bill: state.bill,
  };
}

async function refreshPreview() {
  syncBillFromForm();

  const data = await api(`/api/laws/${encodeURIComponent(state.lawId)}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentPreviewBody()),
  });

  const banner = el("error-banner");
  if (data.error) {
    banner.hidden = false;
    banner.textContent = "שגיאה: " + data.error;
    el("lines-preview").innerHTML = "";
    el("after-tree").innerHTML = "";
    renderFindings([]);
    el("download-btn").disabled = true;
    return;
  }
  banner.hidden = true;
  el("download-btn").disabled = state.transformations.length === 0;

  renderLines(data.lines);
  renderFindings(data.findings);
  renderTree(el("after-tree"), data.after_tree, {
    touched: new Set(data.touched_sections),
    selectable: false,
  });
}

function renderLines(lines) {
  const container = el("lines-preview");
  container.innerHTML = "";
  if (!lines.length) {
    container.innerHTML = '<div class="hint">אין עדיין הוראות תיקון - הוסף/י שינוי.</div>';
    return;
  }
  for (const line of lines) {
    const row = document.createElement("div");
    row.className = "line-row";
    let html = "";
    if (line.side_heading) html += `<div class="line-side-heading">${escapeHtml(line.side_heading)}</div>`;
    const isQuoted = line.style === "TableBlockOutdent";
    const bodyClass = isQuoted ? "line-quoted" : "";
    html += `<div class="${bodyClass}">${escapeHtml(line.text)}${escapeHtml(line.text_after || "")}</div>`;
    row.innerHTML = html;
    container.appendChild(row);
  }
}

const STATUS_CLASS = { "עבר": "pass", "נכשל": "fail", "אזהרה": "warn", "לא נבדק": "skip" };

function renderFindings(findings) {
  const body = el("findings-body");
  body.innerHTML = "";
  for (const f of findings) {
    const tr = document.createElement("tr");
    const cls = STATUS_CLASS[f.status] || "skip";
    tr.innerHTML = `
      <td>${f.check_number}</td>
      <td><span class="status-badge ${cls}">${f.status}</span></td>
      <td>${escapeHtml(f.description)}</td>
      <td class="hint">${escapeHtml(f.message)}</td>
    `;
    body.appendChild(tr);
  }
}

function escapeHtml(s) {
  return (s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* ---------- טופס פרטי הצעת החוק ---------- */

function syncBillFromForm() {
  state.bill = {
    title: el("bill-title-input").value,
    initiator: el("bill-initiator-input").value,
    submitted_date: el("bill-date-input").value,
    source_ref: el("source-ref-field").querySelector("input").value,
  };
}

function setupBillForm() {
  ["bill-title-input", "bill-initiator-input", "bill-date-input"].forEach((id) => {
    el(id).addEventListener("change", refreshPreview);
  });
  el("source-ref-field").querySelector("input").addEventListener("change", refreshPreview);
}

/* ---------- הורדת docx ---------- */

async function downloadDocx() {
  syncBillFromForm();
  if (!state.bill.source_ref) {
    alert("מראה מקום (ס\"ח) הוא שדה חובה - בלי הערת שוליים למקור, ההצעה נכשלת בבדיקה 2 בוולידטור.");
    return;
  }
  const res = await fetch(`/api/laws/${encodeURIComponent(state.lawId)}/docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentPreviewBody()),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "שגיאה לא ידועה" }));
    alert("שגיאה בהפקת docx: " + (err.detail || res.status));
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${state.lawId}-הצעת-חוק.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/* ---------- אתחול ---------- */

window.addEventListener("DOMContentLoaded", () => {
  loadLaws();
  setupBillForm();
  el("download-btn").addEventListener("click", downloadDocx);
});
