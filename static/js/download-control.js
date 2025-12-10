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

// Mostrar modal de limite excedido
function showDownloadLimitModal(message, autoRedirect = true) {
    createDownloadLimitModal();
    
    const modal = document.getElementById('downloadLimitModal');
    const messageEl = document.getElementById('limitMessage');
    const countdownNumber = document.getElementById('countdownNumber');
    const countdownText = document.getElementById('countdownText');
    const progressCircle = modal.querySelector('.countdown-progress');
    
    messageEl.textContent = message;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    if (autoRedirect) {
        let countdown = 5;
        const circumference = 2 * Math.PI * 54;
        progressCircle.style.strokeDasharray = circumference;
        
        const interval = setInterval(() => {
            countdown--;
            countdownNumber.textContent = countdown;
            countdownText.textContent = countdown;
            
            // Atualizar círculo de progresso
            const offset = circumference - (countdown / 5) * circumference;
            progressCircle.style.strokeDashoffset = offset;
            
            if (countdown <= 0) {
                clearInterval(interval);
                redirectToPlans();
            }
        }, 1000);
        
        // Armazenar interval para poder cancelar
        modal.dataset.interval = interval;
    }
}

// Fechar modal
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
            
            if (data.plan === 'free') {
                message = `Você atingiu o limite de ${data.limit} downloads diários do plano gratuito. Faça upgrade para continuar baixando!`;
            } else if (data.plan === 'premium') {
                message = `Você atingiu o limite de ${data.limit} downloads diários do plano Premium. Considere o plano VIP para downloads ilimitados!`;
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

// Interceptar cliques em botões de download
function setupDownloadButtons() {
    // Selecionar todos os botões de download
    const downloadButtons = document.querySelectorAll('a[href*="download"], .download-btn, .btn-download, [data-action="download"]');
    
    downloadButtons.forEach(button => {
        // Remover listeners antigos
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
        
        // Adicionar novo listener
        newButton.addEventListener('click', async function(e) {
            // Verificar se o usuário está logado
            const isAuthenticated = document.body.dataset.authenticated === 'true';
            
            if (!isAuthenticated) {
                e.preventDefault();
                alert('Você precisa estar logado para fazer downloads!');
                window.location.href = '/login';
                return;
            }
            
            // Verificar limite de downloads
            const canDownload = await checkDownloadLimit();
            
            if (!canDownload) {
                e.preventDefault();
                return;
            }
            
            // Se passou nas verificações, permitir o download
            // O link será seguido normalmente
        });
    });
}

// Função para limpar histórico de downloads
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
    const observer = new MutationObserver(function(mutations) {
        setupDownloadButtons();
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});
