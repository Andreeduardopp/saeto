/**
 * Shared "Save Project" dialog and call for the model screens.
 *
 * Loaded once by home.html; the screens are injected into #main-content, so this
 * global stays available on every screen. Returns the server's JSON response
 * (or undefined when the request failed).
 */
(function () {
    const MESSAGES = {
        pt: {
            title: 'Salvar projeto',
            name: 'Nome do exemplo (opcional)',
            hint: 'Até 255 caracteres. Deixe em branco para usar o nome automático.',
            cancel: 'Cancelar',
            save: 'Salvar',
            saving: 'Salvando...',
            success: 'Projeto salvo com sucesso!',
            error: 'Erro ao salvar o projeto:',
            unexpected: 'Ocorreu um erro inesperado.',
            report: 'Abrir relatório',
            changed: 'Dados alterados. Recalcule antes de salvar.',
        },
        en: {
            title: 'Save project',
            name: 'Example name (optional)',
            hint: 'Up to 255 characters. Leave blank to use the automatic name.',
            cancel: 'Cancel',
            save: 'Save',
            saving: 'Saving...',
            success: 'Project saved successfully!',
            error: 'Error saving project:',
            unexpected: 'An unexpected error occurred.',
            report: 'Open report',
            changed: 'Data changed. Recalculate before saving.',
        },
    };

    function findCsrfToken(button) {
        const scope = button.closest('form') || document.getElementById('main-content') || document;
        const input = scope.querySelector('input[name="csrfmiddlewaretoken"]')
            || document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function askProjectName(t, previousName, remember) {
        return new Promise(resolve => {
            const dialog = document.createElement('dialog');
            dialog.className = 'border-0 rounded shadow p-4';
            dialog.style.width = 'min(480px, calc(100% - 2rem))';
            dialog.setAttribute('aria-labelledby', 'saveProjectTitle');
            dialog.innerHTML = `
                <form>
                    <h2 id="saveProjectTitle" class="h5 mb-3">${t.title}</h2>
                    <label for="saveProjectName" class="form-label">${t.name}</label>
                    <input id="saveProjectName" name="name" type="text" maxlength="255"
                           class="form-control" aria-describedby="saveProjectHint" autofocus>
                    <p id="saveProjectHint" class="form-text">${t.hint}</p>
                    <div class="d-flex justify-content-end gap-2 mt-4">
                        <button type="button" class="btn btn-secondary" data-cancel>${t.cancel}</button>
                        <button type="submit" class="btn btn-success">${t.save}</button>
                    </div>
                </form>`;
            const input = dialog.querySelector('input');
            input.value = previousName || '';
            let name = null;
            dialog.querySelector('form').addEventListener('submit', event => {
                event.preventDefault();
                name = input.value.trim();
                dialog.close();
            });
            dialog.querySelector('[data-cancel]').addEventListener('click', () => dialog.close());
            // Escape closes the dialog with the same result as Cancel.
            dialog.addEventListener('close', () => {
                remember(input.value);
                dialog.remove();
                resolve(name);
            }, { once: true });
            document.body.appendChild(dialog);
            dialog.showModal();
            window.saetoLifecycle?.register(() => { if (dialog.open) dialog.close(); });
            input.focus();
        });
    }

    window.saetoSaveProject = async function ({ button, url, modelType, parameters, results, lang, isCurrent = () => true }) {
        if (button.disabled || button.dataset.saving === 'true') return;
        const t = MESSAGES[lang] || MESSAGES.pt;
        const originalHtml = button.innerHTML;
        const snapshot = JSON.stringify({ model_type: modelType, parameters, results });
        button.dataset.saving = 'true';
        button.disabled = true;
        const status = button.saetoSaveStatus || document.createElement('p');
        if (!button.saetoSaveStatus) {
            status.className = 'small mt-2';
            status.setAttribute('role', 'status');
            status.setAttribute('aria-live', 'polite');
            button.insertAdjacentElement('afterend', status);
            button.saetoSaveStatus = status;
        }
        const show = message => { status.textContent = message; };

        try {
            const name = await askProjectName(t, button.dataset.projectName, value => {
                button.dataset.projectName = value;
                window.saetoLifecycle?.changed();
                window.saetoLifecycle?.flush();
            });
            if (name === null) return;
            if (!isCurrent() || button.isConnected === false) { show(t.changed); return; }
            button.innerHTML = `<span class="spinner-border spinner-border-sm"></span> ${t.saving}`;
            show(t.saving);
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': findCsrfToken(button),
                },
                body: JSON.stringify({ ...JSON.parse(snapshot), name }),
            });
            const data = await response.json();
            if (response.ok && data.success) {
                button.dataset.projectName = data.name || name;
                show(t.success);
                if (data.report_url) {
                    const link = document.createElement('a');
                    link.href = data.report_url;
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.textContent = ` ${t.report}`;
                    status.appendChild(link);
                }
            } else {
                show(`${t.error} ${data.error || t.unexpected}`);
            }
            return data;
        } catch (error) {
            console.error('Error saving project:', error);
            show(t.unexpected);
        } finally {
            delete button.dataset.saving;
            button.disabled = !isCurrent() || button.isConnected === false;
            button.innerHTML = originalHtml;
            if (!button.disabled) button.focus();
        }
    };
})();
