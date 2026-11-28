/**
 * Dynamic Page Loading System
 * Loads page content dynamically without full page reload
 */

// Verificar se já foi carregado
if (typeof window.DynamicLoader !== 'undefined') {
    console.log('dynamic-loading.js já carregado, ignorando redeclaração');
} else {

    window.DynamicLoader = class DynamicLoader {
        constructor() {
            this.currentUrl = window.location.href;
            this.isLoading = false;
            this.cache = new Map();
            this.cacheTtlMs = 15000;
            this.loadingDelayMs = 90;
            this.loadingTimer = null;
            this.fullReloadPaths = new Set();
            this.init();
        }

        init() {
            this.installReadyEventFallbacks();
            this.bindEvents();
            this.createLoadingIndicator();
            this.bindLoadingIndicatorBounds();
            this.handleBrowserNavigation();

            // Initialize page styles for current page
            this.initializeCurrentPageStyles();
        }

        bindLoadingIndicatorBounds() {
            if (window.__dynamicLoaderBoundsHandler) return;
            window.__dynamicLoaderBoundsHandler = () => {
                const loader = document.getElementById('dynamic-loader');
                if (loader && getComputedStyle(loader).display !== 'none') {
                    this.attachLoaderToMain(loader);
                }
            };
            window.addEventListener('scroll', window.__dynamicLoaderBoundsHandler, { passive: true });
            window.addEventListener('resize', window.__dynamicLoaderBoundsHandler, { passive: true });
        }

        installReadyEventFallbacks() {
            if (window.__dynamicReadyFallbacksInstalled) {
                return;
            }

            const invokeListener = (listener, target, eventName) => {
                const event = new Event(eventName);
                setTimeout(() => {
                    try {
                        if (typeof listener === 'function') {
                            listener.call(target, event);
                        } else if (listener && typeof listener.handleEvent === 'function') {
                            listener.handleEvent(event);
                        }
                    } catch (error) {
                        console.error(`[DYNAMIC-LOADING] Erro ao disparar ${eventName}:`, error);
                    }
                }, 0);
            };

            const originalDocumentAddEventListener = document.addEventListener.bind(document);
            document.addEventListener = (type, listener, options) => {
                if (type === 'DOMContentLoaded' && document.readyState !== 'loading') {
                    invokeListener(listener, document, 'DOMContentLoaded');
                    return;
                }

                originalDocumentAddEventListener(type, listener, options);
            };

            const originalWindowAddEventListener = window.addEventListener.bind(window);
            window.addEventListener = (type, listener, options) => {
                if (type === 'load' && document.readyState === 'complete') {
                    invokeListener(listener, window, 'load');
                    return;
                }

                originalWindowAddEventListener(type, listener, options);
            };

            window.__dynamicReadyFallbacksInstalled = true;
        }

        initializeCurrentPageStyles() {
            // DON'T call loadPageStyles here!
            // On initial page load (F5), the server already loaded the correct CSS with Jinja2 conditions
            // loadPageStyles should ONLY be called during dynamic navigation
            const currentPath = window.location.pathname;

            // Initialize components for current page
            if (currentPath === '/faq' || document.querySelector('.faq-section')) {
                setTimeout(() => this.initializeFAQ(), 100);
            } else if (currentPath === '/contact' || currentPath === '/contato' || document.querySelector('.contact-section')) {
                setTimeout(() => this.initializeContactForm(), 100);
            } else if (currentPath === '/about' || currentPath === '/sobre' || document.querySelector('.about-hero')) {
                setTimeout(() => this.initializeAboutPage(), 100);
            } else if (currentPath.startsWith('/categoria/') || currentPath.startsWith('/subcategoria/') || document.querySelector('.category-hero')) {
                setTimeout(() => this.initializeCategoryPage(), 100);
            } else if (currentPath.startsWith('/profile') || document.querySelector('.profile-hero')) {
                // Profile page initialization is already handled in profile-page.js
                // No need for timeout, it will reinitialize itself
            } else if (currentPath.startsWith('/post/') || document.querySelector('.post-hero-section') || (currentPath.split('/').length === 3 && currentPath.split('/')[1] && currentPath.split('/')[2])) {
                setTimeout(() => this.initializePostPage(), 100);
            } else if (currentPath === '/termos-de-uso' || document.querySelector('.legal-page-section')) {
                setTimeout(() => this.initializeLegalPage(), 100);
            } else if (currentPath === '/politica-de-privacidade' || document.querySelector('.legal-page-section')) {
                setTimeout(() => this.initializeLegalPage(), 100);
            } else if (currentPath === '/' || currentPath === '/home' || document.querySelector('#hero-particles')) {
                setTimeout(() => this.initializeHomePage(), 100);
            } else if (currentPath === '/planos' || currentPath === '/plans' || document.querySelector('.plans-section')) {
                setTimeout(() => {
                    if (typeof window.initializePlansPage === 'function') {
                        window.initializePlansPage();
                    }
                }, 100);
            }
        }

        bindEvents() {
            // Intercept all internal links - use capture phase to execute before other listeners
            document.addEventListener('click', (e) => {
                // As miniaturas usam o link do post como fallback, mas o clique
                // principal pertence ao lightbox global. Deixar o evento seguir
                // evita que a navegação dinâmica cancele a ampliação da imagem.
                if (e.target.closest('.post-card .post-image img, .related-post-image img, .most-used-thumbnail, .download-title-thumb:not(.download-title-thumb-placeholder)')) {
                    return;
                }
                const link = e.target.closest('a');
                // Mobile navbar group triggers expand in place, not through the AJAX router.
                if (window.matchMedia('(max-width: 1100px)').matches && link?.matches('#primary-navigation .dropdown > .dropdown-toggle')) return;
                // The capture-phase router stops other click handlers; close mobile menus here first.
                if (link?.closest('#primary-navigation')) window.mdiCloseMobileNav?.();
                if (link?.closest('#adminSidebar')) window.mdiCloseMobileAdmin?.();
                const fullReloadUrl = this.getFullReloadUrl(link);
                if (fullReloadUrl) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    this.navigateWithFullPageLoader(fullReloadUrl);
                    return false;
                }

                if (this.shouldInterceptLink(link)) {
                    e.preventDefault();
                    e.stopPropagation(); // Prevent other click handlers
                    e.stopImmediatePropagation(); // Prevent all other handlers
                    this.loadPage(link.href);
                    return false;
                }
            }, true); // Use capture phase

            // Antecipar o HTML quando o usuário demonstra intenção de navegar.
            // Isso elimina boa parte da espera sem alterar a navegação dinâmica.
            document.addEventListener('pointerover', (event) => {
                const link = event.target.closest?.('a[href]');
                if (!this.shouldInterceptLink(link) || link.dataset.dynamicPrefetchPending === 'true') return;
                link.dataset.dynamicPrefetchPending = 'true';
                link._dynamicPrefetchTimer = window.setTimeout(() => {
                    delete link.dataset.dynamicPrefetchPending;
                    link._dynamicPrefetchTimer = null;
                    this.preloadPage(link.href);
                }, 60);
            }, { passive: true });

            document.addEventListener('pointerout', (event) => {
                const link = event.target.closest?.('a[href]');
                if (!link || link.contains(event.relatedTarget) || !link._dynamicPrefetchTimer) return;
                window.clearTimeout(link._dynamicPrefetchTimer);
                link._dynamicPrefetchTimer = null;
                delete link.dataset.dynamicPrefetchPending;
            }, { passive: true });

            document.addEventListener('focusin', (event) => {
                const link = event.target.closest?.('a[href]');
                if (this.shouldInterceptLink(link)) this.preloadPage(link.href);
            });

            // Intercept form submissions
            document.addEventListener('submit', (e) => {
                const form = e.target;
                if (this.shouldInterceptForm(form)) {
                    e.preventDefault();
                    this.submitForm(form);
                }
            });
        }

        getFullReloadUrl(link) {
            if (!link || !link.href) return '';
            if (link.hostname !== window.location.hostname) return '';
            if (link.target === '_blank' || link.download) return '';
            if (link.href.includes('/download/') || link.href.includes('/logout')) return '';

            const url = new URL(link.href);
            const currentIsAdmin = window.location.pathname.startsWith('/admin');
            const targetIsAdmin = url.pathname.startsWith('/admin');

            if (currentIsAdmin !== targetIsAdmin || link.dataset.fullReload === 'true') {
                return url.href;
            }

            return '';
        }

        navigateWithFullPageLoader(url) {
            if (this.isLoading) return;
            this.isLoading = true;

            const preloader = document.querySelector('.preloader');
            if (preloader) {
                preloader.dataset.hidden = 'false';
                preloader.classList.remove('fade-out');
                preloader.style.display = 'flex';
                preloader.style.opacity = '1';
                preloader.style.visibility = 'visible';
            } else {
                const loader = document.getElementById('dynamic-loader');
                if (loader) {
                    loader.style.top = '0';
                    loader.style.left = '0';
                    loader.style.width = '100vw';
                    loader.style.height = '100vh';
                    loader.style.display = 'flex';
                }
            }

            window.setTimeout(() => {
                window.location.href = url;
            }, 80);
        }

        shouldInterceptLink(link) {
            if (!link || !link.href) return false;

            // Don't intercept external links
            if (link.hostname !== window.location.hostname) return false;

            // Don't intercept links with target="_blank"
            if (link.target === '_blank') return false;

            // Don't intercept download links
            if (link.download) return false;

            // DON'T INTERCEPT DOWNLOAD ROUTES - handled by download-control.js
            if (link.href.includes('/download/')) return false;

            // Don't intercept anchor links on same page
            if (link.href.includes('#') && link.pathname === window.location.pathname) return false;

            // Don't intercept logout links
            if (link.href.includes('/logout')) return false;

            if (link.dataset.vipLink === 'true' && link.dataset.vipAccess !== 'vip') {
                return false;
            }

            if (link.dataset.adminPostsPartial === 'true') {
                return false;
            }

            const url = new URL(link.href);
            const currentIsAdmin = window.location.pathname.startsWith('/admin');
            const targetIsAdmin = url.pathname.startsWith('/admin');

            if (currentIsAdmin !== targetIsAdmin) {
                return false;
            }

            if (link.dataset.noDynamic === 'true') return false;

            if (this.shouldForceFullReload(url.pathname)) {
                return false;
            }

            return true;
        }

        shouldForceFullReload(pathname) {
            return this.fullReloadPaths.has(pathname);
        }

        shouldInterceptForm(form) {
            const action = form.action || window.location.href;
            const actionPath = new URL(action, window.location.origin).pathname;

            // No admin mantemos submit tradicional para evitar conflito com formulários complexos
            if (window.location.pathname.startsWith('/admin') || actionPath.startsWith('/admin')) return false;
            // Não interceptar formulários de upload
            if (form.enctype === 'multipart/form-data') return false;
            // Não interceptar forms com target="_blank"
            if (form.target === '_blank') return false;
            // Não interceptar o formulário de login
            if (form.id === 'loginForm' || form.action.includes('/login')) return false;
            // Não interceptar o formulário do chat em tempo real
            if (form.id === 'chat-message-form') return false;
            // Não interceptar o formulário de comentários, pois ele já possui tratamento AJAX próprio
            if (form.id === 'commentForm') return false;
            // Não interceptar formulários de perfil que já possuem tratamento AJAX próprio
            if (form.id === 'editProfileForm' || form.id === 'changePasswordForm') return false;
            return true;
        }

        async loadPage(url, options = {}) {
            const { updateHistory = true, force = false, preserveScroll = false } = options;
            // Prevent loading same page or loading while already loading
            if (this.isLoading || (!force && url === this.currentUrl)) {
                return;
            }

            const targetUrl = new URL(url, window.location.origin);
            const currentPath = window.location.pathname;
            const targetPath = targetUrl.pathname;
            const previousScrollPosition = preserveScroll ? window.scrollY : 0;

            this.isLoading = true;
            this.showLoading();

            try {
                const content = await this.fetchPageContent(url, { force });

                if (updateHistory) {
                    this.updateUrl(url);
                } else {
                    this.currentUrl = url;
                }

                await this.updatePage(content, url, { preserveScroll });
                if (preserveScroll) {
                    window.requestAnimationFrame(() => window.scrollTo({ top: previousScrollPosition, behavior: 'auto' }));
                } else {
                    this.scrollToHashTarget(url);
                }

            } catch (error) {
                console.error('Error loading page:', error);
                // If a post/category being viewed was removed by an admin, keep the
                // live update inside the SPA and take the visitor to the catalogue.
                if (force && updateHistory === false && error.status === 404 && targetPath !== '/posts') {
                    try {
                        const fallbackUrl = '/posts';
                        const fallbackContent = await this.fetchPageContent(fallbackUrl, { force: true });
                        this.currentUrl = fallbackUrl;
                        history.replaceState({ url: fallbackUrl }, '', fallbackUrl);
                        await this.updatePage(fallbackContent, fallbackUrl, { preserveScroll: false });
                        return;
                    } catch (fallbackError) {
                        console.error('Error loading catalogue fallback:', fallbackError);
                    }
                }
                // Fallback to normal navigation
                window.location.href = url;
            } finally {
                this.isLoading = false;
                this.hideLoading();
            }
        }

        normalizeCacheKey(url) {
            const normalized = new URL(url, window.location.origin);
            normalized.hash = '';
            return normalized.href;
        }

        async fetchPageContent(url, options = {}) {
            const { force = false } = options;
            const cacheKey = this.normalizeCacheKey(url);
            const cached = this.cache.get(cacheKey);
            if (!force && cached && Date.now() - cached.createdAt < this.cacheTtlMs) {
                return cached.pageData;
            }

            const response = await fetch(url, {
                credentials: 'same-origin',
                cache: force ? 'no-store' : 'default',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                const error = new Error(`HTTP ${response.status}`);
                error.status = response.status;
                throw error;
            }

            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            // For admin pages, get the admin-content-wrapper
            const isAdminPage = url.includes('/admin');
            let content;

            if (isAdminPage) {
                content = doc.querySelector('.admin-content-wrapper');
            }

            if (!content) {
                content = doc.querySelector('main') ||
                    doc.querySelector('.main-content-container') ||
                    doc.querySelector('.container') ||
                    doc.body;
            }

            const pageData = {
                title: doc.title,
                content: content,
                navigation: doc.querySelector('#primary-navigation')?.innerHTML || '',
                head: {
                    canonical: doc.querySelector('link[rel="canonical"]')?.href || '',
                    metas: [
                        'meta[name="description"]',
                        'meta[name="robots"]',
                        'meta[property="og:type"]',
                        'meta[property="og:url"]',
                        'meta[property="og:title"]',
                        'meta[property="og:description"]',
                        'meta[property="og:image"]',
                        'meta[property="og:site_name"]',
                        'meta[property="og:locale"]',
                        'meta[name="twitter:card"]',
                        'meta[name="twitter:title"]',
                        'meta[name="twitter:description"]',
                        'meta[name="twitter:image"]'
                    ].map((selector) => ({
                        selector,
                        html: doc.querySelector(selector)?.outerHTML || ''
                    })),
                    structuredData: Array.from(doc.querySelectorAll('script[type="application/ld+json"]'))
                        .map((script) => script.textContent)
                },
                scripts: Array.from(doc.querySelectorAll('script[src]')).filter(script =>
                    !script.hasAttribute('data-static-base-script') && !content.contains(script)
                ),
                inlineScripts: Array.from(doc.querySelectorAll('script:not([src])')).filter(script =>
                    !script.hasAttribute('data-static-base-script')
                    && script.type !== 'application/json'
                    && !content.contains(script)
                ),
                styles: Array.from(doc.querySelectorAll('link[rel="stylesheet"]')).filter(style =>
                    !style.hasAttribute('data-static-base-style')
                ),
                inlineStyles: Array.from(doc.querySelectorAll('style')).filter(style =>
                    !style.hasAttribute('data-static-base-style')
                )
            };

            this.cache.set(cacheKey, { createdAt: Date.now(), pageData });
            return pageData;
        }

        updateHeadMetadata(head = {}) {
            let canonical = document.querySelector('link[rel="canonical"]');
            if (head.canonical) {
                if (!canonical) {
                    canonical = document.createElement('link');
                    canonical.rel = 'canonical';
                    document.head.appendChild(canonical);
                }
                canonical.href = head.canonical;
            }

            (head.metas || []).forEach(({ selector, html }) => {
                const current = document.querySelector(selector);
                if (!html) {
                    current?.remove();
                    return;
                }
                const parsed = new DOMParser().parseFromString(`<head>${html}</head>`, 'text/html').head.firstElementChild;
                if (!parsed) return;
                if (current) current.replaceWith(parsed);
                else document.head.appendChild(parsed);
            });

            document.querySelectorAll('script[type="application/ld+json"]').forEach((script) => script.remove());
            (head.structuredData || []).forEach((json) => {
                const script = document.createElement('script');
                script.type = 'application/ld+json';
                script.textContent = json;
                document.head.appendChild(script);
            });
        }

        scrollToHashTarget(url) {
            const hash = new URL(url, window.location.origin).hash;
            if (!hash) return;

            requestAnimationFrame(() => {
                const target = document.querySelector(hash);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        }

        async updatePage(pageData, url, options = {}) {
            const { preserveScroll = false } = options;
            // Update page title
            document.title = pageData.title;
            this.updateHeadMetadata(pageData.head);

            // Load page-specific styles (skipped for admin)
            await this.loadPageStyles(url, pageData.styles);

            // Categorias e subcategorias administradas também entram ao vivo no menu.
            const navigation = document.querySelector('#primary-navigation');
            if (navigation && pageData.navigation && navigation.innerHTML !== pageData.navigation) {
                navigation.innerHTML = pageData.navigation;
            }

            // Find main content container
            // For admin pages, target the admin-content-wrapper specifically
            const targetPath = new URL(url, window.location.origin).pathname;
            const isAdminPage = targetPath.startsWith('/admin');
            let mainContainer;

            if (isAdminPage) {
                mainContainer = document.querySelector('.admin-content-wrapper');
            }

            if (!mainContainer) {
                mainContainer = document.querySelector('.main-content-container') ||
                    document.querySelector('main') ||
                    document.querySelector('.container') ||
                    document.querySelector('#content');
            }

            if (mainContainer && pageData.content) {
                mainContainer.setAttribute('data-dynamic-loading-root', 'true');
                if (isAdminPage) {
                    // Instant update for admin
                    mainContainer.innerHTML = pageData.content.innerHTML;
                    await this.loadPageScripts(url, pageData.scripts);
                    this.executeInlineScripts(pageData.inlineScripts);
                    this.applyInlineStyles(pageData.inlineStyles);
                    this.executeContentScripts(mainContainer);
                    this.reinitializeComponents();
                    if (!preserveScroll) window.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    // Smooth transition for public pages
                    mainContainer.style.opacity = '0';
                    mainContainer.style.transition = 'opacity 0.15s ease-in-out';

                    console.log('[DYNAMIC-LOADING] 📄 Atualizando conteúdo da página');
                    mainContainer.innerHTML = pageData.content.innerHTML;

                    console.log('[DYNAMIC-LOADING] 📜 Carregando scripts');
                    await this.loadPageScripts(url, pageData.scripts);
                    this.executeInlineScripts(pageData.inlineScripts);
                    this.applyInlineStyles(pageData.inlineStyles);
                    this.executeContentScripts(mainContainer);

                    // Reinicializa componentes imediatamente
                    this.reinitializeComponents();

                    // Double rAF ensures the browser has painted with styles applied
                    requestAnimationFrame(() => {
                        requestAnimationFrame(() => {
                            mainContainer.style.opacity = '1';
                        });
                    });

                    if (!preserveScroll) window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }

            // Handle footer visibility based on page
            this.handleFooterVisibility(url);

            // Update active navigation
            this.updateActiveNavigation(url);
        }

        refreshCurrentPage() {
            return this.loadPage(window.location.href, {
                updateHistory: false,
                force: true,
                preserveScroll: true,
            });
        }

        handleFooterVisibility(url) {
            const path = new URL(url, window.location.origin).pathname;
            const footer = document.querySelector('footer') || document.querySelector('.footer');

            if (footer) {
                if (path.startsWith('/profile')) {
                    // Hide footer on profile page
                    footer.style.display = 'none';
                } else {
                    // Show footer on other pages
                    footer.style.display = '';
                }
            }
        }

        reinitializeComponents() {
            console.log('[DYNAMIC-LOADING] 🔄 Reinicializando componentes...');

            // CRÍTICO: Garantir que o scroll está sempre habilitado ao navegar
            document.body.style.overflow = '';
            document.documentElement.style.overflow = '';

            // Fechar qualquer modal aberto
            const contributeModal = document.getElementById('contributeModal');
            if (contributeModal) {
                contributeModal.classList.remove('active');
            }

            // Limpa TODOS os atributos de inicialização para permitir reinicialização
            document.querySelectorAll('[data-suggestions-initialized]').forEach(el => {
                el.removeAttribute('data-suggestions-initialized');
            });
            document.querySelectorAll('[data-faq-initialized]').forEach(el => {
                el.removeAttribute('data-faq-initialized');
            });
            document.querySelectorAll('[data-contact-initialized]').forEach(el => {
                el.removeAttribute('data-contact-initialized');
            });
            document.querySelectorAll('[data-form-initialized]').forEach(el => {
                el.removeAttribute('data-form-initialized');
            });
            document.querySelectorAll('[data-suggestion-initialized]').forEach(el => {
                el.removeAttribute('data-suggestion-initialized');
            });

            // Re-initialize favorite buttons and modal
            if (window.favoriteManager) {
                console.log('[DYNAMIC-LOADING] ⭐ Reinicializando favoriteManager');
                // Garante que o modal existe após carregamento dinâmico
                window.favoriteManager.createConfirmModal();
                // Força reinicialização sem duplicar listeners
                window.favoriteManager._isInitialized = false;
                window.favoriteManager.init();
            }

            // Re-initialize search suggestions for all search inputs
            if (window.SearchSuggestions) {
                console.log('[DYNAMIC-LOADING] 🔍 Reinicializando search suggestions');
                // Buscar todos os inputs de pesquisa
                const searchInputs = document.querySelectorAll('input[name="q"], .search-bar input, #home-search-input');
                searchInputs.forEach((input, idx) => {
                    if (input && input.id) {
                        try {
                            new SearchSuggestions(`#${input.id}`);
                            console.log(`[DYNAMIC-LOADING] ✅ Search suggestions ${idx + 1} inicializado`);
                        } catch (e) {
                            console.warn(`[DYNAMIC-LOADING] ⚠️ Erro ao inicializar search ${idx + 1}:`, e);
                        }
                    }
                });
            }

            // Re-initialize feature modals (for categories pages)
            if (typeof window.initFeatureModals === 'function') {
                console.log('[DYNAMIC-LOADING] 🎬 Reinicializando feature modals');
                window.initFeatureModals();
            }

            // Re-initialize FAQ functionality
            if (window.location.pathname === '/faq' && typeof window.toggleFAQ === 'function') {
                console.log('[DYNAMIC-LOADING] ❓ Reinicializando FAQ');
                this.initializeFAQ();
            }

            // Re-initialize contact form functionality
            if (window.location.pathname === '/contact' || window.location.pathname === '/contato') {
                console.log('[DYNAMIC-LOADING] 📧 Reinicializando contact form');
                this.initializeContactForm();
            }

            // Re-initialize category page functionality
            if (window.location.pathname.startsWith('/categoria/')) {
                console.log('[DYNAMIC-LOADING] 📁 Reinicializando category page');
                this.initializeCategoryPage();
            }

            // Re-initialize profile page functionality
            if (window.location.pathname.startsWith('/profile')) {
                console.log('[DYNAMIC-LOADING] 👤 Reinicializando profile page');
                this.initializeProfilePage();
            }

            // Re-initialize posts list page functionality
            if (window.location.pathname === '/posts') {
                console.log('[DYNAMIC-LOADING] 📚 Reinicializando posts list page');
                this.initializeCategoryPage();
            }

            // Re-initialize post page functionality
            const currentPath = window.location.pathname;
            if (currentPath.startsWith('/post/') || (!currentPath.startsWith('/admin') && currentPath.split('/').length === 3 && currentPath.split('/')[1] && currentPath.split('/')[2])) {
                console.log('[DYNAMIC-LOADING] 📄 Reinicializando post page');
                this.initializePostPage();
            }

            // Re-initialize legal pages functionality
            if (window.location.pathname === '/termos-de-uso' || window.location.pathname === '/politica-de-privacidade') {
                console.log('[DYNAMIC-LOADING] ⚖️ Reinicializando legal page');
                this.initializeLegalPage();
            }

            // Re-initialize admin components
            if (currentPath.startsWith('/admin')) {
                console.log('[DYNAMIC-LOADING] 🔧 Reinicializando admin components');
                this.reinitializeAdminComponents();
            }

            // Re-initialize home page functionality
            if (currentPath === '/' || currentPath === '/home' || document.querySelector('#hero-particles')) {
                console.log('[DYNAMIC-LOADING] 🏠 Reinicializando home page');
                this.initializeHomePage();
            }

            // Re-initialize About page functionality
            if (currentPath === '/about' || currentPath === '/sobre') {
                console.log('[DYNAMIC-LOADING] ℹ️ Reinicializando about page');
                this.initializeAboutPage();
            }

            // Re-initialize Plans page functionality
            if (currentPath === '/planos' || currentPath === '/plans') {
                console.log('[DYNAMIC-LOADING] 💳 Reinicializando plans page');
                // Force activate Plans CSS
                const plansCSS = document.getElementById('plans-css');
                if (plansCSS) {
                    plansCSS.media = 'all';
                }
                // Reset flag para permitir reinicialização
                window.plansPageInitialized = false;
                if (typeof window.initializePlansPage === 'function') {
                    window.initializePlansPage();
                }
            }

            // Re-initialize download buttons (CRITICAL for download limit checks)
            if (typeof window.setupDownloadButtons === 'function') {
                console.log('[DYNAMIC-LOADING] 📥 Reinicializando download buttons');
                window.setupDownloadButtons();
            }

            // Re-initialize theme toggler
            if (typeof window.initTheme === 'function') {
                console.log('[DYNAMIC-LOADING] 🎨 Reinicializando theme');
                window.initTheme();
            }

            // Re-initialize shared UI behaviors
            if (typeof window.initializeMainUi === 'function') {
                console.log('[DYNAMIC-LOADING] 🧩 Reinicializando main UI');
                window.initializeMainUi();
            }

            // Re-initialize navbar interactions
            if (typeof window.initNavbar === 'function') {
                console.log('[DYNAMIC-LOADING] 📱 Reinicializando navbar');
                window.initNavbar();
            }

            // Re-initialize any other components
            console.log('[DYNAMIC-LOADING] ✨ Disparando eventos de ciclo de vida');
            this.dispatchEvent('contentLoaded');
            this.dispatchEvent('pageLoaded');

            console.log('[DYNAMIC-LOADING] ✅ Reinicialização completa!');
        }

        reinitializeAdminComponents() {
            document.querySelectorAll('[data-modal-initialized]').forEach((element) => {
                element.removeAttribute('data-modal-initialized');
            });
            document.querySelectorAll('[data-close-initialized]').forEach((element) => {
                element.removeAttribute('data-close-initialized');
            });
            document.querySelectorAll('[data-dismiss-initialized]').forEach((element) => {
                element.removeAttribute('data-dismiss-initialized');
            });

            // Re-initialize modal handlers
            if (typeof window.handleModals === 'function') {
                window.handleModals();
            }

            // Re-initialize modern forms
            if (typeof window.initializeModernForms === 'function') {
                window.initializeModernForms();
            }

            // Re-initialize profile images
            if (typeof window.initializeProfileImages === 'function') {
                window.initializeProfileImages();
            }

            const addPostModal = document.getElementById('addPostModal');
            if (addPostModal) {
                addPostModal.removeAttribute('data-post-wizard-initialized');
                addPostModal.removeAttribute('data-postWizardInitialized');
            }

            if (typeof window.initPostWizard === 'function') {
                window.initPostWizard();
            }

            // Re-initialize admin-specific functionality
            const adminScriptEvent = new CustomEvent('adminPageLoaded');
            document.dispatchEvent(adminScriptEvent);
        }

        async loadPageStyles(url, styles) {
            const path = new URL(url, window.location.origin).pathname;

            // Reset all page-specific styles to print media (disabled)
            const faqCSS = document.getElementById('faq-css');
            const contactCSS = document.getElementById('contact-css');
            const aboutCSS = document.getElementById('about-css');
            const aboutPageCSS = document.getElementById('about-page-css');
            const categoryCSS = document.getElementById('category-css');
            const profileCSS = document.getElementById('profile-css');
            const plansCSS = document.getElementById('plans-css');
            const postDetailCSS = document.getElementById('post-detail-css');
            const adminCSS = document.getElementById('admin-css');

            const activatedStyles = [];

            // Desativar todos os CSS específicos de página
            if (faqCSS) faqCSS.media = 'print';
            if (contactCSS) contactCSS.media = 'print';
            if (aboutCSS) aboutCSS.media = 'print';
            if (aboutPageCSS) aboutPageCSS.media = 'print';
            if (categoryCSS) categoryCSS.media = 'print';
            if (profileCSS) profileCSS.media = 'print';
            if (plansCSS) plansCSS.media = 'print';
            if (postDetailCSS) postDetailCSS.media = 'print';
            if (adminCSS) adminCSS.media = 'print';

            // Determine which page-specific CSS to activate based on URL
            if ((path === '/faq' || path === '/solicitacoes') && faqCSS) {
                faqCSS.media = 'all';
                activatedStyles.push(faqCSS);
                console.log('[DYNAMIC-LOADING] 🎨 FAQ CSS ativado');
            } else if ((path === '/contact' || path === '/contato') && contactCSS) {
                contactCSS.media = 'all';
                activatedStyles.push(contactCSS);
                console.log('[DYNAMIC-LOADING] 🎨 Contact CSS ativado');
            } else if ((path === '/about' || path === '/sobre') && aboutCSS) {
                aboutCSS.media = 'all';
                activatedStyles.push(aboutCSS);
                if (aboutPageCSS) aboutPageCSS.media = 'all';
                if (aboutPageCSS) activatedStyles.push(aboutPageCSS);
                console.log('[DYNAMIC-LOADING] 🎨 About CSS ativado');
            } else if ((path.startsWith('/categoria/') || path.startsWith('/subcategoria/') || path === '/categorias' || path === '/posts') && categoryCSS) {
                categoryCSS.media = 'all';
                activatedStyles.push(categoryCSS);
                console.log('[DYNAMIC-LOADING] 🎨 Category CSS ativado');
            } else if (path.startsWith('/profile')) {
                if (profileCSS) profileCSS.media = 'all';
                if (profileCSS) activatedStyles.push(profileCSS);
                if (adminCSS) adminCSS.media = 'all'; // Profile também usa admin.css
                if (adminCSS) activatedStyles.push(adminCSS);
                console.log('[DYNAMIC-LOADING] 🎨 Profile CSS ativado');
            } else if ((path === '/plans' || path === '/planos') && plansCSS) {
                plansCSS.media = 'all';
                activatedStyles.push(plansCSS);
                console.log('[DYNAMIC-LOADING] 🎨 Plans CSS ativado');
            } else if (path.startsWith('/post/') || this.isPostPage(path)) {
                if (postDetailCSS) postDetailCSS.media = 'all';
                if (postDetailCSS) activatedStyles.push(postDetailCSS);
                console.log('[DYNAMIC-LOADING] 🎨 Post Detail CSS ativado');
            } else if (path.startsWith('/admin')) {
                if (adminCSS) adminCSS.media = 'all';
                if (adminCSS) activatedStyles.push(adminCSS);
                console.log('[DYNAMIC-LOADING] 🎨 Admin CSS ativado');
            }

            await Promise.all(activatedStyles.map((styleLink) => this.ensureStylesheetReady(styleLink)));
            await this.syncDynamicStyles(styles);
            await this.waitForNextPaint();
        }

        // Helper para detectar páginas de post (categoria/slug)
        isPostPage(path) {
            const parts = path.split('/').filter(p => p);
            return parts.length === 2 && !['admin', 'profile', 'categoria', 'subcategoria', 'api'].includes(parts[0]);
        }

        async loadPageScripts(url, scripts) {
            document.querySelectorAll('script[data-dynamic-js="true"]').forEach((script) => script.remove());
            const baseScriptUrls = new Set(
                Array.from(document.querySelectorAll('script[data-static-base-script="true"][src]'))
                    .map((script) => script.src)
            );
            const loadedDynamicUrls = new Set();

            for (const scriptElement of scripts) {
                if (!scriptElement.src) {
                    continue;
                }

                const normalizedSrc = new URL(scriptElement.src, window.location.origin).href;
                if (baseScriptUrls.has(normalizedSrc) || loadedDynamicUrls.has(normalizedSrc)) {
                    continue;
                }
                loadedDynamicUrls.add(normalizedSrc);

                await new Promise((resolve) => {
                    const script = document.createElement('script');
                    script.src = normalizedSrc;
                    script.async = false;
                    script.setAttribute('data-dynamic-js', 'true');

                    Array.from(scriptElement.attributes).forEach(attr => {
                        if (attr.name !== 'src') {
                            script.setAttribute(attr.name, attr.value);
                        }
                    });

                    script.onload = () => {
                        console.log('Script loaded:', scriptElement.src);
                        resolve();
                    };

                    script.onerror = () => {
                        console.error('Failed to load script:', scriptElement.src);
                        resolve();
                    };

                    document.body.appendChild(script);
                });
            }
        }

        executeInlineScripts(inlineScripts) {
            // Remove previous inline scripts added dynamically
            document.querySelectorAll('script[data-dynamic-inline="true"]').forEach(s => s.remove());

            // Execute inline scripts from the loaded page
            inlineScripts.forEach(scriptElement => {
                const script = document.createElement('script');
                script.textContent = scriptElement.textContent;
                script.setAttribute('data-dynamic-inline', 'true');

                // Copy all attributes except src
                Array.from(scriptElement.attributes).forEach(attr => {
                    if (attr.name !== 'src') {
                        script.setAttribute(attr.name, attr.value);
                    }
                });

                document.body.appendChild(script);
            });
        }

        applyInlineStyles(inlineStyles) {
            // Remove previous inline styles added dynamically
            document.querySelectorAll('style[data-dynamic-style="true"]').forEach(s => s.remove());

            // Apply inline styles from the loaded page
            inlineStyles.forEach(styleElement => {
                const style = document.createElement('style');
                style.textContent = styleElement.textContent;
                style.setAttribute('data-dynamic-style', 'true');

                // Copy all attributes
                Array.from(styleElement.attributes).forEach(attr => {
                    style.setAttribute(attr.name, attr.value);
                });

                document.head.appendChild(style);
            });
        }

        async syncDynamicStyles(styles) {
            const desiredStyles = new Map();
            styles.forEach((style) => {
                if (!style.href) return;
                desiredStyles.set(new URL(style.href, window.location.origin).href, style);
            });
            const desiredHrefs = new Set(desiredStyles.keys());

            document.querySelectorAll('link[data-dynamic-page-style="true"]').forEach(link => {
                if (!desiredHrefs.has(link.href)) {
                    link.remove();
                }
            });

            const existingHrefs = new Set(
                Array.from(document.querySelectorAll('link[rel="stylesheet"][href]'))
                    .map(link => link.href)
            );

            const pendingStyles = Array.from(desiredHrefs)
                .filter((href) => !existingHrefs.has(href))
                .map((href) => new Promise((resolve) => {
                    const link = document.createElement('link');
                    const sourceStyle = desiredStyles.get(href);
                    link.rel = 'stylesheet';
                    link.href = href;
                    link.setAttribute('data-dynamic-page-style', 'true');
                    if (sourceStyle?.id) link.id = sourceStyle.id;
                    if (sourceStyle?.media) link.media = sourceStyle.media;
                    link.onload = () => resolve();
                    link.onerror = () => resolve();
                    document.head.appendChild(link);
                }));
            await Promise.all(pendingStyles);
        }

        ensureStylesheetReady(link) {
            if (!link) {
                return Promise.resolve();
            }

            return new Promise((resolve) => {
                let settled = false;
                const finish = () => {
                    if (settled) {
                        return;
                    }
                    settled = true;
                    link.dataset.dynamicStylesheetReady = 'true';
                    link.removeEventListener('load', finish);
                    link.removeEventListener('error', finish);
                    resolve();
                };

                if (this.isStylesheetReady(link)) {
                    finish();
                    return;
                }

                link.addEventListener('load', finish, { once: true });
                link.addEventListener('error', finish, { once: true });

                setTimeout(() => {
                    if (this.isStylesheetReady(link)) {
                        finish();
                    }
                }, 0);

                setTimeout(finish, 1500);
            });
        }

        isStylesheetReady(link) {
            try {
                return Boolean(link.sheet);
            } catch (error) {
                return true;
            }
        }

        waitForNextPaint() {
            return new Promise((resolve) => {
                requestAnimationFrame(() => {
                    requestAnimationFrame(resolve);
                });
            });
        }

        executeContentScripts(container) {
            // Execute scripts that are inside the loaded HTML content
            const scripts = container.querySelectorAll('script');
            scripts.forEach(oldScript => {
                const newScript = document.createElement('script');

                // Copy script content
                if (oldScript.src) {
                    newScript.src = oldScript.src;
                } else {
                    newScript.textContent = oldScript.textContent;
                }

                // Copy all attributes
                Array.from(oldScript.attributes).forEach(attr => {
                    newScript.setAttribute(attr.name, attr.value);
                });

                // Replace old script with new one to force execution
                oldScript.parentNode.replaceChild(newScript, oldScript);
            });
        }

        initializeFAQ() {
            // Force activate FAQ CSS
            const faqCSS = document.getElementById('faq-css');
            if (faqCSS) {
                faqCSS.media = 'all';
            }

            // Initialize FAQ functionality
            setTimeout(() => {
                const faqSearch = document.getElementById('faq-search');
                if (faqSearch && !faqSearch.hasAttribute('data-faq-initialized')) {
                    // Re-bind FAQ search functionality
                    faqSearch.setAttribute('data-faq-initialized', 'true');
                    faqSearch.addEventListener('input', function () {
                        const searchTerm = this.value.toLowerCase();
                        const faqItems = document.querySelectorAll('.faq-item');

                        faqItems.forEach(item => {
                            const keywords = item.dataset.keywords || '';
                            const question = item.querySelector('.faq-question h3')?.textContent || '';
                            const answer = item.querySelector('.faq-answer p')?.textContent || '';

                            const searchContent = `${keywords} ${question} ${answer}`.toLowerCase();

                            if (searchContent.includes(searchTerm)) {
                                item.style.display = 'block';
                            } else {
                                item.style.display = 'none';
                            }
                        });
                    });
                }

                // Re-bind suggestion clicks
                document.querySelectorAll('.search-suggestion').forEach(btn => {
                    if (!btn.hasAttribute('data-suggestion-initialized')) {
                        btn.setAttribute('data-suggestion-initialized', 'true');
                        btn.addEventListener('click', function () {
                            const searchTerm = this.dataset.search;
                            if (faqSearch) {
                                faqSearch.value = searchTerm;
                                faqSearch.dispatchEvent(new Event('input'));
                            }
                        });
                    }
                });

                // Initialize Contribute Modal for FAQ page
                this.initializeContributeModalFAQ();
            }, 100);
        }

        initializeContributeModalFAQ() {
            if (window.ContributeModal && typeof window.ContributeModal.init === 'function') {
                window.ContributeModal.init();
            }
        }

        initializeContactForm() {
            // Force activate Contact CSS
            const contactCSS = document.getElementById('contact-css');
            if (contactCSS) {
                contactCSS.media = 'all';
            }

            setTimeout(() => {
                if (window.ContactPage && typeof window.ContactPage.init === 'function') {
                    window.ContactPage.init();
                }

                // Initialize particles for contact hero
                this.initContactParticles();
            }, 100);
        }

        initContactParticles() {
            const hero = document.querySelector('.contact-hero');
            if (!hero) return;

            const particles = hero.querySelector('.hero-particles');
            if (!particles) return;

            // Clear existing particles
            particles.innerHTML = '';

            // Create particle elements
            for (let i = 0; i < 50; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.animationDelay = Math.random() * 20 + 's';
                particle.style.animationDuration = (Math.random() * 10 + 10) + 's';
                particles.appendChild(particle);
            }
        }

        initializeLegalPage() {
            // Initialize legal pages (Terms of Service, Privacy Policy)
            setTimeout(() => {
                // Smooth scroll for anchor links within legal pages
                const legalContent = document.querySelector('.legal-content');
                if (legalContent) {
                    const anchorLinks = legalContent.querySelectorAll('a[href^="#"]');
                    anchorLinks.forEach(link => {
                        link.addEventListener('click', function (e) {
                            e.preventDefault();
                            const targetId = this.getAttribute('href').substring(1);
                            const targetElement = document.getElementById(targetId);
                            if (targetElement) {
                                targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            }
                        });
                    });
                }

                // Initialize particles for legal pages during SPA navigation
                const legalSection = document.querySelector('.legal-page-section');
                if (legalSection && typeof InteractiveParticles !== 'undefined') {
                    // Remove any existing particle canvas to avoid duplicates
                    const existingCanvas = legalSection.querySelector('canvas');
                    if (existingCanvas) existingCanvas.remove();

                    legalSection.id = 'legal-particles-container';
                    new InteractiveParticles('legal-particles-container', {
                        particleCount: 70,
                        particleSize: 3.5,
                        particleSpeed: 0.4,
                        connectionDistance: 130,
                        mouseRadius: 200,
                        mouseRepel: true
                    });
                    console.log('[DYNAMIC-LOADING] ✨ Legal page particles initialized');
                }

                // Add animation to sections on scroll
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.style.opacity = '1';
                            entry.target.style.transform = 'translateY(0)';
                        }
                    });
                }, { threshold: 0.1 });

                document.querySelectorAll('.legal-section').forEach(section => {
                    section.style.opacity = '0';
                    section.style.transform = 'translateY(20px)';
                    section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                    observer.observe(section);
                });
            }, 100);
        }

        updateActiveNavigation(url) {
            const targetPath = new URL(url, window.location.origin).pathname;
            const supportPaths = new Set([
                '/about',
                '/sobre',
                '/faq',
                '/contact',
                '/contato',
                '/solicitacoes',
                '/termos-de-uso',
                '/politica-de-privacidade'
            ]);
            const isCategoryPath = targetPath === '/categorias' || targetPath.startsWith('/categoria/') || targetPath.startsWith('/subcategoria/');

            // Remove active class from all nav links
            document.querySelectorAll('.nav-menu a').forEach(link => {
                link.classList.remove('active');
            });

            document.querySelectorAll('.nav-menu a[data-nav-group="support"]').forEach(link => {
                if (supportPaths.has(targetPath)) {
                    link.classList.add('active');
                }
            });

            document.querySelectorAll('.nav-menu a[data-nav-group="categories"]').forEach(link => {
                if (isCategoryPath) {
                    link.classList.add('active');
                }
            });

            // Add active class to current page link
            document.querySelectorAll('.nav-menu a[href]').forEach(link => {
                try {
                    const rawHref = link.getAttribute('href');
                    if (!rawHref || rawHref === '#' || link.dataset.navGroup) {
                        return;
                    }

                    const linkPath = new URL(link.href, window.location.origin).pathname;
                    if (linkPath === targetPath) {
                        link.classList.add('active');
                    }
                } catch (error) {
                    console.warn('[DYNAMIC-LOADING] Erro ao atualizar navegação ativa:', error);
                }
            });

            document.querySelectorAll('.admin-nav-item[href]').forEach((link) => {
                try {
                    const rawHref = link.getAttribute('href');
                    if (!rawHref || rawHref === '#' || rawHref.startsWith('#')) {
                        link.classList.remove('active');
                        return;
                    }

                    const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/+$/, '');
                    const normalizedTargetPath = targetPath.replace(/\/+$/, '');
                    link.classList.toggle('active', linkPath === normalizedTargetPath);
                } catch (error) {
                    console.warn('[DYNAMIC-LOADING] Erro ao atualizar navegação ativa do admin:', error);
                }
            });
        }

        updateUrl(url) {
            this.currentUrl = url;
            history.pushState({ url }, '', url);
        }

        handleBrowserNavigation() {
            window.addEventListener('popstate', (e) => {
                const targetUrl = e.state?.url || window.location.href;
                this.loadPage(targetUrl, { updateHistory: false });
            });
        }

        async submitForm(form) {
            if (this.isLoading) return;

            this.isLoading = true;
            this.showLoading();

            try {
                const formData = new FormData(form);
                const response = await fetch(form.action || window.location.href, {
                    method: form.method || 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                // Get the final URL (handles redirects)
                const finalUrl = response.url;

                // Parse response content
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const content = {
                    title: doc.title,
                    content: doc.querySelector('main') || doc.querySelector('.container') || doc.body,
                    scripts: Array.from(doc.querySelectorAll('script[src]')).filter(script =>
                        !script.hasAttribute('data-static-base-script')
                    ),
                    inlineScripts: Array.from(doc.querySelectorAll('script:not([src])')).filter(script =>
                        !script.hasAttribute('data-static-base-script') && script.type !== 'application/json'
                    ),
                    styles: Array.from(doc.querySelectorAll('link[rel="stylesheet"]')).filter(style =>
                        !style.hasAttribute('data-static-base-style')
                    ),
                    inlineStyles: Array.from(doc.querySelectorAll('style')).filter(style =>
                        !style.hasAttribute('data-static-base-style')
                    )
                };

                this.updateUrl(finalUrl);
                // Update page with new content (whether it's the same page with errors or a new page)
                await this.updatePage(content, finalUrl);

            } catch (error) {
                console.error('Error submitting form:', error);
                // Fallback to normal form submission
                form.submit();
            } finally {
                this.isLoading = false;
                this.hideLoading();
            }
        }

        createLoadingIndicator() {
            if (document.getElementById('dynamic-loader')) {
                return;
            }

            const loader = document.createElement('div');
            loader.id = 'dynamic-loader';
            loader.innerHTML = `
            <div class="loader-spinner">
                <div class="spinner"></div>
                <p>Carregando...</p>
            </div>
        `;

            const style = document.createElement('style');
            style.textContent = `
            #dynamic-loader {
                position: fixed;
                inset: 70px 0 0;
                width: auto;
                height: auto;
                background: rgba(255, 255, 255, 0.9);
                display: none;
                justify-content: center;
                align-items: center;
                z-index: 900;
                backdrop-filter: blur(5px);
                -webkit-backdrop-filter: blur(5px);
                pointer-events: auto;
                overflow: hidden;
            }

            .loader-spinner {
                text-align: center;
            }

            .spinner {
                width: 40px;
                height: 40px;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 1rem;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .loader-spinner p {
                color: #667eea;
                font-weight: 600;
                margin: 0;
            }
        `;

            document.head.appendChild(style);
            document.body.appendChild(loader);
        }

        showLoading() {
            window.clearTimeout(this.loadingTimer);
            this.loadingTimer = window.setTimeout(() => {
                const loader = document.getElementById('dynamic-loader');
                if (!loader || !this.isLoading) return;
                this.attachLoaderToMain(loader);
                loader.style.display = 'flex';
                window.requestAnimationFrame(() => this.attachLoaderToMain(loader));
            }, this.loadingDelayMs);
        }

        hideLoading() {
            window.clearTimeout(this.loadingTimer);
            this.loadingTimer = null;
            const loader = document.getElementById('dynamic-loader');
            if (loader) {
                loader.style.display = 'none';
            }
        }

        attachLoaderToMain(loader) {
            const isAdminPage = document.body.classList.contains('admin-page')
                || window.location.pathname.startsWith('/admin');
            const adminContent = document.querySelector('.admin-content');

            if (isAdminPage && adminContent) {
                const adminRect = adminContent.getBoundingClientRect();
                const left = Math.max(adminRect.left, 0);

                if (loader.parentNode !== document.body) {
                    document.body.appendChild(loader);
                }

                loader.style.inset = 'auto';

                // O painel mantém a sidebar disponível e cobre uniformemente toda a
                // viewport de conteúdo. A altura do documento ou a posição do scroll
                // não podem mais fazer o blur começar no meio da tela.
                loader.style.top = '0';
                loader.style.left = `${left}px`;
                loader.style.width = `${Math.max(window.innerWidth - left, 0)}px`;
                loader.style.height = '100dvh';
                return;
            }

            const mainContainer = document.querySelector('.main-content-container') ||
                document.querySelector('main') ||
                document.querySelector('[data-dynamic-loading-root="true"]');

            if (!mainContainer) {
                if (loader.parentNode !== document.body) {
                    document.body.appendChild(loader);
                }
                loader.style.inset = '0';
                loader.style.width = '100dvw';
                loader.style.height = '100dvh';
                return;
            }

            if (loader.parentNode !== document.body) {
                document.body.appendChild(loader);
            }

            const header = document.querySelector('body > header');
            const footer = document.querySelector('body > footer, .modern-footer');
            const viewportHeight = window.innerHeight;
            const headerBottom = header
                ? Math.max(0, Math.min(viewportHeight, header.getBoundingClientRect().bottom))
                : 0;
            const footerTop = footer ? footer.getBoundingClientRect().top : viewportHeight;
            const visibleFooterTop = Math.max(headerBottom, Math.min(viewportHeight, footerTop));
            loader.style.inset = 'auto';
            loader.style.top = `${headerBottom}px`;
            loader.style.left = '0';
            loader.style.width = '100dvw';
            loader.style.height = `${Math.max(visibleFooterTop - headerBottom, 0)}px`;
            loader.style.bottom = 'auto';
        }

        dispatchEvent(eventName, data = {}) {
            const event = new CustomEvent(eventName, { detail: data });
            document.dispatchEvent(event);
        }

        initializeAboutPage() {
            // Force activate about CSS
            const aboutCSS = document.getElementById('about-css');
            const aboutPageCSS = document.getElementById('about-page-css');
            if (aboutCSS) {
                aboutCSS.media = 'all';
            }
            if (aboutPageCSS) {
                aboutPageCSS.media = 'all';
            }

            // Initialize About page functionality
            setTimeout(() => {
                // Initialize statistics counter animation (somente cards de serviços da página Sobre)
                const statsCounters = document.querySelectorAll('.service-stats .stat-number');
                if (statsCounters.length > 0) {
                    // Animate counters when they come into view
                    const observer = new IntersectionObserver((entries) => {
                        entries.forEach(entry => {
                            if (entry.isIntersecting) {
                                const counter = entry.target;
                                const target = parseInt((counter.textContent || '').replace(/[^\d]/g, ''), 10);
                                if (!Number.isFinite(target) || target <= 0) {
                                    observer.unobserve(counter);
                                    return;
                                }
                                const increment = target / 50;
                                let current = 0;

                                const timer = setInterval(() => {
                                    current += increment;
                                    if (current >= target) {
                                        counter.innerText = target.toLocaleString();
                                        clearInterval(timer);
                                    } else {
                                        counter.innerText = Math.floor(current).toLocaleString();
                                    }
                                }, 30);

                                observer.unobserve(counter);
                            }
                        });
                    }, { threshold: 0.1 });

                    statsCounters.forEach(counter => observer.observe(counter));
                }

                // Add smooth scroll for mission cards
                const missionCards = document.querySelectorAll('.mission-card');
                if (missionCards.length > 0) {
                    missionCards.forEach((card, index) => {
                        card.style.animationDelay = `${index * 0.2}s`;
                    });
                }

                // Add hover effects for service cards
                const serviceCards = document.querySelectorAll('.service-card');
                if (serviceCards.length > 0) {
                    serviceCards.forEach(card => {
                        card.addEventListener('mouseenter', function () {
                            this.style.transform = 'translateY(-10px) scale(1.02)';
                        });

                        card.addEventListener('mouseleave', function () {
                            this.style.transform = 'translateY(0) scale(1)';
                        });
                    });
                }

                // Initialize Contribute Modal
                this.initializeContributeModal();
            }, 100);
        }

        initializeContributeModal() {
            const modal = document.getElementById('contributeModal');
            const openBtn = document.getElementById('openContributeModal');
            const closeBtn = document.getElementById('closeContributeModal');
            const overlay = modal?.querySelector('.contribute-modal-overlay');

            if (!modal) return;

            // Limpar estado anterior do modal (garantir que scroll esteja liberado)
            modal.classList.remove('active');
            document.body.style.overflow = '';

            // Função para abrir o modal
            const openModal = (e) => {
                e.preventDefault();
                e.stopPropagation();
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            };

            // Função para fechar o modal
            const closeModal = () => {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            };

            // Limpar e adicionar event listener no botão de abrir
            if (openBtn) {
                // Clonar para remover listeners antigos
                const newOpenBtn = openBtn.cloneNode(true);
                openBtn.parentNode?.replaceChild(newOpenBtn, openBtn);
                newOpenBtn.addEventListener('click', openModal);
            }

            // Limpar e adicionar event listener no botão de fechar
            if (closeBtn) {
                const newCloseBtn = closeBtn.cloneNode(true);
                closeBtn.parentNode?.replaceChild(newCloseBtn, closeBtn);
                newCloseBtn.addEventListener('click', closeModal);
            }

            // Overlay - clonar para limpar listeners
            if (overlay) {
                const newOverlay = overlay.cloneNode(true);
                overlay.parentNode?.replaceChild(newOverlay, overlay);
                newOverlay.addEventListener('click', closeModal);
            }

            // Fechar com ESC - usar handler global único
            if (!window._contributeModalEscHandler) {
                window._contributeModalEscHandler = (e) => {
                    if (e.key === 'Escape') {
                        const activeModal = document.getElementById('contributeModal');
                        if (activeModal?.classList.contains('active')) {
                            activeModal.classList.remove('active');
                            document.body.style.overflow = '';
                        }
                    }
                };
                document.addEventListener('keydown', window._contributeModalEscHandler);
            }

            // Restaurar scroll quando clicar em links dentro do modal
            const modalContent = document.querySelector('.contribute-modal-content');
            if (modalContent) {
                const modalLinks = modalContent.querySelectorAll('a[href]');
                modalLinks.forEach(link => {
                    // Clonar para limpar listeners antigos
                    const newLink = link.cloneNode(true);
                    link.parentNode?.replaceChild(newLink, link);

                    newLink.addEventListener('click', function (e) {
                        // Restaurar scroll IMEDIATAMENTE antes de qualquer navegação
                        document.body.style.overflow = '';
                        modal.classList.remove('active');
                    });
                });
            }
        }

        initializeCategoryPage() {
            // Force activate category CSS
            const categoryCSS = document.getElementById('category-css');
            if (categoryCSS) {
                categoryCSS.media = 'all';
            }

            // Initialize Category page functionality
            setTimeout(() => {
                // Initialize category search functionality
                const searchInput = document.querySelector('.category-search-input');
                const suggestionsDropdown = document.querySelector('.search-suggestions-dropdown');

                if (searchInput && suggestionsDropdown && !searchInput.dataset.dynamicCategorySearchInit) {
                    searchInput.dataset.dynamicCategorySearchInit = 'true';
                    let debounceTimer;
                    let currentQuery = '';

                    // Function to fetch suggestions
                    async function fetchSuggestions(query, category) {
                        try {
                            const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}`);
                            const suggestions = await response.json();
                            return suggestions;
                        } catch (error) {
                            console.error('Error fetching suggestions:', error);
                            return [];
                        }
                    }

                    // Function to render suggestions
                    function renderSuggestions(suggestions) {
                        if (suggestions.length === 0) {
                            suggestionsDropdown.innerHTML = '<div class="no-suggestions">Nenhuma sugestão encontrada</div>';
                            return;
                        }

                        const html = suggestions.map(suggestion => {
                            const fileTypes = Array.isArray(suggestion.file_types)
                                ? suggestion.file_types.filter(Boolean).join('/')
                                : '';
                            return `
                        <div class="suggestion-item" data-url="${suggestion.url}">
                            ${suggestion.type === 'post' && suggestion.image_url ? `
                                <div class="suggestion-thumb">
                                    <img src="${suggestion.image_url}" alt="${escapeHtmlSuggestion(suggestion.title)}" loading="lazy">
                                </div>
                            ` : `
                                <div class="suggestion-icon">
                                    <i class="${suggestion.icon}"></i>
                                </div>
                            `}
                            <div class="suggestion-content">
                                <div class="suggestion-title">${suggestion.title}</div>
                                ${fileTypes ? `<span class="suggestion-file-types">${escapeHtmlSuggestion(fileTypes)}</span>` : ''}
                                <div class="suggestion-description">${suggestion.description}</div>
                            </div>
                        </div>
                    `;
                        }).join('');

                        suggestionsDropdown.innerHTML = html;

                        // Add click handlers
                        suggestionsDropdown.querySelectorAll('.suggestion-item').forEach(item => {
                            item.addEventListener('click', function () {
                                const url = this.getAttribute('data-url');
                                // Use dynamic loading for internal links
                                if (window.dynamicLoader) {
                                    window.dynamicLoader.loadPage(url);
                                } else {
                                    window.location.href = url;
                                }
                            });
                        });
                    }

                    // Show suggestions
                    function showSuggestions() {
                        suggestionsDropdown.style.display = 'block';
                    }

                    // Hide suggestions
                    function hideSuggestions() {
                        setTimeout(() => {
                            suggestionsDropdown.style.display = 'none';
                        }, 200);
                    }

                    // Input event handler
                    searchInput.addEventListener('input', function () {
                        const query = this.value.trim();
                        const category = this.getAttribute('data-category');

                        currentQuery = query;

                        clearTimeout(debounceTimer);

                        if (query.length < 2) {
                            hideSuggestions();
                            return;
                        }

                        debounceTimer = setTimeout(async () => {
                            if (currentQuery === query) { // Check if query hasn't changed
                                const suggestions = await fetchSuggestions(query, category);
                                renderSuggestions(suggestions);
                                showSuggestions();
                            }
                        }, 300);
                    });

                    // Focus and blur events
                    searchInput.addEventListener('focus', function () {
                        if (this.value.trim().length >= 2) {
                            showSuggestions();
                        }
                    });

                    searchInput.addEventListener('blur', function () {
                        hideSuggestions();
                    });

                    // Keyboard navigation
                    searchInput.addEventListener('keydown', function (e) {
                        const items = suggestionsDropdown.querySelectorAll('.suggestion-item');
                        const current = suggestionsDropdown.querySelector('.suggestion-item.highlighted');

                        if (e.key === 'ArrowDown') {
                            e.preventDefault();
                            if (current) {
                                current.classList.remove('highlighted');
                                const next = current.nextElementSibling || items[0];
                                next.classList.add('highlighted');
                            } else if (items.length > 0) {
                                items[0].classList.add('highlighted');
                            }
                        } else if (e.key === 'ArrowUp') {
                            e.preventDefault();
                            if (current) {
                                current.classList.remove('highlighted');
                                const prev = current.previousElementSibling || items[items.length - 1];
                                prev.classList.add('highlighted');
                            } else if (items.length > 0) {
                                items[items.length - 1].classList.add('highlighted');
                            }
                        } else if (e.key === 'Enter') {
                            if (current) {
                                e.preventDefault();
                                current.click();
                            }
                        } else if (e.key === 'Escape') {
                            hideSuggestions();
                            this.blur();
                        }
                    });

                    function escapeHtmlSuggestion(value) {
                        return String(value || '')
                            .replace(/&/g, '&amp;')
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/"/g, '&quot;')
                            .replace(/'/g, '&#039;');
                    }
                }

                // Initialize post card animations
                const postCards = document.querySelectorAll('.modern-post-card');
                if (postCards.length > 0) {
                    postCards.forEach((card, index) => {
                        card.style.animationDelay = `${index * 0.1}s`;
                        card.classList.add('animate-fade-up');
                    });
                }

                // Initialize hero particles animation
                // const heroParticles = document.querySelector('.hero-particles');
                // if (heroParticles) {
                //     heroParticles.style.animation = 'float 20s ease-in-out infinite';
                // }
            }, 100);
        }

        initializeProfilePage() {
            // Force activate profile CSS
            const profileCSS = document.getElementById('profile-css');
            const adminCSS = document.getElementById('admin-css');
            if (profileCSS) {
                profileCSS.media = 'all';
            }
            if (adminCSS) {
                adminCSS.media = 'all';
            }

            // Initialize Profile page functionality
            setTimeout(() => {
                // Initialize tab functionality
                const tabButtons = document.querySelectorAll('.tab-button');
                const tabContents = document.querySelectorAll('.tab-content-item');

                if (tabButtons.length > 0) {
                    tabButtons.forEach(button => {
                        button.addEventListener('click', function () {
                            const targetTab = this.getAttribute('data-tab');

                            // Remove active class from all buttons and contents
                            tabButtons.forEach(btn => btn.classList.remove('active'));
                            tabContents.forEach(content => content.classList.remove('active'));

                            // Add active class to clicked button and corresponding content
                            this.classList.add('active');
                            const targetContent = document.getElementById(targetTab + '-content');
                            if (targetContent) {
                                targetContent.classList.add('active');
                            }
                        });
                    });
                }

                // Initialize profile image upload
                const profileImageForm = document.getElementById('profile-image-form');
                const profileImageInput = document.getElementById('profile-image-input');

                if (profileImageForm && profileImageInput) {
                    profileImageInput.addEventListener('change', function () {
                        if (this.files.length > 0) {
                            profileImageForm.submit();
                        }
                    });
                }

                // Initialize hero particles animation
                // const heroParticles = document.querySelector('.hero-particles');
                // if (heroParticles) {
                //     heroParticles.style.animation = 'float 20s ease-in-out infinite';
                // }

                // Initialize stat cards animations
                const statCards = document.querySelectorAll('.stat-card');
                if (statCards.length > 0) {
                    statCards.forEach((card, index) => {
                        card.style.animationDelay = `${index * 0.1}s`;
                        card.classList.add('animate-fade-up');
                    });
                }

                // Initialize info items animations
                const infoItems = document.querySelectorAll('.info-item');
                if (infoItems.length > 0) {
                    infoItems.forEach((item, index) => {
                        item.style.animationDelay = `${index * 0.1}s`;
                        item.classList.add('animate-fade-up');
                    });
                }

                // Initialize social cards animations
                const socialCards = document.querySelectorAll('.social-card');
                if (socialCards.length > 0) {
                    socialCards.forEach((card, index) => {
                        card.style.animationDelay = `${index * 0.1}s`;
                        card.classList.add('animate-fade-up');
                    });
                }
            }, 100);
        }

        initializePostPage() {
            // Force activate post detail CSS
            const postDetailCSS = document.getElementById('post-detail-css');
            if (postDetailCSS) {
                postDetailCSS.media = 'all';
            }

            // Initialize Post page functionality
            setTimeout(() => {
                // Initialize image lightbox effect
                const postImage = document.querySelector('.post-image-container');
                if (postImage) {
                    postImage.addEventListener('click', function () {
                        const img = this.querySelector('img');
                        if (img) {
                            const lightbox = document.createElement('div');
                            lightbox.className = 'image-lightbox';
                            lightbox.innerHTML = `
                            <div class="lightbox-content">
                                <span class="lightbox-close">&times;</span>
                                <img src="${img.src}" alt="${img.alt}">
                            </div>
                        `;
                            document.body.appendChild(lightbox);

                            setTimeout(() => lightbox.classList.add('active'), 10);

                            const close = () => {
                                lightbox.classList.remove('active');
                                setTimeout(() => lightbox.remove(), 300);
                            };

                            lightbox.querySelector('.lightbox-close').addEventListener('click', close);
                            lightbox.addEventListener('click', (e) => {
                                if (e.target === lightbox) close();
                            });
                        }
                    });
                }

                // Initialize share buttons with dynamic data
                const shareButtons = document.querySelectorAll('.share-btn');
                if (shareButtons.length > 0) {
                    const currentUrl = encodeURIComponent(window.location.href);
                    const pageTitle = encodeURIComponent(document.title);

                    shareButtons.forEach(btn => {
                        const platform = btn.classList.contains('facebook') ? 'facebook' :
                            btn.classList.contains('twitter') ? 'twitter' :
                                btn.classList.contains('whatsapp') ? 'whatsapp' :
                                    btn.classList.contains('telegram') ? 'telegram' :
                                        btn.classList.contains('linkedin') ? 'linkedin' : null;

                        if (platform) {
                            btn.addEventListener('click', (e) => {
                                // Share functionality
                            });
                        }
                    });
                }

                // Animate stat items
                const statItems = document.querySelectorAll('.stat-item');
                if (statItems.length > 0) {
                    statItems.forEach((item, index) => {
                        item.style.animationDelay = `${index * 0.1}s`;
                        item.classList.add('animate-slide-up');
                    });
                }

                // Animate related posts
                const relatedPosts = document.querySelectorAll('.related-post-item');
                if (relatedPosts.length > 0) {
                    relatedPosts.forEach((post, index) => {
                        post.style.animationDelay = `${index * 0.1}s`;
                        post.classList.add('animate-slide-up');
                    });
                }

                // Animate tags
                const tags = document.querySelectorAll('.tag-item');
                if (tags.length > 0) {
                    tags.forEach((tag, index) => {
                        tag.style.animationDelay = `${index * 0.05}s`;
                        tag.classList.add('animate-fade-in');
                    });
                }

                // Animate share buttons
                const shareBtns = document.querySelectorAll('.share-btn');
                if (shareBtns.length > 0) {
                    shareBtns.forEach((btn, index) => {
                        btn.style.animationDelay = `${index * 0.1}s`;
                        btn.classList.add('animate-slide-up');
                    });
                }
            }, 100);
        }

        initializeHomePage() {
            // Re-initialize home search if the function exists
            if (typeof window.initializeHomeSearch === 'function') {
                // Reset the initialized flag to allow re-initialization
                const searchInput = document.getElementById('home-search-input');
                if (searchInput) {
                    searchInput.removeAttribute('data-home-search-initialized');
                }
                window.initializeHomeSearch();
            }

            // Re-initialize hero text animation
            if (typeof window.initHeroSplitText === 'function') {
                window.initHeroSplitText();
            }

            // Re-initialize particles for hero section
            if (typeof window.initializeParticles === 'function') {
                window.initializeParticles();
            }

            // Re-initialize favoriteManager for home page posts
            if (window.favoriteManager) {
                window.favoriteManager.init();
            }
        }

        // Clear cache
        clearCache() {
            this.cache.clear();
        }

        // Preload page
        async preloadPage(url) {
            try {
                await this.fetchPageContent(url);
            } catch (error) {
                console.warn('Failed to preload page:', url, error);
            }
        }
    }

} // Fim da verificação de carregamento

// Initialize as soon as the DOM is available. This keeps the first click in the
// admin panel dynamic even when the script is loaded after DOMContentLoaded.
if (typeof window.DynamicLoader !== 'undefined') {
    window.ensureDynamicLoader = function () {
        if (!window.dynamicLoader) {
            window.dynamicLoader = new window.DynamicLoader();
        }
        return window.dynamicLoader;
    };

    // O script fica no fim do body: a estrutura de navegação já existe e pode ser
    // interceptada imediatamente. Esperar DOMContentLoaded fazia o primeiro clique do
    // painel escapar e recarregar sidebar + conteúdo por completo.
    window.ensureDynamicLoader();
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.ensureDynamicLoader, { once: true });
    }
}

// Global functions
window.showCoverageMap = function () {
    if (window.ContactPage && typeof window.ContactPage.openCoverageModal === 'function') {
        window.ContactPage.openCoverageModal();
        return;
    }

    alert('Nossa cobertura abrange todo o território nacional através da internet. Atendemos clientes de qualquer estado do Brasil!');
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DynamicLoader;
}
