(function () {
    let retryTimer = null;
    let retryCount = 0;
    const MAX_RETRIES = 20;

    function readFirebaseConfig() {
        const configScript = document.getElementById('firebase-config');
        if (!configScript) return null;

        try {
            const parsed = JSON.parse(configScript.textContent || '{}');
            if (!parsed || !parsed.apiKey || !parsed.authDomain || !parsed.projectId || !parsed.appId) {
                return null;
            }
            return parsed;
        } catch (error) {
            console.error('[GOOGLE-AUTH] Config Firebase inválida:', error);
            return null;
        }
    }

    function setButtonsState(disabled, text) {
        document.querySelectorAll('[data-google-auth-button]').forEach((btn) => {
            btn.disabled = disabled;
            if (disabled) {
                btn.classList.add('is-disabled');
                if (text) btn.setAttribute('title', text);
            } else {
                btn.classList.remove('is-disabled');
                btn.removeAttribute('title');
            }
        });
    }

    function showError(message) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, 'error');
            return;
        }
        alert(message);
    }

    async function authenticateWithBackend(idToken) {
        const csrfToken = (window.csrfUtils && window.csrfUtils.getCsrfToken && window.csrfUtils.getCsrfToken())
            || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            || '';

        const next = new URLSearchParams(window.location.search).get('next') || '';

        const response = await fetch('/auth/google', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            },
            credentials: 'same-origin',
            body: JSON.stringify({ idToken, next })
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || 'Falha na autenticação com Google.');
        }
        return data;
    }

    async function initializeGoogleAuth() {
        const buttons = document.querySelectorAll('[data-google-auth-button]');
        if (!buttons.length) return;

        const firebaseConfig = readFirebaseConfig();
        if (!firebaseConfig) {
            setButtonsState(true, 'Google Sign-In não configurado no servidor.');
            return;
        }

        if (typeof firebase === 'undefined' || !firebase?.auth) {
            // Em navegação dinâmica, scripts externos podem carregar após este arquivo.
            if (retryCount < MAX_RETRIES) {
                retryCount += 1;
                setButtonsState(true, 'Carregando autenticação Google...');
                clearTimeout(retryTimer);
                retryTimer = setTimeout(initializeGoogleAuth, 200);
            } else {
                setButtonsState(true, 'Biblioteca do Firebase não carregada.');
            }
            return;
        }

        retryCount = 0;
        clearTimeout(retryTimer);

        if (!firebase.apps.length) {
            firebase.initializeApp(firebaseConfig);
        }

        const auth = firebase.auth();
        const provider = new firebase.auth.GoogleAuthProvider();
        provider.setCustomParameters({ prompt: 'select_account' });

        buttons.forEach((button) => {
            if (button.dataset.googleBound === 'true') return;
            button.dataset.googleBound = 'true';

            button.addEventListener('click', async function (event) {
                event.preventDefault();

                const originalLabel = button.innerHTML;
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Conectando...';

                try {
                    const result = await auth.signInWithPopup(provider);
                    const idToken = await result.user.getIdToken(true);
                    const backendResponse = await authenticateWithBackend(idToken);

                    if (backendResponse.redirect_url) {
                        window.location.href = backendResponse.redirect_url;
                        return;
                    }

                    window.location.href = '/';
                } catch (error) {
                    console.error('[GOOGLE-AUTH] Erro:', error);
                    showError(error.message || 'Não foi possível entrar com Google.');
                    button.disabled = false;
                    button.innerHTML = originalLabel;
                }
            });
        });

        // Libera botão caso tenha sido desabilitado durante tentativas de retry
        setButtonsState(false);
    }

    function bootGoogleAuth() {
        clearTimeout(retryTimer);
        retryCount = 0;
        initializeGoogleAuth();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootGoogleAuth);
    } else {
        bootGoogleAuth();
    }

    // Reexecutar após carregamento dinâmico de páginas (dynamic-loading.js)
    document.addEventListener('pageLoaded', () => {
        setTimeout(bootGoogleAuth, 60);
    });
})();
