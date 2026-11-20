(function () {
    // Advance to the next limb level and wrap at the end.
    function nextLimbLevel(level, count) {
        return (level + 1) % count;
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
        let armsLevel = parseInt(armsLink.dataset.armLevel, 10) || 0;
        let legsLevel = parseInt(legsLink.dataset.legLevel, 10) || 0;
        let saving = false;

        // Apply the taller-canvas offset only to no-leg green/red sprites.
        function updateSpriteAlignment() {
            const color = sprite.dataset.color || sprite.dataset.repkinColor;
            const needsOffset = ["blue", "yellow"].includes(color)
                || (["green", "purple", "red"].includes(color) && legsLevel === 0);
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
            armsLink.setAttribute("href", "?arms=" + nextLimbLevel(armsLevel, 4));
            legsLink.setAttribute("href", "?legs=" + nextLimbLevel(legsLevel, 4));
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
                    throw new Error("The sprite selection could not be saved.");
                }

                const saved = await response.json();
                armsLevel = saved.arms_level;
                legsLevel = saved.legs_level;
                sprite.src = spriteUrls[String(armsLevel)][String(legsLevel)];
                const alwaysOffsetColors = new Set(["blue", "yellow"]);
                const needsOffset =
                    alwaysOffsetColors.has(sprite.dataset.color) ||
                    (["green", "purple", "red"].includes(sprite.dataset.color) &&
                        legsLevel === 0);
                sprite.classList.toggle("non-green-no-legs", needsOffset);
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

        // Save the next arm level while preserving the current leg level.
        armsLink.addEventListener("click", function (event) {
            event.preventDefault();
            saveLevels(nextLimbLevel(armsLevel, 4), legsLevel);
        });

        // Save the next leg level while preserving the current arm level.
        legsLink.addEventListener("click", function (event) {
            event.preventDefault();
            saveLevels(armsLevel, nextLimbLevel(legsLevel, 4));
        });

        updateControlLinks();
        updateSpriteAlignment();
    }

    if (typeof module !== "undefined" && module.exports) {
        module.exports = { nextLimbLevel, setupArmToggle };
    } else {
        // Running in the browser.
        document.addEventListener("DOMContentLoaded", function () {
            setupArmToggle(document, window);
        });
    }
})();
