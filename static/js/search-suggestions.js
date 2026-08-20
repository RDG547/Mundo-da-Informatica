/**
 * Search Suggestions Functionality
 * Provides real-time search suggestions for categories and posts
 */

// Verificar se já foi carregado
if (typeof window.SearchSuggestions !== 'undefined') {
} else {

window.SearchSuggestions = class SearchSuggestions {
    constructor(inputSelector, suggestionsSelector) {
        this.input = document.querySelector(inputSelector);
        this.suggestionsContainer = document.querySelector(suggestionsSelector);

        if (!this.input) {
            return;
        }

        if (this.input.id === 'home-search-input' || this.input.dataset.searchSuggestionsSkip === 'true') {
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
            const fileTypes = Array.isArray(suggestion.file_types)
                ? suggestion.file_types.filter(Boolean).join('/')
                : '';
            html += `
                <div class="suggestion-item ${typeClass}" data-index="${index}" data-url="${suggestion.url}">
                    ${this.renderSuggestionLeading(suggestion)}
                    <div class="suggestion-content">
                        <div class="suggestion-title">${this.highlightQuery(suggestion.title, this.input.value)}</div>
                        ${fileTypes ? `<span class="suggestion-file-types">${this.escapeHtml(fileTypes)}</span>` : ''}
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

    renderSuggestionLeading(suggestion) {
        if (suggestion.type === 'post' && suggestion.image_url) {
            return `
                <div class="suggestion-thumb">
                    <img src="${suggestion.image_url}" alt="${this.escapeHtml(suggestion.title)}" loading="lazy">
                </div>
            `;
        }

        return `
            <div class="suggestion-icon">
                <i class="${suggestion.icon}"></i>
            </div>
        `;
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

    escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    hideSuggestions() {
        this.suggestionsContainer.style.display = 'none';
        this.suggestionsContainer.innerHTML = '';
    }
};

} // Fim da verificação de carregamento

// Initialize search suggestions when DOM is loaded
function initializeSearchSuggestions() {
    if (typeof window.SearchSuggestions === 'undefined') {
        return;
    }

        const homeSearchInput = document.getElementById('home-search-input');
        if (homeSearchInput) {
            homeSearchInput.setAttribute('data-search-suggestions-skip', 'true');
            homeSearchInput.setAttribute('data-suggestions-initialized', 'true');
            return;
        }

        // Initialize for hero search bar
        const heroInput = document.querySelector('.hero .search-bar input[name="q"]:not(#home-search-input)');

        if (heroInput) {
            const input = heroInput;
            if (!input.hasAttribute('data-suggestions-initialized')) {
                new window.SearchSuggestions(`#${input.id || 'home-search-input'}`);
                input.setAttribute('data-suggestions-initialized', 'true');
            }
        }

        // Initialize for any other search inputs
        const otherSearchInputs = document.querySelectorAll('input[name="q"]:not([data-suggestions-initialized]):not(#home-search-input)');
        otherSearchInputs.forEach(input => {
            if (input.id) {
                new window.SearchSuggestions(`#${input.id}`, null);
                input.setAttribute('data-suggestions-initialized', 'true');
            }
        });

}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSearchSuggestions);
} else {
    initializeSearchSuggestions();
}

document.addEventListener('pageLoaded', initializeSearchSuggestions);
window.initializeSearchSuggestions = initializeSearchSuggestions;
