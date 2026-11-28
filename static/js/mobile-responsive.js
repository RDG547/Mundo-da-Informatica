/* Mobile-only interaction layer. Existing desktop navigation and business handlers stay intact. */
(() => {
    'use strict';
    if (window.__mdiMobileReady) return;
    window.__mdiMobileReady = true;
    const navMedia = matchMedia('(max-width: 1100px)');
    const adminMedia = matchMedia('(max-width: 991px)');
    const smallMedia = matchMedia('(max-width: 767px)');
    let nextId = 0;
    let returnFocus = null;
    const nav = () => document.getElementById('primary-navigation');
    const navButton = () => document.querySelector('.mobile-menu-toggle');
    function syncNav(open) {
        const menu = nav();
        if (!menu) return;
        menu.classList.toggle('active', open);
        navButton()?.setAttribute('aria-expanded', String(open));
        navButton()?.setAttribute('aria-label', open ? 'Fechar menu de navegação' : 'Abrir menu de navegação');
        const icon = navButton()?.querySelector('i');
        icon?.classList.toggle('fa-bars', !open);
        icon?.classList.toggle('fa-times', open);
        document.documentElement.classList.toggle('mdi-nav-open', open && navMedia.matches);
        if (!open) {
            menu.querySelectorAll('.dropdown.active,.dropdown-submenu.active').forEach(el => el.classList.remove('active'));
            menu.querySelectorAll('[aria-expanded="true"]').forEach(el => el.setAttribute('aria-expanded','false'));
        }
    }
    function syncAdmin(open) {
        const sidebar = document.getElementById('adminSidebar');
        if (!sidebar) return;
        sidebar.classList.toggle('show', open);
        if (adminMedia.matches) sidebar.classList.remove('collapsed');
        document.documentElement.classList.toggle('mdi-admin-open', open && adminMedia.matches);
        document.querySelector('.mdi-mobile-admin-toggle')?.setAttribute('aria-expanded', String(open));
        document.querySelector('.mdi-admin-backdrop')?.classList.toggle('is-visible', open);
        if (adminMedia.matches) sidebar.inert = !open;
        else sidebar.inert = false;
        if (open) {
            returnFocus = document.activeElement;
            sidebar.querySelector('#sidebarToggle')?.focus({preventScroll:true});
        } else if (returnFocus) {
            returnFocus.focus({preventScroll:true});
            returnFocus = null;
        }
    }
    window.mdiCloseMobileNav = () => { if (navMedia.matches) syncNav(false); };
    window.mdiCloseMobileAdmin = () => { if (adminMedia.matches && document.documentElement.classList.contains('mdi-admin-open')) syncAdmin(false); };
    function prepare() {
        const menu = nav();
        if (menu) {
            menu.querySelectorAll('.dropdown-submenu').forEach(group => {
                const child = group.querySelector(':scope > .submenu-content');
                const link = group.querySelector(':scope > .dropdown-item-main');
                if (!child || !link || group.querySelector(':scope > .mdi-submenu-toggle')) return;
                child.id ||= 'mdi-submenu-' + (++nextId);
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'mdi-submenu-toggle';
                button.setAttribute('aria-expanded','false');
                button.setAttribute('aria-controls',child.id);
                button.setAttribute('aria-label','Subcategorias de ' + link.textContent.trim());
                const icon = document.createElement('i');
                icon.className = 'fas fa-chevron-down';
                icon.setAttribute('aria-hidden','true');
                button.append(icon);
                link.after(button);
            });
            menu.querySelectorAll('.dropdown > .dropdown-toggle').forEach(link => {
                if (!link.hasAttribute('aria-expanded')) link.setAttribute('aria-expanded','false');
            });
        }
        if (document.getElementById('adminSidebar') && !document.querySelector('.mdi-admin-backdrop')) {
            const backdrop = document.createElement('button');
            backdrop.type = 'button';
            backdrop.className = 'mdi-admin-backdrop';
            backdrop.setAttribute('aria-label','Fechar menu administrativo');
            document.body.append(backdrop);
        }
        const sidebar = document.getElementById('adminSidebar');
        if (sidebar) sidebar.inert = adminMedia.matches && !sidebar.classList.contains('show');
        // Existing scroll containers remain untouched; plain wide tables get local scrolling.
        document.querySelectorAll('main table,.admin-content table').forEach(table => {
            if (!table.closest('.table-responsive,.admin-table-container,.table-scroll,.plans-comparison')) table.classList.add('mdi-mobile-table');
        });
    }
    document.addEventListener('click', event => {
        const target = event.target instanceof Element ? event.target : event.target.parentElement;
        if (!target) return;
        if (adminMedia.matches && target.closest('.mdi-mobile-admin-toggle,#sidebarToggle,.mdi-admin-backdrop,.sidebar-backdrop')) {
            if (!document.getElementById('adminSidebar')) return;
            // Capture once; avoid the legacy competing collapse/show click listeners.
            event.preventDefault(); event.stopImmediatePropagation();
            syncAdmin(!target.closest('.mdi-admin-backdrop,.sidebar-backdrop') && !document.documentElement.classList.contains('mdi-admin-open'));
            return;
        }
        if (!navMedia.matches) return;
        if (target.closest('.mobile-menu-toggle')) {
            event.preventDefault(); event.stopImmediatePropagation();
            syncNav(!nav()?.classList.contains('active'));
            return;
        }
        const toggle = target.closest('.mdi-submenu-toggle');
        if (toggle) {
            event.preventDefault(); event.stopImmediatePropagation();
            const group = toggle.closest('.dropdown-submenu');
            const open = !group.classList.contains('active');
            group.classList.toggle('active',open);
            toggle.setAttribute('aria-expanded',String(open));
            return;
        }
        const link = target.closest('#primary-navigation a');
        if (link && !link.matches('.dropdown > .dropdown-toggle') && link.getAttribute('href') !== '#') syncNav(false);
        else if (!target.closest('#primary-navigation,.mobile-menu-toggle') && nav()?.classList.contains('active')) syncNav(false);
    }, true);
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        if (adminMedia.matches && document.documentElement.classList.contains('mdi-admin-open')) syncAdmin(false);
        if (navMedia.matches && nav()?.classList.contains('active')) { syncNav(false); navButton()?.focus(); }
    });
    document.addEventListener('click', event => {
        if (adminMedia.matches && event.target.closest?.('#adminSidebar a[href]:not([href="#"])')) syncAdmin(false);
    });
    navMedia.addEventListener('change', () => syncNav(false));
    adminMedia.addEventListener('change', () => syncAdmin(false));
    const refresh = () => { if(navMedia.matches) syncNav(false); if(adminMedia.matches) syncAdmin(false); prepare(); };
    document.addEventListener('pageLoaded', refresh);
    document.addEventListener('adminPageLoaded', refresh);
    window.addEventListener('pageshow', refresh);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',prepare,{once:true}); else prepare();
})();
