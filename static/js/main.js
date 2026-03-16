(function () {
    'use strict';

    function hidePreloader() {
        const preloader = document.querySelector('.preloader');
        if (!preloader || preloader.dataset.hidden === 'true') {
            return;
        }

        setTimeout(() => {
            preloader.classList.add('fade-out');
            setTimeout(() => {
                preloader.style.display = 'none';
                preloader.dataset.hidden = 'true';
            }, 500);
        }, 500);
    }

    function initializeAOS() {
        if (typeof AOS === 'undefined') {
            return;
        }

        if (!window.__mainAosInitialized) {
            AOS.init({
                duration: 800,
                easing: 'ease-in-out',
                once: true,
                mirror: false
            });
            window.__mainAosInitialized = true;
            return;
        }

        if (typeof AOS.refreshHard === 'function') {
            AOS.refreshHard();
        } else if (typeof AOS.refresh === 'function') {
            AOS.refresh();
        }
    }

    function handleImageState(img) {
        if (img.naturalWidth === 0 || img.naturalHeight === 0) {
            img.classList.add('error');
        } else {
            img.classList.remove('error');
            const container = img.closest('.admin-profile-img, .user-avatar, .profile-img');
            if (container) {
                container.classList.remove('loading');
            }
        }
    }

    function bindProfileImage(img) {
        if (!img || img.tagName !== 'IMG') {
            return;
        }

        if (img.dataset.mainProfileBound === 'true') {
            if (img.complete) {
                handleImageState(img);
            }
            return;
        }

        img.dataset.mainProfileBound = 'true';

        if (img.complete) {
            handleImageState(img);
        } else {
            img.addEventListener('load', function () {
                handleImageState(this);
            });
        }

        img.addEventListener('error', function () {
            this.classList.add('error');

            if (!this.dataset.retried) {
                this.dataset.retried = 'true';
                const originalSrc = this.src;
                this.removeAttribute('src');
                setTimeout(() => {
                    if (this) {
                        this.src = originalSrc;
                    }
                }, 500);
            }
        });
    }

    function handleProfileImages() {
        const profileImages = document.querySelectorAll('.profile-img, .profile-img img, .user-avatar img, .admin-profile-img img');
        profileImages.forEach(bindProfileImage);
    }

    function bindMenuToggle() {
        const menuToggle = document.querySelector('.menu-toggle');
        const navMenu = document.querySelector('.nav-menu');

        if (!menuToggle || !navMenu || menuToggle.dataset.mainMenuBound === 'true') {
            return;
        }

        menuToggle.dataset.mainMenuBound = 'true';
        menuToggle.addEventListener('click', function () {
            navMenu.classList.toggle('active');
            menuToggle.classList.toggle('active');
        });
    }

    function bindNavLinks() {
        const navMenu = document.querySelector('.nav-menu');
        const menuToggle = document.querySelector('.menu-toggle');

        document.querySelectorAll('.nav-menu a').forEach((link) => {
            if (link.dataset.mainNavLinkBound === 'true') {
                return;
            }

            link.dataset.mainNavLinkBound = 'true';
            link.addEventListener('click', () => {
                if (navMenu) {
                    navMenu.classList.remove('active');
                }
                if (menuToggle) {
                    menuToggle.classList.remove('active');
                }
            });
        });
    }

    function bindAccordionHeaders() {
        document.querySelectorAll('.accordion-header').forEach((header) => {
            if (header.dataset.mainAccordionBound === 'true') {
                return;
            }

            header.dataset.mainAccordionBound = 'true';
            header.addEventListener('click', () => {
                const content = header.nextElementSibling;
                const accordionHeaders = document.querySelectorAll('.accordion-header');

                header.classList.toggle('active');

                accordionHeaders.forEach((otherHeader) => {
                    if (otherHeader !== header) {
                        otherHeader.classList.remove('active');
                        if (otherHeader.nextElementSibling) {
                            otherHeader.nextElementSibling.style.maxHeight = 0;
                            otherHeader.nextElementSibling.classList.remove('active');
                        }
                    }
                });

                if (!content) {
                    return;
                }

                if (header.classList.contains('active')) {
                    content.style.maxHeight = `${content.scrollHeight}px`;
                    content.classList.add('active');
                } else {
                    content.style.maxHeight = 0;
                    content.classList.remove('active');
                }
            });
        });
    }

    function bindSmoothScrollAnchors() {
        document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
            if (anchor.dataset.mainSmoothScrollBound === 'true') {
                return;
            }

            anchor.dataset.mainSmoothScrollBound = 'true';
            anchor.addEventListener('click', function (e) {
                const href = this.getAttribute('href');
                if (!href || href === '#') {
                    return;
                }

                const targetElement = document.querySelector(href);
                if (!targetElement) {
                    return;
                }

                e.preventDefault();
                window.scrollTo({
                    top: targetElement.offsetTop - 80,
                    behavior: 'smooth'
                });
            });
        });
    }

    function updateNavbarScrollState() {
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            navbar.classList.toggle('scrolled', window.scrollY > 50);
        }
    }

    function updateScrollTopState() {
        const scrollTop = document.querySelector('.scroll-top');
        const floatingChat = document.getElementById('floating-chat-btn');
        const floatingChatPanel = document.getElementById('floating-chat-panel');
        const shouldShift = window.scrollY > 300;

        if (scrollTop) {
            scrollTop.classList.toggle('active', shouldShift);
        }
        if (floatingChat) {
            floatingChat.classList.toggle('shifted-up', shouldShift);
        }
        if (floatingChatPanel) {
            floatingChatPanel.classList.toggle('shifted-up', shouldShift);
        }
    }

    function bindScrollTopButton() {
        const scrollTop = document.querySelector('.scroll-top');
        if (!scrollTop) {
            return;
        }

        if (scrollTop.dataset.mainScrollTopBound !== 'true') {
            scrollTop.dataset.mainScrollTopBound = 'true';
            scrollTop.addEventListener('click', () => {
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            });
        }

        updateScrollTopState();
    }

    function bindDarkModeToggle() {
        const darkModeToggle = document.querySelector('.dark-mode');
        if (!darkModeToggle || darkModeToggle.dataset.mainDarkModeBound === 'true') {
            return;
        }

        darkModeToggle.dataset.mainDarkModeBound = 'true';
        darkModeToggle.addEventListener('click', () => {
            document.body.setAttribute(
                'data-theme',
                document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'
            );
        });
    }

    function bindShareButtons() {
        document.querySelectorAll('.social-share a').forEach((button) => {
            if (button.dataset.mainShareBound === 'true') {
                return;
            }

            button.dataset.mainShareBound = 'true';
            button.addEventListener('click', function (e) {
                e.preventDefault();

                const pageUrl = window.location.href;
                const pageTitle = document.title;

                if (this.querySelector('.fa-facebook') || this.classList.contains('facebook')) {
                    window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl)}`, 'facebook-share', 'width=580,height=296');
                } else if (this.querySelector('.fa-twitter') || this.classList.contains('twitter')) {
                    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(pageTitle)}&url=${encodeURIComponent(pageUrl)}`, 'twitter-share', 'width=550,height=235');
                } else if (this.querySelector('.fa-whatsapp') || this.classList.contains('whatsapp')) {
                    window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(`${pageTitle} ${pageUrl}`)}`, 'whatsapp-share', 'width=550,height=450');
                } else if (this.querySelector('.fa-telegram') || this.classList.contains('telegram')) {
                    window.open(`https://telegram.me/share/url?url=${encodeURIComponent(pageUrl)}&text=${encodeURIComponent(pageTitle)}`, 'telegram-share', 'width=550,height=450');
                }
            });
        });
    }

    function getLazyImageObserver() {
        if (!window.__mainLazyImageObserver) {
            window.__mainLazyImageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }

                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    observer.unobserve(img);
                });
            });
        }

        return window.__mainLazyImageObserver;
    }

    function initializeLazyImages() {
        const observer = getLazyImageObserver();
        document.querySelectorAll('img[data-src]:not([data-main-lazy-observed])').forEach((img) => {
            img.dataset.mainLazyObserved = 'true';
            observer.observe(img);
        });
    }

    function getRevealObserver() {
        if (!window.__mainRevealObserver) {
            window.__mainRevealObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }

                    entry.target.classList.add('animate');
                    observer.unobserve(entry.target);
                });
            }, {
                root: null,
                threshold: 0.1
            });
        }

        return window.__mainRevealObserver;
    }

    function initializeRevealCards() {
        const observer = getRevealObserver();
        document.querySelectorAll('.category-card, .post-card, .team-member').forEach((item) => {
            item.classList.add('reveal');
            if (item.dataset.mainRevealObserved === 'true') {
                return;
            }

            item.dataset.mainRevealObserved = 'true';
            observer.observe(item);
        });
    }

    function updateParallaxEffects() {
        document.querySelectorAll('.hero, .cta, .about-header, .contact-header').forEach((element) => {
            const scrollPosition = window.scrollY;
            const elementPosition = element.offsetTop;
            const elementHeight = element.offsetHeight;

            if (scrollPosition > elementPosition - window.innerHeight && scrollPosition < elementPosition + elementHeight) {
                const speed = Number(element.dataset.speed || 0.5);
                const yPos = (scrollPosition - elementPosition) * speed;
                element.style.backgroundPosition = `center ${yPos}px`;
            }
        });
    }

    function getSimpleCounterObserver() {
        if (!window.__mainSimpleCounterObserver) {
            window.__mainSimpleCounterObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting || entry.target.dataset.mainCounterAnimated === 'true') {
                        return;
                    }

                    const countTarget = parseInt(entry.target.getAttribute('data-count') || '0', 10);
                    if (!Number.isFinite(countTarget) || countTarget <= 0) {
                        observer.unobserve(entry.target);
                        return;
                    }

                    entry.target.dataset.mainCounterAnimated = 'true';
                    let count = 0;
                    const duration = 2000;
                    const step = Math.max(1, Math.ceil(countTarget / (duration / 16)));

                    const counter = setInterval(() => {
                        count += step;
                        if (count >= countTarget) {
                            entry.target.textContent = countTarget;
                            clearInterval(counter);
                            return;
                        }

                        entry.target.textContent = count;
                    }, 16);

                    observer.unobserve(entry.target);
                });
            });
        }

        return window.__mainSimpleCounterObserver;
    }

    function initializeSimpleCounters() {
        const observer = getSimpleCounterObserver();
        document.querySelectorAll('.counter[data-count]').forEach((counter) => {
            if (counter.dataset.mainCounterObserved === 'true') {
                return;
            }

            counter.dataset.mainCounterObserved = 'true';
            observer.observe(counter);
        });
    }

    function initializeTypedText() {
        if (typeof Typed === 'undefined') {
            return;
        }

        const typedElement = document.querySelector('.typed-text');
        if (!typedElement) {
            if (window.__mainTypedInstance && typeof window.__mainTypedInstance.destroy === 'function') {
                window.__mainTypedInstance.destroy();
            }
            window.__mainTypedInstance = null;
            window.__mainTypedElement = null;
            return;
        }

        if (window.__mainTypedElement === typedElement && window.__mainTypedInstance) {
            return;
        }

        if (window.__mainTypedInstance && typeof window.__mainTypedInstance.destroy === 'function') {
            window.__mainTypedInstance.destroy();
        }

        const typedItems = typedElement.getAttribute('data-typed-items');
        if (!typedItems) {
            return;
        }

        window.__mainTypedElement = typedElement;
        window.__mainTypedInstance = new Typed(typedElement, {
            strings: typedItems.split(','),
            typeSpeed: 100,
            backSpeed: 50,
            backDelay: 2000,
            loop: true
        });
    }

    function getAnimationObserver() {
        if (!window.__mainAnimationObserver) {
            window.__mainAnimationObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }

                    entry.target.style.opacity = 1;
                    observer.unobserve(entry.target);
                });
            }, { threshold: 0.1 });
        }

        return window.__mainAnimationObserver;
    }

    function initializeStaticAnimations() {
        const observer = getAnimationObserver();
        document.querySelectorAll('.animate-fade-in, .animate-slide-left, .animate-slide-right, .animate-slide-up, .animate-pulse').forEach((elem) => {
            if (elem.dataset.mainAnimationObserved === 'true') {
                return;
            }

            elem.dataset.mainAnimationObserved = 'true';
            elem.style.opacity = 0;
            observer.observe(elem);
        });
    }

    function bindFilterButtons() {
        document.querySelectorAll('[data-filter]').forEach((button) => {
            if (button.dataset.mainFilterBound === 'true') {
                return;
            }

            button.dataset.mainFilterBound = 'true';
            button.addEventListener('click', function () {
                const filterValue = this.dataset.filter;
                const filterButtons = document.querySelectorAll('[data-filter]');
                const items = document.querySelectorAll('[data-category]');

                filterButtons.forEach((btn) => btn.classList.remove('active'));
                this.classList.add('active');

                items.forEach((item) => {
                    if (filterValue === 'all' || item.dataset.category === filterValue) {
                        item.style.display = 'block';
                        setTimeout(() => {
                            item.style.opacity = 1;
                            item.style.transform = 'scale(1)';
                        }, 10);
                    } else {
                        item.style.opacity = 0;
                        item.style.transform = 'scale(0.8)';
                        setTimeout(() => {
                            item.style.display = 'none';
                        }, 300);
                    }
                });
            });
        });
    }

    function initializeSwipers() {
        if (typeof Swiper === 'undefined') {
            return;
        }

        document.querySelectorAll('.swiper').forEach((swiperElement) => {
            if (swiperElement.dataset.mainSwiperInitialized === 'true') {
                if (swiperElement.swiper && typeof swiperElement.swiper.update === 'function') {
                    swiperElement.swiper.update();
                }
                return;
            }

            swiperElement.dataset.mainSwiperInitialized = 'true';
            new Swiper(swiperElement, {
                slidesPerView: 'auto',
                spaceBetween: 30,
                pagination: {
                    el: swiperElement.querySelector('.swiper-pagination') || '.swiper-pagination',
                    clickable: true,
                },
                navigation: {
                    nextEl: swiperElement.querySelector('.swiper-button-next') || '.swiper-button-next',
                    prevEl: swiperElement.querySelector('.swiper-button-prev') || '.swiper-button-prev',
                },
                breakpoints: {
                    640: {
                        slidesPerView: 1,
                        spaceBetween: 20,
                    },
                    768: {
                        slidesPerView: 2,
                        spaceBetween: 30,
                    },
                    1024: {
                        slidesPerView: 3,
                        spaceBetween: 30,
                    },
                }
            });
        });
    }

    function bindGlobalWindowHandlers() {
        if (window.__mainGlobalHandlersBound) {
            updateNavbarScrollState();
            updateScrollTopState();
            updateParallaxEffects();
            return;
        }

        window.__mainGlobalHandlersBound = true;
        window.addEventListener('scroll', () => {
            updateNavbarScrollState();
            updateScrollTopState();
            updateParallaxEffects();
        }, { passive: true });

        window.addEventListener('resize', () => {
            initializeAOS();
        }, { passive: true });

        updateNavbarScrollState();
        updateScrollTopState();
        updateParallaxEffects();
    }

    function initializeMainUi() {
        bindGlobalWindowHandlers();
        bindMenuToggle();
        bindNavLinks();
        bindAccordionHeaders();
        bindSmoothScrollAnchors();
        bindScrollTopButton();
        bindDarkModeToggle();
        bindShareButtons();
        handleProfileImages();
        initializeLazyImages();
        initializeRevealCards();
        initializeSimpleCounters();
        initializeTypedText();
        initializeStaticAnimations();
        bindFilterButtons();
        initializeSwipers();
        initializeAOS();
    }

    window.handleProfileImages = handleProfileImages;
    window.initializeMainUi = initializeMainUi;

    window.addEventListener('load', () => {
        hidePreloader();
        initializeMainUi();
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeMainUi);
    } else {
        initializeMainUi();
    }

    document.addEventListener('pageLoaded', () => {
        setTimeout(initializeMainUi, 0);
    });
})();
