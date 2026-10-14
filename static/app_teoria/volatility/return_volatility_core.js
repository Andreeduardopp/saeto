/**
 * Rules of the return & volatility screen, with no DOM and no messages: reading a
 * typed price, the size of the series, the returns and their sample statistics,
 * and the pagination arithmetic.
 *
 * Every failure comes back as a code, so the screen keeps the Portuguese and
 * English texts and this file can be tested under node (tests/js/).
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    if (root) {
        root.saetoReturnVolatility = api;
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    // The feedback asks for at least 300 prices; 1,000 is the limit the screen,
    // the import, the restore and the save validation all share (plan §3).
    const MIN_PRICES = 3;
    const MAX_PRICES = 1000;
    const PAGE_SIZES = [25, 50, 100];
    const DEFAULT_PAGE_SIZE = 25;

    // Codes for one price: the screen turns each one into a message next to its row.
    const PRICE_ERRORS = ['EMPTY', 'AMBIGUOUS_SEPARATOR', 'NOT_A_NUMBER', 'NOT_POSITIVE'];
    // Codes for the series as a whole and for the "number of prices" field.
    const SERIES_ERRORS = ['SERIES_TOO_SHORT', 'SERIES_TOO_LONG'];
    const COUNT_ERRORS = ['COUNT_EMPTY', 'COUNT_NOT_INTEGER', 'COUNT_RANGE'];

    const text = (value) => (value === undefined || value === null ? '' : String(value)).trim();

    /**
     * One typed price. Accepts a comma or a dot as the decimal separator, rejects
     * thousands separators and any mix of the two, and never silently drops input.
     */
    function parsePrice(value) {
        const raw = text(value);
        if (raw === '') {
            return { code: 'EMPTY' };
        }
        const dots = (raw.match(/\./g) || []).length;
        const commas = (raw.match(/,/g) || []).length;
        if (dots + commas > 1) {
            return { code: 'AMBIGUOUS_SEPARATOR' };
        }
        const normalized = raw.replace(',', '.');
        // Plain decimals only: "1.234" would be read as 1.234, never as 1234.
        if (!/^[+-]?(\d+(\.\d*)?|\.\d+)$/.test(normalized)) {
            return { code: 'NOT_A_NUMBER' };
        }
        const number = Number(normalized);
        if (!Number.isFinite(number)) {
            return { code: 'NOT_A_NUMBER' };
        }
        if (number <= 0) {
            return { code: 'NOT_POSITIVE' };
        }
        return { value: number };
    }

    /** The "number of prices (N)" field: a whole number inside the shared range. */
    function parseCount(value, limits) {
        const { min, max } = range(limits);
        const raw = text(value);
        if (raw === '') {
            return { code: 'COUNT_EMPTY' };
        }
        if (!/^[+-]?\d+$/.test(raw)) {
            return { code: 'COUNT_NOT_INTEGER' };
        }
        const number = Number(raw);
        if (!Number.isInteger(number)) {
            return { code: 'COUNT_NOT_INTEGER' };
        }
        if (number < min || number > max) {
            return { code: 'COUNT_RANGE' };
        }
        return { value: number };
    }

    function range(limits) {
        const min = limits && Number.isInteger(limits.min) ? limits.min : MIN_PRICES;
        const max = limits && Number.isInteger(limits.max) ? limits.max : MAX_PRICES;
        return { min, max };
    }

    /**
     * The whole series as typed. Returns every offending row instead of stopping at
     * the first one, so the screen can list them and jump to each.
     */
    function validateSeries(values, limits) {
        const { min, max } = range(limits);
        const list = Array.isArray(values) ? values : [];
        const prices = [];
        const rowErrors = [];
        list.forEach((value, index) => {
            const parsed = parsePrice(value);
            if (parsed.code) {
                rowErrors.push({ index, code: parsed.code });
            } else {
                prices.push(parsed.value);
            }
        });
        const seriesErrors = [];
        if (list.length < min) {
            seriesErrors.push({ code: 'SERIES_TOO_SHORT' });
        } else if (list.length > max) {
            seriesErrors.push({ code: 'SERIES_TOO_LONG' });
        }
        const valid = rowErrors.length === 0 && seriesErrors.length === 0;
        return { valid, prices: valid ? prices : null, rowErrors, seriesErrors, count: list.length };
    }

    const mean = (values) => values.reduce((acc, value) => acc + value, 0) / values.length;

    /** Sample standard deviation: the sum of squares over n − 1 = N − 2. */
    function sampleStd(values) {
        if (values.length < 2) {
            return NaN;
        }
        const average = mean(values);
        const squares = values.reduce((acc, value) => acc + (value - average) ** 2, 0);
        return Math.sqrt(squares / (values.length - 1));
    }

    /**
     * N prices give n = N − 1 returns; the first price has no return of its own.
     * Values stay as fractions (0.05), never multiplied by 100 for display.
     */
    function computeReturns(prices) {
        if (!Array.isArray(prices) || prices.length < 2) {
            return null;
        }
        const discrete = [];
        const continuous = [];
        for (let i = 1; i < prices.length; i++) {
            discrete.push((prices[i] - prices[i - 1]) / prices[i - 1]);
            continuous.push(Math.log(prices[i] / prices[i - 1]));
        }
        return {
            discrete_returns: discrete,
            continuous_returns: continuous,
            mean_discrete: mean(discrete),
            mean_continuous: mean(continuous),
            volatility_discrete: sampleStd(discrete),
            volatility_continuous: sampleStd(continuous),
        };
    }

    // --- Pagination: presentation only, never the set that gets calculated -------

    const pageCount = (total, size) => Math.max(1, Math.ceil(Math.max(total, 0) / size));

    const clampPage = (page, total, size) => Math.min(Math.max(1, Math.trunc(page) || 1), pageCount(total, size));

    /** Half-open range [start, end) of the rows shown on a page. */
    function pageRange(page, total, size) {
        const current = clampPage(page, total, size);
        const start = (current - 1) * size;
        return { page: current, start, end: Math.min(start + size, Math.max(total, 0)) };
    }

    /** The page a row index (0-based) falls on, to jump straight to a failed row. */
    const pageOfIndex = (index, size) => Math.max(1, Math.floor(Math.max(index, 0) / size) + 1);

    return {
        MIN_PRICES,
        MAX_PRICES,
        PAGE_SIZES,
        DEFAULT_PAGE_SIZE,
        PRICE_ERRORS,
        SERIES_ERRORS,
        COUNT_ERRORS,
        parsePrice,
        parseCount,
        validateSeries,
        mean,
        sampleStd,
        computeReturns,
        pageCount,
        clampPage,
        pageRange,
        pageOfIndex,
    };
}));
