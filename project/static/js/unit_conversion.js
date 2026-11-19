//This script is intended to usedin our conversions when prompted by the user. We will be using SI Units(cm,kg) and Imperial Units(ft,lbs)
//  primarily with our main menu display and data handling to our encrypted database(Firebase).
window.Units = (function () {
    const CM_PER_IN = 2.54, LB_PER_KG = 2.20462;
    const round1 = (n) => Math.round(n * 10) / 10;
    const num = (t) => { const s = String(t).trim(); return s === "" ? NaN : Number(s); };

    function parseHeight(text, system) {            // returns cm, or NaN
        const t = String(text).trim().toLowerCase();
        if (system === "si") return num(t);
        const m = t.match(/^(\d+)\s*(?:'|ft|\s)\s*(\d+(?:\.\d+)?)\s*(?:"|in)?$/);   // 5'11, 5 11, 5 ft 11 in
        if (m) return (Number(m[1]) * 12 + Number(m[2])) * CM_PER_IN;
        const feet = num(t);                         // plain "5.9" means decimal feet
        return feet * 12 * CM_PER_IN;
    }
    function parseWeight(text, system) {            // returns kg, or NaN
        const n = num(text);
        return system === "si" ? n : n / LB_PER_KG;
    }
    function formatHeight(cm, system) {
        if (cm == null) return "";
        if (system === "si") return round1(cm) + " cm";
        const inches = Math.round(cm / CM_PER_IN);
        return Math.floor(inches / 12) + " ft " + (inches % 12) + " in";
    }
    function formatWeight(kg, system) {
        if (kg == null) return "";
        return system === "si" ? round1(kg) + " kg" : round1(kg * LB_PER_KG) + " lbs";
    }
    return { parseHeight, parseWeight, formatHeight, formatWeight };
})();