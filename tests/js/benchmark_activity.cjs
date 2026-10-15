// Local processing benchmark, NOT browser paint/interaction timings.
const { performance } = require('node:perf_hooks');
const os = require('node:os');
const { resolve } = require('node:path');
const { screenHarness } = require('./helpers/return_volatility_harness.cjs');
const XLSX = process.env.SAETO_XLSX_PATH ? require(resolve(process.env.SAETO_XLSX_PATH)) : null;
const percentile95 = samples => [...samples].sort((a, b) => a - b)[Math.ceil(samples.length * .95) - 1];
(async () => {
    const measurements = [];
    for (const count of [249, 300, 1000]) {
        const prices = Array.from({ length: count }, (_, i) => 100 + i / 17);
        const csv = 'Price\n' + prices.join('\n');
        let buffer;
        if (XLSX) {
            const book = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([['Price'], ...prices.map(p => [p])]), 'Prices');
            buffer = XLSX.write(book, { type: 'buffer', bookType: 'xlsx' });
        }
        const times = { csv_preview: [], xlsx_preview: [], calculate: [], annualize: [], page: [], input: [] };
        for (let repeat = -1; repeat < 20; repeat++) {
            const ui = screenHarness('pt', null, null, XLSX);
            const timed = async (key, action) => {
                const start = performance.now();
                await action();
                if (repeat >= 0) times[key].push(performance.now() - start);
            };
            ui.mode('file');
            await timed('csv_preview', () => ui.csv(csv));
            if (buffer) await timed('xlsx_preview', () => ui.file({ name: 'prices.xlsx', size: buffer.length, arrayBuffer: async () => buffer }));
            ui.click('usePricesButton');
            await timed('calculate', () => ui.click('calculateButton'));
            ui.el('annualizeToggle').checked = true;
            ui.fire('annualizeToggle', 'change');
            await timed('annualize', () => ui.type('periodsPerYear', '52'));
            ui.mode('manual');
            await timed('page', () => ui.fire('pricesPager', 'click', { target: { closest: () => ({ dataset: { page: 'next' } }) } }));
            const input = ui.el('price_26');
            await timed('input', () => {
                input.value = '123,456';
                ui.el('inputTable').querySelector('tbody').listeners.input({ target: input });
            });
            ui.dispose();
        }
        measurements.push({ prices: count, repetitions: 20,
            p95_ms: Object.fromEntries(Object.entries(times).filter(([, values]) => values.length)
                .map(([name, values]) => [name, Number(percentile95(values).toFixed(3))])) });
    }
    process.stdout.write(JSON.stringify({ date: '2026-10-14', timezone: 'America/Sao_Paulo',
        runtime: process.version, os: `${os.platform()} ${os.release()} ${os.arch()}`, cpu: os.cpus()[0].model,
        scope: 'Node.js, real screen handlers with simulated DOM and Chart. CSV and XLSX bytes in memory. No network, browser paint, clipboard or assistive technology.',
        reader: XLSX ? XLSX.version : null, measurements }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
