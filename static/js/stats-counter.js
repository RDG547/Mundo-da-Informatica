function isElementInViewport(el) {
    const rect = el.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    return rect.top <= viewportHeight * 0.9 && rect.bottom >= 0;
}

function animateCounters() {
    const counters = document.querySelectorAll('.count[data-count]');

    counters.forEach(counter => {
        if (counter.classList.contains('animated')) return;
        if (!isElementInViewport(counter)) return;

        const target = parseInt(counter.getAttribute('data-count') || '0', 10);
        if (!Number.isFinite(target) || target < 0) return;

        counter.classList.add('animated');

        const duration = 2000;
        const step = Math.max(1, target / duration * 10);
        let current = 0;

        const counterAnimation = setInterval(() => {
            current += step;
            if (current >= target) {
                counter.textContent = target.toLocaleString('pt-BR');
                clearInterval(counterAnimation);
            } else {
                counter.textContent = Math.floor(current).toLocaleString('pt-BR');
            }
        }, 10);
    });
}

function initializeStatsCounters() {
    animateCounters();
    window.removeEventListener('scroll', animateCounters);
    window.addEventListener('scroll', animateCounters, { passive: true });
}

window.initializeStatsCounters = initializeStatsCounters;

document.addEventListener('DOMContentLoaded', initializeStatsCounters);
document.addEventListener('pageLoaded', () => {
    setTimeout(initializeStatsCounters, 80);
});
