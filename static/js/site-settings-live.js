(function () {
    if (window.__siteSettingsLiveInitialized) return;
    window.__siteSettingsLiveInitialized = true;

    const POLL_INTERVAL_MS = 8000;
    const STORAGE_KEY = 'site_settings_live_snapshot';
    const CHANNEL_NAME = 'site-settings-live';
    let latestSettings = null;
    let requestInFlight = false;
    let contentVersion = null;
    let contentRequestInFlight = false;
    let channel = null;

    try {
        channel = new BroadcastChannel(CHANNEL_NAME);
    } catch (_error) {
        channel = null;
    }

    function setText(selector, value) {
        if (value === undefined || value === null) return;
        document.querySelectorAll(selector).forEach((element) => {
            const text = String(value);
            if (element.textContent !== text) element.textContent = text;
        });
    }

    function setLinkState(element, url) {
        const enabled = Boolean(String(url || '').trim());
        element.classList.toggle('is-disabled', !enabled);
        element.setAttribute('aria-disabled', enabled ? 'false' : 'true');
        if (enabled) {
            element.setAttribute('href', String(url).trim());
            element.setAttribute('target', '_blank');
            element.setAttribute('rel', 'noopener noreferrer');
            element.removeAttribute('tabindex');
        } else {
            element.removeAttribute('href');
            element.removeAttribute('target');
            element.removeAttribute('rel');
            element.setAttribute('tabindex', '-1');
        }
    }

    function applySocialLinks(settings) {
        const links = settings.social_links || {};
        ['facebook', 'instagram', 'twitter', 'youtube'].forEach((network) => {
            document.querySelectorAll(`[data-live-social="${network}"]`).forEach((element) => {
                setLinkState(element, links[network]);
            });
        });
    }

    function applyContactSettings(settings) {
        setText('[data-live-contact-email]', settings.contact_email);
        setText('[data-live-contact-phone]', settings.contact_phone);
        setText('[data-live-contact-address]', settings.contact_address);

        document.querySelectorAll('[data-live-email-link]').forEach((element) => {
            element.href = `mailto:${settings.contact_email || ''}`;
        });
        document.querySelectorAll('[data-live-whatsapp-link]').forEach((element) => {
            element.href = settings.contact_whatsapp_url || '#';
            const label = settings.contact_phone || '';
            element.setAttribute('aria-label', `WhatsApp ${label}`.trim());
            element.setAttribute('title', `WhatsApp ${label}`.trim());
        });
    }

    function applyThemeSettings(settings) {
        const root = document.documentElement;
        const primary = settings.primary_color || '#3a86ff';
        const secondary = settings.secondary_color || '#8338ec';
        root.style.setProperty('--primary-color', primary);
        root.style.setProperty('--secondary-color', secondary);
        root.style.setProperty('--primary-rgb', settings.primary_rgb || '58, 134, 255');
        root.style.setProperty('--secondary-rgb', settings.secondary_rgb || '131, 56, 236');

        document.querySelectorAll('meta[name="theme-color"], meta[name="msapplication-TileColor"]').forEach((meta) => {
            meta.setAttribute('content', primary);
        });

        if (!document.body) return;
        const darkModeEnabled = settings.enable_dark_mode !== false;
        document.body.dataset.darkModeEnabled = darkModeEnabled ? 'true' : 'false';
        document.querySelectorAll('.dark-mode').forEach((toggle) => {
            toggle.hidden = !darkModeEnabled;
            toggle.setAttribute('aria-hidden', darkModeEnabled ? 'false' : 'true');
        });
        if (!darkModeEnabled && !document.body.classList.contains('admin-page')) {
            document.body.setAttribute('data-theme', 'light');
        }
    }

    function applyAnalytics(settings) {
        const measurementId = String(settings.google_analytics || '').trim();
        if (!measurementId) {
            document.getElementById('site-live-analytics-loader')?.remove();
            return;
        }

        let loader = document.getElementById('site-live-analytics-loader');
        if (!loader) {
            loader = document.createElement('script');
            loader.id = 'site-live-analytics-loader';
            loader.async = true;
            document.head.appendChild(loader);
        }
        const nextSource = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
        if (loader.src !== nextSource) loader.src = nextSource;

        window.dataLayer = window.dataLayer || [];
        window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
        window.gtag('js', new Date());
        window.gtag('config', measurementId);
    }

    function getMaintenanceOverlay() {
        let overlay = document.getElementById('live-maintenance-overlay');
        if (overlay) return overlay;

        overlay = document.createElement('div');
        overlay.id = 'live-maintenance-overlay';
        overlay.setAttribute('role', 'alertdialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.innerHTML = `
            <div class="live-maintenance-card">
                <i class="fas fa-tools" aria-hidden="true"></i>
                <h1>Estamos em manutenção</h1>
                <p>Estamos realizando melhorias. Tente novamente em alguns instantes.</p>
                <a data-live-email-link href="#"><i class="fas fa-envelope"></i> <span data-live-contact-email></span></a>
            </div>
        `;
        const style = document.createElement('style');
        style.id = 'live-maintenance-overlay-style';
        style.textContent = `
            #live-maintenance-overlay{position:fixed;inset:0;z-index:2147483647;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 20% 20%,rgba(var(--primary-rgb),.34),transparent 34%),linear-gradient(135deg,#101827,#1f2937);color:#fff}
            .live-maintenance-card{width:min(560px,100%);padding:42px 30px;text-align:center;border:1px solid rgba(255,255,255,.14);border-radius:24px;background:rgba(15,23,42,.88);box-shadow:0 30px 80px rgba(0,0,0,.38)}
            .live-maintenance-card>i{font-size:3rem;color:var(--primary-color);margin-bottom:18px}.live-maintenance-card h1{margin:0 0 12px;font-size:clamp(1.8rem,5vw,2.7rem)}.live-maintenance-card p{margin:0 0 24px;color:#cbd5e1;line-height:1.65}.live-maintenance-card a{display:inline-flex;align-items:center;gap:9px;color:#fff;text-decoration:none;padding:11px 16px;border-radius:12px;background:var(--primary-color)}
        `;
        document.head.appendChild(style);
        document.body.appendChild(overlay);
        return overlay;
    }

    function applyMaintenanceMode(settings) {
        if (!document.body || document.body.dataset.isAdmin === 'true') return;

        const isMaintenancePage = document.body.dataset.liveMaintenancePage === 'true';
        const isLoginPage = /^\/(login|admin(?:\/|$))/.test(window.location.pathname);
        if (isMaintenancePage && settings.maintenance_mode === false) {
            window.location.replace('/');
            return;
        }
        if (isLoginPage) return;

        if (settings.maintenance_mode === true) {
            getMaintenanceOverlay();
            document.body.style.overflow = 'hidden';
            applyContactSettings(settings);
        } else {
            document.getElementById('live-maintenance-overlay')?.remove();
            document.getElementById('live-maintenance-overlay-style')?.remove();
            document.body.style.overflow = '';
        }
    }

    function applyDocumentIdentity(settings) {
        const previousName = document.documentElement.dataset.siteName || '';
        const nextName = String(settings.site_name || previousName || 'Mundo da Informática');
        if (previousName && nextName !== previousName && document.title.includes(previousName)) {
            document.title = document.title.replace(previousName, nextName);
        }
        document.documentElement.dataset.siteName = nextName;
        setText('[data-live-setting="site_name"]', nextName);
        setText('[data-live-setting="site_description"]', settings.site_description);
        setText('[data-live-setting="footer_description"]', settings.footer_description || settings.site_description);
        setText('[data-live-setting="footer_text"]', settings.footer_text);
        setText('[data-current-year]', settings.current_year || new Date().getFullYear());
        setText('[data-plan-name="free"]', settings.plan_name_free);
        setText('[data-plan-name="premium"]', settings.plan_name_premium);
        setText('[data-plan-name="vip"]', settings.plan_name_vip);
        setText('[data-live-setting="home_hero_subtitle"]', settings.home_hero_subtitle);

        const heroTitle = document.querySelector('[data-live-setting="home_hero_title"]');
        if (heroTitle && settings.home_hero_title) {
            const nextHeroTitle = String(settings.home_hero_title).trim();
            const previousHeroTitle = String(heroTitle.dataset.heroTitle || '').trim();
            heroTitle.dataset.heroTitle = nextHeroTitle;
            heroTitle.setAttribute('aria-label', nextHeroTitle);

            if (nextHeroTitle && nextHeroTitle !== previousHeroTitle) {
                if (window.gsap) window.gsap.killTweensOf(heroTitle.querySelectorAll('*'));
                heroTitle.textContent = nextHeroTitle;
                window.requestAnimationFrame(() => {
                    if (typeof window.initHeroSplitText === 'function') window.initHeroSplitText();
                });
            }
        }
        document.querySelectorAll('meta[name="description"]').forEach((meta) => {
            meta.setAttribute('content', settings.site_description || '');
        });
        document.querySelectorAll('meta[name="author"]').forEach((meta) => {
            meta.setAttribute('content', nextName);
        });
    }

    function applySettings(settings) {
        if (!settings || typeof settings !== 'object') return;
        latestSettings = settings;
        applyDocumentIdentity(settings);
        applyThemeSettings(settings);
        applyContactSettings(settings);
        applySocialLinks(settings);
        applyAnalytics(settings);
        applyMaintenanceMode(settings);
        window.dispatchEvent(new CustomEvent('siteSettingsApplied', { detail: { settings } }));
    }

    function publishSettings(settings) {
        applySettings(settings);
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ settings, updatedAt: Date.now() }));
        } catch (_error) {
            // BroadcastChannel e polling continuam disponíveis.
        }
        channel?.postMessage({ settings });
    }

    async function refreshSettings() {
        if (requestInFlight) return;
        requestInFlight = true;
        try {
            const response = await fetch('/api/site-settings', {
                credentials: 'same-origin',
                cache: 'no-store',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) return;
            const data = await response.json().catch(() => ({}));
            if (data.success && data.settings) applySettings(data.settings);
        } catch (_error) {
            // A próxima sincronização tentará novamente.
        } finally {
            requestInFlight = false;
        }
    }

    function isPublicContentPage() {
        if (document.body?.classList.contains('admin-page')) return false;
        const path = window.location.pathname;
        return path === '/'
            || path === '/posts'
            || path.startsWith('/post/')
            || path.startsWith('/categoria/')
            || path.startsWith('/subcategoria/')
            || path.startsWith('/buscar')
            || path.startsWith('/search')
            || (/^\/[^/]+\/[^/]+\/?$/.test(path) && !path.startsWith('/api/'));
    }

    function hasActiveEditableField() {
        const active = document.activeElement;
        return active instanceof HTMLElement && (
            active.matches('input, textarea, select, [contenteditable="true"]')
            || active.isContentEditable
        );
    }

    async function refreshPublicContent() {
        if (!isPublicContentPage() || document.hidden || contentRequestInFlight) return;
        contentRequestInFlight = true;
        try {
            const response = await fetch('/api/public-content-version', {
                credentials: 'same-origin',
                cache: 'no-store',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!response.ok) return;
            const data = await response.json().catch(() => ({}));
            const nextVersion = String(data.version || '');
            if (!data.success || !nextVersion) return;
            if (contentVersion === null) {
                contentVersion = nextVersion;
                return;
            }
            if (contentVersion === nextVersion || hasActiveEditableField()) return;

            const loader = window.ensureDynamicLoader?.() || window.dynamicLoader;
            if (!loader?.refreshCurrentPage) return;
            await loader.refreshCurrentPage();
            contentVersion = nextVersion;
            window.dispatchEvent(new CustomEvent('publicContentUpdated', { detail: { version: nextVersion } }));
        } catch (_error) {
            // Uma falha transitória não deve interromper a navegação do usuário.
        } finally {
            contentRequestInFlight = false;
        }
    }

    window.applySiteSettings = applySettings;
    window.publishSiteSettings = publishSettings;
    window.refreshSiteSettings = refreshSettings;
    window.refreshPublicContent = refreshPublicContent;

    channel?.addEventListener('message', (event) => applySettings(event.data?.settings));
    window.addEventListener('storage', (event) => {
        if (event.key !== STORAGE_KEY || !event.newValue) return;
        try {
            applySettings(JSON.parse(event.newValue).settings);
        } catch (_error) {
            refreshSettings();
        }
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            refreshSettings();
            refreshPublicContent();
        }
    });
    document.addEventListener('pageLoaded', () => latestSettings ? applySettings(latestSettings) : refreshSettings());
    document.addEventListener('adminPageLoaded', () => latestSettings ? applySettings(latestSettings) : refreshSettings());

    refreshSettings();
    refreshPublicContent();
    window.setInterval(refreshSettings, POLL_INTERVAL_MS);
    window.setInterval(refreshPublicContent, POLL_INTERVAL_MS);
})();
