/* eslint-env browser */
/* global window, fetch */
// Sistema de Favoritos - Versão Corrigida

// Verificar se já foi carregado
if (typeof window.FavoriteManager !== 'undefined') {
} else {

/**
 * Classe para gerenciar favoritos de forma centralizada
 */
window.FavoriteManager = class FavoriteManager {
    constructor() {
        this.pendingRequests = new Map();
        this.isInitialized = false;
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
                        <button class="favorite-modal-btn favorite-modal-btn-cancel"><i class="fas fa-times"></i> Cancelar</button>
                        <button class="favorite-modal-btn favorite-modal-btn-confirm"><i class="fas fa-trash"></i> Remover</button>
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

        // Apenas o overlay fecha o modal (cancelamento)
        overlay.addEventListener('click', () => {
            if (this._modalResolve) {
                this._modalResolve(false);
            }
            this.hideConfirmModal();
        });
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
            const cancelBtn = modal.querySelector('.favorite-modal-btn-cancel');

            // Salva o resolve para uso em outros métodos (ex: overlay click)
            this._modalResolve = resolve;

            // Remove listeners antigos se existirem
            const newConfirmBtn = confirmBtn.cloneNode(true);
            const newCancelBtn = cancelBtn.cloneNode(true);
            confirmBtn.replaceWith(newConfirmBtn);
            cancelBtn.replaceWith(newCancelBtn);

            // Mostra o modal
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('active'), 10);

            // Adiciona novos listeners
            newConfirmBtn.addEventListener('click', () => {
                this._modalResolve = null;
                this.hideConfirmModal();
                resolve(true);
            });

            newCancelBtn.addEventListener('click', () => {
                this._modalResolve = null;
                this.hideConfirmModal();
                resolve(false);
            });
        });
    }

    /**
     * Esconde o modal de confirmação
     */
    hideConfirmModal() {
        const modal = document.getElementById('favorite-confirm-modal');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => {
                modal.style.display = 'none';
            }, 300);
        }
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
                if (now - cached.timestamp < 30000) { // 30 segundos
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

        // Força atualização visual
        button.offsetHeight; // Trigger reflow
    }

    /**
     * Sincroniza TODOS os botões de um post em TODAS as páginas abertas (usando BroadcastChannel)
     */
    broadcastFavoriteChange(postId, isFavorited) {
        // Atualiza todos os botões na página atual
        const buttons = this.getAllButtons(postId);
        buttons.forEach((btn) => {
            this.updateButtonUI(btn, isFavorited);
        });
    }

    /**
     * Encontra todos os botões de um post específico
     */
    getAllButtons(postId) {
        const buttons = document.querySelectorAll(`button[data-post-id="${postId}"]`);
        return buttons;
    }

    /**
     * Sincroniza todos os botões de um post com o estado do servidor
     * Apenas chama se forceRefresh=true ou se não tiver cache
     */
    async syncButtons(postId, forceRefresh = false) {
        // Se não for forçado e tiver cache válido, usa cache
        if (!forceRefresh) {
            const cacheKey = `status_${postId}`;
            if (this._statusCache && this._statusCache[cacheKey]) {
                const cached = this._statusCache[cacheKey];
                const now = Date.now();
                if (now - cached.timestamp < 30000) {
                    const buttons = this.getAllButtons(postId);
                    buttons.forEach(btn => this.updateButtonUI(btn, cached.value));
                    return cached.value;
                }
            }
        }

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

            // Usa estado do botão ao invés de fazer requisição
            const firstButton = buttons[0];
            const currentStatus = firstButton?.classList.contains('favorited') || false;

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
                const errorText = await response.text();
                console.error(`[FAVORITOS] Erro HTTP ${response.status}: ${errorText}`);
                throw new Error(`Erro HTTP ${response.status}`);
            }

            const data = await response.json();
            if (!data.success) {
                // Mostrar mensagem específica do servidor
                console.error('[FAVORITOS] Falha ao favoritar:', data.message);
                this.showToast(data.message || 'Erro ao atualizar favorito', 'error');
                await this.syncButtons(postId, true);
                buttons.forEach(btn => btn.disabled = false);
                this.pendingRequests.delete(postId);
                return;
            }

            // Atualiza cache local
            const cacheKey = `status_${postId}`;
            if (!this._statusCache) this._statusCache = {};
            this._statusCache[cacheKey] = {
                value: data.is_favorited,
                timestamp: Date.now()
            };

            // Atualiza UI imediatamente usando broadcast para garantir todos os botões
            this.broadcastFavoriteChange(postId, data.is_favorited);

            // Mostra mensagem de sucesso
            this.showToast(
                data.is_favorited ? 'Adicionado aos favoritos!' : 'Removido dos favoritos!',
                'success'
            );

            // Log final para confirmar estado

            // Se estamos na página de perfil e removemos um favorito, recarrega dinamicamente
            if (!data.is_favorited && window.location.pathname.includes('/profile')) {
                if (typeof window.reloadFavoritesSection === 'function') {
                    await window.reloadFavoritesSection();
                }
            }

        } catch (error) {
            console.error('[FAVORITOS] Erro:', error);
            this.showToast(error.message || 'Erro ao atualizar favorito. Tente novamente.', 'error');
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
        // Evita inicialização duplicada
        const now = Date.now();
        if (this.isInitialized && this._lastInit && (now - this._lastInit) < 1000) {
            return;
        }

        this.isInitialized = true;
        this._lastInit = now;

        // Garante que o modal existe
        this.createConfirmModal();

        // NÃO faz syncButtons() no init para evitar rate limit
        // Os botões já vem com o estado correto do servidor (HTML renderizado)
        // Apenas inicializa o cache com o estado atual dos botões
        const buttons = document.querySelectorAll('button[data-post-id]');
        const uniquePostIds = new Set();

        buttons.forEach(btn => {
            const postId = parseInt(btn.dataset.postId);
            if (postId) {
                uniquePostIds.add(postId);
                // Inicializa cache com estado do botão (sem fazer requisição)
                const isFavorited = btn.classList.contains('favorited');
                const cacheKey = `status_${postId}`;
                if (!this._statusCache) this._statusCache = {};
                this._statusCache[cacheKey] = {
                    value: isFavorited,
                    timestamp: Date.now()
                };
            }
        });

    }

    /**
     * Remove um favorito diretamente (usado na página de perfil)
     */
    async remove(postId, skipConfirmation = false) {
        if (this.pendingRequests.has(postId)) {
            return;
        }

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

            // Atualiza cache e UI
            const cacheKey = `status_${postId}`;
            if (!this._statusCache) this._statusCache = {};
            this._statusCache[cacheKey] = {
                value: false,
                timestamp: Date.now()
            };
            // Atualiza todos os botões
            this.broadcastFavoriteChange(postId, false);

            this.showToast('Removido dos favoritos!', 'success');
            this.pendingRequests.delete(postId);
            return true;

        } catch (error) {
            console.error(`[FAVORITOS] ❌ Erro ao remover favorito ${postId}:`, error);
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

    document.addEventListener('pageLoaded', () => favoriteManager.init());
}
