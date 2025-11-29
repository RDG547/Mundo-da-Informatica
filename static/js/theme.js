/**
 * Gerenciamento de temas para o Mundo da Informática
 */

// Sistema de Temas
const ThemeManager = {
    // Chave para salvar a preferência no localStorage
    STORAGE_KEY: 'mundoinformatica_theme',

    // Inicializa o gerenciador de temas
    init() {
        this.setupThemeToggle();
        this.loadSavedTheme();
        this.setupColorCustomization();
        this.setupTransitions();
        this.setupScrollEffects();
        this.setupNeuefectComponents();
    },

    // Configura o botão de alternar tema (dark/light)
    setupThemeToggle() {
        const toggleBtn = document.querySelector('.theme-toggle');
        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', () => {
            const currentTheme = document.body.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            this.setTheme(newTheme);
            localStorage.setItem(this.STORAGE_KEY, newTheme);

            // Atualiza o ícone
            toggleBtn.innerHTML = newTheme === 'dark'
                ? '<i class="fas fa-sun"></i>'
                : '<i class="fas fa-moon"></i>';
        });
    },

    // Carrega o tema salvo ou usa a preferência do sistema
    loadSavedTheme() {
        const savedTheme = localStorage.getItem(this.STORAGE_KEY);

        if (savedTheme) {
            this.setTheme(savedTheme);
        } else {
            // Usa a preferência do sistema se disponível
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.setTheme(prefersDark ? 'dark' : 'light');
        }

        // Atualiza o ícone no toggle
        const toggleBtn = document.querySelector('.theme-toggle');
        if (toggleBtn) {
            toggleBtn.innerHTML = document.body.getAttribute('data-theme') === 'dark'
                ? '<i class="fas fa-sun"></i>'
                : '<i class="fas fa-moon"></i>';
        }

        // Adiciona ouvinte para mudanças na preferência do sistema
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem(this.STORAGE_KEY)) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    },

    // Aplica o tema na página
    setTheme(theme) {
        document.body.setAttribute('data-theme', theme);

        // Atualiza a meta tag para a barra de navegação móvel
        const metaThemeColor = document.querySelector('meta[name="theme-color"]');
        if (metaThemeColor) {
            metaThemeColor.setAttribute('content', theme === 'dark' ? '#121212' : '#ffffff');
        }

        // Dispara evento personalizado
        document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    },

    // Configura personalização de cores do tema
    setupColorCustomization() {
        // Procura por configurações de cores personalizadas no HTML
        const primaryColor = document.body.getAttribute('data-primary-color');
        const secondaryColor = document.body.getAttribute('data-secondary-color');

        // Aplica cores personalizadas se existirem
        if (primaryColor) {
            document.documentElement.style.setProperty('--primary-color', primaryColor);
            // Gera variações da cor primária
            this.setColorVariations('primary', primaryColor);
        }

        if (secondaryColor) {
            document.documentElement.style.setProperty('--secondary-color', secondaryColor);
            // Gera variações da cor secundária
            this.setColorVariations('secondary', secondaryColor);
        }
    },

    // Gera variações mais claras e escuras de uma cor
    setColorVariations(prefix, hexColor) {
        // Converte hex para RGB
        const r = parseInt(hexColor.slice(1, 3), 16);
        const g = parseInt(hexColor.slice(3, 5), 16);
        const b = parseInt(hexColor.slice(5, 7), 16);

        // Variação mais clara (15% mais clara)
        const lighterR = Math.min(255, Math.round(r * 1.15));
        const lighterG = Math.min(255, Math.round(g * 1.15));
        const lighterB = Math.min(255, Math.round(b * 1.15));
        const lighterHex = `#${lighterR.toString(16).padStart(2, '0')}${lighterG.toString(16).padStart(2, '0')}${lighterB.toString(16).padStart(2, '0')}`;

        // Variação mais escura (20% mais escura)
        const darkerR = Math.round(r * 0.8);
        const darkerG = Math.round(g * 0.8);
        const darkerB = Math.round(b * 0.8);
        const darkerHex = `#${darkerR.toString(16).padStart(2, '0')}${darkerG.toString(16).padStart(2, '0')}${darkerB.toString(16).padStart(2, '0')}`;

        // Aplicar as variações às variáveis CSS
        document.documentElement.style.setProperty(`--${prefix}-light`, lighterHex);
        document.documentElement.style.setProperty(`--${prefix}-dark`, darkerHex);
    },

    // Configura transições suaves para mudanças de tema
    setupTransitions() {
        document.body.classList.add('theme-transition');

        // Adiciona classe de transição a elementos específicos
        const transitionElements = [
            '.card', '.btn', '.navbar', 'input', 'textarea',
            '.post-card', '.featured-card', '.category-card'
        ];

        transitionElements.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                el.classList.add('theme-transition');
            });
        });
    },

    // Configura efeitos de animação ao scroll
    setupScrollEffects() {
        // Animação para elementos que entram na tela
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        // Observa todos os elementos com a classe stagger-item
        document.querySelectorAll('.stagger-item').forEach((item, index) => {
            // Adiciona um atraso crescente baseado no índice
            item.style.animationDelay = `${0.1 * index}s`;
            observer.observe(item);
        });

        // Efeitos parallax para backgrounds
        window.addEventListener('scroll', () => {
            const parallaxElements = document.querySelectorAll('[data-parallax]');

            parallaxElements.forEach(element => {
                const speed = parseFloat(element.getAttribute('data-parallax') || 0.2);
                const rect = element.getBoundingClientRect();
                const viewHeight = window.innerHeight;

                // Verifica se o elemento está visível na tela
                if (rect.bottom > 0 && rect.top < viewHeight) {
                    const scrollPos = window.scrollY;
                    const elementTop = rect.top + scrollPos;
                    const distance = scrollPos - elementTop;
                    const translateY = distance * speed;

                    element.style.backgroundPositionY = `calc(50% + ${translateY}px)`;
                }
            });
        });
    },

    // Configura componentes com efeitos especiais
    setupNeuefectComponents() {
        // Cards com efeito de profundidade
        document.querySelectorAll('.neuemorph-card').forEach(card => {
            card.addEventListener('mousemove', e => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left; // Posição X relativa ao card
                const y = e.clientY - rect.top;  // Posição Y relativa ao card

                const centerX = rect.width / 2;
                const centerY = rect.height / 2;

                // Calcula o ângulo baseado na posição do mouse
                const rotateY = ((x - centerX) / centerX) * 5; // Limita a 5 graus
                const rotateX = ((centerY - y) / centerY) * 5;

                // Aplica a rotação
                card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;

                // Efeito de iluminação
                const intensity = 0.2;
                const spotlightX = x / rect.width * 100;
                const spotlightY = y / rect.height * 100;
                card.style.background = `radial-gradient(circle at ${spotlightX}% ${spotlightY}%, rgba(255,255,255,${intensity}), transparent 100px)`;
            });

            // Reseta quando o mouse sai
            card.addEventListener('mouseleave', () => {
                card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
                card.style.background = '';
            });
        });
    }
};

// Inicializa o gerenciador de temas quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
});
