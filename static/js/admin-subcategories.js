(function () {
    let tree = [];
    let version = '';
    let categories = [];
    let requestInFlight = false;

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function csrfToken() {
        return window.csrfUtils?.getCsrfToken?.()
            || document.querySelector('meta[name="csrf-token"]')?.content
            || '';
    }

    function notify(message, type = 'info') {
        if (typeof window.showNotification === 'function') window.showNotification(message, type);
    }

    function flatten(nodes = tree, depth = 0, output = []) {
        nodes.forEach((node) => {
            output.push({ ...node, depth });
            flatten(node.children || [], depth + 1, output);
        });
        return output;
    }

    function findNode(id) {
        return flatten().find((node) => String(node.id) === String(id));
    }

    function categoryName(categoryId) {
        return categories.find((item) => String(item.id) === String(categoryId))?.name || 'Categoria';
    }

    function renderNode(node, depth) {
        const state = node.is_active ? 'Ativa' : 'Inativa';
        const visibility = node.is_visible ? 'Pública' : 'Oculta';
        const menu = node.show_in_menu ? 'No menu' : 'Fora do menu';
        const children = (node.children || []).map((child) => renderNode(child, depth + 1)).join('');
        return `
            <div class="subcategory-node${node.is_active ? '' : ' is-inactive'}" style="--tree-depth:${depth}" data-subcategory-id="${node.id}">
                <div class="subcategory-node-main">
                    <i class="${escapeHtml(node.icon || 'fas fa-folder')}"></i>
                    <div class="subcategory-node-copy">
                        <strong>${escapeHtml(node.name)}</strong>
                        <small>/subcategoria/${escapeHtml(node.slug)}</small>
                        <div class="subcategory-node-badges">
                            <span>${state}</span><span>${visibility}</span><span>${menu}</span>
                            <span>${Number(node.total_post_count || node.post_count || 0)} post(s)</span>
                        </div>
                    </div>
                </div>
                <div class="subcategory-node-actions">
                    <button type="button" class="btn-action" data-subcategory-add-child="${node.id}" title="Adicionar nível abaixo"><i class="fas fa-level-down-alt"></i></button>
                    <button type="button" class="btn-action btn-edit" data-subcategory-edit="${node.id}" title="Editar"><i class="fas fa-edit"></i></button>
                    <a class="btn-action btn-view" href="/subcategoria/${encodeURIComponent(node.slug)}" target="_blank" title="Visualizar"><i class="fas fa-eye"></i></a>
                    <button type="button" class="btn-action btn-delete" data-subcategory-delete="${node.id}" title="Excluir"><i class="fas fa-trash"></i></button>
                </div>
            </div>${children}`;
    }

    function render() {
        const container = document.getElementById('subcategoryTree');
        if (!container) return;
        if (!tree.length) {
            container.innerHTML = '<div class="subcategory-empty"><i class="fas fa-folder-open fa-2x"></i><p>Nenhuma subcategoria configurada.</p></div>';
            return;
        }

        const rootsByCategory = new Map();
        tree.forEach((node) => {
            if (!rootsByCategory.has(node.category_id)) rootsByCategory.set(node.category_id, []);
            rootsByCategory.get(node.category_id).push(node);
        });
        container.innerHTML = Array.from(rootsByCategory.entries()).map(([categoryId, nodes]) => `
            <section class="subcategory-category-group">
                <h3 class="subcategory-category-title"><i class="fas fa-folder-open"></i>${escapeHtml(categoryName(categoryId))}</h3>
                ${nodes.map((node) => renderNode(node, 0)).join('')}
            </section>
        `).join('');
    }

    function updateCategoryOptions(selectedValue) {
        const select = document.getElementById('subcategoryCategory');
        if (!select) return;
        const selected = String(selectedValue ?? select.value ?? '');
        select.innerHTML = categories.map((category) => `
            <option value="${category.id}"${String(category.id) === selected ? ' selected' : ''}>${escapeHtml(category.name)}</option>
        `).join('');
    }

    function updateParentOptions(categoryId, selectedParentId = '', editingId = '') {
        const select = document.getElementById('subcategoryParent');
        if (!select) return;
        const currentNode = editingId ? findNode(editingId) : null;
        const blockedIds = new Set(currentNode ? flatten(currentNode.children || []).map((node) => String(node.id)) : []);
        blockedIds.add(String(editingId || ''));
        const options = flatten().filter((node) => String(node.category_id) === String(categoryId) && !blockedIds.has(String(node.id)));
        select.innerHTML = '<option value="">Diretamente na categoria</option>' + options.map((node) => {
            const prefix = '— '.repeat(node.depth);
            return `<option value="${node.id}"${String(node.id) === String(selectedParentId) ? ' selected' : ''}>${escapeHtml(prefix + node.name)}</option>`;
        }).join('');
    }

    function openModal(node = null, parent = null) {
        const form = document.getElementById('subcategoryForm');
        form?.reset();
        const editingId = node?.id || '';
        const categoryId = node?.category_id || parent?.category_id || categories[0]?.id || '';
        document.getElementById('subcategoryId').value = editingId;
        document.getElementById('subcategoryModalTitle').innerHTML = node
            ? '<i class="fas fa-edit"></i> Editar subcategoria'
            : '<i class="fas fa-folder-plus"></i> Nova subcategoria';
        updateCategoryOptions(categoryId);
        updateParentOptions(categoryId, node?.parent_id || parent?.id || '', editingId);
        document.getElementById('subcategoryName').value = node?.name || '';
        document.getElementById('subcategorySlug').value = node?.slug || '';
        document.getElementById('subcategoryDescription').value = node?.description || '';
        document.getElementById('subcategoryIcon').value = node?.icon || 'fas fa-folder';
        document.getElementById('subcategoryOrder').value = node?.order || 0;
        document.getElementById('subcategoryActive').checked = node?.is_active !== false;
        document.getElementById('subcategoryVisible').checked = node?.is_visible !== false;
        document.getElementById('subcategoryMenu').checked = node?.show_in_menu !== false;
        if (typeof window.openModal === 'function') window.openModal('subcategoryModal');
    }

    function closeModal() {
        if (typeof window.closeModal === 'function') window.closeModal('subcategoryModal');
    }

    async function request(url, method, payload) {
        const response = await fetch(url, {
            method,
            credentials: 'same-origin',
            cache: 'no-store',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken(),
            },
            body: payload ? JSON.stringify(payload) : undefined,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) throw new Error(data.message || 'Não foi possível concluir a operação.');
        return data;
    }

    function applySnapshot(data) {
        if (Array.isArray(data.tree)) tree = data.tree;
        if (Array.isArray(data.categories)) categories = data.categories;
        version = data.version || version;
        render();
        updateCategoryOptions();
    }

    async function refresh(silent = true) {
        if (requestInFlight || !document.getElementById('subcategoryManager') || document.hidden) return;
        requestInFlight = true;
        try {
            const response = await fetch('/admin/subcategories', {
                credentials: 'same-origin', cache: 'no-store', headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.message || 'Falha ao sincronizar subcategorias.');
            if (data.version !== version || !categories.length) applySnapshot(data);
        } catch (error) {
            if (!silent) notify(error.message, 'error');
        } finally {
            requestInFlight = false;
        }
    }

    function init() {
        const manager = document.getElementById('subcategoryManager');
        if (!manager || manager.dataset.initialized === 'true') return;
        manager.dataset.initialized = 'true';
        try {
            tree = JSON.parse(document.getElementById('subcategoryInitialTree')?.textContent || '[]');
        } catch (_error) {
            tree = [];
        }
        categories = Array.from(document.getElementById('subcategoryCategory')?.options || []).map((option) => ({
            id: Number(option.value), name: option.textContent.trim(),
        }));
        render();

        document.getElementById('newSubcategoryBtn')?.addEventListener('click', () => openModal());
        document.getElementById('subcategoryCategory')?.addEventListener('change', (event) => {
            updateParentOptions(event.target.value, '', document.getElementById('subcategoryId')?.value || '');
        });
        document.querySelectorAll('[data-subcategory-close]').forEach((button) => button.addEventListener('click', closeModal));

        manager.addEventListener('click', async (event) => {
            const addButton = event.target.closest('[data-subcategory-add-child]');
            const editButton = event.target.closest('[data-subcategory-edit]');
            const deleteButton = event.target.closest('[data-subcategory-delete]');
            if (addButton) openModal(null, findNode(addButton.dataset.subcategoryAddChild));
            if (editButton) openModal(findNode(editButton.dataset.subcategoryEdit));
            if (!deleteButton) return;
            const node = findNode(deleteButton.dataset.subcategoryDelete);
            const confirmed = typeof window.showAdminConfirm === 'function'
                ? await window.showAdminConfirm({
                    title: 'Excluir subcategoria?',
                    message: `Excluir "${node?.name || 'esta subcategoria'}" e os níveis abaixo? Os posts serão movidos para o nível anterior.`,
                    confirmLabel: 'Excluir', intent: 'danger', icon: 'fa-trash',
                })
                : window.confirm('Excluir esta subcategoria?');
            if (!confirmed) return;
            try {
                const data = await request(`/admin/subcategories/${deleteButton.dataset.subcategoryDelete}`, 'DELETE');
                applySnapshot(data);
                notify(data.message, 'success');
            } catch (error) {
                notify(error.message, 'error');
            }
        });

        document.getElementById('subcategoryForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const id = document.getElementById('subcategoryId').value;
            const payload = {
                category_id: document.getElementById('subcategoryCategory').value,
                parent_id: document.getElementById('subcategoryParent').value,
                name: document.getElementById('subcategoryName').value,
                slug: document.getElementById('subcategorySlug').value,
                description: document.getElementById('subcategoryDescription').value,
                icon: document.getElementById('subcategoryIcon').value,
                order: document.getElementById('subcategoryOrder').value,
                is_active: document.getElementById('subcategoryActive').checked,
                is_visible: document.getElementById('subcategoryVisible').checked,
                show_in_menu: document.getElementById('subcategoryMenu').checked,
            };
            const button = document.getElementById('saveSubcategoryBtn');
            button.disabled = true;
            try {
                const data = await request(id ? `/admin/subcategories/${id}` : '/admin/subcategories', id ? 'PUT' : 'POST', payload);
                applySnapshot(data);
                closeModal();
                notify(data.message, 'success');
            } catch (error) {
                notify(error.message, 'error');
            } finally {
                button.disabled = false;
            }
        });

        refresh();
        if (window.__subcategoryAdminTimer) window.clearInterval(window.__subcategoryAdminTimer);
        window.__subcategoryAdminTimer = window.setInterval(() => refresh(true), 4000);
    }

    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('adminPageLoaded', init);
})();
