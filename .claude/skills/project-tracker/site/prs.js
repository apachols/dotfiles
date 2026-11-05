"use strict";

// The PR list comes from data.json, which `tracker.py pr-discover` fills. The reader's
// choices live in the shared store as pr.<number> = { priority, hidden, track }, and
// the next discovery run reads them: a priority set here wins over the agent's, and
// "Add to Sources" makes the next update start a change log for the PR.

const Prs = (() => {
  const PREFIX = "pr.";
  const API = "/_yard/v1/shared/";
  const JIRA = "https://roverdotcom.atlassian.net/browse/";
  const SECTIONS = [
    [1, "P1 · Needs you", "Review requests, mentions, project PRs you have reviewed."],
    [2, "P2 · Keep current", "Project work worth reading to stay up to date."],
    [3, "P3 · Everything else", "Teammates' PRs for other tickets, bots."],
    [null, "Not classified yet", "The next update judges these."],
  ];

  const state = {
    overrides: {}, // number -> { rec, version }
    loaded: false,
    error: null,
    show: "open",
    showHidden: false,
    busy: {},
    notices: {},
  };
  let view = null;

  // ---------------------------------------------------------------- store

  async function getKey(key) {
    const r = await fetch(API + encodeURIComponent(key), { cache: "no-store" });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(`GET ${key}: ${r.status}`);
    const env = await r.json();
    return { rec: JSON.parse(env.value), version: env.version };
  }

  async function load() {
    const r = await fetch(API.slice(0, -1), { cache: "no-store" });
    if (!r.ok) throw new Error(`could not read PR choices (${r.status})`);
    const keys = (await r.json()).keys.filter((k) => k.key.startsWith(PREFIX));
    const next = {};
    await Promise.all(keys.map(async (k) => {
      const number = Number(k.key.slice(PREFIX.length));
      const cached = state.overrides[number];
      if (cached && cached.version === k.version) next[number] = cached;
      else {
        const item = await getKey(k.key);
        if (item) next[number] = item;
      }
    }));
    state.overrides = next;
    state.loaded = true;
    state.error = null;
  }

  // Re-read before each write and send its version, so two tabs (or two people)
  // changing different fields of the same PR both keep their change.
  async function change(number, patch) {
    state.busy[number] = true;
    delete state.notices[number];
    paint();
    try {
      for (let attempt = 0; attempt < 4; attempt++) {
        const latest = await getKey(PREFIX + number);
        const rec = { number, priority: null, hidden: false, track: false, ...(latest?.rec || {}), ...patch };
        rec.updated = new Date().toISOString().replace(/\.\d+Z$/, "Z");
        const r = await fetch(API + encodeURIComponent(PREFIX + number), {
          method: "PUT",
          headers: { "Content-Type": "application/json", "If-Match": latest ? `"${latest.version}"` : "*" },
          body: JSON.stringify(rec),
        });
        if (r.status === 412) continue;
        if (!r.ok) throw new Error(`save failed (${r.status})`);
        const saved = await getKey(PREFIX + number);
        if (saved) state.overrides[number] = saved;
        return;
      }
      throw new Error("someone else kept changing this PR; reload and try again");
    } catch (err) {
      state.notices[number] = err.message;
    } finally {
      delete state.busy[number];
      paint();
    }
  }

  // ---------------------------------------------------------------- helpers

  function choice(pr) {
    return state.overrides[pr.number]?.rec || {};
  }

  function priorityOf(pr) {
    const p = choice(pr).priority;
    return [1, 2, 3].includes(p) ? p : (pr.priority ?? null);
  }

  function visible(prs) {
    return prs.filter((pr) => (state.show === "open" ? pr.state === "open" : pr.state !== "open"));
  }

  // ---------------------------------------------------------------- views

  function row(pr) {
    const c = choice(pr);
    const p = priorityOf(pr);
    const busy = state.busy[pr.number] ? "disabled" : "";
    const seg = (n) => `<button class="seg ${p === n ? "is-active" : ""}" data-pr="priority" data-n="${pr.number}" data-p="${n}" ${busy}>P${n}</button>`;
    const tickets = (pr.tickets || []).map((t) => external(JIRA + t, t)).join(" ");
    const why = [1, 2, 3].includes(c.priority) && c.priority !== pr.priority
      ? `You set P${c.priority}${pr.priority ? ` (the agent said P${pr.priority}: ${pr.reason})` : ""}`
      : pr.reason || "";
    let track = "";
    if (pr.doc) track = `<a href="#doc=${encodeURIComponent(pr.doc)}">In Sources: change log</a>`;
    else if (c.track) track = `<span class="pending">Joins Sources on the next update · <button class="linkish" data-pr="untrack" data-n="${pr.number}" ${busy}>undo</button></span>`;
    else if (pr.state === "open") track = `<button class="btn btn-small" data-pr="track" data-n="${pr.number}" ${busy}>Add to Sources</button>`;
    const closed = pr.state !== "open" ? `<span class="pill archived-pill">${esc(pr.state)} ${pr.closedAt ? esc(shortDate(pr.closedAt)) : ""}</span>` : "";
    return `
      <li class="pr ${c.hidden ? "is-hidden" : ""}">
        <div class="source-date">${esc(shortDate(pr.updatedAt))}</div>
        <div class="pr-body">
          ${state.notices[pr.number] ? `<p class="notice">${esc(state.notices[pr.number])}</p>` : ""}
          <div class="source-title">
            ${external(pr.url, pr.title)}
            ${pr.draft ? `<span class="pill archived-pill">Draft</span>` : ""}
            ${closed}
          </div>
          <div class="pr-meta">
            <span class="mono">#${pr.number}</span>
            <span>${esc(pr.author)}</span>
            ${tickets}
            ${why ? `<span class="pr-why">${esc(why)}</span>` : ""}
          </div>
          <div class="pr-actions">
            <div class="segmented" role="group" aria-label="Priority">${seg(1)}${seg(2)}${seg(3)}</div>
            ${track}
            <button class="btn btn-small" data-pr="${c.hidden ? "unhide" : "hide"}" data-n="${pr.number}" ${busy}>${c.hidden ? "Unhide" : "Hide"}</button>
          </div>
        </div>
      </li>`;
  }

  function html() {
    if (!DATA) return `<p class="empty">Loading…</p>`;
    const all = DATA.prs || [];
    if (!all.length) {
      return `<h1>Pull requests</h1><p class="empty">No PRs discovered yet. Run <code>tracker.py pr-discover</code> from a session.</p>`;
    }
    const shown = visible(all);
    const hiddenCount = shown.filter((pr) => choice(pr).hidden).length;
    const listed = state.showHidden ? shown : shown.filter((pr) => !choice(pr).hidden);
    const count = (s) => all.filter((pr) => (s === "open" ? pr.state === "open" : pr.state !== "open")).length;
    const seg = (s, label) => `<button class="seg ${state.show === s ? "is-active" : ""}" data-pr="show" data-show="${s}">${label} <span>${count(s)}</span></button>`;
    const sections = SECTIONS.map(([p, title, blurb]) => {
      const rows = listed.filter((pr) => priorityOf(pr) === p);
      if (!rows.length) return "";
      return `<h2 class="section-head">${esc(title)} <span class="count">${rows.length}</span></h2>
        <p class="section-blurb">${esc(blurb)}</p>
        <ul class="sources">${rows.map(row).join("")}</ul>`;
    }).join("");
    const discovered = DATA.prsDiscoveredAt ? `Discovered ${esc(stamp(DATA.prsDiscoveredAt))}` : "";
    return `
      <div class="page-head">
        <div>
          <h1>Pull requests</h1>
          <p class="meta">${discovered}<span>Priority, hide and Add to Sources choices are shared by everyone who opens this site.</span></p>
        </div>
      </div>
      ${state.error ? `<p class="notice">Could not load choices: ${esc(state.error)}</p>` : ""}
      <div class="toolbar">
        <div class="segmented">${seg("open", "Open")}${seg("closed", "Merged or closed")}</div>
        ${hiddenCount ? `<button class="btn btn-small" data-pr="toggle-hidden">${state.showHidden ? "Hide" : "Show"} ${hiddenCount} hidden</button>` : ""}
      </div>
      ${sections || `<p class="empty">Nothing here.</p>`}`;
  }

  function paint() {
    if (view && location.hash === "#prs") view.innerHTML = html();
  }

  async function refresh() {
    try {
      await load();
    } catch (err) {
      state.error = err.message;
    }
    paint();
  }

  // ---------------------------------------------------------------- events

  document.addEventListener("click", (event) => {
    const el = event.target.closest("[data-pr]");
    if (!el || location.hash !== "#prs") return;
    event.preventDefault();
    const n = Number(el.dataset.n);
    const action = el.dataset.pr;
    if (action === "show") state.show = el.dataset.show;
    else if (action === "toggle-hidden") state.showHidden = !state.showHidden;
    else if (action === "priority") return change(n, { priority: Number(el.dataset.p) });
    else if (action === "track") return change(n, { track: true });
    else if (action === "untrack") return change(n, { track: false });
    else if (action === "hide") return change(n, { hidden: true });
    else if (action === "unhide") return change(n, { hidden: false });
    paint();
  });

  window.addEventListener("focus", () => location.hash === "#prs" && refresh());

  return {
    mount(el) {
      view = el;
      paint();
      refresh();
    },
    repaint: paint,
  };
})();
