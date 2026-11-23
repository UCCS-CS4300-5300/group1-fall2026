(function () {
    // Advance to the next limb level and wrap at the end.
    function nextLimbLevel(level, count) {
        return (level + 1) % count;
    }

    // How many levels can be chosen. Missing or bad values mean all 4.
    function readLevelCount(value) {
        const maxLevel = parseInt(value, 10);
        if (Number.isNaN(maxLevel) || maxLevel < 0) {
            return 4;
        }
        return Math.min(maxLevel, 3) + 1;
    }

    // Connect the arm and leg controls to saved sprite updates.
    function setupArmToggle(doc, win) {
        const armsLink = doc.getElementById("arms-arrow-btn");
        const legsLink = doc.getElementById("legs-arrow-btn");
        const sprite = doc.getElementById("repkin-sprite");
        const urlData = doc.getElementById("sprite-gif-urls");
        const saveForm = doc.getElementById("sprite-save-form");
        const status = doc.getElementById("sprite-save-status");
        if (!armsLink || !legsLink || !sprite || !urlData || !saveForm || !status) {
            return;
        }

        const spriteUrls = JSON.parse(urlData.textContent);
        const tokenInput = saveForm.querySelector('input[name="csrfmiddlewaretoken"]');
        const armsCount = readLevelCount(armsLink.dataset.maxArmLevel);
        const legsCount = readLevelCount(legsLink.dataset.maxLegLevel);
        let armsLevel = parseInt(armsLink.dataset.armLevel, 10) || 0;
        let legsLevel = parseInt(legsLink.dataset.legLevel, 10) || 0;
        let saving = false;

        // Align taller base canvases and no-leg sprite variants.
        function updateSpriteAlignment() {
            const color = sprite.dataset.color || sprite.dataset.repkinColor;
            const needsOffset = color === "yellow"
                || (["blue", "green", "purple", "red"].includes(color) && legsLevel === 0);
            sprite.classList.toggle("non-green-no-legs", needsOffset);

            // Set the transform directly so it cannot remain stale after a limb change.
            if (needsOffset) {
                sprite.style.transform = "translate(-50%, -50%) translateY(29%)";
            } else {
                sprite.style.removeProperty("transform");
            }
        }

        // Keep the non-JavaScript links pointed at the next levels.
        function updateControlLinks() {
            armsLink.setAttribute("href", "?arms=" + nextLimbLevel(armsLevel, armsCount));
            legsLink.setAttribute("href", "?legs=" + nextLimbLevel(legsLevel, legsCount));
        }

        // Read the server's error message, if it sent one.
        async function errorMessage(response) {
            try {
                const data = await response.json();
                return data.error;
            } catch (error) {
                return "";
            }
        }

        // Save both levels together and update the displayed sprite on success.
        async function saveLevels(nextArmsLevel, nextLegsLevel) {
            if (saving) {
                return;
            }
            saving = true;
            armsLink.setAttribute("aria-disabled", "true");
            legsLink.setAttribute("aria-disabled", "true");
            status.textContent = "";

            const body = new URLSearchParams({
                arms_level: String(nextArmsLevel),
                legs_level: String(nextLegsLevel),
                csrfmiddlewaretoken: tokenInput ? tokenInput.value : "",
            });

            try {
                const response = await win.fetch(saveForm.action, {
                    method: "POST",
                    body: body,
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    const message = await errorMessage(response);
                    throw new Error(message || "The sprite selection could not be saved.");
                }

                const saved = await response.json();
                armsLevel = saved.arms_level;
                legsLevel = saved.legs_level;
                sprite.src = spriteUrls[String(armsLevel)][String(legsLevel)];
                armsLink.dataset.armLevel = String(armsLevel);
                legsLink.dataset.legLevel = String(legsLevel);
                updateSpriteAlignment();
                updateControlLinks();
                win.history.replaceState(
                    null,
                    "",
                    "?arms=" + armsLevel + "&legs=" + legsLevel
                );
            } catch (error) {
                status.textContent = error.message || "The sprite selection could not be saved.";
            } finally {
                saving = false;
                armsLink.removeAttribute("aria-disabled");
                legsLink.removeAttribute("aria-disabled");
            }
        }

        // Save the next unlocked arm level while keeping the current leg level.
        armsLink.addEventListener("click", function (event) {
            event.preventDefault();
            if (armsCount <= 1) {
                status.textContent = armsLink.dataset.lockedMessage || "Arms are still locked.";
                return;
            }
            saveLevels(nextLimbLevel(armsLevel, armsCount), legsLevel);
        });

        // Save the next unlocked leg level while keeping the current arm level.
        legsLink.addEventListener("click", function (event) {
            event.preventDefault();
            if (legsCount <= 1) {
                status.textContent = legsLink.dataset.lockedMessage || "Legs are still locked.";
                return;
            }
            saveLevels(armsLevel, nextLimbLevel(legsLevel, legsCount));
        });

        updateControlLinks();
        updateSpriteAlignment();
    }

    if (typeof module !== "undefined" && module.exports) {
        module.exports = { nextLimbLevel, readLevelCount, setupArmToggle };
    } else {
        // Running in the browser.
        document.addEventListener("DOMContentLoaded", function () {
            setupArmToggle(document, window);
        });
    }
})();
