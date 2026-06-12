/**
 * Post Wizard - Multi-Step Form for Creating Posts
 * Gerencia o formulário de múltiplas etapas para criar posts
 */

function initPostWizard() {
    // Verificar se o modal existe na página
    const addPostModal = document.getElementById('addPostModal');
    if (!addPostModal) {
        return; // Sair se não houver modal de post na página
    }

    if (addPostModal.dataset.postWizardInitialized === 'true') {
        return;
    }
    addPostModal.dataset.postWizardInitialized = 'true';

    console.log('Post Wizard inicializado');

    // ==========================================
    // MULTI-STEP FORM WIZARD
    // ==========================================
    let currentStep = 1;
    const totalSteps = 3;

    const nextBtn = document.getElementById('nextStep');
    const prevBtn = document.getElementById('prevStep');
    const saveBtn = document.getElementById('savePostBtn');
    const richEditor = document.getElementById('postContentEditor');
    const hiddenTextarea = document.getElementById('postContent');
    const addPostForm = document.getElementById('addPostForm');
    const saveBtnDefaultHtml = saveBtn ? saveBtn.innerHTML : '';
    const VALIDATABLE_FIELDS_SELECTOR = 'input, select, textarea';
    let downloadTypes = getConfiguredDownloadTypes();

    if (!nextBtn || !prevBtn || !saveBtn) {
        console.error('Botões do wizard não encontrados!');
        return;
    }

    if (addPostForm) {
        addPostForm.noValidate = true;
    }

    function setSubmitState(isSubmitting) {
        saveBtn.disabled = isSubmitting;
        saveBtn.innerHTML = isSubmitting
            ? '<i class="fas fa-spinner fa-spin"></i> Publicando...'
            : saveBtnDefaultHtml;
    }

    function syncRichEditorContent() {
        if (richEditor && hiddenTextarea) {
            hiddenTextarea.value = richEditor.innerHTML;
        }
    }

    function getConfiguredDownloadTypes() {
        const fallbackTypes = [{ label: 'BIOS' }, { label: 'EC' }, { label: 'ME' }, { label: 'Outros' }];
        const script = document.getElementById('download-file-types-data');

        try {
            const parsed = script?.textContent ? JSON.parse(script.textContent) : window.adminDownloadTypes;
            if (!Array.isArray(parsed)) {
                return fallbackTypes;
            }

            const normalized = parsed
                .map((item) => ({ label: String(item?.label || item || '').trim() }))
                .filter((item, index, list) => item.label && list.findIndex((candidate) => candidate.label.toLowerCase() === item.label.toLowerCase()) === index);

            return normalized.length ? normalized : fallbackTypes;
        } catch (_error) {
            return fallbackTypes;
        }
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function renderDownloadTypeOptions(selectedValue = '') {
        const selected = String(selectedValue || '');
        const optionLabels = downloadTypes.map((item) => item.label);

        if (selected && !optionLabels.includes(selected)) {
            optionLabels.push(selected);
        }

        return optionLabels.map((label) => (
            `<option value="${escapeHtml(label)}"${label === selected ? ' selected' : ''}>${escapeHtml(label)}</option>`
        )).join('');
    }

    function refreshDownloadTypeSelects() {
        document.querySelectorAll('.download-type-select').forEach((select) => {
            const previousValue = select.value;
            select.innerHTML = renderDownloadTypeOptions(previousValue);
            if (!select.value && downloadTypes[0]) {
                select.value = downloadTypes[0].label;
            }
        });
    }

    function getCsrfToken() {
        return (window.csrfUtils && window.csrfUtils.getCsrfToken && window.csrfUtils.getCsrfToken())
            || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            || '';
    }

    function initDownloadTypesManager() {
        const manager = document.getElementById('downloadTypesManager');
        const manageBtn = document.getElementById('manageDownloadTypesBtn');
        const list = document.getElementById('downloadTypesList');
        const addTypeBtn = document.getElementById('addDownloadTypeBtn');
        const saveTypesBtn = document.getElementById('saveDownloadTypesBtn');

        if (!manager || !manageBtn || !list || manager.dataset.initialized === 'true') {
            return;
        }

        manager.dataset.initialized = 'true';

        function renderRows() {
            list.innerHTML = downloadTypes.map((type) => `
                <div class="download-type-row">
                    <input type="text" class="form-control modern-input download-type-name-input" value="${escapeHtml(type.label)}" maxlength="30" aria-label="Nome do tipo de download">
                    <button type="button" class="download-type-remove" title="Excluir tipo" aria-label="Excluir tipo">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `).join('');
        }

        function collectRows() {
            const labels = [];
            const seenLabels = new Set();

            list.querySelectorAll('.download-type-name-input').forEach((input) => {
                const label = String(input.value || '').trim().replace(/\s+/g, ' ');
                const key = label.toLowerCase();
                if (label && !seenLabels.has(key)) {
                    labels.push({ label });
                    seenLabels.add(key);
                }
            });

            return labels;
        }

        manageBtn.addEventListener('click', () => {
            manager.classList.toggle('active');
            if (manager.classList.contains('active')) {
                renderRows();
            }
        });

        addTypeBtn?.addEventListener('click', () => {
            const row = document.createElement('div');
            row.className = 'download-type-row';
            row.innerHTML = `
                <input type="text" class="form-control modern-input download-type-name-input" value="" maxlength="30" aria-label="Nome do tipo de download">
                <button type="button" class="download-type-remove" title="Excluir tipo" aria-label="Excluir tipo">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            list.appendChild(row);
            row.querySelector('input')?.focus();
        });

        list.addEventListener('click', (event) => {
            const removeBtn = event.target.closest('.download-type-remove');
            if (!removeBtn) return;

            const rows = list.querySelectorAll('.download-type-row');
            if (rows.length <= 1) {
                if (typeof showNotification === 'function') {
                    showNotification('Mantenha pelo menos um tipo de arquivo.', 'warning');
                }
                return;
            }

            removeBtn.closest('.download-type-row')?.remove();
        });

        saveTypesBtn?.addEventListener('click', async () => {
            const nextTypes = collectRows();
            if (!nextTypes.length) {
                if (typeof showNotification === 'function') {
                    showNotification('Informe pelo menos um tipo de arquivo.', 'warning');
                }
                return;
            }

            const defaultHtml = saveTypesBtn.innerHTML;
            saveTypesBtn.disabled = true;
            saveTypesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';

            try {
                const response = await fetch('/admin/download-types', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ types: nextTypes })
                });
                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(data.message || 'Erro ao salvar tipos de download.');
                }

                downloadTypes = getConfiguredDownloadTypesFromPayload(data.types);
                window.adminDownloadTypes = downloadTypes;
                const script = document.getElementById('download-file-types-data');
                if (script) {
                    script.textContent = JSON.stringify(downloadTypes);
                }

                refreshDownloadTypeSelects();
                renderRows();
                if (typeof showNotification === 'function') {
                    showNotification(data.message || 'Tipos de download salvos com sucesso.', 'success');
                }
            } catch (error) {
                if (typeof showNotification === 'function') {
                    showNotification(error.message, 'error');
                }
            } finally {
                saveTypesBtn.disabled = false;
                saveTypesBtn.innerHTML = defaultHtml;
            }
        });

        renderRows();
    }

    function getConfiguredDownloadTypesFromPayload(payload) {
        const normalized = Array.isArray(payload)
            ? payload.map((item) => ({ label: String(item?.label || item || '').trim() })).filter((item) => item.label)
            : [];
        return normalized.length ? normalized : [{ label: 'BIOS' }];
    }

    function initIconSelects(root = document) {
        root.querySelectorAll('[data-icon-select]').forEach((wrapper) => {
            if (wrapper.dataset.iconSelectInitialized === 'true') {
                syncIconSelect(wrapper);
                return;
            }

            const selectId = wrapper.dataset.sourceSelect;
            const select = selectId ? document.getElementById(selectId) : null;
            const trigger = wrapper.querySelector('.icon-select-trigger');
            const options = wrapper.querySelectorAll('.icon-select-option');

            if (!select || !trigger) {
                return;
            }

            wrapper.dataset.iconSelectInitialized = 'true';

            trigger.addEventListener('click', () => {
                const isOpen = wrapper.classList.toggle('open');
                trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            });

            options.forEach((option) => {
                option.addEventListener('click', () => {
                    select.value = option.dataset.value || '';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    syncIconSelect(wrapper);
                    wrapper.classList.remove('open');
                    trigger.setAttribute('aria-expanded', 'false');
                });
            });

            select.addEventListener('change', () => syncIconSelect(wrapper));
            syncIconSelect(wrapper);
        });
    }

    function syncIconSelect(wrapper) {
        const selectId = wrapper.dataset.sourceSelect;
        const select = selectId ? document.getElementById(selectId) : null;
        const current = wrapper.querySelector('.icon-select-current');

        if (!select || !current) {
            return;
        }

        const selectedOption = select.options[select.selectedIndex] || select.options[0];
        const icon = selectedOption?.dataset?.icon || 'fas fa-folder';
        const label = selectedOption?.textContent?.trim() || 'Selecione uma categoria';

        current.innerHTML = `<i class="${escapeHtml(icon)}"></i><span>${escapeHtml(label)}</span>`;

        wrapper.querySelectorAll('.icon-select-option').forEach((option) => {
            option.classList.toggle('active', (option.dataset.value || '') === select.value);
        });
    }

    function getRichEditorText() {
        if (!richEditor) {
            return hiddenTextarea?.value?.trim() || '';
        }

        return richEditor.textContent
            .replace(/\u00a0/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function normalizeDownloadSizeValue(rawValue) {
        const trimmedValue = typeof rawValue === 'string' ? rawValue.trim() : '';

        if (!trimmedValue) {
            return '';
        }

        const normalizedValue = trimmedValue.replace(',', '.').replace(/\s+/g, '');

        if (!/^\d+(?:\.\d+)?$/.test(normalizedValue)) {
            return null;
        }

        return normalizedValue;
    }

    function markFieldInvalid(field) {
        field.classList.add('is-invalid');
    }

    function clearFieldInvalid(field) {
        field.classList.remove('is-invalid');
    }

    function shouldSkipFieldValidation(field, options = {}) {
        if (!field || field.disabled || field === hiddenTextarea) {
            return true;
        }

        const fieldType = (field.getAttribute('type') || '').toLowerCase();
        if (['hidden', 'button', 'submit', 'reset', 'file'].includes(fieldType)) {
            return true;
        }

        const stepContent = field.closest('.step-content');
        let currentNode = field;

        while (currentNode && currentNode !== stepContent) {
            if (currentNode.hidden) {
                return true;
            }

            const style = window.getComputedStyle(currentNode);
            if (style.display === 'none' || style.visibility === 'hidden') {
                return true;
            }

            currentNode = currentNode.parentElement;
        }

        return !options.ignoreWizardVisibility
            && stepContent
            && !stepContent.classList.contains('active');
    }

    function validateRichEditor() {
        syncRichEditorContent();

        const hasContent = getRichEditorText().length > 0;
        const target = richEditor || hiddenTextarea;

        if (target) {
            target.classList.toggle('is-invalid', !hasContent);
        }

        if (hiddenTextarea) {
            hiddenTextarea.classList.toggle('is-invalid', !hasContent);
        }

        return hasContent;
    }

    function validateDownloadSizeField(field) {
        const normalizedValue = normalizeDownloadSizeValue(field.value);

        if (normalizedValue === null) {
            markFieldInvalid(field);
            return false;
        }

        if (normalizedValue) {
            field.value = normalizedValue;
        }

        clearFieldInvalid(field);
        return true;
    }

    function validateField(field, options = {}) {
        if (shouldSkipFieldValidation(field, options)) {
            return true;
        }

        if (field.classList.contains('download-size-input')) {
            return validateDownloadSizeField(field);
        }

        const fieldType = (field.getAttribute('type') || '').toLowerCase();
        const rawValue = typeof field.value === 'string' ? field.value.trim() : '';
        const hasValue = fieldType === 'checkbox' || fieldType === 'radio'
            ? field.checked
            : rawValue.length > 0;

        if (!field.required && !hasValue) {
            clearFieldInvalid(field);
            return true;
        }

        if (!field.checkValidity()) {
            markFieldInvalid(field);
            return false;
        }

        clearFieldInvalid(field);
        return true;
    }

    function showStep(step) {
        // Ocultar todos os step-content
        addPostModal.querySelectorAll('.step-content').forEach(content => {
            content.classList.remove('active');
        });

        // Remover active de todos os steps
        addPostModal.querySelectorAll('.form-steps .step').forEach(stepEl => {
            stepEl.classList.remove('active', 'completed');
        });

        // Mostrar o step atual
        const currentContent = addPostModal.querySelector(`.step-content[data-step="${step}"]`);
        if (currentContent) {
            currentContent.classList.add('active');
        }

        // Marcar step atual como ativo
        const currentStepEl = addPostModal.querySelector(`.form-steps .step[data-step="${step}"]`);
        if (currentStepEl) {
            currentStepEl.classList.add('active');
        }

        // Marcar steps anteriores como completados
        for (let i = 1; i < step; i++) {
            const prevStepEl = addPostModal.querySelector(`.form-steps .step[data-step="${i}"]`);
            if (prevStepEl) {
                prevStepEl.classList.add('completed');
            }
        }

        // Controlar visibilidade dos botões
        if (step === 1) {
            prevBtn.style.display = 'none';
        } else {
            prevBtn.style.display = 'inline-flex';
        }

        if (step === totalSteps) {
            nextBtn.style.display = 'none';
            saveBtn.style.display = 'inline-flex';
        } else {
            nextBtn.style.display = 'inline-flex';
            saveBtn.style.display = 'none';
        }

        currentStep = step;
    }

    // Permitir clicar nos números das etapas para navegar
    addPostModal.querySelectorAll('.form-steps .step').forEach(stepEl => {
        stepEl.style.cursor = 'pointer';
        stepEl.addEventListener('click', function() {
            const targetStep = parseInt(this.getAttribute('data-step'));
            if (targetStep && targetStep >= 1 && targetStep <= totalSteps) {
                saveDraft();
                showStep(targetStep);
            }
        });
    });

    // Botão Próximo
    nextBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();

        // Permitir navegação sem validação - apenas salvar rascunho
        if (currentStep < totalSteps) {
            saveDraft();
            showStep(currentStep + 1);
        }
    });

    // Botão Anterior
    prevBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();

        if (currentStep > 1) {
            saveDraft();
            showStep(currentStep - 1);
        }
    });

    // Botão Salvar (submeter formulário) - VALIDAÇÃO APENAS AQUI
    saveBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();

        if (saveBtn.disabled) {
            return;
        }

        syncRichEditorContent();
        collectDownloadData();

        // Validar TODOS os steps antes de salvar
        const validationResult = validateAllSteps();
        if (validationResult.isValid) {
            // Submeter o formulário
            if (addPostForm) {
                setSubmitState(true);
                clearDraft(); // Limpar rascunho antes de enviar
                try {
                    if (typeof addPostForm.requestSubmit === 'function') {
                        addPostForm.requestSubmit();
                    } else {
                        addPostForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                    }
                } catch (error) {
                    setSubmitState(false);
                    throw error;
                }
            }
        } else {
            if (validationResult.firstInvalidStep) {
                showStep(validationResult.firstInvalidStep);
            }

            scrollToFirstInvalidField();

            if (typeof showNotification !== 'undefined') {
                showNotification(validationResult.message || 'Revise os campos obrigatórios antes de concluir.', 'warning');
            } else {
                alert(validationResult.message || 'Revise os campos obrigatórios antes de concluir.');
            }
        }
    });

    // Validar todos os steps
    function validateAllSteps() {
        let firstInvalidStep = null;

        for (let step = 1; step <= totalSteps; step++) {
            if (!validateStep(step, { ignoreWizardVisibility: true }) && firstInvalidStep === null) {
                firstInvalidStep = step;
            }
        }

        return {
            isValid: firstInvalidStep === null,
            firstInvalidStep,
            message: buildValidationMessage()
        };
    }

    function getFieldLabel(field) {
        if (!field) return '';

        if (field === richEditor || field === hiddenTextarea || field.id === 'postContent') {
            return 'Descrição Completa';
        }

        if (field.classList.contains('download-size-input')) {
            return 'Tamanho do download';
        }

        if (field.matches('input[type="url"][name^="download_url_"]')) {
            return 'Link de Download';
        }

        const fieldId = field.getAttribute('id');
        const label = fieldId ? addPostModal.querySelector(`label[for="${fieldId}"]`) : null;
        if (label) {
            return label.textContent.replace('*', '').replace(/\s+/g, ' ').trim();
        }

        const groupLabel = field.closest('.form-group')?.querySelector('.form-label');
        if (groupLabel) {
            return groupLabel.textContent.replace('*', '').replace(/\s+/g, ' ').trim();
        }

        return field.getAttribute('name') || 'Campo';
    }

    function buildValidationMessage() {
        const labels = [];
        const seenLabels = new Set();

        addPostModal.querySelectorAll('.is-invalid').forEach((field) => {
            const label = getFieldLabel(field);
            const key = label.toLowerCase();

            if (label && !seenLabels.has(key)) {
                labels.push(label);
                seenLabels.add(key);
            }
        });

        return labels.length
            ? `Campos pendentes: ${labels.join(', ')}.`
            : 'Revise os campos obrigatórios.';
    }

    // Validação de cada step
    function validateStep(step, options = {}) {
        const currentContent = addPostModal.querySelector(`.step-content[data-step="${step}"]`);

        if (!currentContent) {
            return true;
        }

        let isValid = true;
        const fields = currentContent.querySelectorAll(VALIDATABLE_FIELDS_SELECTOR);

        if (step === 1 && !validateRichEditor()) {
            isValid = false;
        }

        fields.forEach(field => {
            if (!validateField(field, options)) {
                isValid = false;
            }
        });

        return isValid;
    }

    // Função para rolar até o primeiro campo inválido
    function scrollToFirstInvalidField() {
        const firstInvalid = addPostModal.querySelector('.step-content.active .is-invalid');
        if (firstInvalid) {
            firstInvalid.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
            if (typeof firstInvalid.focus === 'function') {
                firstInvalid.focus();
            }
        }
    }

    // Funções de Rascunho
    function saveDraft() {
        const formData = {
            title: document.getElementById('postTitle')?.value || '',
            content: document.getElementById('postContent')?.value || '',
            category: document.getElementById('postCategory')?.value || ''
        };
        localStorage.setItem('postDraft', JSON.stringify(formData));
    }

    function loadDraft() {
        const draft = localStorage.getItem('postDraft');
        if (draft) {
            try {
                const formData = JSON.parse(draft);
                if (document.getElementById('postTitle')) {
                    document.getElementById('postTitle').value = formData.title || '';
                }
                if (document.getElementById('postContent')) {
                    document.getElementById('postContent').value = formData.content || '';
                    if (document.getElementById('postContentEditor')) {
                        document.getElementById('postContentEditor').innerHTML = formData.content || '';
                    }
                }
                if (document.getElementById('postCategory')) {
                    document.getElementById('postCategory').value = formData.category || '';
                }
                return true;
            } catch (e) {
                console.error('Erro ao carregar rascunho:', e);
            }
        }
        return false;
    }

    function clearDraft() {
        localStorage.removeItem('postDraft');
    }

    function resetForm() {
        if (addPostForm) {
            addPostForm.reset();
            addPostForm.querySelectorAll('.is-invalid, .is-valid').forEach(field => {
                field.classList.remove('is-invalid', 'is-valid');
            });

            if (richEditor) {
                richEditor.innerHTML = '';
            }

            if (hiddenTextarea) {
                hiddenTextarea.value = '';
            }

            const downloadFilesData = document.getElementById('downloadFilesData');
            const downloadLinkField = document.getElementById('postDownloadLink');

            if (downloadFilesData) {
                downloadFilesData.value = '';
            }

            if (downloadLinkField) {
                downloadLinkField.value = '';
            }
        }

        setSubmitState(false);
    }

    // Sincronizar editor rich text com textarea oculto
    if (richEditor && hiddenTextarea) {
        richEditor.addEventListener('input', function() {
            syncRichEditorContent();
            richEditor.classList.remove('is-invalid');
            hiddenTextarea.classList.remove('is-invalid');
        });

        richEditor.addEventListener('paste', function() {
            setTimeout(() => {
                syncRichEditorContent();
                richEditor.classList.remove('is-invalid');
                hiddenTextarea.classList.remove('is-invalid');
            }, 100);
        });
    }

    addPostModal.addEventListener('input', function(event) {
        const target = event.target;

        if (!(target instanceof HTMLElement)) {
            return;
        }

        if (target.classList.contains('download-size-input')) {
            const normalizedValue = normalizeDownloadSizeValue(target.value);
            if (normalizedValue !== null) {
                clearFieldInvalid(target);
            }
            return;
        }

        if (target.matches(VALIDATABLE_FIELDS_SELECTOR) && target.checkValidity()) {
            clearFieldInvalid(target);
        }
    }, true);

    addPostModal.addEventListener('focusout', function(event) {
        const target = event.target;
        if (!(target instanceof HTMLElement) || !target.classList.contains('download-size-input')) {
            return;
        }

        const normalizedValue = normalizeDownloadSizeValue(target.value);
        if (normalizedValue) {
            target.value = normalizedValue;
            clearFieldInvalid(target);
        }
    }, true);

    // Resetar wizard ao abrir modal
    if (addPostModal) {
        addPostModal.addEventListener('show', function() {
            resetForm();
            showStep(1);

            const hasDraft = loadDraft();
            initIconSelects(addPostModal);
            refreshDownloadTypeSelects();
            if (typeof window.refreshIconSelects === 'function') {
                window.refreshIconSelects();
            }
            if (hasDraft && typeof showNotification !== 'undefined') {
                showNotification('Rascunho carregado automaticamente', 'info');
            }
        });
    }

    // Limpar rascunho ao submeter formulário
    if (addPostForm) {
        addPostForm.addEventListener('submit', function() {
            clearDraft();
        });

        addPostForm.addEventListener('post:create:complete', function() {
            setSubmitState(false);
        });
    }

    // Inicializar no step 1
    initIconSelects(document);
    if (document.body.dataset.iconSelectOutsideBound !== 'true') {
        document.body.dataset.iconSelectOutsideBound = 'true';
        document.addEventListener('click', (event) => {
            if (event.target.closest('[data-icon-select]')) {
                return;
            }

            document.querySelectorAll('[data-icon-select].open').forEach((wrapper) => {
                wrapper.classList.remove('open');
                wrapper.querySelector('.icon-select-trigger')?.setAttribute('aria-expanded', 'false');
            });
        });
    }
    initDownloadTypesManager();
    refreshDownloadTypeSelects();
    showStep(1);

    // ==========================================
    // MULTI-DOWNLOAD ENTRIES
    // ==========================================
    let downloadEntryIndex = 1;
    const container = document.getElementById('downloadLinksContainer');
    const addBtn = document.getElementById('addDownloadEntry');

    if (addBtn && container) {
        addBtn.addEventListener('click', function() {
            const idx = downloadEntryIndex++;
            const entry = document.createElement('div');
            entry.className = 'download-entry';
            entry.setAttribute('data-index', idx);
            entry.innerHTML = `
                <div class="download-entry-row">
                    <select name="download_type_${idx}" class="form-select download-type-select">
                        ${renderDownloadTypeOptions()}
                    </select>
                    <div class="input-group download-url-group">
                        <input type="url" name="download_url_${idx}"
                               class="form-control modern-input"
                               placeholder="https://exemplo.com/arquivo.zip"
                               required>
                        <button type="button" class="btn-group-item validate-link-btn" title="Validar Link">
                            <i class="fas fa-check"></i>
                        </button>
                    </div>
                    <button type="button" class="btn btn-sm remove-download-entry" title="Remover"
                            style="background: rgba(220,53,69,0.1); color: #dc3545; border: 1px solid #dc3545; border-radius: 6px; padding: 6px 10px; cursor: pointer; flex-shrink: 0;">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div class="download-size-row">
                    <input type="text" name="download_size_${idx}" class="form-control modern-input download-size-input" placeholder="Tamanho" inputmode="decimal" autocomplete="off">
                    <select name="download_size_unit_${idx}" class="form-select download-size-unit">
                        <option value="MB">MB</option>
                        <option value="GB">GB</option>
                        <option value="KB">KB</option>
                    </select>
                </div>
            `;
            container.appendChild(entry);

            // bind remove
            entry.querySelector('.remove-download-entry').addEventListener('click', function() {
                entry.remove();
            });

            // bind validate
            entry.querySelector('.validate-link-btn').addEventListener('click', function() {
                const urlInput = entry.querySelector('input[type="url"]');
                if (urlInput && urlInput.value) {
                    validateDownloadLink(urlInput, this);
                }
            });
        });
    }

    // Bind validate buttons on initial entry
    container?.querySelectorAll('.validate-link-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const urlInput = btn.closest('.download-entry')?.querySelector('input[type="url"]');
            if (urlInput && urlInput.value) {
                validateDownloadLink(urlInput, btn);
            }
        });
    });

    function validateDownloadLink(urlInput, btn) {
        try {
            new URL(urlInput.value);
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            setTimeout(function() {
                btn.innerHTML = '<i class="fas fa-check" style="color: #28a745;"></i>';
                urlInput.classList.remove('is-invalid');
                urlInput.classList.add('is-valid');
            }, 800);
        } catch(e) {
            btn.innerHTML = '<i class="fas fa-times" style="color: #dc3545;"></i>';
            urlInput.classList.add('is-invalid');
            urlInput.classList.remove('is-valid');
        }
    }

    function collectDownloadData() {
        const entries = document.querySelectorAll('#downloadLinksContainer .download-entry');
        const files = [];
        entries.forEach(function(entry) {
            const typeSelect = entry.querySelector('select');
            const urlInput = entry.querySelector('input[type="url"]');
            if (typeSelect && urlInput && urlInput.value.trim()) {
                const sizeInput = entry.querySelector('.download-size-input');
                const unitSelect = entry.querySelectorAll('select')[1];
                let size = '';
                if (sizeInput) {
                    const normalizedSize = normalizeDownloadSizeValue(sizeInput.value);
                    if (normalizedSize) {
                        sizeInput.value = normalizedSize;
                    }
                }

                if (sizeInput && sizeInput.value) {
                    const unit = unitSelect ? unitSelect.value : 'MB';
                    size = sizeInput.value + ' ' + unit;
                }
                files.push({
                    type: typeSelect.value,
                    url: urlInput.value.trim(),
                    size: size
                });
            }
        });

        // Set hidden fields
        const downloadFilesData = document.getElementById('downloadFilesData');
        const downloadLinkField = document.getElementById('postDownloadLink');
        if (downloadFilesData) {
            downloadFilesData.value = JSON.stringify(files);
        }
        if (downloadLinkField) {
            downloadLinkField.value = files.length > 0 ? files[0].url : '';
        }
    }

    window.adminDownloadTypes = downloadTypes;
    window.renderDownloadTypeOptions = renderDownloadTypeOptions;
    window.refreshDownloadTypeSelects = refreshDownloadTypeSelects;
    window.initializeIconSelects = initIconSelects;
    window.refreshIconSelects = function () {
        initIconSelects(document);
        document.querySelectorAll('[data-icon-select]').forEach(syncIconSelect);
    };
}

window.initPostWizard = initPostWizard;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPostWizard);
} else {
    initPostWizard();
}

document.addEventListener('adminPageLoaded', initPostWizard);
