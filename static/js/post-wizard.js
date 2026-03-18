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
    const saveBtnDefaultHtml = saveBtn ? saveBtn.innerHTML : '';

    if (!nextBtn || !prevBtn || !saveBtn) {
        console.error('Botões do wizard não encontrados!');
        return;
    }

    function setSubmitState(isSubmitting) {
        saveBtn.disabled = isSubmitting;
        saveBtn.innerHTML = isSubmitting
            ? '<i class="fas fa-spinner fa-spin"></i> Publicando...'
            : saveBtnDefaultHtml;
    }

    function showStep(step) {
        // Ocultar todos os step-content
        document.querySelectorAll('.step-content').forEach(content => {
            content.classList.remove('active');
        });

        // Remover active de todos os steps
        document.querySelectorAll('.form-steps .step').forEach(stepEl => {
            stepEl.classList.remove('active', 'completed');
        });

        // Mostrar o step atual
        const currentContent = document.querySelector(`.step-content[data-step="${step}"]`);
        if (currentContent) {
            currentContent.classList.add('active');
        }

        // Marcar step atual como ativo
        const currentStepEl = document.querySelector(`.form-steps .step[data-step="${step}"]`);
        if (currentStepEl) {
            currentStepEl.classList.add('active');
        }

        // Marcar steps anteriores como completados
        for (let i = 1; i < step; i++) {
            const prevStepEl = document.querySelector(`.form-steps .step[data-step="${i}"]`);
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
    document.querySelectorAll('.form-steps .step').forEach(stepEl => {
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

        // Validar TODOS os steps antes de salvar
        if (validateAllSteps()) {
            // Sincronizar editor com textarea antes de enviar
            if (richEditor && hiddenTextarea) {
                hiddenTextarea.value = richEditor.innerHTML;
            }

            // Coletar dados de multi-download antes de submeter
            collectDownloadData();

            // Submeter o formulário
            const form = document.getElementById('addPostForm');
            if (form) {
                setSubmitState(true);
                clearDraft(); // Limpar rascunho antes de enviar
                try {
                    if (typeof form.requestSubmit === 'function') {
                        form.requestSubmit();
                    } else {
                        form.submit();
                    }
                } catch (error) {
                    setSubmitState(false);
                    throw error;
                }
            }
        } else {
            // Ir para o primeiro step com erro
            for (let step = 1; step <= totalSteps; step++) {
                if (!validateStep(step)) {
                    showStep(step);
                    scrollToFirstInvalidField();
                    alert('Por favor, preencha todos os campos obrigatórios antes de concluir.');
                    break;
                }
            }
        }
    });

    // Validar todos os steps
    function validateAllSteps() {
        let allValid = true;
        for (let step = 1; step <= totalSteps; step++) {
            if (!validateStep(step)) {
                allValid = false;
            }
        }
        return allValid;
    }

    // Validação de cada step
    function validateStep(step) {
        const currentContent = document.querySelector(`.step-content[data-step="${step}"]`);

        if (!currentContent) {
            return true;
        }

        const requiredFields = currentContent.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            const isVisible = field.offsetParent !== null;
            const fieldValue = field.value ? field.value.trim() : '';

            if (isVisible) {
                if (!fieldValue) {
                    field.classList.add('is-invalid');
                    isValid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            }
        });

        if (!isValid && typeof showNotification !== 'undefined') {
            showNotification('Por favor, preencha todos os campos obrigatórios.', 'warning');
        }

        return isValid;
    }

    // Função para rolar até o primeiro campo inválido
    function scrollToFirstInvalidField() {
        const firstInvalid = document.querySelector('.step-content.active .is-invalid');
        if (firstInvalid) {
            firstInvalid.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
            firstInvalid.focus();
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
        const form = document.getElementById('addPostForm');
        if (form) {
            form.reset();
            if (richEditor) {
                richEditor.innerHTML = '';
            }
        }
        setSubmitState(false);
    }

    // Sincronizar editor rich text com textarea oculto
    if (richEditor && hiddenTextarea) {
        richEditor.addEventListener('input', function() {
            hiddenTextarea.value = richEditor.innerHTML;
        });

        richEditor.addEventListener('paste', function() {
            setTimeout(() => {
                hiddenTextarea.value = richEditor.innerHTML;
            }, 100);
        });
    }

    // Resetar wizard ao abrir modal
    if (addPostModal) {
        addPostModal.addEventListener('show', function() {
            resetForm();
            showStep(1);

            const hasDraft = loadDraft();
            if (hasDraft && typeof showNotification !== 'undefined') {
                showNotification('Rascunho carregado automaticamente', 'info');
            }
        });
    }

    // Limpar rascunho ao submeter formulário
    const addPostForm = document.getElementById('addPostForm');
    if (addPostForm) {
        addPostForm.addEventListener('submit', function() {
            clearDraft();
        });

        addPostForm.addEventListener('post:create:complete', function() {
            setSubmitState(false);
        });
    }

    // Inicializar no step 1
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
                        <option value="BIOS">BIOS</option>
                        <option value="EC">EC</option>
                        <option value="ME">ME</option>
                        <option value="Outro">Outro</option>
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
                    <input type="number" name="download_size_${idx}" class="form-control modern-input download-size-input" placeholder="Tamanho" step="0.1" min="0">
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
                const sizeInput = entry.querySelector('input[type="number"]');
                const unitSelect = entry.querySelectorAll('select')[1];
                let size = '';
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
        if (downloadLinkField && files.length > 0) {
            downloadLinkField.value = files[0].url;
        }
    }
}

window.initPostWizard = initPostWizard;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPostWizard);
} else {
    initPostWizard();
}

document.addEventListener('adminPageLoaded', initPostWizard);
