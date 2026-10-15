const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const shared = readFileSync(join(__dirname, '../../static/app_teoria/home/server_screen.js'), 'utf8');

const SCREENS = {
    european: {
        template: 'templates/site/financeiros/options_price_mcs.html',
        form: 'precificacaoOpcaoForm', results: 'resultSection', price: 'estimatedPrice',
        error: 'screenError', run: 'submitMonteCarloForm', reset: 'resetMcsForm',
        answer: {
            preco_estimado: 10.450583572,
            price_plot: 'AAA', distribution_plot: 'BBB',
            stats_descriptive: { mean: 105.1234567, std: 21.25 },
            stats_inferential: { mean_estimated: 105.1234567, standard_error: 0.0672 },
        },
    },
    american: {
        template: 'templates/site/financeiros/options_price_american_mcs.html',
        form: 'americanOptionForm', results: 'resultSectionAmerican', price: 'estimatedPriceAmerican',
        error: 'screenErrorAmerican', run: 'submitAmericanOptionForm', reset: 'resetMcsAmericanForm',
        answer: {
            preco_estimado: 6.081234567,
            price_plot: 'AAA', exercise_boundary_plot: 'BBB', convergence_plot: 'CCC',
        },
    },
};

// Exercise the actual screen handlers with small DOM and jQuery doubles. This
// checks state, discarded answers and what Save sends, not browser layout.
function screenHarness(name, language = 'pt') {
    const screen = SCREENS[name];
    const template = readFileSync(join(__dirname, '../..', screen.template), 'utf8');
    const nodes = new Map(), saves = [], requests = [];

    class Element {
        constructor(id = '', tag = '') {
            this.tag = tag;
            this.children = [];
            this.dataset = {};
            this.style = {};
            this.value = '';
            this.textContent = '';
            this.disabled = false;
            this.id = id;
        }
        set id(value) { this._id = value; if (value) nodes.set(value, this); }
        get id() { return this._id; }
        set innerHTML(value) { if (!value) this.children = []; }
        append(...children) { this.children.push(...children); }
        appendChild(child) { this.children.push(child); return child; }
        reset() { this.wasReset = true; }
        get text() { return this.children.map(child => child.textContent); }
    }
    for (const match of template.matchAll(/\bid="([\w-]+)"/g)) new Element(match[1]);
    for (const match of template.matchAll(/\|json_script:"([\w-]+)"/g)) new Element(match[1]);
    const el = id => {
        assert.ok(nodes.has(id), `Missing element: ${id}`);
        return nodes.get(id);
    };
    const labels = { mean: 'Média', std: 'Desvio padrão', mean_estimated: 'Média estimada',
                     standard_error: 'Erro padrão da média' };
    const english = { mean: 'Mean', std: 'Standard deviation', mean_estimated: 'Estimated mean',
                      standard_error: 'Standard error of the mean' };
    if (nodes.has('statLabelsEuropean')) {
        el('statLabelsEuropean').textContent = JSON.stringify(language === 'en' ? english : labels);
    }
    const bodies = new Map([['#descStatsTable tbody', new Element()], ['#infStatsTable tbody', new Element()]]);

    // Only the calls these two screens make.
    const wrap = elements => ({
        elements,
        length: elements.length,
        first() { return wrap(elements.slice(0, 1)); },
        empty() { elements.forEach(node => { node.children = []; }); return this; },
        append(child) {
            // jQuery appends the nodes of a wrapped set, not the wrapper itself.
            const added = child.elements || [child];
            elements.forEach(node => added.forEach(one => node.appendChild(one)));
            return this;
        },
        text(value) {
            if (value === undefined) return elements[0] ? elements[0].textContent : '';
            elements.forEach(node => { node.textContent = String(value); });
            return this;
        },
        attr(key, value) {
            if (value === undefined) return elements[0] ? elements[0].dataset[key] : undefined;
            elements.forEach(node => { node.dataset[key] = value; });
            return this;
        },
        css(key, value) { elements.forEach(node => { node.style[key] = value; }); return this; },
        hide() { return this.css('display', 'none'); },
        show() { return this.css('display', 'block'); },
        serialize() { return 'serialized'; },
    });
    const errorLists = () => [...nodes.values()].filter(node => node.id.endsWith('_errors'));
    const $ = selector => {
        if (selector === '.errorlist') return wrap(errorLists());
        if (selector.startsWith('<')) return wrap([new Element('', selector.slice(1, -1))]);
        const found = selector.split(',')
            .map(part => nodes.get(part.trim().slice(1)))
            .filter(Boolean);
        return wrap(found);
    };
    $.ajax = options => { requests.push(options); };

    const context = {
        console,
        document: {
            getElementById: id => nodes.get(id) || null,
            createElement: tag => new Element('', tag),
            querySelector: selector => bodies.get(selector) || null,
        },
        window: {},
        $, jQuery: $,
    };
    vm.runInNewContext(shared, context);
    context.saetoServerScreen = context.window.saetoServerScreen;
    context.saetoSaveProject = payload => { saves.push(JSON.parse(JSON.stringify(payload))); return payload; };
    context.window.saetoSaveProject = context.saetoSaveProject;

    for (const field of ['S0', 'K', 'T', 'r', 'sigma', 'num_simulacoes', 'num_passos',
                         'option_type', 'S0_american', 'K_american', 'T_american', 'r_american',
                         'sigma_american', 'num_simulacoes_american', 'option_type_american']) {
        if (nodes.has(field)) el(field).value = '1';
    }
    el(screen.form).dataset.action = '/simulate/';

    const script = template.split('<script>')[1].split('</script>')[0]
        .replace(/\{\{ language \}\}/g, language)
        .replace(/\{% url "save_financial_model" %\}/g, '/save/');
    vm.runInNewContext(script, context, { filename: screen.template });

    return {
        el, saves, requests, answer: screen.answer,
        run: () => context.window[screen.run](),
        reset: () => context.window[screen.reset](),
        save: () => context.window.saveProject(),
        succeed(request, data) { request.success(data || screen.answer); },
        fail(request, body, status = 400) {
            request.error({ status, responseJSON: body }, 'error', 'Bad Request');
        },
        stats(which) { return bodies.get(`#${which}StatsTable tbody`).children.map(row => row.text); },
        get price() { return el(screen.price).textContent; },
        get error() { return el(screen.error).textContent; },
        get visible() { return el(screen.results).style.display === 'block'; },
        get saveDisabled() { return el('saveProjectBtn').disabled; },
        messages(field) {
            const list = nodes.get(`${field}_errors`) || nodes.get(`${field}_american_errors`);
            return list.children.map(item => item.textContent);
        },
    };
}

for (const name of Object.keys(SCREENS)) {
    test(`${name}: a run shows the price in the language of the session`, () => {
        const pt = screenHarness(name, 'pt');
        pt.run();
        pt.succeed(pt.requests[0]);
        assert.equal(pt.price, name === 'european' ? '10,4506' : '6,0812');
        assert.equal(pt.visible, true);
        assert.equal(pt.saveDisabled, false);

        const en = screenHarness(name, 'en');
        en.run();
        en.succeed(en.requests[0]);
        assert.equal(en.price, name === 'european' ? '10.4506' : '6.0812');
    });

    test(`${name}: Save sends the numbers of the run, not the text on the screen`, () => {
        const ui = screenHarness(name, 'pt');
        ui.run();
        ui.succeed(ui.requests[0]);
        ui.save();
        assert.equal(ui.saves.length, 1);
        const results = ui.saves[0].results;
        const price = name === 'european' ? results.estimated_price : results.preco_estimado;
        assert.equal(price, ui.answer.preco_estimado);
        assert.equal(results.price_plot, 'data:image/png;base64,AAA');
        assert.equal(ui.saves[0].lang, 'pt');
    });

    test(`${name}: an answer from before Reset restores nothing`, () => {
        const ui = screenHarness(name, 'pt');
        ui.run();
        ui.reset();
        assert.equal(ui.saveDisabled, true);

        ui.succeed(ui.requests[0]);
        assert.equal(ui.visible, false);
        assert.equal(ui.saveDisabled, true);
        assert.equal(ui.price, '');
    });

    test(`${name}: an answer from the previous click never lands on the current run`, () => {
        const ui = screenHarness(name, 'pt');
        ui.run();
        ui.run();
        ui.succeed(ui.requests[1]);
        ui.fail(ui.requests[0], { errors: { S0: 'Antigo' } });
        assert.equal(ui.error, '');
        assert.equal(ui.visible, true);
        assert.deepEqual(ui.messages('S0'), []);
    });

    test(`${name}: a refused run marks each field and says so once`, () => {
        const ui = screenHarness(name, 'pt');
        ui.run();
        ui.fail(ui.requests[0], { errors: {
            S0: 'Preço Atual do Ativo (S0) deve ser maior que 0.',
            num_simulacoes: 'Número de Simulações deve estar entre 1.000 e 10.000.',
        } });
        assert.deepEqual(ui.messages('S0'), ['Preço Atual do Ativo (S0) deve ser maior que 0.']);
        assert.deepEqual(ui.messages('num_simulacoes'),
                         ['Número de Simulações deve estar entre 1.000 e 10.000.']);
        assert.equal(ui.error, 'Erro de validação. Verifique os campos marcados.');
        assert.equal(ui.visible, false);
        assert.equal(ui.saveDisabled, true);
    });

    test(`${name}: the message of the server is shown as it is`, () => {
        const ui = screenHarness(name, 'pt');
        ui.run();
        ui.fail(ui.requests[0], { error: 'Ocorreu um erro inesperado durante a simulação.' }, 500);
        assert.equal(ui.error, 'Ocorreu um erro inesperado durante a simulação.');
    });

    test(`${name}: an unreachable server says so in the session language`, () => {
        for (const [language, expected] of [['pt', /^Não foi possível falar com o servidor/],
                                            ['en', /^Could not reach the server/]]) {
            const ui = screenHarness(name, language);
            ui.run();
            ui.fail(ui.requests[0], undefined, 0);
            assert.match(ui.error, expected);
        }
    });

    test(`${name}: a second run clears the messages of the first`, () => {
        const ui = screenHarness(name, 'pt');
        ui.run();
        ui.fail(ui.requests[0], { errors: { S0: 'Inválido' } });
        ui.run();
        assert.deepEqual(ui.messages('S0'), []);
        assert.equal(ui.error, '');
    });
}

test('european: the statistics are labelled and formatted in the session language', () => {
    const pt = screenHarness('european', 'pt');
    pt.run();
    pt.succeed(pt.requests[0]);
    assert.deepEqual(pt.stats('desc'), [['Média', '105,1235'], ['Desvio padrão', '21,2500']]);
    assert.deepEqual(pt.stats('inf'), [['Média estimada', '105,1235'], ['Erro padrão da média', '0,0672']]);

    const en = screenHarness('european', 'en');
    en.run();
    en.succeed(en.requests[0]);
    assert.deepEqual(en.stats('desc'), [['Mean', '105.1235'], ['Standard deviation', '21.2500']]);
});

test('european: a message without a field of its own is still shown', () => {
    const ui = screenHarness('european', 'pt');
    ui.run();
    ui.fail(ui.requests[0], { errors: { seed: 'Semente deve estar entre 0 e 4.294.967.295.' } });
    assert.equal(ui.error, 'Semente deve estar entre 0 e 4.294.967.295.');
});

test('european: Save sends the statistics by key, with their full precision', () => {
    const ui = screenHarness('european', 'pt');
    ui.run();
    ui.succeed(ui.requests[0]);
    ui.save();
    assert.deepEqual(ui.saves[0].results.statistics, { mean: 105.1234567, std: 21.25 });
});
