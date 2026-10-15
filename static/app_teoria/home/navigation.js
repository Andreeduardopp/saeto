/* Only catalogue pages (and owner-checked project pages) can supply fragments. */
(function () {
    const config = JSON.parse(document.getElementById('saetoNavigation').textContent);
    const lifecycle = window.saetoLifecycle;
    const content = document.getElementById('main-content');
    const status = document.getElementById('navigationStatus');
    const retry = document.getElementById('navigationRetry');
    let current = config, sequence = 0, controller, failed = null;
    const t = config.lang === 'en'
        ? { loading: 'Loading…', error: 'Could not load the page. Your current work is still available.', language: 'Could not change the language. Try again.' }
        : { loading: 'Carregando…', error: 'Não foi possível carregar a página. Seu trabalho atual continua disponível.', language: 'Não foi possível mudar o idioma. Tente novamente.' };
    function route(value) {
        const url = new URL(value, location.href);
        if (url.origin !== location.origin || url.hash) return null;
        const entry = config.routes.find(r => r.url === url.pathname || r.legacy === url.pathname);
        if (entry) {
            // Only pagination is a navigation parameter; prices never enter URLs.
            const page = url.searchParams.get('page');
            return { ...entry, url: entry.url + (entry.key === 'projetos' && /^\d+$/.test(page || '') ? `?page=${page}` : '') };
        }
        if (/^\/projetos\/[0-9a-f-]{36}\/reexecutar\/$/i.test(url.pathname)) {
            return { url: url.pathname, enhanced: true };
        }
        return null;
    }
    function markPage() {
        document.title = `${current.title} · SAETO`;
        document.querySelectorAll('.sidebar a[href]').forEach(link => {
            const item = route(link.href);
            const active = item && item.key === current.menu;
            if (active) {
                link.setAttribute('aria-current', 'page');
                const checkbox = link.closest('.accordion-section')?.querySelector('.accordion-checkbox');
                if (checkbox) checkbox.checked = true;
            } else link.removeAttribute('aria-current');
        });
    }
    function message(text, error = false) {
        status.textContent = text;
        status.hidden = !text;
        status.className = error ? 'alert alert-danger' : 'alert alert-info';
        retry.hidden = !error;
    }
    async function navigate(target, pop = false) {
        if (!target) return;
        const request = ++sequence;
        controller?.abort();
        if (!lifecycle.canLeave()) {
            message('');
            content.removeAttribute('aria-busy');
            failed = null;
            if (pop) history.replaceState({ saeto: true }, '', current.url);
            return;
        }
        const leaveRevision = lifecycle.revision;
        if (!current.enhanced || !target.enhanced) {
            message(t.loading);
            location.assign(target.url);
            return;
        }
        controller = new AbortController();
        failed = { target, pop };
        message(t.loading);
        content.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(target.url, {
                headers: { 'X-SAETO-Fragment': '1' }, signal: controller.signal,
            });
            if (request !== sequence) return;
            if (response.redirected) { location.assign(response.url); return; }
            if (!response.ok) throw new Error('Navigation failed');
            const data = await response.json();
            if (request !== sequence) return;
            if (!data.page || typeof data.html !== 'string') throw new Error('Invalid page');
            if (!data.page.enhanced) { location.assign(target.url); return; }
            // Edits made while loading belong to the page that is still displayed.
            if (lifecycle.revision !== leaveRevision && !lifecycle.canLeave()) throw new Error('Draft unavailable');
            lifecycle.dispose();
            lifecycle.mount(data.page);
            current = data.page;
            window.jQuery(content).html(data.html);
            if (!pop) history.pushState({ saeto: true }, '', target.url);
            else history.replaceState({ saeto: true }, '', target.url);
            current.url = target.url;
            failed = null;
            message('');
            markPage();
            window.saetoCloseMenu?.();
            content.focus();
        } catch (error) {
            if (request !== sequence || error.name === 'AbortError') return;
            if (pop) {
                history.replaceState({ saeto: true }, '', current.url);
                failed.pop = false;
            }
            message(t.error, true);
        } finally {
            if (request === sequence) content.removeAttribute('aria-busy');
        }
    }
    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target || link.hasAttribute('download')) return;
        if (link.hasAttribute('data-saeto-logout')) { lifecycle.clear(); return; }
        const target = route(link.href);
        if (target) { event.preventDefault(); navigate(target); }
    });
    retry.addEventListener('click', () => { if (failed) navigate(failed.target, failed.pop); });
    window.addEventListener('popstate', () => {
        const target = route(location.href);
        if (target) navigate(target, true);
        else location.reload();
    });
    window.updateLanguage = async language => {
        if (!lifecycle.canLeave()) return;
        const leaveRevision = lifecycle.revision;
        const select = document.getElementById('languageSelect');
        select.disabled = true;
        message(t.loading);
        try {
            const response = await fetch('/set_language/', {
                method: 'POST', body: new URLSearchParams({ language }),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!response.ok || !(await response.json()).success) throw new Error();
            if (lifecycle.revision !== leaveRevision && !lifecycle.canLeave()) {
                message('');
                return;
            }
            location.reload();
        } catch (_) { message(t.language); select.value = config.lang; }
        finally { select.disabled = false; }
    };
    history.replaceState({ saeto: true }, '', current.url);
    markPage();
})();
