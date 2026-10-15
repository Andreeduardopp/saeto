const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const source = readFileSync(join(__dirname, '../../static/app_teoria/home/page_lifecycle.js'), 'utf8');

function harness({ user = '1', project = '', key = 'retorno-volatilidade', store = {}, unavailable = false } = {}) {
    const events = {}, warnings = [], restores = [], confirmations = [];
    const storage = new Proxy(store, { get(target, property) {
        if (property === 'getItem') return name => { if (unavailable) throw Error(); return target[name] || null; };
        if (property === 'setItem') return (name, value) => { if (unavailable) throw Error(); target[name] = value; };
        if (property === 'removeItem') return name => { if (unavailable) throw Error(); delete target[name]; };
        return target[property];
    } });
    let data = { prices: ['100', 'invalid', '110'] }, cleaned = 0;
    const context = { sessionStorage: storage, document: { getElementById: () => ({ textContent: JSON.stringify({ user, project, key, lang: 'pt' }) }) },
        window: { addEventListener: (name, callback) => { events[name] = callback; },
            confirm: message => { confirmations.push(message); return false; } } };
    vm.runInNewContext(source, context);
    const lifecycle = context.window.saetoLifecycle;
    lifecycle.attachDraft({ capture: () => data, restore: restored => { restores.push(restored); return true; }, warn: text => warnings.push(text) });
    lifecycle.register(() => cleaned++);
    return { lifecycle, store, events, restores, warnings, confirmations, get cleaned() { return cleaned; } };
}

test('tab drafts survive remount and are partitioned by user, tool and project', () => {
    const ui = harness();
    ui.lifecycle.changed();
    assert.equal(ui.lifecycle.canLeave(), true);
    const recovered = harness({ store: ui.store });
    assert.deepEqual(JSON.parse(JSON.stringify(recovered.restores[0])), { prices: ['100', 'invalid', '110'] });
    for (const override of [{ user: '2' }, { project: 'a' }, { key: 'other' }]) {
        assert.equal(harness({ store: ui.store, ...override }).restores.length, 0);
    }
    assert.equal(ui.confirmations.length, 0);
    ui.lifecycle.dispose();
    assert.equal(ui.cleaned, 1);
});

test('unavailable storage warns before navigation or closing and preserves the active analysis', () => {
    const ui = harness({ unavailable: true });
    assert.match(ui.warnings[0], /armazenamento/);
    ui.lifecycle.changed();
    assert.equal(ui.lifecycle.canLeave(), false);
    assert.equal(ui.confirmations.length, 1);
    let prevented = false;
    ui.events.beforeunload({ preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    assert.equal(ui.cleaned, 0);
});

test('discard and logout remove only SAETO drafts, including other project keys', () => {
    const ui = harness({ store: { unrelated: 'keep', 'saeto:draft:v1:1:other:new': '{}' } });
    ui.lifecycle.changed();
    ui.lifecycle.flush();
    ui.lifecycle.discard();
    assert.equal(harness({ store: ui.store }).restores.length, 0);
    ui.lifecycle.clear();
    assert.deepEqual(ui.store, { unrelated: 'keep' });
});

test('an unsupported version is never restored', () => {
    const ui = harness({ store: { 'saeto:draft:v1:1:retorno-volatilidade:new': '{"version":2,"data":{"prices":[1]}}' } });
    assert.equal(ui.restores.length, 0);
});
