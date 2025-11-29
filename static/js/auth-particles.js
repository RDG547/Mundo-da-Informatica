/**
 * Interactive Particles for Auth Pages
 * Partículas interativas para páginas de login e cadastro
 */

class InteractiveParticles {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.warn('Container não encontrado:', containerId);
            return;
        }

        this.options = {
            particleCount: options.particleCount || 80,
            particleSize: options.particleSize || 4,
            particleSpeed: options.particleSpeed || 0.5,
            particleColors: options.particleColors || [
                'rgba(58, 134, 255, 0.6)',
                'rgba(131, 56, 236, 0.6)',
                'rgba(255, 255, 255, 0.4)'
            ],
            connectionDistance: options.connectionDistance || 150,
            mouseRadius: options.mouseRadius || 200,
            mouseRepel: options.mouseRepel || true,
            ...options
        };

        this.particles = [];
        this.canvas = null;
        this.ctx = null;
        this.animationId = null;
        this.mouse = { x: null, y: null, radius: this.options.mouseRadius };

        this.init();
    }

    init() {
        this.createCanvas();
        this.createParticles();
        this.setupMouseInteraction();
        this.animate();
        this.handleResize();
    }

    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '1';

        this.container.style.position = 'relative';
        this.container.appendChild(this.canvas);

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
    }

    resizeCanvas() {
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }

    createParticles() {
        this.particles = [];

        for (let i = 0; i < this.options.particleCount; i++) {
            const color = this.options.particleColors[
                Math.floor(Math.random() * this.options.particleColors.length)
            ];

            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                baseX: 0,
                baseY: 0,
                vx: (Math.random() - 0.5) * this.options.particleSpeed,
                vy: (Math.random() - 0.5) * this.options.particleSpeed,
                size: Math.random() * this.options.particleSize + 1,
                opacity: Math.random() * 0.5 + 0.3,
                color: color
            });
        }

        // Definir posições base
        this.particles.forEach(particle => {
            particle.baseX = particle.x;
            particle.baseY = particle.y;
        });
    }

    setupMouseInteraction() {
        // Rastrear posição do mouse
        this.mouseMoveHandler = (e) => {
            const rect = this.container.getBoundingClientRect();
            this.mouse.x = e.clientX - rect.left;
            this.mouse.y = e.clientY - rect.top;
        };

        this.mouseLeaveHandler = () => {
            this.mouse.x = null;
            this.mouse.y = null;
        };

        this.container.addEventListener('mousemove', this.mouseMoveHandler);
        this.container.addEventListener('mouseleave', this.mouseLeaveHandler);
    }

    updateParticles() {
        this.particles.forEach(particle => {
            // Movimento base
            particle.x += particle.vx;
            particle.y += particle.vy;

            // Interação com mouse
            if (this.mouse.x !== null && this.mouse.y !== null) {
                const dx = this.mouse.x - particle.x;
                const dy = this.mouse.y - particle.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.mouse.radius) {
                    const force = (this.mouse.radius - distance) / this.mouse.radius;
                    const angle = Math.atan2(dy, dx);

                    if (this.options.mouseRepel) {
                        // Repelir partículas
                        particle.x -= Math.cos(angle) * force * 5;
                        particle.y -= Math.sin(angle) * force * 5;
                    } else {
                        // Atrair partículas
                        particle.x += Math.cos(angle) * force * 2;
                        particle.y += Math.sin(angle) * force * 2;
                    }
                }
            }

            // Voltar suavemente para posição base
            const dxBase = particle.baseX - particle.x;
            const dyBase = particle.baseY - particle.y;
            particle.x += dxBase * 0.02;
            particle.y += dyBase * 0.02;

            // Bounce nas bordas
            if (particle.x < 0 || particle.x > this.canvas.width) {
                particle.vx *= -1;
                particle.baseX = particle.x;
            }
            if (particle.y < 0 || particle.y > this.canvas.height) {
                particle.vy *= -1;
                particle.baseY = particle.y;
            }

            // Manter dentro dos limites
            particle.x = Math.max(0, Math.min(this.canvas.width, particle.x));
            particle.y = Math.max(0, Math.min(this.canvas.height, particle.y));
        });
    }

    drawParticles() {
        this.particles.forEach(particle => {
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            this.ctx.fillStyle = particle.color.replace(/[\d.]+\)$/, particle.opacity + ')');
            this.ctx.fill();

            // Adicionar brilho
            this.ctx.shadowBlur = 10;
            this.ctx.shadowColor = particle.color;
            this.ctx.fill();
            this.ctx.shadowBlur = 0;
        });
    }

    drawConnections() {
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.options.connectionDistance) {
                    const opacity = (1 - distance / this.options.connectionDistance) * 0.4;
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.strokeStyle = `rgba(58, 134, 255, ${opacity})`;
                    this.ctx.lineWidth = 1;
                    this.ctx.stroke();
                }
            }
        }

        // Conectar com mouse
        if (this.mouse.x !== null && this.mouse.y !== null) {
            this.particles.forEach(particle => {
                const dx = this.mouse.x - particle.x;
                const dy = this.mouse.y - particle.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < 150) {
                    const opacity = (1 - distance / 150) * 0.5;
                    this.ctx.beginPath();
                    this.ctx.moveTo(particle.x, particle.y);
                    this.ctx.lineTo(this.mouse.x, this.mouse.y);
                    this.ctx.strokeStyle = `rgba(131, 56, 236, ${opacity})`;
                    this.ctx.lineWidth = 2;
                    this.ctx.stroke();
                }
            });
        }
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.updateParticles();
        this.drawConnections();
        this.drawParticles();

        this.animationId = requestAnimationFrame(() => this.animate());
    }

    handleResize() {
        this.resizeHandler = () => {
            this.resizeCanvas();
            this.createParticles();
        };

        window.addEventListener('resize', this.resizeHandler);
    }

    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }

        // Remover event listeners
        this.container.removeEventListener('mousemove', this.mouseMoveHandler);
        this.container.removeEventListener('mouseleave', this.mouseLeaveHandler);
        window.removeEventListener('resize', this.resizeHandler);
    }
}

// Guardar instância atual para poder destruir antes de recriar
let currentParticlesInstance = null;

// Função para inicializar partículas em páginas de autenticação
function initAuthParticles() {
    // Destruir instância anterior se existir
    if (currentParticlesInstance) {
        currentParticlesInstance.destroy();
        currentParticlesInstance = null;
    }

    // Aguardar um pouco para garantir que o DOM está pronto
    setTimeout(function() {
        const loginSection = document.querySelector('.login-section');
        const registerSection = document.querySelector('.register-section');

        if (loginSection) {
            // Remover canvas antigo se existir
            const oldCanvas = loginSection.querySelector('canvas');
            if (oldCanvas) {
                oldCanvas.remove();
            }

            loginSection.id = 'auth-particles-container';
            currentParticlesInstance = new InteractiveParticles('auth-particles-container', {
                particleCount: 60,
                particleSize: 3,
                particleSpeed: 0.4,
                connectionDistance: 120,
                mouseRadius: 180,
                mouseRepel: true
            });
            console.log('Partículas de login inicializadas');
        }

        if (registerSection) {
            // Remover canvas antigo se existir
            const oldCanvas = registerSection.querySelector('canvas');
            if (oldCanvas) {
                oldCanvas.remove();
            }

            registerSection.id = 'auth-particles-container';
            currentParticlesInstance = new InteractiveParticles('auth-particles-container', {
                particleCount: 70,
                particleSize: 3.5,
                particleSpeed: 0.3,
                connectionDistance: 130,
                mouseRadius: 200,
                mouseRepel: true
            });
            console.log('Partículas de registro inicializadas');
        }
    }, 100);
}

// Inicializar quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuthParticles);
} else {
    initAuthParticles();
}

// Também reinicializar em navegações subsequentes
window.addEventListener('load', function() {
    initAuthParticles();
});

// Observar mudanças no body para detectar navegações SPA
if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length > 0) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) {
                        if (node.classList && (node.classList.contains('login-section') || node.classList.contains('register-section'))) {
                            console.log('Seção de auth detectada, reinicializando partículas');
                            initAuthParticles();
                        } else if (node.querySelector && (node.querySelector('.login-section') || node.querySelector('.register-section'))) {
                            console.log('Container com seção de auth detectado, reinicializando partículas');
                            initAuthParticles();
                        }
                    }
                });
            }
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}

// Disponibilizar globalmente
window.InteractiveParticles = InteractiveParticles;
window.initAuthParticles = initAuthParticles;
