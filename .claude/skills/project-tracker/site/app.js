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
let READ = {};
let STORAGE_KEY = "project-tracker:read";

// ------------------------------------------------------------------ read state

function loadRead() {
  try {
    READ = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
  } catch (e) {
    READ = {};
  }
}

function saveRead() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(READ));
  } catch (e) {
    /* private window or blocked storage: marks last for this page view only */
  }
}

// An entry the agent rewrote since you read it counts as unread again.
function isUnread(entry) {
  return READ[entry.id] !== entry.updated;
}

function setRead(entries, read) {
  for (const entry of entries) {
    if (read) READ[entry.id] = entry.updated;
    else delete READ[entry.id];
  }
  saveRead();
  render();
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

// ------------------------------------------------------------------ views

function renderSources() {
  const docs = [...DATA.docs].sort((a, b) => {
    const la = latestStart(a.id) || "";
    const lb = latestStart(b.id) || "";
    return lb.localeCompare(la) || a.name.localeCompare(b.name);
  });
  const allEntries = DATA.entries;
  const unreadTotal = allEntries.filter(isUnread).length;

  const rows = docs.map((doc) => {
    const entries = entriesFor(doc.id);
    const unread = entries.filter(isUnread).length;
    const latest = latestStart(doc.id);
    const headline = entries.length ? entries[0].title : "No changes logged yet";
    return `
      <li class="source">
        <div class="source-date">${latest ? esc(shortDate(latest)) : "—"}</div>
        <div class="source-body">
          <div class="source-title">
            <a href="#doc=${encodeURIComponent(doc.id)}">${esc(doc.name)}</a>
            ${unread ? `<span class="pill unread-pill">${unread} unread</span>` : ""}
            <span class="kind">${esc(KIND_LABELS[doc.kind] || doc.kind)}</span>
          </div>
          <div class="source-headline">${inline(headline)}</div>
          <div class="source-links">
            ${external(doc.url, "Open doc")}
            <a href="#doc=${encodeURIComponent(doc.id)}">Change log (${entries.length})</a>
          </div>
        </div>
      </li>`;
  });

  return `
    <div class="page-head">
      <h1>Sources</h1>
      ${unreadTotal ? `<button class="btn accent-2" data-action="read-all">Mark all ${unreadTotal} read</button>` : ""}
    </div>
    ${docs.length ? `<ul class="sources">${rows.join("")}</ul>` : `<p class="empty">No docs tracked yet.</p>`}`;
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
        <time class="mono" datetime="${esc(entry.start)}">${esc(start)}${span}</time>
        <h2>${inline(entry.title)}</h2>
        <button class="btn btn-small" data-action="toggle" data-id="${esc(entry.id)}">${unread ? "Mark read" : "Mark unread"}</button>
      </header>
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
          ${external(doc.url, "Open doc")}
          <span>${coverage}</span>
        </p>
      </div>
      ${unread ? `<button class="btn accent-2" data-action="read-doc" data-id="${esc(doc.id)}">Mark all ${unread} read</button>` : ""}
    </div>
    ${entries.length ? entries.map(renderEntry).join("") : `<p class="empty">No changes logged yet.</p>`}`;
}

function render() {
  const view = document.getElementById("view");
  const hash = decodeURIComponent(location.hash.slice(1));
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
    setRead(DATA.entries, true);
  }
});

window.addEventListener("hashchange", () => {
  render();
  window.scrollTo(0, 0);
});

fetch("data.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((data) => {
    DATA = data;
    STORAGE_KEY = `${data.project.site}:read`;
    loadRead();
    document.title = data.project.title;
    document.getElementById("brand").textContent = data.project.title;
    document.getElementById("freshness").textContent = `Updated ${longDate(data.generatedAt)}`;
    render();
  })
  .catch((err) => {
    document.getElementById("view").innerHTML = `<p class="empty">Could not load data.json: ${esc(err)}</p>`;
  });
