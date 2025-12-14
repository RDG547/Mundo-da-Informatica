/* eslint-env browser */
/* global window, fetch */
// Sistema de Favoritos - Versão Corrigida

// Verificar se já foi carregado
if (typeof window.FavoriteManager !== 'undefined') {
    console.log('favorites.js já carregado, ignorando redeclaração');
} else {

/**
 * Classe para gerenciar favoritos de forma centralizada
 */
window.FavoriteManager = class FavoriteManager {
    constructor() {
        this.pendingRequests = new Map();
        this.createConfirmModal();
    }

    /**
     * Cria o modal de confirmação estilizado
     */
    createConfirmModal() {
        // Remove modal existente se houver
        const existingModal = document.getElementById('favorite-confirm-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const modalHTML = `
            <div id="favorite-confirm-modal" class="favorite-modal" style="display: none;">
                <div class="favorite-modal-overlay"></div>
                <div class="favorite-modal-content">
                    <div class="favorite-modal-icon">
                        <i class="fas fa-star"></i>
                    </div>
                    <h3 class="favorite-modal-title">Remover dos Favoritos?</h3>
                    <p class="favorite-modal-text">Tem certeza que deseja remover este post dos seus favoritos?</p>
                    <div class="favorite-modal-buttons">
                        <button class="favorite-modal-btn favorite-modal-btn-cancel">Cancelar</button>
                        <button class="favorite-modal-btn favorite-modal-btn-confirm">Remover</button>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.attachModalEvents();
    }

    /**
     * Anexa eventos ao modal
     */
    attachModalEvents() {
        const modal = document.getElementById('favorite-confirm-modal');
        const overlay = modal.querySelector('.favorite-modal-overlay');
        const cancelBtn = modal.querySelector('.favorite-modal-btn-cancel');

        overlay.addEventListener('click', () => this.hideConfirmModal());
        cancelBtn.addEventListener('click', () => this.hideConfirmModal());
    }

    /**
     * Mostra o modal de confirmação
     */
    showConfirmModal() {
        return new Promise((resolve) => {
            // Garante que o modal existe antes de exibir
            let modal = document.getElementById('favorite-confirm-modal');
            if (!modal) {
                this.createConfirmModal();
                modal = document.getElementById('favorite-confirm-modal');
            }

            const confirmBtn = modal.querySelector('.favorite-modal-btn-confirm');

            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('active'), 10);

            const handleConfirm = () => {
                confirmBtn.removeEventListener('click', handleConfirm);
                this.hideConfirmModal();
                resolve(true);
            };

            confirmBtn.addEventListener('click', handleConfirm);
        });
    }

    /**
     * Esconde o modal de confirmação
     */
    hideConfirmModal() {
        const modal = document.getElementById('favorite-confirm-modal');
        modal.classList.remove('active');
        setTimeout(() => modal.style.display = 'none', 300);
    }

    /**
     * Busca o estado atual de um favorito no servidor (com rate limiting)
     */
    async getStatus(postId) {
        try {
            // Rate limiting local - evita múltiplas chamadas
            const now = Date.now();
            const cacheKey = `status_${postId}`;
            
            if (this._statusCache && this._statusCache[cacheKey]) {
                const cached = this._statusCache[cacheKey];
                if (now - cached.timestamp < 2000) { // 2 segundos
                    return cached.value;
                }
            }
            
            const response = await fetch(`/api/check-favorite/${postId}`, {
                cache: 'force-cache',
                headers: { 'Cache-Control': 'max-age=2' }
            });
            if (!response.ok) throw new Error('Erro na requisição');
            const data = await response.json();
            
            // Salvar em cache local
            if (!this._statusCache) this._statusCache = {};
            this._statusCache[cacheKey] = {
                value: data.is_favorited,
                timestamp: now
            };
            
            return data.is_favorited;
        } catch (error) {
            return null;
        }
    }

    /**
     * Atualiza a aparência de um botão com base no estado
     */
    updateButtonUI(button, isFavorited) {
        const icon = button.querySelector('i');

        if (isFavorited) {
            button.classList.add('favorited');
            if (icon) {
                icon.classList.remove('far');
                icon.classList.add('fas');
            }
            button.title = 'Remover dos favoritos';
        } else {
            button.classList.remove('favorited');
            if (icon) {
                icon.classList.remove('fas');
                icon.classList.add('far');
            }
            button.title = 'Adicionar aos favoritos';
        }
    }

    /**
     * Encontra todos os botões de um post específico
     */
    getAllButtons(postId) {
        return document.querySelectorAll(`button[data-post-id="${postId}"]`);
    }

    /**
     * Sincroniza todos os botões de um post com o estado do servidor
     */
    async syncButtons(postId, forceRefresh = false) {
        const status = await this.getStatus(postId);
        if (status === null) return;

        const buttons = this.getAllButtons(postId);
        buttons.forEach(btn => this.updateButtonUI(btn, status));

        return status;
    }

    /**
     * Mostra toast de notificação
     */
    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `favorite-toast favorite-toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
            <span>${message}</span>
        `;
        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Alterna o estado de favorito de um post
     */
    async toggle(postId) {
        if (this.pendingRequests.has(postId)) return;

        const buttons = this.getAllButtons(postId);
        buttons.forEach(btn => btn.disabled = true);

        try {
            this.pendingRequests.set(postId, true);

            // Busca estado atual FRESCO do servidor
            const currentStatus = await this.getStatus(postId);
            if (currentStatus === null) {
                throw new Error('Não foi possível verificar o estado atual');
            }

            // Se está nos favoritos, pede confirmação
            if (currentStatus) {
                const confirmed = await this.showConfirmModal();
                if (!confirmed) {
                    buttons.forEach(btn => btn.disabled = false);
                    this.pendingRequests.delete(postId);
                    return;
                }
            }

            // Define a ação
            const action = currentStatus ? 'unfavorite' : 'favorite';
            const url = `/${action}/${postId}`;

            // Envia requisição
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                cache: 'no-cache'
            });

            if (!response.ok) {
                throw new Error(`Erro HTTP ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.message || 'Erro desconhecido');
            }

            // Atualiza UI imediatamente
            buttons.forEach(btn => this.updateButtonUI(btn, data.is_favorited));

            // Mostra mensagem de sucesso
            this.showToast(
                data.is_favorited ? 'Adicionado aos favoritos!' : 'Removido dos favoritos!',
                'success'
            );

            // Aguarda e sincroniza com servidor para garantir consistência
            await new Promise(resolve => setTimeout(resolve, 300));
            const finalStatus = await this.syncButtons(postId, true);

            // Se estamos na página de perfil e removemos um favorito, recarrega
            if (!finalStatus && window.location.pathname.includes('/profile')) {
                setTimeout(() => window.location.reload(), 500);
            }

        } catch (error) {
            this.showToast('Erro ao atualizar favorito. Tente novamente.', 'error');
            await this.syncButtons(postId, true);
        } finally {
            buttons.forEach(btn => btn.disabled = false);
            this.pendingRequests.delete(postId);
        }
    }

    /**
     * Inicializa todos os botões na página
     */
    init() {
        // Garante que o modal existe
        this.createConfirmModal();

        // Seleciona apenas BOTÕES com data-post-id para evitar conflitos com outros elementos
        const buttons = document.querySelectorAll('button[data-post-id]');
        const uniquePostIds = new Set();

        buttons.forEach(btn => {
            const postId = parseInt(btn.dataset.postId);
            if (postId) uniquePostIds.add(postId);
        });

        uniquePostIds.forEach(postId => this.syncButtons(postId));
    }

    /**
     * Remove um favorito diretamente (usado na página de perfil)
     */
    async remove(postId, skipConfirmation = false) {
        if (this.pendingRequests.has(postId)) return;

        try {
            this.pendingRequests.set(postId, true);

            // Pede confirmação se não for skip
            if (!skipConfirmation) {
                const confirmed = await this.showConfirmModal();
                if (!confirmed) {
                    this.pendingRequests.delete(postId);
                    return false;
                }
            }

            // Envia requisição de remoção
            const response = await fetch(`/unfavorite/${postId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                cache: 'no-cache'
            });

            if (!response.ok) {
                throw new Error(`Erro HTTP ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.message || 'Erro ao remover favorito');
            }

            this.showToast('Removido dos favoritos!', 'success');
            this.pendingRequests.delete(postId);
            return true;

        } catch (error) {
            this.showToast('Erro ao remover favorito. Tente novamente.', 'error');
            this.pendingRequests.delete(postId);
            return false;
        }
    }
};

} // Fim da verificação de carregamento

// Instância global
if (typeof window.FavoriteManager !== 'undefined') {
    const favoriteManager = new window.FavoriteManager();
    window.favoriteManager = favoriteManager;

    // Função global para ser chamada pelos botões HTML
    window.toggleFavorite = function(postId) {
        favoriteManager.toggle(postId);
    };

    // Inicializa quando o DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => favoriteManager.init());
    } else {
        favoriteManager.init();
    }
}
