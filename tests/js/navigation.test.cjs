const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const source = readFileSync(join(__dirname, '../../static/app_teoria/home/navigation.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness() {
    const routes = ['home', 'retorno-volatilidade', 'projetos', 'referencias'].map(key => ({ key,
        url: `/${key}/`, legacy: `/legacy/${key}`, enhanced: true, title: key, menu: key }));
    routes.push({ key: 'bs', url: '/bs/', legacy: '/bs-api/', enhanced: false });
    const config = { ...routes[1], routes, user: '1', lang: 'pt', project: '' };
    const docEvents = {}, winEvents = {}, requests = [], pushes = [], replaces = [], assigns = [];
    const nodes = {};
    for (const id of ['main-content', 'navigationStatus', 'navigationRetry', 'languageSelect']) {
        nodes[id] = { innerHTML: 'original', hidden: true, attributes: {}, listeners: {},
            setAttribute(k, v) { this.attributes[k] = v; }, removeAttribute(k) { delete this.attributes[k]; },
            addEventListener(k, v) { this.listeners[k] = v; }, focus() { this.focused = true; } };
    }
    let disposed = 0, allowed = true;
    const lifecycle = { revision: 0, canLeave: () => allowed, flush() {}, clear() {},
        dispose() { disposed++; }, mount(page) { this.page = page; } };
    const location = { href: `https://saeto.test${config.url}`, origin: 'https://saeto.test',
        assign: url => assigns.push(url), reload: () => assigns.push('reload') };
    const context = { URL, URLSearchParams, AbortController, location,
        history: { replaceState: (_, __, url) => replaces.push(url), pushState: (_, __, url) => pushes.push(url) },
        document: { title: '', getElementById: id => id === 'saetoNavigation' ? { textContent: JSON.stringify(config) } : nodes[id],
            querySelectorAll: () => [], addEventListener: (name, fn) => { docEvents[name] = fn; } },
        window: { saetoLifecycle: lifecycle, jQuery: node => ({ html: value => { node.innerHTML = value; } }),
            addEventListener: (name, fn) => { winEvents[name] = fn; } },
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject })),
    };
    vm.runInNewContext(source, context);
    const click = (url, modifiers = {}) => {
        let prevented = false;
        const link = { href: url, hasAttribute: () => false };
        docEvents.click({ target: { closest: () => link }, button: 0,
            preventDefault() { prevented = true; }, ...modifiers });
        return prevented;
    };
    return { nodes, requests, pushes, replaces, assigns, lifecycle, context, click,
        get disposed() { return disposed; }, block: () => { allowed = false; },
        pop: url => { location.href = `https://saeto.test${url}`; winEvents.popstate(); },
        retry: () => nodes.navigationRetry.listeners.click(),
        respond: async (index, key, ok = true) => {
            requests[index].resolve({ ok, json: async () => ({ html: `page:${key}`,
                page: { ...routes.find(r => r.key === key), routes, user: '1', lang: 'pt' } }) });
            await tick();
        },
    };
}

test('initial state is replaced and successful navigation pushes once, then popstate does not push', async () => {
    const ui = harness();
    assert.deepEqual(ui.replaces, ['/retorno-volatilidade/']);
    ui.click('/projetos/?page=2');
    assert.equal(ui.requests[0].url, '/projetos/?page=2');
    assert.equal(ui.nodes['main-content'].innerHTML, 'original');
    await ui.respond(0, 'projetos');
    assert.deepEqual(ui.pushes, ['/projetos/?page=2']);
    assert.equal(ui.context.document.title, 'projetos · SAETO');
    ui.pop('/retorno-volatilidade/');
    await ui.respond(1, 'retorno-volatilidade');
    assert.equal(ui.pushes.length, 1);
    assert.equal(ui.disposed, 2);
    assert.equal(ui.nodes['main-content'].focused, true);
});

test('only the latest quick navigation can replace the visible analysis', async () => {
    const ui = harness();
    ui.click('/projetos/');
    ui.click('/referencias/');
    assert.equal(ui.requests[0].options.signal.aborted, true);
    await ui.respond(1, 'referencias');
    await ui.respond(0, 'projetos');
    assert.equal(ui.nodes['main-content'].innerHTML, 'page:referencias');
    assert.deepEqual(ui.pushes, ['/referencias/']);
    assert.equal(ui.disposed, 1);
});

test('failed loading leaves the current screen usable and offers a working retry', async () => {
    const ui = harness();
    ui.click('/projetos/');
    await ui.respond(0, 'projetos', false);
    assert.equal(ui.nodes['main-content'].innerHTML, 'original');
    assert.equal(ui.disposed, 0);
    assert.equal(ui.nodes.navigationRetry.hidden, false);
    assert.equal(ui.pushes.length, 0);
    ui.retry();
    await ui.respond(1, 'projetos');
    assert.equal(ui.nodes.navigationRetry.hidden, true);
    assert.equal(ui.disposed, 1);
});

test('new tabs and unknown or external URLs are never hijacked or fetched as fragments', () => {
    const ui = harness();
    assert.equal(ui.click('/projetos/', { ctrlKey: true }), false);
    assert.equal(ui.click('https://elsewhere.test/projetos/'), false);
    assert.equal(ui.click('/admin/'), false);
    assert.equal(ui.click('/retorno-volatilidade/#formula'), false);
    assert.equal(ui.requests.length, 0);
    ui.click('/bs/');
    assert.deepEqual(ui.assigns, ['/bs/']);
});

test('storage refusal prevents navigation and a changed analysis is checked again before replacement', async () => {
    const ui = harness();
    ui.click('/projetos/');
    ui.lifecycle.revision++;
    ui.block();
    await ui.respond(0, 'projetos');
    assert.equal(ui.disposed, 0);
    assert.equal(ui.nodes['main-content'].innerHTML, 'original');
    ui.click('/referencias/');
    assert.equal(ui.requests.length, 1);
});

test('failed Back restores the displayed URL without adding a history entry', async () => {
    const ui = harness();
    ui.pop('/projetos/');
    await ui.respond(0, 'projetos', false);
    assert.equal(ui.replaces.at(-1), '/retorno-volatilidade/');
    assert.equal(ui.pushes.length, 0);
    ui.retry();
    await ui.respond(1, 'projetos');
    assert.deepEqual(ui.pushes, ['/projetos/']);
});

test('language change posts the chosen language and reloads the same canonical URL', async () => {
    const ui = harness();
    const changing = ui.context.window.updateLanguage('en');
    assert.equal(ui.requests[0].url, '/set_language/');
    assert.equal(ui.requests[0].options.body.get('language'), 'en');
    assert.equal(ui.nodes.languageSelect.disabled, true);
    ui.requests[0].resolve({ ok: true, json: async () => ({ success: true }) });
    await changing;
    assert.deepEqual(ui.assigns, ['reload']);
    assert.equal(ui.pushes.length, 0);
});

test('a failed language request keeps the analysis and restores the selector', async () => {
    const ui = harness();
    const changing = ui.context.window.updateLanguage('en');
    ui.requests[0].reject(new Error('offline'));
    await changing;
    assert.equal(ui.nodes['main-content'].innerHTML, 'original');
    assert.equal(ui.nodes.languageSelect.disabled, false);
    assert.equal(ui.nodes.languageSelect.value, 'pt');
    assert.equal(ui.assigns.length, 0);
});
