const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const template = readFileSync(
    join(__dirname, '../../templates/site/teoria_dos_jogos/dilema_prisioneiro.html'), 'utf8');

// Exercise the actual screen handlers with a small DOM double. This checks state,
// paging and discarded answers, not browser layout.
function screenHarness(language = 'pt', pageSize = 50) {
    const nodes = new Map(), requests = [];
    class Element {
        constructor(id = '', tag = '') {
            this.tag = tag;
            this.children = [];
            this.listeners = {};
            this.dataset = {};
            this.style = {};
            this.value = '';
            this.textContent = '';
            this.hidden = false;
            this.disabled = false;
            this.id = id;
        }
        set id(value) { this._id = value; if (value) nodes.set(value, this); }
        get id() { return this._id; }
        addEventListener(name, handler) { this.listeners[name] = handler; }
        appendChild(child) { this.children.push(child); return child; }
        replaceChildren(...children) { this.children = children; }
        querySelector() { return { value: 'token' }; }
    }
    for (const match of template.matchAll(/\bid="([\w-]+)"/g)) new Element(match[1]);
    const el = id => {
        assert.ok(nodes.has(id), `Missing element: ${id}`);
        return nodes.get(id);
    };
    el('dilema-form').dataset.action = '/teoria-dos-jogos/dilema-do-prisioneiro/';
    const logged = [];
    const context = {
        // The screen logs the cause of a failed request; a test reads it here
        // instead of printing it over the results of the run.
        console: { ...console, error: (...args) => logged.push(args) },
        document: { getElementById: id => nodes.get(id) || null, createElement: tag => new Element('', tag) },
        window: {},
        FormData: class { constructor(form) { this.form = form; } },
        AbortController: class {
            constructor() { this.aborted = false; this.signal = { controller: this }; }
            abort() { this.aborted = true; }
        },
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject })),
    };
    let cleanup = () => {};
    context.window.saetoLifecycle = { register(callback) { cleanup = callback; } };

    const script = template.split('<script>')[1].split('</script>')[0]
        .replace('{{ language }}', language)
        .replace('{{ history_page_size }}', String(pageSize));
    vm.runInNewContext(script, context, { filename: 'dilema_prisioneiro.html' });

    const rows = () => el('historyBody').children.map(row => row.children.map(cell => cell.textContent));
    return {
        el, rows, requests,
        submit: () => el('dilema-form').listeners.submit({ preventDefault() {} }),
        click: id => { assert.equal(el(id).disabled, false, `${id} is disabled`); el(id).listeners.click(); },
        leave: () => cleanup(),
        answer(request, body, ok = true) {
            request.resolve({ ok, json: async () => body });
        },
        get error() { return el('dilemaError').textContent; },
        get logged() { return logged; },
        get visible() { return el('simulation-results').style.display === 'block'; },
    };
}

/** A game of `rounds` rounds where player 1 always cooperates and player 2 always defects. */
function game(rounds) {
    return {
        result: {
            history1: Array.from({ length: rounds }, () => 'cooperate'),
            history2: Array.from({ length: rounds }, () => 'defect'),
            payoff1: 0,
            payoff2: 5 * rounds,
        },
    };
}

test('a run shows the scores and the first page of rounds', async () => {
    const ui = screenHarness();
    const running = ui.submit();
    assert.equal(ui.el('dilemaSubmit').disabled, true);
    assert.equal(ui.el('dilemaSubmit').textContent, 'Simulando...');
    ui.answer(ui.requests[0], game(3));
    await running;

    assert.equal(ui.visible, true);
    assert.equal(ui.el('player1Score').textContent, 0);
    assert.equal(ui.el('player2Score').textContent, 15);
    assert.deepEqual(ui.rows(), [
        ['1', 'Cooperar', 'Trair'], ['2', 'Cooperar', 'Trair'], ['3', 'Cooperar', 'Trair'],
    ]);
    assert.equal(ui.el('historyRange').textContent, 'Rodadas 1 a 3 de 3.');
    assert.equal(ui.el('historyPager').hidden, true);
    assert.equal(ui.el('dilemaSubmit').disabled, false);
    assert.equal(ui.el('dilemaSubmit').textContent, 'Simular');
});

test('the moves and the paging follow the language of the session', async () => {
    const ui = screenHarness('en');
    const running = ui.submit();
    ui.answer(ui.requests[0], game(2));
    await running;
    assert.deepEqual(ui.rows(), [['1', 'Cooperate', 'Defect'], ['2', 'Cooperate', 'Defect']]);
    assert.equal(ui.el('historyRange').textContent, 'Rounds 1 to 2 of 2.');
});

test('a long game is read one page at a time, never rendered whole', async () => {
    const ui = screenHarness();
    const running = ui.submit();
    ui.answer(ui.requests[0], game(120));
    await running;

    assert.equal(ui.rows().length, 50);
    assert.equal(ui.el('historyPage').textContent, 'Página 1 de 3');
    assert.equal(ui.el('historyPager').hidden, false);
    assert.equal(ui.el('historyPrevious').disabled, true);

    ui.click('historyNext');
    assert.equal(ui.rows()[0][0], '51');
    assert.equal(ui.rows().length, 50);
    assert.equal(ui.el('historyPrevious').disabled, false);

    ui.click('historyNext');
    assert.equal(ui.rows().length, 20);
    assert.equal(ui.el('historyRange').textContent, 'Rodadas 101 a 120 de 120.');
    assert.equal(ui.el('historyNext').disabled, true);

    ui.click('historyPrevious');
    assert.equal(ui.rows()[0][0], '51');
});

test('a new run starts the history at its first page', async () => {
    const ui = screenHarness();
    let running = ui.submit();
    ui.answer(ui.requests[0], game(120));
    await running;
    ui.click('historyNext');
    assert.equal(ui.rows()[0][0], '51');

    running = ui.submit();
    ui.answer(ui.requests[1], game(120));
    await running;
    assert.equal(ui.rows()[0][0], '1');
    assert.equal(ui.el('historyPage').textContent, 'Página 1 de 3');
});

test('a refused run shows the message of the server and no results', async () => {
    const ui = screenHarness();
    const running = ui.submit();
    ui.answer(ui.requests[0], { error: 'Iterações deve estar entre 1 e 1.000.' }, false);
    await running;
    assert.equal(ui.error, 'Iterações deve estar entre 1 e 1.000.');
    assert.equal(ui.visible, false);
    assert.equal(ui.rows().length, 0);
    assert.equal(ui.el('dilemaSubmit').disabled, false);
});

test('a failed request says so in the session language and frees the button', async () => {
    const ui = screenHarness();
    const running = ui.submit();
    ui.requests[0].reject(new Error('network down'));
    await running;
    assert.match(ui.error, /^Não foi possível falar com o servidor/);
    assert.equal(ui.logged.length, 1);
    assert.equal(ui.visible, false);
    assert.equal(ui.el('dilemaSubmit').disabled, false);
});

test('the answer of a previous click never lands on the current run', async () => {
    const ui = screenHarness();
    const first = ui.submit();
    const second = ui.submit();
    assert.equal(ui.requests[0].options.signal.controller.aborted, true);

    ui.answer(ui.requests[1], game(2));
    await second;
    ui.answer(ui.requests[0], game(99));
    await first;

    assert.equal(ui.rows().length, 2);
    assert.equal(ui.el('historyRange').textContent, 'Rodadas 1 a 2 de 2.');
});

test('a late error from a previous click does not replace the current results', async () => {
    const ui = screenHarness();
    const first = ui.submit();
    const second = ui.submit();
    ui.answer(ui.requests[1], game(2));
    await second;

    ui.answer(ui.requests[0], { error: 'Iterações deve estar entre 1 e 1.000.' }, false);
    await first;
    assert.equal(ui.error, '');
    assert.equal(ui.visible, true);
    assert.equal(ui.rows().length, 2);
});

test('leaving the screen drops an answer that is still on its way', async () => {
    const ui = screenHarness();
    const running = ui.submit();
    ui.leave();
    assert.equal(ui.requests[0].options.signal.controller.aborted, true);

    ui.answer(ui.requests[0], game(5));
    await running;
    assert.equal(ui.visible, false);
    assert.equal(ui.rows().length, 0);
});

test('every click sends one request to the url of the form', async () => {
    const ui = screenHarness();
    const running = ui.submit();
    ui.answer(ui.requests[0], game(1));
    await running;
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.requests[0].url, '/teoria-dos-jogos/dilema-do-prisioneiro/');
    assert.equal(ui.requests[0].options.method, 'POST');
    assert.equal(ui.requests[0].options.headers['X-CSRFToken'], 'token');
});
