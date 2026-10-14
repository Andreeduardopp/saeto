const assert = require('node:assert/strict');
const test = require('node:test');

const reader = require('../../static/app_teoria/volatility/price_file_reader.js');
const core = require('../../static/app_teoria/volatility/return_volatility_core.js');

const rowsOf = (text, delimiter) => reader.readDelimitedText(text, { delimiter: delimiter }).rows;
const raws = (rows) => rows.map(row => row.map(cell => cell.raw));

test('a single column of prices needs no delimiter', () => {
    const file = '100\n105\n98\n';
    assert.equal(reader.detectDelimiter(file), null);
    const read = reader.readDelimitedText(file);
    assert.deepEqual(raws(read.rows), [['100'], ['105'], ['98']]);
    assert.equal(read.firstLine, 1);
});

test('a decimal comma is not read as a delimiter', () => {
    const file = '26,27103\n26,17373\n26,48509\n';
    assert.equal(reader.detectDelimiter(file), null);
    assert.deepEqual(raws(rowsOf(file)), [['26,27103'], ['26,17373'], ['26,48509']]);
    // and the shared rule still reads each line as one price
    assert.deepEqual(core.parsePrice(rowsOf(file)[0][0].raw), { value: 26.27103 });
});

test('a comma file that reads two ways is reported, not resolved', () => {
    // "1,100" is an index and a price; "26,27103" is one price. Both are valid
    // readings of the same shape, so the screen is told and the user chooses.
    const file = '1,100\n2,105\n3,98\n4,110\n';
    const decimal = reader.readDelimitedText(file);
    assert.equal(decimal.delimiter, null, 'the decimal reading stays the default');
    assert.equal(decimal.ambiguous, true);
    assert.equal(reader.commaIsAmbiguous(file), true);
    // the other reading is one choice away, and it is the two columns of the file
    const columns = reader.readDelimitedText(file, { delimiter: ',' });
    assert.deepEqual(raws(columns.rows)[0], ['1', '100']);
    assert.equal(columns.ambiguous, false, 'a separator the user chose is not a guess');
    // a header above the prices leaves no doubt at all
    assert.equal(reader.readDelimitedText(reader.modelCsv('pt')).ambiguous, false);
    assert.equal(reader.readDelimitedText('100\n105\n98\n').ambiguous, false);
});

test('a used range wider than the data does not become empty rows', () => {
    // A sheet keeps "A1:A1000" after the rows below the data are deleted.
    const sheet = {
        '!ref': 'A1:A1000',
        A1: { t: 'n', v: 100 }, A2: { t: 'n', v: 105 }, A3: { t: 'n', v: 98 },
    };
    const read = reader.readWorksheet(sheet);
    assert.equal(read.rows.length, 3, 'the 997 empty rows are not observations');
    const series = reader.seriesFromEntries(reader.columnEntries(read.rows, { column: 0 }));
    assert.deepEqual(core.validateSeries(series.texts, { min: 3, max: 1000 }).prices,
                     [100, 105, 98]);
});

test('a column is named by the letter it has in the file', () => {
    const sheet = { '!ref': 'C5:C7', C5: { t: 'n', v: 1 }, C6: { t: 'n', v: 2 }, C7: { t: 'n', v: 3 } };
    const read = reader.readWorksheet(sheet);
    const columns = reader.describeColumns(read.rows, false, read.firstColumn);
    assert.equal(columns[0].letter, 'C', 'the same column the addresses quote');
    assert.equal(reader.describeColumns(read.rows, false)[0].letter, 'A', 'no offset, no shift');
});

test('a date cell is quoted as the day it holds, in any time zone', () => {
    // SheetJS builds a local midnight; reading it in UTC quotes the day before
    // east of Greenwich, so the message would point at a date not in the file.
    assert.equal(reader.excelCell({ t: 'd', v: new Date(2026, 9, 1) }).raw, '2026-10-01');
    // the text the sheet shows still wins
    assert.equal(reader.excelCell({ t: 'd', v: new Date(2026, 9, 1), w: '01/10/2026' }).raw,
                 '01/10/2026');
});

test('the Brazilian CSV of semicolons and decimal commas is read', () => {
    const file = 'Data;Preço\r\n01/10/2026;26,27103\r\n02/10/2026;26,17373\r\n';
    assert.equal(reader.detectDelimiter(file), ';');
    const rows = rowsOf(file);
    assert.deepEqual(raws(rows), [['Data', 'Preço'], ['01/10/2026', '26,27103'], ['02/10/2026', '26,17373']]);
    assert.equal(reader.hasHeaderRow(rows), true);
    const columns = reader.describeColumns(rows, true);
    assert.equal(columns[1].name, 'Preço');
    assert.equal(reader.suggestColumn(columns), 1, 'the price column, not the dates');
});

test('the English CSV of commas and decimal dots is read', () => {
    const file = 'Date,Close\n2026-10-01,26.27103\n2026-10-02,26.17373\n';
    assert.equal(reader.detectDelimiter(file), ',');
    const rows = rowsOf(file);
    assert.equal(reader.suggestColumn(reader.describeColumns(rows, true)), 1);
});

test('quoted fields and a BOM survive', () => {
    const file = '﻿"Data";"Preço"\n"01/10/2026";"1.234"\n"02/10/2026";"2,5"\n';
    const rows = rowsOf(file, ';');
    assert.deepEqual(raws(rows)[0], ['Data', 'Preço']);
    assert.deepEqual(raws(rows)[1], ['01/10/2026', '1.234']);
});

test('a quoted field may hold the delimiter itself', () => {
    const rows = rowsOf('"a;b";10\n"c";20\n', ';');
    assert.deepEqual(raws(rows), [['a;b', '10'], ['c', '20']]);
});

test('blank lines outside the block are dropped, the ones inside are kept', () => {
    const read = reader.readDelimitedText('\n\n100\n\n105\n\n\n');
    assert.deepEqual(raws(read.rows), [['100'], [''], ['105']]);
    assert.equal(read.firstLine, 3, 'the first price is on line 3 of the file');
});

test('a file of absurd length is refused instead of truncated', () => {
    const file = Array.from({ length: reader.MAX_ROWS + 1 }, () => '100').join('\n');
    const read = reader.readDelimitedText(file);
    assert.equal(read.code, 'FILE_TOO_MANY_ROWS');
    assert.equal(read.limit, reader.MAX_ROWS);
});

test('a header is only a header when numbers follow it', () => {
    assert.equal(reader.hasHeaderRow(rowsOf('Preço\n100\n105\n')), true);
    assert.equal(reader.hasHeaderRow(rowsOf('100\n105\n98\n')), false);
    assert.equal(reader.hasHeaderRow(rowsOf('100\n')), false);
});

test('a column is suggested only when it is beyond doubt', () => {
    const one = rowsOf('100\n105\n98\n');
    assert.equal(reader.suggestColumn(reader.describeColumns(one, false)), 0);
    // two numeric columns with no names: the screen has to ask
    const two = rowsOf('100;200\n105;210\n98;190\n', ';');
    assert.equal(reader.suggestColumn(reader.describeColumns(two, false)), null);
    // named columns: Fechamento wins over the other numbers
    const named = rowsOf('Abertura;Fechamento;Volume\n10;11;1000\n12;13;2000\n', ';');
    assert.equal(reader.suggestColumn(reader.describeColumns(named, true)), 1);
});

test('column letters follow the spreadsheet', () => {
    assert.equal(reader.columnLetter(0), 'A');
    assert.equal(reader.columnLetter(25), 'Z');
    assert.equal(reader.columnLetter(26), 'AA');
    assert.equal(reader.cellAddress(17, 1), 'B18');
    assert.deepEqual(reader.parseAddress('B18'), { row: 17, column: 1 });
    assert.deepEqual(reader.parseAddress('AA2'), { row: 1, column: 26 });
});

test('a worksheet is read cell by cell, keeping stored values', () => {
    const sheet = {
        '!ref': 'A1:B4',
        A1: { t: 's', v: 'Data' }, B1: { t: 's', v: 'Preço' },
        A2: { t: 'd', v: new Date('2026-10-01'), w: '01/10/2026' }, B2: { t: 'n', v: 26.27103 },
        A3: { t: 'd', v: new Date('2026-10-02'), w: '02/10/2026' }, B3: { t: 'n', v: 26.17373 },
        A4: { t: 'd', v: new Date('2026-10-03'), w: '03/10/2026' }, B4: { t: 'n', v: 26.48509, f: 'C4*1' },
    };
    const read = reader.readWorksheet(sheet);
    assert.equal(read.rows.length, 4);
    assert.equal(read.rows[1][1].kind, 'number');
    assert.equal(read.rows[1][1].raw, '26.27103', 'no rounding on the way in');
    assert.equal(read.rows[1][0].kind, 'date');
    // a formula with a stored result is a number like any other
    assert.equal(read.rows[3][1].number, 26.48509);
    const columns = reader.describeColumns(read.rows, reader.hasHeaderRow(read.rows));
    assert.equal(reader.suggestColumn(columns), 1);
});

test('a stub cell never becomes a price of zero', () => {
    // sheetStubs keeps blank cells as type "z" carrying v = 0.
    const sheet = {
        '!ref': 'A1:A3',
        A1: { t: 'n', v: 10 },
        A2: { t: 'z', v: 0 },
        A3: { t: 'z', v: 0, f: 'A2*2' },
    };
    const rows = reader.readWorksheet(sheet).rows;
    assert.equal(rows[1][0].kind, 'empty');
    assert.equal(rows[1][0].number, null);
    assert.equal(rows[2][0].kind, 'formula', 'a stub holding a formula lost its result');
    const series = reader.seriesFromEntries(reader.columnEntries(rows, { column: 0 }));
    assert.deepEqual(series.issues, [{ index: 2, code: 'CELL_FORMULA_WITHOUT_VALUE' }]);
});

test('a formula with no stored result is reported, not guessed', () => {
    const sheet = {
        '!ref': 'A1:A3',
        A1: { t: 'n', v: 10 },
        A2: { f: 'A1*2' },
        A3: { t: 'n', v: 30 },
    };
    const rows = reader.readWorksheet(sheet).rows;
    assert.equal(rows[1][0].kind, 'formula');
    const entries = reader.columnEntries(rows, { column: 0, firstLine: 1 });
    const series = reader.seriesFromEntries(entries);
    assert.deepEqual(series.issues, [{ index: 1, code: 'CELL_FORMULA_WITHOUT_VALUE' }]);
    assert.equal(entries[1].address, 'A2');
});

test('dates, true/false and error cells are never taken for prices', () => {
    const sheet = {
        '!ref': 'A1:A4',
        A1: { t: 'n', v: 10 },
        A2: { t: 'd', v: new Date('2026-10-01'), w: '01/10/2026' },
        A3: { t: 'b', v: true },
        A4: { t: 'e', v: 7, w: '#DIV/0!' },
    };
    const rows = reader.readWorksheet(sheet).rows;
    const series = reader.seriesFromEntries(reader.columnEntries(rows, { column: 0 }));
    assert.deepEqual(series.issues.map(issue => issue.code),
        ['CELL_IS_DATE', 'CELL_IS_BOOLEAN', 'CELL_IS_ERROR']);
});

test('a sheet that does not start at A1 keeps its real addresses', () => {
    const sheet = { '!ref': 'C5:C7', C5: { t: 'n', v: 1 }, C6: { t: 'n', v: 2 }, C7: { t: 'n', v: 3 } };
    const read = reader.readWorksheet(sheet);
    assert.equal(read.firstLine, 5);
    const entries = reader.columnEntries(read.rows,
        { column: 0, firstLine: read.firstLine, firstColumn: read.firstColumn });
    assert.deepEqual(entries.map(entry => entry.address), ['C5', 'C6', 'C7']);
    assert.deepEqual(entries.map(entry => entry.line), [5, 6, 7]);
});

test('the chosen rows keep the order of the file, and can be reversed on request', () => {
    const rows = rowsOf('Preço\n100\n105\n98\n110\n');
    const entries = reader.columnEntries(rows, { column: 0, hasHeader: true, firstLine: 1 });
    assert.deepEqual(reader.seriesFromEntries(entries).texts, ['100', '105', '98', '110']);
    assert.deepEqual(entries.map(entry => entry.line), [2, 3, 4, 5]);
    const reversed = reader.columnEntries(rows, { column: 0, hasHeader: true, reversed: true });
    assert.deepEqual(reader.seriesFromEntries(reversed).texts, ['110', '98', '105', '100']);
});

test('a range of rows leaves out totals and notes without deleting them', () => {
    const rows = rowsOf('Preço\n100\n105\n98\nTotal\n303\n');
    const entries = reader.columnEntries(rows, { column: 0, hasHeader: true, from: 2, to: 4 });
    assert.deepEqual(reader.seriesFromEntries(entries).texts, ['100', '105', '98']);
});

test('what the file holds is judged by the same rule as a typed price', () => {
    const rows = rowsOf('Preço\n100\n\nabc\n0\n1.234,56\n');
    const entries = reader.columnEntries(rows, { column: 0, hasHeader: true, firstLine: 1 });
    const { texts } = reader.seriesFromEntries(entries);
    const checked = core.validateSeries(texts, { min: 3, max: 1000 });
    assert.deepEqual(checked.rowErrors, [
        { index: 1, code: 'EMPTY' },
        { index: 2, code: 'NOT_A_NUMBER' },
        { index: 3, code: 'NOT_POSITIVE' },
        { index: 4, code: 'AMBIGUOUS_SEPARATOR' },
    ]);
    // every error can be pointed at a line of the file
    assert.deepEqual(checked.rowErrors.map(error => entries[error.index].line), [3, 4, 5, 6]);
});

test('a file is checked before it is read', () => {
    const big = { name: 'serie.csv', size: reader.MAX_FILE_BYTES + 1 };
    assert.equal(reader.inspectFile(big).code, 'FILE_TOO_LARGE');
    assert.equal(reader.inspectFile({ name: 'serie.csv', size: 0 }).code, 'FILE_EMPTY');
    assert.equal(reader.inspectFile({ name: 'serie.csv', size: 10 }).reader, 'csv');
    assert.equal(reader.inspectFile({ name: 'SERIE.TXT', size: 10 }).reader, 'csv');
    assert.equal(reader.inspectFile({ name: 'planilha.xlsx', size: 10 }).reader, 'excel');
    assert.equal(reader.inspectFile({ name: 'antiga.xls', size: 10 }).code, 'FILE_TYPE_REFUSED');
    assert.equal(reader.inspectFile({ name: 'macro.xlsm', size: 10 }).code, 'FILE_TYPE_REFUSED');
    assert.equal(reader.inspectFile({ name: 'foto.png', size: 10 }).code, 'FILE_TYPE_UNKNOWN');
});

test('the model file is a series the tool can calculate', () => {
    const pt = reader.modelCsv('pt');
    assert.equal(pt.split('\r\n')[0], 'Preço');
    assert.ok(pt.includes('26,27103'), 'decimal comma in Portuguese');
    const rows = rowsOf(pt);
    assert.equal(reader.hasHeaderRow(rows), true);
    const entries = reader.columnEntries(rows, { column: 0, hasHeader: true });
    const { texts } = reader.seriesFromEntries(entries);
    const checked = core.validateSeries(texts, { min: 3, max: 1000 });
    assert.equal(checked.valid, true);
    assert.deepEqual(checked.prices, reader.MODEL_PRICES);
    // the handbook numbers come back out of the model
    const run = core.computeReturns(checked.prices);
    assert.ok(Math.abs(run.mean_continuous * 100 - 0.1427007065) < 1e-9);
    assert.ok(Math.abs(run.volatility_continuous * 100 - 1.5484927046) < 1e-9);

    const en = reader.modelCsv('en');
    assert.equal(en.split('\r\n')[0], 'Price');
    assert.ok(en.includes('26.27103'), 'decimal dot in English');
});
