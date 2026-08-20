/**
 * Plans Page Functionality
 * Handles Stripe checkout, downgrade modal, and FAQ interactions.
 */

window.initializePlansPage = function () {
    const plansContainer = document.querySelector('.plans-section');
    if (!plansContainer) return;

    // Prevenir inicialização duplicada
    if (window.plansPageInitialized) {
        return;
    }
    window.plansPageInitialized = true;

    const stripePublicKey = plansContainer.dataset.stripeKey;
    const checkoutPlan = plansContainer.dataset.checkoutPlan;
    let stripe = null;
    let stripeInitialized = false;

    const isPlanAvailable = (plan) => {
        const normalizedPlan = String(plan || '').trim().toLowerCase();
        const card = document.querySelector(`[data-plan-card="${normalizedPlan}"]`);
        if (card) return card.dataset.planEnabled !== 'false';
        return window.planAvailability?.[normalizedPlan] !== false;
    };

    const ensurePlanAvailable = (plan) => {
        if (isPlanAvailable(plan)) return true;
        alert('Este plano está temporariamente indisponível. Escolha outra opção.');
        return false;
    };

    const normalizePaymentMethod = (method) => method === 'credit_card' ? 'card' : String(method || '');

    const isPaymentMethodAvailable = (plan, method) => {
        const normalizedPlan = String(plan || '').trim().toLowerCase();
        const normalizedMethod = normalizePaymentMethod(method);
        const card = document.querySelector(`[data-plan-card="${normalizedPlan}"]`);
        const datasetKey = normalizedMethod === 'card' ? 'planCardEnabled' : 'planPixEnabled';
        if (card && card.dataset[datasetKey]) {
            return card.dataset[datasetKey] !== 'false';
        }
        return window.planPaymentAvailability?.[normalizedPlan]?.[normalizedMethod] !== false;
    };

    const getPlanDisplayName = (plan) => {
        const normalizedPlan = String(plan || '').trim().toLowerCase();
        return document.querySelector(`[data-plan-card="${normalizedPlan}"] [data-plan-name="${normalizedPlan}"]`)
            ?.textContent.trim() || normalizedPlan.toUpperCase();
    };

    // Function to initialize Stripe when ready
    const initializeStripe = () => {
        // Evitar múltiplas inicializações
        if (stripeInitialized) {
            return;
        }

        if (stripePublicKey && stripePublicKey !== 'None') {
            try {
                if (typeof Stripe !== 'undefined') {
                    stripe = Stripe(stripePublicKey);
                    stripeInitialized = true;
                } else {
                    console.error('Stripe.js not loaded');
                }
            } catch (e) {
                console.error('Error initializing Stripe:', e);
            }
        }
    };

    // Wait for Stripe.js to load if not already loaded
    if (typeof Stripe === 'undefined') {
        // Load Stripe.js dynamically if not present
        if (!document.querySelector('script[src*="stripe.com"]')) {
            const stripeScript = document.createElement('script');
            stripeScript.src = 'https://js.stripe.com/v3/';
            stripeScript.onload = initializeStripe;
            stripeScript.onerror = () => {
                console.error('Failed to load Stripe.js');
            };
            document.head.appendChild(stripeScript);
        } else {
            // Script is loading, wait for it
            let checkStripe;
            let timeoutId;

            checkStripe = setInterval(() => {
                if (typeof Stripe !== 'undefined') {
                    clearInterval(checkStripe);
                    clearTimeout(timeoutId);
                    initializeStripe();
                }
            }, 100);

            // Timeout after 5 seconds
            timeoutId = setTimeout(() => {
                clearInterval(checkStripe);
                if (typeof Stripe === 'undefined') {
                    console.error('Stripe.js loading timeout');
                }
            }, 5000);
        }
    } else {
        // Stripe is already loaded
        initializeStripe();
    }

    // Checkout Function
    // Checkout Function
    window.checkout = function (plan) {
        if (!ensurePlanAvailable(plan)) return;
        if (!isPaymentMethodAvailable(plan, 'card')) {
            alert('A assinatura por cartão está temporariamente indisponível para este plano.');
            return;
        }
        if (!stripe) {
            alert('Erro: Configuração de pagamento não encontrada. Por favor, contate o suporte.');
            console.error('Stripe public key is missing');
            return;
        }

        fetch('/create-checkout-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                plan: plan
            }),
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (session) {
                if (session.error) {
                    alert(session.error);
                } else if (session.clientSecret) {
                    // Initialize Embedded Checkout
                    stripe.initEmbeddedCheckout({
                        clientSecret: session.clientSecret
                    }).then(function (checkout) {
                        // Open Modal
                        const modal = document.getElementById('stripeEmbeddedCheckoutModal');
                        if (modal) {
                            modal.style.display = 'flex';
                            document.body.style.overflow = 'hidden';

                            // Mount Checkout
                            checkout.mount('#checkout-element');

                            // Save instance for cleanup
                            window.currentStripeCheckout = checkout;
                        }
                    });
                } else {
                    alert('Erro inesperado: Sessão inválida.');
                }
            })
            .catch(function (error) {
                console.error('Error:', error);
                alert('Erro ao iniciar pagamento. Tente novamente.');
            });
    };

    window.closeStripeEmbeddedModal = function () {
        const modal = document.getElementById('stripeEmbeddedCheckoutModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';

            // Unmount and destroy checkout instance if exists
            if (window.currentStripeCheckout) {
                window.currentStripeCheckout.destroy();
                window.currentStripeCheckout = null;
            }
        }
    };

    // Payment Method Modal
    let paymentMethodModal = null;
    let selectedPlan = null;

    function syncPaymentMethodModal(plan) {
        if (!paymentMethodModal) return false;
        const normalizedPlan = String(plan || '').trim().toLowerCase();
        const planName = getPlanDisplayName(normalizedPlan);
        const selectedPlanName = paymentMethodModal.querySelector('[data-selected-plan-name]');
        if (selectedPlanName) selectedPlanName.textContent = planName;

        let availableCount = 0;
        paymentMethodModal.querySelectorAll('[data-payment-method]').forEach((methodCard) => {
            const method = methodCard.dataset.paymentMethod;
            const isAvailable = isPaymentMethodAvailable(normalizedPlan, method);
            methodCard.disabled = !isAvailable;
            methodCard.classList.toggle('is-disabled', !isAvailable);
            methodCard.setAttribute('aria-disabled', isAvailable ? 'false' : 'true');
            const unavailableLabel = methodCard.querySelector('.payment-unavailable');
            if (unavailableLabel) unavailableLabel.hidden = isAvailable;
            if (isAvailable) availableCount += 1;
        });
        return availableCount > 0;
    }
    window.syncPlanPaymentMethodModal = syncPaymentMethodModal;

    window.showPaymentMethodModal = function (plan) {
        if (!ensurePlanAvailable(plan)) return;
        selectedPlan = plan;
        if (!paymentMethodModal) {
            paymentMethodModal = document.getElementById('paymentMethodModal');
        }
        if (paymentMethodModal) {
            if (!syncPaymentMethodModal(plan)) {
                selectedPlan = null;
                alert('As formas de pagamento deste plano estão temporariamente indisponíveis.');
                return;
            }
            paymentMethodModal.style.display = "flex";
            document.body.style.overflow = "hidden";
        }
    };

    window.closePaymentMethodModal = function () {
        if (paymentMethodModal) {
            paymentMethodModal.style.display = "none";
            document.body.style.overflow = "auto";
        }
        // Não limpar selectedPlan aqui - será limpo após o pagamento
    };

    window.selectPaymentMethod = function (method) {
        if (!selectedPlan) {
            console.error('Nenhum plano selecionado');
            alert('Erro: Nenhum plano selecionado. Por favor, tente novamente.');
            return;
        }

        if (!isPaymentMethodAvailable(selectedPlan, method)) {
            alert('Esta forma de pagamento está temporariamente indisponível para o plano selecionado.');
            syncPaymentMethodModal(selectedPlan);
            return;
        }

        // Salvar o plano antes de fechar o modal
        const planToCheckout = selectedPlan;

        // Analytics de checkout sem dados pessoais.
        const amountElement = document.querySelector(`.plan-card.${planToCheckout} .plan-price .amount`);
        const amountValue = amountElement
            ? parseFloat(amountElement.textContent.trim().replace(/\./g, '').replace(',', '.'))
            : NaN;
        if (!isNaN(amountValue)) {
            if (typeof fbq === 'function') {
                fbq('track', 'InitiateCheckout', {value: amountValue, currency: 'BRL', content_name: planToCheckout});
            }
            if (typeof gtag === 'function') {
                gtag('event', 'begin_checkout', {
                    currency: 'BRL',
                    value: amountValue,
                    items: [{item_id: planToCheckout, item_name: planToCheckout}]
                });
            }
        }

        window.closePaymentMethodModal();

        if (method === 'credit_card') {
            // Prosseguir com Stripe
            window.checkout(planToCheckout);
        } else if (method === 'pix') {
            // Prosseguir com Abacate Pay (PIX)
            checkoutPix(planToCheckout);
        }

        // Limpar após iniciar o checkout
        selectedPlan = null;
    };

    function checkoutPix(plan) {
        if (!ensurePlanAvailable(plan)) return;
        if (!isPaymentMethodAvailable(plan, 'pix')) {
            alert('O pagamento via PIX está temporariamente indisponível para este plano.');
            return;
        }
        const payload = { plan: plan };

        fetch('/create-pix-checkout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        })
            .then(response => response.json())
            .then(data => {
                const planDetails = getPlanPixDetails(plan);

                if (data.billing_id && typeof window.openPixCheckoutModal === 'function') {
                    window.openPixCheckoutModal({
                        billingId: data.billing_id,
                        itemLabel: 'Plano',
                        itemValue: planDetails.label,
                        modeLabel: 'Periodo',
                        modeValue: 'Mensal',
                        amountText: planDetails.amountText,
                        successMessage: `Pagamento confirmado. O ${planDetails.label} sera ativado automaticamente.`,
                        successRedirectUrl: data.success_redirect_url || `/pix-checkout-success?billing_id=${encodeURIComponent(data.billing_id)}&next=${encodeURIComponent('/planos')}`
                    });
                } else if (data.billing_id) {
                    alert('O modal PIX não pôde ser carregado. Atualize a página e tente novamente.');
                } else if (data.error && typeof data.error === 'string') {
                    alert(data.error);
                } else {
                    alert('Erro ao criar pagamento PIX. Por favor, tente novamente.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Erro ao criar pagamento PIX. Por favor, tente novamente.');
            });
    }

    function getPlanPixDetails(plan) {
        const normalizedPlan = String(plan || '').trim().toLowerCase();
        const amountElement = document.querySelector(`.plan-card.${normalizedPlan} .plan-price .amount`);
        const amountText = amountElement ? `R$ ${amountElement.textContent.trim()}` : '';

        return { label: `Plano ${getPlanDisplayName(normalizedPlan)}`, amountText };
    }

    window.currentPlanPaymentSelection = () => selectedPlan;
    if (!window.__planPaymentAvailabilityListenerBound) {
        window.__planPaymentAvailabilityListenerBound = true;
        window.addEventListener('planAvailabilityChanged', () => {
            const activePlan = window.currentPlanPaymentSelection?.();
            const activeModal = document.getElementById('paymentMethodModal');
            if (activePlan && activeModal?.style.display === 'flex') {
                if (!window.syncPlanPaymentMethodModal?.(activePlan)) window.closePaymentMethodModal?.();
            }
        });
    }

    // Retoma a escolha feita antes do cadastro/login sem pular a seleção
    // entre cartão e PIX.
    if (
        checkoutPlan
        && checkoutPlan !== 'None'
        && document.body.dataset.authenticated === 'true'
    ) {
        window.setTimeout(() => window.showPaymentMethodModal(checkoutPlan), 0);
    }

    // FAQ Toggle
    window.toggleFAQ = function (element) {
        const question = element?.closest ? element.closest('.faq-question') : element;
        const faqItem = question ? question.closest('.faq-item') : null;
        if (!faqItem) return;
        const isActive = faqItem.classList.contains('active');
        const scope = faqItem.closest('.plans-faq-section') || document;

        // Close all FAQ items
        scope.querySelectorAll('.faq-item').forEach(item => {
            item.classList.remove('active');
        });

        // Toggle current item
        if (!isActive) {
            faqItem.classList.add('active');
        }
    };

    // Downgrade Modal Logic
    let modal = null;
    let targetPlan = 'free'; // Plano de destino padrão

    window.openDowngradeModal = function (plan = 'free') {
        if (!ensurePlanAvailable(plan)) return;
        targetPlan = plan; // Salvar plano de destino

        if (!modal) {
            modal = document.getElementById('downgradeModal');
        }

        // Atualizar mensagens do modal baseado no plano
        const messageEl = document.getElementById('downgradeMessage');
        const warningEl = document.getElementById('downgradeWarning');

        if (plan === 'free') {
            if (messageEl) messageEl.textContent = `Tem certeza que deseja voltar para o plano ${getPlanDisplayName('free')}?`;
            if (warningEl) warningEl.textContent = 'Você perderá acesso imediato aos benefícios exclusivos do seu plano atual, como downloads ilimitados, suporte prioritário e área VIP.';
        } else if (plan === 'premium') {
            if (messageEl) messageEl.textContent = `Tem certeza que deseja fazer downgrade para o plano ${getPlanDisplayName('premium')}?`;
            if (warningEl) warningEl.textContent = 'Você perderá acesso aos benefícios exclusivos do plano VIP, como downloads ilimitados e área VIP exclusiva.';
        }

        if (modal) {
            modal.style.display = "flex";
            document.body.style.overflow = "hidden"; // Prevent scrolling
        } else {
            console.error('Modal element not found');
        }
    };

    window.closeDowngradeModal = function () {
        if (modal) {
            modal.style.display = "none";
            document.body.style.overflow = "auto"; // Enable scrolling
        }
    };

    window.confirmDowngrade = function () {
        fetch('/downgrade_plan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                target_plan: targetPlan
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.closeDowngradeModal();

                    // Update UI baseado no plano de destino
                    const freeCta = document.querySelector('.plan-card.free .plan-cta');
                    const premiumCta = document.querySelector('.plan-card.premium .plan-cta');
                    const vipCta = document.querySelector('.plan-card.vip .plan-cta');

                    if (targetPlan === 'free') {
                        // Downgrade para Free
                        if (freeCta) {
                            freeCta.innerHTML = '<div class="plan-badge current-plan-free"><i class="fas fa-check-circle"></i> Plano Atual</div>';
                        }
                        if (premiumCta) {
                            premiumCta.innerHTML = `<button class="plan-btn" onclick="showPaymentMethodModal('premium')">Assinar <span data-plan-name="premium">${getPlanDisplayName('premium')}</span></button>`;
                        }
                        if (vipCta) {
                            vipCta.innerHTML = `<button class="plan-btn" onclick="showPaymentMethodModal('vip')">Assinar <span data-plan-name="vip">${getPlanDisplayName('vip')}</span></button>`;
                        }
                    } else if (targetPlan === 'premium') {
                        // Downgrade para Premium (vindo do VIP)
                        if (freeCta) {
                            freeCta.innerHTML = '<button class="plan-btn downgrade-btn" onclick="openDowngradeModal(\'free\')">Voltar ao plano grátis</button>';
                        }
                        if (premiumCta) {
                            premiumCta.innerHTML = '<div class="plan-badge current-plan-premium"><i class="fas fa-check-circle"></i> Plano Atual</div>';
                        }
                        if (vipCta) {
                            vipCta.innerHTML = `<button class="plan-btn" onclick="showPaymentMethodModal('vip')">Assinar <span data-plan-name="vip">${getPlanDisplayName('vip')}</span></button>`;
                        }
                    }

                    // Show success toast
                    showToast('success', data.message);
                } else {
                    showToast('error', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('error', 'Erro ao processar solicitação.');
            });
    };

    function showToast(type, message) {
        const toastContainer = document.getElementById('flash-messages') || createToastContainer();
        const toast = document.createElement('div');
        toast.className = `favorite-toast favorite-toast-${type === 'error' ? 'danger' : type} show`;

        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        if (type === 'error') icon = 'exclamation-circle';

        toast.innerHTML = `<i class="fas fa-${icon}"></i><span>${message}</span>`;

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'flash-messages';
        container.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px;';
        document.body.appendChild(container);
        return container;
    }

    if (!window.__plansPageOutsideClickBound) {
        window.__plansPageOutsideClickBound = true;
        window.addEventListener('click', function (event) {
            const downgradeModal = document.getElementById('downgradeModal');
            const paymentModal = document.getElementById('paymentMethodModal');

            if (downgradeModal && event.target === downgradeModal) {
                window.closeDowngradeModal();
            }

            if (paymentModal && event.target === paymentModal) {
                window.closePaymentMethodModal();
            }
        });
    }
};

// Auto-initialize if loaded directly
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initializePlansPage);
} else {
    window.initializePlansPage();
}

document.addEventListener('pageLoaded', function () {
    if (document.querySelector('.plans-section')) {
        window.plansPageInitialized = false;
        window.initializePlansPage();
    }
});
