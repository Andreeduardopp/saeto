/* One lifecycle per mounted page. Drafts are tab-local, versioned and user-scoped. */
(function () {
    const config = JSON.parse(document.getElementById('saetoNavigation').textContent);
    let page = config, cleanups = [], draft = null, dirty = false, unavailable = false, revision = 0;
    const prefix = 'saeto:draft:v1:';
    const key = () => `${prefix}${config.user}:${page.key}:${page.project || 'new'}`;
    const warning = () => config.lang === 'en'
        ? 'Draft storage is unavailable. Leaving this page may lose your edits. Continue?'
        : 'O armazenamento de rascunhos está indisponível. Sair desta página pode perder suas edições. Continuar?';
    function flush() {
        if (!draft || !dirty) return true;
        try {
            sessionStorage.setItem(key(), JSON.stringify({ version: 1, data: draft.capture() }));
            unavailable = false;
            return true;
        } catch (_) {
            unavailable = true;
            draft.warn?.(warning());
            return false;
        }
    }
    function clear() {
        try {
            for (const name of Object.keys(sessionStorage)) {
                if (name.startsWith(prefix)) sessionStorage.removeItem(name);
            }
        } catch (_) { /* An unavailable store contains no recoverable draft here. */ }
        dirty = false;
    }
    window.saetoLifecycle = {
        get page() { return page; },
        get revision() { return revision; },
        register(cleanup) { cleanups.push(cleanup); },
        attachDraft(hooks) {
            draft = hooks;
            try {
                const stored = JSON.parse(sessionStorage.getItem(key()) || 'null');
                if (stored?.version === 1 && hooks.restore(stored.data)) dirty = true;
            } catch (_) { unavailable = true; }
            // Check write access now, before any edits or navigation.
            try {
                sessionStorage.setItem('saeto:probe', '1');
                sessionStorage.removeItem('saeto:probe');
            } catch (_) { unavailable = true; hooks.warn?.(warning()); }
        },
        changed() { dirty = true; revision++; },
        flush,
        canLeave() { return flush() || window.confirm(warning()); },
        discard() {
            try { sessionStorage.removeItem(key()); } catch (_) { /* no stored draft */ }
            dirty = false;
        },
        clear,
        mount(next) { page = next; draft = null; dirty = false; unavailable = false; },
        dispose() {
            flush();
            cleanups.forEach(cleanup => cleanup());
            cleanups = [];
            if (window.Chart?.instances) {
                Object.values(window.Chart.instances).forEach(chart => chart.destroy());
            }
            draft = null;
        },
    };
    window.addEventListener('pagehide', flush);
    // A browser-cached document must recheck login and session language on Back.
    window.addEventListener('pageshow', event => {
        if (event.persisted) window.location.reload();
    });
    window.addEventListener('beforeunload', event => {
        if (!flush() && dirty && unavailable) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
})();
