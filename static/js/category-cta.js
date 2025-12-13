/**
 * Category CTA Functions
 * Funções para o Call-to-Action da página de categoria
 */

function transformToSearchBar() {
    const searchBtn = document.getElementById('toggleSearchBtnCat');
    const form = document.getElementById('inlineSearchFormCat');
    const input = document.getElementById('inlineSearchInputCat');

    if (!searchBtn || !form || !input) {
        console.error('Elementos não encontrados:', { searchBtn, form, input });
        return;
    }

    // Animar saída apenas do botão de busca
    searchBtn.style.transition = 'all 0.4s ease';
    searchBtn.style.opacity = '0';
    searchBtn.style.transform = 'scale(0.8)';

    setTimeout(() => {
        // Esconder apenas o botão de busca
        searchBtn.style.display = 'none';

        // Mostrar formulário
        form.style.display = 'block';

        // Animar entrada do formulário
        setTimeout(() => {
            form.style.opacity = '1';
            form.style.transform = 'translateY(0)';
            input.focus();
        }, 50);
    }, 400);
}

async function checkPlanForContentRequest(isAuthenticated, userPlan, contactUrl, loginUrl) {
    if (isAuthenticated) {
        if (userPlan === 'free') {
            // Mostrar modal de upgrade com conteúdo personalizado
            showContentRequestModal('A solicitação de conteúdo está disponível apenas para planos Premium e VIP. Faça upgrade para ter acesso a esse recurso exclusivo e solicitar materiais personalizados!');
        } else {
            // Redirecionar para página de contato com categoria pré-selecionada
            window.location.href = contactUrl + '?category=solicitacao';
        }
    } else {
        // Redirecionar para login
        window.location.href = loginUrl + '?next=' + encodeURIComponent(contactUrl);
    }
}

function showContentRequestModal(message) {
    // Criar modal dinamicamente se não existir
    let modal = document.getElementById('contentRequestModal');
    
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'contentRequestModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content-request">
                <span class="modal-close" onclick="closeContentRequestModal()">&times;</span>
                <div class="modal-icon">
                    <i class="fas fa-crown"></i>
                </div>
                <h3>Recurso Exclusivo</h3>
                <p id="contentRequestMessage">${message}</p>
                <div class="modal-buttons">
                    <a href="/planos" class="btn btn-gradient primary">
                        <i class="fas fa-star"></i> Ver Planos
                    </a>
                    <button onclick="closeContentRequestModal()" class="btn btn-outline">
                        Fechar
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    } else {
        document.getElementById('contentRequestMessage').textContent = message;
    }
    
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeContentRequestModal() {
    const modal = document.getElementById('contentRequestModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// Inicializar sugestões de pesquisa e eventos
document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('inlineSearchInputCat');
    if (input) {
        input.addEventListener('focus', function () {
            this.style.borderColor = '#667eea';
            this.style.boxShadow = '0 0 0 3px rgba(102, 126, 234, 0.1)';
        });
        input.addEventListener('blur', function () {
            this.style.borderColor = '#ddd';
            this.style.boxShadow = 'none';
        });

        // Ativar sugestões de pesquisa
        if (typeof SearchSuggestions !== 'undefined') {
            const catSearchSuggestions = new SearchSuggestions(
                '#inlineSearchInputCat',
                '#catSearchSuggestions'
            );
        }
    }
});

// CSS do modal (adicionar dinamicamente)
if (!document.getElementById('category-cta-styles')) {
    const style = document.createElement('style');
    style.id = 'category-cta-styles';
    style.textContent = `
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 10000;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(5px);
        }

        .modal-content-request {
            background: white;
            border-radius: 20px;
            padding: 3rem;
            max-width: 500px;
            width: 90%;
            position: relative;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            text-align: center;
            animation: modalFadeIn 0.3s ease;
        }

        @keyframes modalFadeIn {
            from {
                opacity: 0;
                transform: scale(0.9) translateY(20px);
            }
            to {
                opacity: 1;
                transform: scale(1) translateY(0);
            }
        }

        .modal-close {
            position: absolute;
            top: 1rem;
            right: 1.5rem;
            font-size: 2rem;
            cursor: pointer;
            color: #999;
            transition: color 0.3s;
            line-height: 1;
        }

        .modal-close:hover {
            color: #333;
        }

        .modal-icon {
            width: 80px;
            height: 80px;
            margin: 0 auto 1.5rem;
            background: linear-gradient(135deg, #ff006e, #ff3085);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
            color: white;
        }

        .modal-content-request h3 {
            font-size: 1.8rem;
            margin-bottom: 1rem;
            color: #2d3748;
        }

        .modal-content-request p {
            color: #4a5568;
            line-height: 1.6;
            margin-bottom: 2rem;
        }

        .modal-buttons {
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
        }

        .btn-outline {
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }

        .btn-outline:hover {
            background: #667eea;
            color: white;
        }
    `;
    document.head.appendChild(style);
}
