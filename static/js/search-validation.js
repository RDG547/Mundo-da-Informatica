/* global document */

/**
 * Validação genérica para todos os formulários de pesquisa
 * Previne submissão vazia sem reload da página
 */

// Função toast inline que sempre funciona
function showInlineToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#28a745' : type === 'warning' ? '#ffc107' : '#dc3545'};
        color: ${type === 'warning' ? '#000' : 'white'};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        animation: slideInRight 0.3s ease;
    `;
    toast.textContent = message;

    if (!document.getElementById('toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(400px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(400px); opacity: 0; }
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
