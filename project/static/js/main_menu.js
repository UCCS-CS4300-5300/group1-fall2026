(function () {
    const menu = document.getElementById("mainMenu");
    const menuButton = document.getElementById("mainMenuButton");
    const creditsOverlay = document.getElementById("creditsOverlay");
    if (!menu || !menuButton) return;

    function closeMenu() {
        menu.classList.add("hidden");
        creditsOverlay.classList.add("hidden");
        menuButton.setAttribute("aria-expanded", "false");
    }

    menuButton.addEventListener("click", () => {
        const isOpen = menu.classList.toggle("hidden") === false;
        menuButton.setAttribute("aria-expanded", String(isOpen));
        if (!isOpen) creditsOverlay.classList.add("hidden");
    });

    menu.addEventListener("click", (e) => { if (e.target === menu) closeMenu(); });
    document.getElementById("menuExitButton").addEventListener("click", closeMenu);

    // Escape closes credits first, then the menu
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        if (!creditsOverlay.classList.contains("hidden")) creditsOverlay.classList.add("hidden");
        else closeMenu();
    });

    // credits
    document.getElementById("creditsButton").addEventListener("click", () => creditsOverlay.classList.remove("hidden"));
    creditsOverlay.addEventListener("click", (e) => { e.stopPropagation(); creditsOverlay.classList.add("hidden"); });

    // music and units, remembered across pages
    const art = document.getElementById("menuArt");
    const music = document.getElementById("bg-music");
    const musicBtn = document.getElementById("musicBtn");
    const impBtn = document.getElementById("impBtn");
    const siBtn = document.getElementById("siBtn");
    const load = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } };
    const save = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };

    let musicOn = load("repkinz.music", "on") === "on";
    let unit = load("repkinz.unit", "imp");
    if (unit === "lbs") unit = "imp";   // values saved by the old version
    if (unit === "kgs") unit = "si";

    function render() {
        art.src = art.dataset[unit + (musicOn ? "On" : "Off")];
        musicBtn.setAttribute("aria-pressed", String(musicOn));
        impBtn.setAttribute("aria-pressed", String(unit === "imp"));
        siBtn.setAttribute("aria-pressed", String(unit === "si"));
        if (music) { musicOn ? music.play().catch(() => {}) : music.pause(); }
    }

    musicBtn.addEventListener("click", () => { musicOn = !musicOn; save("repkinz.music", musicOn ? "on" : "off"); render(); });
    impBtn.addEventListener("click", () => { unit = "imp"; save("repkinz.unit", unit); render(); });
    siBtn.addEventListener("click", () => { unit = "si"; save("repkinz.unit", unit); render(); });

    // browsers block autoplay with sound, so start on the first click if music is on
    document.addEventListener("pointerdown", () => {
        if (musicOn && music && music.paused) music.play().catch(() => {});
    }, { once: true });

    render();

    //Forms that save information through the server and update the display boxes
    document.querySelectorAll(".menu_form[data-key]").forEach((form) => {
    form.addEventListener("submit", async (e) => {
        e.preventDefault();                       // stop the page reload
        const box = document.getElementById(form.dataset.display);
        const old = box.value;
        try {
            const res = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),         // includes the csrf token
                credentials: "same-origin",
            });
            const data = await res.json();
            if (res.ok) {
                box.value = data[form.dataset.key];   // show the saved value
                form.reset();                         // clear the typing box
            } else {
                box.value = data.error || "Could not save.";
                setTimeout(() => { box.value = old; }, 2000);
            }
        } catch (err) {
            box.value = "Network error.";
            setTimeout(() => { box.value = old; }, 2000);
        }
        });
    });
})();