(function () {
    if (window.ProjectDropdowns) return;

    const states = new Set();
    let activeState = null;
    let sequence = 0;

    function normalize(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
    }

    function inferIcon(optionOrText, value = '') {
        const dataIcon = optionOrText?.dataset?.icon;
        if (dataIcon) return dataIcon;

        const text = normalize(optionOrText?.textContent || optionOrText || '');
        const key = `${text} ${normalize(value || optionOrText?.value)}`;
        const rules = [
            [/\b(vip|coroa)\b/, 'fas fa-crown'],
            [/\b(premium|destaque|featured)\b/, 'fas fa-star'],
            [/\b(ativo|ativa|active|habilitado)\b/, 'fas fa-check-circle'],
            [/\b(inativo|inativa|inactive|desabilitado)\b/, 'fas fa-pause-circle'],
            [/\b(excluir|delete|remover)\b/, 'fas fa-trash-alt'],
            [/\b(importar|import)\b/, 'fas fa-file-import'],
            [/\b(exportar|export)\b/, 'fas fa-file-export'],
            [/\b(download|baixar|bios)\b/, 'fas fa-download'],
            [/\b(upload|enviar arquivo|envio de arquivo)\b/, 'fas fa-upload'],
            [/\b(suporte|atendimento)\b/, 'fas fa-headset'],
            [/\b(chamado|ticket)\b/, 'fas fa-ticket-alt'],
            [/\b(problema|erro|bug|falha)\b/, 'fas fa-bug'],
            [/\b(sugestao|ideia|solicitacao|recurso)\b/, 'fas fa-lightbulb'],
            [/\b(parceria|parcerias|parceiro|parceiros)\b/, 'fas fa-handshake'],
            [/\b(enviar|boas-vindas|mensagem)\b/, 'fas fa-paper-plane'],
            [/\b(outro|outros)\b/, 'fas fa-ellipsis-h'],
            [/\b(data|date|periodo|hoje)\b/, 'fas fa-calendar-alt'],
            [/\b(dia|dias|mes|meses|ano|anos)\b/, 'fas fa-calendar-alt'],
            [/\b(hora|time|fuso|timezone|frequencia)\b/, 'fas fa-clock'],
            [/\b(titulo|title|nome)\b/, 'fas fa-heading'],
            [/\b(view|visualiz|ver)\b/, 'fas fa-eye'],
            [/\b(admin|administrador)\b/, 'fas fa-user-shield'],
            [/\b(editor)\b/, 'fas fa-user-edit'],
            [/\b(usuario|user|gratis|free)\b/, 'fas fa-user'],
            [/\b(status|situacao)\b/, 'fas fa-toggle-on'],
            [/\b(categoria|category|grupo)\b/, 'fas fa-folder'],
            [/\b(comentario)\b/, 'fas fa-comment'],
            [/\b(newsletter|email)\b/, 'fas fa-envelope'],
            [/\b(idioma|language)\b/, 'fas fa-globe'],
            [/\b(arquivo|documento|pdf|zip|rar)\b/, 'fas fa-file-alt'],
            [/\b(mb|gb|kb|armazenamento|retencao)\b/, 'fas fa-hdd'],
            [/\b(diario|daily)\b/, 'fas fa-calendar-day'],
            [/\b(semanal|weekly)\b/, 'fas fa-calendar-week'],
            [/\b(mensal|monthly)\b/, 'fas fa-calendar'],
            [/\b(todos|todas|all)\b/, 'fas fa-layer-group'],
            [/\b(ordem|ordenar|sort)\b/, 'fas fa-sort-amount-down']
        ];
        return rules.find(([pattern]) => pattern.test(key))?.[1] || 'fas fa-list-ul';
    }

    function createIcon(className) {
        const icon = document.createElement('i');
        icon.className = className;
        icon.setAttribute('aria-hidden', 'true');
        return icon;
    }

    function closeState(state) {
        if (!state) return;
        state.root.classList.remove('is-open');
        state.menu.classList.remove('is-open');
        state.trigger.setAttribute('aria-expanded', 'false');
        if (activeState === state) activeState = null;
    }

    function closeAll(except = null) {
        states.forEach((state) => {
            if (state !== except) closeState(state);
        });
        document.querySelectorAll('.admin-smart-select.is-open, .quick-edit-control.is-open, [data-icon-select].open').forEach((root) => {
            root.classList.remove('is-open', 'open');
            root.querySelector('[aria-expanded="true"]')?.setAttribute('aria-expanded', 'false');
        });
    }

    function positionMenu(state) {
        const rect = state.trigger.getBoundingClientRect();
        const viewportPadding = 10;
        const width = Math.max(rect.width, 180);
        const availableBelow = window.innerHeight - rect.bottom - viewportPadding;
        const availableAbove = rect.top - viewportPadding;
        const expectedHeight = Math.min(state.menu.scrollHeight || 280, 310, window.innerHeight * 0.55);
        const openAbove = availableBelow < Math.min(expectedHeight, 180) && availableAbove > availableBelow;

        state.menu.style.width = `${Math.min(width, window.innerWidth - viewportPadding * 2)}px`;
        state.menu.style.maxWidth = `${Math.max(window.innerWidth - viewportPadding * 2, 180)}px`;
        state.menu.style.left = `${Math.min(Math.max(rect.left, viewportPadding), Math.max(viewportPadding, window.innerWidth - width - viewportPadding))}px`;
        state.menu.style.top = openAbove
            ? `${Math.max(viewportPadding, rect.top - expectedHeight - 7)}px`
            : `${Math.min(window.innerHeight - viewportPadding, rect.bottom + 7)}px`;
        state.menu.dataset.placement = openAbove ? 'top' : 'bottom';
    }

    function getOptionNodes(select) {
        const entries = [];
        Array.from(select.children).forEach((child) => {
            if (child.tagName === 'OPTGROUP') {
                entries.push({ type: 'group', label: child.label });
                Array.from(child.children).forEach((option) => entries.push({ type: 'option', option }));
            } else if (child.tagName === 'OPTION') {
                entries.push({ type: 'option', option: child });
            }
        });
        return entries;
    }

    function syncState(state) {
        const selected = state.select.options[state.select.selectedIndex] || state.select.options[0];
        const label = selected?.textContent?.trim() || 'Selecione uma opção';
        const iconClass = inferIcon(selected, selected?.value || '');
        const tone = selected?.dataset?.tone || '';
        const currentIcon = createIcon(iconClass);

        if (selected?.dataset?.color) currentIcon.style.color = selected.dataset.color;

        state.current.replaceChildren(currentIcon, Object.assign(document.createElement('span'), { textContent: label }));
        state.trigger.disabled = state.select.disabled;
        state.trigger.setAttribute('aria-disabled', state.select.disabled ? 'true' : 'false');
        if (tone) {
            state.root.dataset.tone = tone;
            state.trigger.dataset.tone = tone;
        } else {
            delete state.root.dataset.tone;
            delete state.trigger.dataset.tone;
        }
        state.menu.querySelectorAll('.project-select-option').forEach((button) => {
            const isSelected = button.dataset.value === String(state.select.value || '');
            button.classList.toggle('is-selected', isSelected);
            button.setAttribute('aria-selected', isSelected ? 'true' : 'false');
        });
    }

    function mirrorNativeProperty(state, propertyName) {
        const descriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, propertyName);
        if (!descriptor?.get || !descriptor?.set || Object.prototype.hasOwnProperty.call(state.select, propertyName)) {
            return;
        }

        try {
            Object.defineProperty(state.select, propertyName, {
                configurable: true,
                enumerable: descriptor.enumerable,
                get() {
                    return descriptor.get.call(this);
                },
                set(value) {
                    descriptor.set.call(this, value);
                    if (document.contains(state.select)) syncState(state);
                }
            });
        } catch (error) {
            console.warn(`[DROPDOWNS] Não foi possível observar ${propertyName}:`, error);
        }
    }

    function chooseOption(state, option) {
        if (option.disabled) return;
        state.select.value = option.value;
        state.select.dispatchEvent(new Event('change', { bubbles: true }));
        state.trigger.classList.remove('is-invalid');
        syncState(state);
        closeState(state);
        state.trigger.focus();
    }

    function rebuildMenu(state) {
        state.menu.replaceChildren();
        getOptionNodes(state.select).forEach((entry) => {
            if (entry.type === 'group') {
                const group = document.createElement('div');
                group.className = 'project-select-group';
                group.textContent = entry.label;
                state.menu.appendChild(group);
                return;
            }

            const option = entry.option;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'project-select-option';
            button.dataset.value = String(option.value || '');
            if (option.dataset.tone) button.dataset.tone = option.dataset.tone;
            button.setAttribute('role', 'option');
            button.disabled = option.disabled;

            const main = document.createElement('span');
            main.className = 'project-select-option-main';
            const icon = createIcon(inferIcon(option, option.value));
            if (option.dataset.color) icon.style.color = option.dataset.color;
            const label = document.createElement('span');
            label.textContent = option.textContent.trim();
            main.append(icon, label);

            const check = createIcon('fas fa-check project-select-check');
            button.append(main, check);
            button.addEventListener('click', () => chooseOption(state, option));
            state.menu.appendChild(button);
        });
        syncState(state);
    }

    function openState(state) {
        if (state.select.disabled) return;
        closeAll(state);
        state.root.classList.add('is-open');
        state.menu.classList.add('is-open');
        state.trigger.setAttribute('aria-expanded', 'true');
        activeState = state;
        positionMenu(state);
        state.menu.querySelector('.project-select-option.is-selected')?.scrollIntoView({ block: 'nearest' });
    }

    function handleTriggerKeydown(state, event) {
        if (event.key === 'Escape') {
            closeState(state);
            return;
        }
        if (!['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(event.key)) return;
        event.preventDefault();
        if (!state.root.classList.contains('is-open')) openState(state);
        const options = Array.from(state.menu.querySelectorAll('.project-select-option:not(:disabled)'));
        const currentIndex = options.findIndex((button) => button.classList.contains('is-highlighted'));
        const selectedIndex = options.findIndex((button) => button.classList.contains('is-selected'));
        let nextIndex = currentIndex >= 0 ? currentIndex : Math.max(selectedIndex, 0);
        if (event.key === 'ArrowDown') nextIndex = Math.min(nextIndex + (currentIndex >= 0 ? 1 : 0), options.length - 1);
        if (event.key === 'ArrowUp') nextIndex = Math.max(nextIndex - 1, 0);
        options.forEach((button, index) => button.classList.toggle('is-highlighted', index === nextIndex));
        options[nextIndex]?.scrollIntoView({ block: 'nearest' });
        if ((event.key === 'Enter' || event.key === ' ') && currentIndex >= 0) options[currentIndex]?.click();
    }

    function shouldSkip(select) {
        return !select
            || select.dataset.projectSelectInitialized === 'true'
            || select.dataset.projectSelect === 'native'
            || select.multiple
            || Number(select.size || 0) > 1
            || select.hidden
            || select.classList.contains('smart-select-native')
            || select.classList.contains('icon-select-native')
            || select.closest('[data-project-select]');
    }

    function copyLayout(select, root) {
        const parentDisplay = select.parentElement ? getComputedStyle(select.parentElement).display : '';
        if (!parentDisplay.includes('flex') && !parentDisplay.includes('grid')) return;
        const computed = getComputedStyle(select);
        root.style.flex = computed.flex;
        root.style.width = computed.width;
        root.style.minWidth = computed.minWidth;
        root.style.maxWidth = computed.maxWidth;
        root.style.margin = computed.margin;
    }

    function enhanceSelect(select) {
        if (shouldSkip(select)) return null;

        const root = document.createElement('div');
        root.className = 'project-select';
        root.dataset.projectSelect = 'true';
        copyLayout(select, root);

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'project-select-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        const current = document.createElement('span');
        current.className = 'project-select-current';
        const chevron = createIcon('fas fa-chevron-down project-select-chevron');
        trigger.append(current, chevron);

        const explicitLabel = select.getAttribute('aria-label');
        const relatedLabel = select.id
            ? document.querySelector(`label[for="${CSS.escape(select.id)}"]`)?.textContent?.trim()
            : '';
        trigger.setAttribute('aria-label', explicitLabel || relatedLabel || 'Selecionar opção');

        const menu = document.createElement('div');
        menu.className = 'project-select-menu';
        menu.id = `project-select-menu-${++sequence}`;
        menu.setAttribute('role', 'listbox');
        trigger.setAttribute('aria-controls', menu.id);

        select.parentNode.insertBefore(root, select);
        root.append(select, trigger);
        document.body.appendChild(menu);
        select.classList.add('project-select-native');
        select.dataset.projectSelectInitialized = 'true';
        select.tabIndex = -1;

        const state = { select, root, trigger, current, menu, observer: null };
        states.add(state);
        mirrorNativeProperty(state, 'value');
        mirrorNativeProperty(state, 'selectedIndex');
        rebuildMenu(state);

        trigger.addEventListener('click', () => {
            if (root.classList.contains('is-open')) closeState(state);
            else openState(state);
        });
        trigger.addEventListener('keydown', (event) => handleTriggerKeydown(state, event));
        select.addEventListener('change', () => {
            trigger.classList.remove('is-invalid');
            syncState(state);
        });
        select.addEventListener('invalid', () => {
            trigger.focus();
            trigger.classList.add('is-invalid');
        });
        select.form?.addEventListener('reset', () => setTimeout(() => syncState(state), 0));

        state.observer = new MutationObserver(() => rebuildMenu(state));
        state.observer.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['selected', 'disabled', 'data-icon', 'data-color', 'data-tone'] });
        return state;
    }

    function decorateExistingMenus(root = document) {
        root.querySelectorAll?.('.dropdown-menu a, .dropdown-menu button, .role-dropdown-menu .dropdown-item').forEach((item) => {
            if (item.dataset.projectMenuDecorated === 'true') return;
            item.dataset.projectMenuDecorated = 'true';
            if (!item.querySelector('i')) {
                const icon = createIcon(`${inferIcon(item, item.getAttribute('href') || '')} project-menu-fallback-icon`);
                item.prepend(icon);
            }
        });
    }

    function enhanceAll(root = document) {
        if (root.matches?.('select')) enhanceSelect(root);
        root.querySelectorAll?.('select').forEach(enhanceSelect);
        decorateExistingMenus(root);
    }

    function cleanupDetachedStates() {
        states.forEach((state) => {
            if (document.contains(state.select)) return;
            closeState(state);
            state.observer?.disconnect();
            state.menu.remove();
            states.delete(state);
        });
    }

    document.addEventListener('click', (event) => {
        if (activeState && !activeState.root.contains(event.target) && !activeState.menu.contains(event.target)) {
            closeState(activeState);
        }
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && activeState) closeState(activeState);
    });
    window.addEventListener('resize', () => activeState && positionMenu(activeState), { passive: true });
    document.addEventListener('scroll', (event) => {
        if (!activeState) return;
        // Rolar a própria lista não pode fechá-la. Apenas uma rolagem do
        // documento ou de outro contêiner encerra o dropdown.
        if (event.target === activeState.menu || activeState.menu.contains(event.target)) return;
        closeState(activeState);
    }, true);

    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) enhanceAll(node);
        }));
        cleanupDetachedStates();
    });

    function init() {
        enhanceAll(document);
        if (document.body && document.body.dataset.projectDropdownObserver !== 'true') {
            document.body.dataset.projectDropdownObserver = 'true';
            observer.observe(document.body, { childList: true, subtree: true });
        }
    }

    window.ProjectDropdowns = { init, refresh: init, enhanceSelect, closeAll };
    window.refreshProjectDropdowns = init;

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
    else init();
    document.addEventListener('pageLoaded', init);
    document.addEventListener('adminPageLoaded', init);
})();
