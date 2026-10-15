const assert = require('node:assert/strict');
const test = require('node:test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { createHash } = require('node:crypto');
const { screenHarness } = require('./helpers/return_volatility_harness.cjs');
const path = process.env.SAETO_XLSX_PATH;
let XLSX;
if (path) {
    const bytes = readFileSync(path);
    assert.equal(createHash('sha384').update(bytes).digest('base64'), 'EnyY0/GSHQGSxSgMwaIPzSESbqoOLSexfnSMN2AP+39Ckmn92stwABZynq1JyzdT');
    XLSX = require(resolve(path));
}
const options = { skip: path ? false : 'Set SAETO_XLSX_PATH to the pinned SheetJS 0.20.3 file to exercise real XLSX bytes.' };
const prices = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832, 26.25157, 26.41698, 27.14673, 26.57266];
function file(sheets) {
    const book = XLSX.utils.book_new();
    for (const [name, sheet] of Object.entries(sheets)) XLSX.utils.book_append_sheet(book, sheet, name);
    const buffer = XLSX.write(book, { type: 'buffer', bookType: 'xlsx' });
    return { name: 'acceptance.xlsx', size: buffer.length, arrayBuffer: async () => buffer };
}

test('real XLSX numeric/text cells and CSV produce identical full-precision saved results', options, async () => {
    const ui = screenHarness('pt', null, null, XLSX);
    const data = [['Date', 'Price'], ...prices.map((value, index) => ['2026-10-' + (index + 1), index % 2 ? String(value).replace('.', ',') : value])];
    ui.mode('file');
    await ui.file(file({ Prices: XLSX.utils.aoa_to_sheet(data) }));
    assert.equal(ui.el('usePricesButton').disabled, false);
    ui.click('usePricesButton');
    ui.click('calculateButton');
    ui.click('saveProjectButton');
    const csv = screenHarness('pt');
    csv.mode('file');
    await csv.csv('Price\n' + prices.join('\n'));
    csv.click('usePricesButton');
    csv.click('calculateButton');
    csv.click('saveProjectButton');
    assert.deepEqual(ui.saves[0].parameters, csv.saves[0].parameters);
    assert.deepEqual(ui.saves[0].results, csv.saves[0].results);
});

test('real XLSX with multiple sheets requires choosing the intended series', options, async () => {
    const ui = screenHarness('en', null, null, XLSX);
    ui.mode('file');
    await ui.file(file({ First: XLSX.utils.aoa_to_sheet([['Price'], [100], [101], [102]]),
        Second: XLSX.utils.aoa_to_sheet([['Price'], ...prices.map(value => [value])]) }));
    ui.fire('previewSheet', 'change', { target: { value: '1' } });
    ui.click('usePricesButton');
    ui.click('calculateButton');
    ui.click('saveProjectButton');
    assert.deepEqual(ui.saves[0].parameters.prices, prices);
});

test('real XLSX cached formulas are read; missing caches and interior blanks cannot be applied', options, async () => {
    for (const invalid of ['missing-cache', 'blank', 'none']) {
        const ui = screenHarness('pt', null, null, XLSX);
        const sheet = XLSX.utils.aoa_to_sheet([['Price'], [100], [105], [110]]);
        sheet.A3 = invalid === 'missing-cache' ? { t: 'n', f: '100+5' }
            : invalid === 'blank' ? { t: 'z' } : { t: 'n', f: '100+5', v: 105 };
        ui.mode('file');
        await ui.file(file({ Prices: sheet }));
        assert.equal(ui.el('usePricesButton').disabled, invalid !== 'none', invalid);
        if (invalid === 'none') {
            ui.click('usePricesButton');
            ui.click('calculateButton');
            ui.click('saveProjectButton');
            assert.deepEqual(ui.saves[0].parameters.prices, [100, 105, 110]);
        } else assert.equal(ui.el('checkFirst').textContent, '100');
    }
});

test('cancelled or superseded file reads never replace the current preview', async () => {
    const ui = screenHarness('pt');
    ui.mode('file');
    let complete;
    await ui.file({ name: 'old.csv', size: 20, arrayBuffer: () => new Promise(resolve => { complete = resolve; }) });
    await ui.csv('Price\n200\n210\n220');
    complete(new TextEncoder().encode('Price\n100\n105\n110').buffer);
    await new Promise(resolve => setImmediate(resolve));
    ui.click('usePricesButton');
    assert.equal(ui.el('checkFirst').textContent, '200');
    await ui.file({ name: 'cancel.csv', size: 20, arrayBuffer: () => new Promise(resolve => { complete = resolve; }) });
    ui.click('cancelImportButton');
    complete(new TextEncoder().encode('Price\n300\n310\n320').buffer);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.el('importPreview').hidden, true);
    assert.equal(ui.el('checkFirst').textContent, '200');
});

test('a refused replacement file also discards a previous slow read', async () => {
    const ui = screenHarness('pt');
    ui.mode('file');
    let complete;
    await ui.file({ name: 'old.csv', size: 20, arrayBuffer: () => new Promise(resolve => { complete = resolve; }) });
    await ui.file({ name: 'unsupported.xls', size: 20 });
    complete(new TextEncoder().encode('Price\n300\n310\n320').buffer);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.el('importPreview').hidden, true);
    assert.equal(ui.el('importError').hidden, false);
    assert.equal(ui.el('checkFirst').textContent, '100');
});
