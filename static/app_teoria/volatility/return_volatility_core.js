/**
 * Rules of the return & volatility screen, with no DOM and no messages: reading a
 * typed price, the size of the series, the returns and their sample statistics,
 * how a number is written out (the separator comes from the caller) and the
 * pagination arithmetic.
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

    // Annualization (plan §6): m is the number of periods per year, fixed by the
    // frequency of the prices the user picks. 252, 12 and 1 are the usual
    // conventions, not a count of the prices in the sample.
    const PERIODS_PER_YEAR = { daily: 252, monthly: 12, annual: 1 };
    const FREQUENCIES = Object.keys(PERIODS_PER_YEAR);
    const MIN_PERIODS_PER_YEAR = 1;
    // Minute data of a trading year is around 98,000 periods: the cap keeps m a
    // plausible frequency, and the overflow guard of `annualize` does the rest.
    const MAX_PERIODS_PER_YEAR = 100000;

    // Codes for one price: the screen turns each one into a message next to its row.
    const PRICE_ERRORS = ['EMPTY', 'AMBIGUOUS_SEPARATOR', 'NOT_A_NUMBER', 'NOT_POSITIVE'];
    // Codes for the series as a whole and for the "number of prices" field.
    const SERIES_ERRORS = ['SERIES_TOO_SHORT', 'SERIES_TOO_LONG'];
    const COUNT_ERRORS = ['COUNT_EMPTY', 'COUNT_NOT_INTEGER', 'COUNT_RANGE'];
    // Codes for the "periods per year (m)" field and for an annualization whose
    // result leaves the range a number can hold.
    const PERIODS_ERRORS = ['PERIODS_EMPTY', 'PERIODS_NOT_INTEGER', 'PERIODS_RANGE'];
    const ANNUAL_ERRORS = ['ANNUAL_NOT_FINITE'];

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

    /** A typed whole number inside a range, with the codes of its own field. */
    function parseInteger(value, bounds, codes) {
        const raw = text(value);
        if (raw === '') {
            return { code: codes.empty };
        }
        if (!/^[+-]?\d+$/.test(raw)) {
            return { code: codes.notInteger };
        }
        const number = Number(raw);
        if (!Number.isInteger(number)) {
            return { code: codes.notInteger };
        }
        if (number < bounds.min || number > bounds.max) {
            return { code: codes.range };
        }
        return { value: number };
    }

    /** The "number of prices (N)" field: a whole number inside the shared range. */
    function parseCount(value, limits) {
        return parseInteger(value, range(limits),
            { empty: 'COUNT_EMPTY', notInteger: 'COUNT_NOT_INTEGER', range: 'COUNT_RANGE' });
    }

    /** The "periods per year (m)" field: a positive whole number, never a count of prices. */
    function parsePeriodsPerYear(value, limits) {
        return parseInteger(value, periodsRange(limits),
            { empty: 'PERIODS_EMPTY', notInteger: 'PERIODS_NOT_INTEGER', range: 'PERIODS_RANGE' });
    }

    function bounded(limits, key, fallback) {
        return limits && Number.isInteger(limits[key]) ? limits[key] : fallback;
    }

    function range(limits) {
        return { min: bounded(limits, 'min', MIN_PRICES), max: bounded(limits, 'max', MAX_PRICES) };
    }

    function periodsRange(limits) {
        return {
            min: bounded(limits, 'min', MIN_PERIODS_PER_YEAR),
            max: bounded(limits, 'max', MAX_PERIODS_PER_YEAR),
        };
    }

    /** The m fixed by a frequency, or null when the frequency is not one of the screen's. */
    function suggestedPeriods(frequency) {
        const suggestion = PERIODS_PER_YEAR[frequency];
        return suggestion === undefined ? null : suggestion;
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

    /**
     * A pasted column is one price per line, never CSV. Keep original line numbers
     * and character offsets so an error can select the offending text, even after
     * ignoring empty lines outside the block. Internal blanks remain observations.
     */
    function readPastedColumn(content, limits) {
        const raw = content === undefined || content === null ? '' : String(content);
        const entries = [];
        const lines = /([^\r\n]*)(\r\n|\r|\n|$)/g;
        let match;
        let line = 1;
        while ((match = lines.exec(raw)) !== null) {
            entries.push({ text: match[1].trim(), line, start: match.index,
                end: match.index + match[1].length });
            line++;
            if (!match[2]) break;
        }
        let start = 0;
        let end = entries.length;
        while (start < end && entries[start].text === '') start++;
        while (end > start && entries[end - 1].text === '') end--;
        const selected = entries.slice(start, end);
        const texts = selected.map(entry => entry.text);
        return { ...validateSeries(texts, limits), texts, entries: selected };
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

    /**
     * Annualizes a calculated run, from its **continuous** statistics: the annual
     * rate equivalent to the mean log return, and the volatility scaled by the
     * square root of time. Fractions in, fractions out.
     *
     *     annual_rate_equivalent     = exp(m * mu_log) - 1
     *     annual_volatility_continuous = sqrt(m) * sigma_log
     *
     * This is not the accumulated return of the window (S_final / S_inicial - 1),
     * and the square root of time assumes returns with no autocorrelation and a
     * stable variance. A product outside the range a number can hold comes back as
     * a code, instead of an Infinity reaching the screen, the copy or the save.
     */
    function annualize(results, periodsPerYear) {
        // No coercion: the caller parses the field, so a "252" here is a mistake.
        const m = periodsPerYear;
        const meanLog = results ? results.mean_continuous : undefined;
        const volatilityLog = results ? results.volatility_continuous : undefined;
        if (!Number.isInteger(m) || m < MIN_PERIODS_PER_YEAR
            || !Number.isFinite(meanLog) || !Number.isFinite(volatilityLog)) {
            return { code: 'ANNUAL_NOT_FINITE' };
        }
        const rate = Math.exp(m * meanLog) - 1;
        const volatility = Math.sqrt(m) * volatilityLog;
        if (!Number.isFinite(rate) || !Number.isFinite(volatility)) {
            return { code: 'ANNUAL_NOT_FINITE' };
        }
        return {
            value: {
                periods_per_year: m,
                annual_rate_equivalent: rate,
                annual_volatility_continuous: volatility,
            },
        };
    }

    // --- Presentation: one rule for the screen, the copy and the report ---------

    // Four decimals of a percentage, the precision the returns table, the summary,
    // the copy and the saved report all show (plan §5). Chart axes may show fewer.
    const PERCENT_DECIMALS = 4;

    /**
     * A finite number as text, with the decimal separator given by the screen's
     * language. Without `decimals` every digit the number holds is kept, so a
     * price shown back to the user never loses the precision it was typed with.
     */
    function formatNumber(value, options) {
        if (typeof value !== 'number' || !Number.isFinite(value)) {
            return '-';
        }
        const settings = options || {};
        const text = settings.decimals === undefined
            ? String(value)
            : value.toFixed(settings.decimals);
        const separator = settings.separator || '.';
        return separator === '.' ? text : text.replace('.', separator);
    }

    /** A return kept as a fraction (0.001742), shown as a percentage (0,1742%). */
    function formatPercent(value, options) {
        if (typeof value !== 'number' || !Number.isFinite(value)) {
            return '-';
        }
        const settings = options || {};
        const decimals = settings.decimals === undefined ? PERCENT_DECIMALS : settings.decimals;
        return `${formatNumber(value * 100, { decimals: decimals, separator: settings.separator })}%`;
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
        PERCENT_DECIMALS,
        PERIODS_PER_YEAR,
        FREQUENCIES,
        MIN_PERIODS_PER_YEAR,
        MAX_PERIODS_PER_YEAR,
        PRICE_ERRORS,
        SERIES_ERRORS,
        COUNT_ERRORS,
        PERIODS_ERRORS,
        ANNUAL_ERRORS,
        parsePrice,
        parseCount,
        parsePeriodsPerYear,
        suggestedPeriods,
        validateSeries,
        readPastedColumn,
        mean,
        sampleStd,
        computeReturns,
        annualize,
        formatNumber,
        formatPercent,
        pageCount,
        clampPage,
        pageRange,
        pageOfIndex,
    };
}));
