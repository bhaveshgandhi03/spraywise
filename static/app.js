"use strict";
/* SprayWise front end. No framework, no inline scripts (CSP: script-src 'self').
   All text from the server or the packet is inserted with textContent, never as HTML. */

const LOCALE = { en: "en-IN", hi: "hi-IN", te: "te-IN", ta: "ta-IN" };
const CROPS = ["tomato", "groundnut", "paddy", "other"];

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode: keep working without saving */ } },
};

const state = {
  lang: store.get("kr.lang", "en"),
  crop: store.get("kr.crop", "paddy"),
  view: "scan",
  dict: {},
  meta: null,
  file: null,
  pendingLabel: null,
  lastScan: null,
  lastSearch: null,
  searchForm: { ai: "", strength: "", form: "", expiry: "" },
};

/* ------------------------------------------------------------------ helpers */
const $ = (s, r = document) => r.querySelector(s);

function t(key, params = {}) {
  const d = state.dict[state.lang] || {};
  let s = d[key] ?? (state.dict.en || {})[key] ?? key;
  for (const [k, v] of Object.entries(params)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "dataset") Object.assign(el.dataset, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "list" || k === "capture" || k.startsWith("aria-")) el.setAttribute(k, v);
    else if (k in el) el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const ICONS = {
  danger: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8.5 8.5 7 7M15.5 8.5l-7 7"/></svg>',
  warning: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.5 20h19z"/><path d="M12 10v5M12 17.5v.01"/></svg>',
  info: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/></svg>',
  camera: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/></svg>',
};
function icon(name) {
  const span = document.createElement("span");
  span.innerHTML = ICONS[name]; // constant markup only
  return span.firstChild;
}

function say(msg) { $("#status").textContent = msg; }

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(LOCALE[state.lang], { day: "numeric", month: "short", year: "numeric" });
}
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function addDays(iso, n) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function daysBetween(fromISO, toISO) {
  return Math.round((new Date(`${toISO}T00:00:00`) - new Date(`${fromISO}T00:00:00`)) / 86400000);
}

async function api(path, opts) {
  let r;
  try { r = await fetch(path, opts); } catch { throw { code: "network" }; }
  let data = null;
  try { data = await r.json(); } catch { /* not JSON */ }
  if (!r.ok) throw { code: data?.error?.code || (r.status === 429 ? "rate" : "generic") };
  return data;
}
function errText(code) {
  return (state.dict.en || {})[`err.${code}`] ? t(`err.${code}`) : t("err.generic");
}

function ingredientsText(label) {
  return (label.ingredients || []).map((i) => (i.percent ? `${i.name} ${i.percent}` : i.name)).join(" + ");
}

/* ------------------------------------------------------------------ shared pieces */
function cropChips() {
  const wrap = h("div", { class: "chips", role: "group", "aria-label": t("crop.label") });
  const draw = () => wrap.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.crop === state.crop)));
  for (const c of CROPS) {
    wrap.append(h("button", {
      class: "chip", type: "button", dataset: { crop: c },
      onclick: () => { state.crop = c; store.set("kr.crop", c); draw(); },
    }, t(`crop.${c}`)));
  }
  draw();
  return h("div", {}, h("h3", {}, t("crop.label")), wrap);
}

function alertText(a) {
  const p = { ...a.params };
  if (p.crop) p.crop = t(`crop.${p.crop}`);
  if (p.date) p.date = fmtDate(p.date);
  return t(`al.${a.code}`, p);
}

function spokenText(res) {
  const parts = [t(`res.verdict.${res.verdict}`)];
  res.alerts.slice(0, 3).forEach((a) => parts.push(alertText(a)));
  if (res.waiting.days != null) parts.push(`${t("res.wait")}: ${t("res.days", { n: res.waiting.days })}`);
  return parts.join(". ");
}

function speak(res, note) {
  if (!("speechSynthesis" in window)) { note.textContent = t("voice.missing"); return; }
  const synth = window.speechSynthesis;
  if (synth.speaking) { synth.cancel(); return; }
  const u = new SpeechSynthesisUtterance(spokenText(res));
  u.lang = LOCALE[state.lang];
  const voices = synth.getVoices();
  const ok = state.lang === "en" || !voices.length || voices.some((v) => v.lang.toLowerCase().startsWith(state.lang));
  note.textContent = ok ? "" : t("voice.missing");
  synth.speak(u);
}

function addToPlan(res, date) {
  const items = store.get("kr.plan", []);
  items.push({
    id: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now() + Math.random()),
    crop: res.crop, spray_date: date, label: res.label, wait_days: res.waiting.days,
    coverage_status: res.coverage?.status || "product_unverified",
  });
  store.set("kr.plan", items.slice(-12));
}

function renderResult(res) {
  const tox = res.toxicity?.color;
  const dateInput = h("input", { type: "date", value: todayISO(), min: addDays(todayISO(), -30), max: addDays(todayISO(), 60) });
  const voiceNote = h("p", { class: "muted", role: "status" });
  const added = h("p", { class: "muted", role: "status" });

  const facts = h("dl", { class: "facts" },
    h("dt", {}, t("res.product")), h("dd", {}, res.label.product_name || "—"),
    h("dt", {}, t("res.ai")), h("dd", {}, ingredientsText(res.label) || "—"),
    h("dt", {}, t("res.form")), h("dd", {}, res.label.formulation || "—"),
    h("dt", {}, t("res.tox")),
    h("dd", {}, tox
      ? [h("span", { class: "swatch", style: `background:var(--tox-${tox})` }), t(`tox.${tox}`)]
      : t("tox.none")),
    h("dt", {}, t("res.expiry")),
    h("dd", {}, res.expiry.date ? fmtDate(res.expiry.date) : (res.expiry.raw || t("res.expiry.unknown"))),
    h("dt", {}, t("res.wait")),
    h("dd", {}, res.waiting.days != null
      ? h("span", { class: "wait" }, t("res.days", { n: res.waiting.days }))
      : t("res.wait.unknown")),
  );

  const alerts = h("ul", { class: "alerts" }, res.alerts.map((a) => h("li", { class: "alert", dataset: { l: a.level } },
    icon(a.level),
    h("div", {}, alertText(a),
      a.params.detail ? h("small", {}, `${t("res.official")} ${a.params.detail}`) : null))));

  const summary = res.summary && res._lang === state.lang
    ? h("div", { class: "summary" }, h("strong", {}, t("res.explain")), h("p", {}, res.summary), h("small", {}, t("res.explain.note")))
    : null;
  const coverage = h("p", { class: "coverage-note", role: "note" }, t(`coverage.${res.coverage?.status || "product_unverified"}`));

  const actions = h("div", { class: "actions" },
    h("button", { class: "btn ghost small", type: "button", onclick: () => speak(res, voiceNote) }, t("res.listen")),
    res.verdict !== "danger" && res.label.ingredients.length
      ? [
        h("label", { class: "field" }, h("span", {}, t("res.sprayDate")), dateInput),
        h("button", {
          class: "btn small", type: "button",
          onclick: () => { addToPlan(res, dateInput.value || todayISO()); added.textContent = t("res.added"); say(t("res.added")); },
        }, t("res.addplan")),
      ]
      : null);

  return h("article", { class: "result", dataset: { tox: tox || "none" } },
    h("div", { class: "verdict", dataset: { v: res.verdict } }, icon(res.verdict), t(`res.verdict.${res.verdict}`)),
    h("div", { class: "body" },
      res.source === "sample" ? h("span", { class: "badge" }, `${t("res.sample")}: ${res.sample_title}`) : null,
      coverage, facts, alerts, summary, actions, voiceNote, added,
      h("details", {}, h("summary", {}, t("tips.title")),
        h("ul", {}, [1, 2, 3, 4, 5, 6].map((i) => h("li", {}, t(`tips.${i}`)))))),
    h("p", { class: "muted", style: "padding:0 16px 14px;margin:0" }, t("disclaimer")));
}

/* ------------------------------------------------------------------ scan view */
async function shrink(file) {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, 1280 / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * scale);
    c.height = Math.round(bmp.height * scale);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    // Re-encoding drops EXIF data such as GPS location before the photo leaves the phone.
    const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.85));
    return blob || file;
  } catch { return file; }
}

function busy(on) {
  const out = $("#out");
  if (!out) return;
  out.replaceChildren(on ? h("div", { class: "item", role: "status" }, h("div", { class: "spin", "aria-hidden": "true" }), t("scan.working")) : "");
}

function showOut(node) { const out = $("#out"); out.replaceChildren(node); node.scrollIntoView?.({ block: "start", behavior: "smooth" }); }
function showError(code) { showOut(h("div", { class: "notice", role: "alert" }, errText(code))); }

async function runScan() {
  if (!state.file) return;
  const btn = $("#scanBtn");
  btn.disabled = true;
  busy(true);
  say(t("scan.working"));
  try {
    const blob = await shrink(state.file);
    const fd = new FormData();
    fd.append("image", blob, "label.jpg");
    fd.append("crop", state.crop);
    fd.append("lang", state.lang);
    const res = await api("/api/read-label", { method: "POST", body: fd });
    state.pendingLabel = res.label;
    state.lastScan = null;
    showOut(renderLabelConfirmation(res.label));
  } catch (e) { showError(e.code || "generic"); }
  finally { btn.disabled = false; }
}

function renderLabelConfirmation(label) {
  const ingredients = label.ingredients || [];
  const fields = [
    h("label", { class: "field" }, h("span", {}, t("scan.productname")),
      h("input", { name: "product_name", value: label.product_name || "", maxlength: 80 })),
    h("div", { class: "stack" }, ingredients.map((ingredient, index) =>
      h("div", { class: "row2" },
        h("label", { class: "field" }, h("span", {}, `${t("scan.ingredient")} ${index + 1}`),
          h("input", { name: "ingredient_name", value: ingredient.name || "", maxlength: 80, required: true })),
        h("label", { class: "field" }, h("span", {}, t("scan.strength")),
          h("input", { name: "ingredient_percent", value: ingredient.percent || "", maxlength: 30 }))))),
    h("label", { class: "field" }, h("span", {}, t("scan.form")),
      h("input", { name: "formulation", value: label.formulation || "", maxlength: 30 })),
    h("label", { class: "field" }, h("span", {}, t("scan.crops")),
      h("input", { name: "printed_crops", value: (label.printed_crops || []).join(", "), maxlength: 600 })),
    h("label", { class: "field" }, h("span", {}, t("scan.waitingPeriod")),
      h("input", { name: "printed_waiting_period", value: label.printed_waiting_period || "", maxlength: 120 })),
    h("label", { class: "field" }, h("span", {}, t("scan.expiry")),
      h("input", { name: "expiry_date", value: label.expiry_date || "", maxlength: 30 })),
    h("label", { class: "field" }, h("span", {}, t("scan.registration")),
      h("input", { name: "registration_number", value: label.registration_number || "", maxlength: 60 })),
  ];
  return h("form", { class: "stack", onsubmit: confirmScannedLabel },
    h("h3", {}, t("scan.review.title")),
    h("p", { class: "notice" }, t("scan.review.note")),
    ...fields,
    h("button", { class: "btn big go", type: "submit" }, t("scan.confirm")));
}

async function confirmScannedLabel(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const names = values.getAll("ingredient_name").map((name) => String(name).trim());
  if (!names.some(Boolean)) {
    showError("unreadable");
    if (state.pendingLabel) $("#out").append(renderLabelConfirmation(state.pendingLabel));
    return;
  }
  busy(true);
  try {
    const res = await api("/api/check", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        crop: state.crop,
        lang: state.lang,
        scan_confirmed: true,
        label: {
          product_name: String(values.get("product_name") || "").trim() || null,
          ingredients: names.map((name, index) => ({
            name,
            percent: String(values.getAll("ingredient_percent")[index] || "").trim() || null,
          })).filter((ingredient) => ingredient.name),
          formulation: String(values.get("formulation") || "").trim() || null,
          printed_crops: String(values.get("printed_crops") || "").split(",").map((crop) => crop.trim()).filter(Boolean),
          printed_waiting_period: String(values.get("printed_waiting_period") || "").trim() || null,
          expiry_date: String(values.get("expiry_date") || "").trim() || null,
          registration_number: String(values.get("registration_number") || "").trim() || null,
        },
      }),
    });
    res._lang = state.lang;
    state.pendingLabel = null;
    state.lastScan = res;
    showOut(renderResult(res));
  } catch (e) {
    showError(e.code || "generic");
    if (state.pendingLabel) $("#out").append(renderLabelConfirmation(state.pendingLabel));
  }
}

async function runSample(s) {
  state.pendingLabel = null;
  state.crop = s.crop; store.set("kr.crop", s.crop);
  document.querySelectorAll(".chip[data-crop]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.crop === state.crop)));
  busy(true);
  try {
    const res = await api(`/api/sample/${encodeURIComponent(s.id)}?crop=${state.crop}&lang=${state.lang}`);
    res._lang = state.lang;
    state.lastScan = res;
    showOut(renderResult(res));
  } catch (e) { showError(e.code || "generic"); }
}

async function viewScan(root) {
  const photoOn = state.meta?.photo_reading !== false;
  const preview = h("img", { class: "preview", alt: "", hidden: !state.file });
  if (state.file) preview.src = URL.createObjectURL(state.file);
  const input = h("input", {
    type: "file", accept: "image/jpeg,image/png,image/webp", capture: "environment", disabled: !photoOn,
    onchange: (e) => {
      const f = e.target.files?.[0];
      if (!f) return;
      state.file = f;
      state.pendingLabel = null;
      state.lastScan = null;
      preview.src = URL.createObjectURL(f);
      preview.hidden = false;
      $("#out").replaceChildren();
      $("#scanBtn").disabled = false;
    },
  });
  const sampleBox = h("div", { class: "samples" });
  root.append(
    h("div", { class: "stack" },
      cropChips(),
      h("label", { class: "drop" }, input, icon("camera"), h("strong", {}, t("scan.take")), h("span", { class: "muted" }, t("scan.tip"))),
      photoOn ? null : h("p", { class: "notice" }, t("scan.nophoto")),
      preview,
      h("button", { id: "scanBtn", class: "btn big go", type: "button", disabled: !state.file || !photoOn, onclick: runScan }, t("scan.analyze")),
      h("div", { id: "out", "aria-live": "polite" }),
      h("section", {}, h("h3", {}, t("scan.sample")), h("p", { class: "muted" }, t("scan.sample.note")), sampleBox)));
  if (state.pendingLabel) $("#out").append(renderLabelConfirmation(state.pendingLabel));
  else if (state.lastScan) $("#out").append(renderResult(state.lastScan));
  try {
    const list = await api("/api/samples");
    list.forEach((s) => sampleBox.append(h("button", { class: "sample", type: "button", onclick: () => runSample(s) }, s.title)));
  } catch { /* samples are optional */ }
}

/* ------------------------------------------------------------------ search view */
function splitFormulation(text) {
  const m = /^\s*([\d.]+\s*(?:%|g\s*\/\s*l)?)\s*(?:w\s*\/\s*[wv])?\s*([a-z]{1,4})\s*$/i.exec(text || "");
  return m ? { strength: m[1].replace(/\s+/g, ""), form: m[2].toUpperCase() } : { strength: "", form: "" };
}

async function runSearch() {
  const f = state.searchForm;
  if (!f.ai.trim()) return;
  const out = $("#out");
  busy(true);
  try {
    const res = await api("/api/check", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        crop: state.crop, lang: state.lang,
        label: {
          ingredients: [{ name: f.ai.trim(), percent: f.strength.trim() || null }],
          formulation: f.form.trim() || null,
          expiry_date: f.expiry.trim() || null,
          printed_crops: [],
        },
      }),
    });
    res._lang = state.lang;
    state.lastSearch = res;
    drawSearchResult(res);
  } catch (e) { out.replaceChildren(h("div", { class: "notice", role: "alert" }, errText(e.code || "generic"))); }
}

function drawSearchResult(res) {
  const out = $("#out");
  const nodes = [renderResult(res)];
  const cands = res.reference?.candidates || [];
  if (["formulation_unknown", "formulation_not_in_reference"].includes(res.reference?.match) && cands.length) {
    nodes.unshift(h("div", {},
      h("p", {}, t("search.pick")),
      h("div", { class: "picker" }, cands.map((c) => h("button", {
        class: "sample", type: "button",
        onclick: () => {
          const s = splitFormulation(c.formulation);
          Object.assign(state.searchForm, { strength: s.strength, form: s.form });
          $("#fStrength").value = s.strength; $("#fForm").value = s.form;
          runSearch();
        },
      }, c.formulation)))));
  }
  out.replaceChildren(...nodes);
  out.firstChild.scrollIntoView?.({ block: "start", behavior: "smooth" });
}

function viewSearch(root) {
  const f = state.searchForm;
  const bind = (key) => (e) => { f[key] = e.target.value; };
  const dl = h("datalist", { id: "ais" }, (state.meta?.ingredients || []).map((n) => h("option", { value: n })));
  const forms = h("datalist", { id: "forms" }, ["EC", "SC", "WP", "WG", "WDG", "SL", "SP", "SG", "DF", "GR", "CG", "FS"].map((n) => h("option", { value: n })));
  root.append(h("form", {
    class: "stack",
    onsubmit: (e) => { e.preventDefault(); runSearch(); },
  },
  h("h2", {}, t("search.title")),
  cropChips(),
  h("label", { class: "field" }, h("span", {}, t("search.ai")), h("input", { value: f.ai, list: "ais", required: true, autocomplete: "off", oninput: bind("ai") }), dl),
  h("div", { class: "row2" },
    h("label", { class: "field" }, h("span", {}, t("search.strength")), h("input", { id: "fStrength", value: f.strength, inputMode: "decimal", oninput: bind("strength") })),
    h("label", { class: "field" }, h("span", {}, t("search.form")), h("input", { id: "fForm", value: f.form, list: "forms", autocapitalize: "characters", oninput: bind("form") }), forms)),
  h("label", { class: "field" }, h("span", {}, t("search.expiry")), h("input", { value: f.expiry, oninput: bind("expiry") })),
  h("button", { class: "btn big go", type: "submit" }, t("search.go")),
  h("div", { id: "out", "aria-live": "polite" })));
  if (state.lastSearch) drawSearchResult(state.lastSearch);
}

/* ------------------------------------------------------------------ plan view */
function icsFor(item, safeISO) {
  const name = item.label.product_name || ingredientsText(item.label);
  const ymd = safeISO.replaceAll("-", "");
  const lines = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SprayWise//EN", "BEGIN:VEVENT",
    `UID:${item.id}@spraywise`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
    `DTSTART;VALUE=DATE:${ymd}`, `SUMMARY:${`Earliest harvest after waiting period: ${name}`.replace(/[,;\n]/g, " ")}`,
    "DESCRIPTION:Check the product label before harvest.", "END:VEVENT", "END:VCALENDAR",
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
  const a = h("a", { href: URL.createObjectURL(blob), download: "harvest-reminder.ics" });
  document.body.append(a); a.click(); a.remove();
}

function rel(n) {
  if (n > 0) return t("plan.in", { n });
  if (n === 0) return t("plan.today");
  return t("plan.ready");
}

async function viewPlan(root) {
  const items = store.get("kr.plan", []);
  const wrap = h("div", { class: "stack" }, h("h2", {}, t("plan.title")));
  root.append(wrap);
  if (!items.length) { wrap.append(h("p", { class: "muted" }, t("plan.empty")), h("p", { class: "muted" }, t("plan.private"))); return; }

  let server = null;
  try {
    server = await api("/api/plan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: items.map((i) => ({ label: i.label, crop: i.crop, spray_date: i.spray_date })) }),
    });
  } catch { /* offline or rate limited: fall back to what was stored on the phone */ }

  const rows = items.map((it, idx) => {
    const sv = server?.items?.[idx];
    const days = sv ? sv.analysis.waiting.days : it.wait_days;
    const safe = sv ? sv.safe_harvest : (days != null ? addDays(it.spray_date, days) : null);
    return { it, safe, left: safe ? daysBetween(todayISO(), safe) : null, analysis: sv?.analysis };
  });
  const known = rows.filter((r) => r.safe).map((r) => r.safe).sort();
  const earliest = known.length ? known[known.length - 1] : null;

  if (earliest) {
    const left = daysBetween(todayISO(), earliest);
    wrap.append(h("div", { class: "seal" },
      h("span", {}, t("plan.earliest")),
      h("span", { class: "big" }, fmtDate(earliest)),
      h("span", {}, rel(left)),
      h("small", {}, t("plan.rule"))));
  }
  if (rows.some((r) => !r.safe)) wrap.append(h("p", { class: "notice" }, t("plan.unknown")));
  (server?.alerts || []).forEach((a) => wrap.append(h("div", { class: "alert", dataset: { l: a.level } }, icon(a.level), h("div", {}, alertText(a)))));
  rows.forEach((r) => {
    (r.analysis?.alerts || []).filter((a) => a.level === "danger").forEach((a) =>
      wrap.append(h("div", { class: "alert", dataset: { l: "danger" } }, icon("danger"), h("div", {}, alertText(a)))));
    wrap.append(h("div", { class: "item" },
      h("div", { class: "top2" },
        h("b", {}, r.it.label.product_name || ingredientsText(r.it.label)),
        r.safe ? h("span", { class: `pill ${r.left <= 0 ? "done" : ""}` }, rel(r.left)) : null),
      h("span", { class: "muted" }, `${t(`crop.${r.it.crop}`)} · ${t("res.sprayDate")}: ${fmtDate(r.it.spray_date)}`),
      r.safe ? h("span", {}, `${t("plan.earliest")}: ${fmtDate(r.safe)}`) : h("span", { class: "muted" }, t("plan.unknown")),
      h("span", { class: "coverage-note" }, t(`coverage.${r.analysis?.coverage?.status || r.it.coverage_status || "product_unverified"}`)),
      h("div", { class: "btns" },
        r.safe ? h("button", { class: "btn ghost small", type: "button", onclick: () => icsFor(r.it, r.safe) }, t("plan.remind")) : null,
        h("button", {
          class: "btn ghost small", type: "button",
          onclick: () => { store.set("kr.plan", items.filter((x) => x.id !== r.it.id)); go("plan"); },
        }, t("plan.remove")))));
  });
  wrap.append(
    h("p", { class: "coverage-note" }, t("plan.calculationOnly")),
    h("p", { class: "muted" }, t("plan.mix")),
    h("p", { class: "muted" }, t("plan.private")),
    h("button", { class: "link", type: "button", onclick: () => { store.set("kr.plan", []); go("plan"); } }, t("plan.clear")));
}

/* ------------------------------------------------------------------ about view */
function viewAbout(root) {
  const src = Object.values(state.meta?.sources || {});
  const sourceItems = src.map((source) => h("li", {},
    h("a", { href: source.url, target: "_blank", rel: "noopener noreferrer" }, source.title),
    source.issuer ? h("p", { class: "muted" }, `${t("about.source.issuer")}: ${source.issuer}`) : null,
    h("p", { class: "muted" }, `${t("about.source.date")}: ${source.as_on || t("about.source.undated")}`),
    source.coverage_note ? h("p", { class: "muted" }, source.coverage_note) : null));
  const gaps = state.meta?.known_gaps || [];
  const banNotes = state.meta?.ban_verification_notes || [];
  root.append(h("div", { class: "stack" },
    h("h2", {}, t("about.title")),
    h("p", {}, t("about.body")),
    h("p", { class: "notice" }, t("about.help")),
    h("p", {}, t("about.data")),
    h("details", {}, h("summary", {}, t("about.sources.title")),
      h("ul", {}, sourceItems)),
    h("details", {}, h("summary", {}, t("about.scope.title")), h("ul", {}, gaps.map((gap) => h("li", {}, gap)))),
    h("details", {}, h("summary", {}, t("about.banVerification.title")), h("ul", {}, banNotes.map((note) => h("li", {}, note)))),
    h("details", {}, h("summary", {}, t("tips.title")), h("ul", {}, [1, 2, 3, 4, 5, 6].map((i) => h("li", {}, t(`tips.${i}`))))),
    h("p", { class: "muted" }, t("disclaimer"))));
}

/* ------------------------------------------------------------------ shell */
const VIEWS = { scan: viewScan, search: viewSearch, plan: viewPlan, about: viewAbout };

async function go(view) {
  state.view = view;
  document.querySelectorAll(".tabs button").forEach((b) => {
    if (b.dataset.view === view) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  const main = $("#view");
  main.replaceChildren();
  await VIEWS[view](main);
}

function applyLang() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  $("#tagline").textContent = t("app.tag");
  document.querySelectorAll(".langs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === state.lang)));
}

async function boot() {
  document.querySelectorAll(".langs button").forEach((b) => b.addEventListener("click", () => {
    state.lang = b.dataset.lang; store.set("kr.lang", state.lang); applyLang(); go(state.view);
  }));
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => go(b.dataset.view)));
  try { state.dict = await (await fetch("/i18n.json")).json(); } catch { state.dict = { en: {} }; }
  if (!state.dict[state.lang]) state.lang = "en";
  try { state.meta = await api("/api/meta"); } catch { state.meta = null; }
  applyLang();
  await go("scan");
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}
boot();
