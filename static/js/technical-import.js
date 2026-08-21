(function () {
    'use strict';

    const page = document.getElementById('technicalImportPage');
    if (!page) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const jsonHeaders = { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken };
    const notify = (message, type = 'success') => {
        if (typeof window.showNotification === 'function') window.showNotification(message, type);
        else console[type === 'error' ? 'error' : 'log'](message);
    };
    const api = async (url, options = {}) => {
        options.headers = { 'X-CSRFToken': csrfToken, ...(options.headers || {}) };
        const response = await fetch(url, options);
        const payload = await response.json().catch(() => ({ success: false, message: 'Resposta inválida do servidor.' }));
        if (!response.ok || payload.success === false) throw new Error(payload.message || `HTTP ${response.status}`);
        return payload;
    };

    page.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => {
        page.querySelectorAll('[data-tab]').forEach(item => item.classList.toggle('active', item === button));
        page.querySelectorAll('[data-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.panel === button.dataset.tab));
    }));

    const automationForm = document.getElementById('automationForm');
    automationForm?.querySelector('[name="technical_automation_percentage"]')?.addEventListener('input', event => {
        automationForm.querySelector('[data-percentage-output]').textContent = `${event.target.value}%`;
    });
    automationForm?.querySelector('[name="technical_auto_publish_threshold"]')?.addEventListener('input', event => {
        automationForm.querySelector('[data-threshold-output]').textContent = `${event.target.value}%`;
    });
    automationForm?.addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = form.querySelector('[type="submit"]');
        submit.disabled = true;
        try {
            const data = new FormData(form);
            const payload = {
                technical_import_enabled: data.has('technical_import_enabled'),
                technical_automation_mode: data.get('technical_automation_mode'),
                technical_automation_percentage: Number(data.get('technical_automation_percentage')),
                technical_auto_publish_threshold: Number(data.get('technical_auto_publish_threshold')),
                technical_require_storage_ready: data.has('technical_require_storage_ready'),
            };
            await api('/api/admin/technical-import/settings', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) });
            notify('Configuração da automação salva.');
        } catch (error) { notify(error.message, 'error'); }
        finally { submit.disabled = false; }
    });

    const importModal = document.getElementById('importModal');
    const editModal = document.getElementById('editPreviewModal');
    const setModal = (modal, open) => {
        if (!modal) return;
        modal.classList.toggle('open', open);
        modal.setAttribute('aria-hidden', open ? 'false' : 'true');
        document.body.classList.toggle('technical-modal-lock', Boolean(document.querySelector('.technical-modal.open')));
    };
    page.querySelector('[data-open-import]')?.addEventListener('click', () => setModal(importModal, true));
    importModal?.querySelectorAll('[data-close-modal]').forEach(button => button.addEventListener('click', () => setModal(importModal, false)));
    editModal?.querySelectorAll('[data-close-edit]').forEach(button => button.addEventListener('click', () => setModal(editModal, false)));
    [importModal, editModal].forEach(modal => modal?.addEventListener('click', event => {
        if (event.target === modal) setModal(modal, false);
    }));
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') { setModal(importModal, false); setModal(editModal, false); }
    });

    const importForm = document.getElementById('technicalImportForm');
    importForm?.querySelectorAll('[name="type"]').forEach(radio => radio.addEventListener('change', () => {
        importForm.querySelectorAll('[data-import-fields]').forEach(group => { group.hidden = group.dataset.importFields !== radio.value; });
    }));
    importForm?.addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = form.querySelector('[type="submit"]');
        submit.disabled = true;
        submit.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analisando…';
        try {
            const payload = await api('/api/admin/technical-import/analyze', { method: 'POST', body: new FormData(form) });
            notify(`${payload.message} ${payload.auto_published ? `${payload.auto_published} publicado(s) automaticamente.` : ''}`);
            setModal(importModal, false);
            window.location.reload();
        } catch (error) { notify(error.message, 'error'); }
        finally { submit.disabled = false; submit.innerHTML = '<i class="fas fa-search"></i> Analisar e gerar previews'; }
    });

    page.querySelectorAll('[data-save-source]').forEach(button => button.addEventListener('click', async () => {
        const card = button.closest('[data-source-id]');
        const payload = {};
        card.querySelectorAll('[data-source-field]').forEach(field => { payload[field.dataset.sourceField] = field.type === 'checkbox' ? field.checked : field.value; });
        button.disabled = true;
        try {
            await api(`/api/admin/technical-import/sources/${card.dataset.sourceId}`, { method: 'PATCH', headers: jsonHeaders, body: JSON.stringify(payload) });
            notify('Fonte atualizada.');
        } catch (error) { notify(error.message, 'error'); }
        finally { button.disabled = false; }
    }));

    page.querySelectorAll('[data-sync-source]').forEach(button => button.addEventListener('click', async () => {
        const card = button.closest('[data-source-id]');
        button.disabled = true;
        const original = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sincronizando…';
        try {
            const payload = await api(`/api/admin/technical-import/sources/${card.dataset.sourceId}/sync`, { method: 'POST' });
            notify(payload.message);
            window.location.reload();
        } catch (error) { notify(error.message, 'error'); }
        finally { button.disabled = false; button.innerHTML = original; }
    }));

    page.querySelectorAll('[data-contribution-id]').forEach(row => {
        const contributionId = row.dataset.contributionId;
        row.querySelector('[data-analyze-contribution]')?.addEventListener('click', async event => {
            const button = event.currentTarget;
            button.disabled = true;
            try {
                const payload = await api(`/api/admin/technical-import/contributions/${contributionId}/analyze`, { method: 'POST' });
                notify(payload.message);
                window.location.reload();
            } catch (error) { notify(error.message, 'error'); button.disabled = false; }
        });
        row.querySelector('[data-reject-contribution]')?.addEventListener('click', async event => {
            if (!window.confirm('Rejeitar esta contribuição?')) return;
            const button = event.currentTarget;
            button.disabled = true;
            try {
                const payload = await api(`/api/admin/technical-import/contributions/${contributionId}/reject`, { method: 'POST' });
                notify(payload.message);
                row.remove();
            } catch (error) { notify(error.message, 'error'); button.disabled = false; }
        });
    });

    page.querySelectorAll('[data-health-file-id]').forEach(row => {
        row.querySelector('[data-check-health]')?.addEventListener('click', async event => {
            const button = event.currentTarget;
            button.disabled = true;
            try {
                const payload = await api(`/api/admin/technical-import/files/${row.dataset.healthFileId}/health`, { method: 'POST' });
                const status = row.querySelector('[data-health-status]');
                status.textContent = payload.status;
                status.className = `technical-badge ${payload.status}`;
                row.querySelector('[data-health-http]').textContent = payload.http_status || '—';
                row.querySelector('[data-health-date]').textContent = 'Agora';
                notify(payload.message || 'Link verificado.');
            } catch (error) { notify(error.message, 'error'); }
            finally { button.disabled = false; }
        });
    });

    page.querySelectorAll('[data-item-id]').forEach(card => {
        const itemId = card.dataset.itemId;
        card.querySelector('[data-approve-item]')?.addEventListener('click', async () => {
            const button = card.querySelector('[data-approve-item]'); button.disabled = true;
            try { await api(`/api/admin/technical-import/items/${itemId}/approve`, { method: 'POST' }); notify('Item publicado.'); card.remove(); }
            catch (error) { notify(error.message, 'error'); button.disabled = false; }
        });
        card.querySelector('[data-reject-item]')?.addEventListener('click', async () => {
            if (!window.confirm('Rejeitar este item? O registro continuará no histórico de auditoria.')) return;
            try { await api(`/api/admin/technical-import/items/${itemId}/reject`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ reason: 'Rejeitado no painel.' }) }); notify('Item rejeitado.'); card.remove(); }
            catch (error) { notify(error.message, 'error'); }
        });
        card.querySelector('[data-edit-item]')?.addEventListener('click', () => {
            const metadata = JSON.parse(card.querySelector('[data-item-metadata]').textContent || '{}');
            const form = document.getElementById('editPreviewForm');
            form.elements.item_id.value = itemId;
            ['manufacturer', 'model', 'board_code', 'board_revision', 'file_type', 'chip_position', 'provider_url', 'distribution_policy'].forEach(name => {
                if (form.elements[name]) form.elements[name].value = metadata[name] || '';
            });
            form.elements.confidence.value = card.querySelector('.confidence-ring')?.textContent.replace('%', '').trim() || 0;
            setModal(editModal, true);
        });
    });

    document.getElementById('editPreviewForm')?.addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = Object.fromEntries(new FormData(form).entries());
        const itemId = data.item_id; delete data.item_id;
        data.confidence = Number(data.confidence);
        try {
            await api(`/api/admin/technical-import/items/${itemId}`, { method: 'PATCH', headers: jsonHeaders, body: JSON.stringify(data) });
            notify('Preview atualizado.'); setModal(editModal, false); window.location.reload();
        } catch (error) { notify(error.message, 'error'); }
    });
})();
