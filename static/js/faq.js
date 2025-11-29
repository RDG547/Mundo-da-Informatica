/**
 * FAQ Page JavaScript
 * Handles interactive functionality for the FAQ page
 */

// Simple and reliable FAQ toggle functionality
function toggleFAQ(element) {
    console.log('toggleFAQ called with:', element);

    const faqItem = element.closest('.faq-item');
    if (!faqItem) {
        console.error('FAQ item not found');
        return;
    }

    const faqAnswer = faqItem.querySelector('.faq-answer');
    const faqToggle = faqItem.querySelector('.faq-toggle i');

    if (!faqAnswer || !faqToggle) {
        console.error('FAQ answer or toggle not found');
        return;
    }

    console.log('Current state:', faqItem.classList.contains('active'));

    // Close other open FAQs (accordion behavior)
    document.querySelectorAll('.faq-item').forEach(item => {
        if (item !== faqItem && item.classList.contains('active')) {
            closeFAQItem(item);
        }
    });

    // Toggle current FAQ
    if (faqItem.classList.contains('active')) {
        closeFAQItem(faqItem);
    } else {
        openFAQItem(faqItem);
    }
}

function openFAQItem(faqItem) {
    console.log('Opening FAQ item');

    const faqAnswer = faqItem.querySelector('.faq-answer');
    const faqToggle = faqItem.querySelector('.faq-toggle i');

    if (!faqAnswer || !faqToggle) return;

    faqItem.classList.add('active');

    // Remove any inline styles that might interfere
    faqAnswer.style.removeProperty('display');
    faqAnswer.style.removeProperty('max-height');
    faqAnswer.style.removeProperty('opacity');

    // Force reflow and let CSS handle the animation
    faqAnswer.offsetHeight;

    // Update toggle icon
    faqToggle.classList.remove('fa-plus');
    faqToggle.classList.add('fa-minus');

    console.log('FAQ item opened');
}

function closeFAQItem(faqItem) {
    console.log('Closing FAQ item');

    const faqAnswer = faqItem.querySelector('.faq-answer');
    const faqToggle = faqItem.querySelector('.faq-toggle i');

    if (!faqAnswer || !faqToggle) return;

    faqItem.classList.remove('active');

    // Update toggle icon
    faqToggle.classList.remove('fa-minus');
    faqToggle.classList.add('fa-plus');

    console.log('FAQ item closed');
}

// Initialize FAQ functionality
function initializeFAQ() {
    console.log('Initializing FAQ functionality');

    const faqItems = document.querySelectorAll('.faq-item');
    console.log('Found FAQ items:', faqItems.length);

    // Ensure all FAQ items start in closed state
    faqItems.forEach(item => {
        item.classList.remove('active');
        const answer = item.querySelector('.faq-answer');
        const icon = item.querySelector('.faq-toggle i');

        if (answer) {
            answer.style.removeProperty('display');
            answer.style.removeProperty('max-height');
            answer.style.removeProperty('opacity');
        }

        if (icon) {
            icon.classList.remove('fa-minus');
            icon.classList.add('fa-plus');
        }
    });

    console.log('FAQ initialization complete');
}

// Mark answer as helpful
function markHelpful(button) {
    const icon = button.querySelector('i');
    const text = button.childNodes[1];

    if (button.classList.contains('marked')) {
        button.classList.remove('marked');
        icon.classList.remove('fas', 'fa-thumbs-up');
        icon.classList.add('far', 'fa-thumbs-up');
        text.textContent = ' Útil';
    } else {
        button.classList.add('marked');
        icon.classList.remove('far', 'fa-thumbs-up');
        icon.classList.add('fas', 'fa-thumbs-up');
        text.textContent = ' Obrigado!';

        // Show brief success message
        setTimeout(() => {
            text.textContent = ' Útil';
        }, 2000);
    }
}

// FAQ Search Functionality
function initializeFAQSearch() {
    const faqSearch = document.getElementById('faq-search');
    const searchClear = document.getElementById('search-clear');
    const faqItems = document.querySelectorAll('.faq-item');

    if (!faqSearch) return;

    // Search input handler
    faqSearch.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        let hasResults = false;

        if (searchTerm === '') {
            // Show all items if search is empty
            faqItems.forEach(item => {
                item.style.display = 'block';
            });
            hasResults = true;
        } else {
            // Filter items based on search term
            faqItems.forEach(item => {
                const keywords = item.dataset.keywords || '';
                const question = item.querySelector('.faq-question h3')?.textContent || '';
                const answer = item.querySelector('.faq-answer p')?.textContent || '';

                const searchContent = `${keywords} ${question} ${answer}`.toLowerCase();

                if (searchContent.includes(searchTerm)) {
                    item.style.display = 'block';
                    hasResults = true;
                } else {
                    item.style.display = 'none';
                }
            });
        }

        // Show/hide clear button
        if (searchClear) {
            searchClear.style.display = searchTerm ? 'block' : 'none';
        }

        // Show no results message if needed
        showNoResultsMessage(!hasResults);
    });

    // Clear search
    if (searchClear) {
        searchClear.addEventListener('click', function() {
            faqSearch.value = '';
            faqSearch.dispatchEvent(new Event('input'));
            faqSearch.focus();
        });
    }

    // Search suggestions
    document.querySelectorAll('.search-suggestion').forEach(suggestion => {
        suggestion.addEventListener('click', function() {
            const searchTerm = this.dataset.search;
            faqSearch.value = searchTerm;
            faqSearch.dispatchEvent(new Event('input'));
            faqSearch.focus();
        });
    });
}

// Show/hide no results message
function showNoResultsMessage(show) {
    let noResultsMsg = document.querySelector('.no-results-message');

    if (show && !noResultsMsg) {
        noResultsMsg = document.createElement('div');
        noResultsMsg.className = 'no-results-message';
        noResultsMsg.innerHTML = `
            <div class="no-results-content">
                <i class="fas fa-search"></i>
                <h4>Nenhum resultado encontrado</h4>
                <p>Tente usar palavras-chave diferentes ou entre em contato conosco.</p>
                <a href="/contact" class="btn btn-gradient primary">
                    <i class="fas fa-envelope"></i> Entrar em Contato
                </a>
            </div>
        `;

        const faqContainer = document.querySelector('.faq-container');
        if (faqContainer) {
            faqContainer.appendChild(noResultsMsg);
        }

        // Add CSS for no results message
        if (!document.getElementById('no-results-style')) {
            const style = document.createElement('style');
            style.id = 'no-results-style';
            style.textContent = `
                .no-results-message {
                    text-align: center;
                    padding: 3rem;
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                    border: 1px solid #e2e8f0;
                    margin-top: 2rem;
                }

                .no-results-content i {
                    font-size: 3rem;
                    color: #cbd5e0;
                    margin-bottom: 1rem;
                }

                .no-results-content h4 {
                    font-size: 1.4rem;
                    color: #4a5568;
                    margin-bottom: 0.5rem;
                }

                .no-results-content p {
                    color: #718096;
                    margin-bottom: 1.5rem;
                }
            `;
            document.head.appendChild(style);
        }
    } else if (!show && noResultsMsg) {
        noResultsMsg.remove();
    }
}

// Open live chat (placeholder function)
function openLiveChat() {
    alert('O chat online estará disponível em breve! Por enquanto, use nosso formulário de contato.');
}

// Initialize FAQ functionality when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, checking for FAQ elements');
    if (document.querySelector('.faq-section') || document.querySelector('.faq-item')) {
        console.log('FAQ elements found, initializing');
        initializeFAQ();
        initializeFAQSearch();
    }
});

// Handle page refresh and navigation
window.addEventListener('load', function() {
    console.log('Window loaded, checking for FAQ elements');
    if (document.querySelector('.faq-section') || document.querySelector('.faq-item')) {
        console.log('FAQ elements found on load, reinitializing');
        initializeFAQ();
    }
});

// Handle dynamic content loading
document.addEventListener('pageLoaded', function() {
    console.log('Page loaded event, checking for FAQ elements');
    if (document.querySelector('.faq-section') || document.querySelector('.faq-item')) {
        setTimeout(() => {
            console.log('Delayed FAQ initialization');
            initializeFAQ();
            initializeFAQSearch();
        }, 100);
    }
});

// Handle browser back/forward navigation
window.addEventListener('popstate', function() {
    console.log('Popstate event, checking for FAQ elements');
    if (document.querySelector('.faq-section') || document.querySelector('.faq-item')) {
        setTimeout(() => {
            console.log('Delayed FAQ reinitialization on popstate');
            initializeFAQ();
        }, 100);
    }
});

// Export functions for global access
window.toggleFAQ = toggleFAQ;
window.markHelpful = markHelpful;
window.openLiveChat = openLiveChat;
window.initializeFAQ = initializeFAQ;

// Initialize immediately if DOM is already ready
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    console.log('Script loaded after DOM ready, checking for FAQ elements');
    if (document.querySelector('.faq-section') || document.querySelector('.faq-item')) {
        console.log('FAQ elements found, initializing immediately');
        initializeFAQ();
    }
}
