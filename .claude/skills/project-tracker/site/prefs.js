"use strict";

// Each reader's own choices, in their Yard key/value store (per signed-in user, so they
// follow the reader to any browser): { prs: { <number>: { priority, hidden } },
// docs: { <id>: { hidden } }, read: { <entry id>: <entry updated stamp> } }. One key,
// written with If-Match so two tabs both keep their change.

const Prefs = (() => {
  const URL = "/_yard/v1/kv/choices";
  let value = { prs: {}, docs: {}, read: {} };
  let version = null;
  let loaded = null;
  let error = null;
  const listeners = [];

  function normalize(raw) {
    const v = raw && typeof raw === "object" ? raw : {};
    return { prs: v.prs || {}, docs: v.docs || {}, read: v.read || {} };
  }

  async function fetchLatest() {
    const r = await fetch(URL, { cache: "no-store" });
    if (r.status === 404) return { value: normalize(null), version: null };
    if (!r.ok) throw new Error(`could not read your choices (${r.status})`);
    const env = await r.json();
    return { value: normalize(JSON.parse(env.value)), version: env.version };
  }

  function notify() {
    for (const fn of listeners) fn();
  }

  function load() {
    loaded = fetchLatest()
      .then((got) => {
        value = got.value;
        version = got.version;
        error = null;
      })
      .catch((err) => {
        error = err.message;
      })
      .finally(notify);
    return loaded;
  }

  // patch(value) edits a value in place. It runs on the local copy first so the page
  // answers at once, then on a fresh copy of the stored value for the save.
  async function update(patch) {
    patch(value);
    notify();
    for (let attempt = 0; attempt < 4; attempt++) {
      const latest = await fetchLatest();
      patch(latest.value);
      const r = await fetch(URL, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "If-Match": latest.version == null ? "*" : `"${latest.version}"`,
        },
        body: JSON.stringify(latest.value),
      });
      if (r.status === 412) continue;
      if (!r.ok) return fail(`could not save your choice (${r.status})`);
      value = latest.value;
      version = (await fetchLatest()).version;
      error = null;
      notify();
      return;
    }
    return fail("your choices kept changing in another tab; reload and try again");
  }

  // Put the stored value back so the page never shows a change that didn't save.
  async function fail(message) {
    await load();
    error = message;
    notify();
  }

  return {
    load,
    ready: () => loaded || load(),
    error: () => error,
    pr: (number) => value.prs[number] || {},
    doc: (id) => value.docs[id] || {},
    setPr: (number, fields) =>
      update((v) => {
        v.prs[number] = { ...(v.prs[number] || {}), ...fields };
      }),
    setDoc: (id, fields) =>
      update((v) => {
        v.docs[id] = { ...(v.docs[id] || {}), ...fields };
      }),
    readStamp: (entryId) => value.read[entryId],
    // marks maps entry id to its updated stamp, or to null to mark it unread.
    setRead: (marks) =>
      update((v) => {
        for (const [id, stamp] of Object.entries(marks)) {
          if (stamp == null) delete v.read[id];
          else v.read[id] = stamp;
        }
      }),
    onChange: (fn) => listeners.push(fn),
  };
})();
