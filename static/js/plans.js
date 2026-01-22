/**
 * Plans Page Functionality
 * Handles Stripe checkout, downgrade modal, and FAQ interactions.
 */

window.initializePlansPage = function () {
    const plansContainer = document.querySelector('.plans-section');
    if (!plansContainer) return;

    // Prevenir inicialização duplicada
    if (window.plansPageInitialized) {
        console.log('Plans page already initialized, skipping');
        return;
    }
    window.plansPageInitialized = true;

    const stripePublicKey = plansContainer.dataset.stripeKey;
    const checkoutPlan = plansContainer.dataset.checkoutPlan;
    let stripe = null;
    let stripeInitialized = false;

    // Function to initialize Stripe when ready
    const initializeStripe = () => {
        // Evitar múltiplas inicializações
        if (stripeInitialized) {
            console.log('Stripe already initialized, skipping');
            return;
        }

        if (stripePublicKey && stripePublicKey !== 'None') {
            try {
                if (typeof Stripe !== 'undefined') {
                    stripe = Stripe(stripePublicKey);
                    stripeInitialized = true;
                    console.log('Stripe initialized successfully');

                    // Auto-checkout if plan is specified
                    if (checkoutPlan && checkoutPlan !== 'None') {
                        window.checkout(checkoutPlan);
                    }
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
    window.checkout = function (plan) {
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
                } else {
                    return stripe.redirectToCheckout({ sessionId: session.id });
                }
            })
            .then(function (result) {
                if (result.error) {
                    alert(result.error.message);
                }
            })
            .catch(function (error) {
                console.error('Error:', error);
            });
    };

    // Payment Method Modal
    let paymentMethodModal = null;
    let selectedPlan = null;

    window.showPaymentMethodModal = function (plan) {
        selectedPlan = plan;
        console.log('Modal de pagamento aberto para plano:', selectedPlan);
        if (!paymentMethodModal) {
            paymentMethodModal = document.getElementById('paymentMethodModal');
        }
        if (paymentMethodModal) {
            paymentMethodModal.style.display = "block";
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

        console.log('Método de pagamento selecionado:', method);
        console.log('Plano selecionado:', selectedPlan);

        // Salvar o plano antes de fechar o modal
        const planToCheckout = selectedPlan;

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
        console.log('checkoutPix chamado com plano:', plan);

        const payload = { plan: plan };
        console.log('Payload enviado:', payload);

        fetch('/create-pix-checkout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        })
            .then(response => response.json())
            .then(data => {
                console.log('Resposta recebida:', data);

                // Verificar se há redirect_url (mesmo com erro)
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
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

    // FAQ Toggle
    window.toggleFAQ = function (element) {
        const faqItem = element.parentElement;
        const isActive = faqItem.classList.contains('active');

        // Close all FAQ items
        document.querySelectorAll('.faq-item').forEach(item => {
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
        targetPlan = plan; // Salvar plano de destino

        if (!modal) {
            modal = document.getElementById('downgradeModal');
        }

        // Atualizar mensagens do modal baseado no plano
        const messageEl = document.getElementById('downgradeMessage');
        const warningEl = document.getElementById('downgradeWarning');

        if (plan === 'free') {
            if (messageEl) messageEl.textContent = 'Tem certeza que deseja voltar para o plano grátis?';
            if (warningEl) warningEl.textContent = 'Você perderá acesso imediato aos benefícios exclusivos do seu plano atual, como downloads ilimitados, suporte prioritário e área VIP.';
        } else if (plan === 'premium') {
            if (messageEl) messageEl.textContent = 'Tem certeza que deseja fazer downgrade para o plano Premium?';
            if (warningEl) warningEl.textContent = 'Você perderá acesso aos benefícios exclusivos do plano VIP, como downloads ilimitados e área VIP exclusiva.';
        }

        if (modal) {
            modal.style.display = "block";
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
                            premiumCta.innerHTML = '<button class="plan-btn" onclick="showPaymentMethodModal(\'premium\')">Assinar Premium</button>';
                        }
                        if (vipCta) {
                            vipCta.innerHTML = '<button class="plan-btn" onclick="showPaymentMethodModal(\'vip\')">Assinar VIP</button>';
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
                            vipCta.innerHTML = '<button class="plan-btn" onclick="showPaymentMethodModal(\'vip\')">Assinar VIP</button>';
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

    // Close modal when clicking outside
    window.onclick = function (event) {
        if (modal && event.target == modal) {
            window.closeDowngradeModal();
        }
        if (paymentMethodModal && event.target == paymentMethodModal) {
            window.closePaymentMethodModal();
        }
    };
};

// Auto-initialize if loaded directly
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initializePlansPage);
} else {
    window.initializePlansPage();
}
