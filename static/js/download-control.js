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
    window.location.href = '/planos';
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
    // Selecionar todos os botões de download
    const downloadButtons = document.querySelectorAll('a[href*="download"], .download-btn, .btn-download, [data-action="download"]');

    downloadButtons.forEach(button => {
        // Verificar se já foi processado (evita duplicação)
        if (button.dataset.downloadControlled === 'true') {
            return;
        }

        // Marcar como processado
        button.dataset.downloadControlled = 'true';

        // Adicionar listener com PREVENÇÃO IMEDIATA
        button.addEventListener('click', async function(e) {
            // SEMPRE prevenir comportamento padrão primeiro
            e.preventDefault();
            e.stopPropagation();

            // Prevenir múltiplos cliques
            if (button.dataset.downloading === 'true') {
                return;
            }

            // Verificar se o usuário está logado
            const isAuthenticated = document.body.dataset.authenticated === 'true';

            if (!isAuthenticated) {
                alert('Você precisa estar logado para fazer downloads!');
                window.location.href = '/login';
                return;
            }

            // Marcar como processando
            button.dataset.downloading = 'true';

            // VERIFICAR LIMITE PRIMEIRO, antes de qualquer navegação
            const canDownload = await checkDownloadLimit();

            if (!canDownload) {
                console.log('[DOWNLOAD] Limite atingido, bloqueando download');
                button.dataset.downloading = 'false';
                return; // Modal já foi exibido, não fazer nada mais
            }

            console.log('[DOWNLOAD] Limite OK, redirecionando para download');

            // Apenas se passou na verificação, fazer navegação manual
            const downloadUrl = button.href || button.dataset.href;
            if (downloadUrl) {
                window.location.href = downloadUrl;
            }

            // Liberar botão após navegação
            setTimeout(() => {
                button.dataset.downloading = 'false';
            }, 2000);
        }, true); // useCapture=true para garantir execução antes de outros handlers
    });
}

// Função para limpar histórico de downloads
// eslint-disable-next-line no-unused-vars
async function confirmClearHistory() {
    const confirmation = confirm('Tem certeza que deseja limpar todo o histórico de downloads? Esta ação não pode ser desfeita.');

    if (!confirmation) {
        return;
    }

    try {
        const response = await fetch('/clear-download-history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            // Mostrar mensagem de sucesso
            alert(data.message);

            // Recarregar a página para atualizar o histórico
            window.location.reload();
        } else {
            alert('Erro: ' + data.message);
        }
    } catch (error) {
        console.error('Erro ao limpar histórico:', error);
        alert('Erro ao limpar histórico. Tente novamente.');
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    setupDownloadButtons();

    // Observar mudanças no DOM para novos botões adicionados dinamicamente
    let observerTimeout;
    const observer = new MutationObserver(function(mutations) {
        // Debounce: aguardar 100ms antes de processar mudanças
        clearTimeout(observerTimeout);
        observerTimeout = setTimeout(() => {
            setupDownloadButtons();
        }, 100);
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});
