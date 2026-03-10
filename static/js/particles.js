/**
 * Animated Particles Background
 * Creates floating particles animation for hero section
 */

// Verificar se já foi carregado
if (typeof window.ParticlesAnimation !== 'undefined') {
    console.log('particles.js já carregado, ignorando redeclaração');
} else {

window.ParticlesAnimation = class ParticlesAnimation {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.options = {
            particleCount: options.particleCount || 50,
            particleSize: options.particleSize || 3,
            particleSpeed: options.particleSpeed || 0.5,
            particleColor: options.particleColor || 'rgba(255, 255, 255, 0.6)',
            connectionDistance: options.connectionDistance || 100,
            connectionColor: options.connectionColor || 'rgba(255, 255, 255, 0.2)',
            ...options
        };

        this.particles = [];
        this.canvas = null;
        this.ctx = null;
        this.animationId = null;

        this.init();
    }

    init() {
        this.createCanvas();
        this.createParticles();
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
        this.canvas.style.zIndex = '5';

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
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * this.options.particleSpeed,
                vy: (Math.random() - 0.5) * this.options.particleSpeed,
                size: Math.random() * this.options.particleSize + 1,
                opacity: Math.random() * 0.5 + 0.3
            });
        }
    }

    updateParticles() {
        this.particles.forEach(particle => {
            particle.x += particle.vx;
            particle.y += particle.vy;

            // Bounce off edges
            if (particle.x < 0 || particle.x > this.canvas.width) {
                particle.vx *= -1;
            }
            if (particle.y < 0 || particle.y > this.canvas.height) {
                particle.vy *= -1;
            }

            // Keep particles within bounds
            particle.x = Math.max(0, Math.min(this.canvas.width, particle.x));
            particle.y = Math.max(0, Math.min(this.canvas.height, particle.y));
        });
    }

    drawParticles() {
        this.particles.forEach(particle => {
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            this.ctx.fillStyle = this.options.particleColor.replace('0.6', particle.opacity);
            this.ctx.fill();
        });
    }

    drawConnections() {
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.options.connectionDistance) {
                    const opacity = (1 - distance / this.options.connectionDistance) * 0.3;
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.strokeStyle = this.options.connectionColor.replace('0.2', opacity);
                    this.ctx.lineWidth = 1;
                    this.ctx.stroke();
                }
            }
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
        window.addEventListener('resize', () => {
            this.resizeCanvas();
            this.createParticles();
        });
    }

    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

// Initialize particles when DOM is loaded
function initializeParticles() {
    const heroSection = document.querySelector('#hero-particles');
    if (heroSection) {
        // Remove existing canvas if any
        const existingCanvas = heroSection.querySelector('canvas');
        if (existingCanvas) {
            existingCanvas.remove();
        }

        // Add particles container
        heroSection.style.overflow = 'hidden';

        // Initialize particles animation
        new window.ParticlesAnimation('hero-particles', {
            particleCount: 60,
            particleSize: 2,
            particleSpeed: 0.3,
            particleColor: 'rgba(255, 255, 255, 0.7)',
            connectionDistance: 120,
            connectionColor: 'rgba(255, 255, 255, 0.15)'
        });
    }
}

} // Fim da verificação de carregamento

// Initialize on DOM load
if (typeof window.ParticlesAnimation !== 'undefined') {
    document.addEventListener('DOMContentLoaded', initializeParticles);
}

// Make function globally available for dynamic loading
window.initializeParticles = initializeParticles;

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ParticlesAnimation;
}
