/**
 * Search Suggestions Functionality
 * Provides real-time search suggestions for categories and posts
 */

class SearchSuggestions {
    constructor(inputSelector, suggestionsSelector) {
        this.input = document.querySelector(inputSelector);
        this.suggestionsContainer = document.querySelector(suggestionsSelector);

        if (!this.input) {
            console.warn('Search input not found:', inputSelector);
            return;
        }

        this.createSuggestionsContainer();
        this.bindEvents();
        this.debounceTimer = null;
    }

    createSuggestionsContainer() {
        if (!this.suggestionsContainer) {
            this.suggestionsContainer = document.createElement('div');
            this.suggestionsContainer.className = 'search-suggestions';

            // Garantir que o container pai tenha position relative
            let parent = this.input.parentNode;

            // Se o pai for .search-input-wrapper, use ele; senão, use o próprio input parent
            if (!parent.classList.contains('search-input-wrapper')) {
                // Criar wrapper se não existir
                const wrapper = document.createElement('div');
                wrapper.className = 'search-input-wrapper';
                wrapper.style.position = 'relative';
                wrapper.style.width = '100%';

                this.input.parentNode.insertBefore(wrapper, this.input);
                wrapper.appendChild(this.input);
                parent = wrapper;
            }

            parent.style.position = 'relative';
            parent.appendChild(this.suggestionsContainer);
        }
    }

    bindEvents() {
        this.input.addEventListener('input', (e) => {
            this.handleInput(e.target.value);
        });

        this.input.addEventListener('focus', (e) => {
            if (e.target.value.trim().length >= 1) {  // Mudado de 2 para 1
                this.handleInput(e.target.value);
            }
        });

        this.input.addEventListener('blur', (e) => {
            // Delay hiding to allow clicking on suggestions
            setTimeout(() => {
                this.hideSuggestions();
            }, 200);
        });

        // Handle keyboard navigation
        this.input.addEventListener('keydown', (e) => {
            this.handleKeyNavigation(e);
        });

        // Hide suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }

    handleInput(value) {
        const query = value.trim();

        // Clear previous timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        if (query.length < 1) {  // Mudado para 1 para pesquisar desde a primeira letra
            this.hideSuggestions();
            return;
        }

        // Debounce the search request (reduzido para resposta mais rápida)
        this.debounceTimer = setTimeout(() => {
            this.fetchSuggestions(query);
        }, 200);  // Reduzido de 300 para 200ms
    }

    async fetchSuggestions(query) {
        try {
            const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}`);
            const suggestions = await response.json();
            console.log('Sugestões recebidas:', suggestions); // Debug
            this.displaySuggestions(suggestions);
        } catch (error) {
            console.error('Error fetching suggestions:', error);
            this.hideSuggestions();
        }
    }

    displaySuggestions(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            this.hideSuggestions();
            return;
        }

        let html = '';
        suggestions.forEach((suggestion, index) => {
            const typeClass = suggestion.type === 'category' ? 'suggestion-category' : 'suggestion-post';
            html += `
                <div class="suggestion-item ${typeClass}" data-index="${index}" data-url="${suggestion.url}">
                    <div class="suggestion-icon">
                        <i class="${suggestion.icon}"></i>
                    </div>
                    <div class="suggestion-content">
                        <div class="suggestion-title">${this.highlightQuery(suggestion.title, this.input.value)}</div>
                        <div class="suggestion-description">${suggestion.description}</div>
                    </div>
                    <div class="suggestion-type">
                        ${suggestion.type === 'category' ? 'Categoria' : 'Post'}
                    </div>
                </div>
            `;
        });

        this.suggestionsContainer.innerHTML = html;
        this.suggestionsContainer.style.display = 'block';

        // Bind click events to suggestions
        this.bindSuggestionEvents();
    }

    bindSuggestionEvents() {
        const items = this.suggestionsContainer.querySelectorAll('.suggestion-item');
        items.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const url = item.dataset.url;
                if (url) {
                    window.location.href = url;
                }
            });

            item.addEventListener('mouseenter', () => {
                this.clearActiveItem();
                item.classList.add('active');
            });
        });
    }

    handleKeyNavigation(e) {
        const items = this.suggestionsContainer.querySelectorAll('.suggestion-item');
        if (items.length === 0) return;

        const activeItem = this.suggestionsContainer.querySelector('.suggestion-item.active');
        let currentIndex = activeItem ? parseInt(activeItem.dataset.index) : -1;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                currentIndex = Math.min(currentIndex + 1, items.length - 1);
                this.setActiveItem(currentIndex);
                break;

            case 'ArrowUp':
                e.preventDefault();
                currentIndex = Math.max(currentIndex - 1, 0);
                this.setActiveItem(currentIndex);
                break;

            case 'Enter':
                e.preventDefault();
                if (activeItem) {
                    const url = activeItem.dataset.url;
                    if (url) {
                        window.location.href = url;
                    }
                } else {
                    // Submit the form normally
                    this.input.closest('form').submit();
                }
                break;

            case 'Escape':
                this.hideSuggestions();
                this.input.blur();
                break;
        }
    }

    setActiveItem(index) {
        this.clearActiveItem();
        const items = this.suggestionsContainer.querySelectorAll('.suggestion-item');
        if (items[index]) {
            items[index].classList.add('active');
        }
    }

    clearActiveItem() {
        const activeItem = this.suggestionsContainer.querySelector('.suggestion-item.active');
        if (activeItem) {
            activeItem.classList.remove('active');
        }
    }

    highlightQuery(text, query) {
        if (!query) return text;

        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    hideSuggestions() {
        this.suggestionsContainer.style.display = 'none';
        this.suggestionsContainer.innerHTML = '';
    }
}

// Initialize search suggestions when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize for hero search bar
    const heroInput = document.querySelector('.hero .search-bar input[name="q"]');
    const homeSearchInput = document.getElementById('home-search-input');

    if (heroInput || homeSearchInput) {
        const input = heroInput || homeSearchInput;
        if (!input.hasAttribute('data-suggestions-initialized')) {
            new SearchSuggestions(`#${input.id || 'home-search-input'}`);
            input.setAttribute('data-suggestions-initialized', 'true');
        }
    }

    // Initialize for any other search inputs
    const otherSearchInputs = document.querySelectorAll('input[name="q"]:not([data-suggestions-initialized])');
    otherSearchInputs.forEach(input => {
        if (input.id) {
            new SearchSuggestions(`#${input.id}`, null);
            input.setAttribute('data-suggestions-initialized', 'true');
        }
    });
});

// Export for module usage and expose globally
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SearchSuggestions;
}

// Expose globally for dynamic-loading
window.SearchSuggestions = SearchSuggestions;
