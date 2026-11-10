"use strict";

const KIND_LABELS = {
  github_pr: "GitHub PR",
  confluence: "Confluence",
  jira: "Jira",
  claude_artifact: "Claude artifact",
  slack_canvas: "Slack canvas",
  google_doc: "Google Doc",
  other: "Link",
};

let DATA = null;
let STORAGE_KEY = "project-tracker:read";
let SHOW_ARCHIVED = false;
let SHOW_HIDDEN = false;
let DOC_NOTICE = {};

// ------------------------------------------------------------------ read state

// Read marks used to live in localStorage. Copy any left there into the reader's choices
// once, then drop them.
function migrateLocalRead() {
  let local = null;
  try {
    local = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  } catch (e) {
    return;
  }
  if (!local || typeof local !== "object") return;
  const marks = {};
  for (const [id, stamp] of Object.entries(local)) {
    if (Prefs.readStamp(id) == null) marks[id] = stamp;
  }
  const done = () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      /* blocked storage */
    }
  };
  if (Object.keys(marks).length) Prefs.setRead(marks).then(() => Prefs.error() || done());
  else done();
}

// An entry the agent rewrote since you read it counts as unread again.
function isUnread(entry) {
  return Prefs.readStamp(entry.id) !== entry.updated;
}

function setRead(entries, read) {
  const marks = {};
  for (const entry of entries) marks[entry.id] = read ? entry.updated : null;
  Prefs.setRead(marks);
}

// ------------------------------------------------------------------ helpers

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function inline(text) {
  return esc(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function stamp(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function shortDate(iso) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function longDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function entriesFor(docId) {
  return DATA.entries.filter((e) => e.doc === docId);
}

function latestStart(docId) {
  const entries = entriesFor(docId);
  return entries.length ? entries[0].start : null;
}

function external(url, label) {
  return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)} <span aria-hidden="true">↗</span></a>`;
}

function isHidden(doc) {
  return Boolean(Prefs.doc(doc.id).hidden);
}

async function setHidden(docId, hidden) {
  delete DOC_NOTICE[docId];
  try {
    await Prefs.setDoc(docId, { hidden });
  } catch (err) {
    DOC_NOTICE[docId] = err.message;
    render();
  }
}

function hideButton(doc) {
  const hidden = isHidden(doc);
  return `<button class="btn btn-small" data-action="${hidden ? "unhide" : "hide"}" data-id="${esc(doc.id)}">${hidden ? "Unhide" : "Hide"}</button>`;
}

// ------------------------------------------------------------------ views

function sourceRow(doc) {
  const entries = entriesFor(doc.id);
  const unread = entries.filter(isUnread).length;
  const latest = latestStart(doc.id);
  const headline = entries.length ? entries[0].title : "No changes logged yet";
  return `
    <li class="source ${doc.archivedAt ? "is-archived" : ""} ${isHidden(doc) ? "is-hidden" : ""}">
      <div class="source-date">${latest ? esc(shortDate(latest)) : "—"}</div>
      <div class="source-body">
        ${DOC_NOTICE[doc.id] ? `<p class="notice">${esc(DOC_NOTICE[doc.id])}</p>` : ""}
        <div class="source-title">
          <a href="#doc=${encodeURIComponent(doc.id)}">${esc(doc.name)}</a>
          ${unread ? `<span class="pill unread-pill">${unread} unread</span>` : ""}
          ${archivedPill(doc)}
          <span class="kind source-kind">${esc(KIND_LABELS[doc.kind] || doc.kind)}</span>
        </div>
        <div class="source-headline">${inline(headline)}</div>
        <div class="source-links">
          ${external(doc.url, "Open doc")}
          <a href="#doc=${encodeURIComponent(doc.id)}">Change log (${entries.length})</a>
          ${hideButton(doc)}
        </div>
      </div>
    </li>`;
}

function archivedPill(doc) {
  if (!doc.archivedAt) return "";
  const why = doc.archivedReason ? ` title="${esc(doc.archivedReason)}"` : "";
  return `<span class="pill archived-pill"${why}>Archived ${esc(shortDate(doc.archivedAt))}</span>`;
}

// Archived docs are shown only on request, and so are the reader's hidden ones.
function listedDoc(doc) {
  return (SHOW_ARCHIVED || !doc.archivedAt) && (SHOW_HIDDEN || !isHidden(doc));
}

function visibleEntries() {
  const listed = new Set(DATA.docs.filter(listedDoc).map((d) => d.id));
  return DATA.entries.filter((e) => listed.has(e.doc));
}

function renderSources() {
  const byLatest = (a, b) =>
    (latestStart(b.id) || "").localeCompare(latestStart(a.id) || "") || a.name.localeCompare(b.name);
  const active = DATA.docs.filter((d) => !d.archivedAt).sort(byLatest);
  const archived = DATA.docs.filter((d) => d.archivedAt).sort(byLatest);
  const hiddenCount = DATA.docs.filter((d) => (SHOW_ARCHIVED || !d.archivedAt) && isHidden(d)).length;
  const unreadTotal = visibleEntries().filter(isUnread).length;
  const activeListed = active.filter(listedDoc);
  const archivedListed = archived.filter(listedDoc);

  const toggles = [
    archived.length
      ? `<button class="btn btn-small" data-action="toggle-archived">${SHOW_ARCHIVED ? "Hide" : "Show"} ${archived.length} archived</button>`
      : "",
    hiddenCount
      ? `<button class="btn btn-small" data-action="toggle-hidden">${SHOW_HIDDEN ? "Hide" : "Show"} ${hiddenCount} hidden</button>`
      : "",
  ].join("");
  const toggle = toggles ? `<p class="archived-toggle">${toggles}</p>` : "";
  const archivedList = SHOW_ARCHIVED && archivedListed.length
    ? `<h2 class="section-head">Archived</h2><ul class="sources">${archivedListed.map(sourceRow).join("")}</ul>`
    : "";

  return `
    <div class="page-head">
      <h1>Sources</h1>
      ${unreadTotal ? `<button class="btn accent-2" data-action="read-all">Mark all ${unreadTotal} read</button>` : ""}
    </div>
    ${Prefs.error() ? `<p class="notice">${esc(Prefs.error())}</p>` : ""}
    ${activeListed.length ? `<ul class="sources">${activeListed.map(sourceRow).join("")}</ul>` : `<p class="empty">No active docs${hiddenCount && !SHOW_HIDDEN ? " you haven't hidden" : ""}.</p>`}
    ${toggle}
    ${archivedList}`;
}

function renderEntry(entry) {
  const unread = isUnread(entry);
  const actors = entry.actors && entry.actors.length ? `<span class="actors">${esc(entry.actors.join(", "))}</span>` : "";
  const links = (entry.links || []).map((l) => external(l.url, l.label)).join("");
  const start = stamp(entry.start);
  const end = entry.end ? stamp(entry.end) : start;
  const span = end === start ? "" : ` – ${esc(end.slice(0, 10) === start.slice(0, 10) ? end.slice(11) : end)}`;
  return `
    <article class="entry ${unread ? "is-unread" : ""}" id="e-${esc(entry.id)}">
      <header class="entry-head">
        <span class="dot" aria-hidden="true"></span>
        <h2>${inline(entry.title)}</h2>
        <button class="btn btn-small" data-action="toggle" data-id="${esc(entry.id)}">${unread ? "Mark read" : "Mark unread"}</button>
      </header>
      <time class="entry-time mono" datetime="${esc(entry.start)}">${esc(start)}${span}</time>
      ${actors}
      <ul class="bullets">${entry.bullets.map((b) => `<li>${inline(b)}</li>`).join("")}</ul>
      ${links ? `<div class="entry-links">${links}</div>` : ""}
    </article>`;
}

function renderDoc(docId) {
  const doc = DATA.docs.find((d) => d.id === docId);
  if (!doc) return `<p class="empty">No doc named <code>${esc(docId)}</code>. <a href="#">Back to sources</a></p>`;
  const entries = entriesFor(doc.id);
  const unread = entries.filter(isUnread).length;
  const coverage = doc.coverage
    ? `Covers ${esc(longDate(doc.coverage.from))} – ${esc(longDate(doc.coverage.to))}`
    : "Not summarized yet";
  return `
    <p class="crumb"><a href="#">← Sources</a></p>
    <div class="page-head">
      <div>
        <h1>${esc(doc.name)}</h1>
        <p class="meta">
          <span class="kind">${esc(KIND_LABELS[doc.kind] || doc.kind)}</span>
          ${archivedPill(doc)}
          ${external(doc.url, "Open doc")}
          <span>${coverage}</span>
          ${doc.archivedReason ? `<span>${inline(doc.archivedReason)}</span>` : ""}
          ${isHidden(doc) ? `<span class="pill archived-pill">Hidden</span>` : ""}
          ${hideButton(doc)}
        </p>
        ${DOC_NOTICE[doc.id] ? `<p class="notice">${esc(DOC_NOTICE[doc.id])}</p>` : ""}
      </div>
      ${unread ? `<button class="btn accent-2" data-action="read-doc" data-id="${esc(doc.id)}">Mark all ${unread} read</button>` : ""}
    </div>
    ${entries.length ? entries.map(renderEntry).join("") : `<p class="empty">No changes logged yet.</p>`}`;
}

function render() {
  const view = document.getElementById("view");
  const hash = decodeURIComponent(location.hash.slice(1));
  const section = hash === "questions" || hash === "prs" ? hash : "";
  for (const link of document.querySelectorAll(".nav a")) {
    link.classList.toggle("is-active", link.getAttribute("href").slice(1) === section);
  }
  if (hash === "questions") return Questions.mount(view);
  if (hash === "prs") return Prs.mount(view);
  if (!DATA) return;
  const doc = hash.startsWith("doc=") ? hash.slice(4) : null;
  view.innerHTML = doc ? renderDoc(doc) : renderSources();
}

// ------------------------------------------------------------------ boot

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  if (action === "toggle") {
    const entry = DATA.entries.find((e) => e.id === button.dataset.id);
    if (entry) setRead([entry], isUnread(entry));
  } else if (action === "read-doc") {
    setRead(entriesFor(button.dataset.id), true);
  } else if (action === "read-all") {
    setRead(visibleEntries(), true);
  } else if (action === "toggle-archived") {
    SHOW_ARCHIVED = !SHOW_ARCHIVED;
    render();
  } else if (action === "toggle-hidden") {
    SHOW_HIDDEN = !SHOW_HIDDEN;
    render();
  } else if (action === "hide" || action === "unhide") {
    setHidden(button.dataset.id, action === "hide");
  }
});

window.addEventListener("hashchange", () => {
  render();
  window.scrollTo(0, 0);
});

Prefs.onChange(() => {
  const hash = location.hash.slice(1);
  if (hash === "prs") Prs.repaint();
  else if (hash !== "questions") render();
});
Prefs.load();
window.addEventListener("focus", () => Prefs.load());

render();
fetch("data.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((data) => {
    DATA = data;
    STORAGE_KEY = `${data.project.site}:read`;
    Prefs.ready().then(() => Prefs.error() || migrateLocalRead());
    document.title = data.project.title;
    document.getElementById("brand").textContent = data.project.title;
    document.getElementById("freshness").textContent = `Updated ${longDate(data.generatedAt)}`;
    render();
  })
  .catch((err) => {
    if (location.hash === "#questions" || location.hash === "#prs") return;
    document.getElementById("view").innerHTML = `<p class="empty">Could not load data.json: ${esc(err)}</p>`;
  });
