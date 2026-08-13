// ==========================================
// CONTACT PAGE
// ==========================================

(function () {
    if (window.ContactPage && typeof window.ContactPage.init === 'function') {
        window.ContactPage.init();
        return;
    }

    const SUPPORT_EMAIL = 'suporte@mundodainformatica.com';
    const MAX_MESSAGE_LENGTH = 5000;

    function showMessage(message, type) {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type || 'success');
            return;
        }
        window.alert(message);
    }

    function getHeaderOffset() {
        const header = document.querySelector('header');
        const headerHeight = header ? Math.ceil(header.getBoundingClientRect().height) : 70;
        return headerHeight + 16;
    }

    function scrollToElement(target) {
        if (!target) return;
        const top = target.getBoundingClientRect().top + window.scrollY - getHeaderOffset();
        window.scrollTo({
            top: Math.max(top, 0),
            behavior: 'smooth'
        });
    }

    function updateCharCounter() {
        const messageTextarea = document.getElementById('message');
        const charCount = document.getElementById('char-count');
        if (!messageTextarea || !charCount || messageTextarea.dataset.charCounterInit === 'true') {
            return;
        }

        messageTextarea.dataset.charCounterInit = 'true';

        const syncCount = function () {
            if (messageTextarea.value.length > MAX_MESSAGE_LENGTH) {
                messageTextarea.value = messageTextarea.value.slice(0, MAX_MESSAGE_LENGTH);
            }

            const currentLength = messageTextarea.value.length;
            charCount.textContent = String(currentLength);

            if (currentLength > 4500) {
                charCount.style.color = '#dc3545';
            } else if (currentLength > 3500) {
                charCount.style.color = '#f59e0b';
            } else {
                charCount.style.color = '#666';
            }
        };

        messageTextarea.addEventListener('input', syncCount);
        syncCount();
    }

    function updateAttachmentsSummary(input) {
        const summary = document.getElementById('attachments-summary');
        if (!summary || !input) return;

        const files = Array.from(input.files || []);
        if (!files.length) {
            summary.textContent = 'Nenhum arquivo selecionado.';
            return;
        }

        summary.textContent = files.map((file) => file.name).join(', ');
    }

    function formatPhoneValue(rawValue) {
        const digits = String(rawValue || '').replace(/\D/g, '').slice(0, 11);

        if (!digits) {
            return '';
        }

        if (digits.length <= 2) {
            return `(${digits}`;
        }

        if (digits.length <= 6) {
            return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
        }

        if (digits.length <= 10) {
            return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
        }

        return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
    }

    function restoreContactDefaults(form) {
        if (!form) return;

        form.querySelectorAll('[data-contact-default]').forEach((field) => {
            field.value = field.dataset.contactDefault || '';
        });

        const phoneField = form.querySelector('#phone');
        if (phoneField) {
            phoneField.value = formatPhoneValue(phoneField.value);
        }
    }

    function bindFieldMasks(form) {
        if (!form || form.dataset.fieldMasksInit === 'true') {
            return;
        }

        form.dataset.fieldMasksInit = 'true';

        const phoneField = form.querySelector('#phone');
        if (phoneField) {
            const syncPhone = function () {
                phoneField.value = formatPhoneValue(phoneField.value);
            };

            phoneField.addEventListener('input', syncPhone);
            phoneField.addEventListener('blur', syncPhone);
            syncPhone();
        }

        const emailField = form.querySelector('#email');
        if (emailField) {
            const sanitizeEmail = function () {
                emailField.value = emailField.value.replace(/\s+/g, '').toLowerCase();
            };

            emailField.addEventListener('input', sanitizeEmail);
            emailField.addEventListener('blur', sanitizeEmail);
            sanitizeEmail();
        }

        form.addEventListener('reset', function () {
            window.setTimeout(function () {
                restoreContactDefaults(form);
                const charCount = document.getElementById('char-count');
                if (charCount) {
                    charCount.textContent = '0';
                    charCount.style.color = '#666';
                }
            }, 0);
        });
    }

    function bindCoverageModal() {
        const modal = document.getElementById('coverageModal');
        if (!modal || modal.dataset.coverageInit === 'true') {
            return;
        }

        modal.dataset.coverageInit = 'true';

        const closeModal = function () {
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        };

        const openModal = function () {
            modal.classList.add('active');
            modal.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
        };

        modal.querySelectorAll('[data-coverage-close]').forEach((element) => {
            element.addEventListener('click', closeModal);
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
        });

        window.ContactPage = window.ContactPage || {};
        window.ContactPage.openCoverageModal = openModal;
        window.ContactPage.closeCoverageModal = closeModal;
    }

    function bindContactForm() {
        const contactForm = document.getElementById('contact-form');
        if (!contactForm || contactForm.dataset.contactInit === 'true') {
            return;
        }

        contactForm.dataset.contactInit = 'true';
        bindFieldMasks(contactForm);

        const attachmentsInput = document.getElementById('attachments');
        if (attachmentsInput && attachmentsInput.dataset.attachmentsInit !== 'true') {
            attachmentsInput.dataset.attachmentsInit = 'true';
            attachmentsInput.addEventListener('change', function () {
                updateAttachmentsSummary(this);
            });
            updateAttachmentsSummary(attachmentsInput);
        }

        contactForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const submitBtn = contactForm.querySelector('button[type="submit"]');
            const originalLabel = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
            }

            try {
                const response = await fetch(contactForm.action || window.location.pathname, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: new FormData(contactForm)
                });

                const data = await response.json().catch(() => ({}));

                if (data.requires_login) {
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else {
                        showMessage(data.message || 'Entre na sua conta para continuar.', 'warning');
                    }
                    return;
                }

                if (data.requires_upgrade) {
                    if (typeof window.showContentRequestModal === 'function') {
                        window.showContentRequestModal(data.message);
                    } else if (typeof window.showDownloadLimitModal === 'function') {
                        window.showDownloadLimitModal(data.message);
                    } else {
                        showMessage(data.message || 'Esse recurso requer upgrade de plano.', 'warning');
                    }
                    return;
                }

                if (!response.ok) {
                    if (response.status === 413) {
                        throw new Error('Os anexos excederam o limite permitido de tamanho.');
                    }
                    throw new Error(data.message || 'Erro ao enviar mensagem. Tente novamente.');
                }

                showMessage(data.message || `Sua mensagem foi enviada com sucesso para ${SUPPORT_EMAIL}!`, 'success');
                contactForm.reset();
                restoreContactDefaults(contactForm);

                const attachmentsField = document.getElementById('attachments');
                if (attachmentsField) {
                    updateAttachmentsSummary(attachmentsField);
                }

                const charCount = document.getElementById('char-count');
                if (charCount) {
                    charCount.textContent = '0';
                    charCount.style.color = '#666';
                }
            } catch (error) {
                console.error('Erro ao enviar contato:', error);
                showMessage(error.message || 'Erro ao enviar mensagem. Tente novamente.', 'error');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalLabel;
                }
            }
        });
    }

    function scrollToHashTarget() {
        if (!window.location.hash) {
            return;
        }

        const target = document.querySelector(window.location.hash);
        if (!target) {
            return;
        }

        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () {
                scrollToElement(target);
            });
        });
    }

    function init() {
        updateCharCounter();
        bindCoverageModal();
        bindContactForm();
        scrollToHashTarget();
    }

    window.ContactPage = window.ContactPage || {};
    window.ContactPage.init = init;
    window.ContactPage.scrollToHashTarget = scrollToHashTarget;

    window.showCoverageMap = function () {
        if (window.ContactPage && typeof window.ContactPage.openCoverageModal === 'function') {
            window.ContactPage.openCoverageModal();
            return;
        }

        window.alert('Nossa cobertura abrange todo o território nacional através da internet. Atendemos clientes de qualquer estado do Brasil!');
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    document.addEventListener('contentLoaded', init);
    document.addEventListener('pageLoaded', init);
})();
