/**
 * Navbar Functionality
 * Handles mobile menu, dropdowns, and scroll effects
 */

(function () {
    'use strict';

    function updateHeaderScrollState() {
        const header = document.querySelector('header');
        if (header) {
            header.classList.toggle('scrolled', window.scrollY > 50);
        }
    }

    function bindHeaderScrollListener() {
        if (window.__navbarScrollListenerBound) {
            updateHeaderScrollState();
            return;
        }

        window.__navbarScrollListenerBound = true;
        window.addEventListener('scroll', updateHeaderScrollState, { passive: true });
        updateHeaderScrollState();
    }

    function syncMobileMenuIcon() {
        const navMenu = document.querySelector('.nav-menu');
        const menuToggleIcon = document.querySelector('.mobile-menu-toggle i');
        if (!navMenu || !menuToggleIcon) {
            return;
        }

        if (navMenu.classList.contains('active')) {
            menuToggleIcon.classList.remove('fa-bars');
            menuToggleIcon.classList.add('fa-times');
        } else {
            menuToggleIcon.classList.remove('fa-times');
            menuToggleIcon.classList.add('fa-bars');
        }
    }

    function toggleMobileMenu() {
        const navMenu = document.querySelector('.nav-menu');
        if (!navMenu) {
            return;
        }

        navMenu.classList.toggle('active');
        syncMobileMenuIcon();
    }

    function bindDropdowns() {
        document.querySelectorAll('.dropdown').forEach((dropdown) => {
            const toggle = dropdown.querySelector('.dropdown-toggle');
            if (!toggle || toggle.dataset.navbarDropdownBound === 'true') {
                return;
            }

            toggle.dataset.navbarDropdownBound = 'true';
            toggle.addEventListener('click', function (e) {
                if (window.innerWidth <= 992) {
                    e.preventDefault();
                    dropdown.classList.toggle('active');
                    return;
                }

                if (toggle.getAttribute('href') === '#') {
                    e.preventDefault();
                }
            });
        });
    }

    function bindSubmenus() {
        document.querySelectorAll('.dropdown-submenu').forEach((submenu) => {
            const toggle = submenu.querySelector('.dropdown-item-main');
            if (!toggle || toggle.dataset.navbarSubmenuBound === 'true') {
                return;
            }

            toggle.dataset.navbarSubmenuBound = 'true';
            toggle.addEventListener('click', function (e) {
                if (window.innerWidth <= 992) {
                    e.preventDefault();
                    submenu.classList.toggle('active');
                }
            });
        });
    }

    function bindOutsideClick() {
        if (window.__navbarOutsideClickBound) {
            return;
        }

        window.__navbarOutsideClickBound = true;
        document.addEventListener('click', function (e) {
            if (e.target.closest('.dropdown')) {
                return;
            }

            document.querySelectorAll('.dropdown.active').forEach((dropdown) => {
                dropdown.classList.remove('active');
            });
            document.querySelectorAll('.dropdown-submenu.active').forEach((submenu) => {
                submenu.classList.remove('active');
            });
        });
    }

    function initNavbar() {
        bindHeaderScrollListener();
        bindDropdowns();
        bindSubmenus();
        bindOutsideClick();
        syncMobileMenuIcon();
    }

    window.toggleMobileMenu = toggleMobileMenu;
    window.initNavbar = initNavbar;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavbar);
    } else {
        initNavbar();
    }

    document.addEventListener('pageLoaded', initNavbar);
})();
