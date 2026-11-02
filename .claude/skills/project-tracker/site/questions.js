"use strict";

// Open questions live in the site's shared store, one key per question (oq.<id>),
// and scripts/oq.py edits the same keys. Every write sends the version it was based
// on, so a save that races another one gets a 412 and merges instead of erasing it.

const Questions = (() => {
  const PREFIX = "oq.";
  const API = "/_yard/v1/shared/";
  const REFRESH_MS = 60_000;

  const state = {
    items: {}, // id -> { rec, version, by, at }
    loaded: false,
    error: null,
    filter: { status: "open", tag: null, text: "" },
    drafts: {}, // id or "new" -> editable copy, with baseVersion
    notices: {}, // id -> message shown on its card or editor
  };
  let view = null;

  // ---------------------------------------------------------------- store

  async function getKey(key) {
    const r = await fetch(API + encodeURIComponent(key), { cache: "no-store" });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(`GET ${key}: ${r.status}`);
    const env = await r.json();
    return { rec: JSON.parse(env.value), version: env.version, by: env.updated_by, at: env.updated_at };
  }

  async function load() {
    const r = await fetch(API.slice(0, -1), { cache: "no-store" });
    if (!r.ok) throw new Error(`could not list questions (${r.status})`);
    const keys = (await r.json()).keys.filter((k) => k.key.startsWith(PREFIX));
    const live = new Set();
    await Promise.all(keys.map(async (k) => {
      const id = k.key.slice(PREFIX.length);
      live.add(id);
      if (state.items[id] && state.items[id].version === k.version) return;
      const item = await getKey(k.key);
      if (item) state.items[id] = item;
    }));
    for (const id of Object.keys(state.items)) if (!live.has(id)) delete state.items[id];
    state.loaded = true;
    state.error = null;
  }

  async function put(id, rec, ifMatch) {
    const r = await fetch(API + encodeURIComponent(PREFIX + id), {
      method: "PUT",
      headers: { "Content-Type": "application/json", "If-Match": ifMatch },
      body: JSON.stringify(rec, null, 1),
    });
    if (r.status === 412) return false;
    if (!r.ok) throw new Error(`save failed (${r.status})`);
    const item = await getKey(PREFIX + id);
    if (item) state.items[id] = item;
    return true;
  }

  // ---------------------------------------------------------------- helpers

  function slugify(title) {
    const slug = title.toLowerCase().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return (slug.length > 60 ? slug.slice(0, 60).replace(/-[^-]*$/, "") : slug) || "question";
  }

  function normTag(tag) {
    return tag.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }

  function mdInline(text) {
    return String(text).split("`").map((part, i) => {
      if (i % 2) return `<code>${esc(part)}</code>`;
      return esc(part)
        .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    }).join("");
  }

  function md(text) {
    const lines = String(text || "").split("\n");
    const out = [];
    for (let i = 0; i < lines.length;) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (line.startsWith("```")) {
        const code = [];
        for (i++; i < lines.length && !lines[i].startsWith("```"); i++) code.push(lines[i]);
        i++;
        out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`);
      } else if (line.startsWith(">")) {
        const quote = [];
        for (; i < lines.length && lines[i].startsWith(">"); i++) quote.push(lines[i].replace(/^> ?/, ""));
        out.push(`<blockquote>${md(quote.join("\n"))}</blockquote>`);
      } else if (/^[-*] /.test(line)) {
        // Top-level bullets; an indented "- " line is a sub-bullet, other indented lines continue the item.
        const items = [];
        for (; i < lines.length && /^([-*] |\s{2,}\S)/.test(lines[i]); i++) {
          const l = lines[i];
          if (/^[-*] /.test(l)) items.push({ text: mdInline(l.slice(2)), subs: [] });
          else if (/^\s+[-*] /.test(l)) items[items.length - 1].subs.push(mdInline(l.trim().slice(2)));
          else items[items.length - 1].text += "<br>" + mdInline(l.trim());
        }
        out.push(`<ul>${items.map((it) => `<li>${it.text}${it.subs.length
          ? `<ul>${it.subs.map((s) => `<li>${s}</li>`).join("")}</ul>` : ""}</li>`).join("")}</ul>`);
      } else {
        const para = [];
        for (; i < lines.length && lines[i].trim() && !/^(```|>|[-*] )/.test(lines[i]); i++) para.push(mdInline(lines[i]));
        out.push(`<p>${para.join("<br>")}</p>`);
      }
    }
    return out.join("");
  }

  function who(email) {
    return String(email || "").split("@")[0];
  }

  function ordered() {
    const all = Object.values(state.items).map((i) => i.rec);
    const open = all.filter((r) => r.status === "open").sort((a, b) => b.created.localeCompare(a.created));
    const done = all.filter((r) => r.status === "resolved")
      .sort((a, b) => (b.resolved || b.created).localeCompare(a.resolved || a.created));
    return [...open, ...done];
  }

  function matches(rec) {
    const f = state.filter;
    if (f.status !== "all" && rec.status !== f.status) return false;
    if (f.tag && !(rec.tags || []).includes(f.tag)) return false;
    if (f.text) {
      const hay = [rec.title, rec.body, rec.answer?.summary, rec.answer?.detail, ...(rec.tags || [])].join(" ").toLowerCase();
      if (!hay.includes(f.text.toLowerCase())) return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- drafts

  const FIELDS = { title: "question", body: "details", status: "status", summary: "answer", detail: "answer details", tags: "tags", links: "links" };

  function formFields(rec) {
    return {
      title: rec.title,
      body: rec.body || "",
      status: rec.status,
      summary: rec.answer?.summary || "",
      detail: rec.answer?.detail || "",
      tags: (rec.tags || []).join(", "),
      links: (rec.links || []).map((l) => `${l.label} | ${l.url}`).join("\n"),
    };
  }

  // A draft keeps the fields it started from (base), so a conflicting save can tell
  // which fields this user changed and take everything else from the other writer.
  function startDraft(id, resolving) {
    const item = state.items[id];
    const base = formFields(item ? item.rec : { title: "", status: "open" });
    state.drafts[id] = { ...base, status: resolving ? "resolved" : base.status, base, baseVersion: item ? item.version : null };
    delete state.notices[id];
  }

  function merge(draft, latest) {
    const theirs = formFields(latest.rec);
    const clashes = [];
    for (const f of Object.keys(FIELDS)) {
      if (draft[f] === draft.base[f]) draft[f] = theirs[f];
      else if (theirs[f] !== draft.base[f] && theirs[f] !== draft[f]) clashes.push(FIELDS[f]);
    }
    draft.base = theirs;
    draft.baseVersion = latest.version;
    return clashes;
  }

  // Descriptions and answer details are bullet lists: any line that is not a bullet, an
  // indented continuation, a quote or fenced code gets a "- " when saved. oq.py refuses them.
  function bulletize(text) {
    let inFence = false;
    return text.split("\n").map((line) => {
      if (line.startsWith("```")) inFence = !inFence;
      else if (!inFence && line.trim() && !/^([-*] |\s{2}|>)/.test(line)) return `- ${line.trim()}`;
      return line;
    }).join("\n");
  }

  function fromDraft(id, draft) {
    const prev = state.items[id]?.rec;
    const now = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    const links = [];
    for (const line of draft.links.split("\n").map((l) => l.trim()).filter(Boolean)) {
      const cut = line.lastIndexOf("|");
      const url = cut < 0 ? line : line.slice(cut + 1).trim();
      if (!/^https?:\/\//.test(url)) throw new Error(`A link needs "Label | https://…": ${line}`);
      links.push({ label: cut < 0 ? url : line.slice(0, cut).trim() || url, url });
    }
    const rec = {
      id,
      title: draft.title.trim(),
      body: bulletize(draft.body.trim()),
      status: draft.status,
      answer: draft.summary.trim() || draft.detail.trim()
        ? { summary: draft.summary.trim(), detail: bulletize(draft.detail.trim()) } : null,
      tags: [...new Set(draft.tags.split(",").map(normTag).filter(Boolean))].sort(),
      links,
      created: prev?.created || now,
      updated: now,
    };
    if (rec.status === "resolved") rec.resolved = prev?.status === "resolved" && prev.resolved ? prev.resolved : now;
    if (!rec.title) throw new Error("A question needs a title.");
    return rec;
  }

  async function save(id, attempt = 1) {
    const draft = state.drafts[id];
    let rec;
    try {
      rec = fromDraft(id === "new" ? null : id, draft);
    } catch (err) {
      state.notices[id] = err.message;
      return paint();
    }
    try {
      if (id === "new") {
        const base = slugify(rec.title);
        for (let n = 1; n < 20; n++) {
          rec.id = n === 1 ? base : `${base}-${n}`;
          if (await put(rec.id, rec, "*")) break;
        }
        delete state.drafts.new;
        state.filter.status = "open";
      } else if (await put(id, rec, draft.baseVersion === null ? "*" : `"${draft.baseVersion}"`)) {
        delete state.drafts[id];
        delete state.notices[id];
      } else {
        const latest = await getKey(PREFIX + id);
        if (!latest) {
          state.notices[id] = "Someone deleted this question while you were editing. Save again to put it back.";
          draft.baseVersion = null;
          return paint();
        }
        state.items[id] = latest;
        const clashes = merge(draft, latest);
        if (!clashes.length && attempt < 5) return save(id, attempt + 1);
        state.notices[id] = `${who(latest.by)} saved this question at ${stamp(latest.at)} while you were editing. ` +
          `Their other changes are merged in, but you both changed the ${clashes.join(", ")}. ` +
          "The form shows yours: Save to keep it, or Cancel to keep theirs.";
      }
    } catch (err) {
      state.notices[id] = err.message;
    }
    paint();
  }

  async function remove(id) {
    const rec = state.items[id]?.rec;
    if (!rec || !confirm(`Delete "${rec.title}"? This cannot be undone here.`)) return;
    const r = await fetch(API + encodeURIComponent(PREFIX + id), { method: "DELETE" });
    if (!r.ok && r.status !== 404) {
      state.notices[id] = `Delete failed (${r.status})`;
    } else {
      delete state.items[id];
      delete state.drafts[id];
    }
    paint();
  }

  // ---------------------------------------------------------------- views

  function tagChips(tags, active) {
    return (tags || []).map((t) =>
      `<button class="tag ${t === active ? "is-active" : ""}" data-q="tag" data-tag="${esc(t)}">#${esc(t)}</button>`).join("");
  }

  function editor(id) {
    const d = state.drafts[id];
    const field = (name, label, input) => `<label class="field"><span>${label}</span>${input}</label>`;
    const text = (name, value, extra = "") => `<input data-field="${name}" value="${esc(value)}" ${extra}>`;
    const area = (name, value, rows, hint = "") =>
      `<textarea data-field="${name}" rows="${rows}" placeholder="${esc(hint)}">${esc(value)}</textarea>`;
    return `
      <form class="q-card editor" data-id="${esc(id)}">
        ${state.notices[id] ? `<p class="notice">${esc(state.notices[id])}</p>` : ""}
        ${field("title", "Question", text("title", d.title, 'required placeholder="What do we need to decide?"'))}
        ${field("body", "Details <em>(bullets, one point per line; lines without a “- ” get one when saved)</em>", area("body", d.body, 5, "- For: Tax / Legal\n- What we know\n- What we need to decide"))}
        <div class="field-row">
          ${field("tags", "Tags <em>(comma separated)</em>", text("tags", d.tags, 'placeholder="tax, legal"'))}
          ${field("status", "Status", `<select data-field="status">
            <option value="open" ${d.status === "open" ? "selected" : ""}>Open</option>
            <option value="resolved" ${d.status === "resolved" ? "selected" : ""}>Resolved</option></select>`)}
        </div>
        ${field("links", "Links <em>(one per line: Label | URL)</em>", area("links", d.links, 3))}
        ${field("summary", "Answer", text("summary", d.summary, 'placeholder="The decision, in one line"'))}
        ${field("detail", "Answer details <em>(bullets)</em>", area("detail", d.detail, 4, "- Who decided, and where\n- What changes because of it"))}
        <div class="editor-actions">
          <button class="btn accent" data-q="save" data-id="${esc(id)}">Save</button>
          <button class="btn" data-q="cancel" data-id="${esc(id)}" type="button">Cancel</button>
          ${id !== "new" ? `<button class="btn danger" data-q="delete" data-id="${esc(id)}" type="button">Delete</button>` : ""}
        </div>
      </form>`;
  }

  function card(rec) {
    if (state.drafts[rec.id]) return editor(rec.id);
    const item = state.items[rec.id];
    const resolved = rec.status === "resolved";
    const links = (rec.links || []).map((l) => external(l.url, l.label)).join("");
    const answer = rec.answer && (rec.answer.summary || rec.answer.detail)
      ? `<div class="answer"><div class="answer-head">${resolved ? "✅ " : "Proposed answer: "}${mdInline(rec.answer.summary || "")}</div>${md(rec.answer.detail)}</div>`
      : "";
    return `
      <article class="q-card ${resolved ? "is-resolved" : ""}" id="q-${esc(rec.id)}">
        ${state.notices[rec.id] ? `<p class="notice">${esc(state.notices[rec.id])}</p>` : ""}
        <header class="q-head">
          <h2>${resolved ? '<span class="check" aria-label="Resolved">✓</span> ' : ""}${mdInline(rec.title)}</h2>
          <div class="q-actions">
            <button class="btn btn-small" data-q="edit" data-id="${esc(rec.id)}">Edit</button>
            ${resolved
              ? `<button class="btn btn-small" data-q="reopen" data-id="${esc(rec.id)}">Reopen</button>`
              : `<button class="btn btn-small accent-2" data-q="resolve" data-id="${esc(rec.id)}">Resolve</button>`}
          </div>
        </header>
        ${rec.tags?.length ? `<div class="tags">${tagChips(rec.tags, state.filter.tag)}</div>` : ""}
        <div class="md">${md(rec.body)}</div>
        ${links ? `<div class="entry-links">${links}</div>` : ""}
        ${answer}
        <footer class="q-meta">Last saved by ${esc(who(item?.by))} · ${esc(item?.at ? stamp(item.at) : "")}</footer>
      </article>`;
  }

  function html() {
    if (state.error && !state.loaded) return `<p class="empty">Could not load questions: ${esc(state.error)}</p>`;
    if (!state.loaded) return `<p class="empty">Loading questions…</p>`;
    const all = ordered();
    const count = (s) => all.filter((r) => s === "all" || r.status === s).length;
    const tagCounts = {};
    for (const r of all) for (const t of r.tags || []) tagCounts[t] = (tagCounts[t] || 0) + 1;
    const shown = all.filter(matches);
    const f = state.filter;
    const seg = (s, label) => `<button class="seg ${f.status === s ? "is-active" : ""}" data-q="status" data-status="${s}">${label} <span>${count(s)}</span></button>`;
    return `
      <div class="page-head">
        <div>
          <h1>Open questions</h1>
          <p class="meta">Shared with everyone who can open this site. Edits save for everyone.</p>
        </div>
        ${state.drafts.new ? "" : `<button class="btn accent" data-q="new">New question</button>`}
      </div>
      ${state.drafts.new ? editor("new") : ""}
      <div class="toolbar">
        <div class="segmented">${seg("open", "Open")}${seg("resolved", "Resolved")}${seg("all", "All")}</div>
        <input class="search" type="search" placeholder="Search" value="${esc(f.text)}" data-q-search>
      </div>
      ${Object.keys(tagCounts).length ? `<div class="tags tag-filter">${Object.keys(tagCounts).sort().map((t) =>
        `<button class="tag ${t === f.tag ? "is-active" : ""}" data-q="tag" data-tag="${esc(t)}">#${esc(t)} <span>${tagCounts[t]}</span></button>`).join("")}</div>` : ""}
      ${shown.length ? shown.map(card).join("") : `<p class="empty">No questions match.</p>`}`;
  }

  function editing() {
    return Object.keys(state.drafts).length > 0;
  }

  function paint() {
    if (view && location.hash === "#questions") view.innerHTML = html();
  }

  async function refresh() {
    try {
      await load();
    } catch (err) {
      state.error = err.message;
    }
    if (!editing() && document.activeElement?.dataset?.qSearch === undefined) paint();
  }

  // ---------------------------------------------------------------- events

  document.addEventListener("click", (event) => {
    const el = event.target.closest("[data-q]");
    if (!el || location.hash !== "#questions") return;
    event.preventDefault();
    const id = el.dataset.id;
    const action = el.dataset.q;
    if (action === "status") state.filter.status = el.dataset.status;
    else if (action === "tag") state.filter.tag = state.filter.tag === el.dataset.tag ? null : el.dataset.tag;
    else if (action === "new") startDraft("new");
    else if (action === "edit") startDraft(id);
    else if (action === "resolve") startDraft(id, true);
    else if (action === "cancel") { delete state.drafts[id]; delete state.notices[id]; }
    else if (action === "save") return save(id);
    else if (action === "delete") return remove(id);
    else if (action === "reopen") {
      startDraft(id);
      state.drafts[id].status = "open";
      return save(id);
    }
    paint();
    if (action === "resolve") view.querySelector('[data-field="summary"]')?.focus();
    if (action === "new" || action === "edit") view.querySelector('[data-field="title"]')?.focus();
  });

  document.addEventListener("input", (event) => {
    const el = event.target;
    if (el.matches("[data-q-search]")) {
      state.filter.text = el.value;
      const pos = el.selectionStart;
      paint();
      const search = view.querySelector("[data-q-search]");
      search.focus();
      search.setSelectionRange(pos, pos);
      return;
    }
    const form = el.closest("form.editor");
    if (form && el.dataset.field) state.drafts[form.dataset.id][el.dataset.field] = el.value;
  });

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form.editor");
    if (!form) return;
    event.preventDefault();
    save(form.dataset.id);
  });

  window.addEventListener("focus", () => location.hash === "#questions" && refresh());
  setInterval(() => location.hash === "#questions" && !document.hidden && refresh(), REFRESH_MS);

  return {
    mount(el) {
      view = el;
      paint();
      refresh();
    },
  };
})();
