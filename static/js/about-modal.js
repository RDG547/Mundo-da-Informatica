// ==========================================
// MODAL DE CONTRIBUIÇÃO
// ==========================================

(function() {
    // Evitar inicialização duplicada
    if (window._aboutModalInitialized) return;
    window._aboutModalInitialized = true;

    function initContributeModal() {
        const modal = document.getElementById('contributeModal');
        const openBtn = document.getElementById('openContributeModal');
        const closeBtn = document.getElementById('closeContributeModal');
        const overlay = modal?.querySelector('.contribute-modal-overlay');

        if (!modal) return;

        // Função para abrir o modal
        function openModal(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        // Função para fechar o modal
        function closeModal() {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }

        // Event listeners
        if (openBtn && !openBtn.hasAttribute('data-modal-init')) {
            openBtn.setAttribute('data-modal-init', 'true');
            openBtn.addEventListener('click', openModal);
        }

        if (closeBtn && !closeBtn.hasAttribute('data-modal-init')) {
            closeBtn.setAttribute('data-modal-init', 'true');
            closeBtn.addEventListener('click', closeModal);
        }

        if (overlay && !overlay.hasAttribute('data-modal-init')) {
            overlay.setAttribute('data-modal-init', 'true');
            overlay.addEventListener('click', closeModal);
        }

        // Fechar com ESC - handler global único
        if (!window._contributeModalEscHandler) {
            window._contributeModalEscHandler = function(e) {
                if (e.key === 'Escape') {
                    const activeModal = document.getElementById('contributeModal');
                    if (activeModal?.classList.contains('active')) {
                        activeModal.classList.remove('active');
                        document.body.style.overflow = '';
                    }
                }
            };
            document.addEventListener('keydown', window._contributeModalEscHandler);
        }

        // Restaurar scroll quando clicar em links dentro do modal
        const modalLinks = modal.querySelectorAll('a[href]');
        modalLinks.forEach(link => {
            if (!link.hasAttribute('data-modal-link-init')) {
                link.setAttribute('data-modal-link-init', 'true');
                link.addEventListener('click', function() {
                    document.body.style.overflow = '';
                    modal.classList.remove('active');
                });
            }
        });
    }

    // Inicializar quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initContributeModal);
    } else {
        initContributeModal();
    }
})();
