const { test } = require("node:test");
const assert = require("node:assert/strict");
const { JSDOM } = require("jsdom");

const { readLevelCount, setupArmToggle } = require("../static/core/arm_toggle.js");

// Every arms + legs combination, like the page's sprite-gif-urls data.
function spriteMatrix() {
    const urls = {};
    for (let arms = 0; arms < 4; arms++) {
        urls[arms] = {};
        for (let legs = 0; legs < 4; legs++) {
            urls[arms][legs] = "/static/a" + arms + "_l" + legs + ".gif";
        }
    }
    return urls;
}

// A small fake locker room. The server is faked too: it saves whatever is sent,
// unless refuse is set, then it answers like a locked evolution.
function makePage({ maxArms, maxLegs, refuse = false }) {
    const html =
        '<img id="repkin-sprite" data-color="green" src="/static/a0_l0.gif">' +
        '<a id="arms-arrow-btn" href="?arms=1" data-arm-level="0"' +
        ' data-max-arm-level="' + maxArms + '"' +
        ' data-locked-message="Arms level 1 unlocks at 100 strength."></a>' +
        '<a id="legs-arrow-btn" href="?legs=1" data-leg-level="0"' +
        ' data-max-leg-level="' + maxLegs + '"' +
        ' data-locked-message="Legs level 1 unlocks at 100 endurance."></a>' +
        '<form id="sprite-save-form" action="/repkin/sprite/">' +
        '<input name="csrfmiddlewaretoken" value="token"></form>' +
        '<p id="sprite-save-status"></p>' +
        '<script id="sprite-gif-urls" type="application/json">' +
        JSON.stringify(spriteMatrix()) + "</script>";

    const dom = new JSDOM(html, { url: "http://localhost/locker-room/" });
    const saves = [];
    dom.window.fetch = async (url, options) => {
        const arms = Number(options.body.get("arms_level"));
        const legs = Number(options.body.get("legs_level"));
        saves.push({ arms, legs });
        if (refuse) {
            return { ok: false, json: async () => ({ error: "That evolution is still locked." }) };
        }
        return { ok: true, json: async () => ({ arms_level: arms, legs_level: legs }) };
    };
    setupArmToggle(dom.window.document, dom.window);
    return { dom, saves };
}

function click(dom, id) {
    const link = dom.window.document.getElementById(id);
    link.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true, cancelable: true }));
}

// Let the fake save finish before checking.
function settle() {
    return new Promise((resolve) => setTimeout(resolve, 10));
}

function statusText(dom) {
    return dom.window.document.getElementById("sprite-save-status").textContent;
}

test("level count comes from the highest unlocked level", () => {
    assert.equal(readLevelCount("0"), 1);
    assert.equal(readLevelCount("2"), 3);
    assert.equal(readLevelCount("3"), 4);
});

test("a missing or bad limit falls back to all 4 levels", () => {
    assert.equal(readLevelCount(undefined), 4);
    assert.equal(readLevelCount("banana"), 4);
    assert.equal(readLevelCount("-1"), 4);
});

test("locked arms do not try to save and show what unlocks them", async () => {
    const { dom, saves } = makePage({ maxArms: 0, maxLegs: 0 });
    click(dom, "arms-arrow-btn");
    await settle();

    assert.equal(saves.length, 0);
    assert.equal(statusText(dom), "Arms level 1 unlocks at 100 strength.");
});

test("arms only cycle through the unlocked levels", async () => {
    const { dom, saves } = makePage({ maxArms: 1, maxLegs: 0 });
    click(dom, "arms-arrow-btn");
    await settle();
    click(dom, "arms-arrow-btn");
    await settle();

    assert.deepEqual(saves, [{ arms: 1, legs: 0 }, { arms: 0, legs: 0 }]);
});

test("arms and legs are locked separately", async () => {
    const { dom, saves } = makePage({ maxArms: 3, maxLegs: 0 });
    click(dom, "arms-arrow-btn");
    await settle();
    click(dom, "legs-arrow-btn");
    await settle();

    assert.deepEqual(saves, [{ arms: 1, legs: 0 }]);
    assert.equal(statusText(dom), "Legs level 1 unlocks at 100 endurance.");
});

test("the server's locked message is shown if it refuses a save", async () => {
    const { dom } = makePage({ maxArms: 3, maxLegs: 3, refuse: true });
    click(dom, "arms-arrow-btn");
    await settle();

    assert.equal(statusText(dom), "That evolution is still locked.");
    const sprite = dom.window.document.getElementById("repkin-sprite");
    assert.equal(sprite.getAttribute("src"), "/static/a0_l0.gif");
});
