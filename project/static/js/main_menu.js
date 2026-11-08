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

    // settings forms aren't wired to the server yet
    document.querySelectorAll(".menu_form").forEach((f) => f.addEventListener("submit", (e) => e.preventDefault()));

    // music and units, remembered across pages
    const art = document.getElementById("menuArt");
    const music = document.getElementById("bg-music");
    const musicBtn = document.getElementById("musicBtn");
    const lbsBtn = document.getElementById("lbsBtn");
    const kgsBtn = document.getElementById("kgsBtn");
    const load = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } };
    const save = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };

    let musicOn = load("repkinz.music", "on") === "on";
    let unit = load("repkinz.unit", "lbs");

    function render() {
        art.src = art.dataset[unit + (musicOn ? "On" : "Off")];
        musicBtn.setAttribute("aria-pressed", String(musicOn));
        lbsBtn.setAttribute("aria-pressed", String(unit === "lbs"));
        kgsBtn.setAttribute("aria-pressed", String(unit === "kgs"));
        if (music) { musicOn ? music.play().catch(() => {}) : music.pause(); }
    }

    musicBtn.addEventListener("click", () => { musicOn = !musicOn; save("repkinz.music", musicOn ? "on" : "off"); render(); });
    lbsBtn.addEventListener("click", () => { unit = "lbs"; save("repkinz.unit", unit); render(); });
    kgsBtn.addEventListener("click", () => { unit = "kgs"; save("repkinz.unit", unit); render(); });

    // browsers block autoplay with sound, so start on the first click if music is on
    document.addEventListener("pointerdown", () => {
        if (musicOn && music && music.paused) music.play().catch(() => {});
    }, { once: true });

    render();
})();