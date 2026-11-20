const { test } = require("node:test");
const assert = require("node:assert/strict");
const { JSDOM } = require("jsdom");

const { nextLimbLevel, setupArmToggle } = require("../static/core/arm_toggle.js");

// Build a small locker-room page with sprite URLs and a mocked save endpoint.
function makePage(armsLevel = 0, legsLevel = 0, color = "green") {
    const urls = {};
    for (let arms = 0; arms < 4; arms++) {
        urls[arms] = {};
        for (let legs = 0; legs < 4; legs++) {
            urls[arms][legs] = `/static/sprite-${arms}-${legs}.gif`;
        }
    }

    const html =
        '<img id="repkin-sprite" src="' + urls[armsLevel][legsLevel] + '" data-repkin-color="' + color + '"' +
        (legsLevel === 0 ? ' class="user-base-gif non-green-no-legs"' : ' class="user-base-gif"') + '>' +
        '<a id="arms-arrow-btn" href="?arms=1" data-arm-level="' + armsLevel + '"></a>' +
        '<a id="legs-arrow-btn" href="?legs=1" data-leg-level="' + legsLevel + '"></a>' +
        '<script id="sprite-gif-urls" type="application/json">' + JSON.stringify(urls) + "</script>" +
        '<form id="sprite-save-form" action="/repkin/sprite/">' +
        '<input name="csrfmiddlewaretoken" value="test-token"></form>' +
        '<p id="sprite-save-status"></p>';
    const dom = new JSDOM(html, { url: "http://localhost/locker-room/" });
    const savedRequests = [];
    dom.window.fetch = async (url, options) => {
        const values = Object.fromEntries(new URLSearchParams(options.body));
        savedRequests.push({ url, values });
        return {
            ok: true,
            json: async () => ({
                arms_level: Number(values.arms_level),
                legs_level: Number(values.legs_level),
            }),
        };
    };
    setupArmToggle(dom.window.document, dom.window);
    return { dom, savedRequests };
}

// Click a limb control and wait for its save handler to finish.
async function clickControl(dom, controlId) {
    const link = dom.window.document.getElementById(controlId);
    const click = new dom.window.MouseEvent("click", { bubbles: true, cancelable: true });
    const pageWouldNavigate = link.dispatchEvent(click);
    await new Promise((resolve) => setImmediate(resolve));
    return pageWouldNavigate;
}

// Return the currently displayed sprite URL.
function spriteSrc(dom) {
    return dom.window.document.getElementById("repkin-sprite").getAttribute("src");
}

// Check that limb levels advance and wrap to zero.
test("limb levels move forward and wrap after the last one", () => {
    assert.equal(nextLimbLevel(0, 4), 1);
    assert.equal(nextLimbLevel(2, 4), 3);
    assert.equal(nextLimbLevel(3, 4), 0);
});

// Check that changing arms saves the selection without navigating away.
test("changing arms saves the selection without reloading", async () => {
    const { dom, savedRequests } = makePage();
    const pageWouldNavigate = await clickControl(dom, "arms-arrow-btn");

    assert.equal(pageWouldNavigate, false);
    assert.equal(spriteSrc(dom), "/static/sprite-1-0.gif");
    assert.equal(new URL(savedRequests[0].url).pathname, "/repkin/sprite/");
    assert.deepEqual(savedRequests[0].values, {
        arms_level: "1",
        legs_level: "0",
        csrfmiddlewaretoken: "test-token",
    });
});

// Check that arm and leg changes remain independent and both update the sprite.
test("arm and leg selections update independently", async () => {
    const { dom } = makePage();

    await clickControl(dom, "arms-arrow-btn");
    await clickControl(dom, "legs-arrow-btn");

    assert.equal(spriteSrc(dom), "/static/sprite-1-1.gif");
    assert.equal(dom.window.document.getElementById("arms-arrow-btn").dataset.armLevel, "1");
    assert.equal(dom.window.document.getElementById("legs-arrow-btn").dataset.legLevel, "1");
    assert.equal(dom.window.location.search, "?arms=1&legs=1");
});

// Check that a failed save leaves the displayed sprite unchanged.
test("failed saves keep the current sprite and show an error", async () => {
    const { dom } = makePage();
    dom.window.fetch = async () => ({ ok: false });

    await clickControl(dom, "arms-arrow-btn");

    assert.equal(spriteSrc(dom), "/static/sprite-0-0.gif");
    assert.match(
        dom.window.document.getElementById("sprite-save-status").textContent,
        /could not be saved/
    );
});

// Check that the script safely ignores pages without sprite controls.
test("a page without limb controls does not crash the script", () => {
    const dom = new JSDOM("<p>no locker room here</p>", { url: "http://localhost/" });
    assert.doesNotThrow(() => setupArmToggle(dom.window.document, dom.window));
});

test("green and red no-legs alignment toggles with leg level", async () => {
    for (const color of ["green", "red"]) {
        const { dom } = makePage(0, 0, color);
        const sprite = dom.window.document.getElementById("repkin-sprite");

        assert.equal(sprite.classList.contains("non-green-no-legs"), true);
        await clickControl(dom, "legs-arrow-btn");
        assert.equal(sprite.classList.contains("non-green-no-legs"), false);

        await clickControl(dom, "legs-arrow-btn");
        await clickControl(dom, "legs-arrow-btn");
        await clickControl(dom, "legs-arrow-btn");
        assert.equal(sprite.classList.contains("non-green-no-legs"), true);
    }
});
