(function () {
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
            alert(message);
        }
    }

    function getRows() {
        return Array.from(document.querySelectorAll('#postsTableBody tr[data-post-id]'));
    }

    function getCurrentPage() {
        const container = document.getElementById('postsPaginationContainer');
        const fromData = parseInt(container?.dataset?.currentPage || '1', 10);
        const fromUrl = parseInt(new URLSearchParams(window.location.search).get('page') || '', 10);
        return Number.isFinite(fromUrl) && fromUrl > 0 ? fromUrl : (Number.isFinite(fromData) && fromData > 0 ? fromData : 1);
    }

    function getPerPage() {
        const container = document.getElementById('postsPaginationContainer');
        const fromData = parseInt(container?.dataset?.perPage || '10', 10);
        return Number.isFinite(fromData) && fromData > 0 ? fromData : 10;
    }

    function hasActiveFilters() {
        const search = document.getElementById('searchPosts')?.value?.trim();
        const category = document.getElementById('filterCategory')?.value?.trim();
        const status = document.getElementById('filterStatus')?.value?.trim();
        return Boolean(search || category || status);
    }

    function getPageWindow(totalPages, currentPage) {
        const pages = [];
        const add = (value) => {
            if (!pages.includes(value)) pages.push(value);
        };

        add(1);
        add(totalPages);
        for (let p = currentPage - 2; p <= currentPage + 2; p += 1) {
            if (p > 1 && p < totalPages) add(p);
        }

        pages.sort((a, b) => a - b);
        const output = [];
        for (let i = 0; i < pages.length; i += 1) {
            const page = pages[i];
            const prev = pages[i - 1];
            if (i > 0 && prev + 1 < page) output.push(null);
            output.push(page);
        }
        return output;
    }

    function renderPagination(totalRows, page, perPage) {
        const container = document.getElementById('postsPaginationContainer');
        if (!container) return;

        const paginationList = container.querySelector('.pagination');
        const info = document.getElementById('postsPaginationInfo');
        const totalPages = Math.max(1, Math.ceil(totalRows / perPage));
        const safePage = Math.min(Math.max(1, page), totalPages);

        if (info) {
            const visibleRows = getRows().filter((row) => row.style.display !== 'none').length;
            info.textContent = `Mostrando ${visibleRows} de ${totalRows} posts`;
        }

        if (!paginationList) return;

        const pageItems = getPageWindow(totalPages, safePage)
            .map((value) => {
                if (value === null) {
                    return '<li class="page-item disabled"><span class="page-link">…</span></li>';
                }
                if (value === safePage) {
                    return `<li class="page-item active"><span class="page-link">${value}</span></li>`;
                }
                return `<li class="page-item"><a class="page-link" href="/admin/posts?page=${value}" data-page="${value}">${value}</a></li>`;
            })
            .join('');

        const prevDisabled = safePage <= 1;
        const nextDisabled = safePage >= totalPages;
        const prevHref = `/admin/posts?page=${Math.max(1, safePage - 1)}`;
        const nextHref = `/admin/posts?page=${Math.min(totalPages, safePage + 1)}`;

        paginationList.innerHTML = `
            <li class="page-item ${prevDisabled ? 'disabled' : ''}">
                ${prevDisabled ? '<span class="page-link"><i class="fas fa-chevron-left"></i></span>' : `<a class="page-link" href="${prevHref}" data-page="${safePage - 1}"><i class="fas fa-chevron-left"></i></a>`}
            </li>
            ${pageItems}
            <li class="page-item ${nextDisabled ? 'disabled' : ''}">
                ${nextDisabled ? '<span class="page-link"><i class="fas fa-chevron-right"></i></span>' : `<a class="page-link" href="${nextHref}" data-page="${safePage + 1}"><i class="fas fa-chevron-right"></i></a>`}
            </li>
        `;

        container.dataset.currentPage = String(safePage);
    }

    function applyClientPagination(targetPage) {
        const rows = getRows();
        const perPage = getPerPage();

        if (!rows.length) {
            renderPagination(0, 1, perPage);
            return;
        }

        if (hasActiveFilters()) {
            const total = rows.length;
            renderPagination(total, 1, total || perPage);
            return;
        }

        const totalRows = rows.length;
        const totalPages = Math.max(1, Math.ceil(totalRows / perPage));
        const page = Math.min(Math.max(1, targetPage || 1), totalPages);
        const start = (page - 1) * perPage;
        const end = start + perPage;

        rows.forEach((row, index) => {
            row.style.display = index >= start && index < end ? '' : 'none';
        });

        renderPagination(totalRows, page, perPage);

        const url = new URL(window.location.href);
        url.searchParams.set('page', String(page));
        window.history.replaceState({}, '', `${url.pathname}${url.search}`);
    }

    function buildPostRow(post) {
        const featuredHtml = post.featured
            ? '<span class="featured-indicator" title="Post em destaque"><i class="fas fa-star"></i></span>'
            : '';

        const statusHtml = post.featured
            ? '<span class="badge badge-warning"><i class="fas fa-star"></i> Destaque</span>'
            : (post.is_active
                ? '<span class="badge badge-success"><i class="fas fa-check-circle"></i> Ativo</span>'
                : '<span class="badge badge-secondary"><i class="fas fa-pause-circle"></i> Inativo</span>');

        return `
            <tr data-post-id="${post.id}" class="${post.is_active ? '' : 'inactive-row'}">
                <td><input type="checkbox" class="form-check-input post-checkbox" value="${post.id}"></td>
                <td>
                    <div class="post-title-cell">
                        <div class="post-thumb">
                            <img src="${escapeHtml(post.image_url)}" alt="" class="post-thumb-img">
                        </div>
                        <div class="post-title-info">
                            <div class="post-title">${escapeHtml(post.title)}</div>
                            ${post.description ? `<small class="post-excerpt text-muted">${escapeHtml(post.description.substring(0, 100))}${post.description.length > 100 ? '...' : ''}</small>` : ''}
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
                <td class="actions">
                    <div class="action-buttons">
                        <a href="${escapeHtml(post.post_url || '#')}" class="btn-action btn-view" title="Visualizar" target="_blank"><i class="fas fa-eye"></i></a>
                        <a href="#" class="btn-action btn-edit" title="Editar" data-post-id="${post.id}"><i class="fas fa-edit"></i></a>
                        <a href="#" class="btn-action btn-duplicate" title="Duplicar" data-post-id="${post.id}"><i class="fas fa-copy"></i></a>
                        <a href="#" class="btn-action btn-delete" title="Excluir" data-post-id="${post.id}" data-post-title="${escapeHtml(post.title)}"><i class="fas fa-trash"></i></a>
                    </div>
                </td>
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
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || 'Erro na operação.');
        }
        return data;
    }

    function initPostsDynamic() {
        if (!document.getElementById('postsTableBody')) return;

        applyClientPagination(getCurrentPage());

        // Reaplicar paginação quando filtros mudarem
        ['searchPosts', 'filterCategory', 'filterStatus'].forEach((id) => {
            const input = document.getElementById(id);
            input?.addEventListener('input', () => {
                setTimeout(() => applyClientPagination(1), 0);
            });
            input?.addEventListener('change', () => {
                setTimeout(() => applyClientPagination(1), 0);
            });
        });

        // Interceptar links de paginação
        document.addEventListener('click', function (event) {
            const link = event.target.closest('#postsPaginationContainer a.page-link');
            if (!link) return;

            const page = parseInt(link.dataset.page || '', 10);
            if (!Number.isFinite(page)) return;

            event.preventDefault();
            event.stopPropagation();
            applyClientPagination(page);
        }, true);

        // Impedir submit padrão do formulário de edição (evita location.reload em listeners antigos)
        const editForm = document.getElementById('editPostForm');
        if (editForm && !editForm.dataset.dynamicBound) {
            editForm.dataset.dynamicBound = 'true';
            editForm.addEventListener('submit', function (event) {
                event.preventDefault();
                event.stopImmediatePropagation();
                if (typeof window.savePost === 'function') {
                    window.savePost(event);
                }
            }, true);
        }

        // Abertura de modal de exclusão com delegação (captura)
        document.addEventListener('click', function (event) {
            const deleteBtn = event.target.closest('.btn-delete');
            if (!deleteBtn) return;

            event.preventDefault();
            event.stopImmediatePropagation();

            const postId = deleteBtn.getAttribute('data-post-id');
            const postTitle = deleteBtn.getAttribute('data-post-title') || 'este post';
            const modal = document.getElementById('deleteModal');
            const form = document.getElementById('deletePostForm');
            if (!modal || !form || !postId) return;

            const modalBodyP = modal.querySelector('.modal-body p');
            if (modalBodyP) {
                modalBodyP.innerHTML = `Tem certeza que deseja excluir o post <strong>"${escapeHtml(postTitle)}"</strong>? Esta ação não pode ser desfeita.`;
            }

            form.action = `/admin/posts/${postId}/delete`;
            if (typeof window.openModal === 'function') {
                window.openModal('deleteModal');
            }
        }, true);

        // Excluir post sem reload
        const deleteForm = document.getElementById('deletePostForm');
        if (deleteForm && !deleteForm.dataset.dynamicBound) {
            deleteForm.dataset.dynamicBound = 'true';
            deleteForm.addEventListener('submit', async function (event) {
                event.preventDefault();
                event.stopImmediatePropagation();

                try {
                    const result = await ajaxPost(deleteForm.action);
                    const row = document.querySelector(`tr[data-post-id="${result.post_id}"]`);
                    if (row) row.remove();
                    showToast(result.message || 'Post excluído com sucesso!', 'success');
                    if (typeof window.closeModal === 'function') {
                        window.closeModal('deleteModal');
                    }
                    applyClientPagination(getCurrentPage());
                } catch (error) {
                    showToast(error.message, 'error');
                }
            }, true);
        }

        // Duplicar post sem reload
        document.addEventListener('click', async function (event) {
            const duplicateBtn = event.target.closest('.btn-duplicate');
            if (!duplicateBtn) return;

            event.preventDefault();
            event.stopImmediatePropagation();

            const postId = duplicateBtn.getAttribute('data-post-id');
            if (!postId) return;

            if (!window.confirm('Deseja duplicar este post?')) return;

            try {
                const result = await ajaxPost(`/admin/posts/${postId}/duplicate`);
                if (result.post) {
                    const tableBody = document.getElementById('postsTableBody');
                    tableBody?.insertAdjacentHTML('afterbegin', buildPostRow(result.post));
                    applyClientPagination(1);
                }
                showToast(result.message || 'Post duplicado com sucesso!', 'success');
            } catch (error) {
                showToast(error.message, 'error');
            }
        }, true);

        // Criar novo post sem reload
        const addPostForm = document.getElementById('addPostForm');
        if (addPostForm && !addPostForm.dataset.dynamicBound) {
            addPostForm.dataset.dynamicBound = 'true';
            addPostForm.addEventListener('submit', async function (event) {
                event.preventDefault();

                const formData = new FormData(addPostForm);

                try {
                    const result = await ajaxPost(addPostForm.action, formData);
                    if (result.post) {
                        const tableBody = document.getElementById('postsTableBody');
                        tableBody?.insertAdjacentHTML('afterbegin', buildPostRow(result.post));
                        applyClientPagination(1);
                    }

                    addPostForm.reset();
                    const editor = document.getElementById('postContentEditor');
                    if (editor) editor.innerHTML = '';

                    if (typeof window.closeModal === 'function') {
                        window.closeModal('addPostModal');
                    }

                    showToast(result.message || 'Post criado com sucesso!', 'success');
                } catch (error) {
                    showToast(error.message, 'error');
                }
            }, true);
        }
    }

    document.addEventListener('DOMContentLoaded', initPostsDynamic);
})();
