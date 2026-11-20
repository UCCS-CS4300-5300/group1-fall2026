// Tests for the home page handoff (static/js/workout_logged.js).
//
// After a workout is logged, the workout page leaves a note and goes home; this script
// reads the note and fires the "exercise:logged" event that makes RepKin comment.
//
// The last test is the important one: it loads the REAL bubble script and the REAL
// handoff script in a page the way the browser does (bubble deferred), to prove the
// bubble is listening by the time the event fires.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM, ResourceLoader } = require("jsdom");

const ROOT = path.join(__dirname, "..");
const HANDOFF = fs.readFileSync(path.join(ROOT, "static", "js", "workout_logged.js"), "utf8");
const KEY = "repkinz.pendingWorkoutLog";
const NOW = 1700000000000;

const flush = async () => { for (let i = 0; i < 4; i += 1) { await new Promise((r) => setImmediate(r)); } };

function load() {
    const dom = new JSDOM("<!doctype html><body></body>", { runScripts: "outside-only", url: "http://localhost/" });
    dom.window.__workoutLoggedManualStart = true;
    dom.window.eval(HANDOFF);
    return dom.window;
}

const note = (value) => JSON.stringify(value);

// Values made inside the simulated browser come from a different JavaScript "realm",
// which strict comparison refuses even when the contents match. Compare plain copies.
const plain = (value) => JSON.parse(JSON.stringify(value));

// A tiny stand-in for sessionStorage.
function storageWith(initial) {
    const data = { ...initial };
    return {
        data,
        getItem: (key) => (key in data ? data[key] : null),
        removeItem: (key) => { delete data[key]; },
    };
}

// ---- Reading the note --------------------------------------------------------------------

test("a fresh note gives its log ids, and is removed so it can't be used twice", () => {
    const w = load();
    const storage = storageWith({ [KEY]: note({ logIds: [4, 5, 6], at: NOW - 1000 }) });
    assert.deepEqual(plain(w.WorkoutLogged.takePendingLogIds(storage, NOW)), [4, 5, 6]);
    assert.equal(KEY in storage.data, false);
    assert.equal(w.WorkoutLogged.takePendingLogIds(storage, NOW), null);
});

test("no note means nothing to announce", () => {
    const w = load();
    assert.equal(w.WorkoutLogged.takePendingLogIds(storageWith({}), NOW), null);
});

test("rubbish notes are ignored (and still cleared)", () => {
    const w = load();
    const bad = [
        "not json at all",
        "null",
        "42",
        note({}),
        note({ logIds: "5", at: NOW }),
        note({ logIds: [], at: NOW }),
        note({ logIds: [1.5], at: NOW }),
        note({ logIds: [0], at: NOW }),
        note({ logIds: [-3], at: NOW }),
        note({ logIds: ["7"], at: NOW }),
        note({ logIds: [null], at: NOW }),
        note({ logIds: [Number.MAX_SAFE_INTEGER + 2], at: NOW }),
        note({ logIds: Array.from({ length: 21 }, (_, i) => i + 1), at: NOW }),
        note({ logIds: [1] }),
        note({ logIds: [1], at: "yesterday" }),
    ];
    bad.forEach((raw) => {
        const storage = storageWith({ [KEY]: raw });
        assert.equal(w.WorkoutLogged.takePendingLogIds(storage, NOW), null, raw);
        assert.equal(KEY in storage.data, false, `cleared: ${raw}`);
    });
});

test("twenty ids is fine (a full workout is 4 sections of 5)", () => {
    const w = load();
    const ids = Array.from({ length: 20 }, (_, i) => i + 1);
    const storage = storageWith({ [KEY]: note({ logIds: ids, at: NOW }) });
    assert.deepEqual(plain(w.WorkoutLogged.takePendingLogIds(storage, NOW)), ids);
});

test("a note older than five minutes is dropped rather than announced late", () => {
    const w = load();
    const old = storageWith({ [KEY]: note({ logIds: [1], at: NOW - 5 * 60 * 1000 - 1 }) });
    assert.equal(w.WorkoutLogged.takePendingLogIds(old, NOW), null);
    const edge = storageWith({ [KEY]: note({ logIds: [1], at: NOW - 5 * 60 * 1000 }) });
    assert.deepEqual(plain(w.WorkoutLogged.takePendingLogIds(edge, NOW)), [1]);
});

test("a note dated in the future is dropped", () => {
    const w = load();
    const storage = storageWith({ [KEY]: note({ logIds: [1], at: NOW + 60000 }) });
    assert.equal(w.WorkoutLogged.takePendingLogIds(storage, NOW), null);
});

test("storage that throws is survived", () => {
    const w = load();
    const broken = { getItem: () => { throw new Error("blocked"); }, removeItem: () => {} };
    assert.equal(w.WorkoutLogged.takePendingLogIds(broken, NOW), null);
});

// ---- Announcing ----------------------------------------------------------------------------

test("announce fires exercise:logged with the log ids", () => {
    const w = load();
    w.sessionStorage.setItem(KEY, note({ logIds: [8, 9], at: NOW }));
    const heard = [];
    w.document.addEventListener("exercise:logged", (event) => heard.push(event.detail));
    assert.equal(w.WorkoutLogged.announce(w, NOW), true);
    assert.deepEqual(plain(heard), [{ logIds: [8, 9] }]);
    assert.equal(w.sessionStorage.getItem(KEY), null);
});

test("announce does nothing, and says so, when there is no note", () => {
    const w = load();
    const heard = [];
    w.document.addEventListener("exercise:logged", () => heard.push(1));
    assert.equal(w.WorkoutLogged.announce(w, NOW), false);
    assert.deepEqual(heard, []);
});

test("announce copes with a browser that blocks sessionStorage", () => {
    const w = load();
    const fakeWindow = {
        get sessionStorage() { throw new Error("SecurityError"); },
        document: w.document,
        CustomEvent: w.CustomEvent,
    };
    assert.equal(w.WorkoutLogged.announce(fakeWindow, NOW), false);
});

// ---- Timing --------------------------------------------------------------------------------

test("while the page is still loading it waits for DOMContentLoaded", () => {
    const w = load();
    const waiting = [];
    const heard = [];
    const fakeDocument = {
        readyState: "loading",
        addEventListener: (name, handler) => waiting.push({ name, handler }),
        dispatchEvent: (event) => heard.push(event.detail),
    };
    const fakeWindow = {
        document: fakeDocument,
        sessionStorage: storageWith({ [KEY]: note({ logIds: [3], at: NOW }) }),
        CustomEvent: w.CustomEvent,
    };
    w.WorkoutLogged.start(fakeWindow, () => NOW);
    assert.deepEqual(heard, [], "nothing fired yet");
    assert.deepEqual(waiting.map((entry) => entry.name), ["DOMContentLoaded"]);
    waiting[0].handler();
    assert.deepEqual(plain(heard), [{ logIds: [3] }]);
});

test("if the page has already loaded it announces straight away", () => {
    const w = load();
    w.sessionStorage.setItem(KEY, note({ logIds: [3], at: NOW }));
    const heard = [];
    w.document.addEventListener("exercise:logged", (event) => heard.push(event.detail));
    Object.defineProperty(w.document, "readyState", { value: "complete", configurable: true });
    w.WorkoutLogged.start(w, () => NOW);
    assert.deepEqual(plain(heard), [{ logIds: [3] }]);
});

// ---- Both real scripts together ----------------------------------------------------------------

// Serves /static/... files from the project folder, so the page can load its real scripts.
class StaticLoader extends ResourceLoader {
    fetch(url) {
        const match = /^http:\/\/localhost\/static\/(.+)$/.exec(url);
        if (!match) { return null; }
        return Promise.resolve(fs.readFileSync(path.join(ROOT, "static", match[1])));
    }
}

async function openHome(note) {
    const calls = [];
    const html = `<!doctype html><html><body>
      <div id="repkin-bubble" class="repkin-bubble" hidden
           data-message-url="/repkin/message/" data-csrf-token="test-token-0123456789-abcdef"
           data-messages="workout">
        <p class="repkin-bubble__text"></p>
        <button type="button" class="repkin-bubble__close">&times;</button>
      </div>
      <!-- the same order and attributes as home.html -->
      <script src="/static/core/repkin_bubble.js" defer></script>
      <script src="/static/js/workout_logged.js"></script>
    </body></html>`;
    const dom = new JSDOM(html, {
        url: "http://localhost/",
        runScripts: "dangerously",
        resources: new StaticLoader(),
        pretendToBeVisual: true,
        beforeParse(window) {
            if (note) { window.sessionStorage.setItem(KEY, JSON.stringify(note)); }
            window.fetch = async (url, options) => {
                const form = new URLSearchParams(options.body);
                calls.push({ url, kind: form.get("kind"), logIds: form.getAll("log_ids") });
                return {
                    ok: true, status: 200, redirected: false,
                    headers: { get: () => "application/json" },
                    json: async () => ({ message: "Great workout!", kind: "workout", fallback: false }),
                };
            };
        },
    });
    await new Promise((resolve) => dom.window.addEventListener("load", resolve));
    await flush();
    return { dom, calls };
}

test("on the real home-page load order, RepKin is asked to comment on the logged workout", async () => {
    const { dom, calls } = await openHome({ logIds: [21, 22, 23], at: Date.now() });
    try {
        assert.equal(calls.length, 1, "exactly one message request");
        assert.equal(calls[0].url, "/repkin/message/");
        assert.equal(calls[0].kind, "workout");
        assert.deepEqual(calls[0].logIds, ["21", "22", "23"]);
        assert.equal(dom.window.sessionStorage.getItem(KEY), null);
    } finally {
        dom.window.close();
    }
});

test("on the real home-page load order, no note means RepKin is not asked", async () => {
    const { dom, calls } = await openHome(null);
    try {
        assert.equal(calls.length, 0);
    } finally {
        dom.window.close();
    }
});
