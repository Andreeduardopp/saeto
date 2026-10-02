/**
 * Shared behaviour of the screens whose calculation runs on the server
 * (the stochastic-process screens): post the form, show the server's error
 * or the results, keep the last successful run and save it.
 *
 * The server validates the inputs and answers errors in the session language,
 * so the screen does not repeat the limits. Loaded once by home.html.
 */
(function () {
    const MESSAGES = {
        pt: { running: 'Processando...', unexpected: 'Ocorreu um erro inesperado. Tente novamente.' },
        en: { running: 'Processing...', unexpected: 'An unexpected error occurred. Please try again.' },
    };

    window.saetoServerScreen = function (config) {
        const {
            form, url, modelType, saveUrl, lang,
            resultsContainer, errorBox, submitButton, resetButton, saveButton,
            readParameters, render, onReset,
        } = config;
        const t = MESSAGES[lang] || MESSAGES.pt;
        // Inputs and results of the last successful run; Save sends exactly this.
        let lastRun = null;
        let currentRequest = 0;
        const originalSubmitHtml = submitButton.innerHTML;

        const setRunning = (running) => {
            submitButton.disabled = running;
            submitButton.innerHTML = running
                ? `<span class="spinner-border spinner-border-sm"></span> ${t.running}`
                : originalSubmitHtml;
        };

        const setLastRun = (run) => {
            lastRun = run;
            saveButton.disabled = !run;
        };
        const showError = (message) => {
            errorBox.textContent = message;
            errorBox.style.display = message ? 'block' : 'none';
        };
        const hideResults = () => {
            setLastRun(null);
            resultsContainer.style.display = 'none';
        };

        async function run() {
            const requestId = ++currentRequest;
            hideResults();
            showError('');
            const parameters = readParameters();
            setRunning(true);
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = (await response.json().catch(() => null)) || {};
                if (requestId !== currentRequest) return;
                if (!response.ok || data.error) {
                    showError(data.error || t.unexpected);
                    return;
                }
                const results = render(data);
                if ('seed' in data) {
                    parameters.seed = data.seed;
                    const seedOutput = resultsContainer.querySelector('[data-seed-used]');
                    if (seedOutput) seedOutput.textContent = data.seed;
                }
                resultsContainer.style.display = 'block';
                setLastRun({ parameters, results });
            } catch (error) {
                if (requestId !== currentRequest) return;
                console.error(error);
                showError(t.unexpected);
            } finally {
                if (requestId === currentRequest) setRunning(false);
            }
        }

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            run();
        });
        // Back to the loaded values: the defaults, or the saved run on rerun.
        resetButton.addEventListener('click', () => {
            // A response from before Reset must not restore results or Save.
            currentRequest++;
            setRunning(false);
            form.reset();
            showError('');
            hideResults();
            if (onReset) onReset();
        });
        saveButton.addEventListener('click', () => {
            if (!lastRun) return;
            saetoSaveProject({
                button: saveButton,
                url: saveUrl,
                modelType: modelType,
                parameters: lastRun.parameters,
                results: lastRun.results,
                lang: lang,
            });
        });
        hideResults();
        return { run };
    };

    /** The named inputs of a form as parameters: {name: 'number' | 'text'}. */
    window.saetoServerScreen.readForm = function (form, fields) {
        const parameters = {};
        for (const [name, kind] of Object.entries(fields)) {
            const value = form.elements[name].value;
            parameters[name] = kind === 'number' ? Number(value) : value;
        }
        return parameters;
    };

    window.saetoServerScreen.dataUri = (base64) => `data:image/png;base64,${base64}`;

    window.saetoServerScreen.formatNumber = function (value, lang, decimals = 4) {
        if (typeof value !== 'number' || !Number.isFinite(value)) return '-';
        return value.toLocaleString(lang === 'en' ? 'en-US' : 'pt-BR', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    };

    /** Fills a <tbody> with one row per statistic, labelled by key. */
    window.saetoServerScreen.fillStats = function (tbody, stats, labels, lang, decimals = 4) {
        tbody.innerHTML = '';
        for (const [key, value] of Object.entries(stats)) {
            const row = document.createElement('tr');
            const label = document.createElement('td');
            const cell = document.createElement('td');
            label.textContent = labels[key] || key;
            cell.textContent = window.saetoServerScreen.formatNumber(value, lang, decimals);
            row.append(label, cell);
            tbody.appendChild(row);
        }
    };
})();
