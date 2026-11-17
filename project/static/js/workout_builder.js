/*
 * Workout logging page: build a workout, save it as a preset, load or delete one.
 *
 * The server decides what is valid (see core/workout_presets.py). This file keeps
 * the workout being built in memory, does a quick sanity check so people get
 * instant feedback, and shows whatever the server says. Text from the server or
 * the user is only ever inserted with textContent, never as HTML.
 *
 * Everything outside the page (fetch, confirm, navigation, storage) is passed in,
 * so tests can replace it. The page itself just calls start().
 */
(function () {
    "use strict";

    // The same limits the server enforces (core/forms_workout.py).
    const MAX_SETS = 100;
    const MAX_REPS = 1000;
    const MAX_DURATION_SECONDS = 24 * 60 * 60;

    // After logging, the home page is told which logs were just made so RepKin can
    // comment on them (see static/js/workout_logged.js, which reads this same key).
    const HANDOFF_KEY = "repkinz.pendingWorkoutLog";

    // Mirrors core/units.py. The main menu saves "lbs" or "kgs" under this key.
    const UNIT_KEY = "repkinz.unit";
    const UNIT_LABELS = {
        imperial: { weight: "lb", distance: "mi" },
        si: { weight: "kg", distance: "km" },
    };

    function create(env) {
        const doc = env.document;
        const $ = (id) => doc.getElementById(id);
        const app = $("workout-app");
        if (!app) {
            return null;
        }
        const config = {
            homeUrl: app.dataset.homeUrl,
            catalogUrl: app.dataset.catalogUrl,
            presetsUrl: app.dataset.presetsUrl,
            saveUrl: app.dataset.saveUrl,
            detailUrl: app.dataset.detailUrl,
            deleteUrl: app.dataset.deleteUrl,
            logUrl: app.dataset.logUrl,
            csrf: app.dataset.csrfToken,
        };

        const el = {
            create: $("wl-create"), load: $("wl-load"), status: $("wl-status"),
            errors: $("wl-errors"), errorsHeading: $("wl-errors-heading"), errorsList: $("wl-errors-list"),
            presets: $("wl-presets"), presetsEmpty: $("wl-presets-empty"), presetList: $("wl-preset-list"),
            builder: $("wl-builder"), name: $("wl-name"), units: $("wl-units"), sections: $("wl-sections"),
            save: $("wl-save"), log: $("wl-log"), intro: $("wl-intro"),
            picker: $("wl-picker"), pickerForm: $("wl-picker-form"), pickerTitle: $("wl-picker-title"),
            pickerSelect: $("wl-picker-exercise"), pickerError: $("wl-picker-error"),
            pickerCancel: $("wl-picker-cancel"), pickerRemove: $("wl-picker-remove"),
            fieldReps: $("wl-field-reps"), fieldWeight: $("wl-field-weight"),
            fieldDuration: $("wl-field-duration"), fieldDistance: $("wl-field-distance"),
            sets: $("wl-sets"), reps: $("wl-reps"), weight: $("wl-weight"),
            minutes: $("wl-minutes"), seconds: $("wl-seconds"), distance: $("wl-distance"),
            weightLabel: $("wl-weight-label"), distanceLabel: $("wl-distance-label"),
        };

        const state = {
            catalog: null,        // { sections: [...], limits: {...} } from the server
            id: null,             // the preset being edited, or null for a new one
            unitSystem: "imperial",
            items: {},            // { section_key: [ {exercise_type, sets, reps, ...} ] }
            dirty: false,         // unsaved changes?
            picking: null,        // { section, index } while the picker is open
        };

        // ---- Small helpers -----------------------------------------------------
        function currentUnitSystem() {
            let choice = null;
            try {
                choice = env.storage && env.storage.getItem(UNIT_KEY);
            } catch (e) {
                choice = null;
            }
            return choice === "kgs" ? "si" : "imperial";
        }

        function sectionList() {
            return state.catalog ? state.catalog.sections : [];
        }

        function sectionTitle(key) {
            const found = sectionList().find((section) => section.key === key);
            return found ? found.title : key;
        }

        function exerciseInfo(key) {
            for (const section of sectionList()) {
                const found = section.exercises.find((exercise) => exercise.key === key);
                if (found) {
                    return found;
                }
            }
            return null;
        }

        function setHidden(node, hidden) {
            node.hidden = hidden;
        }

        function clean(number) {
            // 135 -> "135", 2.50 -> "2.5"
            return String(Number(number));
        }

        function labelFor(item) {
            const info = exerciseInfo(item.exercise_type);
            return info ? info.label : item.exercise_type;
        }

        function describe(item) {
            const info = exerciseInfo(item.exercise_type);
            const units = UNIT_LABELS[state.unitSystem];
            const type = info ? info.input_type : null;
            if (type === "reps") {
                let text = `${item.sets} \u00d7 ${item.reps}`;
                if (item.weight != null) {
                    text += ` @ ${clean(item.weight)} ${units.weight}`;
                }
                return text;
            }
            if (type === "duration") {
                const minutes = Math.floor(item.duration_seconds / 60);
                const seconds = item.duration_seconds % 60;
                const parts = [];
                if (minutes) { parts.push(`${minutes} min`); }
                if (seconds || !minutes) { parts.push(`${seconds} sec`); }
                return parts.join(" ");
            }
            if (type === "distance") {
                return `${clean(item.distance)} ${units.distance}`;
            }
            return "";
        }

        // ---- Messages ----------------------------------------------------------
        function clearMessages() {
            setHidden(el.status, true);
            el.status.textContent = "";
            setHidden(el.errors, true);
            el.errorsHeading.textContent = "";
            el.errorsList.textContent = "";
        }

        function showStatus(text) {
            clearMessages();
            el.status.textContent = text;
            setHidden(el.status, false);
        }

        function showErrors(heading, lines) {
            clearMessages();
            el.errorsHeading.textContent = heading;
            (lines || []).forEach((line) => {
                const li = doc.createElement("li");
                li.textContent = line;
                el.errorsList.appendChild(li);
            });
            setHidden(el.errors, false);
        }

        function serverErrorLines(errors) {
            return (errors || []).map((problem) => {
                if (problem.where === "item") {
                    return `${sectionTitle(problem.section)}, exercise ${problem.index + 1}: ${problem.message}`;
                }
                if (problem.where === "section" && problem.section) {
                    return `${sectionTitle(problem.section)}: ${problem.message}`;
                }
                if (problem.where === "name") {
                    return `Name: ${problem.message}`;
                }
                return problem.message;
            });
        }

        // ---- Talking to the server -----------------------------------------------
        async function request(url, options) {
            const response = await env.fetch(url, Object.assign({ credentials: "same-origin" }, options));
            let data = {};
            try {
                data = await response.json();
            } catch (e) {
                data = {};
            }
            return { ok: response.ok, status: response.status, data: data };
        }

        function post(url, body) {
            return request(url, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": config.csrf },
                body: body === undefined ? undefined : JSON.stringify(body),
            });
        }

        function urlFor(template, id) {
            return template.replace(/\/0\//, `/${id}/`);
        }

        async function ensureCatalog() {
            if (state.catalog) {
                return true;
            }
            try {
                const result = await request(config.catalogUrl);
                if (result.ok && result.data.sections) {
                    state.catalog = result.data;
                    return true;
                }
            } catch (e) {
                // fall through to the message below
            }
            showErrors("The exercise list couldn't be loaded. Please try again.");
            return false;
        }

        // ---- Rendering the builder -------------------------------------------------
        function emptyItems() {
            const items = {};
            sectionList().forEach((section) => { items[section.key] = []; });
            return items;
        }

        function totalItems() {
            return Object.values(state.items).reduce((sum, list) => sum + list.length, 0);
        }

        function renderBuilder() {
            const units = UNIT_LABELS[state.unitSystem];
            el.units.textContent =
                `Weights are in ${units.weight} and distances in ${units.distance}. ` +
                "You can change this in the main menu.";
            el.sections.textContent = "";

            sectionList().forEach((section) => {
                const wrapper = doc.createElement("section");
                wrapper.className = "wl-section";
                wrapper.dataset.section = section.key;

                const heading = doc.createElement("h2");
                heading.className = "wl-section__title";
                heading.textContent = section.title;
                wrapper.appendChild(heading);

                const list = doc.createElement("ol");
                list.className = "wl-items";
                (state.items[section.key] || []).forEach((item, index) => {
                    const row = doc.createElement("li");
                    const button = doc.createElement("button");
                    button.type = "button";
                    button.className = "wl-item";
                    button.dataset.index = String(index);
                    button.setAttribute("aria-label", `Edit ${labelFor(item)}: ${describe(item)}`);

                    const label = doc.createElement("span");
                    label.className = "wl-item__label";
                    label.textContent = labelFor(item);
                    const detail = doc.createElement("span");
                    detail.className = "wl-item__detail";
                    detail.textContent = describe(item);
                    button.appendChild(label);
                    button.appendChild(detail);

                    button.addEventListener("click", () => openPicker(section.key, index));
                    row.appendChild(button);
                    list.appendChild(row);
                });
                wrapper.appendChild(list);

                if ((state.items[section.key] || []).length < section.max_items) {
                    const add = doc.createElement("button");
                    add.type = "button";
                    add.className = "wl-add";
                    add.textContent = "+";
                    add.setAttribute("aria-label", `Add an exercise to ${section.title}`);
                    add.addEventListener("click", () => openPicker(section.key, null));
                    wrapper.appendChild(add);
                } else {
                    const full = doc.createElement("p");
                    full.className = "wl-section__full";
                    full.textContent = `This section is full (${section.max_items} exercises).`;
                    wrapper.appendChild(full);
                }
                el.sections.appendChild(wrapper);
            });
        }

        function showBuilder() {
            setHidden(el.builder, false);
            setHidden(el.intro, true);
            renderBuilder();
        }

        function startNewWorkout() {
            state.id = null;
            state.unitSystem = currentUnitSystem();
            state.items = emptyItems();
            state.dirty = false;
            el.name.value = "";
            showBuilder();
        }

        function confirmDiscard() {
            return !state.dirty || env.confirm("You have unsaved changes. Discard them?");
        }

        async function onCreate() {
            clearMessages();
            if (!(await ensureCatalog())) {
                return;
            }
            if (!confirmDiscard()) {
                return;
            }
            setHidden(el.presets, true);
            el.load.setAttribute("aria-expanded", "false");
            startNewWorkout();
            el.name.focus();
        }

        // ---- The exercise picker -----------------------------------------------------
        function openDialog(dialog) {
            if (typeof dialog.showModal === "function") {
                dialog.showModal();
            } else {
                dialog.setAttribute("open", "");
            }
        }

        function closeDialog(dialog) {
            if (typeof dialog.close === "function") {
                dialog.close();
            } else {
                dialog.removeAttribute("open");
            }
        }

        function fillPickerOptions(sectionKey) {
            const section = sectionList().find((candidate) => candidate.key === sectionKey);
            el.pickerSelect.textContent = "";
            const placeholder = doc.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "Choose an exercise...";
            el.pickerSelect.appendChild(placeholder);

            let group = null;
            let groupName = null;
            section.exercises.forEach((exercise) => {
                if (exercise.group !== groupName) {
                    groupName = exercise.group;
                    group = doc.createElement("optgroup");
                    group.label = groupName;
                    el.pickerSelect.appendChild(group);
                }
                const option = doc.createElement("option");
                option.value = exercise.key;
                option.textContent = exercise.label;
                group.appendChild(option);
            });
        }

        function showFieldsFor(exerciseKey) {
            const info = exerciseInfo(exerciseKey);
            const type = info ? info.input_type : null;
            const units = UNIT_LABELS[state.unitSystem];
            setHidden(el.fieldReps, type !== "reps");
            setHidden(el.fieldWeight, !(type === "reps" && info.weighted));
            setHidden(el.fieldDuration, type !== "duration");
            setHidden(el.fieldDistance, type !== "distance");
            el.weightLabel.textContent = `Weight (${units.weight}), optional`;
            el.distanceLabel.textContent = `Distance (${units.distance})`;
            setHidden(el.pickerError, true);
        }

        function fillPickerValues(item) {
            const value = (number) => (number == null ? "" : String(number));
            el.sets.value = item ? value(item.sets) : "";
            el.reps.value = item ? value(item.reps) : "";
            el.weight.value = item ? value(item.weight) : "";
            el.distance.value = item ? value(item.distance) : "";
            if (item && item.duration_seconds != null) {
                el.minutes.value = String(Math.floor(item.duration_seconds / 60));
                el.seconds.value = String(item.duration_seconds % 60);
            } else {
                el.minutes.value = "";
                el.seconds.value = "";
            }
        }

        function openPicker(sectionKey, index) {
            const editing = index !== null;
            const item = editing ? state.items[sectionKey][index] : null;
            state.picking = { section: sectionKey, index: index };

            el.pickerTitle.textContent = editing
                ? `Edit exercise: ${sectionTitle(sectionKey)}`
                : `Add to: ${sectionTitle(sectionKey)}`;
            fillPickerOptions(sectionKey);
            el.pickerSelect.value = item ? item.exercise_type : "";
            fillPickerValues(item);
            showFieldsFor(el.pickerSelect.value);
            setHidden(el.pickerRemove, !editing);
            openDialog(el.picker);
        }

        function closePicker() {
            state.picking = null;
            closeDialog(el.picker);
        }

        function wholeNumber(raw) {
            const text = String(raw).trim();
            return /^\d+$/.test(text) ? Number(text) : NaN;
        }

        function positiveNumber(raw) {
            const text = String(raw).trim();
            const number = Number(text);
            return text !== "" && Number.isFinite(number) && number > 0 ? number : NaN;
        }

        // A number box holding something it can't read (like "1e" or "12.3.4") reports
        // an EMPTY value, so without this check we'd treat it as "left blank".
        function hasUnreadableNumber(inputs) {
            return inputs.some((input) => input.validity && input.validity.badInput);
        }

        // Reads the picker's boxes. Returns { item } or { error }.
        function readPicker() {
            const key = el.pickerSelect.value;
            const info = exerciseInfo(key);
            if (!info) {
                return { error: "Choose an exercise first." };
            }
            const visibleBoxes = {
                reps: [el.sets, el.reps, el.weight],
                duration: [el.minutes, el.seconds],
                distance: [el.distance],
            }[info.input_type] || [];
            if (hasUnreadableNumber(visibleBoxes)) {
                return { error: "Please enter plain numbers, like 12 or 2.5." };
            }
            const item = { exercise_type: key };

            if (info.input_type === "reps") {
                const sets = wholeNumber(el.sets.value);
                const reps = wholeNumber(el.reps.value);
                if (!(sets >= 1 && sets <= MAX_SETS)) {
                    return { error: `Sets must be a whole number from 1 to ${MAX_SETS}.` };
                }
                if (!(reps >= 1 && reps <= MAX_REPS)) {
                    return { error: `Reps must be a whole number from 1 to ${MAX_REPS}.` };
                }
                item.sets = sets;
                item.reps = reps;
                if (info.weighted && el.weight.value.trim() !== "") {
                    const weight = positiveNumber(el.weight.value);
                    if (Number.isNaN(weight)) {
                        return { error: "Weight must be a number greater than zero, or left empty." };
                    }
                    item.weight = weight;
                }
            } else if (info.input_type === "duration") {
                const minutes = el.minutes.value.trim() === "" ? 0 : wholeNumber(el.minutes.value);
                const seconds = el.seconds.value.trim() === "" ? 0 : wholeNumber(el.seconds.value);
                const total = minutes * 60 + seconds;
                if (Number.isNaN(total) || seconds > 59) {
                    return { error: "Minutes and seconds must be whole numbers (seconds up to 59)." };
                }
                if (total < 1 || total > MAX_DURATION_SECONDS) {
                    return { error: "Enter a duration of at least one second, and at most 24 hours." };
                }
                item.duration_seconds = total;
            } else {
                const distance = positiveNumber(el.distance.value);
                if (Number.isNaN(distance)) {
                    return { error: "Distance must be a number greater than zero." };
                }
                item.distance = distance;
            }
            return { item: item };
        }

        function onPickerSubmit(event) {
            event.preventDefault();
            if (!state.picking) {
                return;
            }
            const result = readPicker();
            if (result.error) {
                el.pickerError.textContent = result.error;
                setHidden(el.pickerError, false);
                return;
            }
            const { section, index } = state.picking;
            const list = state.items[section];
            if (index === null) {
                list.push(result.item);
            } else {
                list[index] = result.item;
            }
            state.dirty = true;
            closePicker();
            renderBuilder();
        }

        function onPickerRemove() {
            if (!state.picking || state.picking.index === null) {
                return;
            }
            const { section, index } = state.picking;
            state.items[section].splice(index, 1);
            state.dirty = true;
            closePicker();
            renderBuilder();
        }

        // ---- Saving ---------------------------------------------------------------
        function buildPayload() {
            const sections = {};
            Object.keys(state.items).forEach((key) => {
                sections[key] = state.items[key].map((item) => {
                    const out = { exercise_type: item.exercise_type };
                    ["sets", "reps", "duration_seconds", "distance", "weight"].forEach((field) => {
                        if (item[field] != null) {
                            out[field] = item[field];
                        }
                    });
                    return out;
                });
            });
            const payload = {
                name: el.name.value.trim(),
                unit_system: state.unitSystem,
                sections: sections,
            };
            if (state.id !== null) {
                payload.id = state.id;
            }
            return payload;
        }

        // Disabling the buttons while a save or log is in flight is what stops a
        // double-click from doing it twice.
        function setBusy(busy) {
            el.save.disabled = busy;
            el.log.disabled = busy;
        }

        function goHome() {
            state.dirty = false;
            env.navigate(config.homeUrl);
        }

        // Sends `payload`. If the name is already taken, asks whether to replace that
        // workout and, if so, sends again aimed at it. Returns the server's answer, or
        // null if the person said no.
        async function postReplacingIfAsked(url, payload) {
            let result = await post(url, payload);
            if (result.status === 409 && result.data.error === "name_taken") {
                const replace = env.confirm(
                    `You already have a workout called "${payload.name}". Replace it?`
                );
                if (!replace) {
                    return null;
                }
                payload.id = result.data.existing_id;
                result = await post(url, payload);
            }
            return result;
        }

        async function onSave() {
            clearMessages();
            if (el.name.value.trim() === "") {
                showErrors("Give your workout a name before saving.");
                el.name.focus();
                return;
            }
            if (totalItems() === 0) {
                showErrors("Add at least one exercise before saving.");
                return;
            }

            setBusy(true);
            try {
                const result = await postReplacingIfAsked(config.saveUrl, buildPayload());
                if (result === null) {
                    return;
                }

                if (result.ok) {
                    goHome();
                } else if (result.status === 400 && result.data.errors) {
                    showErrors(result.data.message || "Please fix the problems below.",
                        serverErrorLines(result.data.errors));
                } else {
                    showErrors(result.data.message || "Your workout couldn't be saved. Please try again.");
                }
            } catch (e) {
                showErrors("Couldn't reach the server. Check your connection and try again.");
            } finally {
                setBusy(false);
            }
        }

        // ---- Logging -----------------------------------------------------------------
        // A workout opened from a preset and not touched since is already saved.
        // Anything else (a new workout, or a loaded one that was edited) is not.
        function isSavedAndUnchanged() {
            return state.id !== null && !state.dirty;
        }

        function rememberLogsForHome(logIds) {
            try {
                if (env.sessionStorage) {
                    env.sessionStorage.setItem(
                        HANDOFF_KEY, JSON.stringify({ logIds: logIds, at: env.now() })
                    );
                }
            } catch (e) {
                // Without it RepKin just won't comment this time. The workout IS logged.
            }
        }

        async function onLog() {
            clearMessages();
            if (totalItems() === 0) {
                showErrors("Add at least one exercise before logging.");
                return;
            }
            const sure = env.confirm(
                "Log this workout now? It counts toward RepKin's stats and can't be undone. " +
                "Workouts not saved as presets will be automatically saved upon workout submission."
            );
            if (!sure) {
                return;
            }

            setBusy(true);
            try {
                const payload = buildPayload();
                if (isSavedAndUnchanged()) {
                    // Nothing new to save: just log it.
                    delete payload.name;
                    delete payload.id;
                } else {
                    // Not saved yet (or changed since it was loaded): the server saves it
                    // as part of logging, giving it a dated name if it has none.
                    payload.save_preset = true;
                }
                const result = await postReplacingIfAsked(config.logUrl, payload);
                if (result === null) {
                    return;
                }

                if (result.ok && Array.isArray(result.data.log_ids)) {
                    rememberLogsForHome(result.data.log_ids);
                    goHome();
                } else if (result.status === 400 && result.data.errors) {
                    showErrors(result.data.message || "Please fix the problems below.",
                        serverErrorLines(result.data.errors));
                } else if (result.data.error === "too_many_presets") {
                    showErrors(`${result.data.message} Your workout wasn't logged.`);
                } else {
                    showErrors(result.data.message || "Your workout couldn't be logged. Please try again.");
                }
            } catch (e) {
                showErrors("Couldn't reach the server. Check your connection and try again.");
            } finally {
                setBusy(false);
            }
        }

        // ---- Loading and deleting presets ------------------------------------------------
        function formatDate(iso) {
            const date = new Date(iso);
            return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
        }

        function renderPresetList(presets) {
            el.presetList.textContent = "";
            setHidden(el.presetsEmpty, presets.length > 0);
            presets.forEach((preset) => {
                const row = doc.createElement("li");
                row.className = "wl-preset";
                row.dataset.id = String(preset.id);

                const open = doc.createElement("button");
                open.type = "button";
                open.className = "wl-preset__open";
                const name = doc.createElement("span");
                name.className = "wl-preset__name";
                name.textContent = preset.name;
                const meta = doc.createElement("span");
                meta.className = "wl-preset__meta";
                const count = preset.exercise_count;
                const when = formatDate(preset.updated_at);
                meta.textContent = `${count} ${count === 1 ? "exercise" : "exercises"}` +
                    (when ? ` \u00b7 updated ${when}` : "");
                open.appendChild(name);
                open.appendChild(meta);
                open.addEventListener("click", () => openPreset(preset.id));

                const remove = doc.createElement("button");
                remove.type = "button";
                remove.className = "wl-button wl-button--danger wl-preset__delete";
                remove.textContent = "Delete";
                remove.setAttribute("aria-label", `Delete ${preset.name}`);
                remove.addEventListener("click", () => deletePreset(preset));

                row.appendChild(open);
                row.appendChild(remove);
                el.presetList.appendChild(row);
            });
        }

        async function onLoadToggle() {
            clearMessages();
            if (!el.presets.hidden) {
                setHidden(el.presets, true);
                el.load.setAttribute("aria-expanded", "false");
                return;
            }
            if (!(await ensureCatalog())) {
                return;
            }
            try {
                const result = await request(config.presetsUrl);
                if (!result.ok) {
                    showErrors("Your workouts couldn't be loaded. Please try again.");
                    return;
                }
                renderPresetList(result.data.presets || []);
                setHidden(el.presets, false);
                el.load.setAttribute("aria-expanded", "true");
            } catch (e) {
                showErrors("Couldn't reach the server. Check your connection and try again.");
            }
        }

        async function openPreset(id) {
            if (!confirmDiscard()) {
                return;
            }
            clearMessages();
            const unitSystem = currentUnitSystem();
            try {
                const result = await request(
                    `${urlFor(config.detailUrl, id)}?unit_system=${unitSystem}`
                );
                if (!result.ok) {
                    showErrors(result.data.message || "That workout couldn't be loaded.");
                    return;
                }
                const preset = result.data;
                state.id = preset.id;
                state.unitSystem = unitSystem;
                state.items = emptyItems();
                Object.keys(preset.sections || {}).forEach((key) => {
                    if (!state.items[key]) {
                        return;
                    }
                    state.items[key] = preset.sections[key].map((item) => ({
                        exercise_type: item.exercise_type,
                        sets: item.sets != null ? item.sets : null,
                        reps: item.reps != null ? item.reps : null,
                        duration_seconds: item.duration_seconds != null ? item.duration_seconds : null,
                        distance: item.distance != null ? item.distance : null,
                        weight: item.weight != null ? item.weight : null,
                    }));
                });
                state.dirty = false;
                el.name.value = preset.name;
                setHidden(el.presets, true);
                el.load.setAttribute("aria-expanded", "false");
                showBuilder();
                el.name.focus();
            } catch (e) {
                showErrors("Couldn't reach the server. Check your connection and try again.");
            }
        }

        async function deletePreset(preset) {
            if (!env.confirm(`Delete "${preset.name}"? This can't be undone.`)) {
                return;
            }
            clearMessages();
            try {
                const result = await post(urlFor(config.deleteUrl, preset.id));
                if (!result.ok) {
                    showErrors(result.data.message || "That workout couldn't be deleted.");
                    return;
                }
                const row = el.presetList.querySelector(`[data-id="${preset.id}"]`);
                if (row) {
                    row.remove();
                }
                setHidden(el.presetsEmpty, el.presetList.children.length > 0);
                if (state.id === preset.id) {
                    state.id = null;        // saving it now makes a new preset
                }
                showStatus(`Deleted "${preset.name}".`);
            } catch (e) {
                showErrors("Couldn't reach the server. Check your connection and try again.");
            }
        }

        // ---- Wiring ------------------------------------------------------------------
        function start() {
            el.create.addEventListener("click", onCreate);
            el.load.addEventListener("click", onLoadToggle);
            el.save.addEventListener("click", onSave);
            el.log.addEventListener("click", onLog);
            el.name.addEventListener("input", () => { state.dirty = true; });
            el.pickerForm.addEventListener("submit", onPickerSubmit);
            el.pickerCancel.addEventListener("click", closePicker);
            el.pickerRemove.addEventListener("click", onPickerRemove);
            el.pickerSelect.addEventListener("change", () => showFieldsFor(el.pickerSelect.value));
            el.picker.addEventListener("close", () => { state.picking = null; });

            env.window.addEventListener("beforeunload", (event) => {
                if (state.dirty) {
                    event.preventDefault();
                    event.returnValue = "";
                }
            });
            // Fetch the exercise list now so the first tap on "+" is instant.
            ensureCatalog();
        }

        return { start: start, state: state };
    }

    function realEnvironment() {
        let storage = null;
        try {
            storage = window.localStorage;
        } catch (e) {
            storage = null;
        }
        let sessionStorage = null;
        try {
            sessionStorage = window.sessionStorage;
        } catch (e) {
            sessionStorage = null;
        }
        return {
            window: window,
            document: document,
            fetch: window.fetch.bind(window),
            confirm: window.confirm.bind(window),
            navigate: (url) => window.location.assign(url),
            storage: storage,
            sessionStorage: sessionStorage,
            now: () => Date.now(),
        };
    }

    window.WorkoutBuilder = { create: create };
    // Tests set this flag so they can build the page with their own fakes.
    if (!window.__workoutBuilderManualStart) {
        const builder = create(realEnvironment());
        if (builder) {
            builder.start();
        }
    }
})();
