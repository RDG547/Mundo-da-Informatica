/**
 * Dynamic Page Loading System
 * Loads page content dynamically without full page reload
 */

class DynamicLoader {
    constructor() {
        this.currentUrl = window.location.href;
        this.isLoading = false;
        this.cache = new Map();
        this.init();
    }

    init() {
        this.bindEvents();
        this.createLoadingIndicator();
        this.handleBrowserNavigation();

        // Initialize page styles for current page
        this.initializeCurrentPageStyles();
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
        } else if (currentPath.startsWith('/categoria/') || document.querySelector('.category-hero')) {
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
            const link = e.target.closest('a');
            if (this.shouldInterceptLink(link)) {
                e.preventDefault();
                e.stopPropagation(); // Prevent other click handlers
                e.stopImmediatePropagation(); // Prevent all other handlers
                this.loadPage(link.href);
                return false;
            }
        }, true); // Use capture phase

        // Intercept form submissions
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (this.shouldInterceptForm(form)) {
                e.preventDefault();
                this.submitForm(form);
            }
        });
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

        // DON'T INTERCEPT ANY ADMIN LINKS - admin is a separate application
        const url = new URL(link.href);
        if (url.pathname.startsWith('/admin')) {
            return false;
        }

        return true;
    }

    shouldInterceptForm(form) {
        // Não interceptar formulários de upload
        if (form.enctype === 'multipart/form-data') return false;
        // Não interceptar forms com target="_blank"
        if (form.target === '_blank') return false;
        // Não interceptar o formulário de login
        if (form.id === 'loginForm' || form.action.includes('/login')) return false;
        // Não interceptar formulários de perfil que já possuem tratamento AJAX próprio
        if (form.id === 'editProfileForm' || form.id === 'changePasswordForm') return false;
        return true;
    }

    async loadPage(url) {
        // Prevent loading same page or loading while already loading
        if (this.isLoading || url === this.currentUrl) {
            return;
        }

        this.isLoading = true;
        this.showLoading();

        try {
            let content;

            // Check cache first
            if (this.cache.has(url)) {
                content = this.cache.get(url);
            } else {
                content = await this.fetchPageContent(url);
                this.cache.set(url, content);
            }

            this.updatePage(content, url);
            this.updateUrl(url);

        } catch (error) {
            console.error('Error loading page:', error);
            // Fallback to normal navigation
            window.location.href = url;
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }

    async fetchPageContent(url) {
        const response = await fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
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

        return {
            title: doc.title,
            content: content,
            scripts: Array.from(doc.querySelectorAll('script[src]')),
            inlineScripts: Array.from(doc.querySelectorAll('script:not([src])')),
            styles: Array.from(doc.querySelectorAll('link[rel="stylesheet"]')),
            inlineStyles: Array.from(doc.querySelectorAll('style'))
        };
    }

    updatePage(pageData, url) {
        // Update page title
        document.title = pageData.title;

        // Load page-specific styles (skipped for admin)
        this.loadPageStyles(url, pageData.styles);

        // Find main content container
        // For admin pages, target the admin-content-wrapper specifically
        const isAdminPage = window.location.pathname.startsWith('/admin');
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
            if (isAdminPage) {
                // Instant update for admin
                mainContainer.innerHTML = pageData.content.innerHTML;
                this.loadPageScripts(pageData.scripts);
                this.executeInlineScripts(pageData.inlineScripts);
                this.applyInlineStyles(pageData.inlineStyles);
                this.executeContentScripts(mainContainer);
                this.reinitializeComponents();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                // Smooth transition for public pages
                mainContainer.style.opacity = '0';

                setTimeout(() => {
                    mainContainer.innerHTML = pageData.content.innerHTML;
                    this.loadPageScripts(pageData.scripts);
                    this.executeInlineScripts(pageData.inlineScripts);
                    this.applyInlineStyles(pageData.inlineStyles);
                    this.executeContentScripts(mainContainer);
                    // Wait a bit for scripts to load before reinitializing
                    setTimeout(() => {
                        this.reinitializeComponents();
                    }, 200);
                    mainContainer.style.opacity = '1';
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }, 150);
            }
        }

        // Handle footer visibility based on page
        this.handleFooterVisibility(url);

        // Update active navigation
        this.updateActiveNavigation(url);
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
        // Re-initialize favorite buttons and modal
        if (window.favoriteManager) {
            // Garante que o modal existe após carregamento dinâmico
            window.favoriteManager.createConfirmModal();
            window.favoriteManager.init();
        }

        // Re-initialize search suggestions for all search inputs
        if (window.SearchSuggestions) {
            // Buscar todos os inputs de pesquisa
            const searchInputs = document.querySelectorAll('input[name="q"], .search-bar input, #home-search-input');
            searchInputs.forEach(input => {
                if (input && !input.hasAttribute('data-suggestions-initialized')) {
                    new SearchSuggestions(`#${input.id || 'home-search-input'}`);
                    input.setAttribute('data-suggestions-initialized', 'true');
                }
            });
        }

        // Re-initialize feature modals (for categories pages)
        if (typeof window.initFeatureModals === 'function') {
            window.initFeatureModals();
        }

        // Re-initialize FAQ functionality
        if (window.location.pathname === '/faq' && typeof window.toggleFAQ === 'function') {
            this.initializeFAQ();
        }

        // Re-initialize contact form functionality
        if (window.location.pathname === '/contact') {
            this.initializeContactForm();
        }

        // Re-initialize category page functionality
        if (window.location.pathname.startsWith('/categoria/')) {
            this.initializeCategoryPage();
        }

        // Re-initialize profile page functionality
        if (window.location.pathname.startsWith('/profile')) {
            this.initializeProfilePage();
        }

        // Re-initialize post page functionality
        const currentPath = window.location.pathname;
        if (currentPath.startsWith('/post/') || (currentPath.split('/').length === 3 && currentPath.split('/')[1] && currentPath.split('/')[2])) {
            this.initializePostPage();
        }

        // Re-initialize legal pages functionality
        if (window.location.pathname === '/termos-de-uso' || window.location.pathname === '/politica-de-privacidade') {
            this.initializeLegalPage();
        }

        // Re-initialize admin components
        if (currentPath.startsWith('/admin')) {
            this.reinitializeAdminComponents();
        }

        // Re-initialize home page functionality
        if (currentPath === '/' || currentPath === '/home' || document.querySelector('#hero-particles')) {
            this.initializeHomePage();
        }

        // Re-initialize Plans page functionality
        if ((currentPath === '/planos' || currentPath === '/plans') && typeof window.initializePlansPage === 'function') {
            window.initializePlansPage();
        }

        // Re-initialize download buttons (CRITICAL for download limit checks)
        if (typeof window.setupDownloadButtons === 'function') {
            window.setupDownloadButtons();
        }

        // Re-initialize any other components
        this.dispatchEvent('pageLoaded');
    }

    reinitializeAdminComponents() {
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

        // Re-initialize admin-specific functionality
        const adminScriptEvent = new CustomEvent('adminPageLoaded');
        document.dispatchEvent(adminScriptEvent);
    }

    loadPageStyles(url, styles) {
        // Don't reload styles in admin area - they're already loaded
        const path = new URL(url, window.location.origin).pathname;
        if (path.startsWith('/admin')) {
            return;
        }

        // Reset all page-specific styles to print media (disabled)
        const faqCSS = document.getElementById('faq-css');
        const contactCSS = document.getElementById('contact-css');
        const aboutCSS = document.getElementById('about-css');
        const categoryCSS = document.getElementById('category-css');
        const profileCSS = document.getElementById('profile-css');
        const plansCSS = document.getElementById('plans-css');

        if (faqCSS) faqCSS.media = 'print';
        if (contactCSS) contactCSS.media = 'print';
        if (aboutCSS) aboutCSS.media = 'print';
        if (categoryCSS) categoryCSS.media = 'print';
        if (profileCSS) profileCSS.media = 'print';
        if (plansCSS) plansCSS.media = 'print';

        // Determine which page-specific CSS to activate based on URL
        if (path === '/faq' && faqCSS) {
            faqCSS.media = 'all';
        } else if ((path === '/contact' || path === '/contato') && contactCSS) {
            contactCSS.media = 'all';
        } else if ((path === '/about' || path === '/sobre') && aboutCSS) {
            aboutCSS.media = 'all';
        } else if ((path.startsWith('/categoria/') || path === '/categorias') && categoryCSS) {
            categoryCSS.media = 'all';
        } else if (path.startsWith('/profile') && profileCSS) {
            profileCSS.media = 'all';
            console.log('Profile CSS activated:', profileCSS);
        } else if ((path === '/plans' || path === '/planos') && plansCSS) {
            plansCSS.media = 'all';
        }
    }

    loadPageScripts(scripts) {
        // Don't reload scripts in admin area - they're already loaded
        const currentPath = window.location.pathname;
        if (currentPath.startsWith('/admin')) {
            return;
        }

        // Load page-specific scripts
        scripts.forEach(scriptElement => {
            if (scriptElement.src && !document.querySelector(`script[src="${scriptElement.src}"]`)) {
                const script = document.createElement('script');
                script.src = scriptElement.src;
                script.async = true; // Load asynchronously
                script.setAttribute('data-dynamic-js', 'true');

                // Add load listener for debugging
                script.onload = () => {
                    console.log('Script loaded:', scriptElement.src);
                };

                script.onerror = () => {
                    console.error('Failed to load script:', scriptElement.src);
                };

                document.head.appendChild(script);
            }
        });
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
        // Initialize FAQ functionality
        setTimeout(() => {
            const faqSearch = document.getElementById('faq-search');
            if (faqSearch) {
                // Re-bind FAQ search functionality
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
                btn.addEventListener('click', function () {
                    const searchTerm = this.dataset.search;
                    if (faqSearch) {
                        faqSearch.value = searchTerm;
                        faqSearch.dispatchEvent(new Event('input'));
                    }
                });
            });
        }, 100);
    }

    initializeContactForm() {
        // Initialize contact form functionality
        setTimeout(() => {
            const messageTextarea = document.getElementById('message');
            const charCounter = document.getElementById('char-count');

            if (messageTextarea && charCounter) {
                messageTextarea.addEventListener('input', function () {
                    const currentLength = this.value.length;
                    charCounter.textContent = currentLength;

                    if (currentLength > 800) {
                        charCounter.style.color = '#ff6b6b';
                    } else if (currentLength > 600) {
                        charCounter.style.color = '#ffa726';
                    } else {
                        charCounter.style.color = '#666';
                    }
                });
            }

            // Form validation and submission
            const contactForm = document.getElementById('contact-form');
            if (contactForm) {
                contactForm.addEventListener('submit', function (e) {
                    e.preventDefault();

                    // Add loading state
                    const submitBtn = this.querySelector('button[type="submit"]');
                    const originalText = submitBtn.innerHTML;
                    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
                    submitBtn.disabled = true;

                    // Simulate form submission
                    setTimeout(() => {
                        alert('Mensagem enviada com sucesso! Entraremos em contato em breve.');
                        submitBtn.innerHTML = originalText;
                        submitBtn.disabled = false;
                        this.reset();
                        if (charCounter) charCounter.textContent = '0';
                    }, 2000);
                });
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
        // Remove active class from all nav links
        document.querySelectorAll('.nav-menu a').forEach(link => {
            link.classList.remove('active');
        });

        // Add active class to current page link
        const currentLink = document.querySelector(`a[href="${url}"]`);
        if (currentLink) {
            currentLink.classList.add('active');
        }
    }

    updateUrl(url) {
        this.currentUrl = url;
        history.pushState({ url }, '', url);
    }

    handleBrowserNavigation() {
        window.addEventListener('popstate', (e) => {
            if (e.state && e.state.url) {
                this.loadPage(e.state.url);
            }
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

            if (response.redirected) {
                this.loadPage(response.url);
            } else {
                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const content = {
                    title: doc.title,
                    content: doc.querySelector('main') || doc.querySelector('.container') || doc.body
                };

                this.updatePage(content, window.location.href);
            }

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
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(255, 255, 255, 0.9);
                display: none;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                backdrop-filter: blur(5px);
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
        const loader = document.getElementById('dynamic-loader');
        if (loader) {
            loader.style.display = 'flex';
        }
    }

    hideLoading() {
        const loader = document.getElementById('dynamic-loader');
        if (loader) {
            loader.style.display = 'none';
        }
    }

    dispatchEvent(eventName, data = {}) {
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }

    initializeAboutPage() {
        // Initialize About page functionality
        setTimeout(() => {
            // Initialize statistics counter animation
            const statsCounters = document.querySelectorAll('.stat-number');
            if (statsCounters.length > 0) {
                // Animate counters when they come into view
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const counter = entry.target;
                            const target = parseInt(counter.innerText);
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
        }, 100);
    }

    initializeCategoryPage() {
        // Initialize Category page functionality
        setTimeout(() => {
            // Initialize category search functionality
            const searchInput = document.querySelector('.category-search-input');
            const suggestionsDropdown = document.querySelector('.search-suggestions-dropdown');

            if (searchInput && suggestionsDropdown) {
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

                    const html = suggestions.map(suggestion => `
                        <div class="suggestion-item" data-url="${suggestion.url}">
                            <div class="suggestion-icon">
                                <i class="${suggestion.icon}"></i>
                            </div>
                            <div class="suggestion-content">
                                <div class="suggestion-title">${suggestion.title}</div>
                                <div class="suggestion-description">${suggestion.description}</div>
                            </div>
                        </div>
                    `).join('');

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
        if (profileCSS) {
            profileCSS.media = 'all';
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
        if (!this.cache.has(url)) {
            try {
                const content = await this.fetchPageContent(url);
                this.cache.set(url, content);
            } catch (error) {
                console.warn('Failed to preload page:', url, error);
            }
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    // Only initialize if not in admin area
    if (!window.location.pathname.startsWith('/admin')) {
        window.dynamicLoader = new DynamicLoader();
    }
});

// Global functions
window.showCoverageMap = function () {
    alert('Nossa cobertura abrange todo o território nacional através da internet. Atendemos clientes de qualquer estado do Brasil!');
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DynamicLoader;
}
