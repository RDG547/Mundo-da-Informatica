// Preloader
window.addEventListener('load', function() {
    const preloader = document.querySelector('.preloader');
    if (preloader) {
        setTimeout(() => {
            preloader.classList.add('fade-out');
            setTimeout(() => {
                preloader.style.display = 'none';
            }, 500);
        }, 500);
    }

    // Inicializar AOS (Animate On Scroll)
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-in-out',
            once: true,
            mirror: false
        });
    }

    // Tratamento para erros de carregamento de imagens de perfil
    handleProfileImages();
});

// Função para lidar com as imagens de perfil na interface
function handleProfileImages() {
    // Seleciona todas as imagens de perfil
    const profileImages = document.querySelectorAll('.profile-img, .user-avatar img, .admin-profile-img img');

    // Adiciona manipulador de eventos para cada imagem
    profileImages.forEach(img => {
        // Verifica se a imagem já foi carregada
        if (img.complete) {
            handleImageState(img);
        } else {
            img.addEventListener('load', function() {
                handleImageState(this);
            });
        }

        // Manipula erros de carregamento
        img.addEventListener('error', function() {
            this.classList.add('error');

            // Tenta carregar novamente a partir do cache (apenas uma vez)
            if (!this.dataset.retried) {
                this.dataset.retried = 'true';
                const originalSrc = this.src;
                this.removeAttribute('src');
                setTimeout(() => {
                    if (this) this.src = originalSrc;
                }, 500);
            }
        });
    });
}

// Função auxiliar para gerenciar o estado da imagem
function handleImageState(img) {
    // Verifica se a imagem tem conteúdo válido
    if (img.naturalWidth === 0 || img.naturalHeight === 0) {
        img.classList.add('error');
    } else {
        img.classList.remove('error');

        // Remove classe de carregamento do contêiner
        const container = img.closest('.admin-profile-img, .user-avatar, .profile-img');
        if (container) {
            container.classList.remove('loading');
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Menu Toggle para dispositivos móveis
    const menuToggle = document.querySelector('.menu-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            navMenu.classList.toggle('active');
            menuToggle.classList.toggle('active');
        });
    }

    // Navbar Scroll Effect
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Fechar o menu ao clicar em um link
    const navLinks = document.querySelectorAll('.nav-menu a');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navMenu.classList.remove('active');
            menuToggle.classList.remove('active');
        });
    });

    // Accordion para FAQ
    const accordionHeaders = document.querySelectorAll('.accordion-header');
    accordionHeaders.forEach(header => {
        header.addEventListener('click', () => {
            header.classList.toggle('active');
            const content = header.nextElementSibling;

            // Fechar outros acordeões
            accordionHeaders.forEach(otherHeader => {
                if (otherHeader !== header) {
                    otherHeader.classList.remove('active');
                    otherHeader.nextElementSibling.style.maxHeight = 0;
                    otherHeader.nextElementSibling.classList.remove('active');
                }
            });

            if (header.classList.contains('active')) {
                content.style.maxHeight = content.scrollHeight + 'px';
                content.classList.add('active');
            } else {
                content.style.maxHeight = 0;
                content.classList.remove('active');
            }
        });
    });

    // Animação de rolagem suave para links internos
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            if (this.getAttribute('href') !== '#') {
                e.preventDefault();

                const targetId = this.getAttribute('href');
                const targetElement = document.querySelector(targetId);

                if (targetElement) {
                    window.scrollTo({
                        top: targetElement.offsetTop - 80,
                        behavior: 'smooth'
                    });
                }
            }
        });
    });

    // Scroll to top button
    const scrollTop = document.querySelector('.scroll-top');
    if (scrollTop) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                scrollTop.classList.add('active');
            } else {
                scrollTop.classList.remove('active');
            }
        });

        scrollTop.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // Dark mode toggle
    const darkModeToggle = document.querySelector('.dark-mode');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', () => {
            document.body.setAttribute('data-theme',
                document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
        });
    }

    // Formulário de contato com validação e animação
    const contactForm = document.querySelector('.contact-form form');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // Validação básica
            let isValid = true;
            const inputs = this.querySelectorAll('input, textarea');

            inputs.forEach(input => {
                if (input.value.trim() === '') {
                    isValid = false;
                    input.classList.add('error');

                    const errorMessage = document.createElement('div');
                    errorMessage.className = 'error-message';
                    errorMessage.textContent = 'Este campo é obrigatório';

                    // Remover mensagem de erro existente
                    const existingError = input.parentElement.querySelector('.error-message');
                    if (existingError) {
                        existingError.remove();
                    }

                    input.parentElement.appendChild(errorMessage);

                    // Adicionar evento para remover o erro quando o usuário digitar
                    input.addEventListener('input', function() {
                        if (this.value.trim() !== '') {
                            this.classList.remove('error');
                            const errorMsg = this.parentElement.querySelector('.error-message');
                            if (errorMsg) {
                                errorMsg.remove();
                            }
                        }
                    });
                }
            });

            if (isValid) {
                // Simulando envio
                const submitButton = this.querySelector('button[type="submit"]');
                const originalText = submitButton.textContent;

                submitButton.disabled = true;
                submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';

                // Simulando uma requisição
                setTimeout(() => {
                    // Animação de sucesso
                    contactForm.innerHTML = `
                        <div class="success-message" style="text-align: center;">
                            <div class="success-icon">
                                <i class="fas fa-check-circle"></i>
                            </div>
                            <h3>Mensagem Enviada!</h3>
                            <p>Obrigado pelo seu contato. Responderemos em breve.</p>
                        </div>
                    `;

                    // Animar entrada da mensagem de sucesso
                    const successMessage = contactForm.querySelector('.success-message');
                    successMessage.style.opacity = 0;
                    successMessage.style.transform = 'translateY(20px)';

                    setTimeout(() => {
                        successMessage.style.transition = 'all 0.5s ease';
                        successMessage.style.opacity = 1;
                        successMessage.style.transform = 'translateY(0)';
                    }, 100);

                }, 1500);
            }
        });
    }

    // Botões de compartilhamento com compartilhamento real
    const shareButtons = document.querySelectorAll('.social-share a');
    if (shareButtons.length > 0) {
        shareButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();

                const pageUrl = window.location.href;
                const pageTitle = document.title;

                // Identificar a rede social pelo ícone
                if (this.querySelector('.fa-facebook') || this.classList.contains('facebook')) {
                    window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl)}`, 'facebook-share', 'width=580,height=296');
                } else if (this.querySelector('.fa-twitter') || this.classList.contains('twitter')) {
                    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(pageTitle)}&url=${encodeURIComponent(pageUrl)}`, 'twitter-share', 'width=550,height=235');
                } else if (this.querySelector('.fa-whatsapp') || this.classList.contains('whatsapp')) {
                    window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(pageTitle + ' ' + pageUrl)}`, 'whatsapp-share', 'width=550,height=450');
                } else if (this.querySelector('.fa-telegram') || this.classList.contains('telegram')) {
                    window.open(`https://telegram.me/share/url?url=${encodeURIComponent(pageUrl)}&text=${encodeURIComponent(pageTitle)}`, 'telegram-share', 'width=550,height=450');
                }
            });
        });
    }

    // Lazy loading para imagens
    const lazyImages = document.querySelectorAll('img[data-src]');
    if (lazyImages.length > 0) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    imageObserver.unobserve(img);
                }
            });
        });

        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
    }

    // Adicionar animações aos cards
    const animateElements = (entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate');
                observer.unobserve(entry.target);
            }
        });
    };

    const observer = new IntersectionObserver(animateElements, {
        root: null,
        threshold: 0.1
    });

    document.querySelectorAll('.category-card, .post-card, .team-member').forEach(item => {
        item.classList.add('reveal');
        observer.observe(item);
    });

    // Efeito Parallax para seções com fundo
    window.addEventListener('scroll', function() {
        const parallaxElements = document.querySelectorAll('.hero, .cta, .about-header, .contact-header');
        parallaxElements.forEach(element => {
            const scrollPosition = window.scrollY;
            const elementPosition = element.offsetTop;
            const elementHeight = element.offsetHeight;

            if (scrollPosition > elementPosition - window.innerHeight && scrollPosition < elementPosition + elementHeight) {
                const speed = element.dataset.speed || 0.5;
                const yPos = (scrollPosition - elementPosition) * speed;
                element.style.backgroundPosition = `center ${yPos}px`;
            }
        });
    });

    // Contador para estatísticas (se existirem)
    const statsElements = document.querySelectorAll('.counter');
    if (statsElements.length > 0) {
        const statsObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const countTarget = parseInt(entry.target.getAttribute('data-count'));
                    const countElement = entry.target;
                    let count = 0;
                    const duration = 2000; // ms
                    const interval = duration / countTarget;

                    const counter = setInterval(() => {
                        count++;
                        countElement.textContent = count;

                        if (count >= countTarget) {
                            clearInterval(counter);
                        }
                    }, interval);

                    observer.unobserve(entry.target);
                }
            });
        });

        statsElements.forEach(stat => {
            statsObserver.observe(stat);
        });
    }

    // Typed.js para elementos de texto dinâmico (se existir)
    const typedElement = document.querySelector('.typed-text');
    if (typedElement && typeof Typed !== 'undefined') {
        new Typed(typedElement, {
            strings: typedElement.getAttribute('data-typed-items').split(','),
            typeSpeed: 100,
            backSpeed: 50,
            backDelay: 2000,
            loop: true
        });
    }

    // FAQ functionality is now handled by the dedicated FAQManager class in faq.js
    // This prevents conflicts and ensures proper functionality after page refreshes
});

// Adicionar classe de animação CSS para elementos estáticos
document.addEventListener('DOMContentLoaded', function() {
    const animElements = document.querySelectorAll('.animate-fade-in, .animate-slide-left, .animate-slide-right, .animate-slide-up, .animate-pulse');
    animElements.forEach(elem => {
        elem.style.opacity = 0;

        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = 1;
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        observer.observe(elem);
    });
});

// Filtros para galerias ou listas (se existirem)
document.addEventListener('DOMContentLoaded', function() {
    const filterButtons = document.querySelectorAll('[data-filter]');
    if (filterButtons.length > 0) {
        filterButtons.forEach(button => {
            button.addEventListener('click', function() {
                const filterValue = this.dataset.filter;
                const items = document.querySelectorAll('[data-category]');

                // Remover classe ativa de todos os botões
                filterButtons.forEach(btn => btn.classList.remove('active'));
                // Adicionar classe ativa ao botão clicado
                this.classList.add('active');

                items.forEach(item => {
                    if (filterValue === 'all' || item.dataset.category === filterValue) {
                        item.style.display = 'block';
                        setTimeout(() => {
                            item.style.opacity = 1;
                            item.style.transform = 'scale(1)';
                        }, 10);
                    } else {
                        item.style.opacity = 0;
                        item.style.transform = 'scale(0.8)';
                        setTimeout(() => {
                            item.style.display = 'none';
                        }, 300);
                    }
                });
            });
        });
    }
});

// Swiper Carousel (se existir)
document.addEventListener('DOMContentLoaded', function() {
    if (typeof Swiper !== 'undefined') {
        // Inicializar todos os carousels com a classe swiper
        document.querySelectorAll('.swiper').forEach(swiperElement => {
            new Swiper(swiperElement, {
                slidesPerView: 'auto',
                spaceBetween: 30,
                pagination: {
                    el: '.swiper-pagination',
                    clickable: true,
                },
                navigation: {
                    nextEl: '.swiper-button-next',
                    prevEl: '.swiper-button-prev',
                },
                breakpoints: {
                    640: {
                        slidesPerView: 1,
                        spaceBetween: 20,
                    },
                    768: {
                        slidesPerView: 2,
                        spaceBetween: 30,
                    },
                    1024: {
                        slidesPerView: 3,
                        spaceBetween: 30,
                    },
                }
            });
        });
    }
});
