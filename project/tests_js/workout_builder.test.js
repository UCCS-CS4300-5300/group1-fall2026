// Tests for the workout logging page (static/js/workout_builder.js).
//
// Run them from this folder:   npm test
//
// They load the REAL page template (core/templates/core/workout_logging.html, with
// Django's tags filled in) and the real script, in a simulated browser (jsdom).
// The server, confirm() boxes, navigation and saved unit choice are all fakes, so
// each test can say exactly what the "server" answers and then check what the page did.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const ROOT = path.join(__dirname, "..");
const SCRIPT = fs.readFileSync(path.join(ROOT, "static", "js", "workout_builder.js"), "utf8");
const TEMPLATE = fs.readFileSync(
    path.join(ROOT, "core", "templates", "core", "workout_logging.html"), "utf8");

const URLS = {
    "core:home": "/",
    "core:workout_catalog": "/workouts/catalog/",
    "core:workout_presets": "/workouts/presets/",
    "core:workout_preset_save": "/workouts/presets/save/",
    "core:workout_preset_detail": "/workouts/presets/0/",
    "core:workout_preset_delete": "/workouts/presets/0/delete/",
};

// Fill in Django's template tags, so the test page is the real page.
function renderTemplate() {
    return TEMPLATE
        .replace(/\{% load static %\}/g, "")
        .replace(/\{% static '([^']+)' %\}/g, "/static/$1")
        .replace(/\{% url '([^']+)'(?: \d+)? %\}/g, (_, name) => URLS[name])
        .replace(/\{\{ csrf_token \}\}/g, "test-csrf-token")
        .replace(/<link [^>]*>/g, "")
        .replace(/<script src[^>]*><\/script>/g, "");
}

const EXERCISES = [
    { key: "back_squat", label: "Back squat", group: "Legs", input_type: "reps", weighted: true },
    { key: "push_ups", label: "Push-ups", group: "Chest", input_type: "reps", weighted: false },
    { key: "running", label: "Running", group: "Cardio", input_type: "distance", weighted: false },
    { key: "butterfly_stretch", label: "Butterfly stretch", group: "Stretches", input_type: "duration", weighted: false },
];

const CATALOG = {
    sections: [
        ["warmup_stretch", "Warm up and stretches"],
        ["warmup_sets", "Warm-up sets/exercises"],
        ["working_sets", "Working sets/exercises"],
        ["cooldown_stretch", "Cooldown and stretches"],
    ].map(([key, title]) => ({ key, title, max_items: 5, exercises: EXERCISES })),
    limits: { max_per_section: 5, max_name_length: 40, max_presets: 50 },
};

const reply = (status, data) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
const flush = async () => { for (let i = 0; i < 4; i += 1) { await new Promise((r) => setImmediate(r)); } };

// Opens the page. `routes(call)` plays the server and returns a reply() or undefined.
// `confirms` is the list of answers the fake confirm() box gives, in order.
async function openPage(options = {}) {
    const dom = new JSDOM(renderTemplate(), { runScripts: "outside-only", pretendToBeVisual: true });
    const w = dom.window;
    const calls = [];
    const confirmPrompts = [];
    const navigations = [];
    const answers = [...(options.confirms || [])];
    const stored = options.unit ? { "repkinz.unit": options.unit } : {};

    const env = {
        window: w,
        document: w.document,
        storage: { getItem: (key) => (key in stored ? stored[key] : null) },
        confirm: (text) => { confirmPrompts.push(text); return answers.length ? answers.shift() : true; },
        navigate: (url) => navigations.push(url),
        fetch: async (url, init = {}) => {
            const call = {
                url,
                method: init.method || "GET",
                headers: init.headers || {},
                body: init.body ? JSON.parse(init.body) : undefined,
            };
            calls.push(call);
            if (url === URLS["core:workout_catalog"]) { return reply(200, CATALOG); }
            const answer = options.routes ? options.routes(call) : undefined;
            if (answer instanceof Error) { throw answer; }
            return answer || reply(404, {});
        },
    };

    w.__workoutBuilderManualStart = true;
    w.eval(SCRIPT);
    const builder = w.WorkoutBuilder.create(env);
    builder.start();
    await flush();

    const doc = w.document;
    const page = {
        w, doc, calls, confirmPrompts, navigations, builder,
        $: (id) => doc.getElementById(id),
        saves: () => calls.filter((c) => c.url === URLS["core:workout_preset_save"]),
        async click(node) { node.click(); await flush(); },
        section: (key) => doc.querySelector(`[data-section="${key}"]`),
        addButton: (key) => doc.querySelector(`[data-section="${key}"] .wl-add`),
        items: (key) => [...doc.querySelectorAll(`[data-section="${key}"] .wl-item`)],
        async create() { await page.click(page.$("wl-create")); },
        async choose(key) {
            const select = page.$("wl-picker-exercise");
            select.value = key;
            select.dispatchEvent(new w.Event("change", { bubbles: true }));
        },
        async confirmPicker() { await page.click(page.$("wl-picker-confirm")); },
        // Open a section's "+", pick an exercise, fill the boxes, confirm.
        async add(section, key, values = {}) {
            await page.click(page.addButton(section));
            await page.choose(key);
            Object.entries(values).forEach(([id, value]) => { page.$(id).value = String(value); });
            await page.confirmPicker();
        },
        errorText: () => page.$("wl-errors").hidden ? "" : page.$("wl-errors").textContent,
        pickerOpen: () => page.$("wl-picker").hasAttribute("open"),
    };
    return page;
}

// ---- Starting out ------------------------------------------------------------------

test("starts with the two buttons and a hint, and no builder yet", async () => {
    const p = await openPage();
    assert.equal(p.$("wl-create").textContent.trim(), "Create new workout");
    assert.equal(p.$("wl-load").textContent.trim(), "Load workout preset");
    assert.equal(p.$("wl-builder").hidden, true);
    assert.equal(p.$("wl-intro").hidden, false);
    assert.equal(p.calls.filter((c) => c.url === URLS["core:workout_catalog"]).length, 1);
});

test("the dumbbell page links back to the workout room", async () => {
    const p = await openPage();
    assert.equal(p.doc.querySelector(".wl-back").getAttribute("href"), "/");
});

// ---- Building ----------------------------------------------------------------------

test("create shows the name box and the four sections in order, each with a + bubble", async () => {
    const p = await openPage();
    await p.create();
    assert.equal(p.$("wl-builder").hidden, false);
    assert.equal(p.$("wl-intro").hidden, true);
    assert.equal(p.$("wl-name").value, "");
    const titles = [...p.doc.querySelectorAll(".wl-section__title")].map((h) => h.textContent);
    assert.deepEqual(titles, [
        "Warm up and stretches", "Warm-up sets/exercises", "Working sets/exercises", "Cooldown and stretches",
    ]);
    const adds = [...p.doc.querySelectorAll(".wl-add")];
    assert.equal(adds.length, 4);
    assert.equal(adds[0].textContent, "+");
    assert.equal(adds[0].getAttribute("aria-label"), "Add an exercise to Warm up and stretches");
});

test("the picker groups the section's exercises under headings", async () => {
    const p = await openPage();
    await p.create();
    await p.click(p.addButton("working_sets"));
    assert.equal(p.pickerOpen(), true);
    assert.match(p.$("wl-picker-title").textContent, /Working sets\/exercises/);
    const groups = [...p.doc.querySelectorAll("#wl-picker-exercise optgroup")].map((g) => g.label);
    assert.deepEqual(groups, ["Legs", "Chest", "Cardio", "Stretches"]);
});

test("a weighted lift asks for sets, reps and an optional weight in pounds", async () => {
    const p = await openPage({ unit: "lbs" });
    await p.create();
    await p.click(p.addButton("working_sets"));
    await p.choose("back_squat");
    assert.equal(p.$("wl-field-reps").hidden, false);
    assert.equal(p.$("wl-field-weight").hidden, false);
    assert.equal(p.$("wl-field-duration").hidden, true);
    assert.equal(p.$("wl-field-distance").hidden, true);
    assert.match(p.$("wl-weight-label").textContent, /\(lb\)/);
});

test("a bodyweight exercise has no weight box; stretches ask for time; runs for distance", async () => {
    const p = await openPage();
    await p.create();
    await p.click(p.addButton("working_sets"));
    await p.choose("push_ups");
    assert.equal(p.$("wl-field-weight").hidden, true);
    await p.choose("butterfly_stretch");
    assert.equal(p.$("wl-field-duration").hidden, false);
    assert.equal(p.$("wl-field-reps").hidden, true);
    await p.choose("running");
    assert.equal(p.$("wl-field-distance").hidden, false);
    assert.equal(p.$("wl-field-duration").hidden, true);
});

test("confirming adds the exercise, closes the picker, and a fresh + appears below", async () => {
    const p = await openPage();
    await p.create();
    await p.add("working_sets", "back_squat", { "wl-sets": 3, "wl-reps": 8, "wl-weight": 135 });
    assert.equal(p.pickerOpen(), false);
    const items = p.items("working_sets");
    assert.equal(items.length, 1);
    assert.equal(items[0].querySelector(".wl-item__label").textContent, "Back squat");
    assert.equal(items[0].querySelector(".wl-item__detail").textContent, "3 \u00d7 8 @ 135 lb");
    assert.ok(p.addButton("working_sets"), "another + bubble is offered");
    assert.equal(p.items("warmup_sets").length, 0, "other sections are untouched");
});

test("a section stops offering + after five exercises", async () => {
    const p = await openPage();
    await p.create();
    for (let i = 0; i < 5; i += 1) {
        await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    }
    assert.equal(p.items("working_sets").length, 5);
    assert.equal(p.addButton("working_sets"), null);
    assert.match(p.section("working_sets").textContent, /full/);
    assert.ok(p.addButton("warmup_sets"), "the other sections still offer +");
});

test("times and distances are shown readably", async () => {
    const p = await openPage();
    await p.create();
    await p.add("cooldown_stretch", "butterfly_stretch", { "wl-minutes": 1, "wl-seconds": 30 });
    await p.add("cooldown_stretch", "butterfly_stretch", { "wl-seconds": 45 });
    await p.add("working_sets", "running", { "wl-distance": "2.50" });
    const details = (key) => p.items(key).map((b) => b.querySelector(".wl-item__detail").textContent);
    assert.deepEqual(details("cooldown_stretch"), ["1 min 30 sec", "45 sec"]);
    assert.deepEqual(details("working_sets"), ["2.5 mi"]);
});

// ---- Checking what people type -----------------------------------------------------

test("confirming without choosing an exercise explains what to do and keeps the picker open", async () => {
    const p = await openPage();
    await p.create();
    await p.click(p.addButton("working_sets"));
    await p.confirmPicker();
    assert.equal(p.pickerOpen(), true);
    assert.match(p.$("wl-picker-error").textContent, /Choose an exercise/);
    assert.equal(p.items("working_sets").length, 0);
});

test("sets and reps must be whole numbers in range", async () => {
    const p = await openPage();
    await p.create();
    const attempt = async (values) => {
        await p.click(p.addButton("working_sets"));
        await p.choose("push_ups");
        p.$("wl-sets").value = values.sets;
        p.$("wl-reps").value = values.reps;
        await p.confirmPicker();
        return p.$("wl-picker-error").hidden ? "" : p.$("wl-picker-error").textContent;
    };
    assert.match(await attempt({ sets: "", reps: "10" }), /Sets/);
    assert.match(await attempt({ sets: "0", reps: "10" }), /Sets/);
    assert.match(await attempt({ sets: "2.5", reps: "10" }), /Sets/);
    assert.match(await attempt({ sets: "101", reps: "10" }), /Sets/);
    assert.match(await attempt({ sets: "3", reps: "" }), /Reps/);
    assert.match(await attempt({ sets: "3", reps: "1001" }), /Reps/);
    assert.equal(p.items("working_sets").length, 0);
});

test("bad weights, durations and distances are rejected; an empty weight is fine", async () => {
    const p = await openPage();
    await p.create();
    const tryAdd = async (key, values) => {
        await p.click(p.addButton("working_sets"));
        await p.choose(key);
        Object.entries(values).forEach(([id, value]) => { p.$(id).value = value; });
        await p.confirmPicker();
        return p.$("wl-picker-error").hidden ? "" : p.$("wl-picker-error").textContent;
    };
    assert.match(await tryAdd("back_squat", { "wl-sets": "3", "wl-reps": "5", "wl-weight": "-5" }), /Weight/);
    assert.match(await tryAdd("butterfly_stretch", { "wl-minutes": "", "wl-seconds": "" }), /duration/i);
    assert.match(await tryAdd("butterfly_stretch", { "wl-minutes": "0", "wl-seconds": "75" }), /seconds/i);
    assert.match(await tryAdd("running", { "wl-distance": "0" }), /Distance/);
    assert.match(await tryAdd("running", { "wl-distance": "" }), /Distance/);
    p.$("wl-picker-cancel").click();
    await p.add("working_sets", "back_squat", { "wl-sets": "3", "wl-reps": "5", "wl-weight": "" });
    assert.equal(p.items("working_sets")[0].querySelector(".wl-item__detail").textContent, "3 \u00d7 5");
});

test("a number box the browser can't read is reported, not treated as blank", async () => {
    // Browsers report "" for text like "1e" and flag it with validity.badInput.
    const p = await openPage();
    await p.create();
    await p.click(p.addButton("working_sets"));
    await p.choose("back_squat");
    p.$("wl-sets").value = "3";
    p.$("wl-reps").value = "5";
    Object.defineProperty(p.$("wl-weight"), "validity", { value: { badInput: true } });
    await p.confirmPicker();
    assert.match(p.$("wl-picker-error").textContent, /plain numbers/);
    assert.equal(p.pickerOpen(), true);
    assert.equal(p.items("working_sets").length, 0);
});

test("cancel closes the picker without adding anything", async () => {
    const p = await openPage();
    await p.create();
    await p.click(p.addButton("working_sets"));
    await p.choose("push_ups");
    await p.click(p.$("wl-picker-cancel"));
    assert.equal(p.pickerOpen(), false);
    assert.equal(p.items("working_sets").length, 0);
});

// ---- Editing and removing ------------------------------------------------------------

test("tapping an added exercise reopens it filled in, and confirming updates it", async () => {
    const p = await openPage();
    await p.create();
    await p.add("working_sets", "back_squat", { "wl-sets": 3, "wl-reps": 8, "wl-weight": 135 });
    await p.click(p.items("working_sets")[0]);
    assert.equal(p.pickerOpen(), true);
    assert.match(p.$("wl-picker-title").textContent, /Edit/);
    assert.equal(p.$("wl-picker-exercise").value, "back_squat");
    assert.equal(p.$("wl-sets").value, "3");
    assert.equal(p.$("wl-weight").value, "135");
    assert.equal(p.$("wl-picker-remove").hidden, false);
    p.$("wl-reps").value = "5";
    await p.confirmPicker();
    assert.equal(p.items("working_sets").length, 1, "edited in place, not added again");
    assert.equal(p.items("working_sets")[0].querySelector(".wl-item__detail").textContent, "3 \u00d7 5 @ 135 lb");
});

test("an exercise can be changed to a different kind in the editor", async () => {
    const p = await openPage();
    await p.create();
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.items("working_sets")[0]);
    await p.choose("running");
    p.$("wl-distance").value = "3";
    await p.confirmPicker();
    assert.equal(p.items("working_sets")[0].querySelector(".wl-item__label").textContent, "Running");
    assert.equal(p.items("working_sets")[0].querySelector(".wl-item__detail").textContent, "3 mi");
});

test("remove deletes just that exercise; adding shows no Remove button", async () => {
    const p = await openPage();
    await p.create();
    await p.click(p.addButton("working_sets"));
    assert.equal(p.$("wl-picker-remove").hidden, true);
    p.$("wl-picker-cancel").click();
    await p.add("working_sets", "push_ups", { "wl-sets": 1, "wl-reps": 1 });
    await p.add("working_sets", "back_squat", { "wl-sets": 2, "wl-reps": 2 });
    await p.click(p.items("working_sets")[0]);
    await p.click(p.$("wl-picker-remove"));
    const left = p.items("working_sets");
    assert.equal(left.length, 1);
    assert.equal(left[0].querySelector(".wl-item__label").textContent, "Back squat");
});

// ---- Units ------------------------------------------------------------------------------

test("with the kilogram setting, labels say kg and km, and saving sends unit_system si", async () => {
    const p = await openPage({ unit: "kgs", routes: () => reply(201, { id: 1, name: "X", created: true }) });
    await p.create();
    assert.match(p.$("wl-units").textContent, /kg/);
    assert.match(p.$("wl-units").textContent, /km/);
    await p.add("working_sets", "back_squat", { "wl-sets": 3, "wl-reps": 5, "wl-weight": 60 });
    assert.equal(p.items("working_sets")[0].querySelector(".wl-item__detail").textContent, "3 \u00d7 5 @ 60 kg");
    p.$("wl-name").value = "Heavy";
    await p.click(p.$("wl-save"));
    assert.equal(p.saves()[0].body.unit_system, "si");
});

test("pounds are the default when nothing is stored", async () => {
    const p = await openPage();
    await p.create();
    assert.match(p.$("wl-units").textContent, /lb/);
});

// ---- Saving ------------------------------------------------------------------------------

test("save sends the workout (only the fields that apply) with the CSRF token, then goes home", async () => {
    const p = await openPage({ routes: () => reply(201, { id: 7, name: "Leg day", created: true }) });
    await p.create();
    p.$("wl-name").value = "  Leg day  ";
    await p.add("warmup_stretch", "butterfly_stretch", { "wl-minutes": 1, "wl-seconds": 0 });
    await p.add("working_sets", "back_squat", { "wl-sets": 3, "wl-reps": 8, "wl-weight": 135.5 });
    await p.add("working_sets", "push_ups", { "wl-sets": 2, "wl-reps": 15 });
    await p.add("cooldown_stretch", "running", { "wl-distance": 1 });
    await p.click(p.$("wl-save"));

    assert.equal(p.saves().length, 1);
    const save = p.saves()[0];
    assert.equal(save.method, "POST");
    assert.equal(save.headers["X-CSRFToken"], "test-csrf-token");
    assert.deepEqual(save.body, {
        name: "Leg day",
        unit_system: "imperial",
        sections: {
            warmup_stretch: [{ exercise_type: "butterfly_stretch", duration_seconds: 60 }],
            warmup_sets: [],
            working_sets: [
                { exercise_type: "back_squat", sets: 3, reps: 8, weight: 135.5 },
                { exercise_type: "push_ups", sets: 2, reps: 15 },
            ],
            cooldown_stretch: [{ exercise_type: "running", distance: 1 }],
        },
    });
    assert.deepEqual(p.navigations, ["/"]);
});

test("saving needs a name and at least one exercise, and asks the server nothing until then", async () => {
    const p = await openPage();
    await p.create();
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.$("wl-save"));
    assert.match(p.errorText(), /name/i);

    p.$("wl-name").value = "   ";
    await p.click(p.$("wl-save"));
    assert.match(p.errorText(), /name/i);

    const empty = await openPage();
    await empty.create();
    empty.$("wl-name").value = "Nothing yet";
    await empty.click(empty.$("wl-save"));
    assert.match(empty.errorText(), /at least one exercise/i);

    assert.equal(p.saves().length + empty.saves().length, 0);
    assert.deepEqual(p.navigations.concat(empty.navigations), []);
});

test("a name that is already taken asks to replace, and replacing resends with that id", async () => {
    let attempt = 0;
    const p = await openPage({
        confirms: [true],
        routes: (call) => {
            if (call.url !== URLS["core:workout_preset_save"]) { return undefined; }
            attempt += 1;
            return attempt === 1
                ? reply(409, { error: "name_taken", message: "taken", existing_id: 42 })
                : reply(200, { id: 42, name: "Leg day", created: false });
        },
    });
    await p.create();
    p.$("wl-name").value = "Leg day";
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.$("wl-save"));
    assert.match(p.confirmPrompts[0], /Leg day/);
    assert.match(p.confirmPrompts[0], /Replace/);
    assert.equal(p.saves().length, 2);
    assert.equal(p.saves()[0].body.id, undefined);
    assert.equal(p.saves()[1].body.id, 42);
    assert.deepEqual(p.navigations, ["/"]);
});

test("declining the replace keeps the workout on screen and goes nowhere", async () => {
    const p = await openPage({
        confirms: [false],
        routes: () => reply(409, { error: "name_taken", message: "taken", existing_id: 42 }),
    });
    await p.create();
    p.$("wl-name").value = "Leg day";
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.$("wl-save"));
    assert.equal(p.saves().length, 1);
    assert.deepEqual(p.navigations, []);
    assert.equal(p.items("working_sets").length, 1);
    assert.equal(p.$("wl-save").disabled, false, "the button works again");
});

test("server validation problems are listed with the section and exercise they belong to", async () => {
    const p = await openPage({
        routes: () => reply(400, {
            error: "validation", message: "Please fix the problems below.",
            errors: [
                { where: "item", message: "Reps is required.", section: "working_sets", index: 1, field: "reps" },
                { where: "name", message: "The name can be at most 40 characters." },
                { where: "section", message: "Too many.", section: "warmup_sets" },
                { where: "preset", message: "Add at least one exercise." },
            ],
        }),
    });
    await p.create();
    p.$("wl-name").value = "X";
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.$("wl-save"));
    const lines = [...p.doc.querySelectorAll("#wl-errors-list li")].map((li) => li.textContent);
    assert.deepEqual(lines, [
        "Working sets/exercises, exercise 2: Reps is required.",
        "Name: The name can be at most 40 characters.",
        "Warm-up sets/exercises: Too many.",
        "Add at least one exercise.",
    ]);
    assert.deepEqual(p.navigations, []);
});

test("other server failures show the server's message, or a friendly default", async () => {
    const p = await openPage({
        routes: () => reply(409, { error: "too_many_presets", message: "You can keep up to 50 workouts." }),
    });
    await p.create();
    p.$("wl-name").value = "X";
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.$("wl-save"));
    assert.match(p.errorText(), /up to 50 workouts/);

    const q = await openPage({ routes: () => reply(500, {}) });
    await q.create();
    q.$("wl-name").value = "X";
    await q.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await q.click(q.$("wl-save"));
    assert.match(q.errorText(), /couldn't be saved/);
});

test("a network failure is reported and the button works again", async () => {
    const p = await openPage({ routes: () => new Error("offline") });
    await p.create();
    p.$("wl-name").value = "X";
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.$("wl-save"));
    assert.match(p.errorText(), /reach the server/);
    assert.equal(p.$("wl-save").disabled, false);
    assert.deepEqual(p.navigations, []);
});

test("double-clicking save sends only one request", async () => {
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    const p = await openPage({
        routes: (call) => (call.url === URLS["core:workout_preset_save"]
            ? gate.then(() => reply(201, { id: 1, name: "X", created: true })) : undefined),
    });
    await p.create();
    p.$("wl-name").value = "X";
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    p.$("wl-save").click();
    p.$("wl-save").click();
    await flush();
    assert.equal(p.$("wl-save").disabled, true);
    release();
    await flush();
    assert.equal(p.saves().length, 1);
});

test("log workout is visible but switched off until it is built", async () => {
    const p = await openPage();
    await p.create();
    assert.equal(p.$("wl-log").textContent.trim(), "Log workout");
    assert.equal(p.$("wl-log").disabled, true);
});

// ---- Loading presets ------------------------------------------------------------------------

const PRESET_LIST = {
    presets: [
        { id: 2, name: "Leg day", exercise_count: 3, updated_at: "2026-11-10T12:00:00Z" },
        { id: 1, name: "Stretch", exercise_count: 1, updated_at: "2026-11-01T12:00:00Z" },
    ],
    max_presets: 50,
};

const PRESET_DETAIL = {
    id: 2, name: "Leg day", unit_system: "imperial", units: { weight: "lb", distance: "mi" },
    sections: {
        warmup_stretch: [{ exercise_type: "butterfly_stretch", label: "Butterfly stretch", input_type: "duration", duration_seconds: 90 }],
        warmup_sets: [],
        working_sets: [
            { exercise_type: "back_squat", label: "Back squat", input_type: "reps", sets: 3, reps: 8, weight: 135.0 },
            { exercise_type: "push_ups", label: "Push-ups", input_type: "reps", sets: 2, reps: 15 },
        ],
        cooldown_stretch: [{ exercise_type: "running", label: "Running", input_type: "distance", distance: 1.5 }],
    },
};

function presetRoutes(extra = () => undefined) {
    return (call) => {
        if (call.url === URLS["core:workout_presets"]) { return reply(200, PRESET_LIST); }
        if (call.url.startsWith("/workouts/presets/2/") && call.method === "GET") { return reply(200, PRESET_DETAIL); }
        return extra(call);
    };
}

test("load shows your presets with their size and date, and toggles closed again", async () => {
    const p = await openPage({ routes: presetRoutes() });
    await p.click(p.$("wl-load"));
    assert.equal(p.$("wl-presets").hidden, false);
    assert.equal(p.$("wl-load").getAttribute("aria-expanded"), "true");
    const rows = [...p.doc.querySelectorAll(".wl-preset")];
    assert.equal(rows.length, 2);
    assert.equal(rows[0].querySelector(".wl-preset__name").textContent, "Leg day");
    assert.match(rows[0].querySelector(".wl-preset__meta").textContent, /^3 exercises/);
    assert.match(rows[1].querySelector(".wl-preset__meta").textContent, /^1 exercise\b/);
    await p.click(p.$("wl-load"));
    assert.equal(p.$("wl-presets").hidden, true);
    assert.equal(p.$("wl-load").getAttribute("aria-expanded"), "false");
});

test("with no presets, a friendly message is shown", async () => {
    const p = await openPage({ routes: () => reply(200, { presets: [], max_presets: 50 }) });
    await p.click(p.$("wl-load"));
    assert.equal(p.$("wl-presets-empty").hidden, false);
    assert.equal(p.doc.querySelectorAll(".wl-preset").length, 0);
});

test("a preset name that looks like HTML is shown as plain text", async () => {
    const nasty = '<img src=x onerror="window.hacked=1">';
    const p = await openPage({
        routes: () => reply(200, { presets: [{ id: 9, name: nasty, exercise_count: 1, updated_at: "2026-01-01T00:00:00Z" }] }),
    });
    await p.click(p.$("wl-load"));
    assert.equal(p.doc.querySelector(".wl-preset__name").textContent, nasty);
    assert.equal(p.doc.querySelector(".wl-preset img"), null);
    assert.equal(p.w.hacked, undefined);
});

test("opening a preset fills in the name and every exercise, in the user's units", async () => {
    const p = await openPage({ unit: "kgs", routes: presetRoutes() });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__open"));
    const detailCall = p.calls.find((c) => c.url.startsWith("/workouts/presets/2/"));
    assert.equal(detailCall.url, "/workouts/presets/2/?unit_system=si");
    assert.equal(p.$("wl-builder").hidden, false);
    assert.equal(p.$("wl-presets").hidden, true);
    assert.equal(p.$("wl-name").value, "Leg day");
    const detail = (key) => p.items(key).map((b) => b.querySelector(".wl-item__detail").textContent);
    assert.deepEqual(detail("warmup_stretch"), ["1 min 30 sec"]);
    assert.deepEqual(detail("working_sets"), ["3 \u00d7 8 @ 135 kg", "2 \u00d7 15"]);
    assert.deepEqual(detail("cooldown_stretch"), ["1.5 km"]);
});

test("saving a loaded preset updates it (sends its id) instead of making a copy", async () => {
    const p = await openPage({
        routes: presetRoutes((call) => (call.url === URLS["core:workout_preset_save"]
            ? reply(200, { id: 2, name: "Leg day", created: false }) : undefined)),
    });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__open"));
    await p.add("warmup_sets", "push_ups", { "wl-sets": 1, "wl-reps": 10 });
    await p.click(p.$("wl-save"));
    assert.equal(p.saves()[0].body.id, 2);
    assert.equal(p.saves()[0].body.sections.warmup_sets.length, 1);
    assert.equal(p.saves()[0].body.sections.working_sets.length, 2);
    assert.deepEqual(p.navigations, ["/"]);
});

test("opening a preset over unsaved changes asks first, and declining changes nothing", async () => {
    const p = await openPage({ confirms: [false], routes: presetRoutes() });
    await p.create();
    p.$("wl-name").value = "Mine";
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__open"));
    assert.match(p.confirmPrompts[0], /unsaved/i);
    assert.equal(p.$("wl-name").value, "Mine");
    assert.equal(p.calls.filter((c) => c.url.startsWith("/workouts/presets/2/")).length, 0);
});

test("starting a new workout over unsaved changes asks first", async () => {
    const p = await openPage({ confirms: [false, true] });
    await p.create();
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    await p.create();
    assert.equal(p.items("working_sets").length, 1, "declined, so nothing was cleared");
    await p.create();
    assert.equal(p.items("working_sets").length, 0, "accepted, so a blank workout starts");
});

test("creating a new workout when nothing is unsaved does not nag", async () => {
    const p = await openPage();
    await p.create();
    await p.create();
    assert.equal(p.confirmPrompts.length, 0);
});

test("a preset that can't be loaded shows an error and leaves the page alone", async () => {
    const p = await openPage({
        routes: (call) => (call.url === URLS["core:workout_presets"]
            ? reply(200, PRESET_LIST) : reply(404, { message: "That workout doesn't exist." })),
    });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__open"));
    assert.match(p.errorText(), /doesn't exist/);
    assert.equal(p.$("wl-builder").hidden, true);
});

test("the list failing to load shows an error", async () => {
    const p = await openPage({ routes: () => reply(500, {}) });
    await p.click(p.$("wl-load"));
    assert.match(p.errorText(), /couldn't be loaded/);
    assert.equal(p.$("wl-presets").hidden, true);
});

// ---- Deleting presets -----------------------------------------------------------------------

test("delete asks first; declining sends nothing", async () => {
    const p = await openPage({ confirms: [false], routes: presetRoutes() });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__delete"));
    assert.match(p.confirmPrompts[0], /Delete "Leg day"/);
    assert.equal(p.calls.filter((c) => c.url.endsWith("/delete/")).length, 0);
    assert.equal(p.doc.querySelectorAll(".wl-preset").length, 2);
});

test("confirming delete removes the preset from the list and says so", async () => {
    const p = await openPage({
        confirms: [true],
        routes: presetRoutes((call) => (call.url === "/workouts/presets/2/delete/" ? reply(200, { deleted: true }) : undefined)),
    });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__delete"));
    const del = p.calls.find((c) => c.url.endsWith("/delete/"));
    assert.equal(del.method, "POST");
    assert.equal(del.headers["X-CSRFToken"], "test-csrf-token");
    assert.equal(p.doc.querySelectorAll(".wl-preset").length, 1);
    assert.match(p.$("wl-status").textContent, /Deleted "Leg day"/);
});

test("deleting the last preset shows the empty message", async () => {
    const p = await openPage({
        confirms: [true],
        routes: (call) => (call.url === URLS["core:workout_presets"]
            ? reply(200, { presets: [PRESET_LIST.presets[0]] })
            : reply(200, { deleted: true })),
    });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__delete"));
    assert.equal(p.$("wl-presets-empty").hidden, false);
});

test("a failed delete leaves the row and shows an error", async () => {
    const p = await openPage({
        confirms: [true],
        routes: presetRoutes((call) => (call.url.endsWith("/delete/") ? reply(404, { message: "That workout doesn't exist." }) : undefined)),
    });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__delete"));
    assert.equal(p.doc.querySelectorAll(".wl-preset").length, 2);
    assert.match(p.errorText(), /doesn't exist/);
});

test("deleting the preset you have open means saving makes a new one", async () => {
    const p = await openPage({
        confirms: [true],
        routes: presetRoutes((call) => {
            if (call.url.endsWith("/delete/")) { return reply(200, { deleted: true }); }
            if (call.url === URLS["core:workout_preset_save"]) { return reply(201, { id: 5, name: "Leg day", created: true }); }
            return undefined;
        }),
    });
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__open"));
    await p.click(p.$("wl-load"));
    await p.click(p.doc.querySelector(".wl-preset__delete"));
    await p.click(p.$("wl-save"));
    assert.equal(p.saves()[0].body.id, undefined);
});

// ---- Leaving the page --------------------------------------------------------------------------

test("leaving with unsaved changes triggers the browser's warning; a clean page does not", async () => {
    const p = await openPage();
    const leave = () => {
        const event = new p.w.Event("beforeunload", { cancelable: true });
        p.w.dispatchEvent(event);
        return event.defaultPrevented;
    };
    await p.create();
    assert.equal(leave(), false);
    await p.add("working_sets", "push_ups", { "wl-sets": 3, "wl-reps": 10 });
    assert.equal(leave(), true);
});

test("typing a name counts as a change", async () => {
    const p = await openPage();
    await p.create();
    p.$("wl-name").value = "Hi";
    p.$("wl-name").dispatchEvent(new p.w.Event("input", { bubbles: true }));
    const event = new p.w.Event("beforeunload", { cancelable: true });
    p.w.dispatchEvent(event);
    assert.equal(event.defaultPrevented, true);
});

// ---- When the exercise list can't be fetched -------------------------------------------------------

test("if the exercise list fails to load, the page says so and retries on the next tap", async () => {
    let fail = true;
    const dom = new JSDOM(renderTemplate(), { runScripts: "outside-only" });
    const w = dom.window;
    const env = {
        window: w, document: w.document, storage: { getItem: () => null },
        confirm: () => true, navigate: () => {},
        fetch: async () => (fail ? reply(500, {}) : reply(200, CATALOG)),
    };
    w.__workoutBuilderManualStart = true;
    w.eval(SCRIPT);
    w.WorkoutBuilder.create(env).start();
    await flush();
    w.document.getElementById("wl-create").click();
    await flush();
    assert.equal(w.document.getElementById("wl-builder").hidden, true);
    assert.match(w.document.getElementById("wl-errors").textContent, /exercise list/);
    fail = false;
    w.document.getElementById("wl-create").click();
    await flush();
    assert.equal(w.document.getElementById("wl-builder").hidden, false);
    assert.equal(w.document.getElementById("wl-errors").hidden, true);
});

test("the script does nothing on a page that isn't the workout page", () => {
    const dom = new JSDOM("<!doctype html><body><p>hi</p></body>", { runScripts: "outside-only" });
    dom.window.__workoutBuilderManualStart = true;
    dom.window.eval(SCRIPT);
    assert.equal(dom.window.WorkoutBuilder.create({ document: dom.window.document }), null);
});
