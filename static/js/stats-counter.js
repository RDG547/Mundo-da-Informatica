document.addEventListener('DOMContentLoaded', function() {
    // Função para verificar se um elemento está visível na tela
    function isElementInViewport(el) {
        const rect = el.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }

    // Função para animar a contagem dos números
    function animateCounters() {
        const counters = document.querySelectorAll('.count');

        counters.forEach(counter => {
            // Verificar se o contador já foi animado
            if (counter.classList.contains('animated')) return;

            // Verificar se o contador está visível na tela
            if (isElementInViewport(counter)) {
                counter.classList.add('animated');

                const target = parseInt(counter.getAttribute('data-count'));
                const duration = 2000; // Duração da animação em ms
                const step = target / duration * 10; // Incremento a cada 10ms

                let current = 0;
                const counterAnimation = setInterval(() => {
                    current += step;
                    if (current >= target) {
                        counter.textContent = target;
                        clearInterval(counterAnimation);
                    } else {
                        counter.textContent = Math.floor(current);
                    }
                }, 10);
            }
        });
    }

    // Executar a animação quando a página carregar e durante o scroll
    animateCounters();
    window.addEventListener('scroll', animateCounters);
});
