/**
 * Turns a price file into rows of cells, with no DOM and no messages.
 *
 * CSV/TXT is parsed here; `.xlsx` arrives as a SheetJS worksheet and is walked
 * cell by cell, so a number keeps the value the sheet stored and a formula
 * without a saved result is reported instead of guessed. What a cell means as a
 * price is decided by `saetoReturnVolatility.parsePrice`, the same rule the typed
 * table uses; this file only says which cells to look at.
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
        root.saetoPriceFile = api;
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    const MAX_FILE_BYTES = 5 * 1024 * 1024;   // 5 MB
    const MAX_ROWS = 20000;                   // guards against a file of absurd shape
    const MAX_COLUMNS = 64;
    const DELIMITERS = [';', ',', '\t', '|'];
    const SAMPLE_ROWS = 30;                   // enough to tell the shape of a file
    const CSV_EXTENSIONS = ['csv', 'txt'];
    const EXCEL_EXTENSIONS = ['xlsx'];
    // Older or macro-enabled workbooks are not read: the screen asks for .xlsx or CSV.
    const REFUSED_EXTENSIONS = ['xls', 'xlsm', 'xlsb', 'ods'];

    // Header names that name a price column, best first.
    const PRICE_NAMES = [
        /^pre[çc]o/i, /^price/i, /fechamento/i, /\bclose\b/i, /^[úu]ltimo/i, /\blast\b/i,
        /adj.*close/i, /cota[çc][ãa]o/i, /^valor/i, /^value/i,
    ];
    const DATE_LIKE = /^\d{1,4}[\/-]\d{1,2}[\/-]\d{1,4}$/;

    const text = (value) => (value === undefined || value === null ? '' : String(value)).trim();

    // --- Cells -----------------------------------------------------------------
    // kind: empty | text | number | date | boolean | formula | error
    // `raw` is what the screen shows and what gets parsed as a price; `number` is
    // the value a spreadsheet stored, kept at full precision.

    const emptyCell = () => ({ kind: 'empty', raw: '', number: null });

    // A date, written as the sheet shows it. toISOString would read a local
    // midnight in UTC and quote the day before west of Greenwich.
    const localDate = (date) => [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, '0'),
        String(date.getDate()).padStart(2, '0'),
    ].join('-');

    function textCell(value) {
        const raw = text(value);
        return raw === '' ? emptyCell() : { kind: 'text', raw: raw, number: null };
    }

    /** One cell of a SheetJS worksheet: {t, v, f} as that library stores it. */
    function excelCell(cell) {
        if (!cell) {
            return emptyCell();
        }
        // A blank cell read with `sheetStubs` arrives as type "z" carrying v = 0; it
        // holds a formula only when that formula has no stored result. Reading its
        // zero as a price would invent an observation nobody wrote.
        if (cell.t === 'z') {
            return cell.f ? { kind: 'formula', raw: '=' + cell.f, number: null } : emptyCell();
        }
        // A formula that was never recalculated has no stored result to read.
        if (cell.v === undefined || cell.v === null) {
            return cell.f ? { kind: 'formula', raw: '=' + cell.f, number: null } : emptyCell();
        }
        if (cell.t === 'e') {
            return { kind: 'error', raw: String(cell.w || cell.v), number: null };
        }
        if (cell.t === 'b' || typeof cell.v === 'boolean') {
            return { kind: 'boolean', raw: String(cell.v), number: null };
        }
        if (cell.t === 'd' || cell.v instanceof Date) {
            const date = cell.v instanceof Date ? cell.v : new Date(cell.v);
            return { kind: 'date', raw: cell.w || localDate(date), number: null };
        }
        if (cell.t === 'n' || typeof cell.v === 'number') {
            const number = Number(cell.v);
            if (!Number.isFinite(number)) {
                return { kind: 'error', raw: String(cell.v), number: null };
            }
            // String() keeps every digit the sheet stored: 26.27103 stays 26.27103.
            return { kind: 'number', raw: String(number), number: number };
        }
        return textCell(cell.w !== undefined ? cell.w : cell.v);
    }

    // --- A1 addresses ----------------------------------------------------------

    function columnLetter(index) {
        let letter = '';
        let n = Math.max(0, Math.trunc(index));
        do {
            letter = String.fromCharCode(65 + (n % 26)) + letter;
            n = Math.floor(n / 26) - 1;
        } while (n >= 0);
        return letter;
    }

    const cellAddress = (row, column) => `${columnLetter(column)}${row + 1}`;

    function parseAddress(address) {
        const match = /^([A-Z]+)(\d+)$/.exec(String(address).toUpperCase());
        if (!match) {
            return null;
        }
        let column = 0;
        for (const character of match[1]) {
            column = column * 26 + (character.charCodeAt(0) - 64);
        }
        return { row: Number(match[2]) - 1, column: column - 1 };
    }

    // --- CSV -------------------------------------------------------------------

    /**
     * Splits delimited text, honouring quoted fields and both line endings.
     * Returns the rows and the file line the first one came from, so a message can
     * point at the line the user sees in their editor.
     */
    function parseDelimited(content, delimiter, maxRows) {
        // `maxRows` stops the walk early: detection only needs the first rows,
        // and a 5 MB file should be read once, not once per candidate delimiter.
        const limit = maxRows === undefined || maxRows === null ? Infinity : maxRows;
        const source = String(content || '').replace(/^﻿/, '');
        const rows = [];
        let row = [];
        let field = '';
        let quoted = false;
        for (let i = 0; i < source.length && rows.length < limit; i++) {
            const character = source[i];
            if (quoted) {
                if (character === '"') {
                    if (source[i + 1] === '"') {
                        field += '"';
                        i++;
                    } else {
                        quoted = false;
                    }
                } else {
                    field += character;
                }
            } else if (character === '"') {
                quoted = true;
            } else if (delimiter && character === delimiter) {
                row.push(field);
                field = '';
            } else if (character === '\n') {
                row.push(field);
                rows.push(row);
                row = [];
                field = '';
            } else if (character !== '\r') {
                field += character;
            }
        }
        if (rows.length < limit) {
            row.push(field);
            rows.push(row);
        }

        const blank = (cells) => cells.every(cell => text(cell) === '');
        let firstLine = 1;
        // Blank lines around the block are not observations; the ones inside are.
        while (rows.length && blank(rows[rows.length - 1])) {
            rows.pop();
        }
        while (rows.length && blank(rows[0])) {
            rows.shift();
            firstLine++;
        }
        return { rows: rows, firstLine: firstLine };
    }

    const fieldCounts = (content, delimiter) =>
        parseDelimited(content, delimiter, SAMPLE_ROWS).rows.map(row => row.length);

    /**
     * The delimiter of a file, or null when every line holds a single value.
     * A decimal comma is never mistaken for a separator: "26,27" stays one field.
     */
    function detectDelimiter(content) {
        let best = null;
        for (const delimiter of DELIMITERS) {
            const counts = fieldCounts(content, delimiter);
            if (!counts.length || counts[0] < 2) {
                continue;
            }
            const consistent = counts.every(count => count === counts[0]);
            if (!consistent) {
                continue;
            }
            if (delimiter === ',' && commaIsAmbiguous(content)) {
                continue;
            }
            if (!best || counts[0] > best.columns) {
                best = { delimiter: delimiter, columns: counts[0] };
            }
        }
        return best ? best.delimiter : null;
    }

    /**
     * True when a comma file reads two ways and neither is wrong: "26,27103" is
     * one price, "1,100" is an index and a price. Detection keeps the decimal
     * reading — the one the model file uses — and the screen offers the other,
     * because guessing here silently changes every number of the series.
     */
    function commaIsAmbiguous(content) {
        const rows = parseDelimited(content, ',', SAMPLE_ROWS).rows;
        return rows.length > 0 && rows.every(row =>
            row.length === 2 && row.every(cell => /^\d+$/.test(text(cell))));
    }

    /** CSV/TXT text -> cells, ready for the same preview the spreadsheet uses. */
    function readDelimitedText(content, options) {
        const settings = options || {};
        const detected = settings.delimiter === undefined;
        const delimiter = detected ? detectDelimiter(content) : settings.delimiter;
        const parsed = parseDelimited(content, delimiter);
        if (parsed.rows.length > MAX_ROWS) {
            return { code: 'FILE_TOO_MANY_ROWS', rows: parsed.rows.length, limit: MAX_ROWS };
        }
        const rows = parsed.rows.map(row => row.slice(0, MAX_COLUMNS).map(textCell));
        return {
            rows: rows,
            firstLine: parsed.firstLine,
            delimiter: delimiter,
            // The screen says so and offers the other reading; it never picks for
            // the user when both readings produce a valid series.
            ambiguous: detected && delimiter === null && commaIsAmbiguous(content),
        };
    }

    // --- Spreadsheet -----------------------------------------------------------

    /** A SheetJS worksheet -> the same rows of cells, read from A1 down. */
    function readWorksheet(worksheet) {
        const reference = worksheet && worksheet['!ref'];
        if (!reference) {
            return { rows: [], firstLine: 1 };
        }
        const [from, to] = String(reference).split(':');
        const start = parseAddress(from) || { row: 0, column: 0 };
        const end = parseAddress(to || from) || start;
        const height = end.row - start.row + 1;
        if (height > MAX_ROWS) {
            return { code: 'FILE_TOO_MANY_ROWS', rows: height, limit: MAX_ROWS };
        }
        const lastColumn = Math.min(end.column, start.column + MAX_COLUMNS - 1);
        const rows = [];
        for (let row = start.row; row <= end.row; row++) {
            const cells = [];
            for (let column = start.column; column <= lastColumn; column++) {
                cells.push(excelCell(worksheet[cellAddress(row, column)]));
            }
            rows.push(cells);
        }
        // A sheet keeps its used range after rows are deleted, so the tail of an
        // "A1:A1000" reference is often empty: those rows are not observations.
        while (rows.length && rows[rows.length - 1].every(cell => cell.kind === 'empty')) {
            rows.pop();
        }
        // Row 1 of the sheet is line 1 for the user, even when the data starts lower.
        return { rows: rows, firstLine: start.row + 1, firstColumn: start.column };
    }

    // --- Shape of the table ----------------------------------------------------

    const isNumericCell = (cell) => cell.kind === 'number'
        || (cell.kind === 'text' && /^[+-]?(\d+([.,]\d*)?|[.,]\d+)$/.test(cell.raw));

    /** A first row of names above rows of numbers is a header. */
    function hasHeaderRow(rows) {
        if (!rows || rows.length < 2) {
            return false;
        }
        const filled = (row) => row.filter(cell => cell.kind !== 'empty');
        const head = filled(rows[0]);
        if (!head.length || head.some(isNumericCell)) {
            return false;
        }
        return rows.slice(1, 6).some(row => filled(row).some(isNumericCell));
    }

    /** One entry per column: its name, how numeric it is and what it starts with. */
    function describeColumns(rows, hasHeader, firstColumn) {
        // The letter is the one the spreadsheet shows: a sheet whose data starts
        // at C must not offer a column "A" next to addresses like C6.
        const offset = Math.max(0, Math.trunc(firstColumn || 0));
        const body = hasHeader ? rows.slice(1) : rows;
        const width = rows.reduce((widest, row) => Math.max(widest, row.length), 0);
        const columns = [];
        for (let index = 0; index < width; index++) {
            const cells = body.map(row => row[index] || emptyCell());
            const filled = cells.filter(cell => cell.kind !== 'empty');
            columns.push({
                index: index,
                letter: columnLetter(offset + index),
                name: hasHeader ? text(rows[0][index] && rows[0][index].raw) : '',
                filled: filled.length,
                numeric: filled.filter(isNumericCell).length,
                dates: filled.filter(cell => cell.kind === 'date' || DATE_LIKE.test(cell.raw)).length,
                sample: filled.slice(0, 3).map(cell => cell.raw),
            });
        }
        return columns;
    }

    /**
     * The price column when it is beyond doubt: a single usable column, or a header
     * that names one. Anything else returns null and the screen asks.
     */
    function suggestColumn(columns) {
        const usable = columns.filter(column => column.filled > 0);
        if (!usable.length) {
            return null;
        }
        for (const pattern of PRICE_NAMES) {
            const named = usable.filter(column => pattern.test(column.name));
            if (named.length === 1) {
                return named[0].index;
            }
        }
        const numeric = usable.filter(column =>
            column.numeric > 0 && column.numeric >= column.filled - 1 && column.dates < column.numeric);
        return numeric.length === 1 ? numeric[0].index : null;
    }

    // --- Picking the series ----------------------------------------------------

    /**
     * The cells of one column, in the order the file has them, each carrying the
     * line and the A1 address a message can quote.
     */
    function columnEntries(rows, options) {
        const settings = options || {};
        const column = Math.max(0, Math.trunc(settings.column || 0));
        const firstLine = settings.firstLine === undefined ? 1 : settings.firstLine;
        const firstColumn = settings.firstColumn || 0;
        const start = Math.max(settings.hasHeader ? 1 : 0, (settings.from || 1) - 1);
        const end = settings.to === undefined || settings.to === null
            ? rows.length
            : Math.min(rows.length, Math.trunc(settings.to));
        const entries = [];
        for (let index = start; index < end; index++) {
            const cell = (rows[index] || [])[column] || emptyCell();
            entries.push({
                row: index,
                line: firstLine + index,
                address: cellAddress(firstLine - 1 + index, firstColumn + column),
                cell: cell,
            });
        }
        if (settings.reversed) {
            entries.reverse();
        }
        return entries;
    }

    /**
     * Entries -> the texts the shared validation reads, plus the cells it cannot
     * judge on its own (a date, a true/false, a formula with no stored result).
     */
    function seriesFromEntries(entries) {
        const texts = [];
        const issues = [];
        (entries || []).forEach((entry, index) => {
            const kind = entry.cell.kind;
            if (kind === 'date' || kind === 'boolean' || kind === 'formula' || kind === 'error') {
                issues.push({ index: index, code: {
                    date: 'CELL_IS_DATE',
                    boolean: 'CELL_IS_BOOLEAN',
                    formula: 'CELL_FORMULA_WITHOUT_VALUE',
                    error: 'CELL_IS_ERROR',
                }[kind] });
            }
            // A number cell already carries its stored value as text, at full precision.
            texts.push(entry.cell.raw);
        });
        return { texts: texts, issues: issues };
    }

    // --- Files -----------------------------------------------------------------

    const extensionOf = (name) => {
        const parts = String(name || '').toLowerCase().split('.');
        return parts.length > 1 ? parts.pop() : '';
    };

    /** What to do with a chosen file, before any of it is read. */
    function inspectFile(file) {
        const extension = extensionOf(file && file.name);
        if (REFUSED_EXTENSIONS.includes(extension)) {
            return { code: 'FILE_TYPE_REFUSED', extension: extension };
        }
        if (CSV_EXTENSIONS.includes(extension)) {
            return checkSize(file, 'csv');
        }
        if (EXCEL_EXTENSIONS.includes(extension)) {
            return checkSize(file, 'excel');
        }
        return { code: 'FILE_TYPE_UNKNOWN', extension: extension };
    }

    function checkSize(file, reader) {
        if (file && file.size > MAX_FILE_BYTES) {
            return { code: 'FILE_TOO_LARGE', size: file.size, limit: MAX_FILE_BYTES };
        }
        if (file && file.size === 0) {
            return { code: 'FILE_EMPTY' };
        }
        return { reader: reader };
    }

    // --- Model file ------------------------------------------------------------

    // The nine prices of the handbook example, so the model doubles as a series the
    // student can calculate right away.
    const MODEL_PRICES = [26.27103, 26.17373, 26.48509, 26.37806, 26.00832,
                          26.25157, 26.41698, 27.14673, 26.57266];

    /** Single column, header first, decimal separator of the chosen language. */
    function modelCsv(language) {
        const header = language === 'en' ? 'Price' : 'Preço';
        const rows = MODEL_PRICES.map(price =>
            (language === 'en' ? String(price) : String(price).replace('.', ',')));
        return [header].concat(rows).join('\r\n') + '\r\n';
    }

    return {
        MAX_FILE_BYTES,
        MAX_ROWS,
        MAX_COLUMNS,
        CSV_EXTENSIONS,
        EXCEL_EXTENSIONS,
        REFUSED_EXTENSIONS,
        MODEL_PRICES,
        emptyCell,
        textCell,
        excelCell,
        columnLetter,
        cellAddress,
        parseAddress,
        parseDelimited,
        detectDelimiter,
        commaIsAmbiguous,
        readDelimitedText,
        readWorksheet,
        isNumericCell,
        hasHeaderRow,
        describeColumns,
        suggestColumn,
        columnEntries,
        seriesFromEntries,
        extensionOf,
        inspectFile,
        modelCsv,
    };
}));
