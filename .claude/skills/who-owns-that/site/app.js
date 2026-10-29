"use strict";

const SLACK = "https://rover.enterprise.slack.com/archives/";
const ASSETS_OBJECT = "https://roverdotcom.atlassian.net/jira/assets/object/";
const GITHUB = "https://github.com/roverdotcom/web/blob/";
const RUNBOOK = "https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/1961002737/Updating+Technology+Components";
const OVERVIEW = "https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/4123002944/Technology+Components";
const CHANGE_FORM = "https://roverdotcom.atlassian.net/servicedesk/customer/portal/29/group/124/create/535";

const GITHUB_TREE = "https://github.com/roverdotcom/web/tree/";
const CODEOWNERS_FILE = "https://github.com/roverdotcom/web/blob/master/.github/CODEOWNERS";
const CODEWATCHERS_FILE = "https://github.com/roverdotcom/web/blob/master/danger/CODEWATCHERS";

const KIND_BOOST = { team: 1.15, subconcept: 1.1, component: 1.0, route: 0.95, code: 0.8 };
const RESULTS_LIMIT = 25;
const CODE_LIMIT = 15;
const PATH_LIMIT = 8;
const TABLE_LIMIT = 40;
const PURITY_THRESHOLD = 0.8;
const SOURCE_LABEL = { codeowners: "CODEOWNERS", codewatchers: "CODEWATCHERS", concepts: "concept tag" };

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
const routesBySub = new Map();
const globsByTeam = new Map();
// Directory -> [owner set id, files directly in it], for directories that hold files.
const DIRS = new Map();
// Every directory, including ones that only hold other directories.
const ALL_DIRS = new Set();
// Files whose owners differ from their directory's.
const FILES = new Map();

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

// Why something has no owner depends on which source was asked.
const NO_OWNER = {
  assets: ["No team in Jira Assets", "Jira Assets lists no owning team for this subconcept."],
  unfiled: ["Not under a subconcept", "In Jira Assets this component sits directly under its concept, not under a subconcept, so no team owns it."],
  code: ["No code owner", "No CODEOWNERS or CODEWATCHERS rule matches, and no subconcept tagged in the file has a team."],
};

function noOwner(reason) {
  const [label, title] = NO_OWNER[reason];
  return `<span class="chip retired no-owner" title="${esc(title)}">${label}</span>`;
}

function teamPill(name, reason = "assets") {
  if (!name) return noOwner(reason);
  return `<a class="team-pill" href="${link("team", name)}">${esc(name)}</a>`;
}

function slackLink(team) {
  const t = teamsByName.get(team);
  if (!t || !t.slack) return "";
  return `<a class="slack" href="${SLACK}${esc(t.slack)}" target="_blank" rel="noopener">${t.slackName ? `#${esc(t.slackName)}` : "Team Slack channel"}</a>`;
}

function assetsLink(id, label = "Open in Jira Assets") {
  return `<a class="assets-link" href="${ASSETS_OBJECT}${esc(id)}" target="_blank" rel="noopener">${label}</a>`;
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
  for (const [kind, pattern, name, sub, path, line] of data.routes) {
    const r = { kind, pattern, name, sub, path, line };
    if (!routesBySub.has(sub)) routesBySub.set(sub, []);
    routesBySub.get(sub).push(r);
    DOCS.push({ kind: "route", ref: r, fields: [field(pattern, 3), field(name, 2.5), field(path, 1)] });
  }

  let prev = "";
  for (const [shared, rest, owners, n] of data.paths.dirs) {
    const dir = prev.slice(0, shared) + rest;
    DIRS.set(dir, [owners, n]);
    for (let d = dir; d && !ALL_DIRS.has(d); d = parentDir(d)) ALL_DIRS.add(d);
    prev = dir;
  }
  for (const [path, owners] of Object.entries(data.paths.files)) FILES.set(path, owners);
  for (const [glob, team, purity, files, owned] of data.paths.map) {
    if (!team) continue;
    if (!globsByTeam.has(team)) globsByTeam.set(team, []);
    globsByTeam.get(team).push([glob, team, purity, files, owned]);
  }
}

function ownerOf(subName) {
  return subsByName.get(subName)?.team;
}

function codeHref(path, line) {
  return `${GITHUB}${DATA.source.webSha || "master"}/${path}#L${line}`;
}

function parentDir(path) {
  const i = path.lastIndexOf("/");
  return i < 0 ? "" : path.slice(0, i);
}

function plural(n, word) {
  return `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
}

function pct(part, whole) {
  return whole ? `${Math.round((100 * part) / whole)}%` : "0%";
}

// ---------- code paths ----------

function ownersOfFile(path) {
  if (FILES.has(path)) return FILES.get(path);
  return DIRS.get(parentDir(path))?.[0] ?? 0;
}

function primaryOf(ownerSet) {
  return DATA.paths.owners[ownerSet][0]?.[0] || null;
}

// Files under dir counted by primary owner ("" for no owner), most first.
function rollup(dir) {
  const prefix = dir ? dir + "/" : "";
  const counts = new Map();
  let total = 0;
  const add = (ownerSet, n) => {
    const team = primaryOf(ownerSet) || "";
    counts.set(team, (counts.get(team) || 0) + n);
    total += n;
  };
  for (const [d, [owners, n]] of DIRS) if (d === dir || d.startsWith(prefix)) add(owners, n);
  for (const [f, owners] of FILES) {
    if (!f.startsWith(prefix)) continue;
    add(DIRS.get(parentDir(f))[0], -1);
    add(owners, 1);
  }
  return { total, counts: [...counts].filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]) };
}

function cleanPathQuery(q) {
  return q
    .trim()
    .replace(/^https?:\/\/github\.com\/roverdotcom\/web\/(?:blob|tree)\/[^/]+\//, "")
    .replace(/#L\d+.*$/, "")
    .replace(/:\d+(?::\d+)?$/, "")
    .replace(/^(?:\.\/|\/)+/, "")
    .replace(/^web\//, "")
    .replace(/\/+$/, "");
}

function looksLikePath(q) {
  const t = q.trim();
  return !!t && !/\s/.test(t) && (t.includes("/") || /\.[a-z0-9]{1,5}$/i.test(t));
}

function pathMatches(q) {
  const p = cleanPathQuery(q);
  if (!p) return [];
  const out = [];
  const seen = new Set();
  const push = (m) => {
    if (!seen.has(m.path)) {
      seen.add(m.path);
      out.push(m);
    }
  };
  const endsWith = (full, part) => full === part || full.endsWith("/" + part);
  for (const d of ALL_DIRS) if (endsWith(d, p)) push({ kind: "dir", path: d });
  for (const f of FILES.keys()) if (endsWith(f, p)) push({ kind: "file", path: f });
  const slash = p.lastIndexOf("/");
  const base = p.slice(slash + 1);
  if (slash > 0 && base.includes(".")) {
    const dirPart = p.slice(0, slash);
    for (const d of DIRS.keys()) if (endsWith(d, dirPart)) push({ kind: "file", path: `${d}/${base}` });
  }
  if (!out.length && p.length >= 3) {
    for (const d of ALL_DIRS) {
      if (d.includes(p)) push({ kind: "dir", path: d });
      if (out.length >= PATH_LIMIT) break;
    }
  }
  return out.sort((a, b) => a.path.length - b.path.length).slice(0, PATH_LIMIT);
}

// ---------- renderers ----------

function componentCard(c, tokens = []) {
  const desc = c.description ? `<div class="card-desc">${highlight(c.description, tokens)}</div>` : "";
  const href = c.subconcept ? `href="${link("sub", c.subconcept)}"` : `href="${ASSETS_OBJECT}${esc(c.id)}" target="_blank" rel="noopener"`;
  const sub = c.subconcept ? esc(c.subconcept) : `${esc(c.concept || "")} concept · not under any subconcept in Jira Assets`;
  return `<div class="card">
    <div class="card-top">
      <a class="card-title stretched" ${href}>${highlight(c.short || c.name, tokens)}</a>
      <span class="chip kind">${esc(c.type || "Component")}</span>${statusChip(c.status)}
      <span class="card-owner">${teamPill(c.team || ownerOf(c.subconcept), c.subconcept ? "assets" : "unfiled")}</span>
    </div>
    <div class="card-sub">${sub}</div>${desc}
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
      <span class="chip kind">Subconcept</span>${statusChip(s.status)}
      <span class="card-owner">${teamPill(s.team)}</span>
    </div>
    ${s.description ? `<div class="card-desc">${highlight(s.description, tokens)}</div>` : ""}
    ${counts ? `<div class="card-sub">${counts}</div>` : ""}
  </div>`;
}

function teamSummary(t) {
  const subs = subsByTeam.get(t.name) || [];
  const comps = subs.reduce((n, s) => n + (componentsBySub.get(s.name) || []).length, 0);
  const files = DATA.paths.teamFiles[t.name] || 0;
  return [subs.length && plural(subs.length, "subconcept"), comps && plural(comps, "component"), files && plural(files, "file")]
    .filter(Boolean)
    .join(" · ") || "Nothing";
}

function teamCard(t, tokens = []) {
  const aka = t.context ? ` · aka ${highlight(t.context, tokens)}` : "";
  return `<div class="card">
    <div class="card-top">
      <a class="card-title stretched" href="${link("team", t.name)}">${highlight(t.name, tokens)}</a>
      <span class="chip kind">${t.person ? "Person" : "Team"}</span>${statusChip(t.status)}
    </div>
    <div class="card-sub">Owns ${teamSummary(t)}${aka}</div>
  </div>`;
}

function codeRow(r, tokens = [], showOwner = true) {
  const owner = ownerOf(r.sub);
  return `<a class="code-row" href="${codeHref(r.path, r.line)}" target="_blank" rel="noopener" title="${esc(r.sub)}">
    ${r.symbol ? `<span class="sym">${highlight(r.symbol, tokens)}</span>` : ""}
    <span class="path">${highlight(r.path, tokens)}:${r.line}</span>
    ${showOwner ? `<span class="own">${esc(owner || NO_OWNER.assets[0])} · ${esc(r.sub.split(": ").pop())}</span>` : ""}
  </a>`;
}

function routeRow(r, tokens = [], showOwner = true) {
  const pattern = r.pattern || "(include root)";
  return `<a class="code-row" href="${codeHref(r.path, r.line)}" target="_blank" rel="noopener" title="${esc(r.path)}:${r.line}">
    <span class="chip">${r.kind === "react" ? "React" : "Django"}</span>
    <span class="sym">${highlight(pattern, tokens)}</span>
    <span class="path">${highlight(r.name || r.path, tokens)}</span>
    ${showOwner ? `<span class="own">${esc(ownerOf(r.sub) || NO_OWNER.assets[0])} · ${esc(r.sub.split(": ").pop())}</span>` : ""}
  </a>`;
}

// One pill per team with the sources that named it, primary owner first.
function ownerSetHtml(ownerSet) {
  const entries = DATA.paths.owners[ownerSet] || [];
  if (!entries.length) return noOwner("code");
  const byTeam = new Map();
  for (const [team, source] of entries) {
    if (!byTeam.has(team)) byTeam.set(team, []);
    byTeam.get(team).push(source);
  }
  return [...byTeam]
    .map(([team, sources], i) => `<span class="owner">${teamPill(team)}${sources.map((s) => `<span class="chip src">${SOURCE_LABEL[s]}</span>`).join("")}${i === 0 && byTeam.size > 1 ? `<span class="chip primary">primary</span>` : ""}</span>`)
    .join("");
}

function rollupHtml(r, limit = 4) {
  const parts = r.counts.slice(0, limit).map(([team, n]) => `${team ? esc(team) : "no code owner"} ${pct(n, r.total)}`);
  if (r.counts.length > limit) parts.push(`${r.counts.length - limit} more`);
  return `${plural(r.total, "file")} · ${parts.join(" · ")}`;
}

function pathCard(m, tokens = []) {
  if (m.kind === "file") {
    return `<div class="card">
      <div class="card-top">
        <a class="card-title stretched mono" href="${GITHUB}${DATA.source.webSha}/${esc(m.path)}" target="_blank" rel="noopener">${highlight(m.path, tokens)}</a>
        <span class="chip kind">File</span>
      </div>
      <div class="owners">${ownerSetHtml(ownersOfFile(m.path))}</div>
    </div>`;
  }
  const direct = DIRS.get(m.path);
  return `<div class="card">
    <div class="card-top">
      <a class="card-title stretched mono" href="${link("path", m.path)}">${highlight(m.path, tokens)}/</a>
      <span class="chip kind">Directory</span>
    </div>
    <div class="card-sub">${rollupHtml(rollup(m.path))}</div>
    ${direct ? `<div class="owners"><span class="muted small">Files directly here:</span>${ownerSetHtml(direct[0])}</div>` : ""}
  </div>`;
}

function globTable(rows, { owner = true } = {}) {
  if (!rows.length) return `<p class="empty">None.</p>`;
  const row = ([glob, team, purity, files, owned]) => {
    const base = glob.replace(/\/?\*+$/, "");
    return `<tr>
      <td><a class="mono" href="${link("path", base)}">${esc(glob)}</a></td>
      ${owner ? `<td>${teamPill(team, "code")}</td>` : ""}
      <td class="num">${team ? pct(purity, 1) : "–"}</td>
      <td class="num">${files.toLocaleString()}</td>
      <td class="num">${pct(owned, files)}</td>
    </tr>`;
  };
  const id = `t${Math.random().toString(36).slice(2, 8)}`;
  const head = `<thead><tr><th>Glob</th>${owner ? "<th>Main owner</th>" : ""}<th class="num" title="Share of owned files that belong to the main owner">Consistency</th><th class="num">Files</th><th class="num" title="Files with an owner from any source">Covered</th></tr></thead>`;
  setTimeout(() => {
    document.getElementById(`${id}-more`)?.addEventListener("click", (e) => {
      document.getElementById(id).innerHTML = rows.map(row).join("");
      e.target.remove();
    });
  });
  return `<div class="table-scroll"><table class="drift">${head}<tbody id="${id}">${rows.slice(0, TABLE_LIMIT).map(row).join("")}</tbody></table></div>
    ${rows.length > TABLE_LIMIT ? `<button class="btn more" id="${id}-more">Show all ${rows.length.toLocaleString()}</button>` : ""}`;
}

function renderCard(doc, tokens) {
  if (doc.kind === "component") return componentCard(doc.ref, tokens);
  if (doc.kind === "subconcept") return subconceptCard(doc.ref, tokens);
  if (doc.kind === "team") return teamCard(doc.ref, tokens);
  if (doc.kind === "route") return routeRow(doc.ref, tokens);
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
  const main = scored.filter(([, d]) => d.kind !== "code" && d.kind !== "route");
  const routes = scored.filter(([, d]) => d.kind === "route");
  const code = scored.filter(([, d]) => d.kind === "code");
  const paths = looksLikePath(q) ? pathMatches(q) : [];

  if (!main.length && !code.length && !routes.length && !paths.length) {
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
  let routeHtml = "";
  if (routes.length) {
    routeHtml = `<h2>URL routes (${routes.length})</h2>
      <p class="muted small">Django URL patterns and React routes labelled with a subconcept. A Django pattern is relative to where its <code>urls.py</code> is included.</p>
      <div class="code-list">${routes.slice(0, CODE_LIMIT).map(([, d]) => routeRow(d.ref, tokens)).join("")}</div>`;
  }
  let pathHtml = "";
  if (paths.length) {
    pathHtml = `<h2>Code paths</h2>
      <p class="muted small">Owners from <code>CODEOWNERS</code>, then <code>CODEWATCHERS</code>, then the subconcept tags in the file, the same as <code>bin/file-owners</code>. The first is the primary owner. <a href="#paths">Code map</a></p>
      <div class="results">${paths.map((m) => pathCard(m, tokens)).join("")}</div>`;
  }
  const looksLikeUrl = q.trim().startsWith("/") && routes.length;
  if (looksLikeUrl) view.innerHTML = routeHtml + pathHtml + mainHtml + codeHtml;
  else if (looksLikeCode && code.length) view.innerHTML = pathHtml + codeHtml + mainHtml + routeHtml;
  else view.innerHTML = pathHtml + mainHtml + routeHtml + codeHtml;
  $("#more-code")?.addEventListener("click", (e) => {
    $("#code-results").innerHTML = code.map(([, d]) => codeRow(d.ref, tokens)).join("");
    e.target.remove();
  });
}

function renderHome() {
  const examples = ["cancellation page", "rebook", "stripe", "background check", "inbox", "account_inbox/views.py", "/checkout/", "src/frontend/kibble", "sitter search"];
  view.innerHTML = `
    <p class="muted">Try: ${examples.map((e) => `<a href="${link("q", e)}">${esc(e)}</a>`).join(" · ")}</p>
    <h2>Browse by team</h2>
    ${teamGrid()}
  `;
}

function teamGrid() {
  const size = (t) => [(subsByTeam.get(t.name) || []).length, DATA.paths.teamFiles[t.name] || 0];
  const teams = [...DATA.teams].sort((a, b) => {
    const [sa, fa] = size(a);
    const [sb, fb] = size(b);
    return sb - sa || fb - fa;
  });
  return `<div class="team-grid">${teams
    .map((t) => `<a class="team-tile" href="${link("team", t.name)}"><b>${esc(t.name)} ${statusChip(t.status)}</b>
        <span>${teamSummary(t)}</span></a>`)
    .join("")}</div>`;
}

function renderTeams() {
  view.innerHTML = `<h1 class="page">Teams</h1>
    <p class="lede">Every team that owns a subconcept or component in Jira Assets, or code in <code>CODEOWNERS</code>, <code>CODEWATCHERS</code> or a subconcept tag. The most ownership comes first.</p>
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
  const fileCount = DATA.paths.teamFiles[name] || 0;
  const globs = [...(globsByTeam.get(name) || [])].sort((a, b) => b[4] - a[4]);

  const facts = [
    t.dri && `<span>DRI <b>${esc(t.dri.replace(/\s*\(.*\)$/, ""))}</b></span>`,
    t.parent && `<span>Part of <b>${esc(t.parent)}</b></span>`,
    t.context && `<span>Also known as <b>${esc(t.context)}</b></span>`,
    t.jiraComponent && `<span>Jira component <b>${esc(t.jiraComponent)}</b></span>`,
    t.github?.length && `<span>GitHub <b>${t.github.map((h) => `<code>${esc(h)}</code>`).join(", ")}</b></span>`,
  ].filter(Boolean);
  const owns = [
    subs.length && plural(subs.length, "subconcept"),
    compCount && plural(compCount, "component"),
    codeCount && plural(codeCount, "tagged code symbol"),
    fileCount && `${plural(fileCount, "file")} as primary owner`,
  ].filter(Boolean);
  const missing = t.person
    ? `<div class="callout info">This is a person named in <code>CODEOWNERS</code> or <code>CODEWATCHERS</code>, not a team.</div>`
    : `<div class="callout">This team owns things here but has no entry in the People Directory.</div>`;

  view.innerHTML = `
    <h1 class="page">${esc(t.name)} ${statusChip(t.status)}</h1>
    <p class="lede">Owns ${owns.length ? owns.join(", ") : "nothing"}.</p>
    <div class="facts">${facts.join("")}</div>
    <div class="actions">
      ${t.slack ? `<a class="btn accent-2" href="${SLACK}${esc(t.slack)}" target="_blank" rel="noopener">${t.slackName ? `#${esc(t.slackName)}` : "Open team Slack channel"}</a>` : ""}
      ${t.confluence ? `<a class="btn" href="${esc(t.confluence)}" target="_blank" rel="noopener">Confluence</a>` : ""}
      ${t.id ? `<a class="btn accent-2" href="${ASSETS_OBJECT}${esc(t.id)}" target="_blank" rel="noopener">People Directory entry</a>` : ""}
    </div>
    ${t.missingFromDirectory ? missing : ""}
    ${t.status && t.status !== "Active" ? `<div class="callout">The People Directory marks this team <b>${esc(t.status)}</b>, but it still owns the subconcepts below. They probably need a new owner.</div>` : ""}
    ${drift.length ? `<div class="callout">${drift.length} of this team's subconcepts have a different owner in <code>taxonomy.yml</code>. See <a href="#drift">drift</a>.</div>` : ""}
    <h2>Subconcepts and components</h2>
    ${subs.map(subBlock).join("") || `<p class="empty">No subconcepts.</p>`}
    ${strays.length ? `<h2>Components listed under another team's subconcept</h2><div class="results">${strays.map((c) => componentCard(c)).join("")}</div>` : ""}
    <h2>Code paths (${globs.length})</h2>
    ${globs.length ? `<p class="muted small">Globs where this team is the main owner, split the way <code>bin/subdivide-files</code> splits a branch, with the most owned files first. See the <a href="#paths">code map</a>.</p>` : ""}
    ${globs.length ? globTable(globs, { owner: false }) : `<p class="empty">This team is not the main owner of any directory.</p>`}
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
  const routes = routesBySub.get(name) || [];
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
    <div class="actions">${teamPill(s.team)} ${slackLink(s.team)} ${assetsLink(s.id)}</div>
    <div class="facts">${facts.join("")}</div>
    ${s.rationale ? `<div class="callout info"><b>Why this team:</b> ${esc(s.rationale)}</div>` : ""}
    ${drift ? `<div class="callout"><code>taxonomy.yml</code> in <code>web</code> says <b>${esc(drift.taxonomyTeam)}</b> owns this, but Jira Assets says <b>${esc(drift.assetsTeam)}</b>. Code metrics, SLOs and alerts follow <code>taxonomy.yml</code>.</div>` : ""}
    <h2>Components (${comps.length})</h2>
    ${comps.length ? `<div class="results">${comps.map((c) => componentCard(c)).join("")}</div>` : `<p class="empty">No components listed.</p>`}
    ${routes.length ? `<h2>URL routes (${routes.length})</h2><div class="code-list">${routes.map((r) => routeRow(r, [], false)).join("")}</div>` : ""}
    <h2>Tagged code (${code.length})</h2>
    ${code.length ? `<div class="code-list">${code.map((r) => codeRow(r, [], false)).join("")}</div>` : `<p class="empty">Nothing in <code>web</code> is tagged with this subconcept.</p>`}
  `;
}

function renderCodeMap() {
  const st = DATA.paths.stats;
  const rows = DATA.paths.map;
  const unowned = rows.filter((r) => r[4] === 0).sort((a, b) => b[3] - a[3]);
  const mixed = rows.filter((r) => r[1] && r[2] < PURITY_THRESHOLD).sort((a, b) => b[3] - a[3]);
  const partial = rows.filter((r) => r[1] && r[4] < r[3]).sort((a, b) => b[3] - b[4] - (a[3] - a[4]));
  const unownedFiles = unowned.reduce((n, r) => n + r[3], 0);
  view.innerHTML = `
    <h1 class="page">Code map</h1>
    <p class="lede">Who owns each part of <code>web</code>. A file's owners come from
      <a href="${CODEOWNERS_FILE}" target="_blank" rel="noopener"><code>CODEOWNERS</code></a> (who approves),
      <a href="${CODEWATCHERS_FILE}" target="_blank" rel="noopener"><code>CODEWATCHERS</code></a> (who wants to know) and the
      <code>CONCEPTS.x.y</code> tags in the file, in that order, the same as <code>bin/file-owners</code>.
      The tree is split into globs the way <code>bin/subdivide-files</code> splits a branch: a directory stops splitting once
      ${pct(PURITY_THRESHOLD, 1)} of its owned files share a main owner.</p>
    <div class="facts">
      <span>Files <b>${st.files.toLocaleString()}</b></span>
      <span>With a CODEOWNERS owner <b>${pct(st.codeowners, st.files)}</b></span>
      <span>With any owner <b>${pct(st.owned, st.files)}</b></span>
      <span>Rules <b>${st.codeownersRules} CODEOWNERS · ${st.codewatchersRules} CODEWATCHERS</b></span>
    </div>
    <h2>No owner from any source (${unowned.length} globs, ${plural(unownedFiles, "file")})</h2>
    ${globTable(unowned, { owner: false })}
    <h2>Mixed ownership (${mixed.length})</h2>
    <p class="muted small">Globs too small to split further whose owned files are spread across teams.</p>
    ${globTable(mixed)}
    <h2>Owned, with unowned files inside (${partial.length})</h2>
    <p class="muted small">Unowned files ride along with the main owner when a branch is split, but nothing names an owner for them. Most unowned files first.</p>
    ${globTable(partial)}
    <h2>Every glob (${rows.length})</h2>
    ${globTable([...rows].sort((a, b) => a[0].localeCompare(b[0])))}
  `;
}

function renderPath(path) {
  const p = cleanPathQuery(path);
  const isDir = p === "" || ALL_DIRS.has(p);
  if (!isDir && !DIRS.has(parentDir(p))) return notFound("path", path);
  if (!isDir) {
    view.innerHTML = `<h1 class="page mono">${esc(p)}</h1>
      <div class="actions"><a class="btn" href="${GITHUB}${DATA.source.webSha}/${esc(p)}" target="_blank" rel="noopener">Open on GitHub</a></div>
      <div class="owners">${ownerSetHtml(ownersOfFile(p))}</div>
      <p class="small"><a href="${link("path", parentDir(p))}">${esc(parentDir(p) || "web")}/</a></p>`;
    return;
  }
  const r = rollup(p);
  const direct = DIRS.get(p);
  const prefix = p ? p + "/" : "";
  const globs = DATA.paths.map.filter(([g]) => g.startsWith(prefix) || g === `${p}/**` || g === `${p}/*`);
  const exceptions = [...FILES].filter(([f]) => f.startsWith(prefix));
  const crumbs = p.split("/").map((part, i, all) => `<a href="${link("path", all.slice(0, i + 1).join("/"))}">${esc(part)}</a>`);
  view.innerHTML = `
    <h1 class="page mono">${crumbs.join("/")}/</h1>
    <div class="actions"><a class="btn" href="${GITHUB_TREE}${DATA.source.webSha}/${esc(p)}" target="_blank" rel="noopener">Open on GitHub</a></div>
    <p class="lede">${plural(r.total, "file")}, counted by primary owner.</p>
    <div class="table-scroll"><table class="drift"><thead><tr><th>Primary owner</th><th class="num">Files</th><th class="num">Share</th></tr></thead><tbody>
      ${r.counts.map(([team, n]) => `<tr><td>${teamPill(team, "code")}</td><td class="num">${n.toLocaleString()}</td><td class="num">${pct(n, r.total)}</td></tr>`).join("")}
    </tbody></table></div>
    ${direct ? `<h2>Files directly in this directory (${direct[1]})</h2><div class="owners">${ownerSetHtml(direct[0])}</div>` : ""}
    ${exceptions.length ? `<h2>Files with their own owners (${exceptions.length})</h2>
      <p class="muted small">Files whose owners differ from the rest of their directory.</p>
      <div class="results">${exceptions.slice(0, TABLE_LIMIT).map(([f]) => pathCard({ kind: "file", path: f })).join("")}</div>` : ""}
    <h2>Globs (${globs.length})</h2>
    ${globTable(globs)}
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
      <div><b>CODEOWNERS, CODEWATCHERS</b>Path rules in <code>web</code> for who approves and who is notified.</div>
      <div><b>This site</b>Joins them all, plus team Slack channels from the People Directory.</div>
    </div>
    <ul>
      <li><b>Subconcepts, components, concepts:</b> Jira Assets schema 42, Technology Components.</li>
      <li><b>Teams:</b> Jira Assets People Directory → Groups (Slack channel, DRI, parent team, former names). A <code>CODEOWNERS</code> handle like <code>@roverdotcom/client-platform</code> is matched to its group by name.</li>
      <li><b>Tagged code:</b> every <code>CONCEPTS.&lt;concept&gt;.&lt;subconcept&gt;</code> reference in <code>web</code>, outside tests and migrations, credited to its enclosing class or function. TypeScript symbols are a best guess from the nearest declaration.</li>
      <li><b>URL routes:</b> Django <code>path()</code>/<code>re_path()</code> patterns labelled with a subconcept (directly or through <code>label_url_resolver</code>), and React SSR routes with a <code>concept</code>.</li>
      <li><b>Code paths:</b> every tracked file, owned the way <code>bin/file-owners</code> owns it, using its own matching code from <code>web</code>: <a href="${CODEOWNERS_FILE}" target="_blank" rel="noopener"><code>CODEOWNERS</code></a> first, then <a href="${CODEWATCHERS_FILE}" target="_blank" rel="noopener"><code>CODEWATCHERS</code></a>, then the teams of the subconcepts the file mentions. The first is the primary owner. The <a href="#paths">code map</a> groups them with <code>bin/subdivide-files</code>.</li>
    </ul>

    <h2>Changing who owns something</h2>
    <p>EMs edit <a href="${DATA.source.assets}?typeId=33&view=list" target="_blank" rel="noopener">Jira Assets</a> directly, then do the downstream steps in the
      <a href="${RUNBOOK}" target="_blank" rel="noopener">Updating Technology Components runbook</a> (taxonomy.yml, alerts, CWV mapping, Jira components).
      There is also a <a href="${CHANGE_FORM}" target="_blank" rel="noopener">concept/subconcept change request form</a>.
      To change who owns a code path, open a PR against <code>.github/CODEOWNERS</code> or <code>danger/CODEWATCHERS</code> in <code>web</code>.
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
  if (key === "paths") return renderCodeMap();
  if (key === "path") return renderPath(value);
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
    $("#freshness").innerHTML = `${data.subconcepts.length} subconcepts, ${data.components.length} components, ${data.routes.length} URL routes, ${DOCS.filter((d) => d.kind === "code").length.toLocaleString()} tagged code symbols and ${data.paths.stats.files.toLocaleString()} files. Refreshed ${esc(when.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }))}. <a href="#about">How this works</a>`;
    route();
  })
  .catch((err) => {
    view.innerHTML = `<p class="empty">Could not load data.json: ${esc(err.message)}</p>`;
  });
