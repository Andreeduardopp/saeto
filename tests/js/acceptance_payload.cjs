// Bridge used by Django's integration test: real screen events produce the save payload.
const assert = require('node:assert/strict');
const { screenHarness } = require('./helpers/return_volatility_harness.cjs');
const prices = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832, 26.25157, 26.41698, 27.14673, 26.57266];
(async () => {
    const language = process.argv[2] || 'pt';
    const count = Number(process.argv[3]) || prices.length;
    const series = count === prices.length ? prices : Array.from({ length: count }, (_, i) => 100 + i / 17);
    const ui = screenHarness(language, null, null);
    ui.mode('file');
    await ui.csv('Price\n' + series.join('\n'));
    ui.click('usePricesButton');
    ui.click('calculateButton');
    ui.el('annualizeToggle').checked = true;
    ui.fire('annualizeToggle', 'change');
    ui.click('copyTableButton');
    ui.click('saveProjectButton');
    assert.deepEqual(ui.saves[0].parameters.prices, series);
    const restored = screenHarness(language, ui.saves[0].parameters, ui.captureDraft());
    assert.equal(restored.el('saveProjectButton').disabled, false);
    assert.equal(restored.el('meanContinuous').textContent, ui.el('meanContinuous').textContent);
    process.stdout.write(JSON.stringify({ payload: ui.saves[0], tsv: ui.copies[0],
        mean: ui.el('meanContinuous').textContent, annual: ui.el('annualRate').textContent }));
})().catch(error => { console.error(error); process.exitCode = 1; });
