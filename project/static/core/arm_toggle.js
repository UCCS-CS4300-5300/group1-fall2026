
(function () {
    function nextArmLevel(level, count) {
        return (level + 1) % count;
    }

    function setupArmToggle(doc, win) {
        const link = doc.getElementById("arms-arrow-btn");
        const sprite = doc.getElementById("repkin-sprite");
        const urlData = doc.getElementById("arm-gif-urls");
        if (!link || !sprite || !urlData) {
            return;
        }

        const gifs = JSON.parse(urlData.textContent);
        if (gifs.length === 0) {
            return;
        }

        let level = parseInt(link.dataset.armLevel, 10) || 0;

        link.addEventListener("click", function (event) {
            // Stop the page from reloading, which is what restarted the music.
            event.preventDefault();

            level = nextArmLevel(level, gifs.length);
            sprite.src = gifs[level];
            link.dataset.armLevel = String(level);
            link.setAttribute("href", "?arms=" + nextArmLevel(level, gifs.length));

            // Keep the address bar in sync, so a refresh shows the same arms.
            win.history.replaceState(null, "", "?arms=" + level);
        });
    }

    if (typeof module !== "undefined" && module.exports) {
        // Running in the Node tests.
        module.exports = { nextArmLevel, setupArmToggle };
    } else {
        // Running in the browser.
        document.addEventListener("DOMContentLoaded", function () {
            setupArmToggle(document, window);
        });
    }
})();
