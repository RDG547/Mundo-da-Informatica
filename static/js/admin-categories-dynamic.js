(function () {
    function getCsrfToken() {
        return (window.csrfUtils && window.csrfUtils.getCsrfToken && window.csrfUtils.getCsrfToken())
            || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            || '';
    }

    function notify(message, type) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type || 'info');
        } else {
            alert(message);
        }
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

    function normalizeCategory(raw) {
        return {
            id: Number(raw.id),
            name: raw.name || '',
            slug: raw.slug || '',
            description: raw.description || '',
            icon: raw.icon || 'fas fa-folder',
            order: Number(raw.order || 0),
            post_count: Number(raw.post_count || 0),
            featured_posts: Number(raw.featured_posts || 0),
            total_downloads: Number(raw.total_downloads || 0),
            is_active: Boolean(raw.is_active),
            is_featured: Boolean(raw.featured ?? raw.is_featured),
            show_in_menu: raw.show_in_menu !== false,
            color: raw.color || '#4a90e2'
        };
    }

    async function requestJSON(url, method, payload) {
        const response = await fetch(url, {
            method,
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: payload ? JSON.stringify(payload) : undefined
        });

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.message || 'Falha na operação.');
        }
        return data;
    }

    function getRows() {
        return Array.from(document.querySelectorAll('#categoriesTableBody tr[data-category-id]'));
    }

    function getCards() {
        return Array.from(document.querySelectorAll('#gridView .category-card[data-category-id]'));
    }

    function hasFilters() {
        const search = document.getElementById('searchCategories')?.value?.trim();
        const status = document.getElementById('statusFilter')?.value?.trim();
        return Boolean(search || status);
    }

    function getPerPage() {
        const perPage = parseInt(document.getElementById('categoriesPaginationContainer')?.dataset?.perPage || '10', 10);
        return Number.isFinite(perPage) && perPage > 0 ? perPage : 10;
    }

    function getCurrentPage() {
        const fromUrl = parseInt(new URLSearchParams(window.location.search).get('page') || '', 10);
        return Number.isFinite(fromUrl) && fromUrl > 0 ? fromUrl : 1;
    }

    function renderPagination(totalItems, page, perPage) {
        const container = document.getElementById('categoriesPaginationContainer');
        const list = document.getElementById('categoriesPagination');
        const info = document.getElementById('categoriesPaginationInfo');
        if (!container || !list) return;

        const totalPages = Math.max(1, Math.ceil(totalItems / perPage));
        const safePage = Math.min(Math.max(page, 1), totalPages);

        if (info) {
            const visible = getRows().filter((row) => row.style.display !== 'none').length;
            info.textContent = `Mostrando ${visible} de ${totalItems} categorias`;
        }

        const pages = [];
        for (let p = Math.max(1, safePage - 2); p <= Math.min(totalPages, safePage + 2); p += 1) {
            pages.push(p);
        }

        if (!pages.includes(1)) pages.unshift(1);
        if (!pages.includes(totalPages)) pages.push(totalPages);

        const withEllipsis = [];
        pages.sort((a, b) => a - b).forEach((p, index, arr) => {
            if (index > 0 && arr[index - 1] + 1 < p) withEllipsis.push(null);
            withEllipsis.push(p);
        });

        const pageLinks = withEllipsis.map((value) => {
            if (value === null) return '<li class="page-item disabled"><span class="page-link">…</span></li>';
            if (value === safePage) return `<li class="page-item active"><span class="page-link">${value}</span></li>`;
            return `<li class="page-item"><a class="page-link" href="#" data-page="${value}">${value}</a></li>`;
        }).join('');

        const prevDisabled = safePage <= 1;
        const nextDisabled = safePage >= totalPages;

        list.innerHTML = `
            <li class="page-item ${prevDisabled ? 'disabled' : ''}">${prevDisabled ? '<span class="page-link">&laquo;</span>' : `<a class="page-link" href="#" data-page="${safePage - 1}">&laquo;</a>`}</li>
            ${pageLinks}
            <li class="page-item ${nextDisabled ? 'disabled' : ''}">${nextDisabled ? '<span class="page-link">&raquo;</span>' : `<a class="page-link" href="#" data-page="${safePage + 1}">&raquo;</a>`}</li>
        `;

        container.dataset.currentPage = String(safePage);
    }

    function applyPagination(targetPage) {
        const rows = getRows();
        const cards = getCards();
        const total = rows.length;
        const perPage = getPerPage();

        if (!total) {
            renderPagination(0, 1, perPage);
            return;
        }

        if (hasFilters()) {
            renderPagination(total, 1, Math.max(total, perPage));
            return;
        }

        const totalPages = Math.max(1, Math.ceil(total / perPage));
        const page = Math.min(Math.max(targetPage || 1, 1), totalPages);
        const start = (page - 1) * perPage;
        const end = start + perPage;

        rows.forEach((row, index) => {
            row.style.display = index >= start && index < end ? '' : 'none';
        });

        cards.forEach((card, index) => {
            card.style.display = index >= start && index < end ? '' : 'none';
        });

        renderPagination(total, page, perPage);

        const url = new URL(window.location.href);
        url.searchParams.set('page', String(page));
        window.history.replaceState({}, '', `${url.pathname}${url.search}`);
    }

    function buildRow(category) {
        return `
            <tr data-category-id="${category.id}" data-category-order="${category.order}" ${category.is_active ? '' : 'class="inactive-row"'}>
                <td><input type="checkbox" class="form-check-input category-checkbox" value="${category.id}"></td>
                <td>
                    <div class="category-name">
                        <i class="${escapeHtml(category.icon)}" style="margin-right: 8px; color: #3a86ff;"></i>
                        <span class="category-title">${escapeHtml(category.name)}</span>
                        ${category.description ? `<small class="text-muted">${escapeHtml(category.description.substring(0, 80))}${category.description.length > 80 ? '...' : ''}</small>` : ''}
                    </div>
                </td>
                <td><code class="category-slug">${escapeHtml(category.slug)}</code></td>
                <td><div class="post-stats"><span class="total-posts">${category.post_count}</span>${category.featured_posts > 0 ? `<small class="featured-posts"><i class="fas fa-star text-warning"></i> ${category.featured_posts}</small>` : ''}</div></td>
                <td><span class="download-count">${category.total_downloads}</span></td>
                <td><span class="text-muted">Nenhum post</span></td>
                <td>
                    <button class="badge ${category.is_active ? 'badge-success' : 'badge-secondary'} status-toggle" data-category-id="${category.id}" style="border: none; cursor: pointer;" title="Clique para alterar status">
                        ${category.is_active ? 'Ativa' : 'Inativa'}
                    </button>
                </td>
                <td>
                    <div class="form-check form-switch">
                        <input type="checkbox" class="form-check-input featured-toggle" data-category-id="${category.id}" ${category.is_featured ? 'checked' : ''}>
                    </div>
                </td>
                <td class="actions">
                    <div class="action-buttons">
                        <a href="#" class="btn-action btn-edit" title="Editar" data-category-id="${category.id}"><i class="fas fa-edit"></i></a>
                        <a href="#" class="btn-action btn-delete" title="Excluir" data-category-id="${category.id}" data-category-name="${escapeHtml(category.name)}" data-post-count="${category.post_count}"><i class="fas fa-trash"></i><span>Excluir</span></a>
                        <a href="/categoria/${encodeURIComponent(category.slug)}" class="btn-action btn-view" title="Ver Categoria" target="_blank"><i class="fas fa-external-link-alt"></i></a>
                    </div>
                </td>
            </tr>
        `;
    }

    function buildCard(category) {
        return `
            <div class="category-card${category.is_active ? '' : ' inactive'}" data-category-id="${category.id}" data-category-order="${category.order}">
                <div class="card-header">
                    <div class="category-icon-large"><i class="${escapeHtml(category.icon)}"></i></div>
                    <div class="category-actions-quick">
                        <button class="quick-action featured-toggle" data-category-id="${category.id}" title="${category.is_featured ? 'Remover dos destaques' : 'Destacar categoria'}">
                            <i class="fas fa-star ${category.is_featured ? 'text-warning' : ''}"></i>
                        </button>
                        <button class="quick-action" onclick="editCategory(${category.id})" title="Edição rápida"><i class="fas fa-edit"></i></button>
                    </div>
                </div>
                <div class="card-body">
                    <h4 class="category-name">${escapeHtml(category.name)}</h4>
                    <p class="category-description">${category.description ? `${escapeHtml(category.description.substring(0, 80))}${category.description.length > 80 ? '...' : ''}` : 'Sem descrição'}</p>
                    <div class="category-stats-grid">
                        <div class="stat-item"><span class="stat-number">${category.post_count}</span><span class="stat-label">Posts</span></div>
                        <div class="stat-item"><span class="stat-number">${category.total_downloads}</span><span class="stat-label">Downloads</span></div>
                        <div class="stat-item"><span class="stat-number">${category.featured_posts}</span><span class="stat-label">Destaque</span></div>
                    </div>
                    <button class="status-badge ${category.is_active ? 'active' : 'inactive'} status-toggle" data-category-id="${category.id}" title="Clique para alterar status">${category.is_active ? 'Ativa' : 'Inativa'}</button>
                </div>
                <div class="card-footer">
                    <button class="btn-card btn-primary" onclick="editCategory(${category.id})"><i class="fas fa-edit"></i> Editar</button>
                    <button class="btn-card btn-secondary" onclick="viewCategory('${escapeHtml(category.slug)}')"><i class="fas fa-eye"></i> Ver</button>
                    <button class="btn-card btn-danger" onclick="deleteCategory(${category.id}, '${escapeHtml(category.name)}')"><i class="fas fa-trash"></i> Excluir</button>
                </div>
            </div>
        `;
    }

    function updateRowAndCard(category) {
        const row = document.querySelector(`#categoriesTableBody tr[data-category-id="${category.id}"]`);
        const card = document.querySelector(`#gridView .category-card[data-category-id="${category.id}"]`);
        const has = (key) => Object.prototype.hasOwnProperty.call(category, key);

        if (row) {
            const title = row.querySelector('.category-title');
            const slug = row.querySelector('.category-slug');
            const rowIcon = row.querySelector('.category-name i');
            const postStats = row.querySelector('.post-stats');
            const downloads = row.querySelector('.download-count');
            const statusBtn = row.querySelector('.status-toggle');
            const featuredInput = row.querySelector('.featured-toggle');
            const deleteBtn = row.querySelector('.btn-delete');
            const descSmall = row.querySelector('.category-name small');
            if (has('order')) row.dataset.categoryOrder = String(category.order || 0);
            if (has('name') && title) title.textContent = category.name;
            if (has('slug') && slug) slug.textContent = category.slug;
            if (has('icon') && rowIcon) rowIcon.className = category.icon;
            if (has('description') && descSmall) {
                if (category.description) {
                    descSmall.textContent = `${category.description.substring(0, 80)}${category.description.length > 80 ? '...' : ''}`;
                } else {
                    descSmall.remove();
                }
            }
            if (has('post_count') || has('featured_posts')) {
                const postCount = has('post_count') ? Number(category.post_count || 0) : Number(row.querySelector('.total-posts')?.textContent || 0);
                const featuredPosts = has('featured_posts') ? Number(category.featured_posts || 0) : Number(row.querySelector('.featured-posts')?.textContent?.replace(/[^\d]/g, '') || 0);
                if (postStats) {
                    postStats.innerHTML = `<span class="total-posts">${postCount}</span>${featuredPosts > 0 ? `<small class="featured-posts"><i class="fas fa-star text-warning"></i> ${featuredPosts}</small>` : ''}`;
                }
            }
            if (has('total_downloads') && downloads) downloads.textContent = String(category.total_downloads);
            if (has('is_featured') && featuredInput) featuredInput.checked = Boolean(category.is_featured);
            if (has('is_active') && statusBtn) {
                statusBtn.textContent = category.is_active ? 'Ativa' : 'Inativa';
                statusBtn.classList.toggle('badge-success', category.is_active);
                statusBtn.classList.toggle('badge-secondary', !category.is_active);
                row.classList.toggle('inactive-row', !category.is_active);
            }
            if (deleteBtn && has('name')) {
                deleteBtn.setAttribute('data-category-name', category.name);
            }
        }

        if (card) {
            const name = card.querySelector('.category-name');
            const desc = card.querySelector('.category-description');
            const icon = card.querySelector('.category-icon-large i');
            const statusBadge = card.querySelector('.status-badge');
            const star = card.querySelector('.featured-toggle i');
            const statNumbers = card.querySelectorAll('.category-stats-grid .stat-number');
            const viewBtn = card.querySelector('.btn-card.btn-secondary');
            const editBtn = card.querySelector('.btn-card.btn-primary');
            const deleteBtn = card.querySelector('.btn-card.btn-danger');
            if (has('order')) card.dataset.categoryOrder = String(category.order || 0);
            if (has('name') && name) name.textContent = category.name;
            if (has('description') && desc) {
                desc.textContent = category.description ? `${category.description.substring(0, 80)}${category.description.length > 80 ? '...' : ''}` : 'Sem descrição';
            }
            if (has('icon') && icon) icon.className = category.icon;
            if (has('is_active') && statusBadge) {
                statusBadge.textContent = category.is_active ? 'Ativa' : 'Inativa';
                statusBadge.classList.toggle('active', category.is_active);
                statusBadge.classList.toggle('inactive', !category.is_active);
                card.classList.toggle('inactive', !category.is_active);
            }
            if (has('is_featured') && star) {
                star.classList.toggle('text-warning', category.is_featured);
            }
            if (has('post_count') && statNumbers[0]) statNumbers[0].textContent = String(category.post_count);
            if (has('total_downloads') && statNumbers[1]) statNumbers[1].textContent = String(category.total_downloads);
            if (has('featured_posts') && statNumbers[2]) statNumbers[2].textContent = String(category.featured_posts);
            if (has('slug') && viewBtn) {
                viewBtn.setAttribute('onclick', `viewCategory('${escapeHtml(category.slug)}')`);
            }
            if (has('id') && editBtn) {
                editBtn.setAttribute('onclick', `editCategory(${category.id})`);
            }
            if (has('id') && has('name') && deleteBtn) {
                deleteBtn.setAttribute('onclick', `deleteCategory(${category.id}, '${escapeHtml(category.name)}')`);
            }
        }
    }

    function appendCategory(category) {
        const rowContainer = document.getElementById('categoriesTableBody');
        const grid = document.getElementById('gridView');

        if (rowContainer) rowContainer.insertAdjacentHTML('afterbegin', buildRow(category));
        if (grid) {
            const empty = grid.querySelector('.empty-state-grid');
            if (empty) empty.remove();
            grid.insertAdjacentHTML('afterbegin', buildCard(category));
        }

        const countBadge = document.querySelector('.count-badge');
        if (countBadge) countBadge.textContent = String(getRows().length);

        applyPagination(1);
    }

    function removeCategory(id) {
        document.querySelector(`#categoriesTableBody tr[data-category-id="${id}"]`)?.remove();
        document.querySelector(`#gridView .category-card[data-category-id="${id}"]`)?.remove();

        const countBadge = document.querySelector('.count-badge');
        if (countBadge) countBadge.textContent = String(getRows().length);

        applyPagination(getCurrentPage());
    }

    function openDeleteModal(categoryId, categoryName) {
        const idInput = document.getElementById('deleteCategoryId');
        const nameEl = document.getElementById('deleteCategoryName');
        if (idInput) idInput.value = String(categoryId);
        if (nameEl) nameEl.textContent = categoryName;
        if (typeof window.openModal === 'function') {
            window.openModal('deleteCategoryModal');
        }
    }

    async function openEditModal(categoryId) {
        try {
            const data = await requestJSON(`/admin/categories/${categoryId}/edit`, 'GET');
            const category = normalizeCategory(data.category || {});

            document.getElementById('editCategoryId').value = String(category.id);
            document.getElementById('editCategoryName').value = category.name;
            document.getElementById('editCategorySlug').value = category.slug;
            document.getElementById('editCategoryDescription').value = category.description;
            document.getElementById('editCategoryOrder').value = String(category.order || 0);
            document.getElementById('editCategoryIcon').value = category.icon;
            const _colorEl = document.getElementById('editCategoryColor');
            const _colorTextEl = document.getElementById('editCategoryColorText');
            if (_colorEl) _colorEl.value = category.color || '#4a90e2';
            if (_colorTextEl) _colorTextEl.value = category.color || '#4a90e2';
            document.getElementById('editCategoryActive').checked = category.is_active;
            document.getElementById('editCategoryFeatured').checked = category.is_featured;
            document.getElementById('editCategoryShowInMenu').checked = category.show_in_menu;

            const iconPreview = document.getElementById('editIconPreview');
            if (iconPreview) iconPreview.innerHTML = `<i class="${category.icon}"></i>`;
            const previewName = document.getElementById('editPreviewName');
            if (previewName) previewName.textContent = category.name || 'Nome da Categoria';
            const previewDesc = document.getElementById('editPreviewDesc');
            if (previewDesc) previewDesc.textContent = category.description || 'Descrição da categoria';

            if (typeof window.openModal === 'function') {
                window.openModal('editCategoryModal');
            }
        } catch (error) {
            notify(error.message, 'error');
        }
    }

    async function refreshStats() {
        try {
            const data = await requestJSON('/admin/categories/stats', 'GET');
            const statsValues = document.querySelectorAll('.stats-summary .stats-value');
            if (statsValues.length >= 3) {
                statsValues[0].textContent = String(data.total || 0);
                statsValues[1].textContent = String(data.active || 0);
                statsValues[2].textContent = String(data.featured || 0);
            }
            const countBadge = document.querySelector('.count-badge');
            if (countBadge && typeof data.total !== 'undefined') {
                countBadge.textContent = String(data.total);
            }
        } catch (error) {
            console.warn('Falha ao atualizar estatísticas:', error);
        }
    }

    function init() {
        if (!document.getElementById('categoriesTableBody')) return;

        applyPagination(getCurrentPage());

        ['searchCategories', 'statusFilter'].forEach((id) => {
            const element = document.getElementById(id);
            element?.addEventListener('input', () => setTimeout(() => applyPagination(1), 0));
            element?.addEventListener('change', () => setTimeout(() => applyPagination(1), 0));
        });

        document.querySelectorAll('.view-btn').forEach((button) => {
            button.addEventListener('click', () => setTimeout(() => applyPagination(getCurrentPage()), 0));
        });

        document.addEventListener('click', async function (event) {
            const pageLink = event.target.closest('#categoriesPagination a.page-link[data-page]');
            if (pageLink) {
                event.preventDefault();
                event.stopPropagation();
                const page = parseInt(pageLink.dataset.page || '1', 10);
                applyPagination(page);
                return;
            }

            const editBtn = event.target.closest('.btn-edit[data-category-id]');
            if (editBtn) {
                event.preventDefault();
                event.stopImmediatePropagation();
                const categoryId = editBtn.getAttribute('data-category-id');
                if (categoryId) await openEditModal(categoryId);
                return;
            }

            const deleteBtn = event.target.closest('.btn-delete[data-category-id]');
            if (deleteBtn) {
                event.preventDefault();
                event.stopImmediatePropagation();
                const categoryId = deleteBtn.getAttribute('data-category-id');
                const categoryName = deleteBtn.getAttribute('data-category-name') || 'Categoria';
                if (categoryId) openDeleteModal(categoryId, categoryName);
                return;
            }

            const statusBtn = event.target.closest('.status-toggle[data-category-id]');
            if (statusBtn) {
                event.preventDefault();
                event.stopImmediatePropagation();
                const categoryId = statusBtn.getAttribute('data-category-id');
                if (!categoryId) return;

                try {
                    const result = await requestJSON(`/admin/categories/${categoryId}/toggle-status`, 'POST');
                    const category = { id: Number(categoryId), is_active: Boolean(result.is_active) };
                    updateRowAndCard(category);
                    notify(result.message, 'success');
                    refreshStats();
                } catch (error) {
                    notify(error.message, 'error');
                }
                return;
            }
        }, true);

        document.addEventListener('change', async function (event) {
            const featureCheckbox = event.target.closest('.featured-toggle[data-category-id]');
            if (!featureCheckbox || featureCheckbox.tagName !== 'INPUT') return;

            event.stopImmediatePropagation();
            const categoryId = featureCheckbox.getAttribute('data-category-id');
            if (!categoryId) return;

            try {
                const result = await requestJSON(`/admin/categories/${categoryId}/toggle-featured`, 'POST');
                updateRowAndCard({ id: Number(categoryId), is_featured: Boolean(result.featured) });
                notify(result.message, 'success');
                refreshStats();
            } catch (error) {
                featureCheckbox.checked = !featureCheckbox.checked;
                notify(error.message, 'error');
            }
        }, true);

        // Grid star button
        document.addEventListener('click', async function (event) {
            const starBtn = event.target.closest('.featured-toggle[data-category-id]:not(input)');
            if (!starBtn) return;
            event.preventDefault();
            event.stopImmediatePropagation();

            const categoryId = starBtn.getAttribute('data-category-id');
            if (!categoryId) return;

            try {
                const result = await requestJSON(`/admin/categories/${categoryId}/toggle-featured`, 'POST');
                updateRowAndCard({ id: Number(categoryId), is_featured: Boolean(result.featured) });
                notify(result.message, 'success');
                refreshStats();
            } catch (error) {
                notify(error.message, 'error');
            }
        }, true);

        const saveCategoryBtn = document.getElementById('saveCategoryBtn');
        saveCategoryBtn?.addEventListener('click', async function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();

            const form = document.getElementById('addCategoryForm');
            if (!form) return;
            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }

            const formData = new FormData(form);
            const payload = Object.fromEntries(formData.entries());
            payload.is_active = document.getElementById('categoryActive')?.checked || false;
            payload.featured = document.getElementById('categoryFeatured')?.checked || false;
            payload.show_in_menu = document.getElementById('categoryShowInMenu')?.checked || false;

            try {
                const result = await requestJSON('/admin/categories/create', 'POST', payload);
                const category = normalizeCategory(result.category || {});
                appendCategory(category);
                notify(result.message, 'success');
                form.reset();
                if (typeof window.closeModal === 'function') window.closeModal('addCategoryModal');
                refreshStats();
            } catch (error) {
                notify(error.message, 'error');
            }
        }, true);

        const updateCategoryBtn = document.getElementById('updateCategoryBtn');
        updateCategoryBtn?.addEventListener('click', async function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();

            const form = document.getElementById('editCategoryForm');
            if (!form || !form.checkValidity()) {
                form?.reportValidity();
                return;
            }

            const categoryId = document.getElementById('editCategoryId')?.value;
            if (!categoryId) return;

            const payload = {
                name: document.getElementById('editCategoryName')?.value || '',
                slug: document.getElementById('editCategorySlug')?.value || '',
                description: document.getElementById('editCategoryDescription')?.value || '',
                icon: document.getElementById('editCategoryIcon')?.value || 'fas fa-folder',
                color: document.getElementById('editCategoryColor')?.value || '#4a90e2',
                order: parseInt(document.getElementById('editCategoryOrder')?.value || '0', 10) || 0,
                is_active: document.getElementById('editCategoryActive')?.checked || false,
                featured: document.getElementById('editCategoryFeatured')?.checked || false,
                show_in_menu: document.getElementById('editCategoryShowInMenu')?.checked || false
            };

            try {
                const result = await requestJSON(`/admin/categories/${categoryId}/update`, 'POST', payload);
                const category = normalizeCategory(result.category || { id: categoryId, ...payload });
                updateRowAndCard(category);
                notify(result.message, 'success');
                if (typeof window.closeModal === 'function') window.closeModal('editCategoryModal');
                refreshStats();
            } catch (error) {
                notify(error.message, 'error');
            }
        }, true);

        const confirmDeleteBtn = document.getElementById('confirmDeleteCategory');
        confirmDeleteBtn?.addEventListener('click', async function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();

            const categoryId = document.getElementById('deleteCategoryId')?.value;
            if (!categoryId) return;

            try {
                const result = await requestJSON(`/admin/categories/${categoryId}/delete`, 'DELETE');
                removeCategory(categoryId);
                notify(result.message, 'success');
                if (typeof window.closeModal === 'function') window.closeModal('deleteCategoryModal');
                refreshStats();
            } catch (error) {
                notify(error.message, 'error');
            }
        }, true);

        const bulkBtn = document.getElementById('applyBulkAction');
        bulkBtn?.addEventListener('click', async function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();

            const action = document.getElementById('bulkActionSelect')?.value;
            const selected = Array.from(document.querySelectorAll('.category-checkbox:checked')).map((cb) => cb.value);
            if (!action) {
                notify('Por favor, selecione uma ação.', 'warning');
                return;
            }
            if (!selected.length) {
                notify('Por favor, selecione pelo menos uma categoria.', 'warning');
                return;
            }
            if (action === 'delete' && !window.confirm(`Tem certeza que deseja excluir ${selected.length} categorias?`)) {
                return;
            }

            try {
                const result = await requestJSON('/admin/categories/bulk-action', 'POST', {
                    action,
                    category_ids: selected
                });

                if (action === 'delete') {
                    selected.forEach((id) => removeCategory(id));
                }
                if (action === 'toggle-status') {
                    selected.forEach((id) => {
                        const row = document.querySelector(`#categoriesTableBody tr[data-category-id="${id}"]`);
                        const currentlyActive = row ? !row.classList.contains('inactive-row') : true;
                        updateRowAndCard({ id: Number(id), is_active: !currentlyActive });
                    });
                }
                if (action === 'feature' || action === 'unfeature') {
                    const featured = action === 'feature';
                    selected.forEach((id) => {
                        updateRowAndCard({ id: Number(id), is_featured: featured });
                    });
                }

                document.getElementById('selectAllCategories').checked = false;
                document.querySelectorAll('.category-checkbox').forEach((cb) => { cb.checked = false; });
                document.getElementById('bulkActionSelect').value = '';

                notify(result.message, 'success');
                applyPagination(getCurrentPage());
                refreshStats();
            } catch (error) {
                notify(error.message, 'error');
            }
        }, true);

        // Sobrescrever refresh sem reload
        window.refreshStats = function () {
            notify('Atualizando estatísticas...', 'info');
            refreshStats();
        };

        // Sobrescrever helpers globais para garantir comportamento consistente
        window.deleteCategory = function (categoryId, categoryName) {
            openDeleteModal(categoryId, categoryName);
        };

        window.editCategory = function (categoryId) {
            openEditModal(categoryId);
        };
    }

    document.addEventListener('DOMContentLoaded', init);
})();
