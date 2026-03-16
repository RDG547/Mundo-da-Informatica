(function () {
    function getMetaCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function getCookie(name) {
        const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[2]) : '';
    }

    function getCsrfToken() {
        return getMetaCsrfToken() || getCookie('csrf_token') || '';
    }

    function isUnsafeMethod(method) {
        return !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes((method || 'GET').toUpperCase());
    }

    function isSameOrigin(url) {
        try {
            const parsed = new URL(url, window.location.origin);
            return parsed.origin === window.location.origin;
        } catch (error) {
            return true;
        }
    }

    function ensureFormTokens() {
        const token = getCsrfToken();
        if (!token) return;

        document.querySelectorAll('form').forEach((form) => {
            const method = (form.getAttribute('method') || 'GET').toUpperCase();
            if (!isUnsafeMethod(method)) return;
            if (form.querySelector('input[name="csrf_token"]')) return;

            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'csrf_token';
            input.value = token;
            form.appendChild(input);
        });
    }

    const originalFetch = window.fetch;
    window.fetch = function (resource, options = {}) {
        const requestUrl = typeof resource === 'string' ? resource : (resource && resource.url) || window.location.href;
        const method = (options.method || (resource && resource.method) || 'GET').toUpperCase();

        if (isUnsafeMethod(method) && isSameOrigin(requestUrl)) {
            const headers = new Headers(options.headers || (resource && resource.headers) || {});
            const token = getCsrfToken();
            if (token && !headers.has('X-CSRFToken')) {
                headers.set('X-CSRFToken', token);
            }
            options.headers = headers;
            if (!options.credentials) {
                options.credentials = 'same-origin';
            }
        }

        return originalFetch(resource, options);
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', ensureFormTokens);
    } else {
        ensureFormTokens();
    }

    document.addEventListener('pageLoaded', ensureFormTokens);
    window.csrfUtils = { getCsrfToken, ensureFormTokens };
})();
