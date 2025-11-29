/**
 * Post Wizard - Multi-Step Form for Creating Posts
 * Gerencia o formulário de múltiplas etapas para criar posts
 */

document.addEventListener('DOMContentLoaded', function() {
    // Verificar se o modal existe na página
    const addPostModal = document.getElementById('addPostModal');
    if (!addPostModal) {
        return; // Sair se não houver modal de post na página
    }

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

    if (!nextBtn || !prevBtn || !saveBtn) {
        console.error('Botões do wizard não encontrados!');
        return;
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

    // Botão Próximo
    nextBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();

        if (validateStep(currentStep)) {
            if (currentStep < totalSteps) {
                saveDraft();
                showStep(currentStep + 1);
            }
        } else {
            scrollToFirstInvalidField();
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

    // Botão Salvar (submeter formulário)
    saveBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();

        if (validateStep(currentStep)) {
            // Sincronizar editor com textarea antes de enviar
            if (richEditor && hiddenTextarea) {
                hiddenTextarea.value = richEditor.innerHTML;
            }

            // Submeter o formulário
            const form = document.getElementById('addPostForm');
            if (form) {
                clearDraft(); // Limpar rascunho antes de enviar
                form.submit();
            }
        } else {
            scrollToFirstInvalidField();
        }
    });

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
        addPostForm.addEventListener('submit', function(e) {
            clearDraft();
        });
    }

    // Inicializar no step 1
    showStep(1);
});
