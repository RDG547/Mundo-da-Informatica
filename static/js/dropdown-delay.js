/* global document, clearTimeout, setTimeout */

/**
 * Adiciona delay suave ao fechar dropdowns
 * Quando o mouse sai do dropdown, espera 300ms antes de fechar
 */

function initializeDropdownDelay() {
    document.querySelectorAll('.dropdown').forEach((dropdown) => {
        if (dropdown.dataset.dropdownDelayInitialized === 'true') {
            return;
        }

        dropdown.dataset.dropdownDelayInitialized = 'true';
        let closeTimer = null;

        dropdown.addEventListener('mouseenter', function () {
            if (window.matchMedia('(max-width: 1100px)').matches) return;
            if (closeTimer) {
                clearTimeout(closeTimer);
                closeTimer = null;
            }
            this.classList.add('show');
        });

        dropdown.addEventListener('mouseleave', function () {
            if (window.matchMedia('(max-width: 1100px)').matches) return;
            const self = this;
            closeTimer = setTimeout(function () {
                self.classList.remove('show');
            }, 300);
        });

        const dropdownMenu = dropdown.querySelector('.dropdown-menu');
        if (dropdownMenu) {
            dropdownMenu.addEventListener('mouseenter', function () {
                if (closeTimer) {
                    clearTimeout(closeTimer);
                    closeTimer = null;
                }
            });
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDropdownDelay);
} else {
    initializeDropdownDelay();
}

document.addEventListener('pageLoaded', initializeDropdownDelay);
window.initializeDropdownDelay = initializeDropdownDelay;
