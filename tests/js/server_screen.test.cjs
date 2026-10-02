const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = readFileSync(join(__dirname, '../../static/app_teoria/home/server_screen.js'), 'utf8');

function control() {
    return {
        listeners: {}, style: {}, innerHTML: 'Simular', textContent: '', disabled: false,
        addEventListener(event, handler) { this.listeners[event] = handler; },
        querySelector() { return null; },
    };
}

function screenHarness() {
    const requests = [], renders = [], saves = [];
    const controls = {
        form: { ...control(), reset() {} },
        resultsContainer: control(), errorBox: control(), submitButton: control(),
        resetButton: control(), saveButton: control(),
    };
    const context = {
        window: {}, console, FormData: class {},
        fetch: () => new Promise((resolve, reject) => requests.push({ resolve, reject })),
        saetoSaveProject: payload => saves.push(payload),
    };
    vm.runInNewContext(source, context);
    const screen = context.window.saetoServerScreen({
        ...controls, url: '/simulate', saveUrl: '/save', modelType: 'RANDOM_WALK', lang: 'pt',
        readParameters: () => ({ steps: 50 }),
        render(data) { renders.push(data); return data; },
    });
    return {
        ...controls, screen, requests, renders, saves,
        reset: () => controls.resetButton.listeners.click(),
        save: () => controls.saveButton.listeners.click(),
    };
}

function respond(request, data, ok = true) {
    request.resolve({ ok, json: async () => data });
}

test('reset discards a late successful response and keeps Save disabled', async () => {
    const ui = screenHarness();
    const running = ui.screen.run();
    ui.reset();
    assert.equal(ui.submitButton.disabled, false);
    assert.equal(ui.submitButton.innerHTML, 'Simular');

    respond(ui.requests[0], { seed: 1, statistics: { final: 10 } });
    await running;
    ui.save();
    assert.equal(ui.resultsContainer.style.display, 'none');
    assert.equal(ui.saveButton.disabled, true);
    assert.equal(ui.errorBox.textContent, '');
    assert.equal(ui.renders.length, 0);
    assert.equal(ui.saves.length, 0);
});

for (const failure of ['server', 'network']) {
    test(`reset discards a late ${failure} error`, async () => {
        const ui = screenHarness();
        const running = ui.screen.run();
        ui.reset();
        if (failure === 'server') respond(ui.requests[0], { error: 'Invalid input' }, false);
        else ui.requests[0].reject(new Error('Network unavailable'));
        await running;
        assert.equal(ui.errorBox.textContent, '');
        assert.equal(ui.resultsContainer.style.display, 'none');
        assert.equal(ui.saveButton.disabled, true);
    });
}

for (const oldFinishesFirst of [true, false]) {
    test(`a run after reset owns the results and buttons (old finishes first: ${oldFinishesFirst})`, async () => {
        const ui = screenHarness();
        const oldRun = ui.screen.run();
        ui.reset();
        const newRun = ui.screen.run();

        if (oldFinishesFirst) {
            respond(ui.requests[0], { seed: 1 });
            await oldRun;
            assert.equal(ui.submitButton.disabled, true);
            assert.equal(ui.saveButton.disabled, true);
            assert.equal(ui.renders.length, 0);
        }

        respond(ui.requests[1], { seed: 2, statistics: { final: 20 } });
        await newRun;
        if (!oldFinishesFirst) {
            respond(ui.requests[0], { seed: 1 });
            await oldRun;
        }

        ui.save();
        assert.equal(ui.renders.length, 1);
        assert.equal(ui.resultsContainer.style.display, 'block');
        assert.equal(ui.saveButton.disabled, false);
        assert.equal(ui.submitButton.disabled, false);
        assert.equal(ui.submitButton.innerHTML, 'Simular');
        assert.equal(ui.saves.length, 1);
        assert.equal(ui.saves[0].parameters.seed, 2);
        assert.equal(ui.saves[0].results.statistics.final, 20);
    });
}
