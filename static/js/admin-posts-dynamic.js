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
        const badge = document.querySelector('.admin-nav-item[href="/admin/posts"] .nav-badge')
            || document.querySelector('.admin-nav-item[href="/admin/posts/"] .nav-badge');

        if (badge) {
            badge.textContent = total > 0 ? String(total) : '';
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
        const featuredPosts = Math.max(0, Number(stats.featured_posts) || 0);

        setTotalPosts(totalPosts);

        document.querySelectorAll('[data-posts-total-stat], [data-posts-total-badge]').forEach((element) => {
            element.textContent = String(totalPosts);
        });

        document.querySelectorAll('[data-posts-featured-stat]').forEach((element) => {
            element.textContent = String(featuredPosts);
        });

        updateSidebarPostsBadge(totalPosts);
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

    function buildPostRow(post) {
        const postExcerpt = String(post.excerpt || post.description || '').trim();
        const featuredHtml = post.featured
            ? '<span class="featured-indicator" title="Post em destaque"><i class="fas fa-star"></i></span>'
            : '';

        const statusHtml = post.featured
            ? '<span class="badge badge-warning"><i class="fas fa-star"></i> Destaque</span>'
            : (post.is_active
                ? '<span class="badge badge-success"><i class="fas fa-check-circle"></i> Ativo</span>'
                : '<span class="badge badge-secondary"><i class="fas fa-pause-circle"></i> Inativo</span>');

        return `
            <tr data-post-id="${post.id}" data-category-id="${escapeHtml(post.category_id || '')}" class="${post.is_active ? '' : 'inactive-row'}">
                <td><input type="checkbox" class="form-check-input post-checkbox" value="${post.id}"></td>
                <td class="actions">
                    <div class="action-buttons">
                        <a href="${escapeHtml(post.post_url || '#')}" class="btn-action btn-view" title="Visualizar" target="_blank"><i class="fas fa-eye"></i></a>
                        <a href="#" class="btn-action btn-edit" title="Editar" data-post-id="${post.id}"><i class="fas fa-edit"></i></a>
                        <a href="#" class="btn-action btn-duplicate" title="Duplicar" data-post-id="${post.id}"><i class="fas fa-copy"></i></a>
                        <a href="#" class="btn-action btn-delete" title="Excluir" data-post-id="${post.id}" data-post-title="${escapeHtml(post.title)}"><i class="fas fa-trash"></i></a>
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
                <td>
                    <div class="category-cell">
                        <span class="category-badge" style="background: ${escapeHtml(post.category_color || '#3a86ff')}">
                            <i class="${escapeHtml(post.category_icon || 'fas fa-folder')}"></i>
                            ${escapeHtml(post.category_name || 'Sem categoria')}
                        </span>
                    </div>
                </td>
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
                <td><div class="status-cell">${statusHtml}</div></td>
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

    function bindGlobalHandlers() {
        if (window.__adminPostsDynamicGlobalBound) {
            return;
        }

        window.__adminPostsDynamicGlobalBound = true;

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
        refreshPaginationInfo();
        updateSidebarPostsBadge(getTotalPosts());
    }

    window.AdminPostsDynamic = {
        init,
        updatePostsOverview,
        refreshPaginationInfo
    };

    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('adminPageLoaded', init);
})();
