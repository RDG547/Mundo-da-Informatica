(function () {
    if (window.AdminPostsDynamic && typeof window.AdminPostsDynamic.init === 'function') {
        window.AdminPostsDynamic.init();
        return;
    }

    function getCsrfToken() {
        return (window.csrfUtils && window.csrfUtils.getCsrfToken && window.csrfUtils.getCsrfToken())
            || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            || '';
    }

    function escapeHtml(value) {
        return (value || '')
            .toString()
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function showToast(message, type) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type || 'info');
        } else {
            window.alert(message);
        }
    }

    function getTableBody() {
        return document.getElementById('postsTableBody');
    }

    function getRows() {
        return Array.from(document.querySelectorAll('#postsTableBody tr[data-post-id]'));
    }

    function getPaginationContainer() {
        return document.getElementById('postsPaginationContainer');
    }

    function getCurrentPage() {
        const container = getPaginationContainer();
        const fromData = parseInt(container?.dataset?.currentPage || '1', 10);
        const fromUrl = parseInt(new URLSearchParams(window.location.search).get('page') || '', 10);
        return Number.isFinite(fromUrl) && fromUrl > 0
            ? fromUrl
            : (Number.isFinite(fromData) && fromData > 0 ? fromData : 1);
    }

    function getPerPage() {
        const container = getPaginationContainer();
        const fromData = parseInt(container?.dataset?.perPage || '10', 10);
        return Number.isFinite(fromData) && fromData > 0 ? fromData : 10;
    }

    function getTotalPosts() {
        const container = getPaginationContainer();
        const total = parseInt(container?.dataset?.total || '0', 10);
        return Number.isFinite(total) && total >= 0 ? total : 0;
    }

    function setTotalPosts(total) {
        const container = getPaginationContainer();
        if (container) {
            container.dataset.total = String(Math.max(0, Number(total) || 0));
        }
    }

    function hasActiveFilters() {
        const search = document.getElementById('searchPosts')?.value?.trim();
        const category = document.getElementById('filterCategory')?.value?.trim();
        const status = document.getElementById('filterStatus')?.value?.trim();
        return Boolean(search || category || status);
    }

    async function parseJsonResponse(response) {
        const rawText = await response.text();
        let data = {};

        try {
            data = rawText ? JSON.parse(rawText) : {};
        } catch (_error) {
            const normalized = rawText.trim().slice(0, 120);
            if (normalized.startsWith('<')) {
                throw new Error('O servidor retornou uma pagina invalida em vez de JSON. Verifique o log da aplicacao.');
            }
            throw new Error('A resposta do servidor nao esta em um formato valido.');
        }

        if (!response.ok || !data.success) {
            throw new Error(data.message || 'Erro na operacao.');
        }

        return data;
    }

    function updateSidebarPostsBadge(total) {
        const badge = document.querySelector('[data-sidebar-count="posts"]')
            || document.querySelector('.admin-nav-item[href="/admin/posts"] .nav-badge')
            || document.querySelector('.admin-nav-item[href="/admin/posts/"] .nav-badge');

        if (badge) {
            badge.textContent = String(Math.max(0, Number(total) || 0));
        }
    }

    function refreshPaginationInfo() {
        const info = document.getElementById('postsPaginationInfo');
        if (!info) return;

        const rows = getRows();
        const visibleRows = rows.filter((row) => row.style.display !== 'none');
        const totalPosts = getTotalPosts();

        if (!rows.length) {
            info.textContent = totalPosts > 0
                ? `Mostrando 0 de ${totalPosts} posts`
                : 'Nenhum post encontrado';
            return;
        }

        if (hasActiveFilters()) {
            info.textContent = `Mostrando ${visibleRows.length} de ${rows.length} posts nesta pagina`;
            return;
        }

        info.textContent = `Mostrando ${rows.length} de ${totalPosts} posts`;
    }

    function updatePostsOverview(stats) {
        if (!stats || typeof stats !== 'object') {
            refreshPaginationInfo();
            return;
        }

        const totalPosts = Math.max(0, Number(stats.total_posts) || 0);
        const activePosts = Math.max(0, Number(stats.active_posts) || 0);
        const featuredPosts = Math.max(0, Number(stats.featured_posts) || 0);

        setTotalPosts(totalPosts);

        document.querySelectorAll('[data-posts-total-stat], [data-posts-total-badge]').forEach((element) => {
            element.textContent = String(totalPosts);
        });

        document.querySelectorAll('[data-posts-featured-stat]').forEach((element) => {
            element.textContent = String(featuredPosts);
        });

        updateSidebarPostsBadge(activePosts);
        refreshPaginationInfo();
    }

    function removeEmptyStateRow() {
        document.querySelector('#postsTableBody .empty-state')?.remove();
    }

    function ensureEmptyState() {
        const tbody = getTableBody();
        if (!tbody || getRows().length) return;

        tbody.innerHTML = `
            <tr class="empty-state">
                <td colspan="8" style="text-align: center; padding: 3rem;">
                    <div class="empty-state-content">
                        <i class="fas fa-file-alt fa-3x text-muted mb-3"></i>
                        <h4 class="text-muted">Nenhum post encontrado</h4>
                        <p class="text-muted">Crie um novo post para ele aparecer aqui.</p>
                    </div>
                </td>
            </tr>
        `;

        refreshPaginationInfo();
    }

    function trimRowsForCurrentPage() {
        if (getCurrentPage() !== 1) return;

        const perPage = getPerPage();
        const rows = getRows();
        rows.slice(perPage).forEach((row) => row.remove());
    }

    function reapplyCurrentFilters() {
        if (typeof window.refreshPostsListFilters === 'function') {
            window.refreshPostsListFilters();
            return;
        }

        const searchInput = document.getElementById('searchPosts');
        const categoryFilter = document.getElementById('filterCategory');
        const statusFilter = document.getElementById('filterStatus');

        if (searchInput) {
            searchInput.dispatchEvent(new Event('input', { bubbles: true }));
            return;
        }

        if (categoryFilter) {
            categoryFilter.dispatchEvent(new Event('change', { bubbles: true }));
            return;
        }

        if (statusFilter) {
            statusFilter.dispatchEvent(new Event('change', { bubbles: true }));
            return;
        }

        refreshPaginationInfo();
    }

    function getQuickCategoryOptions() {
        const categorySelect = document.getElementById('filterCategory');
        const root = categorySelect?.closest('[data-smart-select]');
        const options = root
            ? Array.from(root.querySelectorAll('.smart-select-option[data-value]'))
                .filter((option) => option.dataset.value)
                .map((option) => ({
                    value: option.dataset.value,
                    label: option.querySelector('span')?.textContent?.trim() || 'Categoria',
                    icon: option.dataset.icon || 'fas fa-folder',
                    color: option.dataset.color || '#3a86ff'
                }))
            : [];

        return [{ value: '', label: 'Sem categoria', icon: 'fas fa-folder', color: '#64748b' }, ...options];
    }

    function buildCategoryQuickControl(post) {
        const selectedId = String(post.category_id || '');
        const optionsHtml = getQuickCategoryOptions().map((option) => `
            <button type="button" class="quick-edit-option${option.value === selectedId ? ' is-selected' : ''}"
                data-quick-field="category_id" data-value="${escapeHtml(option.value)}"
                data-icon="${escapeHtml(option.icon)}" data-color="${escapeHtml(option.color)}">
                <span><i class="${escapeHtml(option.icon)}"></i> ${escapeHtml(option.label)}</span>
                <i class="fas fa-check option-check"></i>
            </button>
        `).join('');

        return `
            <div class="category-cell quick-edit-control" data-quick-edit-control="category">
                <button type="button" class="category-badge quick-edit-trigger" data-quick-edit-trigger
                    aria-haspopup="listbox" aria-expanded="false" style="background: ${escapeHtml(post.category_color || '#3a86ff')}">
                    <i class="${escapeHtml(post.category_icon || 'fas fa-folder')}"></i>
                    <span>${escapeHtml(post.category_name || 'Sem categoria')}</span>
                    <i class="fas fa-chevron-down quick-edit-chevron"></i>
                </button>
                <div class="quick-edit-menu" role="listbox">${optionsHtml}</div>
            </div>
        `;
    }

    function getPostStatus(post) {
        if (post.featured) return 'featured';
        return post.is_active ? 'active' : 'inactive';
    }

    function buildStatusQuickControl(post) {
        const currentStatus = getPostStatus(post);
        const statuses = [
            { value: 'active', label: 'Ativo', icon: 'fas fa-check-circle', badge: 'badge-success' },
            { value: 'featured', label: 'Destaque', icon: 'fas fa-star', badge: 'badge-warning' },
            { value: 'inactive', label: 'Inativo', icon: 'fas fa-pause-circle', badge: 'badge-secondary' }
        ];
        const current = statuses.find((status) => status.value === currentStatus) || statuses[0];
        const optionsHtml = statuses.map((status) => `
            <button type="button" class="quick-edit-option${status.value === currentStatus ? ' is-selected' : ''}"
                data-quick-field="status" data-value="${status.value}" data-icon="${status.icon}">
                <span><i class="${status.icon}"></i> ${status.label}</span><i class="fas fa-check option-check"></i>
            </button>
        `).join('');

        return `
            <div class="status-cell quick-edit-control" data-quick-edit-control="status">
                <button type="button" class="status-quick-trigger quick-edit-trigger" data-quick-edit-trigger aria-haspopup="listbox" aria-expanded="false">
                    <span class="badge ${current.badge}"><i class="${current.icon}"></i> ${current.label}</span>
                    <i class="fas fa-chevron-down quick-edit-chevron"></i>
                </button>
                <div class="quick-edit-menu quick-edit-menu-right" role="listbox">${optionsHtml}</div>
            </div>
        `;
    }

    function updatePostRowQuickControls(row, post) {
        if (!row || !post) return;
        row.dataset.categoryId = post.category_id || '';
        row.dataset.status = getPostStatus(post);
        row.classList.toggle('inactive-row', !post.is_active);

        const categoryControl = row.querySelector('[data-quick-edit-control="category"]');
        if (categoryControl) categoryControl.outerHTML = buildCategoryQuickControl(post);

        const statusControl = row.querySelector('[data-quick-edit-control="status"]');
        if (statusControl) statusControl.outerHTML = buildStatusQuickControl(post);
    }

    function buildPostRow(post) {
        const rawExcerpt = String(post.excerpt || post.description || '').trim();
        const postExcerpt = rawExcerpt.length > 68 ? `${rawExcerpt.slice(0, 68)}...` : rawExcerpt;
        const featuredHtml = post.featured
            ? '<span class="featured-indicator" title="Post em destaque"><i class="fas fa-star"></i></span>'
            : '';

        return `
            <tr data-post-id="${post.id}" data-category-id="${escapeHtml(post.category_id || '')}" data-status="${getPostStatus(post)}" class="${post.is_active ? '' : 'inactive-row'}">
                <td><input type="checkbox" class="form-check-input post-checkbox" value="${post.id}"></td>
                <td class="actions">
                    <div class="action-buttons">
                        <a href="${escapeHtml(post.post_url || '#')}" class="btn-action btn-view" title="Visualizar" target="_blank"><i class="fas fa-eye"></i><span>Visualizar</span></a>
                        <a href="#" class="btn-action btn-edit" title="Editar" data-post-id="${post.id}"><i class="fas fa-edit"></i><span>Editar</span></a>
                        <a href="#" class="btn-action btn-duplicate" title="Duplicar" data-post-id="${post.id}"><i class="fas fa-copy"></i><span>Duplicar</span></a>
                        <a href="#" class="btn-action btn-delete" title="Excluir" data-post-id="${post.id}" data-post-title="${escapeHtml(post.title)}"><i class="fas fa-trash"></i><span>Excluir</span></a>
                    </div>
                </td>
                <td>
                    <div class="post-title-cell">
                        <div class="post-thumb">
                            <img src="${escapeHtml(post.image_url)}" alt="" class="post-thumb-img">
                        </div>
                        <div class="post-title-info">
                            <div class="post-title">${escapeHtml(post.title)}</div>
                            ${postExcerpt ? `<small class="post-excerpt text-muted">${escapeHtml(postExcerpt)}</small>` : ''}
                            ${featuredHtml}
                        </div>
                    </div>
                </td>
                <td>${buildCategoryQuickControl(post)}</td>
                <td>
                    <div class="date-cell">
                        <div class="date-primary">${escapeHtml(post.date_posted || '')}</div>
                        <small class="date-time text-muted">${escapeHtml(post.time_posted || '')}</small>
                    </div>
                </td>
                <td>
                    <div class="metric-cell">
                        <span class="metric-number">${post.views || 0}</span>
                        <div class="metric-trend"><i class="fas fa-arrow-up text-success"></i><span class="trend-percentage">+0%</span></div>
                    </div>
                </td>
                <td>
                    <div class="metric-cell">
                        <span class="metric-number">${post.downloads || 0}</span>
                        <div class="metric-trend"><i class="fas fa-arrow-up text-success"></i><span class="trend-percentage">+0%</span></div>
                    </div>
                </td>
                <td>${buildStatusQuickControl(post)}</td>
            </tr>
        `;
    }

    async function ajaxPost(url, body) {
        const headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCsrfToken()
        };

        const options = {
            method: 'POST',
            headers,
            credentials: 'same-origin'
        };

        if (body instanceof FormData) {
            options.body = body;
        } else if (body) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);
        return parseJsonResponse(response);
    }

    function prependPostRow(post) {
        if (!post || getCurrentPage() !== 1) {
            return false;
        }

        const tbody = getTableBody();
        if (!tbody) {
            return false;
        }

        removeEmptyStateRow();
        tbody.insertAdjacentHTML('afterbegin', buildPostRow(post));
        trimRowsForCurrentPage();
        reapplyCurrentFilters();
        return true;
    }

    function goToPreviousPageIfNeeded() {
        if (getRows().length || getCurrentPage() <= 1 || getTotalPosts() <= 0) {
            ensureEmptyState();
            refreshPaginationInfo();
            return;
        }

        const previousPageUrl = `/admin/posts?page=${Math.max(1, getCurrentPage() - 1)}`;
        if (window.dynamicLoader && typeof window.dynamicLoader.loadPage === 'function') {
            window.dynamicLoader.loadPage(previousPageUrl);
        } else {
            window.location.href = previousPageUrl;
        }
    }

    function closeAdminDropdowns(exceptRoot) {
        document.querySelectorAll('.admin-smart-select.is-open, .quick-edit-control.is-open').forEach((root) => {
            if (root === exceptRoot) return;
            root.classList.remove('is-open');
            root.querySelector('[aria-expanded="true"]')?.setAttribute('aria-expanded', 'false');
        });
    }

    function syncSmartSelect(root) {
        if (!root) return;
        const select = root.querySelector('select');
        const current = root.querySelector('.smart-select-current');
        const options = Array.from(root.querySelectorAll('.smart-select-option'));
        const selectedOption = options.find((option) => option.dataset.value === select?.value) || options[0];
        if (!select || !current || !selectedOption) return;

        options.forEach((option) => option.classList.toggle('is-selected', option === selectedOption));
        const label = selectedOption.querySelector('span')?.textContent?.trim() || select.selectedOptions[0]?.textContent || '';
        const icon = selectedOption.dataset.icon || 'fas fa-filter';
        const tone = selectedOption.dataset.tone || select.selectedOptions[0]?.dataset?.tone || '';
        if (tone) root.dataset.tone = tone;
        else delete root.dataset.tone;
        current.innerHTML = `<i class="${escapeHtml(icon)}"></i><span>${escapeHtml(label)}</span>`;
    }

    function syncAllSmartSelects() {
        document.querySelectorAll('[data-smart-select]').forEach(syncSmartSelect);
    }

    function bindGlobalHandlers() {
        if (window.__adminPostsDynamicGlobalBound) {
            return;
        }

        window.__adminPostsDynamicGlobalBound = true;

        document.addEventListener('click', async function (event) {
            const smartTrigger = event.target.closest('[data-smart-select-trigger]');
            if (smartTrigger) {
                const root = smartTrigger.closest('[data-smart-select]');
                const willOpen = !root.classList.contains('is-open');
                closeAdminDropdowns(root);
                root.classList.toggle('is-open', willOpen);
                smartTrigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
                return;
            }

            const smartOption = event.target.closest('.smart-select-option');
            if (smartOption) {
                const root = smartOption.closest('[data-smart-select]');
                const select = root?.querySelector('select');
                if (root && select) {
                    select.value = smartOption.dataset.value || '';
                    syncSmartSelect(root);
                    root.classList.remove('is-open');
                    root.querySelector('[data-smart-select-trigger]')?.setAttribute('aria-expanded', 'false');
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return;
            }

            const quickTrigger = event.target.closest('[data-quick-edit-trigger]');
            if (quickTrigger) {
                const root = quickTrigger.closest('.quick-edit-control');
                const willOpen = !root.classList.contains('is-open');
                closeAdminDropdowns(root);
                root.classList.toggle('is-open', willOpen);
                quickTrigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
                return;
            }

            const quickOption = event.target.closest('.quick-edit-option');
            if (quickOption) {
                const row = quickOption.closest('tr[data-post-id]');
                const control = quickOption.closest('.quick-edit-control');
                if (!row || !control || quickOption.classList.contains('is-selected')) {
                    closeAdminDropdowns();
                    return;
                }

                const field = quickOption.dataset.quickField;
                const postId = row.dataset.postId;
                if (!field || !postId) return;

                control.classList.add('is-saving');
                try {
                    const result = await ajaxPost(`/admin/posts/${postId}/quick-update`, {
                        [field]: quickOption.dataset.value || ''
                    });
                    updatePostRowQuickControls(row, result.post);
                    updatePostsOverview(result.stats);
                    reapplyCurrentFilters();
                    showToast(result.message || 'Post atualizado com sucesso!', 'success');
                } catch (error) {
                    control.classList.remove('is-saving');
                    showToast(error.message, 'error');
                } finally {
                    closeAdminDropdowns();
                }
                return;
            }

            closeAdminDropdowns();
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') closeAdminDropdowns();
        });

        document.addEventListener('click', function (event) {
            const deleteBtn = event.target.closest('.btn-delete');
            if (!deleteBtn || !document.getElementById('postsTableBody')) return;

            event.preventDefault();
            event.stopImmediatePropagation();

            const postId = deleteBtn.getAttribute('data-post-id');
            const postTitle = deleteBtn.getAttribute('data-post-title') || 'este post';
            const modal = document.getElementById('deleteModal');
            const form = document.getElementById('deletePostForm');
            if (!modal || !form || !postId) return;

            const modalBodyP = modal.querySelector('.modal-body p');
            if (modalBodyP) {
                modalBodyP.innerHTML = `Tem certeza que deseja excluir o post <strong>"${escapeHtml(postTitle)}"</strong>? Esta acao nao pode ser desfeita.`;
            }

            form.action = `/admin/posts/${postId}/delete`;
            if (typeof window.openModal === 'function') {
                window.openModal('deleteModal');
            }
        }, true);

        document.addEventListener('click', async function (event) {
            const duplicateBtn = event.target.closest('.btn-duplicate');
            if (!duplicateBtn || !document.getElementById('postsTableBody')) return;

            event.preventDefault();
            event.stopImmediatePropagation();

            const postId = duplicateBtn.getAttribute('data-post-id');
            if (!postId || !window.confirm('Deseja duplicar este post?')) return;

            try {
                const result = await ajaxPost(`/admin/posts/${postId}/duplicate`);
                updatePostsOverview(result.stats);

                const inserted = prependPostRow(result.post);
                const message = inserted || getCurrentPage() === 1
                    ? (result.message || 'Post duplicado com sucesso!')
                    : `${result.message || 'Post duplicado com sucesso!'} A copia aparece na pagina 1.`;

                showToast(message, 'success');
            } catch (error) {
                showToast(error.message, 'error');
            }
        }, true);
    }

    function bindDeleteForm() {
        const deleteForm = document.getElementById('deletePostForm');
        if (!deleteForm || deleteForm.dataset.dynamicBound === 'true') return;

        deleteForm.dataset.dynamicBound = 'true';
        deleteForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();

            try {
                const result = await ajaxPost(deleteForm.action);
                document.querySelector(`tr[data-post-id="${result.post_id}"]`)?.remove();
                updatePostsOverview(result.stats);

                if (typeof window.closeModal === 'function') {
                    window.closeModal('deleteModal');
                }

                showToast(result.message || 'Post excluido com sucesso!', 'success');
                goToPreviousPageIfNeeded();
            } catch (error) {
                showToast(error.message, 'error');
            }
        }, true);
    }

    function bindEditForm() {
        const editForm = document.getElementById('editPostForm');
        if (!editForm || editForm.dataset.dynamicBound === 'true') return;

        editForm.dataset.dynamicBound = 'true';
        editForm.addEventListener('submit', function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (typeof window.savePost === 'function') {
                window.savePost(event);
            }
        }, true);
    }

    function bindCreateForm() {
        const addPostForm = document.getElementById('addPostForm');
        if (!addPostForm || addPostForm.dataset.dynamicBound === 'true') return;

        addPostForm.dataset.dynamicBound = 'true';
        addPostForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            if (addPostForm.dataset.submitting === 'true') {
                return;
            }

            addPostForm.dataset.submitting = 'true';

            const saveBtn = document.getElementById('savePostBtn');
            if (saveBtn && !saveBtn.dataset.defaultHtml) {
                saveBtn.dataset.defaultHtml = saveBtn.innerHTML;
            }

            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Publicando...';
            }

            const formData = new FormData(addPostForm);

            try {
                const result = await ajaxPost(addPostForm.action, formData);
                updatePostsOverview(result.stats);

                const inserted = prependPostRow(result.post);

                addPostForm.reset();
                const editor = document.getElementById('postContentEditor');
                if (editor) editor.innerHTML = '';
                if (typeof window.refreshIconSelects === 'function') {
                    window.refreshIconSelects();
                }
                if (typeof window.refreshDownloadTypeSelects === 'function') {
                    window.refreshDownloadTypeSelects();
                }

                if (typeof window.closeModal === 'function') {
                    window.closeModal('addPostModal');
                }

                const message = inserted || getCurrentPage() === 1
                    ? (result.message || 'Post criado com sucesso!')
                    : `${result.message || 'Post criado com sucesso!'} Ele ja esta disponivel na pagina 1.`;

                showToast(message, 'success');
            } catch (error) {
                showToast(error.message, 'error');
            } finally {
                delete addPostForm.dataset.submitting;
                addPostForm.dispatchEvent(new CustomEvent('post:create:complete'));

                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = saveBtn.dataset.defaultHtml || saveBtn.innerHTML;
                }
            }
        }, true);
    }

    function init() {
        if (!document.getElementById('postsTableBody')) return;

        bindGlobalHandlers();
        bindDeleteForm();
        bindEditForm();
        bindCreateForm();
        syncAllSmartSelects();
        refreshPaginationInfo();
    }

    window.AdminPostsDynamic = {
        init,
        updatePostsOverview,
        refreshPaginationInfo,
        syncSmartSelects: syncAllSmartSelects,
        updatePostRowQuickControls
    };

    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('adminPageLoaded', init);
})();
