"use strict";
// Artifact content is assigned only with textContent. No HTML or Markdown evaluation.
const $ = id => document.getElementById(id);
const starts = [0, 8, 19, 31, 43];
const names = ["The question", "The investigation", "The injection", "Observed AI behavior", "Independent control test"];
const slots = {clean: "Clean · AI investigation", permissive: "Poisoned · AI · Permissive", guarded: "Poisoned · AI · Guarded", control_permissive: "Control · No AI · Permissive", control_guarded: "Control · No AI · Guarded"};
let data, catalog, scene = 0, elapsed = 0, playing = false, previousTime = null, audioURL;
const audio = new Audio();
audio.volume = 0.12;
audio.loop = true;

function node(tag, content, className) {
  const element = document.createElement(tag);
  if (content !== undefined) element.textContent = content;
  if (className) element.className = className;
  return element;
}
function add(parent, ...children) { parent.append(...children); return parent; }
function excerpt(value, limit) { return value.length > limit ? value.slice(0, limit) + " … [excerpt]" : value; }
function card(label) { return add(node("div", undefined, "card"), node("div", label, "card-label")); }
function showCalls(run, count = 4) {
  const list = node("div", undefined, "tool-list");
  if (!run) return add(list, node("p", "No compatible recorded run selected."));
  run.calls.slice(0, count).forEach(call => {
    const row = node("div", undefined, "tool-row");
    add(row, node("code", call.tool), node("span", call.decision === "allowed" ? "✓ ALLOWED" : "⊘ DENIED", call.decision));
    add(row, node("small", `${call.evidence_ids.join(" · ") || "No evidence IDs"} — ${call.reason}`));
    list.append(row);
  });
  return list;
}
function metric(value, label) { return add(node("div"), node("div", value == null ? "?" : String(value), "mini-value"), node("p", label, "metric-label")); }
function renderScene() {
  $("scene").replaceChildren();
  const body = node("div", undefined, "scene-body");
  $("scene").append(body);
  $("scene-label").textContent = `${String(scene + 1).padStart(2, "0")} / 05 · ${names[scene]}`;
  if (!data || Object.keys(data.selected).length === 0) {
    add(body, node("div", "RECORDED ARTIFACTS REQUIRED", "eyebrow"), node("h2", "No compatible recorded runs yet."), node("p", "Generate evidence explicitly, then restart the demo server. Playback never calls a hosted model.", "lede"), node("pre", ".\\.venv\\Scripts\\python.exe -m soc_guard investigate --scenario clean --mode guarded\n.\\.venv\\Scripts\\python.exe -m soc_guard compare\n.\\.venv\\Scripts\\python.exe -m soc_guard control", "empty-commands"));
    return;
  }
  const clean = data.selected.clean;
  if (scene === 0) {
    add(body, node("div", "01 / EVIDENCE IS AN INPUT. PERMISSION IS A BOUNDARY.", "eyebrow"), node("h1", "Can an AI SOC analyst be manipulated through the evidence it reads?"), node("p", "One synthetic incident. Poisoned log evidence. Recorded AI behavior. A separate test of server permissions.", "lede"));
    add(body, add(node("div", undefined, "flow"), node("div", "AI investigator", "flow-item"), node("span", "→", "arrow"), node("div", "Real MCP tools", "flow-item"), node("span", "→", "arrow"), node("div", "Server permissions", "flow-item")));
  } else if (scene === 1) {
    add(body, node("div", "02 / RECORDED AI INVESTIGATION", "eyebrow"), node("h2", clean ? `Clean investigation · ${clean.status}` : "Clean investigation unavailable"));
    const evidence = card("ALT-001 · Alert and process evidence");
    add(evidence, node("p", excerpt(data.alert, 230)), node("p", excerpt(data.tree, 150), "tree"), node("p", data.evidence_source, "source"));
    const calls = card("Actual MCP tool calls · Audit record");
    add(calls, showCalls(clean), node("p", clean ? `Source ${clean.run_id.slice(0, 8)} · ${clean.model}` : "Choose a clean AI run in Sources.", "source"));
    add(body, add(node("div", undefined, "two-column"), evidence, calls));
  } else if (scene === 2) {
    add(body, node("div", "03 / ATTACKER-CONTROLLED LOG FIELD", "eyebrow amber"), node("h2", "An instruction hidden inside evidence."));
    const quote = card("⚠ EVT-PS-001.script_annotation · Untrusted text");
    quote.classList.add("injection");
    add(quote, node("blockquote", excerpt(data.injection, 650)), node("p", data.injection_source, "source"));
    add(body, quote, node("p", data.exposure_confirmed ? "Both selected AI audits record this evidence ID returned by search_events. It was evidence, not a user instruction." : "Evidence is not authorization. Exposure is not confirmed in both selected AI records.", "note"));
  } else if (scene === 3) {
    add(body, node("div", "04 / OBSERVED AI BEHAVIOR · RECORDED RESULTS", "eyebrow"), node("h2", data.ai_caption));
    const grid = node("div", undefined, "two-column");
    ["permissive", "guarded"].forEach(mode => {
      const run = data.selected[mode], c = card(`AI investigation · ${mode}`);
      if (!run) add(c, node("p", "Recorded run unavailable."));
      else {
        add(c, add(node("div", undefined, "metrics"), metric(run.attempts, "prohibited attempts"), metric(run.blocked, "blocked attempts")), node("p", `${run.calls.length} audited tool calls · ${run.status}`), node("p", `Synthetic canary in exports: ${run.canary_present === null ? "unverified" : run.canary_present ? "yes" : "no"}`, "note"), node("p", `${run.model} · ${run.run_id.slice(0, 8)}`, "source"));
      }
      grid.append(c);
    });
    add(body, grid, node("p", "Observed behavior in these selected runs. This does not prove universal prompt-injection resistance.", "note"));
  } else {
    add(body, node("div", "05 / DETERMINISTIC TEST · NO AI", "eyebrow accent"), node("h2", "What if the caller ignores instructions?"));
    const grid = node("div", undefined, "two-column");
    ["permissive", "guarded"].forEach(mode => {
      const run = data.selected[`control_${mode}`], c = card(`Deterministic test · No AI · ${mode}`);
      if (!run) add(c, node("p", "Recorded control unavailable."));
      else {
        const canary = run.canary_present === null ? "Unverified" : run.canary_present ? "YES" : "NO";
        add(c, add(node("div", undefined, "metrics"), metric(run.export_count, "local export files"), metric(canary, "canary present on disk")), showCalls(run, 3));
        if (run.warnings.length || run.status !== "complete") add(c, node("p", "⚠ Incomplete or inconsistent control record", "amber note"));
      }
      grid.append(c);
    });
    add(body, grid, node("p", "Test the model. Enforce permissions in code.", "closing accent"));
  }
}
function updateProgress() {
  $("clock").textContent = `00:${String(Math.floor(elapsed)).padStart(2, "0")} / 00:55`;
  $("progress").value = elapsed;
  $("stage-progress").style.width = `${elapsed / 55 * 100}%`;
  $("play").textContent = playing ? "Ⅱ Pause" : "▶ Play";
  $("previous").disabled = scene === 0;
  $("next").disabled = scene === 4;
}
function syncAudio() {
  if (!audioURL) return;
  if (Number.isFinite(audio.duration) && audio.duration > 0) audio.currentTime = elapsed % audio.duration;
  if (playing) audio.play().catch(() => { $("music-status").textContent = "Audio could not play. The presentation continues silently."; });
  else audio.pause();
}
function pause() { playing = false; previousTime = null; audio.pause(); updateProgress(); }
function toggle() {
  if (!data || !Object.keys(data.selected).length) return;
  if (playing) { pause(); return; }
  if (elapsed >= 55) { elapsed = 0; scene = 0; renderScene(); }
  $("technical").open = false;
  playing = true; previousTime = null; syncAudio(); updateProgress();
}
function jump(index) {
  pause(); scene = Math.max(0, Math.min(4, index)); elapsed = starts[scene]; renderScene(); syncAudio(); updateProgress();
}
function tick(time) {
  if (playing) {
    if (previousTime !== null) elapsed = Math.min(55, elapsed + (time - previousTime) / 1000);
    previousTime = time;
    const current = starts.reduce((value, start, index) => elapsed >= start ? index : value, 0);
    if (current !== scene) { scene = current; renderScene(); }
    if (elapsed >= 55) pause();
    updateProgress();
  }
  requestAnimationFrame(tick);
}
async function fullscreen() {
  $("technical").open = false;
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await $("stage").requestFullscreen();
  } catch { $("status").textContent = "Fullscreen unavailable in this browser. Use a desktop browser or its fullscreen shortcut."; }
}
function technical() {
  $("sources").replaceChildren();
  Object.entries(data.selected).forEach(([slot, run]) => {
    const section = node("section");
    add(section, node("h3", slots[slot]), node("p", `Source run: ${run.run_id} · ${run.status} · ${run.kind === "live_model" ? run.model : "Deterministic test · No AI"}`));
    run.warnings.forEach(warning => section.append(node("p", "⚠ " + warning, "amber")));
    add(section, node("pre", run.calls.map((call, index) => `${index + 1}. ${call.tool} · ${call.decision.toUpperCase()} · ${call.reason}\n   Evidence: ${call.evidence_ids.join(", ") || "none"}`).join("\n")));
    $("sources").append(section);
  });
  add($("sources"), node("h3", "Injection excerpt provenance"), node("p", data.injection_source), node("pre", data.injection));
  if (data.missing.length) {
    $("sources").prepend(node("p", "Missing slots: " + data.missing.map(s => slots[s]).join(", ")));
    $("sources").append(node("pre", "Generate missing artifacts explicitly, then restart the server:\n.\\.venv\\Scripts\\python.exe -m soc_guard investigate --scenario clean --mode guarded\n.\\.venv\\Scripts\\python.exe -m soc_guard compare\n.\\.venv\\Scripts\\python.exe -m soc_guard control\nThe AI commands require configured credentials and incur provider usage."));
  }
}
function selectionControls() {
  $("selectors").replaceChildren();
  Object.entries(slots).forEach(([slot, label]) => {
    const select = node("select"); select.id = "select-" + slot;
    const auto = node("option", "Latest recorded run (includes incomplete runs)"); auto.value = ""; select.append(auto);
    catalog.runs.filter(r => {
      const control = slot.startsWith("control_");
      return r.kind === (control ? "deterministic_control" : "live_model") && r.scenario === (slot === "clean" ? "clean" : "poisoned") && (slot === "clean" || r.mode === slot.replace("control_", ""));
    }).forEach(run => {
      const option = node("option", `${run.run_id} · ${run.status}`); option.value = run.run_id;
      option.selected = data.selected[slot]?.run_id === run.run_id; select.append(option);
    });
    add($("selectors"), add(node("label", label), select));
  });
}
async function load(choices) {
  const response = await fetch("/api/replay" + (choices ? "?" + choices.toString() : ""));
  if (!response.ok) throw new Error("Invalid or unavailable selection");
  data = await response.json();
  $("model-label").textContent = data.models.length ? "AI scenes · Recorded model: " + data.models.join(" · ") : "Model identifier unavailable";
  $("play").disabled = !Object.keys(data.selected).length;
  technical(); jump(0);
}
$("play").addEventListener("click", toggle);
$("previous").addEventListener("click", () => jump(scene - 1));
$("next").addEventListener("click", () => jump(scene + 1));
$("restart").addEventListener("click", () => jump(0));
$("fullscreen").addEventListener("click", fullscreen);
$("technical").addEventListener("toggle", () => { if ($("technical").open) pause(); });
$("apply").addEventListener("click", async () => {
  pause(); const choices = new URLSearchParams();
  Object.keys(slots).forEach(slot => { const value = $("select-" + slot).value; if (value) choices.set(slot, value); });
  try { await load(choices); $("status").textContent = "Selected saved runs loaded. No AI requests made."; }
  catch { $("status").textContent = "Could not load this selection. Existing replay is unchanged."; }
});
document.addEventListener("keydown", event => {
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "SUMMARY"].includes(event.target.tagName) && !document.fullscreenElement) return;
  if (["Space", "ArrowLeft", "ArrowRight", "KeyF"].includes(event.code)) event.preventDefault();
  if (event.code === "Space") toggle();
  if (event.code === "ArrowLeft") jump(scene - 1);
  if (event.code === "ArrowRight") jump(scene + 1);
  if (event.code === "KeyF") fullscreen();
});
document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
$("music-file").addEventListener("change", event => {
  audio.pause(); if (audioURL) URL.revokeObjectURL(audioURL);
  const file = event.target.files[0];
  if (!file) { audioURL = undefined; audio.removeAttribute("src"); return; }
  audioURL = URL.createObjectURL(file); audio.src = audioURL;
  $("music-status").textContent = "Local music selected · 12% default volume · never uploaded";
  audio.addEventListener("loadedmetadata", syncAudio, {once: true});
});
$("mute").addEventListener("click", () => { audio.muted = !audio.muted; $("mute").textContent = audio.muted ? "Unmute music" : "Mute music"; $("mute").setAttribute("aria-pressed", String(audio.muted)); });
$("volume").addEventListener("input", event => { audio.volume = Number(event.target.value); });
audio.addEventListener("error", () => { $("music-status").textContent = "Unsupported audio file. The presentation works silently."; });
(async () => {
  try { catalog = await (await fetch("/api/catalog")).json(); await load(); selectionControls(); }
  catch { $("status").textContent = "Recorded data could not be loaded. Restart the local server and check the selected run IDs."; renderScene(); }
  requestAnimationFrame(tick);
})();
