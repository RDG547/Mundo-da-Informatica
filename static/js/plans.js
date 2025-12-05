/**
 * Plans Page Functionality
 * Handles Stripe checkout, downgrade modal, and FAQ interactions.
 */

window.initializePlansPage = function () {
    const plansContainer = document.querySelector('.plans-section');
    if (!plansContainer) return;

    const stripePublicKey = plansContainer.dataset.stripeKey;
    const checkoutPlan = plansContainer.dataset.checkoutPlan;
    let stripe = null;

    // Function to initialize Stripe when ready
    const initializeStripe = () => {
        if (stripePublicKey && stripePublicKey !== 'None') {
            try {
                if (typeof Stripe !== 'undefined') {
                    stripe = Stripe(stripePublicKey);
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
            const checkStripe = setInterval(() => {
                if (typeof Stripe !== 'undefined') {
                    clearInterval(checkStripe);
                    initializeStripe();
                }
            }, 100);

            // Timeout after 5 seconds
            setTimeout(() => {
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

    window.openDowngradeModal = function () {
        if (!modal) {
            modal = document.getElementById('downgradeModal');
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
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.closeDowngradeModal();

                    // Update UI
                    // Free Plan
                    const freeCta = document.querySelector('.plan-card.free .plan-cta');
                    if (freeCta) {
                        freeCta.innerHTML = '<div class="plan-badge current-plan-free"><i class="fas fa-check-circle"></i> Plano Atual</div>';
                    }

                    // Premium Plan
                    const premiumCta = document.querySelector('.plan-card.premium .plan-cta');
                    if (premiumCta) {
                        premiumCta.innerHTML = '<button class="plan-btn" onclick="checkout(\'premium\')">Assinar Premium</button>';
                    }

                    // VIP Plan
                    const vipCta = document.querySelector('.plan-card.vip .plan-cta');
                    if (vipCta) {
                        vipCta.innerHTML = '<button class="plan-btn" onclick="checkout(\'vip\')">Assinar VIP</button>';
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
    };
};

// Auto-initialize if loaded directly
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initializePlansPage);
} else {
    window.initializePlansPage();
}
