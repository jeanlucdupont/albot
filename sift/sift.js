const sampleRows = [
  { CVE: "CVE-2024-3094", Severity: "Critical", CVSS: 10.0, Product: "XZ Utils", Version: "5.6.0–5.6.1", Status: "Open", Owner: "Linux Platform" },
  { CVE: "CVE-2012-2343", Severity: "High", CVSS: 8.8, Product: "Apache HTTP Server", Version: "2.2.21", Status: "Accepted risk", Owner: "Web Services" },
  { CVE: "CVE-2023-4911", Severity: "Critical", CVSS: 9.8, Product: "glibc", Version: "2.34", Status: "In progress", Owner: "Linux Platform" },
  { CVE: "CVE-2012-2344", Severity: "Medium", CVSS: 6.5, Product: "OpenSSL", Version: "1.0.1", Status: "Open", Owner: "Core Infrastructure" },
  { CVE: "CVE-2021-44228", Severity: "Critical", CVSS: 10.0, Product: "Apache Log4j", Version: "2.14.1", Status: "Remediated", Owner: "Application Security" },
  { CVE: "CVE-2023-38408", Severity: "High", CVSS: 9.8, Product: "OpenSSH", Version: "9.3p1", Status: "Open", Owner: "Endpoint" },
  { CVE: "CVE-2012-2343", Severity: "High", CVSS: 8.8, Product: "Apache HTTP Server", Version: "2.2.22", Status: "Remediated", Owner: "Legacy Apps" },
  { CVE: "CVE-2024-21626", Severity: "High", CVSS: 8.6, Product: "runc", Version: "1.1.11", Status: "In progress", Owner: "Container Platform" },
  { CVE: "CVE-2022-0847", Severity: "High", CVSS: 7.8, Product: "Linux Kernel", Version: "5.16.10", Status: "Remediated", Owner: "Linux Platform" },
  { CVE: "CVE-2012-2344", Severity: "Medium", CVSS: 6.5, Product: "OpenSSL", Version: "1.0.0", Status: "Accepted risk", Owner: "Legacy Apps" },
  { CVE: "CVE-2023-0286", Severity: "High", CVSS: 7.4, Product: "OpenSSL", Version: "3.0.7", Status: "Open", Owner: "Core Infrastructure" },
  { CVE: "CVE-2022-0778", Severity: "High", CVSS: 7.5, Product: "OpenSSL", Version: "1.1.1m", Status: "Remediated", Owner: "Core Infrastructure" }
];

const state = {
  fileName: "Sample vulnerability report",
  workbook: { "Vulnerabilities": sampleRows },
  sheet: "Vulnerabilities",
  rules: [],
  savedFilters: loadSavedFilters(),
  columnOrder: [],
  hiddenColumns: new Set(),
  sort: { column: null, direction: "asc" },
  page: 1,
  perPage: 50,
  isSample: true
};

const $ = id => document.getElementById(id);
const els = {
  fileInput: $("fileInput"), dropzone: $("dropzone"), newFileBtn: $("newFileBtn"), exportBtn: $("exportBtn"),
  fileTitle: $("fileTitle"), fileMeta: $("fileMeta"), column: $("columnSelect"), operator: $("operatorSelect"),
  value: $("filterValue"), form: $("filterForm"), rules: $("ruleStrip"), clear: $("clearRulesBtn"),
  head: $("tableHead"), body: $("tableBody"), visible: $("visibleCount"), excluded: $("excludedCount"),
  footer: $("footerSummary"), empty: $("emptyState"), tabs: $("sheetTabs"), prev: $("prevPage"), next: $("nextPage"),
  pageLabel: $("pageLabel"), toast: $("toast")
};

function currentRows() { return state.workbook[state.sheet] || []; }
function columns() {
  const set = new Set();
  currentRows().forEach(row => Object.keys(row).forEach(key => set.add(key)));
  return [...set];
}
function syncColumnOrder() {
  const available = columns();
  state.columnOrder = [...state.columnOrder.filter(c => available.includes(c)), ...available.filter(c => !state.columnOrder.includes(c))];
  state.hiddenColumns = new Set([...state.hiddenColumns].filter(c => available.includes(c)));
}
function displayColumns() { syncColumnOrder(); return state.columnOrder.filter(c => !state.hiddenColumns.has(c)); }
function cellText(value) { return value == null ? "" : String(value); }
function matchesRule(row, rule) {
  const values = rule.column === "__all" ? Object.values(row) : [row[rule.column]];
  if (rule.operator === "notcontains") {
    const misses = raw => !cellText(raw).toLocaleLowerCase().includes(rule.value.toLocaleLowerCase());
    return rule.column === "__all" ? values.every(misses) : misses(values[0]);
  }
  return values.some(raw => {
    const text = cellText(raw);
    const a = text.toLocaleLowerCase();
    const b = rule.value.toLocaleLowerCase();
    if (rule.operator === "empty") return text.trim() === "";
    if (rule.operator === "equals") return a === b;
    if (rule.operator === "starts") return a.startsWith(b);
    if (rule.operator === "ends") return a.endsWith(b);
    if (rule.operator === "regex") { try { return new RegExp(rule.value, "i").test(text); } catch { return false; } }
    return a.includes(b);
  });
}
function visibleRows() {
  const rows = currentRows().filter(row => !state.rules.some(rule => matchesRule(row, rule)));
  if (!state.sort.column) return rows;
  const direction = state.sort.direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => compareValues(a[state.sort.column], b[state.sort.column]) * direction);
}
function compareValues(a, b) {
  const aNum = Number(a), bNum = Number(b);
  if (cellText(a).trim() !== "" && cellText(b).trim() !== "" && Number.isFinite(aNum) && Number.isFinite(bNum)) return aNum - bNum;
  return cellText(a).localeCompare(cellText(b), undefined, { numeric: true, sensitivity: "base" });
}

function render() {
  const rows = currentRows();
  const allCols = columns();
  const cols = displayColumns();
  const visible = visibleRows();
  const pageCount = Math.max(1, Math.ceil(visible.length / state.perPage));
  state.page = Math.min(state.page, pageCount);
  const start = (state.page - 1) * state.perPage;
  const pageRows = visible.slice(start, start + state.perPage);

  els.fileTitle.textContent = state.fileName;
  els.fileMeta.textContent = `${rows.length.toLocaleString()} rows · ${allCols.length} columns · ${state.isSample ? "Sample data" : state.sheet}`;
  els.visible.textContent = visible.length.toLocaleString();
  els.excluded.textContent = (rows.length - visible.length).toLocaleString();
  els.footer.textContent = visible.length ? `Showing ${start + 1}–${Math.min(start + state.perPage, visible.length)} of ${visible.length.toLocaleString()} visible rows` : "No visible rows";
  els.pageLabel.textContent = `Page ${state.page} of ${pageCount}`;
  $("activeRuleSummary").textContent = `${state.rules.length} active`;
  $("savedSetSummary").textContent = `${Object.keys(state.savedFilters).length} saved`;
  els.prev.disabled = state.page <= 1;
  els.next.disabled = state.page >= pageCount;

  const selected = els.column.value;
  els.column.innerHTML = `<option value="__all">Whole sheet</option>` + allCols.map(c => `<option value="${escapeAttr(c)}">${escapeHtml(c)}</option>`).join("");
  if (["__all", ...allCols].includes(selected)) els.column.value = selected;

  els.tabs.innerHTML = Object.keys(state.workbook).map(name => `<button class="sheet-tab ${name === state.sheet ? "active" : ""}" role="tab" aria-selected="${name === state.sheet}" data-sheet="${escapeAttr(name)}">${escapeHtml(name)}</button>`).join("");
  els.rules.innerHTML = state.rules.map((rule, i) => `<div class="rule"><span>${escapeHtml(ruleLabel(rule))}</span><button type="button" data-remove="${i}" aria-label="Remove rule ${i + 1}">×</button></div>`).join("");
  els.head.innerHTML = `<tr><th>#</th>${cols.map(c => `<th title="Sort by ${escapeAttr(c)}"><button class="sort-button" type="button" data-sort="${escapeAttr(c)}">${escapeHtml(c)}${state.sort.column === c ? `<span class="sort-mark">${state.sort.direction === "asc" ? "▲" : "▼"}</span>` : ""}</button></th>`).join("")}</tr>`;
  els.body.innerHTML = pageRows.map((row, i) => `<tr><td>${start + i + 1}</td>${cols.map(c => `<td title="${escapeAttr(cellText(row[c]))}">${formatCell(c, row[c])}</td>`).join("")}</tr>`).join("");
  els.empty.hidden = visible.length !== 0;
  renderColumnManager();
  renderSavedFilters();
}

function ruleLabel(rule) {
  const where = rule.column === "__all" ? "Any field" : rule.column;
  const op = { contains: "contains", notcontains: "does not contain", equals: "equals", starts: "starts with", ends: "ends with", regex: "matches", empty: "is empty" }[rule.operator];
  return `${where} ${op}${rule.operator === "empty" ? "" : ` “${rule.value}”`}`;
}
function formatCell(column, value) {
  const text = cellText(value);
  if (/severity/i.test(column) && /^(critical|high|medium|low)$/i.test(text)) return `<span class="severity ${text.toLowerCase()}">${escapeHtml(text)}</span>`;
  if (/cve/i.test(column) && /^CVE-/i.test(text)) return `<span class="cve">${escapeHtml(text)}</span>`;
  return escapeHtml(text);
}
function escapeHtml(v) { return cellText(v).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch])); }
function escapeAttr(v) { return escapeHtml(v).replace(/`/g, "&#96;"); }
function showToast(message) { els.toast.textContent = message; els.toast.classList.add("show"); clearTimeout(showToast.t); showToast.t = setTimeout(() => els.toast.classList.remove("show"), 2400); }
function loadSavedFilters() {
  try { return JSON.parse(localStorage.getItem("sift.savedFilters") || "{}"); } catch { return {}; }
}
function persistSavedFilters() { localStorage.setItem("sift.savedFilters", JSON.stringify(state.savedFilters)); }
function renderSavedFilters() {
  const select = $("savedFilterSelect");
  const selected = select.value;
  select.innerHTML = `<option value="">Choose a saved set…</option>` + Object.keys(state.savedFilters).sort().map(name => `<option value="${escapeAttr(name)}">${escapeHtml(name)}</option>`).join("");
  if (state.savedFilters[selected]) select.value = selected;
  $("deleteSavedBtn").disabled = !select.value;
}
function renderColumnManager() {
  $("columnList").innerHTML = state.columnOrder.map((column, index) => `<div class="column-row">
    <label><input type="checkbox" data-column-visible="${escapeAttr(column)}" ${state.hiddenColumns.has(column) ? "" : "checked"}><span>${escapeHtml(column)}</span></label>
    <div class="move-buttons"><button type="button" data-move-column="${escapeAttr(column)}" data-direction="-1" ${index === 0 ? "disabled" : ""} aria-label="Move ${escapeAttr(column)} left">←</button><button type="button" data-move-column="${escapeAttr(column)}" data-direction="1" ${index === state.columnOrder.length - 1 ? "disabled" : ""} aria-label="Move ${escapeAttr(column)} right">→</button></div>
  </div>`).join("");
}

async function loadFile(file) {
  if (!file) return;
  try {
    const data = await file.arrayBuffer();
    const wb = XLSX.read(data, { type: "array", cellDates: true });
    const parsed = {};
    wb.SheetNames.forEach(name => {
      parsed[name] = XLSX.utils.sheet_to_json(wb.Sheets[name], { defval: "", raw: false });
    });
    state.workbook = parsed;
    state.sheet = wb.SheetNames[0];
    state.fileName = file.name;
    state.rules = [];
    state.columnOrder = [];
    state.hiddenColumns = new Set();
    state.sort = { column: null, direction: "asc" };
    state.page = 1;
    state.isSample = false;
    render();
    showToast(`${file.name} opened — your data stayed in this browser`);
  } catch (error) {
    console.error(error);
    showToast("That file could not be read. Try another XLS, XLSX, or CSV file.");
  }
}

els.form.addEventListener("submit", event => {
  event.preventDefault();
  const operator = els.operator.value;
  const value = els.value.value.trim();
  if (operator !== "empty" && !value) { els.value.focus(); showToast("Enter a value to exclude"); return; }
  if (operator === "regex") { try { new RegExp(value); } catch { showToast("Enter a valid regular expression"); return; } }
  const rule = { column: els.column.value, operator, value };
  const before = visibleRows().length;
  state.rules.push(rule);
  state.page = 1;
  const removed = before - visibleRows().length;
  els.value.value = "";
  render();
  showToast(`${removed.toLocaleString()} ${removed === 1 ? "row" : "rows"} excluded`);
});
els.operator.addEventListener("change", () => { els.value.disabled = els.operator.value === "empty"; els.value.placeholder = els.operator.value === "regex" ? "e.g. CVE-202[1-4]-" : "e.g. CVE-2012-2343"; });
els.rules.addEventListener("click", e => { const index = e.target.dataset.remove; if (index == null) return; state.rules.splice(Number(index), 1); state.page = 1; render(); });
els.clear.addEventListener("click", () => { if (!state.rules.length) return; state.rules = []; state.page = 1; render(); showToast("All exclusions cleared"); });
els.tabs.addEventListener("click", e => { const sheet = e.target.dataset.sheet; if (!sheet) return; state.sheet = sheet; state.rules = []; state.columnOrder = []; state.hiddenColumns.clear(); state.sort = { column: null, direction: "asc" }; state.page = 1; render(); });
els.head.addEventListener("click", e => {
  const button = e.target.closest("[data-sort]");
  if (!button) return;
  const column = button.dataset.sort;
  state.sort = state.sort.column === column ? { column, direction: state.sort.direction === "asc" ? "desc" : "asc" } : { column, direction: "asc" };
  state.page = 1;
  render();
});
$("columnList").addEventListener("change", e => {
  const column = e.target.dataset.columnVisible;
  if (!column) return;
  e.target.checked ? state.hiddenColumns.delete(column) : state.hiddenColumns.add(column);
  render();
});
$("columnList").addEventListener("click", e => {
  const button = e.target.closest("[data-move-column]");
  if (!button) return;
  const index = state.columnOrder.indexOf(button.dataset.moveColumn);
  const target = index + Number(button.dataset.direction);
  if (target < 0 || target >= state.columnOrder.length) return;
  [state.columnOrder[index], state.columnOrder[target]] = [state.columnOrder[target], state.columnOrder[index]];
  render();
});
$("showAllColumns").addEventListener("click", () => { state.hiddenColumns.clear(); render(); });
$("saveFiltersBtn").addEventListener("click", () => {
  const name = $("savedFilterName").value.trim();
  if (!name) { $("savedFilterName").focus(); showToast("Name this filter set first"); return; }
  if (!state.rules.length) { showToast("Add at least one exclusion before saving"); return; }
  state.savedFilters[name] = state.rules.map(rule => ({ ...rule }));
  persistSavedFilters();
  renderSavedFilters();
  $("savedFilterSelect").value = name;
  $("savedFilterName").value = "";
  $("deleteSavedBtn").disabled = false;
  showToast(`Saved “${name}”`);
});
$("savedFilterSelect").addEventListener("change", e => {
  const rules = state.savedFilters[e.target.value];
  $("deleteSavedBtn").disabled = !rules;
  if (!rules) return;
  state.rules = rules.map(rule => ({ ...rule }));
  state.page = 1;
  render();
  $("savedFilterSelect").value = e.target.value;
  showToast(`Loaded “${e.target.value}”`);
});
$("deleteSavedBtn").addEventListener("click", () => {
  const select = $("savedFilterSelect");
  const name = select.value;
  if (!name) return;
  delete state.savedFilters[name];
  persistSavedFilters();
  renderSavedFilters();
  showToast(`Deleted “${name}”`);
});
els.fileInput.addEventListener("change", e => loadFile(e.target.files[0]));
els.newFileBtn.addEventListener("click", () => els.fileInput.click());
["dragenter", "dragover"].forEach(type => els.dropzone.addEventListener(type, e => { e.preventDefault(); els.dropzone.classList.add("drag"); }));
["dragleave", "drop"].forEach(type => els.dropzone.addEventListener(type, e => { e.preventDefault(); els.dropzone.classList.remove("drag"); }));
els.dropzone.addEventListener("drop", e => loadFile(e.dataTransfer.files[0]));
els.prev.addEventListener("click", () => { state.page--; render(); });
els.next.addEventListener("click", () => { state.page++; render(); });
$("pageSizeSelect").addEventListener("change", e => {
  state.perPage = e.target.value === "all" ? Number.MAX_SAFE_INTEGER : Number(e.target.value);
  state.page = 1;
  render();
});
els.exportBtn.addEventListener("click", () => {
  const rows = visibleRows();
  if (!rows.length) { showToast("There are no visible rows to export"); return; }
  const csv = XLSX.utils.sheet_to_csv(XLSX.utils.json_to_sheet(rows));
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${state.fileName.replace(/\.[^.]+$/, "") || "filtered"}-visible.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast(`${rows.length.toLocaleString()} visible rows exported`);
});

render();
