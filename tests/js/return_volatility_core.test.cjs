const assert = require('node:assert/strict');
const test = require('node:test');

const core = require('../../static/app_teoria/volatility/return_volatility_core.js');

const close = (actual, expected, tolerance = 1e-10) =>
    assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

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
