// Sistema de controle de limites de download

// Adicionar CSS para botão X de remover download
(function addDownloadRemoveButtonStyles() {
    if (document.getElementById('download-remove-btn-styles')) return;

    const style = document.createElement('style');
    style.id = 'download-remove-btn-styles';
    style.textContent = `
        .download-remove-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            border: none;
            background: rgba(220, 53, 69, 0.9);
            color: white;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        .download-remove-btn:hover {
            background: #dc3545;
            transform: scale(1.1);
            box-shadow: 0 4px 12px rgba(220, 53, 69, 0.4);
        }
        .download-remove-btn i {
            font-size: 14px;
        }
        .download-card {
            position: relative;
        }
    `;
    document.head.appendChild(style);
})();

// Modal de limite excedido
function createDownloadLimitModal() {
    const modalHTML = `
        <div id="downloadLimitModal" class="download-limit-modal" style="display: none;">
            <div class="download-limit-overlay"></div>
            <div class="download-limit-content">
                <div class="download-limit-icon">
                    <i class="fas fa-exclamation-circle"></i>
                </div>
                <h2 class="download-limit-title">Limite de Downloads Atingido!</h2>
                <p class="download-limit-message" id="limitMessage"></p>
                <div class="download-limit-countdown">
                    <div class="countdown-circle">
                        <svg class="countdown-svg" width="120" height="120">
                            <circle class="countdown-bg" cx="60" cy="60" r="54"></circle>
                            <circle class="countdown-progress" cx="60" cy="60" r="54"></circle>
                        </svg>
                        <div class="countdown-number" id="countdownNumber">5</div>
                    </div>
                    <p class="countdown-text">Redirecionando para planos em <span id="countdownText">5</span> segundos</p>
                </div>
                <div class="download-limit-actions">
                    <button onclick="redirectToPlans()" class="btn btn-gradient primary">
                        <i class="fas fa-crown"></i> Ver Planos Agora
                    </button>
                    <button onclick="closeDownloadLimitModal()" class="btn btn-outline">
                        <i class="fas fa-times"></i> Fechar
                    </button>
                </div>
            </div>
        </div>
    `;

    // Adicionar modal ao body se não existir
    if (!document.getElementById('downloadLimitModal')) {
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }
}

// Mostrar modal de limite excedido (SEM redirecionamento automático)
function showDownloadLimitModal(message) {
    createDownloadLimitModal();

    const modal = document.getElementById('downloadLimitModal');
    const messageEl = document.getElementById('limitMessage');
    const countdownContainer = modal.querySelector('.download-limit-countdown');

    messageEl.textContent = message;

    // Ocultar contador regressivo (usuário decide se quer ver planos)
    if (countdownContainer) {
        countdownContainer.style.display = 'none';
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Mostrar modal de solicitação de conteúdo (para plano free)
function showContentRequestModal(message) {
    createDownloadLimitModal();

    const modal = document.getElementById('downloadLimitModal');
    const titleEl = modal.querySelector('.download-limit-title');
    const messageEl = document.getElementById('limitMessage');
    const iconEl = modal.querySelector('.download-limit-icon i');
    const countdownContainer = modal.querySelector('.download-limit-countdown');

    // Personalizar para solicitação de conteúdo
    titleEl.textContent = 'Solicitação de Conteúdo Restrita';
    messageEl.textContent = message;
    iconEl.className = 'fas fa-envelope-open-text'; // Ícone diferente

    // Ocultar contador regressivo
    if (countdownContainer) {
        countdownContainer.style.display = 'none';
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Fechar modal
// eslint-disable-next-line no-unused-vars
function closeDownloadLimitModal() {
    const modal = document.getElementById('downloadLimitModal');
    if (modal) {
        // Limpar interval se existir
        if (modal.dataset.interval) {
            clearInterval(parseInt(modal.dataset.interval));
        }
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Redirecionar para página de planos
function redirectToPlans() {
    window.location.href = '/plans';
}

// Verificar limite de downloads antes de baixar
async function checkDownloadLimit() {
    try {
        const response = await fetch('/check-download-limit');
        const data = await response.json();

        if (!data.can_download) {
            let message = '';
            const periodText = data.period === 'daily' ? 'diários' : data.period === 'weekly' ? 'semanais' : '';

            if (data.plan === 'free') {
                message = `Você atingiu o limite de ${data.limit} download${data.limit > 1 ? 's' : ''} ${periodText} do plano gratuito. Faça upgrade para continuar baixando!`;
            } else if (data.plan === 'premium') {
                message = `Você atingiu o limite de ${data.limit} downloads ${periodText} do plano Premium. Considere o plano VIP para downloads ilimitados!`;
            }

            showDownloadLimitModal(message);
            return false;
        }

        return true;
    } catch (error) {
        console.error('Erro ao verificar limite:', error);
        return true; // Em caso de erro, permitir download
    }
}

// Interceptar cliques em botões de download (GLOBAL para ser chamado pelo Dynamic Loading)
window.setupDownloadButtons = function setupDownloadButtons() {
    // Selecionar todos os botões de download - APENAS rotas /download/
    const downloadButtons = document.querySelectorAll('a[href*="/download/"], .download-btn[href*="/download/"], [data-action="download"][href*="/download/"]');

    console.log(`[DOWNLOAD-CONTROL] Encontrados ${downloadButtons.length} botões de download`);
    downloadButtons.forEach(btn => console.log('[DOWNLOAD-CONTROL] Botão:', btn.href, btn.className));

    downloadButtons.forEach(button => {
        // Verificar se já foi processado (evita duplicação)
        if (button.dataset.downloadControlled === 'true') {
            console.log('[DOWNLOAD-CONTROL] Botão já controlado:', button.href);
            return;
        }

        // Marcar como processado
        button.dataset.downloadControlled = 'true';
        console.log('[DOWNLOAD-CONTROL] ✅ Listener adicionado ao botão:', button.href);

        // Adicionar listener com PREVENÇÃO IMEDIATA
        button.addEventListener('click', async function(e) {
            console.log('[DOWNLOAD-CONTROL] 🎯 CLICK INTERCEPTADO!', button.href);

            // SEMPRE prevenir comportamento padrão primeiro
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation(); // Impede TODOS os outros handlers

            // Retornar false explicitamente
            try {
                // Prevenir múltiplos cliques
                if (button.dataset.downloading === 'true') {
                    return false;
                }

                // Verificar se o usuário está logado
                const isAuthenticated = document.body.dataset.authenticated === 'true';

                if (!isAuthenticated) {
                    alert('Você precisa estar logado para fazer downloads!');
                    window.location.href = '/login';
                    return false;
                }

                // Marcar como processando
                button.dataset.downloading = 'true';

                // VERIFICAR LIMITE PRIMEIRO, antes de qualquer navegação
                const canDownload = await checkDownloadLimit();

                if (!canDownload) {
                    console.log('[DOWNLOAD] Limite atingido, bloqueando download');
                    button.dataset.downloading = 'false';
                    return false; // Modal já foi exibido, não fazer nada mais
                }

                console.log('[DOWNLOAD] Limite OK, redirecionando para download');

                // Apenas se passou na verificação, fazer navegação manual
                const downloadUrl = button.href || button.dataset.href;
                if (downloadUrl) {
                    window.location.href = downloadUrl;

                    // Atualizar histórico de download após 1 segundo
                    setTimeout(() => {
                        refreshDownloadHistory();
                    }, 1000);
                }

                // Liberar botão após navegação
                setTimeout(() => {
                    button.dataset.downloading = 'false';
                }, 2000);
            } catch (error) {
                console.error('[DOWNLOAD-CONTROL] Erro:', error);
                button.dataset.downloading = 'false';
            }

            return false;
        }, true); // useCapture=true para garantir execução antes de outros handlers
    });
}

// Função para limpar histórico de downloads
// eslint-disable-next-line no-unused-vars
function confirmClearHistory() {
    // Criar modal de confirmação
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 10000;';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    modalContent.style.cssText = 'background: white; padding: 2rem; border-radius: 10px; max-width: 500px; width: 90%; box-shadow: 0 10px 40px rgba(0,0,0,0.3);';

    modalContent.innerHTML = `
        <div style="text-align: center;">
            <div style="font-size: 3rem; color: #dc3545; margin-bottom: 1rem;">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <h3 style="margin-bottom: 1rem; color: #333;">Limpar Histórico</h3>
            <p style="color: #666; margin-bottom: 2rem;">
                Tem certeza que deseja limpar todo o histórico de downloads?<br>
                <strong>Esta ação não pode ser desfeita.</strong>
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center;">
                <button class="btn-cancel" style="padding: 0.75rem 2rem; border: none; background: #6c757d; color: white; border-radius: 5px; cursor: pointer; font-size: 1rem;">
                    <i class="fas fa-times"></i> Cancelar
                </button>
                <button class="btn-confirm" style="padding: 0.75rem 2rem; border: none; background: #dc3545; color: white; border-radius: 5px; cursor: pointer; font-size: 1rem;">
                    <i class="fas fa-trash"></i> Confirmar
                </button>
            </div>
        </div>
    `;

    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    // Botão cancelar
    modalContent.querySelector('.btn-cancel').addEventListener('click', () => {
        modal.remove();
    });

    // Botão confirmar
    modalContent.querySelector('.btn-confirm').addEventListener('click', async () => {
        const confirmBtn = modalContent.querySelector('.btn-confirm');
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Limpando...';

        try {
            const response = await fetch('/clear-download-history', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                modal.remove();
                showToast(data.message || 'Histórico limpo com sucesso!', 'success');

                // Atualizar seção completa de histórico (igual aos favoritos)
                reloadDownloadHistorySection();
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            console.error('Erro ao limpar histórico:', error);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Confirmar';
            showToast('Erro ao limpar histórico. Tente novamente.', 'error');
        }
    });

    // Fechar ao clicar fora
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Função para recarregar TODA a seção de histórico (similar ao reloadFavoritesSection)
async function reloadDownloadHistorySection() {
    console.log('[DOWNLOAD] 🔄 Recarregando seção de histórico...');

    try {
        const response = await fetch('/api/download-history');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.message || 'Erro ao carregar histórico');
        }

        const historySection = document.getElementById('download-history-section');
        if (!historySection) {
            console.warn('[DOWNLOAD] ⚠️ Seção de histórico não encontrada');
            return;
        }

        // Se não há downloads, mostra mensagem vazia
        if (!data.downloads || data.downloads.length === 0) {
            historySection.innerHTML = `
                <div class="profile-card-header">
                    <div class="profile-card-icon">
                        <i class="fas fa-download"></i>
                    </div>
                    <div>
                        <h2 class="profile-card-title">Histórico de Downloads</h2>
                        <p class="profile-card-subtitle">Últimos arquivos que você baixou</p>
                    </div>
                </div>
                <div class="empty-state">
                    <i class="fas fa-download" style="font-size: 3rem; color: #ddd; margin-bottom: 1rem;"></i>
                    <p>Você ainda não tem downloads registrados.</p>
                    <p class="text-muted">Seus downloads aparecerão aqui!</p>
                </div>
            `;
            console.log('[DOWNLOAD] ✅ Seção vazia renderizada');
            return;
        }

        // Reconstrói o HTML do histórico
        let downloadsHTML = '';
        data.downloads.forEach(download => {
            function getImgUrl(path, folder) {
                if (!path || path === 'default.jpg') return `/static/images/${folder}/default.jpg`;
                if (path.startsWith('http://') || path.startsWith('https://')) return path;
                return `/static/uploads/${folder}/${path}`;
            }

            const postImgUrl = getImgUrl(download.post_image, 'posts');
            const hasImage = download.post_image && download.post_image !== 'default.jpg';

            // Large image removed - only small thumb next to title

            const thumbHtml = hasImage
                ? `<img src="${postImgUrl}" alt="" class="download-title-thumb" onerror="this.style.display='none'">`
                : `<div class="download-title-thumb download-title-thumb-placeholder"><i class="fas fa-file-alt"></i></div>`;

            const linkHtml = download.category_slug
                ? `<a href="/categoria/${download.category_slug}/${download.post_slug}">${download.post_title}</a>`
                : `<span>${download.post_title}</span>`;

            const categoryHtml = download.category_name
                ? `<div class="download-card-category"><i class="fas fa-folder"></i> ${download.category_name}</div>`
                : '';

            const viewBtnHtml = download.category_slug
                ? `<a href="/categoria/${download.category_slug}/${download.post_slug}" class="download-card-btn download-card-btn-secondary"><i class="fas fa-eye"></i> Ver Post</a>`
                : '';

            const downloadBtnHtml = download.download_link
                ? `<a href="${download.download_link}" class="download-card-btn download-card-btn-primary" target="_blank"><i class="fas fa-download"></i> Baixar</a>`
                : '';

            downloadsHTML += `
                <div class="download-card" data-download-id="${download.id}">
                    <button class="download-remove-btn" onclick="removeDownload(${download.id})" title="Remover do histórico">
                        <i class="fas fa-times"></i>
                    </button>
                    <div class="download-card-body">
                        <div class="download-card-title">${thumbHtml}${linkHtml}</div>
                        <div class="download-card-meta">
                            <div class="download-card-date">
                                <i class="far fa-clock"></i>
                                <span>${download.timestamp}</span>
                            </div>
                            ${categoryHtml}
                        </div>
                        <div class="download-card-actions">
                            ${viewBtnHtml}
                            ${downloadBtnHtml}
                        </div>
                    </div>
                </div>
            `;
        });

        // Atualiza o HTML da seção completa
        historySection.innerHTML = `
            <div class="profile-card-header">
                <div class="profile-card-icon">
                    <i class="fas fa-download"></i>
                </div>
                <div style="flex: 1;">
                    <h2 class="profile-card-title">Histórico de Downloads</h2>
                    <p class="profile-card-subtitle">Últimos arquivos que você baixou</p>
                </div>
                ${data.downloads.length > 0 ? `
                    <button onclick="confirmClearHistory()" class="btn btn-sm btn-danger" style="margin-left: auto;">
                        <i class="fas fa-trash"></i> Limpar Histórico
                    </button>
                ` : ''}
            </div>
            <div class="download-history-grid" style="margin-top: 1.5rem;">
                ${downloadsHTML}
            </div>
        `;

        // Animação suave
        historySection.style.opacity = '0';
        setTimeout(() => {
            historySection.style.transition = 'opacity 0.3s ease';
            historySection.style.opacity = '1';
        }, 10);

        console.log('[DOWNLOAD] ✅ Histórico recarregado:', data.downloads.length, 'downloads');

    } catch (error) {
        console.error('[DOWNLOAD] ❌ Erro ao recarregar histórico:', error);
    }
}

// Manter refreshDownloadHistory como alias para compatibilidade
async function refreshDownloadHistory() {
    return reloadDownloadHistorySection();
}

// Inicializar quando o DOM estiver pronto E após pequeno delay
document.addEventListener('DOMContentLoaded', function() {
    console.log('[DOWNLOAD-CONTROL] DOMContentLoaded - iniciando configuração');

    // Chamar imediatamente
    setupDownloadButtons();

    // E também após 500ms para garantir que pegou botões carregados dinamicamente
    setTimeout(() => {
        console.log('[DOWNLOAD-CONTROL] Setup atrasado (500ms) - reprocessando botões');
        setupDownloadButtons();
    }, 500);

    // Observar mudanças no DOM para novos botões adicionados dinamicamente
    let observerTimeout;
    const observer = new MutationObserver(function(mutations) {
        // Debounce: aguardar 100ms antes de processar mudanças
        clearTimeout(observerTimeout);
        observerTimeout = setTimeout(() => {
            console.log('[DOWNLOAD-CONTROL] MutationObserver detectou mudanças');
            setupDownloadButtons();
        }, 100);
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Se estiver na página de perfil, carregar histórico automaticamente
    if (window.location.pathname.includes('/profile')) {
        console.log('[DOWNLOAD-CONTROL] Página de perfil detectada, carregando histórico');
        setTimeout(() => {
            reloadDownloadHistorySection();
        }, 500);
    }
});

// Expor funções globalmente para dynamic loading
window.refreshDownloadHistory = refreshDownloadHistory;
window.reloadDownloadHistorySection = reloadDownloadHistorySection;
window.reloadDownloadHistorySection = reloadDownloadHistorySection;

// Função para limpar todos os favoritos
// eslint-disable-next-line no-unused-vars
function confirmClearFavorites() {
    // Criar modal de confirmação
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 10000;';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    modalContent.style.cssText = 'background: white; padding: 2rem; border-radius: 10px; max-width: 500px; width: 90%; box-shadow: 0 10px 40px rgba(0,0,0,0.3);';

    modalContent.innerHTML = `
        <div style="text-align: center;">
            <div style="font-size: 3rem; color: #ffd700; margin-bottom: 1rem;">
                <i class="fas fa-star"></i>
            </div>
            <h3 style="margin-bottom: 1rem; color: #333;">Limpar Favoritos</h3>
            <p style="color: #666; margin-bottom: 2rem;">
                Tem certeza que deseja remover todos os posts favoritos?<br>
                <strong>Esta ação não pode ser desfeita.</strong>
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center;">
                <button class="btn-cancel" style="padding: 0.75rem 2rem; border: none; background: #6c757d; color: white; border-radius: 5px; cursor: pointer; font-size: 1rem;">
                    <i class="fas fa-times"></i> Cancelar
                </button>
                <button class="btn-confirm" style="padding: 0.75rem 2rem; border: none; background: #dc3545; color: white; border-radius: 5px; cursor: pointer; font-size: 1rem;">
                    <i class="fas fa-trash"></i> Confirmar
                </button>
            </div>
        </div>
    `;

    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    // Botão cancelar
    modalContent.querySelector('.btn-cancel').addEventListener('click', () => {
        modal.remove();
    });

    // Botão confirmar
    modalContent.querySelector('.btn-confirm').addEventListener('click', async () => {
        const confirmBtn = modalContent.querySelector('.btn-confirm');
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Limpando...';

        try {
            const response = await fetch('/api/clear-all-favorites', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                modal.remove();
                showToast(data.message || 'Favoritos removidos com sucesso!', 'success');

                // Recarregar seção de favoritos dinamicamente
                if (typeof window.reloadFavoritesSection === 'function') {
                    await window.reloadFavoritesSection();
                }
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            console.error('Erro ao limpar favoritos:', error);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Confirmar';
            showToast('Erro ao limpar favoritos. Tente novamente.', 'error');
        }
    });

    // Fechar ao clicar fora
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Função para remover um download individual
// eslint-disable-next-line no-unused-vars
function removeDownload(downloadId) {
    // Criar modal de confirmação
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 10000;';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    modalContent.style.cssText = 'background: white; padding: 2rem; border-radius: 10px; max-width: 500px; width: 90%; box-shadow: 0 10px 40px rgba(0,0,0,0.3);';

    modalContent.innerHTML = `
        <div style="text-align: center;">
            <div style="font-size: 3rem; color: #ff6b6b; margin-bottom: 1rem;">
                <i class="fas fa-trash-alt"></i>
            </div>
            <h3 style="margin-bottom: 1rem; color: #333;">Remover Download</h3>
            <p style="color: #666; margin-bottom: 2rem;">
                Tem certeza que deseja remover este download do histórico?<br>
                <strong>Esta ação não pode ser desfeita.</strong>
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center;">
                <button class="btn-cancel" style="padding: 0.75rem 2rem; border: none; background: #6c757d; color: white; border-radius: 5px; cursor: pointer; font-size: 1rem;">
                    <i class="fas fa-times"></i> Cancelar
                </button>
                <button class="btn-confirm" style="padding: 0.75rem 2rem; border: none; background: #dc3545; color: white; border-radius: 5px; cursor: pointer; font-size: 1rem;">
                    <i class="fas fa-trash"></i> Confirmar
                </button>
            </div>
        </div>
    `;

    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    // Botão cancelar
    modalContent.querySelector('.btn-cancel').addEventListener('click', () => {
        modal.remove();
    });

    // Botão confirmar
    modalContent.querySelector('.btn-confirm').addEventListener('click', async () => {
        const confirmBtn = modalContent.querySelector('.btn-confirm');
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removendo...';

        try {
        const response = await fetch(`/api/remove-download/${downloadId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

            if (data.success) {
                modal.remove();
                showToast(data.message || 'Download removido do histórico!', 'success');

                // Remover card visualmente
                const card = document.querySelector(`[data-download-id="${downloadId}"]`);
            if (card) {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.8)';
                setTimeout(() => card.remove(), 300);
            }

            // Verificar se ainda há cards
            setTimeout(() => {
                const historyGrid = document.querySelector('.download-history-grid');
                const remainingCards = historyGrid?.querySelectorAll('.download-card');

                if (!remainingCards || remainingCards.length === 0) {
                    // Mostrar mensagem vazia
                    if (historyGrid) {
                        historyGrid.innerHTML = '<div class="download-empty-state"><i class="fas fa-download"></i><h3>Nenhum download ainda</h3><p>Explore os posts e faça downloads para ver seu histórico aqui!</p></div>';
                    }

                    // Remover botão de limpar histórico
                    const clearButton = document.querySelector('button[onclick="confirmClearHistory()"]');
                    if (clearButton) {
                        clearButton.remove();
                    }
                }
            }, 350);
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            console.error('Erro ao remover download:', error);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-trash"></i> Confirmar';
            showToast('Erro ao remover download. Tente novamente.', 'error');
        }
    });

    // Fechar ao clicar fora
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Função para injetar histórico pré-carregado (usado pelo dynamic-loading)
window.injectPreloadedHistory = function(data) {
    console.log('[DOWNLOAD] ⚡ Injetando histórico pré-carregado');

    const historyContainer = document.querySelector('.download-history-grid');
    if (!historyContainer) {
        console.warn('[DOWNLOAD] Container de histórico não encontrado');
        return;
    }

    if (!data.success || !data.downloads) {
        console.warn('[DOWNLOAD] Dados de histórico inválidos');
        return;
    }

    if (data.downloads.length === 0) {
        historyContainer.innerHTML = '<p style="text-align: center; color: #999;">Nenhum download registrado ainda.</p>';
        console.log('[DOWNLOAD] ✅ Histórico vazio injetado');
        return;
    }

    // Limpar container
    historyContainer.innerHTML = '';

    // Renderizar cada download
    data.downloads.forEach(download => {
        const card = document.createElement('div');
        card.className = 'download-card';
        card.setAttribute('data-download-id', download.id);

        const imageHtml = download.post_image && download.post_image !== 'default.jpg'
            ? `<img src="/static/images/${download.post_image}" alt="${download.post_title}" class="download-card-image" onerror="this.style.display='none'">`
            : `<div class="download-card-image" style="background: linear-gradient(135deg, var(--primary-color), var(--secondary-color)); display: flex; align-items: center; justify-content: center; color: white; font-size: 3rem;"><i class="fas fa-file-alt"></i></div>`;

        const linkHtml = download.category_slug
            ? `<a href="/categoria/${download.category_slug}/${download.post_slug}">${download.post_title}</a>`
            : `<span>${download.post_title}</span>`;

        const categoryHtml = download.category_name
            ? `<div class="download-card-category"><i class="fas fa-folder"></i> ${download.category_name}</div>`
            : '';

        card.innerHTML = `
            <button class="download-remove-btn" onclick="removeDownload(${download.id})" title="Remover do histórico">
                <i class="fas fa-times"></i>
            </button>
            ${imageHtml}
            <div class="download-card-body">
                <div class="download-card-title">${linkHtml}</div>
                <div class="download-card-meta">
                    <div class="download-card-date">
                        <i class="far fa-clock"></i>
                        <span>${download.timestamp}</span>
                    </div>
                    ${categoryHtml}
                </div>
            </div>
        `;

        historyContainer.appendChild(card);
    });

    console.log('[DOWNLOAD] ✅ Histórico injetado:', data.downloads.length, 'downloads');
};
