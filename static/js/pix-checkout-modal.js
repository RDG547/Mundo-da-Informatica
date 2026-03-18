(function () {
    if (window.openPixCheckoutModal) {
        return;
    }

    let modalElements = null;
    let modalState = null;

    function getCsrfToken() {
        if (window.csrfUtils && typeof window.csrfUtils.getCsrfToken === 'function') {
            return window.csrfUtils.getCsrfToken();
        }
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }

    function apiHeaders() {
        const headers = {
            'X-Requested-With': 'XMLHttpRequest'
        };
        const csrfToken = getCsrfToken();
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }
        return headers;
    }

    function ensureModal() {
        if (modalElements) {
            return modalElements;
        }

        const overlay = document.createElement('div');
        overlay.className = 'site-pix-overlay';
        overlay.hidden = true;
        overlay.innerHTML = `
            <div class="site-pix-dialog" role="dialog" aria-modal="true" aria-labelledby="sitePixTitle" tabindex="-1">
                <button type="button" class="site-pix-close" aria-label="Fechar modal PIX">
                    <i class="fas fa-times"></i>
                </button>
                <div class="site-pix-shell">
                    <div class="site-pix-header">
                        <h4 id="sitePixTitle">Pagamento via PIX</h4>
                        <p id="sitePixSubtitle">Escaneie o QR Code ou copie o codigo PIX.</p>
                    </div>
                    <div class="site-pix-summary">
                        <div class="site-pix-summary-row">
                            <span id="sitePixItemLabel">Item</span>
                            <strong id="sitePixItemValue">Pagamento</strong>
                        </div>
                        <div class="site-pix-summary-row">
                            <span id="sitePixModeLabel">Modalidade</span>
                            <strong id="sitePixModeValue">Unica</strong>
                        </div>
                        <div class="site-pix-summary-row is-amount">
                            <span>Valor</span>
                            <strong id="sitePixAmount">R$ 0,00</strong>
                        </div>
                    </div>
                    <div class="site-pix-status" id="sitePixStatus">
                        <i class="fas fa-spinner fa-spin"></i>
                        <div>
                            <strong>Preparando pagamento</strong>
                            <p>Estamos gerando o seu QR Code PIX com seguranca.</p>
                        </div>
                    </div>
                    <div class="site-pix-body">
                        <div class="site-pix-qr" id="sitePixQr">
                            <div class="site-pix-loading">
                                <i class="fas fa-spinner fa-spin"></i>
                                <span>Gerando QR Code de pagamento...</span>
                            </div>
                        </div>
                        <div class="site-pix-code-card">
                            <h5>Codigo PIX copia e cola</h5>
                            <div class="site-pix-code-actions">
                                <textarea class="site-pix-code" id="sitePixCode" readonly placeholder="O codigo PIX aparecera aqui."></textarea>
                                <button type="button" class="site-pix-btn is-primary" id="sitePixCopyBtn">Copiar codigo</button>
                            </div>
                        </div>
                        <div class="site-pix-steps">
                            <h5>Como pagar</h5>
                            <ol>
                                <li>Abra o aplicativo do seu banco.</li>
                                <li>Escolha a opcao PIX.</li>
                                <li>Escaneie o QR Code ou use o codigo copia e cola.</li>
                                <li>Confirme o pagamento no app do banco.</li>
                                <li id="sitePixFinalStep">Pronto! A confirmacao sera processada automaticamente.</li>
                            </ol>
                        </div>
                    </div>
                    <div class="site-pix-actions">
                        <button type="button" class="site-pix-btn is-secondary" id="sitePixCloseBtn">Fechar</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const closeButton = overlay.querySelector('.site-pix-close');
        const footerCloseButton = overlay.querySelector('#sitePixCloseBtn');
        const copyButton = overlay.querySelector('#sitePixCopyBtn');

        function closeHandler() {
            closePixCheckoutModal();
        }

        closeButton.addEventListener('click', closeHandler);
        footerCloseButton.addEventListener('click', closeHandler);
        overlay.addEventListener('click', (event) => {
            if (event.target === overlay) {
                closeHandler();
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && modalState) {
                closeHandler();
            }
        });

        copyButton.addEventListener('click', async () => {
            const pixCodeField = overlay.querySelector('#sitePixCode');
            const pixCode = String(pixCodeField.value || '').trim();
            if (!pixCode) {
                if (typeof window.showSiteToast === 'function') {
                    window.showSiteToast('O codigo PIX ainda nao esta disponivel.', 'warning');
                }
                return;
            }

            try {
                await navigator.clipboard.writeText(pixCode);
                const originalLabel = copyButton.textContent;
                copyButton.textContent = 'Codigo copiado';
                if (typeof window.showSiteToast === 'function') {
                    window.showSiteToast('Codigo PIX copiado com sucesso.', 'success');
                }
                window.setTimeout(() => {
                    copyButton.textContent = originalLabel;
                }, 1800);
            } catch (_error) {
                if (typeof window.showSiteToast === 'function') {
                    window.showSiteToast('Nao foi possivel copiar o codigo PIX.', 'danger');
                }
            }
        });

        modalElements = {
            overlay,
            dialog: overlay.querySelector('.site-pix-dialog'),
            title: overlay.querySelector('#sitePixTitle'),
            subtitle: overlay.querySelector('#sitePixSubtitle'),
            itemLabel: overlay.querySelector('#sitePixItemLabel'),
            itemValue: overlay.querySelector('#sitePixItemValue'),
            modeLabel: overlay.querySelector('#sitePixModeLabel'),
            modeValue: overlay.querySelector('#sitePixModeValue'),
            amount: overlay.querySelector('#sitePixAmount'),
            status: overlay.querySelector('#sitePixStatus'),
            qr: overlay.querySelector('#sitePixQr'),
            code: overlay.querySelector('#sitePixCode'),
            finalStep: overlay.querySelector('#sitePixFinalStep')
        };

        return modalElements;
    }

    function setStatus(title, message, type, iconClass) {
        const { status } = ensureModal();
        status.className = 'site-pix-status';
        if (type) {
            status.classList.add(`is-${type}`);
        }
        status.innerHTML = `
            <i class="fas ${iconClass || 'fa-circle-info'}"></i>
            <div>
                <strong>${title}</strong>
                <p>${message}</p>
            </div>
        `;
    }

    function setQrLoading(message) {
        const { qr } = ensureModal();
        qr.innerHTML = `
            <div class="site-pix-loading">
                <i class="fas fa-spinner fa-spin"></i>
                <span>${message || 'Gerando QR Code de pagamento...'}</span>
            </div>
        `;
    }

    function setQrError(message) {
        const { qr } = ensureModal();
        qr.innerHTML = `
            <div class="site-pix-loading">
                <i class="fas fa-triangle-exclamation"></i>
                <span>${message || 'Nao foi possivel gerar o QR Code PIX.'}</span>
            </div>
        `;
    }

    function renderPixData(qrCode, pixCode) {
        const { qr, code } = ensureModal();
        if (qrCode) {
            qr.innerHTML = `<img src="${qrCode}" alt="QR Code PIX">`;
        }
        code.value = String(pixCode || '');
    }

    async function cancelTransaction(billingId) {
        if (!billingId) {
            return;
        }

        try {
            await fetch(`/cancel-pix-transaction/${encodeURIComponent(billingId)}`, {
                method: 'POST',
                headers: apiHeaders(),
                keepalive: true,
                credentials: 'same-origin'
            });
        } catch (_error) {
            // ignore cancellation errors
        }
    }

    function cleanupState({ cancelPending } = { cancelPending: false }) {
        if (!modalState) {
            return;
        }

        if (modalState.poller) {
            clearInterval(modalState.poller);
            modalState.poller = null;
        }

        if (cancelPending && modalState.billingId && !modalState.completed) {
            cancelTransaction(modalState.billingId);
        }

        modalState = null;
    }

    function closePixCheckoutModal({ cancelPending = true } = {}) {
        const elements = ensureModal();
        elements.overlay.classList.remove('is-visible');
        window.setTimeout(() => {
            elements.overlay.hidden = true;
        }, 180);
        document.body.style.removeProperty('overflow');
        cleanupState({ cancelPending });
    }

    async function pollPaymentStatus() {
        if (!modalState || !modalState.billingId) {
            return;
        }

        try {
            const response = await fetch(`/check-pix-payment/${encodeURIComponent(modalState.billingId)}`, {
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(data.error || 'Nao foi possivel verificar o status do pagamento.');
            }

            if (data.paid) {
                modalState.completed = true;
                setStatus('Pagamento confirmado', modalState.successMessage || 'Pagamento confirmado com sucesso.', 'success', 'fa-check-circle');
                if (modalState.successRedirectUrl) {
                    window.setTimeout(() => {
                        window.location.href = modalState.successRedirectUrl;
                    }, 1600);
                }
                cleanupState({ cancelPending: false });
                return;
            }

            if (data.status === 'cancelled') {
                setStatus('Pagamento cancelado', 'O checkout PIX foi cancelado. Se desejar, voce pode iniciar novamente.', 'error', 'fa-xmark-circle');
                cleanupState({ cancelPending: false });
            }
        } catch (error) {
            console.error('[PIX MODAL] Erro ao verificar pagamento:', error);
        }
    }

    async function processPix(billingId) {
        const response = await fetch(`/process-pix-async/${encodeURIComponent(billingId)}`, {
            method: 'POST',
            headers: apiHeaders(),
            credentials: 'same-origin'
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok || data.status === 'error') {
            throw new Error(data.message || data.error || 'Nao foi possivel preparar o pagamento PIX.');
        }

        if (data.qr_code || data.pix_code) {
            renderPixData(data.qr_code, data.pix_code);
        }
    }

    window.openPixCheckoutModal = async function (options = {}) {
        const billingId = String(options.billingId || '').trim();
        if (!billingId) {
            throw new Error('billingId obrigatorio para abrir o modal PIX.');
        }

        if (modalState) {
            closePixCheckoutModal({ cancelPending: false });
        }

        const elements = ensureModal();
        elements.title.textContent = options.title || 'Pagamento via PIX';
        elements.subtitle.textContent = options.subtitle || 'Escaneie o QR Code ou copie o codigo PIX para concluir o pagamento.';
        elements.itemLabel.textContent = options.itemLabel || 'Item';
        elements.itemValue.textContent = options.itemValue || 'Pagamento';
        elements.modeLabel.textContent = options.modeLabel || 'Modalidade';
        elements.modeValue.textContent = options.modeValue || 'Unica';
        elements.amount.textContent = options.amountText || 'R$ 0,00';
        elements.code.value = '';
        elements.finalStep.textContent = options.finalStep || 'Pronto! A confirmacao sera processada automaticamente.';

        modalState = {
            billingId,
            successRedirectUrl: options.successRedirectUrl || '',
            successMessage: options.successMessage || 'Pagamento confirmado com sucesso.',
            completed: false,
            poller: null
        };

        setStatus('Preparando pagamento', 'Estamos gerando o seu QR Code PIX com seguranca.', '', 'fa-spinner fa-spin');
        setQrLoading(options.loadingMessage || 'Gerando QR Code de pagamento...');

        document.body.style.overflow = 'hidden';
        elements.overlay.hidden = false;
        requestAnimationFrame(() => {
            elements.overlay.classList.add('is-visible');
            elements.dialog.focus();
        });

        try {
            await processPix(billingId);
            if (!modalState || modalState.billingId !== billingId) {
                return;
            }

            setStatus('Aguardando pagamento', 'Escaneie o QR Code ou copie o codigo PIX para pagar.', '', 'fa-hourglass-half');
            modalState.poller = window.setInterval(pollPaymentStatus, 5000);
            pollPaymentStatus();
        } catch (error) {
            console.error('[PIX MODAL] Erro ao preparar checkout PIX:', error);
            setStatus('Nao foi possivel iniciar o PIX', error.message || 'Tente novamente em alguns instantes.', 'error', 'fa-triangle-exclamation');
            setQrError(error.message || 'Nao foi possivel gerar o QR Code PIX.');
        }
    };
})();
