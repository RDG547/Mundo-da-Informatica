// Sistema de controle de limites de download

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
                
                // Limpar histórico visualmente sem reload
                const historyGrid = document.querySelector('.download-history-grid');
                const historySection = document.querySelector('.profile-section');
                const clearButton = document.querySelector('button[onclick="confirmClearHistory()"]');
                
                if (historyGrid) {
                    historyGrid.innerHTML = '<p style="text-align: center; color: #999; padding: 2rem;">Nenhum download registrado ainda.</p>';
                }
                
                // Remover botão de limpar
                if (clearButton) {
                    clearButton.remove();
                }
                
                // Atualizar texto do header da seção
                const historyTitle = document.querySelector('.profile-section h2');
                if (historyTitle && historyTitle.textContent.includes('Histórico')) {
                    const subtitle = historyTitle.nextElementSibling;
                    if (subtitle && subtitle.tagName === 'P') {
                        subtitle.textContent = 'Nenhum download registrado';
                    }
                }
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

// Função para atualizar histórico de download em tempo real
async function refreshDownloadHistory() {
    const historyContainer = document.querySelector('.download-history-grid');
    if (!historyContainer) return;
    
    try {
        const response = await fetch('/api/download-history');
        const data = await response.json();
        
        if (data.success && data.downloads && data.downloads.length > 0) {
            // Limpar container
            historyContainer.innerHTML = '';
            
            // Renderizar cada download
            data.downloads.forEach(download => {
                const card = document.createElement('div');
                card.className = 'download-card';
                
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
            
            console.log('[DOWNLOAD] Histórico atualizado com sucesso');
        } else if (data.downloads && data.downloads.length === 0) {
            historyContainer.innerHTML = '<p style="text-align: center; color: #999;">Nenhum download registrado ainda.</p>';
        }
    } catch (error) {
        console.error('[DOWNLOAD] Erro ao atualizar histórico:', error);
    }
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
});
