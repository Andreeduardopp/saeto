/**
 * Shared "Save Project" call for the financial model screens.
 *
 * Loaded once by home.html; the screens are injected into #main-content, so this
 * global stays available on every screen. Returns the server's JSON response
 * (or undefined when the request failed).
 */
(function () {
    const MESSAGES = {
        pt: {
            saving: 'Salvando...',
            success: 'Projeto salvo com sucesso!',
            error: 'Erro ao salvar o projeto:',
            unexpected: 'Ocorreu um erro inesperado.',
        },
        en: {
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

    window.saetoSaveProject = function ({ button, url, modelType, parameters, results, lang }) {
        const t = MESSAGES[lang] || MESSAGES.pt;
        const originalHtml = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm"></span> ${t.saving}`;

        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': findCsrfToken(button),
            },
            body: JSON.stringify({ model_type: modelType, parameters, results }),
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(t.success);
                } else {
                    alert(`${t.error} ${data.error}`);
                }
                return data;
            })
            .catch(error => {
                console.error('Error saving project:', error);
                alert(t.unexpected);
            })
            .finally(() => {
                button.disabled = false;
                button.innerHTML = originalHtml;
            });
    };
})();
