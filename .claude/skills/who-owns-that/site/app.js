"use strict";

const SLACK = "https://rover.enterprise.slack.com/archives/";
const ASSETS_OBJECT = "https://roverdotcom.atlassian.net/jira/assets/object/";
const GITHUB = "https://github.com/roverdotcom/web/blob/";
const RUNBOOK = "https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/1961002737/Updating+Technology+Components";
const OVERVIEW = "https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/4123002944/Technology+Components";
const CHANGE_FORM = "https://roverdotcom.atlassian.net/servicedesk/customer/portal/29/group/124/create/535";

const KIND_BOOST = { team: 1.15, subconcept: 1.1, component: 1.0, code: 0.8 };
const RESULTS_LIMIT = 25;
const CODE_LIMIT = 15;

const $ = (sel) => document.querySelector(sel);
const view = $("#view");
const input = $("#q");

let DATA = null;
let DOCS = [];
const teamsByName = new Map();
const subsByName = new Map();
const componentsBySub = new Map();
const subsByTeam = new Map();
const driftBySub = new Map();

// ---------- text helpers ----------

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function words(s) {
  return String(s ?? "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .toLowerCase()
    .replace(/&/g, " and ")
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

function flat(s) {
  return String(s ?? "").toLowerCase();
}

function editDistance(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  let prevPrev = null;
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let rowMin = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      let v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      if (prevPrev && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        v = Math.min(v, prevPrev[j - 2] + 1);
      }
      cur.push(v);
      rowMin = Math.min(rowMin, v);
    }
    if (rowMin > max) return max + 1;
    prevPrev = prev;
    prev = cur;
  }
  return prev[b.length];
}

function isSubsequence(t, w) {
  if (w[0] !== t[0]) return false;
  let i = 0;
  for (const ch of w) if (ch === t[i] && ++i === t.length) return true;
  return false;
}

// How well one query token matches one field, 0..1.
function tokenScore(t, field) {
  let best = 0;
  for (const w of field.words) {
    if (w === t) return 1;
    if (t.length >= 2 && w.startsWith(t)) best = Math.max(best, 0.85);
  }
  if (best) return best;
  if (t.length >= 3 && field.flat.includes(t)) return 0.6;
  if (t.length >= 4) {
    const max = t.length >= 7 ? 2 : 1;
    for (const w of field.words) {
      if (w.length < 3) continue;
      if (editDistance(t, w, max) <= max || (w.length > t.length && editDistance(t, w.slice(0, t.length), max) <= max)) {
        return 0.5;
      }
    }
  }
  if (t.length >= 3) for (const w of field.words) if (isSubsequence(t, w)) return 0.3;
  return 0;
}

function scoreDoc(doc, tokens, raw, lenient) {
  let total = 0;
  let matched = 0;
  for (const t of tokens) {
    let best = 0;
    for (const f of doc.fields) best = Math.max(best, tokenScore(t, f) * f.w);
    if (best === 0 && !lenient) return 0;
    if (best > 0) matched++;
    total += best;
  }
  if (lenient && matched < Math.ceil(tokens.length / 2)) return 0;
  if (raw.length >= 3) {
    for (const f of doc.fields) {
      if (f.flat === raw) { total += 4 * f.w; break; }
      if (f.flat.includes(raw)) { total += 1.5 * f.w; break; }
    }
  }
  total *= KIND_BOOST[doc.kind];
  if (doc.retired) total *= 0.6;
  return total / Math.max(1, tokens.length);
}

function field(text, w) {
  return { w, words: words(text), flat: flat(text) };
}

function highlight(text, tokens) {
  let html = esc(text);
  const parts = tokens.filter((t) => t.length >= 2).sort((a, b) => b.length - a.length);
  if (!parts.length) return html;
  const re = new RegExp("(" + parts.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")", "gi");
  return html.replace(/(<[^>]+>)|([^<]+)/g, (m, tag, txt) => (tag ? tag : txt.replace(re, "<mark>$1</mark>")));
}

// ---------- data ----------

function link(kind, value) {
  return `#${kind}=${encodeURIComponent(value)}`;
}

function teamPill(name) {
  if (!name) return `<span class="chip retired">No owner</span>`;
  return `<a class="team-pill" href="${link("team", name)}">${esc(name)}</a>`;
}

function slackLink(team, label) {
  const t = teamsByName.get(team);
  if (!t || !t.slack) return "";
  return `<a class="slack" href="${SLACK}${esc(t.slack)}" target="_blank" rel="noopener">${label || "Slack"}</a>`;
}

function statusChip(status) {
  return status && status !== "Active" ? `<span class="chip retired">${esc(status)}</span>` : "";
}

function index(data) {
  for (const t of data.teams) teamsByName.set(t.name, t);
  for (const s of data.subconcepts) {
    subsByName.set(s.name, s);
    if (s.team) {
      if (!subsByTeam.has(s.team)) subsByTeam.set(s.team, []);
      subsByTeam.get(s.team).push(s);
    }
  }
  for (const c of data.components) {
    if (!componentsBySub.has(c.subconcept)) componentsBySub.set(c.subconcept, []);
    componentsBySub.get(c.subconcept).push(c);
  }
  for (const d of data.drift) driftBySub.set(d.subconcept, d);

  for (const s of data.subconcepts) {
    DOCS.push({
      kind: "subconcept",
      ref: s,
      retired: s.status && s.status !== "Active",
      fields: [
        field(s.short, 3),
        field(s.name, 2.5),
        field((s.codeKeys || []).join(" "), 2),
        field(s.description, 1.4),
        field(s.rationale, 0.5),
      ],
    });
  }
  for (const c of data.components) {
    DOCS.push({
      kind: "component",
      ref: c,
      retired: c.status && c.status !== "Active",
      fields: [field(c.short, 3), field(c.name, 2), field(c.description, 1.4), field(c.type, 0.6)],
    });
  }
  for (const t of data.teams) {
    DOCS.push({
      kind: "team",
      ref: t,
      retired: t.status && t.status !== "Active",
      fields: [field(t.name, 3), field(t.context, 2), field(t.jiraComponent, 1), field(t.parent, 0.4)],
    });
  }
  for (const [sub, rows] of Object.entries(data.code)) {
    for (const [path, line, symbol] of rows) {
      DOCS.push({
        kind: "code",
        ref: { path, line, symbol, sub },
        fields: [field(symbol, 2.5), field(path, 2)],
      });
    }
  }
}

function ownerOf(subName) {
  return subsByName.get(subName)?.team;
}

function codeHref(path, line) {
  return `${GITHUB}${DATA.source.webSha || "master"}/${path}#L${line}`;
}

// ---------- renderers ----------

function componentCard(c, tokens = []) {
  const desc = c.description ? `<div class="card-desc">${highlight(c.description, tokens)}</div>` : "";
  return `<div class="card">
    <div class="card-top">
      <a class="card-title stretched" href="${link("sub", c.subconcept)}">${highlight(c.short || c.name, tokens)}</a>
      <span class="chip">${esc(c.type || "Component")}</span>${statusChip(c.status)}
      <span class="card-owner">${teamPill(c.team || ownerOf(c.subconcept))}</span>
    </div>
    <div class="card-sub">${esc(c.subconcept || c.concept || "")}</div>${desc}
  </div>`;
}

function subconceptCard(s, tokens = []) {
  const n = (componentsBySub.get(s.name) || []).length;
  const code = (DATA.code[s.name] || []).length;
  const counts = [n && `${n} component${n === 1 ? "" : "s"}`, code && `${code} tagged code symbol${code === 1 ? "" : "s"}`]
    .filter(Boolean)
    .join(" · ");
  return `<div class="card">
    <div class="card-top">
      <a class="card-title stretched" href="${link("sub", s.name)}">${highlight(s.name, tokens)}</a>
      <span class="chip">Subconcept</span>${statusChip(s.status)}
      <span class="card-owner">${teamPill(s.team)}</span>
    </div>
    ${s.description ? `<div class="card-desc">${highlight(s.description, tokens)}</div>` : ""}
    ${counts ? `<div class="card-sub">${counts}</div>` : ""}
  </div>`;
}

function teamCard(t, tokens = []) {
  const subs = subsByTeam.get(t.name) || [];
  const comps = subs.reduce((n, s) => n + (componentsBySub.get(s.name) || []).length, 0);
  const aka = t.context ? ` · aka ${highlight(t.context, tokens)}` : "";
  return `<div class="card">
    <div class="card-top">
      <a class="card-title stretched" href="${link("team", t.name)}">${highlight(t.name, tokens)}</a>
      <span class="chip">Team</span>${statusChip(t.status)}
    </div>
    <div class="card-sub">Owns ${subs.length} subconcept${subs.length === 1 ? "" : "s"} and ${comps} component${comps === 1 ? "" : "s"}${aka}</div>
  </div>`;
}

function codeRow(r, tokens = [], showOwner = true) {
  const owner = ownerOf(r.sub);
  return `<a class="code-row" href="${codeHref(r.path, r.line)}" target="_blank" rel="noopener" title="${esc(r.sub)}">
    ${r.symbol ? `<span class="sym">${highlight(r.symbol, tokens)}</span>` : ""}
    <span class="path">${highlight(r.path, tokens)}:${r.line}</span>
    ${showOwner ? `<span class="own">${esc(owner || "No owner")} · ${esc(r.sub.split(": ").pop())}</span>` : ""}
  </a>`;
}

function renderCard(doc, tokens) {
  if (doc.kind === "component") return componentCard(doc.ref, tokens);
  if (doc.kind === "subconcept") return subconceptCard(doc.ref, tokens);
  if (doc.kind === "team") return teamCard(doc.ref, tokens);
  return codeRow(doc.ref, tokens);
}

function renderSearch(q) {
  const raw = flat(q).trim();
  const tokens = words(q);
  if (!tokens.length) return renderHome();

  // "sign up" should also find "Signup", so score the joined words as one token too.
  const joined = tokens.length > 1 ? [tokens.join("")] : null;
  const score = (d, lenient) =>
    Math.max(scoreDoc(d, tokens, raw, lenient), joined ? scoreDoc(d, joined, raw, false) * 1.05 : 0);
  let scored = DOCS.map((d) => [score(d, false), d]).filter(([s]) => s > 0);
  let lenient = false;
  if (scored.filter(([, d]) => d.kind !== "code").length < 3) {
    lenient = true;
    scored = DOCS.map((d) => [score(d, true), d]).filter(([s]) => s > 0);
  }
  const looksLikeCode = !/\s/.test(q.trim()) && /[\/._]|[a-z][A-Z]/.test(q.trim());
  scored.sort((a, b) => b[0] - a[0]);
  const main = scored.filter(([, d]) => d.kind !== "code");
  const code = scored.filter(([, d]) => d.kind === "code");

  if (!main.length && !code.length) {
    view.innerHTML = `<p class="empty">Nothing matched <b>${esc(q)}</b>. Try fewer or different words, a file path, or
      <a href="#teams">browse by team</a>. If it really isn't here, ask in
      <a href="${SLACK}CU7G1BZHS" target="_blank" rel="noopener">#who-owns-that</a>.</p>`;
    return;
  }

  let mainHtml = "";
  if (main.length) {
    mainHtml += `<h2>${lenient ? "Closest matches" : "Matches"}</h2><div class="results">`;
    mainHtml += main.slice(0, RESULTS_LIMIT).map(([, d]) => renderCard(d, tokens)).join("");
    mainHtml += `</div>`;
  }
  let codeHtml = "";
  if (code.length) {
    codeHtml += `<h2>Tagged code (${code.length})</h2>
      <p class="muted small">Classes and functions in <code>web</code> tagged with <code>CONCEPTS.&lt;concept&gt;.&lt;subconcept&gt;</code>. The owner is the subconcept's team.</p>
      <div class="code-list" id="code-results">${code.slice(0, CODE_LIMIT).map(([, d]) => codeRow(d.ref, tokens)).join("")}</div>`;
    if (code.length > CODE_LIMIT) codeHtml += `<button class="btn more" id="more-code">Show all ${code.length}</button>`;
  }
  view.innerHTML = looksLikeCode && code.length ? codeHtml + mainHtml : mainHtml + codeHtml;
  $("#more-code")?.addEventListener("click", (e) => {
    $("#code-results").innerHTML = code.map(([, d]) => codeRow(d.ref, tokens)).join("");
    e.target.remove();
  });
}

function renderHome() {
  const examples = ["cancellation page", "rebook", "stripe", "background check", "inbox", "account_inbox/views.py", "datadog", "sitter search"];
  view.innerHTML = `
    <p class="muted">Try: ${examples.map((e) => `<a href="${link("q", e)}">${esc(e)}</a>`).join(" · ")}</p>
    <h2>Browse by team</h2>
    ${teamGrid()}
  `;
}

function teamGrid() {
  const teams = [...DATA.teams].sort((a, b) => (subsByTeam.get(b.name) || []).length - (subsByTeam.get(a.name) || []).length);
  return `<div class="team-grid">${teams
    .map((t) => {
      const subs = subsByTeam.get(t.name) || [];
      const comps = subs.reduce((n, s) => n + (componentsBySub.get(s.name) || []).length, 0);
      return `<a class="team-tile" href="${link("team", t.name)}"><b>${esc(t.name)} ${statusChip(t.status)}</b>
        <span>${subs.length} subconcepts · ${comps} components</span></a>`;
    })
    .join("")}</div>`;
}

function renderTeams() {
  view.innerHTML = `<h1 class="page">Teams</h1>
    <p class="lede">Every team that owns at least one subconcept or component, with the most ownership first.</p>
    ${teamGrid()}`;
}

function renderTeam(name) {
  const t = teamsByName.get(name);
  if (!t) return notFound("team", name);
  const subs = [...(subsByTeam.get(name) || [])].sort((a, b) => a.name.localeCompare(b.name));
  const ownedSubNames = new Set(subs.map((s) => s.name));
  const strays = DATA.components.filter((c) => c.team === name && !ownedSubNames.has(c.subconcept));
  const drift = DATA.drift.filter((d) => d.assetsTeam === name || d.taxonomyTeam === name);
  const codeCount = subs.reduce((n, s) => n + (DATA.code[s.name] || []).length, 0);
  const compCount = subs.reduce((n, s) => n + (componentsBySub.get(s.name) || []).length, 0);

  const facts = [
    t.dri && `<span>DRI <b>${esc(t.dri.replace(/\s*\(.*\)$/, ""))}</b></span>`,
    t.parent && `<span>Part of <b>${esc(t.parent)}</b></span>`,
    t.context && `<span>Also known as <b>${esc(t.context)}</b></span>`,
    t.jiraComponent && `<span>Jira component <b>${esc(t.jiraComponent)}</b></span>`,
  ].filter(Boolean);

  view.innerHTML = `
    <h1 class="page">${esc(t.name)} ${statusChip(t.status)}</h1>
    <p class="lede">Owns ${subs.length} subconcepts, ${compCount} components and ${codeCount} tagged code symbols.</p>
    <div class="facts">${facts.join("")}</div>
    <div class="actions">
      ${t.slack ? `<a class="btn primary" href="${SLACK}${esc(t.slack)}" target="_blank" rel="noopener">Open team Slack channel</a>` : ""}
      ${t.confluence ? `<a class="btn" href="${esc(t.confluence)}" target="_blank" rel="noopener">Confluence</a>` : ""}
      ${t.id ? `<a class="btn" href="${ASSETS_OBJECT}${esc(t.id)}" target="_blank" rel="noopener">People Directory entry</a>` : ""}
    </div>
    ${t.missingFromDirectory ? `<div class="callout">This team owns things in Technology Components but has no entry in the People Directory.</div>` : ""}
    ${t.status && t.status !== "Active" ? `<div class="callout">The People Directory marks this team <b>${esc(t.status)}</b>, but it still owns the subconcepts below. They probably need a new owner.</div>` : ""}
    ${drift.length ? `<div class="callout">${drift.length} of this team's subconcepts have a different owner in <code>taxonomy.yml</code>. See <a href="#drift">drift</a>.</div>` : ""}
    <h2>Subconcepts and components</h2>
    ${subs.map(subBlock).join("") || `<p class="empty">No subconcepts.</p>`}
    ${strays.length ? `<h2>Components listed under another team's subconcept</h2><div class="results">${strays.map((c) => componentCard(c)).join("")}</div>` : ""}
  `;
}

function subBlock(s) {
  const comps = componentsBySub.get(s.name) || [];
  const code = (DATA.code[s.name] || []).length;
  return `<div class="sub-block">
    <h3><a href="${link("sub", s.name)}">${esc(s.name)}</a> ${statusChip(s.status)}</h3>
    ${s.description ? `<p>${esc(s.description)}</p>` : ""}
    ${comps.length ? `<ul class="comp-list">${comps.map((c) => `<li>${esc(c.short || c.name)}<span class="type">${esc(c.type || "")}</span></li>`).join("")}</ul>` : ""}
    ${code ? `<p class="small"><a href="${link("sub", s.name)}">${code} tagged code symbols</a></p>` : ""}
  </div>`;
}

function renderSub(name) {
  const s = subsByName.get(name);
  if (!s) return notFound("subconcept", name);
  const comps = componentsBySub.get(name) || [];
  const code = (DATA.code[name] || []).map(([path, line, symbol]) => ({ path, line, symbol, sub: name }));
  const drift = driftBySub.get(name);
  const facts = [
    s.concept && `<span>Concept <b>${esc(s.concept)}</b></span>`,
    s.codeKeys?.length && `<span>In code <b>${s.codeKeys.map((k) => `<code>CONCEPTS.${esc(k)}</code>`).join(", ")}</b></span>`,
    s.wiz && `<span>Open WIZ tickets <b>${esc(s.wiz)}</b></span>`,
    s.complexity && `<span>Complexity <b>${esc(s.complexity)}</b></span>`,
  ].filter(Boolean);

  view.innerHTML = `
    <h1 class="page">${esc(s.name)} ${statusChip(s.status)}</h1>
    ${s.description ? `<p class="lede">${esc(s.description)}</p>` : ""}
    <div class="actions">${teamPill(s.team)} ${slackLink(s.team, "Team Slack channel")}
      <a class="slack" href="${ASSETS_OBJECT}${esc(s.id)}" target="_blank" rel="noopener">Open in Jira Assets</a></div>
    <div class="facts">${facts.join("")}</div>
    ${s.rationale ? `<div class="callout info"><b>Why this team:</b> ${esc(s.rationale)}</div>` : ""}
    ${drift ? `<div class="callout"><code>taxonomy.yml</code> in <code>web</code> says <b>${esc(drift.taxonomyTeam)}</b> owns this, but Jira Assets says <b>${esc(drift.assetsTeam)}</b>. Code metrics, SLOs and alerts follow <code>taxonomy.yml</code>.</div>` : ""}
    <h2>Components (${comps.length})</h2>
    ${comps.length ? `<div class="results">${comps.map((c) => componentCard(c)).join("")}</div>` : `<p class="empty">No components listed.</p>`}
    <h2>Tagged code (${code.length})</h2>
    ${code.length ? `<div class="code-list">${code.map((r) => codeRow(r, [], false)).join("")}</div>` : `<p class="empty">Nothing in <code>web</code> is tagged with this subconcept.</p>`}
  `;
}

function renderDrift() {
  const unowned = DATA.subconcepts.filter((s) => !s.team && s.status === "Active");
  const retiredOwners = DATA.subconcepts.filter((s) => s.status === "Active" && teamsByName.get(s.team)?.status === "Retired");
  view.innerHTML = `
    <h1 class="page">Drift</h1>
    <p class="lede">Ownership lives in two places. Jira Assets is the source of truth, and
      <code>taxonomy.yml</code> in <code>web</code> tags code for dashboards, SLOs and alerts.
      The <a href="${RUNBOOK}" target="_blank" rel="noopener">update runbook</a> says to change both. These are the places they disagree.</p>
    <h2>Different owner (${DATA.drift.length})</h2>
    ${DATA.drift.length ? `<div class="table-scroll"><table class="drift"><thead><tr><th>Subconcept</th><th>Jira Assets</th><th>taxonomy.yml</th></tr></thead><tbody>
      ${DATA.drift.map((d) => `<tr><td><a href="${link("sub", d.subconcept)}">${esc(d.subconcept)}</a><div class="muted small"><code>CONCEPTS.${esc(d.codeKey)}</code></div></td><td>${teamPill(d.assetsTeam)}</td><td>${esc(d.taxonomyTeam)}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="empty">None. They agree.</p>`}
    <h2>In taxonomy.yml, missing from Jira Assets (${DATA.unmatchedTaxonomy.length})</h2>
    ${DATA.unmatchedTaxonomy.length ? `<div class="table-scroll"><table class="drift"><thead><tr><th>taxonomy.yml subconcept</th><th>Owner in taxonomy.yml</th></tr></thead><tbody>
      ${DATA.unmatchedTaxonomy.map((u) => `<tr><td>${esc(u.taxonomyName)}<div class="muted small"><code>CONCEPTS.${esc(u.codeKey)}</code></div></td><td>${esc(u.taxonomyTeam)}</td></tr>`).join("")}
    </tbody></table></div><p class="muted small">Either the name differs between the two, or the subconcept was never added to Assets.</p>` : `<p class="empty">None.</p>`}
    <h2>Active subconcepts owned by a retired team (${retiredOwners.length})</h2>
    ${retiredOwners.length ? `<div class="results">${retiredOwners.map((s) => subconceptCard(s)).join("")}</div>` : `<p class="empty">None.</p>`}
    <h2>Active subconcepts with no owner (${unowned.length})</h2>
    ${unowned.length ? `<div class="results">${unowned.map((s) => subconceptCard(s)).join("")}</div>` : `<p class="empty">None.</p>`}
  `;
}

function renderAbout() {
  const gen = new Date(DATA.generatedAt);
  view.innerHTML = `<div class="prose">
    <h1 class="page">About this data</h1>
    <p class="lede">This site is a read-only, searchable copy of Rover's ownership mapping. It changes nothing; to change who owns something, edit Jira Assets.</p>

    <h2>Where it comes from</h2>
    <div class="flow">
      <div><b>Before Sep 2025</b>A Google Sheet, now read-only.</div>
      <div><b>Q3 2025 Maker Days</b>Imported into Jira Assets as the <a href="${OVERVIEW}" target="_blank" rel="noopener">Technology Components</a> schema.</div>
      <div><b>Jira Assets</b>Concept → Subconcept → Component. Each subconcept has exactly one owning team.</div>
      <div><b>web/taxonomy.yml</b>The same subconcepts, used to tag code with <code>CONCEPTS.x.y</code>.</div>
      <div><b>This site</b>Joins both, plus team Slack channels from the People Directory.</div>
    </div>
    <ul>
      <li><b>Subconcepts, components, concepts:</b> Jira Assets schema 42, Technology Components.</li>
      <li><b>Teams:</b> Jira Assets People Directory → Groups (Slack channel, DRI, parent team, former names).</li>
      <li><b>Tagged code:</b> every <code>CONCEPTS.&lt;concept&gt;.&lt;subconcept&gt;</code> reference in <code>web</code>, outside tests and migrations, credited to its enclosing class or function. TypeScript symbols are a best guess from the nearest declaration.</li>
    </ul>

    <h2>Changing who owns something</h2>
    <p>EMs edit <a href="${DATA.source.assets}?typeId=33&view=list" target="_blank" rel="noopener">Jira Assets</a> directly, then do the downstream steps in the
      <a href="${RUNBOOK}" target="_blank" rel="noopener">Updating Technology Components runbook</a> (taxonomy.yml, alerts, CWV mapping, Jira components).
      There is also a <a href="${CHANGE_FORM}" target="_blank" rel="noopener">concept/subconcept change request form</a>.
      This site picks up the change the next time it is refreshed.</p>

    <h2>How this site is refreshed</h2>
    <p>Today it is refreshed by hand. Last refresh: <b>${esc(gen.toLocaleString())}</b>, from <code>web</code> at
      <a href="https://github.com/roverdotcom/web/commit/${esc(DATA.source.webSha)}" target="_blank" rel="noopener"><code>${esc((DATA.source.webSha || "").slice(0, 10))}</code></a>.</p>
    <p>The <code>who-owns-that</code> Claude skill does it in one step. Ask Claude to <i>"refresh the who-owns-that site"</i>. It:</p>
    <ol>
      <li>Exports the Technology Components schema and the People Directory Groups through the Atlassian MCP (two AQL queries).</li>
      <li>Runs <code>scripts/build.py</code>, which joins them with <code>taxonomy.yml</code> and the code tags into <code>data.json</code>.</li>
      <li>Publishes with <code>yard publish</code>.</li>
    </ol>
    <p>The skill lives in Adam Pacholski's dotfiles. Every publish also includes a copy under
      <a href="_source/SKILL.md"><code>_source/</code></a>: <a href="_source/SKILL.md"><code>SKILL.md</code></a>,
      <a href="_source/scripts/build.py"><code>scripts/build.py</code></a> and <code>site/</code>. To get it on a new machine:</p>
    <pre>gh api /repos/roverdotcom/yard/contents/install.sh -H "Accept: application/vnd.github.raw" | bash
yard login --device-code
yard pull who-owns-that ./who-owns-that</pre>
    <p>Then point an agent at <code>./who-owns-that/_source/SKILL.md</code>, or run it yourself without Claude using an Atlassian API token:</p>
    <pre>cd who-owns-that/_source
ATLASSIAN_EMAIL=you@rover.com ATLASSIAN_API_TOKEN=… \\
  python3 scripts/build.py --from-api --web ~/web --out dist
yard publish dist who-owns-that --yes</pre>

    <h2>Automating it later</h2>
    <ul>
      <li><b>Nightly GitHub Action:</b> the same <code>build.py --from-api</code> with an Atlassian service-account token as a repo secret, then <code>YARD_CI=true yard publish</code>. Yard authenticates the workflow by OIDC, so no Yard credential is stored.</li>
      <li><b>On change:</b> a Jira Assets automation rule ("object updated" in schema 42) triggers that workflow through <code>repository_dispatch</code>.</li>
      <li><b>On merge:</b> the same workflow runs when <code>taxonomy.yml</code> changes on <code>master</code>, so the drift page stays current.</li>
    </ul>
  </div>`;
}

function notFound(kind, name) {
  view.innerHTML = `<p class="empty">No ${kind} named <b>${esc(name)}</b>. <a href="#">Back to search</a>.</p>`;
}

// ---------- routing ----------

function route() {
  const hash = decodeURIComponent(location.hash.slice(1));
  const [key, ...rest] = hash.split("=");
  const value = rest.join("=");
  document.querySelectorAll(".topnav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${key}`));
  if (key === "q") {
    if (input.value !== value) input.value = value;
    return renderSearch(value);
  }
  input.value = "";
  if (key === "team") return renderTeam(value);
  if (key === "sub") return renderSub(value);
  if (key === "teams") return renderTeams();
  if (key === "drift") return renderDrift();
  if (key === "about") return renderAbout();
  renderHome();
}

let timer = null;
input.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    const q = input.value;
    history.replaceState(null, "", q.trim() ? link("q", q) : location.pathname);
    route();
    window.scrollTo({ top: 0 });
  }, 60);
});

document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== input) {
    e.preventDefault();
    input.focus();
    input.select();
    return;
  }
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Enter") return;
  const items = [...view.querySelectorAll("a.stretched, a.code-row")];
  if (!items.length) return;
  const box = (el) => el.closest(".card") || el;
  const current = items.findIndex((el) => box(el).classList.contains("active"));
  if (e.key === "Enter") {
    if (current >= 0) { e.preventDefault(); items[current].click(); }
    else if (document.activeElement === input) { e.preventDefault(); items[0].click(); }
    return;
  }
  e.preventDefault();
  const next = e.key === "ArrowDown" ? Math.min(items.length - 1, current + 1) : Math.max(0, current - 1);
  items.forEach((el) => box(el).classList.remove("active"));
  box(items[next]).classList.add("active");
  box(items[next]).scrollIntoView({ block: "nearest" });
});

window.addEventListener("hashchange", route);

fetch("data.json")
  .then((r) => r.json())
  .then((data) => {
    DATA = data;
    index(data);
    const when = new Date(data.generatedAt);
    $("#freshness").innerHTML = `${data.subconcepts.length} subconcepts, ${data.components.length} components and ${DOCS.filter((d) => d.kind === "code").length} tagged code symbols. Refreshed ${esc(when.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }))}. <a href="#about">How this works</a>`;
    route();
  })
  .catch((err) => {
    view.innerHTML = `<p class="empty">Could not load data.json: ${esc(err.message)}</p>`;
  });
