/* global document, clearTimeout, setTimeout */

/**
 * Adiciona delay suave ao fechar dropdowns
 * Quando o mouse sai do dropdown, espera 300ms antes de fechar
 */

document.addEventListener('DOMContentLoaded', function() {
    const dropdowns = document.querySelectorAll('.dropdown');

    dropdowns.forEach(dropdown => {
        let closeTimer = null;

        // Quando o mouse entra no dropdown
        dropdown.addEventListener('mouseenter', function() {
            // Cancela qualquer timer de fechamento pendente
            if (closeTimer) {
                clearTimeout(closeTimer);
                closeTimer = null;
            }
            // Adiciona classe para mostrar o menu
            this.classList.add('show');
        });

        // Quando o mouse sai do dropdown
        dropdown.addEventListener('mouseleave', function() {
            const self = this;
            // Define um delay de 300ms antes de fechar
            closeTimer = setTimeout(function() {
                self.classList.remove('show');
            }, 300); // 300ms de delay
        });

        // Previne o fechamento se o mouse mover para dentro do menu
        const dropdownMenu = dropdown.querySelector('.dropdown-menu');
        if (dropdownMenu) {
            dropdownMenu.addEventListener('mouseenter', function() {
                if (closeTimer) {
                    clearTimeout(closeTimer);
                    closeTimer = null;
                }
            });
        }
    });
});
