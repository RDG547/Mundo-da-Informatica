/* global document, showToast */

/**
 * Validação genérica para todos os formulários de pesquisa
 * Previne submissão vazia sem reload da página
 */

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
                if (typeof showToast === 'function') {
                    showToast('Por favor, digite algo para pesquisar.', 'warning');
                } else {
                    alert('Por favor, digite algo para pesquisar.');
                }
                searchInput.focus();
                return false;
            }
            
            if (query.length < 2) {
                e.preventDefault();
                if (typeof showToast === 'function') {
                    showToast('Digite pelo menos 2 caracteres para pesquisar.', 'warning');
                }
                searchInput.focus();
                return false;
            }
        });
    });
});
