const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const core = require('../../static/app_teoria/volatility/return_volatility_core.js');
const fileApi = require('../../static/app_teoria/volatility/price_file_reader.js');

const template = readFileSync(join(__dirname, '../../templates/site/teoria/volatilidade.html'), 'utf8');

const { screenHarness } = require('./helpers/return_volatility_harness.cjs');

test('a recovered draft preserves invalid edits, mode, pagination and the last calculation', () => {
    const ui = screenHarness('pt', null, null);
    ui.mode('paste');
    ui.paste(Array.from({ length: 300 }, (_, index) => String(100 + index)).join('\n'));
    ui.click('usePastedPrices');
    ui.click('calculateButton');
    ui.fire('annualizeToggle', 'change', { target: Object.assign(ui.el('annualizeToggle'), { checked: true }) });
    ui.type('periodsPerYear', 'invalid');
    ui.mode('manual');
    const input = ui.el('price_1');
    input.value = 'wrong';
    ui.el('inputTable').querySelector('tbody').listeners.input({ target: input });
    const data = ui.captureDraft();
    data.page = 4;
    data.returnsPage = 3;
    assert.equal(data.priceTexts[0], 'wrong');
    assert.equal(data.annual.periodsText, 'invalid');
    assert.equal(data.lastPrices.length, 300);
    assert.equal(data.chart, undefined);
    assert.equal(data.results, undefined);
    const recovered = screenHarness('en', null, data);
    assert.equal(recovered.el('staleBanner').hidden, false);
    assert.equal(recovered.el('saveProjectButton').disabled, true);
    assert.equal(recovered.el('periodsPerYear').value, 'invalid');
    assert.equal(recovered.captureDraft().page, 4);
    assert.equal(recovered.captureDraft().returnsPage, 3);
    assert.equal(recovered.captureDraft().priceTexts[0], 'wrong');
    recovered.mode('paste');
    assert.equal(recovered.el('pastedPrices').value, data.paste);
});

test('recovery rebuilds a valid annualized result and keeps an unapplied paste independent', () => {
    const ui = screenHarness('pt', null, null);
    ui.click('calculateButton');
    ui.el('annualizeToggle').checked = true;
    ui.fire('annualizeToggle', 'change');
    ui.mode('paste');
    ui.paste('100\ninvalid\n110');
    const data = ui.captureDraft();
    const recovered = screenHarness('en', null, data);
    assert.equal(recovered.el('saveProjectButton').disabled, false);
    assert.equal(recovered.el('staleBanner').hidden, true);
    assert.equal(recovered.el('pastedPrices').value, '100\ninvalid\n110');
    assert.equal(recovered.el('annualizeToggle').checked, true);
    assert.equal(recovered.el('meanContinuous').textContent, '1.8080%');
    recovered.click('saveProjectButton');
    assert.deepEqual(recovered.saves[0].parameters.prices, [100, 105, 98, 110, 107.5]);
});

test('file draft recovers applied series and identifies a preview that needs reselection', async () => {
    const ui = screenHarness('pt', null, null);
    ui.mode('file');
    await ui.csv('Preço\n26,27103\n26,17373\n26,48509');
    ui.click('usePricesButton');
    ui.click('calculateButton');
    const data = ui.captureDraft();
    assert.ok(data.sourceDetail.includes('prices.csv'));
    assert.equal(data.file, undefined);
    const recovered = screenHarness('pt', null, data);
    assert.equal(recovered.el('checkFirst').textContent, '26,27103');
    assert.equal(recovered.el('saveProjectButton').disabled, false);
    assert.match(recovered.el('importStatus').textContent, /Selecione o arquivo novamente/);
    recovered.dispose();
});

test('three modes preserve the pasted draft, manual edits, count and radio focus', () => {
    const ui = screenHarness();
    ui.type('priceCount', '8');
    const input = ui.el('price_1');
    input.value = '123,456';
    ui.el('inputTable').querySelector('tbody').listeners.input({ target: input });
    ui.mode('paste');
    assert.equal(ui.focused.id, 'dataModePaste');
    ui.paste('100\ninvalid\n110');
    ui.mode('file');
    assert.equal(ui.el('pasteSection').hidden, true);
    assert.equal(ui.el('importSection').hidden, false);
    ui.mode('manual');
    assert.equal(ui.el('priceCount').value, '8');
    assert.equal(ui.el('price_1').value, '123,456');
    ui.mode('paste');
    assert.equal(ui.el('pastedPrices').value, '100\ninvalid\n110');
    assert.equal(ui.el('pasteErrors').hidden, false);
    assert.equal(ui.el('importSection').hidden, true);
    assert.equal(ui.el('manualTable').hidden, true);
});

test('invalid paste cannot replace a calculated series, even before debounce', () => {
    const ui = screenHarness();
    ui.click('calculateButton');
    ui.mode('paste');
    const raw = '\n100\nwrong\n110';
    ui.type('pastedPrices', raw);
    ui.fire('usePastedPrices', 'click'); // exercise validation even for a programmatic click
    assert.equal(ui.el('checkPrices').textContent, 5);
    assert.equal(ui.el('copyTableButton').disabled, false);
    assert.equal(ui.el('staleBanner').hidden, true);
    assert.equal(ui.el('calculateButton').disabled, true);
    assert.equal(ui.focused.id, 'pastedPrices');
    assert.equal(raw.slice(ui.el('pastedPrices').selectionStart, ui.el('pastedPrices').selectionEnd), 'wrong');
    assert.match(ui.el('pasteErrorsList').children[0].textContent, /Linha 3/);
});

test('applying a paste invalidates output; calculate, copy and save use the whole applied series', async () => {
    const ui = screenHarness();
    ui.click('calculateButton');
    ui.mode('paste');
    ui.paste('26,27103\n26,17373\n26,48509');
    assert.equal(ui.el('copyTableButton').disabled, false); // draft is not applied yet
    ui.click('usePastedPrices');
    assert.equal(ui.el('checkPrices').textContent, 3);
    assert.equal(ui.el('copyTableButton').disabled, true);
    assert.equal(ui.el('saveProjectButton').disabled, true);
    assert.equal(ui.el('staleBanner').hidden, false);
    assert.equal(ui.focused.id, 'calculateButton');
    ui.click('calculateButton');
    ui.click('saveProjectButton');
    ui.click('copyTableButton');
    assert.deepEqual(ui.saves[0].parameters.prices, [26.27103, 26.17373, 26.48509]);
    assert.equal(ui.saves[0].parameters.periods, 3);
    assert.equal(ui.saves[0].results.continuous_returns.length, 2);
    assert.match(ui.copies[0], /26,27103/);
    await Promise.resolve();
});

test('undo restores the previous series and pending manual count without deleting the paste', () => {
    const ui = screenHarness();
    ui.type('priceCount', '9');
    ui.mode('paste');
    ui.paste('200\n210\n220');
    ui.click('usePastedPrices');
    ui.click('undoButton');
    assert.equal(ui.el('checkFirst').textContent, '100');
    assert.equal(ui.el('priceCount').value, '9');
    assert.equal(ui.el('pastedPrices').value, '200\n210\n220');
    assert.equal(ui.el('usePastedPrices').disabled, false);
    assert.equal(ui.focused.id, 'pastedPrices');
    ui.mode('manual');
    assert.equal(ui.el('calculateButton').disabled, true);
});

test('file preview survives visiting paste and never applies itself', async () => {
    const ui = screenHarness();
    ui.mode('file');
    await ui.csv('Preço\n200\n210\n220');
    assert.equal(ui.el('importPreview').hidden, false);
    ui.mode('paste');
    ui.paste('100\nbad\n110');
    ui.mode('file');
    assert.equal(ui.el('importPreview').hidden, false);
    assert.equal(ui.el('checkFirst').textContent, '100');
    ui.click('usePricesButton');
    assert.equal(ui.el('checkFirst').textContent, '200');
    ui.click('calculateButton');
    ui.mode('paste');
    assert.equal(ui.el('pastedPrices').value, '100\nbad\n110');
    assert.equal(ui.el('checkFirst').textContent, '200');
});

test('a long paste is paginated but all observations are saved; oversized blocks are refused', () => {
    const ui = screenHarness();
    ui.mode('paste');
    ui.paste(Array(1000).fill('26,27103').join('\n'));
    ui.click('usePastedPrices');
    ui.click('calculateButton');
    ui.click('saveProjectButton');
    assert.equal(ui.saves[0].parameters.prices.length, 1000);
    assert.equal(ui.saves[0].results.discrete_returns.length, 999);
    ui.mode('manual');
    assert.equal(ui.el('inputTable').querySelector('tbody').children.length, 25);
    ui.mode('paste');
    ui.paste(Array(1001).fill('100').join('\n'));
    assert.equal(ui.el('usePastedPrices').disabled, true);
    assert.equal(ui.el('checkPrices').textContent, 1000);
});

test('English paste messages and error locations use the session language', () => {
    const ui = screenHarness('en');
    ui.mode('paste');
    ui.paste('100\n0\n110');
    assert.match(ui.el('pasteStatus').textContent, /Fix the pasted prices/);
    assert.match(ui.el('pasteErrorsList').children[0].textContent, /Row 2:.*greater than zero/);
});

test('30/31 only changes the manual import suggestion, never the mode or a pasted series', () => {
    const ui = screenHarness();
    ui.type('priceCount', '30');
    assert.equal(ui.el('manualImportSuggestion').hidden, true);
    ui.type('priceCount', '31');
    assert.equal(ui.el('manualImportSuggestion').hidden, false);
    assert.equal(ui.el('dataModeManual').checked, true);
    ui.click('suggestImportButton');
    assert.equal(ui.el('dataModeFile').checked, true);
    assert.equal(ui.focused.id, 'priceFileInput');
    assert.equal(ui.el('priceCount').value, '31');
    ui.mode('paste');
    ui.paste(Array(31).fill('100').join('\n'));
    ui.click('usePastedPrices');
    ui.mode('manual');
    assert.equal(ui.el('manualImportSuggestion').hidden, true);
    const input = ui.el('price_1');
    input.value = '101';
    ui.el('inputTable').querySelector('tbody').listeners.input({ target: input });
    ui.type('priceCount', '32');
    assert.equal(ui.el('manualImportSuggestion').hidden, true);
    ui.click('undoButton');
    assert.equal(ui.el('manualImportSuggestion').hidden, false);
});

const HANDBOOK = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832,
                  26.25157, 26.41698, 27.14673, 26.57266];

/** The nine prices of the handbook, applied from a pasted column. */
function calculatedHandbook(language = 'pt') {
    const ui = screenHarness(language);
    const separator = language === 'en' ? '.' : ',';
    ui.mode('paste');
    ui.paste(HANDBOOK.map(price => String(price).replace('.', separator)).join('\n'));
    ui.click('usePastedPrices');
    ui.click('calculateButton');
    return ui;
}

/** The copied spreadsheet, one array of cells per line. */
const copiedRows = (text) => text.split('\r\n').map(line => line.split('\t'));

test('the summary, the table and the chart show four percentage decimals with a comma', () => {
    const ui = calculatedHandbook();
    assert.equal(ui.el('meanDiscrete').textContent, '0,1533%');
    assert.equal(ui.el('meanContinuous').textContent, '0,1427%');
    assert.equal(ui.el('volatilityDiscrete').textContent, '1,5523%');
    assert.equal(ui.el('volatilityContinuous').textContent, '1,5485%');
    const first = ui.el('resultsTable').children[0];
    assert.deepEqual(first.children.map(cell => cell.textContent),
        ['1 → 2', '-0,3704%', '-0,3711%']);
    // The tip of the chart repeats the number of the table, not a rounded point.
    const tooltip = ui.chart.options.plugins.tooltip.callbacks;
    assert.equal(tooltip.label({ dataset: { label: 'Retorno Contínuo' }, datasetIndex: 1, dataIndex: 0 }),
        'Retorno Contínuo: -0,3711%');
    // The axis keeps two decimals, with the separator of the language.
    assert.equal(ui.chart.options.scales.y.ticks.callback(-0.375), '-0,38%');
});

test('N, n and the sample divisor are stated next to the summary', () => {
    const ui = calculatedHandbook();
    assert.equal(ui.el('resultsMeta').textContent,
        'N = 9 preços · n = N − 1 = 8 retornos · unidade: por período');
    // Nine prices, eight returns, sum of squares divided by 7.
    assert.match(ui.el('statsNote').textContent, /n − 1 = N − 2 = 7/);
    assert.match(ui.el('statsNote').textContent, /por período, sem anualização/);
});

test('the copy to Excel repeats the screen and keeps the precision of the prices', () => {
    const ui = calculatedHandbook();
    ui.click('copyTableButton');
    const rows = copiedRows(ui.copies[0]);
    assert.deepEqual(rows[1], ['1', '26,27103', '', '']);
    assert.deepEqual(rows[2], ['2', '26,17373', '-0,3704%', '-0,3711%']);
    // The last two lines are the two measures of the summary, in the same text.
    assert.deepEqual(rows[rows.length - 2], ['Retorno médio', '', '0,1533%', '0,1427%']);
    assert.deepEqual(rows[rows.length - 1], ['Volatilidade', '', '1,5523%', '1,5485%']);
    // What is saved stays unrounded: the display never reaches the stored numbers.
    ui.click('saveProjectButton');
    assert.deepEqual(ui.saves[0].parameters.prices, HANDBOOK);
    assert.equal(ui.saves[0].results.volatility_continuous.toFixed(10), '0.0154849270');
});

test('English shows the same numbers with a dot, in the summary and in the copy', () => {
    const ui = calculatedHandbook('en');
    assert.equal(ui.el('volatilityContinuous').textContent, '1.5485%');
    assert.equal(ui.el('meanContinuous').textContent, '0.1427%');
    assert.equal(ui.el('resultsMeta').textContent,
        'N = 9 prices · n = N − 1 = 8 returns · unit: per period');
    assert.match(ui.el('statsNote').textContent, /n − 1 = N − 2 = 7/);
    const rows = (ui.click('copyTableButton'), copiedRows(ui.copies[0]));
    assert.deepEqual(rows[1], ['1', '26.27103', '', '']);
    assert.deepEqual(rows[rows.length - 1], ['Volatility', '', '1.5523%', '1.5485%']);
});

// --- Optional annualization (plan §6) ---------------------------------------

/** Switches the option on, as the checkbox does. */
function annualizeOn(ui) {
    ui.el('annualizeToggle').checked = true;
    ui.fire('annualizeToggle', 'change');
}

test('annualizing is off until asked for, and then only the annual block is added', () => {
    const ui = calculatedHandbook();
    assert.equal(ui.el('annualizeToggle').checked, false);
    assert.equal(ui.el('annualFields').hidden, true);
    assert.equal(ui.el('annualBlock').hidden, true);
    assert.match(ui.el('statsNote').textContent, /por período, sem anualização/);

    annualizeOn(ui);
    assert.equal(ui.el('annualFields').hidden, false);
    assert.equal(ui.el('annualBlock').hidden, false);
    // Daily is suggested with m = 252, written into the field so it can be edited.
    assert.equal(ui.el('annualFrequency').value, 'daily');
    assert.equal(ui.el('periodsPerYear').value, '252');
    assert.equal(ui.el('annualRate').textContent, '43,2764%');
    assert.equal(ui.el('annualVolatility').textContent, '24,5816%');
    assert.equal(ui.el('annualMeta').textContent,
        'm = 252 períodos por ano · frequência: diária · unidade: anual');
    // The per-period results are the same ones, and no recalculation was needed.
    assert.equal(ui.el('volatilityContinuous').textContent, '1,5485%');
    assert.equal(ui.el('resultsMeta').textContent,
        'N = 9 preços · n = N − 1 = 8 retornos · unidade: por período');
    assert.equal(ui.el('staleBanner').hidden, true);
    assert.equal(ui.el('calculateButton').textContent, 'Recalcular');
    assert.equal(ui.el('copyTableButton').disabled, false);
    assert.equal(ui.el('saveProjectButton').disabled, false);
    assert.match(ui.el('statsNote').textContent, /a anualização aparece no bloco anual/);
});

test('each frequency suggests its m, and editing m updates only the annual block', () => {
    const ui = calculatedHandbook();
    annualizeOn(ui);
    for (const [frequency, periods] of [['weekly', '52'], ['monthly', '12'], ['daily', '252']]) {
        ui.el('annualFrequency').value = frequency;
        ui.fire('annualFrequency', 'change');
        assert.equal(ui.el('periodsPerYear').value, periods);
        assert.notEqual(ui.el('annualRate').textContent, '—');
        assert.match(ui.el('annualMeta').textContent, new RegExp(`m = ${periods} períodos`));
    }
    // A custom frequency keeps the m in the field and asks the user to write it.
    ui.el('annualFrequency').value = 'custom';
    ui.fire('annualFrequency', 'change');
    assert.equal(ui.el('periodsPerYear').value, '252');
    assert.equal(ui.focused.id, 'periodsPerYear');
    ui.type('periodsPerYear', '52');
    assert.equal(ui.el('annualMeta').textContent,
        'm = 52 períodos por ano · frequência: personalizada · unidade: anual');
    assert.equal(ui.el('annualVolatility').textContent, '11,1663%');
    // Only the annual block moved: the series was never recalculated.
    assert.equal(ui.el('volatilityContinuous').textContent, '1,5485%');
    assert.equal(ui.el('staleBanner').hidden, true);
    assert.equal(ui.el('saveProjectButton').disabled, false);
});

test('an invalid m marks the annual block pending and holds back copy and save', () => {
    const ui = calculatedHandbook();
    annualizeOn(ui);
    for (const [value, message] of [['', /Informe os períodos por ano/],
                                    ['0', /entre 1 e 100000/],
                                    ['2,5', /número inteiro/]]) {
        ui.type('periodsPerYear', value);
        // While typing, the block is pending but the field says nothing yet.
        assert.equal(ui.el('annualPending').hidden, false);
        assert.equal(ui.el('periodsError').hidden, true);
        assert.equal(ui.el('annualRate').textContent, '—');
        assert.equal(ui.el('annualVolatility').textContent, '—');
        // The per-period summary is untouched and still valid.
        assert.equal(ui.el('volatilityContinuous').textContent, '1,5485%');
        assert.equal(ui.el('resultsMeta').textContent,
            'N = 9 preços · n = N − 1 = 8 retornos · unidade: por período');
        assert.equal(ui.el('copyTableButton').disabled, true);
        assert.equal(ui.el('saveProjectButton').disabled, true);
        assert.match(ui.el('outputHint').textContent, /Corrija os períodos por ano/);
        // Confirming the field is what shows its message.
        ui.fire('periodsPerYear', 'change');
        assert.equal(ui.el('periodsError').hidden, false);
        assert.match(ui.el('periodsError').textContent, message);
        assert.equal(ui.el('periodsPerYear').attributes['aria-invalid'], 'true');
        // A click that reaches the handler anyway sends nothing and points at m.
        ui.fire('saveProjectButton', 'click');
        ui.fire('copyTableButton', 'click');
        assert.deepEqual(ui.saves, []);
        assert.deepEqual(ui.copies, []);
        assert.equal(ui.focused.id, 'periodsPerYear');
    }
    ui.type('periodsPerYear', '252');
    assert.equal(ui.el('annualPending').hidden, true);
    assert.equal(ui.el('periodsError').hidden, true);
    assert.equal(ui.el('annualRate').textContent, '43,2764%');
    assert.equal(ui.el('saveProjectButton').disabled, false);
    assert.equal(ui.el('outputHint').hidden, true);
});

test('switching the option off leaves the per-period results and comes back to the last m', () => {
    const ui = calculatedHandbook();
    annualizeOn(ui);
    ui.el('annualFrequency').value = 'monthly';
    ui.fire('annualFrequency', 'change');
    ui.type('periodsPerYear', '13');
    const monthlyRate = ui.el('annualRate').textContent;
    assert.notEqual(monthlyRate, '—');

    ui.el('annualizeToggle').checked = false;
    ui.fire('annualizeToggle', 'change');
    assert.equal(ui.el('annualFields').hidden, true);
    assert.equal(ui.el('annualBlock').hidden, true);
    assert.match(ui.el('statsNote').textContent, /por período, sem anualização/);
    ui.click('saveProjectButton');
    assert.equal('periodsPerYear' in ui.saves[0].parameters, false);
    assert.equal('frequency' in ui.saves[0].parameters, false);
    assert.equal('annual_rate_equivalent' in ui.saves[0].results, false);

    // Back on: the last valid configuration of this analysis, not the default.
    annualizeOn(ui);
    assert.equal(ui.el('annualFrequency').value, 'monthly');
    assert.equal(ui.el('periodsPerYear').value, '13');
    assert.equal(ui.el('annualRate').textContent, monthlyRate);
});

test('the annualized run is what gets saved and copied, in either language', () => {
    const ui = calculatedHandbook();
    annualizeOn(ui);
    ui.click('saveProjectButton');
    const save = ui.saves[0];
    assert.equal(save.parameters.periodsPerYear, 252);
    assert.equal(save.parameters.frequency, 'daily');
    assert.deepEqual(save.parameters.prices, HANDBOOK);
    // Saved unrounded, like every other number of the run.
    assert.equal(save.results.annual_rate_equivalent.toFixed(10), '0.4327644793');
    assert.equal(save.results.annual_volatility_continuous.toFixed(10), '0.2458155962');

    ui.click('copyTableButton');
    const rows = copiedRows(ui.copies[0]);
    assert.deepEqual(rows[rows.length - 3], ['Períodos por ano (m)', '', '', '252']);
    assert.deepEqual(rows[rows.length - 2], ['Taxa anual equivalente', '', '', '43,2764%']);
    assert.deepEqual(rows[rows.length - 1], ['Volatilidade anual', '', '', '24,5816%']);

    const en = calculatedHandbook('en');
    annualizeOn(en);
    assert.equal(en.el('annualRate').textContent, '43.2764%');
    assert.equal(en.el('annualMeta').textContent,
        'm = 252 periods per year · frequency: daily · unit: annual');
    en.click('copyTableButton');
    const copied = copiedRows(en.copies[0]);
    assert.deepEqual(copied[copied.length - 1], ['Annual volatility', '', '', '24.5816%']);
    en.type('periodsPerYear', '0');
    assert.match(en.el('outputHint').textContent, /Fix the periods per year/);
    en.fire('periodsPerYear', 'change');
    assert.match(en.el('periodsError').textContent, /between 1 and 100000/);
});

test('annualizing before calculating, and a new series, keep the block honest', () => {
    const ui = screenHarness();
    annualizeOn(ui);
    // Nothing is annualized before there is a run, and the option does not block it.
    assert.equal(ui.el('annualBlock').hidden, true);
    assert.equal(ui.el('annualFields').hidden, false);
    assert.equal(ui.el('calculateButton').disabled, false);
    ui.click('calculateButton');
    assert.equal(ui.el('annualBlock').hidden, false);
    const exampleRate = ui.el('annualRate').textContent;
    assert.notEqual(exampleRate, '—');

    // A different series: the annual block follows the run it belongs to.
    ui.mode('paste');
    ui.paste(HANDBOOK.map(price => String(price).replace('.', ',')).join('\n'));
    ui.click('usePastedPrices');
    assert.equal(ui.el('staleBanner').hidden, false);
    assert.equal(ui.el('saveProjectButton').disabled, true);
    ui.click('calculateButton');
    assert.equal(ui.el('annualRate').textContent, '43,2764%');
    assert.notEqual(ui.el('annualRate').textContent, exampleRate);
});

test('a project saved with an annualization opens with it, and one without it does not', () => {
    const saved = { periods: 3, prices: [10, 12.5, 11], frequency: 'weekly', periodsPerYear: 52 };
    const ui = screenHarness('pt', saved);
    assert.equal(ui.el('annualizeToggle').checked, true);
    assert.equal(ui.el('annualFields').hidden, false);
    assert.equal(ui.el('annualFrequency').value, 'weekly');
    assert.equal(ui.el('periodsPerYear').value, '52');
    // Nothing is annualized before this project is calculated again.
    assert.equal(ui.el('annualBlock').hidden, true);
    ui.click('calculateButton');
    assert.equal(ui.el('annualBlock').hidden, false);
    assert.match(ui.el('annualMeta').textContent, /m = 52 períodos por ano · frequência: semanal/);
    ui.click('saveProjectButton');
    assert.equal(ui.saves[0].parameters.periodsPerYear, 52);
    assert.equal(ui.saves[0].parameters.frequency, 'weekly');

    // A project saved before the option existed opens with it switched off.
    const old = screenHarness('pt', { periods: 3, prices: [10, 12.5, 11] });
    assert.equal(old.el('annualizeToggle').checked, false);
    assert.equal(old.el('annualFields').hidden, true);
    old.click('calculateButton');
    old.click('saveProjectButton');
    assert.equal('periodsPerYear' in old.saves[0].parameters, false);

    // An m with a frequency the screen does not offer is shown as a custom one.
    const odd = screenHarness('pt', { periods: 3, prices: [10, 12.5, 11], frequency: 'hourly', periodsPerYear: 7 });
    assert.equal(odd.el('annualFrequency').value, 'custom');
    assert.equal(odd.el('periodsPerYear').value, '7');
});

test('an annualization that leaves the representable range says so instead of showing it', () => {
    const ui = screenHarness();
    ui.mode('paste');
    ui.paste(['1', '1000000', '1000000'].join('\n'));
    ui.click('usePastedPrices');
    ui.click('calculateButton');
    annualizeOn(ui);
    ui.type('periodsPerYear', '100000');
    assert.equal(ui.el('annualRate').textContent, '—');
    assert.equal(ui.el('annualVolatility').textContent, '—');
    assert.match(ui.el('annualPending').textContent, /não produz um número representável/);
    assert.equal(ui.el('copyTableButton').disabled, true);
    assert.equal(ui.el('saveProjectButton').disabled, true);
    // The per-period results of this series are still there and still valid.
    assert.notEqual(ui.el('volatilityContinuous').textContent, '—');
    ui.type('periodsPerYear', '1');
    assert.notEqual(ui.el('annualRate').textContent, '—');
    assert.equal(ui.el('annualPending').hidden, true);
    assert.equal(ui.el('saveProjectButton').disabled, false);
});

test('a return of 0.001742 is shown as 0,1742% and the first price has no return', () => {
    const ui = screenHarness();
    ui.mode('paste');
    // 1,001742 / 1 − 1 is exactly 0.001742 as a discrete return.
    ui.paste(['1', '1,001742', '1'].join('\n'));
    ui.click('usePastedPrices');
    ui.click('calculateButton');
    assert.equal(ui.el('resultsTable').children[0].children[1].textContent, '0,1742%');
    assert.equal(ui.el('resultsTable').children.length, 2);   // n = N − 1
    ui.click('copyTableButton');
    const rows = copiedRows(ui.copies[0]);
    assert.deepEqual(rows[1], ['1', '1', '', '']);
    assert.equal(rows[2][2], '0,1742%');
});
