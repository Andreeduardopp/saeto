const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const core = require('../../../static/app_teoria/volatility/return_volatility_core.js');
const fileApi = require('../../../static/app_teoria/volatility/price_file_reader.js');

const template = readFileSync(join(__dirname, '../../../templates/site/teoria/volatilidade.html'), 'utf8');

// Exercise the actual screen handlers with a small DOM double. This checks state,
// events and focus targets, not browser layout or native clipboard behaviour.
function screenHarness(language = 'pt', savedProject = null, draft = undefined, xlsx = undefined) {
    const nodes = new Map(), timers = new Map(), saves = [], copies = [], charts = [];
    let focused = null;
    class Element {
        constructor(id = '', tag = '') {
            this.tag = tag;
            this.children = [];
            this.listeners = {};
            this.attributes = {};
            this.selectors = {};
            this.dataset = {};
            this.style = {};
            this.value = '';
            this.textContent = '';
            this.hidden = false;
            this.disabled = false;
            this.checked = false;
            this.classList = { toggle() {}, add() {}, remove() {} };
            this.id = id;
        }
        set id(value) { this._id = value; if (value) nodes.set(value, this); }
        get id() { return this._id; }
        set innerHTML(value) { this.html = value; this.children = []; }
        get innerHTML() { return this.html || ''; }
        appendChild(child) {
            if (child.tag === 'fragment') this.children.push(...child.children);
            else this.children.push(child);
            return child;
        }
        prepend(...children) { this.children.unshift(...children); }
        insertRow() { return this.appendChild(new Element('', 'tr')); }
        insertCell() { return this.appendChild(new Element('', 'td')); }
        setAttribute(key, value) { this.attributes[key] = value; }
        addEventListener(name, handler) { this.listeners[name] = handler; }
        querySelector(selector) { return this.selectors[selector] ||= new Element(); }
        querySelectorAll() { return []; }
        focus() { focused = this; }
        select() { this.setSelectionRange(0, this.value.length); }
        setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }
        getContext() { return {}; }
    }
    for (const match of template.matchAll(/\bid="([\w-]+)"/g)) new Element(match[1]);
    for (const match of template.matchAll(/\|json_script:"([\w-]+)"/g)) new Element(match[1]);
    const el = id => {
        assert.ok(nodes.has(id), `Missing element: ${id}`);
        return nodes.get(id);
    };
    const modes = ['Manual', 'Paste', 'File'].map(name => {
        const node = el(`dataMode${name}`);
        node.value = name.toLowerCase();
        return node;
    });
    modes[0].checked = true;
    const modeLabels = modes.map(radio => {
        const node = new Element();
        node.selectors.input = radio;
        return node;
    });
    const sizes = ['pricesPageSize', 'returnsPageSize'].map(el);
    el('returnVolatilityScreen').querySelectorAll = selector => ({
        'input[name="dataMode"]': modes,
        '.rv-mode-option': modeLabels,
        '[data-page-size]': sizes,
        '[data-limit-mb]': [],
    }[selector] || []);
    const initial = JSON.stringify({ periods: 5, prices: [100, 105, 98, 110, 107.5] });
    // `savedProject` stands for the parameters of a project being re-run.
    el('volatilityInitialData').textContent =
        savedProject ? JSON.stringify(savedProject) : initial;
    el('volatilityExampleData').textContent = initial;
    const document = {
        getElementById: id => nodes.get(id) || null,
        createElement: tag => new Element('', tag),
        createDocumentFragment: () => new Element('', 'fragment'),
        addEventListener() {}, head: new Element(), body: new Element(),
    };
    const context = {
        document, console, TextDecoder, Uint8Array,
        window: { saetoReturnVolatility: core, saetoPriceFile: fileApi, isSecureContext: true, XLSX: xlsx },
        navigator: { clipboard: { writeText: text => { copies.push(text); return Promise.resolve(); } } },
        Chart: class {
            // Kept so a test can call the tooltip and axis callbacks of the chart.
            constructor(context, config) { charts.push(config); }
            destroy() {}
            toBase64Image() { return 'data:image/png;base64,test'; }
        },
        saetoSaveProject: payload => { saves.push(JSON.parse(JSON.stringify(payload))); },
        setTimeout: callback => { const key = {}; timers.set(key, callback); return key; },
        clearTimeout: key => timers.delete(key),
    };
    let draftHooks, cleanup;
    if (draft !== undefined) context.window.saetoLifecycle = {
        attachDraft(hooks) { draftHooks = hooks; if (draft) hooks.restore(draft); },
        register(callback) { cleanup = callback; },
        changed() {}, flush() {}, discard() {},
    };
    const script = template.split('<script>')[1].split('</script>')[0]
        .replace('{% if is_rerun %}true{% else %}false{% endif %}', 'false')
        .replace('{{ request.session.language|default:"pt" }}', language);
    vm.runInNewContext(script, context, { filename: 'volatilidade.html' });
    const fire = (id, name, event = {}) => el(id).listeners[name]({ target: el(id), preventDefault() {}, ...event });
    const click = id => { assert.equal(el(id).disabled, false, `${id} is disabled`); return fire(id, 'click'); };
    const flush = () => { const pending = [...timers.values()]; timers.clear(); pending.forEach(fn => fn()); };
    const type = (id, value) => { el(id).value = value; fire(id, 'input'); };
    return {
        el, click, fire, flush, type, saves, copies,
        captureDraft: () => JSON.parse(JSON.stringify(draftHooks.capture())),
        dispose: () => cleanup(),
        get chart() { return charts[charts.length - 1]; },
        get focused() { return focused; },
        mode(name) {
            const radio = modes.find(node => node.value === name);
            radio.checked = true;
            radio.focus();
            fire(radio.id, 'change');
        },
        paste(text) { type('pastedPrices', text); flush(); },
        async csv(text) {
            el('priceFileInput').files = [{ name: 'prices.csv', size: text.length,
                arrayBuffer: async () => new TextEncoder().encode(text).buffer }];
            fire('priceFileInput', 'change');
            await new Promise(resolve => setImmediate(resolve));
        },
        async file(file) {
            el('priceFileInput').files = [file];
            fire('priceFileInput', 'change');
            await new Promise(resolve => setImmediate(resolve));
        },
    };
}


module.exports = { screenHarness };
