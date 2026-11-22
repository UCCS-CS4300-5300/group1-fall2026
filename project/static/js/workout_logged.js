/*
 * Home page: tells RepKin's speech bubble about a workout that was just logged.
 *
 * The workout page can't talk to the bubble (it isn't on that page), so after a
 * successful log it leaves a note in sessionStorage and goes home. This script reads
 * the note once, deletes it, and fires the "exercise:logged" event the bubble
 * (core/repkin_bubble.js) listens for.
 *
 * TIMING MATTERS: the bubble script is loaded with `defer`, so it only starts
 * listening once the page has been parsed. Firing straight away would be missed, so
 * we wait for DOMContentLoaded, which comes after deferred scripts have run.
 */
(function () {
    "use strict";

    // The same key workout_builder.js writes.
    const KEY = "repkinz.pendingWorkoutLog";
    const MAX_LOG_IDS = 20;               // the most one workout can contain (4 x 5)
    const MAX_AGE_MS = 5 * 60 * 1000;     // an old note is ignored, not announced late

    // Returns the list of log ids waiting for us, or null. Always clears the note,
    // so a refresh can't announce the same workout twice.
    function takePendingLogIds(storage, now) {
        let raw = null;
        try {
            raw = storage.getItem(KEY);
            storage.removeItem(KEY);
        } catch (e) {
            return null;
        }
        if (!raw) {
            return null;
        }

        let note;
        try {
            note = JSON.parse(raw);
        } catch (e) {
            return null;
        }
        if (!note || typeof note !== "object") {
            return null;
        }

        const ids = note.logIds;
        const wholeNumbers = Array.isArray(ids) && ids.every(
            (id) => Number.isSafeInteger(id) && id > 0
        );
        if (!wholeNumbers || ids.length < 1 || ids.length > MAX_LOG_IDS) {
            return null;
        }
        const age = now - note.at;
        if (!Number.isFinite(age) || age < 0 || age > MAX_AGE_MS) {
            return null;
        }
        return ids;
    }

    function announce(win, now) {
        let storage = null;
        try {
            storage = win.sessionStorage;
        } catch (e) {
            return false;
        }
        if (!storage) {
            return false;
        }
        const ids = takePendingLogIds(storage, now);
        if (!ids) {
            return false;
        }
        win.document.dispatchEvent(
            new win.CustomEvent("exercise:logged", { detail: { logIds: ids } })
        );
        return true;
    }

    function start(win, now) {
        if (win.document.readyState === "loading") {
            win.document.addEventListener("DOMContentLoaded", () => announce(win, now()));
        } else {
            announce(win, now());
        }
    }

    window.WorkoutLogged = { KEY: KEY, takePendingLogIds: takePendingLogIds, announce: announce, start: start };
    // Tests set this flag so they can drive the script themselves.
    if (!window.__workoutLoggedManualStart) {
        start(window, () => Date.now());
    }
})();
