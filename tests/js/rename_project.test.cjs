const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const template = readFileSync(join(__dirname, '../../templates/site/home/simulation_list.html'), 'utf8');
const source = template.match(/<script>([\s\S]*?)<\/script>/)[1];

function classes(...names) {
    const values = new Set(names);
    return { add: name => values.add(name), remove: name => values.delete(name), contains: name => values.has(name) };
}

function harness() {
    const listeners = {}, requests = [], alerts = [];
    const container = { addEventListener: (event, handler) => { listeners[event] = handler; } };
    const nameSpan = {
        textContent: 'Nome original', dataset: { id: 'project-1' }, classList: classes(),
        closest: selector => selector === '.simulation-name' ? nameSpan : null,
    };
    const renameButton = {
        disabled: false, classList: classes(),
        closest: selector => selector === '.rename-btn' ? renameButton : null,
    };
    const input = {
        tagName: 'INPUT', value: 'Nome original', disabled: false,
        classList: classes('form-control', 'd-none'),
        focus() { this.focused = true; }, select() {},
        blur() { this.pendingBlur = listeners.focusout({ target: this }); },
    };
    const td = { querySelector: selector => ({ input, '.simulation-name': nameSpan, '.rename-btn': renameButton })[selector] };
    for (const element of [input, nameSpan, renameButton]) element.parentElement = td;
    const context = {
        document: { cookie: 'csrftoken=test-token', getElementById: () => container },
        console: { log() {}, error() {} },
        alert: text => alerts.push(text),
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({
            url, ...options, body: JSON.parse(options.body), resolve, reject,
        })),
    };
    vm.runInNewContext(source, context);
    return { input, nameSpan, renameButton, requests, alerts,
        open: () => listeners.click({ target: renameButton }),
        doubleClick: () => listeners.dblclick({ target: nameSpan }),
        finish: () => listeners.focusout({ target: input }),
        key: key => listeners.keydown({ target: input, key, preventDefault() {} }),
    };
}

test('Rename and Enter persist the name returned by the server', async () => {
    const ui = harness();
    await ui.open();
    assert.equal(ui.input.focused, true);
    assert.equal(ui.nameSpan.classList.contains('d-none'), true);
    ui.input.value = '  Cenário revisado  ';
    ui.key('Enter');
    assert.equal(ui.input.disabled, true);
    assert.deepEqual(ui.requests[0].body, { id: 'project-1', name: 'Cenário revisado' });
    assert.equal(ui.requests[0].headers['X-CSRFToken'], 'test-token');
    await ui.finish(); // A second blur while saving must not duplicate the request.
    await ui.open();
    assert.equal(ui.requests.length, 1);
    ui.requests[0].resolve({ ok: true, json: async () => ({ status: 'success', name: 'Nome confirmado' }) });
    await ui.input.pendingBlur;
    assert.equal(ui.nameSpan.textContent, 'Nome confirmado');
    assert.equal(ui.input.value, 'Nome confirmado');
    assert.equal(ui.renameButton.disabled, false);
    assert.equal(ui.renameButton.classList.contains('d-none'), false);
    assert.equal(ui.input.classList.contains('d-none'), true);
});

test('double-click still opens editing and Escape cancels without a request', async () => {
    const ui = harness();
    ui.doubleClick();
    assert.equal(ui.input.classList.contains('d-none'), false);
    ui.input.value = 'Descartar';
    ui.key('Escape');
    await ui.input.pendingBlur;
    assert.equal(ui.requests.length, 0);
    assert.equal(ui.input.value, 'Nome original');
    assert.equal(ui.nameSpan.classList.contains('d-none'), false);
});

for (const value of ['', '   ', 'Nome original']) {
    test(`leaving an empty or unchanged name (${JSON.stringify(value)}) keeps the original`, async () => {
        const ui = harness();
        await ui.open();
        ui.input.value = value;
        await ui.finish();
        assert.equal(ui.requests.length, 0);
        assert.equal(ui.input.value, 'Nome original');
        assert.equal(ui.nameSpan.textContent, 'Nome original');
    });
}

for (const failure of ['server', 'network']) {
    test(`a ${failure} error restores the name and permits retry`, async () => {
        const ui = harness();
        await ui.open();
        ui.input.value = 'Não salvo';
        const saving = ui.finish();
        if (failure === 'server') {
            ui.requests[0].resolve({ ok: false, json: async () => ({ message: 'Nome inválido' }) });
        } else {
            ui.requests[0].reject(new Error('offline'));
        }
        await saving;
        assert.equal(ui.nameSpan.textContent, 'Nome original');
        assert.equal(ui.input.value, 'Nome original');
        assert.equal(ui.renameButton.disabled, false);
        assert.equal(ui.alerts.length, 1);
        await ui.open();
        assert.equal(ui.input.disabled, false);
        assert.equal(ui.input.classList.contains('d-none'), false);
    });
}
