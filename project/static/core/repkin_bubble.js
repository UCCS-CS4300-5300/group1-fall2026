/* RepKin's speech bubble.
 *
 * What it does (each page chooses which of these it wants, using the
 * data-messages attribute on the bubble; see _repkin_bubble.html):
 *   - asks the server for ONE greeting once the home page is clear of dialogs
 *     (the server only hands one out per login),
 *   - shows a compliment after an exercise is logged (it listens for the
 *     "exercise:logged" event),
 *   - shows an idle message now and then if nothing has happened for a while.
 *
 * The server decides what RepKin says. This file only decides WHEN to ask and
 * how to show it. Message text is only ever inserted with textContent, never
 * as HTML.
 */
(function () {
    "use strict";

    const root = document.getElementById("repkin-bubble");
    if (!root) {
        return;
    }

    const textElement = root.querySelector(".repkin-bubble__text");
    const closeButton = root.querySelector(".repkin-bubble__close");
    const messageUrl = root.dataset.messageUrl;
    const csrfToken = root.dataset.csrfToken;
    const mainMenu = document.getElementById("mainMenu");

    // Which messages this page may ask for. The workout room allows all three;
    // the locker room only allows "idle", so it never uses up the login's
    // greeting or reacts to workouts.
    const allowedKinds = (root.dataset.messages || "greeting,workout,idle")
        .split(",")
        .map(function (name) { return name.trim(); });

    function allows(kind) {
        return allowedKinds.includes(kind);
    }

    // ---- Timings, in milliseconds. Change these to tune how chatty RepKin is.
    // Keep IDLE_REPEAT_MS at or above the server's idle cooldown
    // (COOLDOWN_SECONDS["idle"] in views_message.py), or the server will refuse.
    const IDLE_DELAY_MS = 15 * 1000;    // quiet time before the first idle message
    const IDLE_REPEAT_MS = 20 * 1000;   // gap between idle messages while still quiet
    const IDLE_RECHECK_MS = 10 * 1000;  // if it's a bad moment, look again after this
    const AUTO_HIDE_MS = 12 * 1000;     // how long a message stays up
    const BLOCKED_CHECK_MS = 500;       // how often we check whether a modal closed

    let requestsInFlight = 0;
    let queuedMessage = null;
    let loggedOut = false;
    let hideTimer = null;
    let blockedTimer = null;
    let idleTimer = null;

    // ---- Showing messages -------------------------------------------------

    function isModalOpen() {
        const menuOpen = mainMenu !== null && !mainMenu.classList.contains("hidden");
        return menuOpen || document.querySelector("dialog[open]") !== null;
    }

    function startHideTimer() {
        clearTimeout(hideTimer);
        hideTimer = setTimeout(dismiss, AUTO_HIDE_MS);
    }

    function dismiss() {
        clearTimeout(hideTimer);
        root.hidden = true;
        textElement.textContent = "";
    }

    function display(text) {
        textElement.textContent = text;
        root.hidden = false;
        startHideTimer();
    }

    // A message that arrives while a modal is open waits until it closes, so
    // the bubble is never hidden behind a dialog. Only the newest one waits.
    function flushQueue() {
        clearTimeout(blockedTimer);
        if (queuedMessage === null) {
            return;
        }
        if (isModalOpen()) {
            blockedTimer = setTimeout(flushQueue, BLOCKED_CHECK_MS);
            return;
        }
        const text = queuedMessage;
        queuedMessage = null;
        display(text);
    }

    function show(text) {
        queuedMessage = text;
        flushQueue();
    }

    // ---- Asking the server -------------------------------------------------

    async function ask(kind, logIds) {
        if (loggedOut || !allows(kind)) {
            return;
        }
        const body = new URLSearchParams();
        body.append("kind", kind);
        body.append("csrfmiddlewaretoken", csrfToken);
        (logIds || []).forEach(function (id) {
            body.append("log_ids", String(id));
        });

        requestsInFlight += 1;
        try {
            const response = await fetch(messageUrl, {
                method: "POST",
                body: body,
                credentials: "same-origin",
            });
            if (response.redirected) {
                // The session ended and we were sent to the login page.
                loggedOut = true;
                clearTimeout(idleTimer);
                return;
            }
            const contentType = response.headers.get("Content-Type") || "";
            if (!response.ok || !contentType.includes("application/json")) {
                return; // too soon, a server error, etc.: stay quiet
            }
            const data = await response.json();
            if (data && typeof data.message === "string" && data.message) {
                show(data.message);
            }
        } catch (error) {
            // Network trouble: stay quiet. RepKin is a bonus, not a requirement.
        } finally {
            requestsInFlight -= 1;
        }
    }

    // ---- The greeting ------------------------------------------------------
    // The server uses up a login's one greeting the moment it is ASKED for. So
    // we only ask once nothing is in the way: no dialog or menu open, and the
    // tab visible. If we asked while the welcome or setup dialog was open, the
    // answer would sit in memory behind it, and saving the setup form reloads
    // the page, which throws the waiting message away. The greeting would be
    // used up and never seen. (Asking later costs nothing: the page that finally
    // asks is the one that shows it.)
    let greetingTimer = null;

    function askForGreetingWhenFree() {
        clearTimeout(greetingTimer);
        if (loggedOut) {
            return;
        }
        if (isModalOpen() || document.visibilityState !== "visible") {
            greetingTimer = setTimeout(askForGreetingWhenFree, BLOCKED_CHECK_MS);
            return;
        }
        ask("greeting");
    }

    // ---- Idle messages -----------------------------------------------------

    function scheduleIdle(delay) {
        clearTimeout(idleTimer);
        idleTimer = setTimeout(onIdle, delay);
    }

    function onIdle() {
        if (loggedOut || !allows("idle")) {
            return;
        }
        const goodMoment =
            document.visibilityState === "visible" &&
            !isModalOpen() &&
            root.hidden &&
            queuedMessage === null &&
            requestsInFlight === 0;
        if (!goodMoment) {
            scheduleIdle(IDLE_RECHECK_MS);
            return;
        }
        ask("idle");
        scheduleIdle(IDLE_REPEAT_MS);
    }

    // Any tap, click, or key press means the user is not idle: start counting again.
    function noteActivity() {
        if (!loggedOut && allows("idle")) {
            scheduleIdle(IDLE_DELAY_MS);
        }
    }

    ["pointerdown", "keydown", "touchstart"].forEach(function (name) {
        document.addEventListener(name, noteActivity, { passive: true });
    });

    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
            noteActivity();
        } else {
            clearTimeout(idleTimer);
        }
    });

    // ---- Wiring ------------------------------------------------------------

    closeButton.addEventListener("click", dismiss);

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !root.hidden && !isModalOpen()) {
            dismiss();
        }
    });

    // Don't whisk the message away while someone is reading or pointing at it.
    root.addEventListener("mouseenter", function () {
        clearTimeout(hideTimer);
    });
    root.addEventListener("mouseleave", function () {
        if (!root.hidden) {
            startHideTimer();
        }
    });

    // The exercise form announces new logs with this event:
    //   document.dispatchEvent(new CustomEvent("exercise:logged",
    //       { detail: { logIds: [12] } }));
    if (allows("workout")) {
        document.addEventListener("exercise:logged", function (event) {
            const logIds = (event.detail && event.detail.logIds) || [];
            ask("workout", logIds);
        });
    }

    window.RepkinBubble = { ask: ask, show: show, dismiss: dismiss };

    if (allows("greeting")) {
        askForGreetingWhenFree();
    }
    noteActivity();
})();
