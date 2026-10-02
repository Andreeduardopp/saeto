/**
 * Seeded random numbers for the screens that simulate in the browser.
 *
 * Math.random cannot be seeded, so a saved simulation could not be re-run with
 * the same numbers. These screens draw from saetoRandom(seed) instead and save
 * the seed they used. Loaded once by home.html, like save_project.js.
 */
(function () {
    const MAX_SEED = 4294967295;  // 2^32 - 1

    // mulberry32: a small, fast 32-bit generator; returns floats in [0, 1).
    function mulberry32(seed) {
        let state = seed >>> 0;
        return function () {
            state = (state + 0x6D2B79F5) >>> 0;
            let t = state;
            t = Math.imul(t ^ (t >>> 15), t | 1);
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    window.saetoRandom = function (seed) {
        const uniform = mulberry32(seed);
        return {
            uniform,
            // Standard normal by Box-Muller; 1 - uniform() keeps log() away from 0.
            normal() {
                const u1 = 1 - uniform();
                const u2 = uniform();
                return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
            },
        };
    };

    window.saetoRandom.MAX_SEED = MAX_SEED;

    // A fresh seed for runs where the user left the seed empty.
    window.saetoRandom.newSeed = function () {
        if (window.crypto && window.crypto.getRandomValues) {
            return window.crypto.getRandomValues(new Uint32Array(1))[0];
        }
        return Math.floor(Math.random() * (MAX_SEED + 1));
    };
})();
