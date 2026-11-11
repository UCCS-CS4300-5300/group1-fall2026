// Tests for RepKin's speech bubble (static/core/repkin_bubble.js).
//
// Run them from this folder:   LINK:https://nodejs.org/en/download
//# Download and install fnm:
//winget install Schniz.fnm
//# In lieu of restarting the shell
//fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
//# Download and install Node.js:
//fnm install --use 26
//# Verify the Node.js version:
//node -v # Should print "v26.13.1".
//# Verify npm version:
//npm -v # Should print "11.20.0".
// ====================Use commands from the above link, then run:       npm install    AND      npm test
// THIS SHOULD RUN ALL THE TESTS!!! 
// They run the real script in a simulated page (jsdom) with a fake fetch() and
// a fake clock, so timing rules like "60 seconds idle" are tested instantly.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const FakeTimers = require("@sinonjs/fake-timers");

const SCRIPT_PATH =
    process.env.BUBBLE_SCRIPT || path.join(__dirname, "..", "static", "core", "repkin_bubble.js");
const SCRIPT = fs.readFileSync(SCRIPT_PATH, "utf8");

// The parts of the home page the script cares about.
const PAGE = `<!doctype html><html><body>
  <div id="mainMenu" class="main_menu hidden"></div>
  <dialog id="welcome-modal"></dialog>
  <dialog id="setup-modal"></dialog>
  <dialog id="exercise-modal"></dialog>
  <div id="repkin-bubble" class="repkin-bubble" hidden
       data-message-url="/repkin/message/" data-csrf-token="test-token-0123456789-abcdef">
    <p class="repkin-bubble__text"></p>
    <button type="button" class="repkin-bubble__close">&times;</button>
  </div>
</body></html>`;

const json = (data, extra = {}) => ({
    ok: true, status: 200, redirected: false,
    headers: { get: () => "application/json" }, json: async () => data, ...extra,
});

// Open a page. `responder(call)` plays the server. `opts` sets the starting state
// (dialogs open, menu open, tab hidden) BEFORE the script runs, like a real page
// whose inline scripts have already opened the welcome modal.
function openPage(responder, opts = {}) {
    const dom = new JSDOM(PAGE, { runScripts: "outside-only", pretendToBeVisual: true });
    const w = dom.window;
    const doc = w.document;
    (opts.dialogsOpen || []).forEach((id) => doc.getElementById(id).setAttribute("open", ""));
    if (opts.menuOpen) doc.getElementById("mainMenu").classList.remove("hidden");
    if (opts.hidden) Object.defineProperty(doc, "visibilityState", { value: "hidden", configurable: true });

    const clock = FakeTimers.withGlobal(w).install({ toFake: ["setTimeout", "clearTimeout"] });
    const calls = [];
    w.fetch = async (url, options) => {
        const form = new URLSearchParams(options.body);
        const call = {
            url, method: options.method, kind: form.get("kind"),
            csrf: form.get("csrfmiddlewaretoken"), logIds: form.getAll("log_ids"), options,
        };
        calls.push(call);
        return responder(call, calls.length);
    };
    w.eval(SCRIPT);

    const bubble = doc.getElementById("repkin-bubble");
    return {
        w, doc, calls, bubble,
        text: () => bubble.querySelector(".repkin-bubble__text").textContent,
        tick: (ms) => clock.tickAsync(ms),
        kinds: (kind) => calls.filter((c) => c.kind === kind),
        open: (id) => doc.getElementById(id).setAttribute("open", ""),
        close: (id) => doc.getElementById(id).removeAttribute("open"),
        announceExercise: (...ids) =>
            doc.dispatchEvent(new w.CustomEvent("exercise:logged", { detail: { logIds: ids } })),
        setVisibility: (state) => {
            Object.defineProperty(doc, "visibilityState", { value: state, configurable: true });
            doc.dispatchEvent(new w.Event("visibilitychange"));
        },
    };
}

const says = (text) => async (call) => json({ message: text, kind: call.kind });

// A fake server that behaves like the real one: ONE greeting per login, used up
// the moment it is asked for. Shared between page loads, like the real session.
function fakeServer() {
    const state = { greetingOwed: true };
    state.respond = async (call) => {
        if (call.kind === "greeting") {
            if (!state.greetingOwed) return json({ message: null, kind: "greeting", reason: "already_greeted" });
            state.greetingOwed = false;
            return json({ message: "Hi, welcome!", kind: "greeting" });
        }
        return json({ message: null, kind: call.kind });
    };
    return state;
}

// ---------------------------------------------------------------- greeting

test("asks for exactly one greeting when the page is clear, as a form POST with the CSRF token", async () => {
    const p = openPage(says("Hi there!"));
    await p.tick(0);
    assert.equal(p.calls.length, 1);
    assert.equal(p.calls[0].kind, "greeting");
    assert.equal(p.calls[0].method, "POST");
    assert.equal(p.calls[0].url, "/repkin/message/");
    assert.equal(p.calls[0].csrf, "test-token-0123456789-abcdef");
    assert.equal(p.calls[0].options.credentials, "same-origin");
});

test("shows the greeting", async () => {
    const p = openPage(says("Hi there!"));
    await p.tick(0);
    assert.equal(p.bubble.hidden, false);
    assert.equal(p.text(), "Hi there!");
});

test("stays hidden when the server has no greeting to give", async () => {
    const p = openPage(async () => json({ message: null, kind: "greeting", reason: "already_greeted" }));
    await p.tick(0);
    assert.equal(p.bubble.hidden, true);
});

test("does NOT ask for the greeting while the welcome modal is open", async () => {
    const p = openPage(says("Welcome!"), { dialogsOpen: ["welcome-modal"] });
    await p.tick(0);
    await p.tick(5000);
    assert.equal(p.kinds("greeting").length, 0, "asking now would use up the greeting behind the modal");
    assert.equal(p.bubble.hidden, true);
});

test("asks once the welcome modal closes (for example, the user pressed Escape), then shows it", async () => {
    const p = openPage(says("Welcome!"), { dialogsOpen: ["welcome-modal"] });
    await p.tick(3000);
    p.close("welcome-modal");
    await p.tick(600);
    assert.equal(p.kinds("greeting").length, 1);
    assert.equal(p.text(), "Welcome!");
});

test("the hand-off from the welcome modal to the setup modal does not trigger a request", async () => {
    const p = openPage(says("Welcome!"), { dialogsOpen: ["welcome-modal"] });
    await p.tick(1000);
    p.open("setup-modal");        // like the "Create RepKin" button:
    p.close("welcome-modal");     // one dialog opens as the other closes, in the same moment
    await p.tick(5000);
    assert.equal(p.kinds("greeting").length, 0);
    p.close("setup-modal");       // user cancels
    await p.tick(600);
    assert.equal(p.kinds("greeting").length, 1);
});

test("waits while the main menu overlay is open", async () => {
    const p = openPage(says("Hi!"), { menuOpen: true });
    await p.tick(3000);
    assert.equal(p.kinds("greeting").length, 0);
    p.doc.getElementById("mainMenu").classList.add("hidden");
    await p.tick(600);
    assert.equal(p.kinds("greeting").length, 1);
});

test("waits while the tab is hidden, then asks when it becomes visible", async () => {
    const p = openPage(says("Hi!"), { hidden: true });
    await p.tick(5000);
    assert.equal(p.kinds("greeting").length, 0);
    p.setVisibility("visible");
    await p.tick(600);
    assert.equal(p.kinds("greeting").length, 1);
});

test("a NEW USER's journey across the page reload is greeted (the original bug)", async () => {
    const server = fakeServer();

    // Page load #1: the welcome modal is open. The user clicks Create RepKin, then Save.
    const page1 = openPage(server.respond, { dialogsOpen: ["welcome-modal"] });
    await page1.tick(1000);
    page1.open("setup-modal");
    page1.close("welcome-modal");
    await page1.tick(3000);
    assert.equal(page1.kinds("greeting").length, 0);
    assert.equal(page1.bubble.hidden, true);
    // Saving the form reloads the page, so page 1 is gone. The greeting is still owed:
    assert.equal(server.greetingOwed, true);

    // Page load #2: setup is finished, nothing is open.
    const page2 = openPage(server.respond);
    await page2.tick(1000);
    assert.equal(page2.kinds("greeting").length, 1);
    assert.equal(page2.bubble.hidden, false);
    assert.equal(page2.text(), "Hi, welcome!");
});

test("a returning user (no modal) is greeted straight away, once", async () => {
    const server = fakeServer();
    const page1 = openPage(server.respond);
    await page1.tick(0);
    assert.equal(page1.text(), "Hi, welcome!");
    const refreshed = openPage(server.respond);       // a refresh: no second greeting
    await refreshed.tick(0);
    assert.equal(refreshed.bubble.hidden, true);
});

// ------------------------------------------------------------ showing / hiding

test("model text is inserted as text, never as HTML", async () => {
    const evil = '<img src=x onerror="window.pwned=1"><b>bold</b>';
    const p = openPage(says(evil));
    await p.tick(0);
    assert.equal(p.text(), evil);
    assert.equal(p.bubble.querySelector("img"), null);
    assert.equal(p.bubble.querySelector("b"), null);
    assert.equal(p.w.pwned, undefined);
});

test("hides itself after 12 seconds", async () => {
    const p = openPage(says("Hi!"));
    await p.tick(0);
    await p.tick(11900);
    assert.equal(p.bubble.hidden, false);
    await p.tick(200);
    assert.equal(p.bubble.hidden, true);
});

test("the close button dismisses it straight away", async () => {
    const p = openPage(says("Hi!"));
    await p.tick(0);
    p.bubble.querySelector(".repkin-bubble__close").click();
    assert.equal(p.bubble.hidden, true);
    assert.equal(p.text(), "");
});

test("Escape dismisses it", async () => {
    const p = openPage(says("Hi!"));
    await p.tick(0);
    p.doc.dispatchEvent(new p.w.KeyboardEvent("keydown", { key: "Escape" }));
    assert.equal(p.bubble.hidden, true);
});

test("an empty or non-text message is ignored", async () => {
    for (const bad of [{ message: "" }, { message: 123 }, { message: { x: 1 } }, {}, null]) {
        const p = openPage(async () => json(bad));
        await p.tick(0);
        assert.equal(p.bubble.hidden, true, JSON.stringify(bad));
    }
});

// ------------------------------------------------------------ workout compliments

test("a logged exercise sends ONE workout request carrying its log id", async () => {
    const p = openPage(async (c) => json({ message: c.kind === "workout" ? "Great push ups!" : null }));
    await p.tick(0);
    p.announceExercise(42);
    await p.tick(0);
    assert.equal(p.kinds("workout").length, 1);
    assert.deepEqual(p.kinds("workout")[0].logIds, ["42"]);
    assert.equal(p.text(), "Great push ups!");
});

test("a workout compliment waits behind the exercise modal and is not lost", async () => {
    const p = openPage(async (c) => json({ message: c.kind === "workout" ? "Great job!" : null }));
    await p.tick(0);
    p.open("exercise-modal");
    p.announceExercise(7);
    await p.tick(1000);
    assert.equal(p.bubble.hidden, true);
    p.close("exercise-modal");
    await p.tick(600);
    assert.equal(p.text(), "Great job!");
});

test("a workout compliment replaces an idle message that is showing", async () => {
    const p = openPage(async (c) => json({ message: c.kind === "workout" ? "Nice work!" : "Just chilling" }));
    await p.tick(0);
    assert.equal(p.text(), "Just chilling");
    p.announceExercise(1);
    await p.tick(0);
    assert.equal(p.text(), "Nice work!");
});

test("a workout request still goes out while another request is in flight", async () => {
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    const p = openPage(async (c) => {
        if (c.kind === "greeting") await gate;
        return json({ message: "x", kind: c.kind });
    });
    await p.tick(0);
    p.announceExercise(5);
    await p.tick(0);
    assert.equal(p.kinds("workout").length, 1);
    release();
});

// ------------------------------------------------------------ idle messages

test("no idle message before 60 seconds of quiet, then exactly one", async () => {
    const p = openPage(async (c) => json({ message: c.kind === "idle" ? "Stretch time!" : null }));
    await p.tick(0);
    await p.tick(59000);
    assert.equal(p.kinds("idle").length, 0);
    await p.tick(1500);
    assert.equal(p.kinds("idle").length, 1);
    assert.equal(p.text(), "Stretch time!");
});

test("any tap or key press restarts the idle countdown", async () => {
    const p = openPage(async (c) => json({ message: null, kind: c.kind }));
    await p.tick(0);
    await p.tick(50000);
    p.doc.dispatchEvent(new p.w.Event("pointerdown"));
    await p.tick(50000);
    assert.equal(p.kinds("idle").length, 0);
    await p.tick(11000);
    assert.equal(p.kinds("idle").length, 1);
});

test("keeps chatting every 90 seconds while the user stays idle", async () => {
    const p = openPage(async (c) => json({ message: c.kind === "idle" ? "Still here!" : null }));
    await p.tick(0);
    await p.tick(61000);
    await p.tick(90000);
    await p.tick(90000);
    assert.equal(p.kinds("idle").length, 3);
});

test("idle waits while a dialog is open", async () => {
    const p = openPage(async (c) => json({ message: null, kind: c.kind }));
    await p.tick(0);
    p.open("exercise-modal");
    await p.tick(65000);
    assert.equal(p.kinds("idle").length, 0);
    p.close("exercise-modal");
    await p.tick(11000);
    assert.equal(p.kinds("idle").length, 1);
});

test("idle is not requested while the tab is hidden", async () => {
    const p = openPage(async (c) => json({ message: null, kind: c.kind }));
    await p.tick(0);
    p.setVisibility("hidden");
    await p.tick(300000);
    assert.equal(p.kinds("idle").length, 0);
    p.setVisibility("visible");
    await p.tick(61000);
    assert.equal(p.kinds("idle").length, 1);
});

test("an idle message does not pile on top of one that is still showing", async () => {
    const p = openPage(async (c) => json({ message: c.kind === "idle" ? "First idle" : null }));
    await p.tick(0);
    await p.tick(61000);
    assert.equal(p.bubble.hidden, false);
    p.doc.dispatchEvent(new p.w.Event("pointerdown"));
    await p.tick(1000);
    assert.equal(p.kinds("idle").length, 1);
});

// ------------------------------------------------------------ when things go wrong

test("a login redirect (session ended) silences everything for good", async () => {
    const p = openPage(async () => ({
        ok: true, status: 200, redirected: true,
        headers: { get: () => "text/html" }, json: async () => { throw new Error("not json"); },
    }));
    await p.tick(0);
    assert.equal(p.bubble.hidden, true);
    const before = p.calls.length;
    await p.tick(400000);
    p.announceExercise(1);
    await p.tick(1000);
    assert.equal(p.calls.length, before);
});

test("a 429 or a server error stays quiet and idle keeps going", async () => {
    let n = 0;
    const p = openPage(async (c) => {
        n += 1;
        if (c.kind === "greeting") return json({ message: null });
        if (n === 2) return { ok: false, status: 429, redirected: false, headers: { get: () => "application/json" }, json: async () => ({ error: "soon" }) };
        return { ok: false, status: 500, redirected: false, headers: { get: () => "text/html" }, json: async () => { throw new Error("html"); } };
    });
    await p.tick(0);
    await p.tick(61000);
    assert.equal(p.bubble.hidden, true);
    await p.tick(91000);
    assert.equal(p.kinds("idle").length, 2);
    assert.equal(p.bubble.hidden, true);
});

test("a network failure does not throw or show anything", async () => {
    const p = openPage(async () => { throw new Error("offline"); });
    await p.tick(0);
    await p.tick(61000);
    assert.equal(p.bubble.hidden, true);
});
