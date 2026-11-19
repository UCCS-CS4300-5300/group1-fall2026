const { test } = require("node:test");
const assert = require("node:assert/strict");
const { JSDOM } = require("jsdom");

const { nextArmLevel, setupArmToggle } = require("../static/core/arm_toggle.js");

const GIFS = [
    "/static/base.gif",
    "/static/arms1.gif",
    "/static/arms2.gif",
    "/static/arms3.gif",
];

// A tiny fake locker room with just the parts the script needs.
function makePage(level = 0) {
    const html =
        '<img id="repkin-sprite" src="' + GIFS[level] + '">' +
        '<a id="arms-arrow-btn" href="?arms=' + ((level + 1) % GIFS.length) + '" data-arm-level="' + level + '"></a>' +
        '<script id="arm-gif-urls" type="application/json">' + JSON.stringify(GIFS) + "</script>";
    const dom = new JSDOM(html, { url: "http://localhost/locker-room/?arms=" + level });
    setupArmToggle(dom.window.document, dom.window);
    return dom;
}

// Clicks the arrow. Returns false if the script stopped the page from reloading.
function clickArrow(dom) {
    const link = dom.window.document.getElementById("arms-arrow-btn");
    const click = new dom.window.MouseEvent("click", { bubbles: true, cancelable: true });
    return link.dispatchEvent(click);
}

function spriteSrc(dom) {
    return dom.window.document.getElementById("repkin-sprite").getAttribute("src");
}

test("next arm level moves forward and wraps after the last one", () => {
    assert.equal(nextArmLevel(0, 4), 1);
    assert.equal(nextArmLevel(2, 4), 3);
    assert.equal(nextArmLevel(3, 4), 0);
});

test("clicking the arrow does not reload the page, so the music keeps playing", () => {
    const dom = makePage(0);
    const pageWouldReload = clickArrow(dom);
    assert.equal(pageWouldReload, false);
});

test("clicking the arrow shows the next arm version", () => {
    const dom = makePage(0);
    clickArrow(dom);
    assert.equal(spriteSrc(dom), GIFS[1]);
});

test("clicking through every version comes back to no arms", () => {
    const dom = makePage(0);
    const seen = [];
    for (let i = 0; i < GIFS.length; i++) {
        clickArrow(dom);
        seen.push(spriteSrc(dom));
    }
    assert.deepEqual(seen, [GIFS[1], GIFS[2], GIFS[3], GIFS[0]]);
});

test("it starts from the arm level the page was loaded with", () => {
    const dom = makePage(2);
    clickArrow(dom);
    assert.equal(spriteSrc(dom), GIFS[3]);
});

test("the address bar is updated so a refresh keeps the same arms", () => {
    const dom = makePage(0);
    clickArrow(dom);
    clickArrow(dom);
    assert.equal(dom.window.location.search, "?arms=2");
});

test("the backup link points to the version after the one showing", () => {
    const dom = makePage(0);
    clickArrow(dom);
    const link = dom.window.document.getElementById("arms-arrow-btn");
    assert.equal(link.getAttribute("href"), "?arms=2");
});

test("a page without the arrow does not crash the script", () => {
    const dom = new JSDOM("<p>no locker room here</p>", { url: "http://localhost/" });
    assert.doesNotThrow(() => setupArmToggle(dom.window.document, dom.window));
});
