/* global document */

/**
 * Validação genérica para todos os formulários de pesquisa
 * Previne submissão vazia sem reload da página
 */

// Função toast inline padronizada (igual às notificações do sistema)
function showInlineToast(message, type = 'success') {
    // Tentar usar o sistema de toast global se disponível
    if (window.favoriteManager && typeof window.favoriteManager.showToast === 'function') {
        window.favoriteManager.showToast(message, type);
        return;
    }

    // Fallback: criar toast com aparência padronizada
    const toast = document.createElement('div');
    toast.className = 'toast-notification';

    const colors = {
        success: { bg: '#10b981', icon: 'check-circle' },
        warning: { bg: '#f59e0b', icon: 'exclamation-triangle' },
        error: { bg: '#ef4444', icon: 'times-circle' }
    };

    const color = colors[type] || colors.success;

    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        min-width: 300px;
        max-width: 500px;
        padding: 16px 20px;
        background: white;
        color: #1f2937;
        border-radius: 12px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05);
        z-index: 10000;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: slideInRight 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        border-left: 4px solid ${color.bg};
    `;

    toast.innerHTML = `
        <i class="fas fa-${color.icon}" style="color: ${color.bg}; font-size: 20px;"></i>
        <span style="flex: 1;">${message}</span>
    `;

    if (!document.getElementById('toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(400px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0) scale(1); opacity: 1; }
                to { transform: translateX(400px) scale(0.9); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

document.addEventListener('DOMContentLoaded', function() {
    // Selecionar todos os formulários de pesquisa que não têm validação específica
    const searchForms = document.querySelectorAll('form[action*="search"], form[action*="pesquisa"]');

    searchForms.forEach(form => {
        // Ignorar se já tem validação (home-search, category-search)
        if (form.id === 'home-search-form' || form.classList.contains('category-search-form')) {
            return;
        }

        // Adicionar validação
        form.addEventListener('submit', function(e) {
            const searchInput = form.querySelector('input[name="q"]');
            if (!searchInput) return;

            const query = searchInput.value.trim();

            if (!query) {
                e.preventDefault();
                showInlineToast('Por favor, digite algo para pesquisar.', 'warning');
                searchInput.focus();
                return false;
            }

            if (query.length < 2) {
                e.preventDefault();
                showInlineToast('Digite pelo menos 2 caracteres para pesquisar.', 'warning');
                searchInput.focus();
                return false;
            }
        });
    });
});
