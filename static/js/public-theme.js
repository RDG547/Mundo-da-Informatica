(function () {
    if (window.PublicTheme) return;

    const STORAGE_KEY = 'mundoinformatica_theme';

    function preferredTheme() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved === 'dark' || saved === 'light') return saved;
        return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function updateControls(theme) {
        document.querySelectorAll('.dark-mode').forEach((button) => {
            const dark = theme === 'dark';
            button.setAttribute('aria-pressed', dark ? 'true' : 'false');
            button.setAttribute('aria-label', dark ? 'Ativar tema claro' : 'Ativar tema escuro');
            button.setAttribute('title', dark ? 'Ativar tema claro' : 'Ativar tema escuro');
            button.innerHTML = `<i class="fas ${dark ? 'fa-sun' : 'fa-moon'}" aria-hidden="true"></i>`;
        });
    }

    function setTheme(theme, persist = false) {
        const normalized = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.dataset.theme = normalized;
        if (document.body) document.body.dataset.theme = normalized;
        if (persist) localStorage.setItem(STORAGE_KEY, normalized);
        updateControls(normalized);
        document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: normalized } }));
        return normalized;
    }

    function bindControls() {
        const theme = document.documentElement.dataset.theme || preferredTheme();
        if (document.body) document.body.dataset.theme = theme;
        document.querySelectorAll('.dark-mode').forEach((button) => {
            if (button.dataset.publicThemeBound === 'true') return;
            button.dataset.publicThemeBound = 'true';
            button.addEventListener('click', () => {
                if (document.body?.dataset.darkModeEnabled === 'false') return;
                setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', true);
            });
        });
        updateControls(theme);
    }

    window.PublicTheme = { init: bindControls, setTheme, preferredTheme };
    setTheme(document.documentElement.dataset.theme || preferredTheme());

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindControls);
    else bindControls();
    document.addEventListener('pageLoaded', bindControls);

    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', (event) => {
        if (!localStorage.getItem(STORAGE_KEY)) setTheme(event.matches ? 'dark' : 'light');
    });
})();
