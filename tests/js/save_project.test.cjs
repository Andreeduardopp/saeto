const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = readFileSync(join(__dirname, '../../static/app_teoria/home/save_project.js'), 'utf8');

function harness({ failure = false, lang = 'pt', delayed = false } = {}) {
    const requests = [], alerts = [], dialogs = [];
    let current = true, resolveResponse;
    const element = () => ({
        listeners: {}, style: {}, value: '', children: [],
        appendChild(child) { this.children.push(child); },
        addEventListener(event, handler) { this.listeners[event] = handler; },
        setAttribute() {}, focus() {},
    });
    const document = {
        body: { appendChild(dialog) { dialogs.push(dialog); } },
        createElement(tag) {
            if (tag !== 'dialog') return element();
            const input = element(), form = element(), cancel = element();
            const dialog = {
                ...element(),
                querySelector(selector) { return { input, form, '[data-cancel]': cancel }[selector]; },
                showModal() { this.open = true; },
                close() { this.open = false; this.listeners.close(); },
                remove() { this.removed = true; },
                submit(value) { input.value = value; form.listeners.submit({ preventDefault() {} }); },
                cancel() { cancel.listeners.click(); },
            };
            return dialog;
        },
    };
    const button = {
        innerHTML: 'Salvar projeto', disabled: false, dataset: {},
        insertAdjacentElement() {}, focus() { this.focused = true; },
        closest() { return { querySelector: () => ({ value: 'csrf-test' }) }; },
    };
    const context = {
        window: {}, document, console: { error() {} }, alert: message => alerts.push(message),
        fetch: async (url, options) => {
            requests.push({ url, ...options, body: JSON.parse(options.body) });
            if (failure) throw new Error('offline');
            const response = { ok: true, json: async () => ({ success: true, name: 'Exemplo salvo', id: '1', report_url: '/report/1/' }) };
            if (delayed) return new Promise(resolve => { resolveResponse = () => resolve(response); });
            return response;
        },
    };
    vm.runInNewContext(source, context);
    return {
        button, requests, alerts, dialogs,
        change: () => { current = false; },
        respond: () => resolveResponse(),
        save: () => context.window.saetoSaveProject({
            button, url: '/save', modelType: 'MARKOV_CHAIN', lang,
            parameters: { iterations: 100000 }, results: { evolution_steps: [0, 100000] },
            isCurrent: () => current,
        }),
    };
}

test('asks for a name before posting and saves the calculated parameters and results', async () => {
    const ui = harness();
    const saving = ui.save();
    assert.equal(ui.requests.length, 0);
    assert.equal(ui.button.disabled, true);
    await ui.save(); // A second click must not open another dialog or duplicate the save.
    assert.equal(ui.dialogs.length, 1);
    ui.dialogs[0].submit('  Exemplo 99,99%  ');
    await saving;
    assert.deepEqual(ui.requests[0].body, {
        name: 'Exemplo 99,99%', model_type: 'MARKOV_CHAIN',
        parameters: { iterations: 100000 }, results: { evolution_steps: [0, 100000] },
    });
    assert.equal(ui.requests[0].headers['X-CSRFToken'], 'csrf-test');
    assert.equal(ui.dialogs[0].removed, true);
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.button.innerHTML, 'Salvar projeto');
    assert.match(ui.button.saetoSaveStatus.textContent, /sucesso/);
    assert.equal(ui.button.saetoSaveStatus.children[0].href, '/report/1/');
    assert.equal(ui.alerts.length, 0);
    const again = ui.save();
    assert.equal(ui.dialogs[1].querySelector('input').value, 'Exemplo salvo');
    ui.dialogs[1].cancel();
    await again;
});

for (const close of ['cancel', 'close']) {
    test(`${close} dismisses the dialog without saving and allows another attempt`, async () => {
        const ui = harness();
        const saving = ui.save();
        ui.dialogs[0][close]();
        await saving;
        assert.equal(ui.requests.length, 0);
        assert.equal(ui.alerts.length, 0);
        assert.equal(ui.button.disabled, false);
        assert.equal(ui.dialogs[0].removed, true);
    });
}

test('a blank name keeps automatic naming and the English dialog is translated', async () => {
    const ui = harness({ lang: 'en' });
    const saving = ui.save();
    assert.match(ui.dialogs[0].innerHTML, /Example name \(optional\)/);
    ui.dialogs[0].submit('   ');
    await saving;
    assert.equal(ui.requests[0].body.name, '');
    assert.equal(ui.button.saetoSaveStatus.textContent, 'Project saved successfully!');
});

test('a failed request restores the Save button', async () => {
    const ui = harness({ failure: true });
    const saving = ui.save();
    ui.dialogs[0].submit('Teste');
    await saving;
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.button.innerHTML, 'Salvar projeto');
    assert.match(ui.button.saetoSaveStatus.textContent, /erro inesperado/);
    assert.equal(ui.button.dataset.projectName, 'Teste');
    assert.equal(ui.button.focused, true);
});

test('an edit while the name dialog is open cannot save the previous analysis', async () => {
    const ui = harness();
    const saving = ui.save();
    ui.change();
    ui.dialogs[0].submit('Keep this name');
    await saving;
    assert.equal(ui.requests.length, 0);
    assert.equal(ui.button.disabled, true);
    assert.equal(ui.button.dataset.projectName, 'Keep this name');
});

test('editing during saving does not reenable the obsolete result or duplicate requests', async () => {
    const ui = harness({ delayed: true });
    const saving = ui.save();
    ui.dialogs[0].submit('Flight');
    await Promise.resolve();
    ui.change();
    ui.button.disabled = false; // another renderer must not bypass the pending flag
    await ui.save();
    assert.equal(ui.requests.length, 1);
    ui.respond();
    await saving;
    assert.equal(ui.button.disabled, true);
});
