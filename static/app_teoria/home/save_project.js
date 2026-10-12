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
        },
    };

    function findCsrfToken(button) {
        const scope = button.closest('form') || document.getElementById('main-content') || document;
        const input = scope.querySelector('input[name="csrfmiddlewaretoken"]')
            || document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function askProjectName(t, previousName) {
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
                dialog.remove();
                resolve(name);
            }, { once: true });
            document.body.appendChild(dialog);
            dialog.showModal();
            input.focus();
        });
    }

    window.saetoSaveProject = async function ({ button, url, modelType, parameters, results, lang }) {
        if (button.disabled) return;
        const t = MESSAGES[lang] || MESSAGES.pt;
        const originalHtml = button.innerHTML;
        button.disabled = true;

        try {
            const name = await askProjectName(t, button.dataset.projectName);
            if (name === null) return;
            button.innerHTML = `<span class="spinner-border spinner-border-sm"></span> ${t.saving}`;
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': findCsrfToken(button),
                },
                body: JSON.stringify({ name, model_type: modelType, parameters, results }),
            });
            const data = await response.json();
            if (response.ok && data.success) {
                button.dataset.projectName = data.name || name;
                alert(t.success);
            } else {
                alert(`${t.error} ${data.error || t.unexpected}`);
            }
            return data;
        } catch (error) {
            console.error('Error saving project:', error);
            alert(t.unexpected);
        } finally {
            button.disabled = false;
            button.innerHTML = originalHtml;
        }
    };
})();
