/**
 * Atualiza os preços dos planos em tempo real em qualquer página que os exiba.
 *
 * Elementos rastreados:
 *   [data-plan-price-amount="premium|vip"] -> apenas o valor ("29,90")
 *   [data-plan-price-full="premium|vip"]   -> valor com moeda ("R$ 29,90")
 *
 * O polling consulta /api/plan-prices e aplica o novo valor com uma animação
 * de destaque sempre que o admin altera os preços no painel.
 */
(function () {
    if (window.refreshPlanPrices) {
        return;
    }

    const POLL_INTERVAL_MS = 10000;

    function flashElement(el) {
        if (typeof el.animate !== 'function') {
            return;
        }
        el.animate(
            [
                { transform: 'scale(1)', filter: 'brightness(1)' },
                { transform: 'scale(1.18)', filter: 'brightness(1.35)', offset: 0.35 },
                { transform: 'scale(1)', filter: 'brightness(1)' }
            ],
            { duration: 700, easing: 'ease-in-out' }
        );
    }

    function setPriceText(el, text) {
        const isFirstSync = el.dataset.planPriceInit !== 'true';
        if (el.textContent.trim() === text) {
            el.dataset.planPriceInit = 'true';
            return;
        }
        el.textContent = text;
        el.dataset.planPriceInit = 'true';
        if (!isFirstSync) {
            flashElement(el);
        }
    }

    function applyPrices(plans) {
        if (!plans) {
            return;
        }

        document.querySelectorAll('[data-plan-price-amount]').forEach((el) => {
            const plan = plans[el.dataset.planPriceAmount];
            if (!plan) {
                return;
            }
            setPriceText(el, plan.display_amount);
        });

        document.querySelectorAll('[data-plan-price-full]').forEach((el) => {
            const plan = plans[el.dataset.planPriceFull];
            if (!plan) {
                return;
            }
            setPriceText(el, plan.display_full);
        });
    }

    async function fetchPlanPrices() {
        try {
            const response = await fetch('/api/plan-prices', {
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) {
                return;
            }
            const data = await response.json().catch(() => ({}));
            if (data && data.success && data.plans) {
                applyPrices(data.plans);
            }
        } catch (_error) {
            // Falhas de rede são ignoradas; a próxima tentativa ocorre no polling.
        }
    }

    function hasPriceElements() {
        return Boolean(document.querySelector('[data-plan-price-amount], [data-plan-price-full]'));
    }

    window.refreshPlanPrices = fetchPlanPrices;

    fetchPlanPrices();
    window.setInterval(() => {
        if (hasPriceElements()) {
            fetchPlanPrices();
        }
    }, POLL_INTERVAL_MS);

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && hasPriceElements()) {
            fetchPlanPrices();
        }
    });
})();
