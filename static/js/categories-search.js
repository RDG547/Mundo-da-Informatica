/* global document, window, fetch, console, setTimeout, clearTimeout */

/**
 * Categories Page Search with Dropdown Suggestions
 * Uses the same logic as home page search with API suggestions
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
    const searchForm = document.querySelector('.category-search-form');
    const searchInput = document.querySelector('.category-search-input');
    const suggestionsDropdown = document.querySelector('.search-suggestions-dropdown');

    if (!searchInput || !suggestionsDropdown) {
        console.warn('Search elements not found on categories page');
        return;
    }

    let debounceTimer = null;
    let selectedIndex = -1;

    // Prevent form submission and show suggestions instead
    searchForm.addEventListener('submit', function(e) {
        const query = searchInput.value.trim();

        // Se não há query, prevenir submit e mostrar mensagem
        if (!query) {
            e.preventDefault();
            e.stopPropagation();
            showInlineToast('Por favor, digite algo para pesquisar.', 'warning');
            searchInput.focus();
            return false;
        }

        // Se a query é muito curta, buscar sugestões ao invés de submeter
        if (query.length < 2) {
            e.preventDefault();
            e.stopPropagation();
            showInlineToast('Digite pelo menos 2 caracteres para pesquisar.', 'warning');
            searchInput.focus();
            return false;
        }

        // Se houver query válida, permitir o submit para a página de resultados
        // O formulário será submetido normalmente
    });

    // Handle input typing
    searchInput.addEventListener('input', function(e) {
        const query = e.target.value.trim();

        // Clear previous timer
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }

        if (query.length < 2) {
            hideSuggestions();
            return;
        }

        // Debounce the search request
        debounceTimer = setTimeout(() => {
            fetchSuggestions(query);
        }, 300);
    });

    // Handle keyboard navigation
    searchInput.addEventListener('keydown', function(e) {
        const items = suggestionsDropdown.querySelectorAll('.suggestion-item');

        if (items.length === 0) return;

        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
                updateSelection(items);
                break;
            case 'ArrowUp':
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, -1);
                updateSelection(items);
                break;
            case 'Enter':
                if (selectedIndex >= 0 && items[selectedIndex]) {
                    e.preventDefault();
                    items[selectedIndex].click();
                }
                // If no suggestion selected, allow form submit
                break;
            case 'Escape':
                hideSuggestions();
                break;
        }
    });

    // Handle focus
    searchInput.addEventListener('focus', function(e) {
        if (e.target.value.trim().length >= 2) {
            fetchSuggestions(e.target.value.trim());
        }
    });

    // Hide suggestions when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !suggestionsDropdown.contains(e.target)) {
            hideSuggestions();
        }
    });

    // Fetch suggestions from API
    async function fetchSuggestions(query) {
        try {
            // Check if we should filter by category
            const categoryFilter = searchInput.getAttribute('data-category');
            let url = `/api/search/suggestions?q=${encodeURIComponent(query)}`;

            if (categoryFilter) {
                url += `&category=${encodeURIComponent(categoryFilter)}`;
            }

            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch suggestions');

            const data = await response.json();
            displaySuggestions(data);
        } catch (error) {
            console.error('Error fetching suggestions:', error);
            hideSuggestions();
        }
    }

    // Display suggestions in dropdown
    function displaySuggestions(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            hideSuggestions();
            return;
        }

        let html = '';

        suggestions.forEach((item, index) => {
            // Use icon from API or determine from type
            const icon = item.icon || getCategoryIcon(item.type);
            const itemType = item.type === 'category' ? 'Categoria' : 'Post';
            const description = item.description || '';

            html += `
                <div class="suggestion-item" data-index="${index}" data-url="${item.url}">
                    <div class="suggestion-icon">
                        <i class="${icon}"></i>
                    </div>
                    <div class="suggestion-content">
                        <div class="suggestion-title">${highlightMatch(item.title, searchInput.value)}</div>
                        <div class="suggestion-meta">
                            <span class="suggestion-type">${itemType}</span>
                            ${description ? `<span class="suggestion-description">${description}</span>` : ''}
                        </div>
                    </div>
                    <div class="suggestion-arrow">
                        <i class="fas fa-arrow-right"></i>
                    </div>
                </div>
            `;
        });

        suggestionsDropdown.innerHTML = html;
        suggestionsDropdown.style.display = 'block';
        selectedIndex = -1;

        // Add click handlers
        const items = suggestionsDropdown.querySelectorAll('.suggestion-item');
        items.forEach(item => {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                const url = this.getAttribute('data-url');
                if (url) {
                    window.location.href = url;
                }
            });
        });
    }

    // Hide suggestions dropdown
    function hideSuggestions() {
        suggestionsDropdown.style.display = 'none';
        suggestionsDropdown.innerHTML = '';
        selectedIndex = -1;
    }

    // Update selected item
    function updateSelection(items) {
        items.forEach((item, index) => {
            if (index === selectedIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    // Get category icon
    function getCategoryIcon(category) {
        const icons = {
            'BIOS': 'fas fa-microchip',
            'Drivers': 'fas fa-cogs',
            'Esquemas': 'fas fa-project-diagram',
            'Softwares': 'fas fa-laptop-code',
            'Impressoras': 'fas fa-print',
            'Cursos': 'fas fa-graduation-cap',
            'category': 'fas fa-folder',
            'post': 'fas fa-file-alt'
        };
        return icons[category] || 'fas fa-file-alt';
    }

    // Highlight matching text
    function highlightMatch(text, query) {
        if (!query) return text;

        const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
        return text.replace(regex, '<strong>$1</strong>');
    }

    // Escape regex special characters
    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
});
