const assert = require('node:assert/strict');
const test = require('node:test');

const core = require('../../static/app_teoria/volatility/return_volatility_core.js');

const close = (actual, expected, tolerance = 1e-10) =>
    assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

test('pasted columns keep decimal commas, precision and order with any line ending', () => {
    for (const newline of ['\n', '\r\n', '\r']) {
        const result = core.readPastedColumn([' 26,27103 ', '26.17373', '26,48509'].join(newline));
        assert.equal(result.valid, true);
        assert.deepEqual(result.prices, [26.27103, 26.17373, 26.48509]);
        assert.deepEqual(result.entries.map(entry => entry.line), [1, 2, 3]);
        assert.deepEqual(core.computeReturns(result.prices), core.computeReturns([26.27103, 26.17373, 26.48509]));
    }
});

test('only outside blank lines are ignored and error selection uses original offsets', () => {
    const raw = '\r\n  \r\n100\r\n\r\n abc \r\n110\r\n \r\n';
    const result = core.readPastedColumn(raw);
    assert.equal(result.valid, false);
    assert.equal(result.prices, null);
    assert.equal(result.count, 4);
    assert.deepEqual(result.rowErrors, [{ index: 1, code: 'EMPTY' }, { index: 2, code: 'NOT_A_NUMBER' }]);
    assert.deepEqual(result.entries.map(entry => entry.line), [3, 4, 5, 6]);
    const wrong = result.entries[2];
    assert.equal(raw.slice(wrong.start, wrong.end), ' abc ');
});

test('pasting never detects headers, CSV columns, thousands separators or formulas', () => {
    for (const bad of ['Preço', '100\t200', '100;200', '1.234,56', '1,234.56', '1,2,3', '=100+1', 'NaN', 'Infinity', '0', '-1']) {
        const result = core.readPastedColumn(`100\n${bad}\n110`);
        assert.equal(result.valid, false, bad);
        assert.equal(result.prices, null, bad);
        assert.equal(result.rowErrors[0].index, 1, bad);
    }
    assert.deepEqual(core.readPastedColumn('1,100\n2,200\n3,300').prices, [1.1, 2.2, 3.3]);
});

test('paste limits refuse the whole block rather than keeping its valid prefix', () => {
    for (const size of [2, 3, 30, 31, 249, 300, 1000, 1001]) {
        const result = core.readPastedColumn(Array(size).fill('100').join('\n'));
        assert.equal(result.count, size);
        assert.equal(result.valid, size >= 3 && size <= 1000);
        if (result.valid) assert.equal(result.prices.length, size);
        else assert.equal(result.prices, null);
    }
    for (const blank of ['', ' \r\n\t\n', null, undefined]) {
        const result = core.readPastedColumn(blank);
        assert.equal(result.count, 0);
        assert.deepEqual(result.seriesErrors, [{ code: 'SERIES_TOO_SHORT' }]);
    }
    assert.equal(core.readPastedColumn('1\n2\n3', { min: 4, max: 6 }).valid, false);
});

test('a typed price accepts a dot or a comma as the decimal separator', () => {
    assert.deepEqual(core.parsePrice('26.27103'), { value: 26.27103 });
    assert.deepEqual(core.parsePrice('26,27103'), { value: 26.27103 });
    assert.deepEqual(core.parsePrice('  107.5  '), { value: 107.5 });
    assert.deepEqual(core.parsePrice('100'), { value: 100 });
    assert.deepEqual(core.parsePrice('.5'), { value: 0.5 });
});

test('a typed price keeps every digit it was given', () => {
    assert.equal(core.parsePrice('26,27103').value, 26.27103);
    assert.equal(String(core.parsePrice('26,27103').value), '26.27103');
});

test('an ambiguous or unreadable price is reported, not guessed', () => {
    assert.deepEqual(core.parsePrice('1.234,56'), { code: 'AMBIGUOUS_SEPARATOR' });
    assert.deepEqual(core.parsePrice('1.234.567'), { code: 'AMBIGUOUS_SEPARATOR' });
    assert.deepEqual(core.parsePrice('1,234,567'), { code: 'AMBIGUOUS_SEPARATOR' });
    assert.deepEqual(core.parsePrice('abc'), { code: 'NOT_A_NUMBER' });
    assert.deepEqual(core.parsePrice('1e3'), { code: 'NOT_A_NUMBER' });
    assert.deepEqual(core.parsePrice('Infinity'), { code: 'NOT_A_NUMBER' });
    assert.deepEqual(core.parsePrice(''), { code: 'EMPTY' });
    assert.deepEqual(core.parsePrice(null), { code: 'EMPTY' });
    assert.deepEqual(core.parsePrice('0'), { code: 'NOT_POSITIVE' });
    assert.deepEqual(core.parsePrice('-5'), { code: 'NOT_POSITIVE' });
});

test('the number of prices must be a whole number inside the shared range', () => {
    const limits = { min: 3, max: 1000 };
    assert.deepEqual(core.parseCount('249', limits), { value: 249 });
    assert.deepEqual(core.parseCount('3', limits), { value: 3 });
    assert.deepEqual(core.parseCount('1000', limits), { value: 1000 });
    assert.deepEqual(core.parseCount('2', limits), { code: 'COUNT_RANGE' });
    assert.deepEqual(core.parseCount('1001', limits), { code: 'COUNT_RANGE' });
    assert.deepEqual(core.parseCount('10.5', limits), { code: 'COUNT_NOT_INTEGER' });
    assert.deepEqual(core.parseCount('abc', limits), { code: 'COUNT_NOT_INTEGER' });
    assert.deepEqual(core.parseCount('  ', limits), { code: 'COUNT_EMPTY' });
});

test('the default limits are 3 to 1000 prices', () => {
    assert.equal(core.MIN_PRICES, 3);
    assert.equal(core.MAX_PRICES, 1000);
    assert.deepEqual(core.parseCount('1001'), { code: 'COUNT_RANGE' });
});

test('a valid series reports its prices in the order received', () => {
    const result = core.validateSeries(['100', '105', '98,5'], { min: 3, max: 1000 });
    assert.equal(result.valid, true);
    assert.deepEqual(result.prices, [100, 105, 98.5]);
    assert.equal(result.count, 3);
    assert.deepEqual(result.rowErrors, []);
});

test('every offending row is listed, not only the first one', () => {
    const result = core.validateSeries(['100', '', 'abc', '-1', '110'], { min: 3, max: 1000 });
    assert.equal(result.valid, false);
    assert.equal(result.prices, null);
    assert.deepEqual(result.rowErrors, [
        { index: 1, code: 'EMPTY' },
        { index: 2, code: 'NOT_A_NUMBER' },
        { index: 3, code: 'NOT_POSITIVE' },
    ]);
    assert.deepEqual(result.seriesErrors, []);
});

test('a series shorter or longer than the limits is reported as such', () => {
    const limits = { min: 3, max: 1000 };
    const short = core.validateSeries(['100', '105'], limits);
    assert.deepEqual(short.seriesErrors, [{ code: 'SERIES_TOO_SHORT' }]);
    const long = core.validateSeries(Array(1001).fill('100'), limits);
    assert.deepEqual(long.seriesErrors, [{ code: 'SERIES_TOO_LONG' }]);
    assert.equal(long.count, 1001);
    assert.equal(core.validateSeries(Array(1000).fill('100'), limits).valid, true);
});

test('N prices give N - 1 returns', () => {
    assert.equal(core.computeReturns([100, 105, 98]).discrete_returns.length, 2);
    const prices = Array.from({ length: 249 }, (_, i) => 100 + i);
    const run = core.computeReturns(prices);
    assert.equal(run.discrete_returns.length, 248);
    assert.equal(run.continuous_returns.length, 248);
    assert.equal(core.computeReturns([100]), null);
    assert.equal(core.computeReturns([]), null);
});

test('the nine prices of the handbook example reproduce the report', () => {
    const prices = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832,
                    26.25157, 26.41698, 27.14673, 26.57266];
    const run = core.computeReturns(prices);
    assert.equal(run.continuous_returns.length, 8);
    close(run.mean_continuous * 100, 0.1427007065, 1e-9);
    close(run.volatility_continuous * 100, 1.5484927046, 1e-9);
});

test('the sample standard deviation divides by n - 1 = N - 2', () => {
    // Eight returns from nine prices divide the sum of squares by 7.
    const returns = [1, 2, 3, 4, 5, 6, 7, 9];
    const average = core.mean(returns);
    const squares = returns.reduce((acc, value) => acc + (value - average) ** 2, 0);
    close(core.sampleStd(returns), Math.sqrt(squares / 7));
    assert.ok(Number.isNaN(core.sampleStd([1])));
});

test('a constant series has zero return and zero volatility', () => {
    const run = core.computeReturns([50, 50, 50, 50]);
    assert.deepEqual(run.discrete_returns, [0, 0, 0]);
    assert.equal(run.mean_continuous, 0);
    assert.equal(run.volatility_discrete, 0);
    assert.equal(run.volatility_continuous, 0);
});

test('three increasing or decreasing prices preserve the sign and the sample divisor', () => {
    for (const [prices, factor] of [[[100, 110, 121], 1.1], [[100, 90, 81], 0.9]]) {
        const run = core.computeReturns(prices);
        assert.equal(run.continuous_returns.length, 2);
        close(run.mean_continuous, Math.log(factor), 1e-14);
        close(run.mean_discrete, factor - 1, 1e-14);
        close(run.volatility_continuous, 0, 1e-14);
        close(run.volatility_discrete, 0, 1e-14);
    }
});

test('a return is written with four percentage decimals in either language', () => {
    assert.equal(core.PERCENT_DECIMALS, 4);
    assert.equal(core.formatPercent(0.001742, { separator: ',' }), '0,1742%');
    assert.equal(core.formatPercent(0.001742, { separator: '.' }), '0.1742%');
    assert.equal(core.formatPercent(0.001742), '0.1742%');
    assert.equal(core.formatPercent(0.05, { separator: ',' }), '5,0000%');
    assert.equal(core.formatPercent(-0.0666667, { separator: ',' }), '-6,6667%');
    assert.equal(core.formatPercent(0, { separator: ',' }), '0,0000%');
    assert.equal(core.formatPercent(-0, { separator: ',' }), '0,0000%');
    // A chart axis may show fewer decimals without changing the rule.
    assert.equal(core.formatPercent(0.015, { decimals: 2, separator: ',' }), '1,50%');
});

test('the nine prices of the handbook give the same text as the saved report', () => {
    const prices = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832,
                    26.25157, 26.41698, 27.14673, 26.57266];
    const run = core.computeReturns(prices);
    const pt = (value) => core.formatPercent(value, { separator: ',' });
    assert.equal(pt(run.mean_continuous), '0,1427%');
    assert.equal(pt(run.volatility_continuous), '1,5485%');
    assert.equal(pt(run.mean_discrete), '0,1533%');
    assert.equal(pt(run.volatility_discrete), '1,5523%');
    assert.equal(pt(run.continuous_returns[0]), '-0,3711%');
    assert.equal(core.formatPercent(run.volatility_continuous, { separator: '.' }), '1.5485%');
});

test('a price keeps every digit it holds; only the separator follows the language', () => {
    assert.equal(core.formatNumber(26.27103, { separator: ',' }), '26,27103');
    assert.equal(core.formatNumber(26.27103, { separator: '.' }), '26.27103');
    assert.equal(core.formatNumber(100, { separator: ',' }), '100');
    assert.equal(core.formatNumber(107.5, { separator: ',' }), '107,5');
    assert.equal(core.formatNumber(1.23456789012, { separator: ',' }), '1,23456789012');
    // Only an explicit number of decimals rounds, and nothing unreadable passes.
    assert.equal(core.formatNumber(26.27103, { decimals: 2, separator: ',' }), '26,27');
    for (const value of [NaN, Infinity, null, undefined, '100']) {
        assert.equal(core.formatNumber(value, { separator: ',' }), '-');
        assert.equal(core.formatPercent(value, { separator: ',' }), '-');
    }
});

// --- Optional annualization (plan §6) ---------------------------------------

test('the periods per year (m) field takes a whole number inside its own range', () => {
    assert.equal(core.MIN_PERIODS_PER_YEAR, 1);
    assert.equal(core.MAX_PERIODS_PER_YEAR, 100000);
    assert.deepEqual(core.parsePeriodsPerYear('252'), { value: 252 });
    assert.deepEqual(core.parsePeriodsPerYear(' 12 '), { value: 12 });
    assert.deepEqual(core.parsePeriodsPerYear(''), { code: 'PERIODS_EMPTY' });
    assert.deepEqual(core.parsePeriodsPerYear(undefined), { code: 'PERIODS_EMPTY' });
    for (const bad of ['2,5', '2.5', '252a', 'daily', '1e3']) {
        assert.deepEqual(core.parsePeriodsPerYear(bad), { code: 'PERIODS_NOT_INTEGER' }, bad);
    }
    for (const bad of ['0', '-252', '100001']) {
        assert.deepEqual(core.parsePeriodsPerYear(bad), { code: 'PERIODS_RANGE' }, bad);
    }
    // A screen may narrow the range; m is never the count of prices (N).
    assert.deepEqual(core.parsePeriodsPerYear('400', { min: 1, max: 365 }), { code: 'PERIODS_RANGE' });
    assert.deepEqual(core.parseCount('252', { min: 3, max: 1000 }), { value: 252 });
});

test('each frequency suggests its usual m, and a custom one suggests none', () => {
    assert.deepEqual(core.PERIODS_PER_YEAR, { daily: 252, weekly: 52, monthly: 12, custom: null });
    assert.deepEqual(core.FREQUENCIES, ['daily', 'weekly', 'monthly', 'custom']);
    assert.equal(core.suggestedPeriods('daily'), 252);
    assert.equal(core.suggestedPeriods('weekly'), 52);
    assert.equal(core.suggestedPeriods('monthly'), 12);
    assert.equal(core.suggestedPeriods('custom'), null);
    assert.equal(core.suggestedPeriods('hourly'), null);
});

test('the nine prices of the handbook annualize to 43,2764% and 24,5816% with m = 252', () => {
    const prices = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832,
                    26.25157, 26.41698, 27.14673, 26.57266];
    const run = core.computeReturns(prices);
    const annual = core.annualize(run, 252).value;
    assert.equal(annual.periods_per_year, 252);
    const pt = (value) => core.formatPercent(value, { separator: ',' });
    assert.equal(pt(annual.annual_rate_equivalent), '43,2764%');
    assert.equal(pt(annual.annual_volatility_continuous), '24,5816%');
    // Rounded to two decimals, the 43,28% and 24,58% of the report.
    assert.equal(core.formatPercent(annual.annual_rate_equivalent, { decimals: 2, separator: ',' }), '43,28%');
    assert.equal(core.formatPercent(annual.annual_volatility_continuous, { decimals: 2, separator: ',' }), '24,58%');
    // The rate uses the continuous mean, not the mean of the discrete returns.
    close(annual.annual_rate_equivalent, Math.exp(252 * run.mean_continuous) - 1);
    assert.notEqual(core.formatPercent(Math.exp(252 * run.mean_discrete) - 1, { separator: ',' }),
        pt(annual.annual_rate_equivalent));
    // Volatility scales by the square root of time, on the fractions themselves.
    close(annual.annual_volatility_continuous, Math.sqrt(252) * run.volatility_continuous);
});

test('annualizing is a change of unit: weekly, monthly and a constant series', () => {
    const run = core.computeReturns([100, 105, 98, 110, 107.5]);
    for (const m of [12, 52, 252, 1]) {
        const annual = core.annualize(run, m).value;
        close(annual.annual_rate_equivalent, Math.exp(m * run.mean_continuous) - 1);
        close(annual.annual_volatility_continuous, Math.sqrt(m) * run.volatility_continuous);
    }
    // m = 1 leaves the log mean as a rate and the volatility untouched.
    const once = core.annualize(run, 1).value;
    close(once.annual_volatility_continuous, run.volatility_continuous);
    const flat = core.annualize(core.computeReturns([50, 50, 50, 50]), 252).value;
    assert.equal(flat.annual_rate_equivalent, 0);
    assert.equal(flat.annual_volatility_continuous, 0);
});

test('an m or a result outside the representable range comes back as a code', () => {
    const run = core.computeReturns([100, 105, 98, 110, 107.5]);
    for (const bad of [0, -252, 2.5, '252', NaN, Infinity, null, undefined]) {
        assert.deepEqual(core.annualize(run, bad), { code: 'ANNUAL_NOT_FINITE' }, String(bad));
    }
    assert.deepEqual(core.annualize(null, 252), { code: 'ANNUAL_NOT_FINITE' });
    assert.deepEqual(core.annualize({}, 252), { code: 'ANNUAL_NOT_FINITE' });
    // exp(m * mu) above the largest number: refused instead of an Infinity on screen.
    assert.deepEqual(core.annualize({ mean_continuous: 1000, volatility_continuous: 0.01 }, 100000),
        { code: 'ANNUAL_NOT_FINITE' });
    assert.deepEqual(core.annualize({ mean_continuous: 0.001, volatility_continuous: NaN }, 252),
        { code: 'ANNUAL_NOT_FINITE' });
    assert.deepEqual(core.ANNUAL_ERRORS, ['ANNUAL_NOT_FINITE']);
    assert.deepEqual(core.PERIODS_ERRORS, ['PERIODS_EMPTY', 'PERIODS_NOT_INTEGER', 'PERIODS_RANGE']);
});

test('pagination splits the rows without changing their order', () => {
    assert.equal(core.pageCount(249, 25), 10);
    assert.equal(core.pageCount(0, 25), 1);
    assert.equal(core.pageCount(25, 25), 1);
    assert.deepEqual(core.pageRange(1, 249, 25), { page: 1, start: 0, end: 25 });
    assert.deepEqual(core.pageRange(10, 249, 25), { page: 10, start: 225, end: 249 });
    // Out-of-range pages come back clamped instead of showing nothing.
    assert.deepEqual(core.pageRange(99, 249, 25), { page: 10, start: 225, end: 249 });
    assert.deepEqual(core.pageRange(0, 249, 25), { page: 1, start: 0, end: 25 });
    assert.equal(core.clampPage(4, 249, 100), 3);
});

test('a row index maps to the page that holds it', () => {
    assert.equal(core.pageOfIndex(0, 25), 1);
    assert.equal(core.pageOfIndex(24, 25), 1);
    assert.equal(core.pageOfIndex(25, 25), 2);
    assert.equal(core.pageOfIndex(248, 25), 10);
    assert.equal(core.pageOfIndex(248, 100), 3);
});
