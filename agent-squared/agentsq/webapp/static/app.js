/* Experiment run dashboard.
 *
 * Reads /api/payload (runs, steps, calls straight out of sqlite) and draws the
 * figures from notebooks/. The ribbons are DOM rather than images so every
 * segment can be clicked: that is the whole point of the page -- a picture of a
 * ribbon cannot tell you why step 17 went STUCK.
 *
 * The families under runs/ do not carry the same fields, so a chart appears
 * only when the selected experiment has the data behind it: token bars need
 * agent_tokens (graph runs), the tool and fault ribbons need a call log.
 */

const PHASES = ["PROGRESSING", "STUCK", "COMPLETED"];
const TOOLS = ["tavily_search", "tavily_research", "tavily_extract",
               "tavily_crawl", "tavily_map"];
const COND_ORDER = ["baseline", "limited", "broken"];
const FALLBACK = ["#7a6ff0", "#0f9bb5", "#c9761d", "#8a8f98"];

const TOKEN_PARTS = [["input", "#86b6ef"], ["visible_output", "#3987e5"],
                     ["reasoning", "#184f95"]];

const state = {
  experiment: null, experiments: [],
  // `all` is the whole family; runs/steps/calls are what the filters let through
  all: { runs: [], steps: [], calls: [] },
  filter: { batch: null, model: null },
  runs: [], steps: [], calls: [], byRun: new Map(), sel: null,
};

/* --- small helpers -------------------------------------------------------- */
const css = (name, fallback) => {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue("--" + name).trim();
  return v || fallback;
};
const condColor = c => COND_ORDER.includes(c) ? css(c, "#898781") : css("muted");
const phaseColor = p => css(p.toLowerCase(), "#898781");
const toolColor = t => TOOLS.includes(t) ? css(t) : FALLBACK[TOOLS.length % 4];

const modelColors = new Map();
function modelColor(m) {
  if (!m) return css("muted");
  if (!modelColors.has(m)) {
    const base = [css("progressing"), css("stuck"), css("completed"), ...FALLBACK];
    modelColors.set(m, base[modelColors.size % base.length]);
  }
  return modelColors.get(m);
}

// batch1-1-broken-gpt-5.6-sol-... -> b1-1 broken; a run filed under a model
// folder (benchmark_runs/broken-batch2/inkling/...) -> b2 t3 inkling broken,
// since its batch is the question set and its trial index is always 0
function short(run) {
  const r = state.byRun.get(run);
  if (!r || !r.parsed) return run.length > 22 ? run.slice(0, 21) + "…" : run;
  const task = run.includes("~") ? ` t${run.split("~").pop()}` : "";
  return r.model_group
    ? `b${r.batch}${task} ${r.model_group} ${r.condition}`
    : `b${r.batch}-${r.trial}${task} ${r.condition}`;
}
const tagOf = r => r.model_group
  ? `b${r.batch ?? "?"} · ${r.model_group}`
  : `b${r.batch ?? "?"}-${r.trial ?? "?"}`;
/* Hand-graded answer: `correct` is true, false, or null until someone checks it. */
const verdict = r => (r.correct == null ? "ungraded" : r.correct ? "right" : "wrong");
const verdictMark = r => (r.correct == null ? "·" : r.correct ? "✓" : "✗");
const verdictColor = r =>
  r.correct == null ? css("muted") : r.correct ? css("completed") : css("alarm");
// "3/5 right", or "" when none of the runs has been graded
function rightOf(runs) {
  const graded = runs.filter(r => r.correct != null);
  return graded.length
    ? `${graded.filter(r => r.correct).length}/${graded.length} right` : "";
}
const pct = x => (x == null ? "–" : `${Math.round(x * 100)}%`);
const num = x => (x == null ? "–" : x.toLocaleString());
const pair = r =>
  [r.agent_model && `${r.agent_model} → ${r.monitor_model}`, r.effort]
    .filter(Boolean).join("   ");
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const svgEl = (tag, attrs = {}) => {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};
function legend(host, entries) {
  const box = document.getElementById(host);
  box.replaceChildren();
  for (const [label, color] of entries) {
    const s = el("span");
    const i = el("i");
    i.style.background = color;
    s.append(i, document.createTextNode(label));
    box.append(s);
  }
}

/* Conditions present, in the canonical order, with unknown ones appended so a
   new arm shows up without a code change here. */
function conditions() {
  const seen = [...new Set(state.runs.map(r => r.condition))];
  return [...COND_ORDER.filter(c => seen.includes(c)),
          ...seen.filter(c => !COND_ORDER.includes(c))];
}
const runsIn = cond => state.runs.filter(r => r.condition === cond);

/* Ribbon groups. A family filed by model (benchmark_runs) groups by batch, then
   model, then condition, so baseline and broken for one model sit together;
   every other family keeps one group per condition. */
const byNum = (a, b) => (a ?? Infinity) - (b ?? Infinity);
function ribbonGroups() {
  if (!state.runs.some(r => r.model_group)) {
    return conditions().map(cond => ({ cond, title: cond, rows: runsIn(cond) }));
  }
  const conds = conditions();
  const groups = new Map();
  for (const r of state.runs) {
    const key = `${r.batch}|${r.model_group}|${r.condition}`;
    if (!groups.has(key)) {
      groups.set(key, { cond: r.condition, batch: r.batch, model: r.model_group || "",
                        title: `batch ${r.batch ?? "?"} · ${r.model_group || "?"} · ${r.condition}`,
                        rows: [] });
    }
    groups.get(key).rows.push(r);
  }
  return [...groups.values()].sort((a, b) =>
    byNum(a.batch, b.batch) || a.model.localeCompare(b.model)
    || conds.indexOf(a.cond) - conds.indexOf(b.cond));
}

/* --- selection ------------------------------------------------------------ */
function select(sel) {
  state.sel = sel;
  renderDetail();
  for (const node of document.querySelectorAll(".seg.active, .cell.selected")) {
    node.classList.remove("active", "selected");
  }
  if (!sel) return;
  const q = sel.kind === "run"
    ? `.cell[data-run="${CSS.escape(sel.run)}"]`
    : `.seg[data-kind="${sel.kind}"][data-run="${CSS.escape(sel.run)}"][data-i="${sel.i}"]`;
  for (const node of document.querySelectorAll(q)) {
    node.classList.add(sel.kind === "run" ? "selected" : "active");
  }
  const card = document.querySelector(`.cell[data-run="${CSS.escape(sel.run)}"]`);
  if (card) card.classList.add("selected");
}

/* --- design grid ---------------------------------------------------------- */
function renderDesign() {
  const host = document.getElementById("design");
  host.replaceChildren();
  const trials = [...new Set(state.runs.map(r => r.trial))].length || 1;
  host.style.gridTemplateColumns = `repeat(${Math.min(trials, 3)}, minmax(0, 1fr))`;

  for (const r of state.runs) {
    const color = condColor(r.condition);
    const cell = el("div", "cell" + (r.parsed ? "" : " unparsed"));
    cell.dataset.run = r.run;
    cell.style.borderColor = color;
    cell.style.background = color + "1f";

    cell.append(el("div", "tag", tagOf(r)));
    const cond = el("div", "cond", r.condition || "unparsed run id");
    cond.style.color = color;
    const mark = el("span", "verdict", ` ${verdictMark(r)} ${verdict(r)}`);
    mark.style.color = verdictColor(r);
    cond.append(mark);
    cell.append(cond);
    const meta = el("div", "meta");
    meta.append(
      el("div", null, r.question_title || "–"),
      el("div", null, `agent: ${r.agent_model || "?"}`),
      el("div", null, `monitor: ${r.monitor_model || "?"}`),
      el("div", null, `effort: ${r.effort || "?"}`),
      el("div", null, `${r.n_steps} steps`),
      el("div", null, `${r.mcp_call_count} calls / ${r.mcp_faulted_count} faulted`));
    cell.append(meta);
    cell.onclick = () => select({ kind: "run", run: r.run });
    host.append(cell);
  }
}

/* --- ribbons -------------------------------------------------------------- */
/* One row per run, one segment per item. `spec` says what an item looks like. */
function renderRibbon(hostId, spec) {
  const host = document.getElementById(hostId);
  host.replaceChildren();

  for (const group of ribbonGroups()) {
    const rows = [...group.rows].sort(spec.sort);
    const right = rightOf(rows);
    const head = el("div", "group-head",
      `${group.title}  (${rows.length} runs${right ? ` · ${right}` : ""})`);
    head.style.color = condColor(group.cond);
    host.append(head);

    for (const r of rows) {
      const items = spec.items(r);
      const row = el("div", "ribbon-row");
      const label = el("div", "label");
      const mark = el("span", "verdict", verdictMark(r) + " ");
      mark.style.color = verdictColor(r);
      mark.title = `answer ${verdict(r)}`;
      label.append(mark, document.createTextNode(spec.label(r, items)));
      row.append(label);

      const ribbon = el("div", "ribbon" + (items.length ? "" : " empty"));
      items.forEach((item, i) => {
        const seg = el("div", "seg");
        seg.style.background = spec.color(item);
        seg.dataset.kind = spec.kind;
        seg.dataset.run = r.run;
        seg.dataset.i = spec.index(item);
        seg.title = spec.tip(item, r);
        seg.onclick = () => select({ kind: spec.kind, run: r.run, i: spec.index(item) });
        ribbon.append(seg);
      });
      if (!items.length) ribbon.title = "no data for this run";
      row.append(ribbon);

      const [text, color] = spec.note ? spec.note(r, items) : ["", ""];
      const note = el("div", "note", text);
      note.style.color = color;
      row.append(note);
      host.append(row);
    }
  }
}

const stepsOf = run => state.steps.filter(s => s.run === run);
const callsOf = run => state.calls.filter(c => c.run === run);

function renderPhaseRibbon() {
  legend("phase-legend", PHASES.map(p => [p, phaseColor(p)]));
  renderRibbon("phase-ribbon", {
    kind: "step",
    sort: (a, b) => b.n_steps - a.n_steps,
    items: r => stepsOf(r.run),
    index: s => s.i,
    color: s => phaseColor(s.phase),
    label: r => `${short(r.run)}   ${pair(r)}   n=${r.n_steps}`,
    tip: s => `step ${s.i} · ${s.phase}\n${(s.summary || "").slice(0, 160)}`,
    note: r => {
      const notes = [];
      if (r.n_completed_labels > 1) notes.push(`${r.n_completed_labels}x COMPLETED`);
      if (r.final_phase !== "COMPLETED") notes.push(`final=${r.final_phase}`);
      if (r.n_stuck === 0) notes.push("never STUCK");
      return [notes.join(" | "), css("alarm")];
    },
  });
}

function renderToolRibbon() {
  legend("tool-legend", TOOLS.map(t => [t, toolColor(t)]));
  renderRibbon("tool-ribbon", {
    kind: "call",
    sort: (a, b) => b.mcp_call_count - a.mcp_call_count,
    items: r => callsOf(r.run),
    index: c => c.index,
    color: c => toolColor(c.tool),
    label: r => `${short(r.run)}   ${pair(r)}   n=${r.mcp_call_count || 0} calls`,
    tip: c => `call ${c.index} · ${c.tool}${c.faulted ? " · faulted" : ""}`,
  });
}

function renderFaultRibbon() {
  legend("fault-legend", [["call reached the server", css("clean")],
                          ["faulted (canned error)", css("faulted")]]);
  renderRibbon("fault-ribbon", {
    kind: "call",
    sort: (a, b) => b.mcp_call_count - a.mcp_call_count,
    items: r => callsOf(r.run),
    index: c => c.index,
    color: c => (c.faulted ? css("faulted") : css("clean")),
    label: r => `${short(r.run)}   ${r.effort || ""}   n=${r.mcp_call_count || 0} calls`,
    tip: c => `call ${c.index} · ${c.tool}${c.faulted ? " · faulted" : " · reached server"}`,
    // every broken run is 100% faulted and every baseline 0%, so the row states
    // the share rather than letting a solid bar imply variation it lacks
    note: r => [`${pct(r.faulted_share)} faulted`,
                r.mcp_faulted_count ? css("alarm") : css("muted")],
  });
}

/* --- stuck share ---------------------------------------------------------- */
function renderStuckPlot() {
  const host = document.getElementById("stuck-plot");
  host.replaceChildren();
  const conds = conditions();
  const W = 720, H = 360, L = 58, R = 24, T = 18, B = 44;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%" });

  const models = [...new Set(state.runs.map(r => r.monitor_model).filter(Boolean))];
  legend("stuck-legend", models.map(m => [m, modelColor(m)]));

  const yMax = 0.7;
  const y = v => T + (1 - v / yMax) * (H - T - B);
  for (let t = 0; t <= 7; t++) {
    const v = t / 10;
    svg.append(svgEl("line", { class: "gridline", x1: L, x2: W - R, y1: y(v), y2: y(v) }));
    const lab = svgEl("text", { class: "tick", x: L - 8, y: y(v) + 4, "text-anchor": "end" });
    lab.textContent = v.toFixed(1);
    svg.append(lab);
  }

  const band = (W - L - R) / conds.length;
  conds.forEach((cond, k) => {
    const cx = L + band * (k + 0.5);
    const rows = [...runsIn(cond)]
      .filter(r => r.stuck_share != null)
      .sort((a, b) => a.stuck_share - b.stuck_share);

    rows.forEach((r, i) => {
      const off = rows.length > 1 ? (i / (rows.length - 1) - 0.5) * band * 0.45 : 0;
      const dot = svgEl("circle", {
        class: "dot", cx: cx + off, cy: y(r.stuck_share),
        r: 6 + Math.min(r.n_steps, 30) * 0.18, fill: modelColor(r.monitor_model),
      });
      dot.onclick = () => select({ kind: "run", run: r.run });
      const title = svgEl("title");
      title.textContent = `${r.run}\nSTUCK ${r.n_stuck}/${r.n_body_steps} = ${pct(r.stuck_share)}`;
      dot.append(title);
      svg.append(dot);

      const lab = svgEl("text", {
        class: "tick", x: cx + off, y: y(r.stuck_share) - 14 - (i % 2) * 11,
        "text-anchor": "middle",
      });
      lab.textContent = short(r.run).split(" ")[0];
      svg.append(lab);
    });

    if (rows.length) {
      const mean = rows.reduce((s, r) => s + r.stuck_share, 0) / rows.length;
      svg.append(svgEl("line", {
        x1: cx + band * 0.28, x2: cx + band * 0.40, y1: y(mean), y2: y(mean),
        stroke: css("ink"), "stroke-width": 2.5,
      }));
      const m = svgEl("text", { class: "val", x: cx + band * 0.43, y: y(mean) + 4 });
      m.textContent = `mean ${mean.toFixed(2)} (n=${rows.length})`;
      svg.append(m);
    }

    const lab = svgEl("text", { class: "lbl", x: cx, y: H - B + 22, "text-anchor": "middle" });
    lab.textContent = cond;
    lab.setAttribute("fill", condColor(cond));
    svg.append(lab);
  });

  const yl = svgEl("text", { class: "lbl", x: 14, y: H / 2, transform: `rotate(-90 14 ${H / 2})`, "text-anchor": "middle" });
  yl.textContent = "share of steps labelled STUCK";
  svg.append(yl);
  host.append(svg);
}

/* --- call bars ------------------------------------------------------------ */
function renderCallBars() {
  const host = document.getElementById("call-bars");
  host.replaceChildren();
  legend("tool-legend-bars", TOOLS.map(t => [t, toolColor(t)]));

  const rows = conditions().flatMap(c => runsIn(c));
  const W = 760, H = 380, L = 52, R = 16, T = 34, B = 74;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%" });
  const max = Math.max(1, ...rows.map(r => r.mcp_call_count));
  const y = v => T + (1 - v / (max * 1.16)) * (H - T - B);

  for (let t = 0; t <= 4; t++) {
    const v = Math.round((max * t) / 4);
    svg.append(svgEl("line", { class: "gridline", x1: L, x2: W - R, y1: y(v), y2: y(v) }));
    const lab = svgEl("text", { class: "tick", x: L - 8, y: y(v) + 4, "text-anchor": "end" });
    lab.textContent = v;
    svg.append(lab);
  }

  const band = (W - L - R) / Math.max(rows.length, 1);
  const bw = Math.min(band * 0.58, 74);
  rows.forEach((r, i) => {
    const cx = L + band * (i + 0.5);
    let acc = 0;
    for (const tool of TOOLS) {
      const n = (r.tool_counts || {})[tool] || 0;
      if (!n) continue;
      const rect = svgEl("rect", {
        class: "bar", x: cx - bw / 2, width: bw,
        y: y(acc + n), height: Math.max(y(acc) - y(acc + n), 0),
        fill: toolColor(tool), stroke: css("panel"), "stroke-width": 1,
      });
      const title = svgEl("title");
      title.textContent = `${r.run}\n${tool}: ${n}`;
      rect.append(title);
      rect.onclick = () => select({ kind: "run", run: r.run });
      svg.append(rect);
      acc += n;
    }
    const total = svgEl("text", { class: "val", x: cx, y: y(acc) - 20, "text-anchor": "middle" });
    total.textContent = `${r.mcp_call_count} calls`;
    svg.append(total);
    const f = svgEl("text", { class: "tick", x: cx, y: y(acc) - 7, "text-anchor": "middle" });
    f.textContent = `${r.mcp_faulted_count} faulted`;
    f.setAttribute("fill", r.mcp_faulted_count ? css("alarm") : css("muted"));
    svg.append(f);

    const lab = svgEl("text", {
      class: "tick", x: cx, y: H - B + 18, "text-anchor": "end",
      transform: `rotate(-30 ${cx} ${H - B + 18})`,
    });
    lab.textContent = short(r.run);
    svg.append(lab);
  });

  const yl = svgEl("text", { class: "lbl", x: 14, y: H / 2, transform: `rotate(-90 14 ${H / 2})`, "text-anchor": "middle" });
  yl.textContent = "MCP tool calls";
  svg.append(yl);
  host.append(svg);
}

/* --- token bars ----------------------------------------------------------- */
/* Only graph runs record tokens; the section stays hidden for families that
   do not, rather than drawing an axis full of zeroes. */
function renderTokenBars() {
  const host = document.getElementById("token-bars");
  host.replaceChildren();
  legend("token-legend",
         [...TOKEN_PARTS.map(([k, c]) => [`monitor ${k.replace("_", " ")}`, c]),
          ["agent total", "#dbdad3"]]);

  const rows = state.runs.filter(r => r.has_tokens);
  const W = 860, H = 400, L = 62, R = 16, T = 34, B = 86;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%" });
  const max = Math.max(1, ...rows.map(r => Math.max(r.monitor_total, r.agent_total)));
  const y = v => T + (1 - v / (max * 1.14)) * (H - T - B);

  for (let t = 0; t <= 4; t++) {
    const v = Math.round((max * t) / 4);
    svg.append(svgEl("line", { class: "gridline", x1: L, x2: W - R, y1: y(v), y2: y(v) }));
    const lab = svgEl("text", { class: "tick", x: L - 8, y: y(v) + 4, "text-anchor": "end" });
    lab.textContent = v >= 1000 ? `${Math.round(v / 1000)}k` : v;
    svg.append(lab);
  }

  const band = (W - L - R) / Math.max(rows.length, 1);
  const bw = Math.min(band * 0.36, 26);
  rows.forEach((r, i) => {
    const cx = L + band * (i + 0.5);
    let acc = 0;
    for (const [part, color] of TOKEN_PARTS) {
      const n = r[`monitor_${part}`] || 0;
      if (!n) continue;
      const rect = svgEl("rect", {
        class: "bar", x: cx - bw - 1, width: bw,
        y: y(acc + n), height: Math.max(y(acc) - y(acc + n), 0),
        fill: color, stroke: css("panel"), "stroke-width": 1,
      });
      const title = svgEl("title");
      title.textContent = `${r.run}\nmonitor ${part}: ${n.toLocaleString()}`;
      rect.append(title);
      rect.onclick = () => select({ kind: "run", run: r.run });
      svg.append(rect);
      acc += n;
    }
    const agent = svgEl("rect", {
      class: "bar", x: cx + 1, width: bw,
      y: y(r.agent_total), height: Math.max(y(0) - y(r.agent_total), 0),
      fill: "#dbdad3", stroke: css("panel"), "stroke-width": 1,
    });
    const at = svgEl("title");
    at.textContent = `${r.run}\nagent total: ${(r.agent_total || 0).toLocaleString()}`;
    agent.append(at);
    agent.onclick = () => select({ kind: "run", run: r.run });
    svg.append(agent);

    if (r.monitor_agent_ratio != null) {
      const lab = svgEl("text", {
        class: "val", x: cx, y: y(Math.max(acc, r.agent_total)) - 6, "text-anchor": "middle",
      });
      lab.textContent = `${r.monitor_agent_ratio.toFixed(2)}x`;
      svg.append(lab);
    }
    const lab = svgEl("text", {
      class: "tick", x: cx, y: H - B + 16, "text-anchor": "end",
      transform: `rotate(-38 ${cx} ${H - B + 16})`,
    });
    lab.textContent = short(r.run);
    svg.append(lab);
  });

  const yl = svgEl("text", { class: "lbl", x: 14, y: H / 2, transform: `rotate(-90 14 ${H / 2})`, "text-anchor": "middle" });
  yl.textContent = "tokens";
  svg.append(yl);
  host.append(svg);
}

/* --- detail panel --------------------------------------------------------- */
function block(title, text, mono, placeholder) {
  const b = el("div", "block");
  b.append(el("h4", null, title));
  if (text) {
    b.append(el(mono ? "pre" : "div", "body", text));
  } else {
    b.append(el("div", "empty-state", placeholder || "(empty)"));
  }
  return b;
}

function prettyArgs(raw) {
  try {
    const o = JSON.parse(raw);
    const primary = ["query", "input", "urls", "url"].find(k => k in o);
    const rest = { ...o };
    let head = null;
    if (primary) { head = [primary, o[primary]]; delete rest[primary]; }
    return [head, JSON.stringify(rest, null, 2)];
  } catch {
    return [null, raw];
  }
}

/* The list payload leaves out answers (large); fetch one run's on demand. */
const answerCache = new Map();
function loadAnswers(run) {
  const key = `${run.experiment}/${run.run}`;
  if (!answerCache.has(key)) {
    answerCache.set(key, fetch(`/api/runs/${encodeURIComponent(run.experiment)}/${encodeURIComponent(run.run)}`)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .catch(err => { answerCache.delete(key); throw err; }));
  }
  return answerCache.get(key);
}

function renderDetail() {
  const host = document.getElementById("detail");
  host.replaceChildren();
  const sel = state.sel;
  if (!sel) {
    host.append(el("p", "empty-state", "Select a run, a step or a tool call."));
    return;
  }
  const run = state.byRun.get(sel.run);
  if (!run) {                       // selection outlived its run
    state.sel = null;
    host.append(el("p", "empty-state", "That run is no longer loaded."));
    return;
  }

  const head = el("div", "detail-head");
  const cond = el("span", "chip", run.condition || "unparsed");
  cond.style.background = condColor(run.condition);
  head.append(cond);

  if (sel.kind === "step") {
    const s = stepsOf(sel.run).find(x => x.i === sel.i);
    const chip = el("span", "chip", s.phase);
    chip.style.background = phaseColor(s.phase);
    head.append(chip, el("span", "chip outline", `step ${s.i} of ${run.n_steps - 1}`));
    if (s.hedged) head.append(el("span", "chip outline", "hedged"));
    host.append(head, el("div", "detail-run", run.run));

    const steps = stepsOf(sel.run);
    const nav = el("div", "stepper");
    const prev = el("button", null, "← prev step");
    const next = el("button", null, "next step →");
    prev.disabled = sel.i <= 0;
    next.disabled = sel.i >= steps.length - 1;
    prev.onclick = () => select({ ...sel, i: sel.i - 1 });
    next.onclick = () => select({ ...sel, i: sel.i + 1 });
    nav.append(prev, next);
    host.append(nav);

    host.append(
      block("monitor justification (analysis_log)", s.justification),
      block("monitor summary (summary_log)", s.summary),
      block("agent reasoning, raw (raw_summary_log)", s.raw_summary));
    return;
  }

  if (sel.kind === "call") {
    const c = callsOf(sel.run).find(x => x.index === sel.i);
    const chip = el("span", "chip", c.tool);
    chip.style.background = toolColor(c.tool);
    const fault = el("span", "chip", c.faulted ? "faulted" : "reached server");
    fault.style.background = c.faulted ? css("faulted") : css("clean");
    head.append(chip, fault,
                el("span", "chip outline", `call ${c.index} of ${run.mcp_call_count}`));
    host.append(head, el("div", "detail-run", run.run));

    const calls = callsOf(sel.run);
    const at = calls.findIndex(x => x.index === c.index);
    const nav = el("div", "stepper");
    const prev = el("button", null, "← prev call");
    const next = el("button", null, "next call →");
    prev.disabled = at <= 0;
    next.disabled = at >= calls.length - 1;
    prev.onclick = () => select({ ...sel, i: calls[at - 1].index });
    next.onclick = () => select({ ...sel, i: calls[at + 1].index });
    nav.append(prev, next);
    host.append(nav);

    const [primary, rest] = prettyArgs(c.arguments);
    if (primary) host.append(block(primary[0], String(primary[1])));
    host.append(block("arguments", rest, true));
    if (c.faulted) {
      host.append(block("note",
        "FaultyMcpTools recorded this call and returned a canned error; it never reached the Tavily server."));
    }
    return;
  }

  const graded = el("span", "chip", `answer ${verdict(run)}`);
  graded.style.background = verdictColor(run);
  head.append(graded,
              el("span", "chip outline", run.effort || "?"),
              el("span", "chip outline", run.topos ? "topos" : "notopos"));
  host.append(head, el("div", "detail-run", run.run));

  const dl = el("dl", "kv");
  const rows = [
    ["question", run.question_title || "–"],
    ["correct", run.correct == null ? "not graded yet" : run.correct ? "yes" : "no"],
    ["agent", run.agent_model || "?"],
    ["monitor", run.monitor_model || "?"],
    ["steps", `${run.n_steps} (${run.n_body_steps} body)`],
    ["STUCK", `${run.n_stuck} = ${pct(run.stuck_share)}`],
    ["final phase", run.final_phase || "–"],
    ["tool calls", num(run.mcp_call_count)],
    ["answer", run.answer_len ? `${run.answer_len} chars` : "empty"],
    ["sources", run.n_sources || 0],
    ["started", run.started || "–"],
  ];
  if (run.mcp_faulted_count != null) {
    rows.splice(9, 0, ["faulted", `${run.mcp_faulted_count} = ${pct(run.faulted_share)}`]);
  }
  if (Object.keys(run.tool_counts || {}).length) {
    rows.splice(10, 0, ["tools", Object.entries(run.tool_counts)
      .map(([t, n]) => `${t} x${n}`).join(", ")]);
  }
  if (run.research_loops != null) rows.push(["research loops", run.research_loops]);
  if (run.has_tokens) {
    rows.push(["agent tokens", num(run.agent_total)],
              ["monitor tokens", num(run.monitor_total)],
              ["monitor/agent", run.monitor_agent_ratio?.toFixed(2) ?? "–"]);
  }
  for (const [k, v] of Object.entries(run.extras || {})) {
    rows.push([k, typeof v === "object" ? JSON.stringify(v) : String(v)]);
  }
  for (const [k, v] of rows) {
    dl.append(el("dt", null, k), el("dd", null, String(v)));
  }
  host.append(dl);
  const answers = el("div", "answers");
  host.append(answers);
  loadAnswers(run).then(a => {
    if (state.sel !== sel) return;          // selection moved on while fetching
    answers.replaceChildren();
    if (a.prompt != null) answers.append(block("prompt", a.prompt));
    answers.append(
      block("agent answer", a.agent_answer || "", false,
            "this run produced no answer text"));
    if (a.expected_answer != null) {
      answers.append(block("expected answer", a.expected_answer));
    }
  }).catch(() => {});
  host.append(el("p", "axis-note",
    "Click a segment in any ribbon to read that step or call."));
}

/* --- experiment tabs ------------------------------------------------------ */
function renderTabs() {
  const host = document.getElementById("tabs");
  host.replaceChildren();
  for (const e of state.experiments) {
    const b = el("button", null, e.experiment);
    b.append(el("span", "n", `${e.n_runs}`));
    b.setAttribute("aria-current", String(e.experiment === state.experiment));
    b.onclick = () => { if (e.experiment !== state.experiment) load(e.experiment); };
    host.append(b);
  }
}

/* --- batch / model filters ----------------------------------------------- */
/* A row of buttons per folder level that actually varies in this family:
   batch (the question set, for benchmark_runs) and the model folder. */
const FILTERS = [["batch", "batch", r => r.batch, b => `batch ${b}`],
                 ["model", "model", r => r.model_group, m => m]];

function renderFilters() {
  const host = document.getElementById("filters");
  host.replaceChildren();
  for (const [key, label, get, name] of FILTERS) {
    const values = [...new Set(state.all.runs.map(get).filter(v => v != null))]
      .sort((a, b) => typeof a === "number" ? a - b : String(a).localeCompare(b));
    if (values.length < 2) continue;
    const box = el("div", "filter");
    box.append(el("span", null, label));
    const nav = el("nav", "tabs");
    for (const v of [null, ...values]) {
      const b = el("button", null, v == null ? "all" : name(v));
      b.append(el("span", "n",
        `${state.all.runs.filter(r => v == null || get(r) === v).length}`));
      b.setAttribute("aria-current", String(state.filter[key] === v));
      b.onclick = () => {
        if (state.filter[key] === v) return;
        state.filter[key] = v;
        render();
      };
      nav.append(b);
    }
    box.append(nav);
    host.append(box);
  }
  host.hidden = !host.children.length;
}

function applyFilter() {
  const keep = r => FILTERS.every(([key, , get]) =>
    state.filter[key] == null || get(r) === state.filter[key]);
  state.runs = state.all.runs.filter(keep);
  const names = new Set(state.runs.map(r => r.run));
  state.steps = state.all.steps.filter(s => names.has(s.run));
  state.calls = state.all.calls.filter(c => names.has(c.run));
  state.byRun = new Map(state.runs.map(r => [r.run, r]));
}

/* A family only gets a chart when it has the data behind it. */
function applyVisibility() {
  const hasCalls = state.calls.length > 0;
  const hasTokens = state.runs.some(r => r.has_tokens);
  document.getElementById("sec-calls").hidden = !hasCalls;
  document.getElementById("sec-tool-ribbon").hidden = !hasCalls;
  document.getElementById("sec-fault-ribbon").hidden =
    !state.runs.some(r => r.mcp_faulted_count != null);
  document.getElementById("sec-tokens").hidden = !hasTokens;
  return { hasCalls, hasTokens };
}

/* --- boot ----------------------------------------------------------------- */
async function load(experiment) {
  const census = document.getElementById("census");
  census.textContent = "loading…";
  let data;
  try {
    const url = experiment
      ? `/api/payload?experiment=${encodeURIComponent(experiment)}`
      : "/api/payload";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    data = await res.json();
  } catch (err) {
    census.textContent = `could not load data: ${err.message}`;
    census.style.color = css("alarm");
    return;
  }
  census.style.color = "";

  state.experiments = data.experiments || [];
  // no experiment asked for yet: show the biggest family
  if (!experiment && state.experiments.length) {
    const biggest = [...state.experiments].sort((a, b) => b.n_runs - a.n_runs)[0];
    return load(biggest.experiment);
  }
  if (experiment !== state.experiment) {
    state.sel = null;
    state.filter = { batch: null, model: null };
  }
  state.experiment = experiment;
  state.all = { runs: data.runs, steps: data.steps, calls: data.calls };

  const s = data.sync || {};
  state.changed = [
    s.added?.length ? `+${s.added.length} new` : null,
    s.updated?.length ? `~${s.updated.length} updated` : null,
    s.removed?.length ? `-${s.removed.length} removed` : null,
  ].filter(Boolean).join(", ");
  renderTabs();
  render();
}

/* Draw the current family through the current filters. */
function render() {
  applyFilter();
  renderFilters();
  const vis = applyVisibility();
  document.getElementById("census").textContent =
    `${state.runs.length} runs · ${state.steps.length} steps`
    + (vis.hasCalls ? ` · ${state.calls.length} tool calls` : "")
    + (rightOf(state.runs) ? ` · ${rightOf(state.runs)}` : "")
    + (state.changed ? `  (resync: ${state.changed})` : "");
  renderDesign();
  renderPhaseRibbon();
  renderStuckPlot();
  if (vis.hasTokens) renderTokenBars();
  if (vis.hasCalls) { renderCallBars(); renderToolRibbon(); renderFaultRibbon(); }

  // keep the current selection if its run survived the resync
  select(state.sel && state.byRun.has(state.sel.run) ? state.sel : null);
}

document.getElementById("reload").onclick = () => load(state.experiment);
load(null);
