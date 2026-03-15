// ==========================================
// MODAL DE CONTRIBUICAO
// ==========================================

(function() {
    if (window.ContributeModal && typeof window.ContributeModal.init === 'function') {
        window.ContributeModal.init();
        return;
    }

    function isAuthenticated() {
        return document.body.dataset.authenticated === 'true';
    }

    function getLoginRedirectUrl() {
        const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        return `/login?next=${encodeURIComponent(next || '/')}`;
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function showFeedback(widget, message, type) {
        const feedback = widget?.querySelector('[data-donation-feedback]');
        if (!feedback) return;
        feedback.hidden = false;
        feedback.classList.remove('is-error', 'is-success');
        if (type === 'error') feedback.classList.add('is-error');
        if (type === 'success') feedback.classList.add('is-success');
        feedback.textContent = message;
    }

    function clearFeedback(widget) {
        const feedback = widget?.querySelector('[data-donation-feedback]');
        if (!feedback) return;
        feedback.hidden = true;
        feedback.textContent = '';
        feedback.classList.remove('is-error', 'is-success');
    }

    function setDonationBusy(widget, busy) {
        widget?.querySelectorAll('[data-donation-method]').forEach((button) => {
            button.disabled = busy;
            if (busy) {
                button.dataset.originalHtml = button.dataset.originalHtml || button.innerHTML;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
            } else if (button.dataset.originalHtml) {
                button.innerHTML = button.dataset.originalHtml;
            }
        });
    }

    function parseDonationAmount(widget) {
        const input = widget?.querySelector('[data-donation-amount]');
        const raw = String(input?.value || '').trim().replace(',', '.');
        const amount = Number(raw);

        if (!raw || Number.isNaN(amount)) {
            return { valid: false, message: 'Informe um valor de doacao valido.' };
        }

        if (amount < 5) {
            return { valid: false, message: 'A doacao minima e de R$ 5,00.' };
        }

        return { valid: true, amount: Number(amount.toFixed(2)) };
    }

    async function startDonation(widget, method) {
        clearFeedback(widget);

        if (!isAuthenticated()) {
            window.location.href = getLoginRedirectUrl();
            return;
        }

        const parsed = parseDonationAmount(widget);
        if (!parsed.valid) {
            showFeedback(widget, parsed.message, 'error');
            return;
        }

        const endpoint = method === 'pix'
            ? '/create-donation-pix-checkout'
            : '/create-donation-checkout-session';

        setDonationBusy(widget, true);

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    ...(window.csrfUtils && window.csrfUtils.getCsrfToken
                        ? { 'X-CSRFToken': window.csrfUtils.getCsrfToken() }
                        : {})
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    amount: parsed.amount,
                    next: window.location.pathname
                })
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.error || 'Nao foi possivel iniciar a doacao.');
            }

            if (method === 'pix' && data.redirect_url) {
                showFeedback(widget, 'Gerando checkout PIX...', 'success');
                window.location.href = data.redirect_url;
                return;
            }

            if (method === 'card' && data.url) {
                showFeedback(widget, 'Redirecionando para o checkout seguro...', 'success');
                window.location.href = data.url;
                return;
            }

            throw new Error('Resposta de pagamento incompleta.');
        } catch (error) {
            console.error('Erro ao iniciar doacao:', error);
            showFeedback(widget, error.message || 'Nao foi possivel iniciar a doacao.', 'error');
        } finally {
            setDonationBusy(widget, false);
        }
    }

    function initDonationWidgets(root) {
        const widgets = (root || document).querySelectorAll('[data-donation-widget]');
        widgets.forEach((widget) => {
            if (widget.dataset.donationInit === 'true') {
                return;
            }
            widget.dataset.donationInit = 'true';

            widget.querySelectorAll('[data-donation-preset]').forEach((button) => {
                button.addEventListener('click', () => {
                    const amount = button.dataset.donationPreset || '';
                    const input = widget.querySelector('[data-donation-amount]');
                    if (input) {
                        input.value = amount;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                    widget.querySelectorAll('[data-donation-preset]').forEach((item) => item.classList.remove('active'));
                    button.classList.add('active');
                    clearFeedback(widget);
                });
            });

            const input = widget.querySelector('[data-donation-amount]');
            if (input) {
                input.addEventListener('input', () => {
                    widget.querySelectorAll('[data-donation-preset]').forEach((item) => {
                        item.classList.toggle('active', item.dataset.donationPreset === input.value.trim());
                    });
                    clearFeedback(widget);
                });
            }

            widget.querySelectorAll('[data-donation-method]').forEach((button) => {
                button.addEventListener('click', () => {
                    startDonation(widget, button.dataset.donationMethod);
                });
            });
        });
    }

    function initModal() {
        const modal = document.getElementById('contributeModal');
        const openBtn = document.getElementById('openContributeModal');
        const closeBtn = document.getElementById('closeContributeModal');
        const overlay = modal?.querySelector('.contribute-modal-overlay');

        if (!modal) return;

        function openModal(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function closeModal() {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }

        if (openBtn && !openBtn.hasAttribute('data-modal-init')) {
            openBtn.setAttribute('data-modal-init', 'true');
            openBtn.addEventListener('click', openModal);
        }

        if (closeBtn && !closeBtn.hasAttribute('data-modal-init')) {
            closeBtn.setAttribute('data-modal-init', 'true');
            closeBtn.addEventListener('click', closeModal);
        }

        if (overlay && !overlay.hasAttribute('data-modal-init')) {
            overlay.setAttribute('data-modal-init', 'true');
            overlay.addEventListener('click', closeModal);
        }

        if (!window._contributeModalEscHandler) {
            window._contributeModalEscHandler = function(e) {
                if (e.key === 'Escape') {
                    const activeModal = document.getElementById('contributeModal');
                    if (activeModal?.classList.contains('active')) {
                        activeModal.classList.remove('active');
                        document.body.style.overflow = '';
                    }
                }
            };
            document.addEventListener('keydown', window._contributeModalEscHandler);
        }

        const modalLinks = modal.querySelectorAll('a[href]');
        modalLinks.forEach((link) => {
            if (!link.hasAttribute('data-modal-link-init')) {
                link.setAttribute('data-modal-link-init', 'true');
                link.addEventListener('click', function() {
                    document.body.style.overflow = '';
                    modal.classList.remove('active');
                });
            }
        });

        initDonationWidgets(modal);
    }

    window.ContributeModal = {
        init: initModal,
        showFeedback: (widget, message, type) => showFeedback(widget, escapeHtml(message), type)
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initModal);
    } else {
        initModal();
    }

    document.addEventListener('pageLoaded', initModal);
})();
