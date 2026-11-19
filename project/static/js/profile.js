//This script handles our PII handling whether it be for display, conversion, or database storing and retrieval.

(function () {
    const forms = document.querySelectorAll(".menu_form[data-profile]");
    if (!forms.length) return;
    const url = forms[0].action;
    const boxes = {
        height_cm: document.getElementById("cur-height"),
        weight_kg: document.getElementById("cur-weight"),
    };
    const saved = {};
    const system = () => document.documentElement.dataset.unit || "imp";

    function show() {
        boxes.height_cm.value = Units.formatHeight(saved.height_cm, system());
        boxes.weight_kg.value = Units.formatWeight(saved.weight_kg, system());
    }
    function flash(box, msg) {
        box.value = msg;
        setTimeout(show, 2000);
    }

    fetch(url, { credentials: "same-origin" })
        .then((r) => (r.ok ? r.json() : {}))
        .then((d) => { Object.assign(saved, d); show(); })
        .catch(() => {});

    document.addEventListener("unitchange", show);

    forms.forEach((form) => {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const field = form.dataset.profile;
            const parse = field === "height_cm" ? Units.parseHeight : Units.parseWeight;
            const value = parse(form.elements[field].value, system());   // typed units -> cm / kg
            if (!Number.isFinite(value)) { flash(boxes[field], "Enter a number."); return; }
            const data = new FormData(form);
            data.set(field, value.toFixed(1));
            try {
                const res = await fetch(form.action, { method: "POST", body: data, credentials: "same-origin" });
                const out = await res.json();
                if (!res.ok) { flash(boxes[field], out.error || "Could not save."); return; }
                saved[field] = out[field];
                show();
                form.reset();
            } catch (err) {
                flash(boxes[field], "Network error.");
            }
        });
    });
})();