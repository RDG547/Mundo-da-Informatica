/**
 * Admin Panel JavaScript
 * Controla todas as funcionalidades do painel administrativo
 */

document.addEventListener('DOMContentLoaded', function () {
    // Inicializar componentes da interface
    initSidebar();
    initThemeToggle();
    initNotifications();
    initActiveMenu();
    initTooltips();
    handleModals();
    handleProfileImages(); // Nova função para tratar imagens de perfil

    // Se a página atual contém tabelas de dados, inicializar recursos de tabela
    if (document.querySelector('.admin-table')) {
        initTables();
    }

    // Verificar atualizações do sistema (simulado)
    checkForUpdates();

    // Funções específicas para páginas específicas
    initPageSpecificFunctions();

    // Melhorias na navegação da barra lateral
    // Adicionar efeitos de hover com movimento suave
    const navItems = document.querySelectorAll('.admin-nav-item');

    navItems.forEach(item => {
        item.addEventListener('mouseenter', function () {
            const icon = this.querySelector('.admin-icon');
            if (icon) {
                icon.style.transform = 'scale(1.1) translateX(2px)';
            }
        });

        item.addEventListener('mouseleave', function () {
            const icon = this.querySelector('.admin-icon');
            if (icon) {
                icon.style.transform = '';
            }
        });

        // Efeito de clique
        item.addEventListener('mousedown', function () {
            this.style.transform = 'scale(0.97)';
        });

        item.addEventListener('mouseup', function () {
            this.style.transform = '';
        });
    });

    // Animar logo e status na barra lateral
    const logoIcon = document.querySelector('.admin-nav-logo .admin-icon');
    if (logoIcon) {
        logoIcon.addEventListener('mouseover', function () {
            this.style.transform = 'rotate(-10deg) scale(1.1)';
        });

        logoIcon.addEventListener('mouseout', function () {
            this.style.transform = '';
        });
    }

    // Marcar automaticamente o item de menu ativo
    const currentPath = window.location.pathname;
    navItems.forEach(item => {
        const itemPath = item.getAttribute('href');
        if (itemPath && currentPath.includes(itemPath) && itemPath !== '/') {
            item.classList.add('active');
        }
    });

    // Efeito suave ao abrir submenus (se houver)
    const subMenuToggles = document.querySelectorAll('.submenu-toggle');
    subMenuToggles.forEach(toggle => {
        toggle.addEventListener('click', function (e) {
            e.preventDefault();
            const subMenu = this.nextElementSibling;

            if (subMenu.style.maxHeight) {
                subMenu.style.maxHeight = null;
                this.classList.remove('open');
            } else {
                subMenu.style.maxHeight = subMenu.scrollHeight + 'px';
                this.classList.add('open');
            }
        });
    });

    // Adicionar animação de pulso para o botão "Novo Post"
    const newPostBtn = document.getElementById('newPostBtn');
    if (newPostBtn) {
        // Adicionar efeito de pulso
        setTimeout(() => {
            newPostBtn.classList.add('pulse-effect');
        }, 2000);

        // Remover efeito após o hover
        newPostBtn.addEventListener('mouseover', function () {
            this.classList.remove('pulse-effect');
        });
    }
});

/**
 * Gerencia o comportamento das imagens de perfil no painel administrativo
 */
function handleProfileImages() {
    // Seleciona todas as imagens de perfil no painel admin
    const profileImages = document.querySelectorAll('.admin-profile-img img, .user-avatar img');

    profileImages.forEach(img => {
        // Adiciona classe de carregamento ao contêiner
        const container = img.closest('.admin-profile-img, .user-avatar');
        if (container) {
            container.classList.add('loading');
        }

        // Verifica se a imagem já foi carregada
        if (img.complete) {
            validateProfileImage(img);
        } else {
            img.addEventListener('load', function () {
                validateProfileImage(this);
            });
        }

        // Tratamento de erro para imagens
        img.addEventListener('error', function () {
            this.classList.add('error');

            // Obtém as iniciais do usuário para o placeholder
            let initials = 'MI';
            const nameElement = img.closest('.admin-profile, .user-card')?.querySelector('.admin-profile-info h4, .user-name');

            if (nameElement) {
                const name = nameElement.textContent.trim();
                const nameParts = name.split(' ');
                if (nameParts.length >= 2) {
                    initials = nameParts[0][0] + nameParts[nameParts.length - 1][0];
                } else if (name.length > 0) {
                    initials = name[0];
                }
            }

            // Cria ou atualiza o placeholder com as iniciais
            let placeholder = img.nextElementSibling;
            if (!placeholder || !placeholder.classList.contains('profile-placeholder')) {
                placeholder = document.createElement('div');
                placeholder.className = 'profile-placeholder';
                img.parentNode.appendChild(placeholder);
            }
            placeholder.textContent = initials.toUpperCase();

            // Remove classe de carregamento
            if (container) {
                container.classList.remove('loading');
            }
        });
    });
}

/**
 * Valida uma imagem de perfil após o carregamento
 */
function validateProfileImage(img) {
    // Verifica se a imagem tem conteúdo válido
    if (img.naturalWidth === 0 || img.naturalHeight === 0) {
        img.classList.add('error');
        // Dispara o evento de erro para ativar o placeholder
        const errorEvent = new Event('error');
        img.dispatchEvent(errorEvent);
    } else {
        img.classList.remove('error');

        // Remove classe de carregamento
        const container = img.closest('.admin-profile-img, .user-avatar');
        if (container) {
            container.classList.remove('loading');
        }
    }
}

/**
 * Inicializa o comportamento da barra lateral
 */
function initSidebar() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const adminSidebar = document.getElementById('adminSidebar');
    const adminContent = document.getElementById('adminContent');

    // Verificar se a sidebar está colapsada no localStorage
    const sidebarState = localStorage.getItem('sidebar_collapsed');
    if (sidebarState === 'true') {
        adminSidebar.classList.add('collapsed');
        adminContent.classList.add('expanded');
    }

    if (sidebarToggle && adminSidebar && adminContent) {
        sidebarToggle.addEventListener('click', function () {
            adminSidebar.classList.toggle('collapsed');
            adminContent.classList.toggle('expanded');

            // Salvar estado no localStorage
            localStorage.setItem('sidebar_collapsed', adminSidebar.classList.contains('collapsed'));
        });

        // Adicionar efeitos hover para sections
        const navSections = document.querySelectorAll('.nav-section');
        navSections.forEach(section => {
            const title = section.querySelector('.nav-section-title');
            if (title) {
                title.addEventListener('click', function () {
                    section.classList.toggle('expanded');
                });
            }
        });
    }
}

/**
 * Destaca o item de menu ativo com base na URL atual
 */
function initActiveMenu() {
    const currentPath = window.location.pathname;
    const menuItems = document.querySelectorAll('.admin-nav-item');

    menuItems.forEach(item => {
        const itemPath = item.getAttribute('href');
        if (itemPath && currentPath === itemPath) {
            item.classList.add('active');

            // Expandir seção pai se necessário
            const parentSection = item.closest('.nav-section');
            if (parentSection) {
                parentSection.classList.add('expanded');
            }
        }
    });
}

/**
 * Inicializa a funcionalidade de troca de tema
 */
function initThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    const htmlElement = document.documentElement;
    const isDarkMode = htmlElement.getAttribute('data-theme') === 'dark';
    const darkIcon = document.querySelector('.theme-icon-dark');
    const lightIcon = document.querySelector('.theme-icon-light');

    // Definir ícone inicial baseado no tema atual
    if (isDarkMode) {
        darkIcon.style.display = 'none';
        lightIcon.style.display = 'inline-block';
    } else {
        darkIcon.style.display = 'inline-block';
        lightIcon.style.display = 'none';
    }

    // Adicionar evento para alternar tema
    if (themeToggle) {
        themeToggle.addEventListener('click', function (e) {
            e.preventDefault();
            const currentTheme = htmlElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            // Mudar tema com animação
            document.body.classList.add('theme-transition');
            setTimeout(() => {
                htmlElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('admin_theme', newTheme);
            }, 50);

            setTimeout(() => {
                document.body.classList.remove('theme-transition');
            }, 500);

            // Alternar ícones
            if (newTheme === 'dark') {
                darkIcon.style.display = 'none';
                lightIcon.style.display = 'inline-block';
            } else {
                darkIcon.style.display = 'inline-block';
                lightIcon.style.display = 'none';
            }

            // Mostrar notificação
            showNotification(`Tema ${newTheme === 'dark' ? 'escuro' : 'claro'} ativado.`, 'info');
        });
    }
}

/**
 * Inicializa o sistema de notificações
 */
function initNotifications() {
    // Adicionar evento de clique para fechar notificações existentes
    document.querySelectorAll('.notification-close').forEach(button => {
        button.addEventListener('click', function () {
            const notification = this.closest('.notification');
            notification.classList.add('slide-out-right');
            setTimeout(() => notification.remove(), 300);
        });
    });
}

/**
 * Mostra uma notificação ao usuário
 */
function showNotification(message, type = 'info', duration = 8000) {
    const notification = document.createElement('div');
    notification.className = `notification ${type} slide-in-right`;

    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'warning' ? 'fa-exclamation-triangle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close">&times;</button>
    `;

    document.body.appendChild(notification);

    // Adicionar evento para fechar notificação
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.add('slide-out-right');
        setTimeout(() => notification.remove(), 300);
    });

    // Auto-fechar após duração especificada
    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.classList.add('slide-out-right');
            setTimeout(() => notification.remove(), 300);
        }
    }, duration);

    return notification;
}

/**
 * Inicializa tooltips em elementos com attribute data-tooltip
 */
function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
        element.addEventListener('focus', showTooltip);
        element.addEventListener('blur', hideTooltip);
    });
}

function showTooltip() {
    const tooltip = this.getAttribute('data-tooltip');
    if (!tooltip) return;

    // Criar elemento tooltip
    const tooltipEl = document.createElement('div');
    tooltipEl.className = 'custom-tooltip';
    tooltipEl.textContent = tooltip;
    document.body.appendChild(tooltipEl);

    // Posicionar tooltip
    const rect = this.getBoundingClientRect();
    tooltipEl.style.left = rect.left + (rect.width / 2) - (tooltipEl.offsetWidth / 2) + 'px';
    tooltipEl.style.top = rect.top - tooltipEl.offsetHeight - 10 + 'px';

    // Mostrar tooltip com animação
    setTimeout(() => tooltipEl.classList.add('visible'), 10);

    // Armazenar referência ao tooltip
    this.tooltip = tooltipEl;
}

function hideTooltip() {
    if (this.tooltip) {
        this.tooltip.classList.remove('visible');
        setTimeout(() => this.tooltip.remove(), 200);
        this.tooltip = null;
    }
}

/**
 * Função para abrir modais
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        document.body.classList.add('modal-open');
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);

        // Fechar modal ao clicar fora do conteúdo
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                closeModal(modalId);
            }
        });

        // Fechar modal ao pressionar ESC
        document.addEventListener('keydown', function escKeyHandler(e) {
            if (e.key === 'Escape') {
                closeModal(modalId);
                document.removeEventListener('keydown', escKeyHandler);
            }
        });
    }
}

/**
 * Função para fechar modais
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
            document.body.classList.remove('modal-open');
        }, 300);
    }
}

/**
 * Gerencie todas as modais da interface
 */
function handleModals() {
    // Abrir modal ao clicar em botões com data-modal
    document.querySelectorAll('[data-modal]:not([data-modal-initialized])').forEach(button => {
        button.setAttribute('data-modal-initialized', 'true');
        button.addEventListener('click', function () {
            const modalId = this.getAttribute('data-modal');
            openModal(modalId);
        });
    });

    // Fechar modal ao clicar no botão de fechar
    document.querySelectorAll('.close-modal:not([data-close-initialized])').forEach(button => {
        button.setAttribute('data-close-initialized', 'true');
        button.addEventListener('click', function (e) {
            e.preventDefault();
            const modal = this.closest('.modal');
            if (modal) {
                closeModal(modal.id);
            }
        });
    });

    // Fechar modal ao clicar em botões com data-bs-dismiss="modal" ou data-dismiss="modal"
    document.querySelectorAll('[data-bs-dismiss="modal"]:not([data-dismiss-initialized]), [data-dismiss="modal"]:not([data-dismiss-initialized])').forEach(button => {
        button.setAttribute('data-dismiss-initialized', 'true');
        button.addEventListener('click', function (e) {
            e.preventDefault();
            const modal = this.closest('.modal');
            if (modal) {
                closeModal(modal.id);
            }
        });
    });
}

/**
 * Inicializa recursos para tabelas de dados
 */
function initTables() {
    // Habilitar ordenação de colunas
    document.querySelectorAll('.admin-table th[data-sort]').forEach(th => {
        th.classList.add('sortable');
        th.addEventListener('click', function () {
            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.rows);
            const sortKey = th.getAttribute('data-sort');
            const direction = th.classList.contains('sort-asc') ? 'desc' : 'asc';

            // Limpar estado de ordenação de todas as colunas
            table.querySelectorAll('th').forEach(column => {
                column.classList.remove('sort-asc', 'sort-desc');
            });

            // Definir nova direção de ordenação
            th.classList.add(`sort-${direction}`);

            // Ordenar linhas
            rows.sort((a, b) => {
                const aValue = a.querySelector(`td[data-${sortKey}]`) ?
                    a.querySelector(`td[data-${sortKey}]`).getAttribute(`data-${sortKey}`) :
                    a.cells[th.cellIndex].textContent;

                const bValue = b.querySelector(`td[data-${sortKey}]`) ?
                    b.querySelector(`td[data-${sortKey}]`).getAttribute(`data-${sortKey}`) :
                    b.cells[th.cellIndex].textContent;

                // Determinar se devemos ordenar como número ou texto
                if (!isNaN(aValue) && !isNaN(bValue)) {
                    return direction === 'asc' ?
                        parseFloat(aValue) - parseFloat(bValue) :
                        parseFloat(bValue) - parseFloat(aValue);
                } else {
                    return direction === 'asc' ?
                        aValue.localeCompare(bValue) :
                        bValue.localeCompare(aValue);
                }
            });

            // Reordenar DOM
            rows.forEach(row => tbody.appendChild(row));
        });
    });

    // Implementar funcionalidade de pesquisa para tabelas com caixas de pesquisa
    document.querySelectorAll('.search-bar input').forEach(searchInput => {
        searchInput.addEventListener('input', function () {
            const table = this.closest('.admin-card').querySelector('.admin-table');
            if (!table) return;

            const searchTerm = this.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    });

    // Implementar seleção em massa com checkboxes
    document.querySelectorAll('.admin-table th input[type="checkbox"]').forEach(headerCheckbox => {
        headerCheckbox.addEventListener('change', function () {
            const table = this.closest('table');
            const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');

            checkboxes.forEach(checkbox => {
                if (!checkbox.closest('tr').style.display || checkbox.closest('tr').style.display !== 'none') {
                    checkbox.checked = this.checked;
                }
            });
        });
    });
}

/**
 * Verifica atualizações do sistema
 */
function checkForUpdates() {
    // Simulação - Em um ambiente real, isto faria uma chamada à API
    setTimeout(() => {
        // 10% de chance de mostrar uma notificação de atualização
        if (Math.random() < 0.1) {
            showNotification('Nova atualização do sistema disponível! Clique para ver as novidades.', 'info', 10000);
        }
    }, 5000);
}

/**
 * Inicializa funções específicas para a página atual
 */
function initPageSpecificFunctions() {
    const currentPath = window.location.pathname;

    // Dashboard - Atualiza estatísticas em tempo real
    if (currentPath.includes('/admin/dashboard')) {
        console.log('Dashboard inicializado');
        setInterval(updateDashboardStats, 60000);
    }

    // As demais páginas (Settings, Profile, Posts, etc.) têm suas
    // inicializações específicas implementadas nas próprias páginas
    if (currentPath.includes('/admin/')) {
        console.log('Página administrativa inicializada:', currentPath);
    }
}

function updateDashboardStats() {
    // Simulação de atualização de estatísticas em tempo real
    const statsElements = document.querySelectorAll('.stat-info h3');
    if (statsElements.length > 0) {
        statsElements.forEach(statEl => {
            const currentValue = parseInt(statEl.textContent);
            if (!isNaN(currentValue)) {
                // Pequena variação para simulação
                const newValue = currentValue + Math.floor(Math.random() * 3);
                statEl.textContent = newValue;

                // Animar com um efeito
                statEl.classList.add('bounce');
                setTimeout(() => statEl.classList.remove('bounce'), 1000);
            }
        });
    }
}

/**
 * Helper para fazer requisições AJAX
 * @param {string} url - URL da requisição
 * @param {string} method - Método HTTP (GET, POST, PUT, DELETE)
 * @param {Object} data - Dados a serem enviados (opcional)
 * @returns {Promise} - Promise com a resposta
 */
function ajaxRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    };

    if (data) {
        if (method === 'GET') {
            // Para GET, adicionar query params
            const params = new URLSearchParams();
            Object.entries(data).forEach(([key, value]) => {
                params.append(key, value);
            });
            url = `${url}?${params.toString()}`;
        } else {
            // Para outros métodos, enviar como JSON
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }
    }

    return fetch(url, options)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }
            return response.json();
        });
}

// Exportar funções para uso global
window.openModal = openModal;
window.closeModal = closeModal;
window.showNotification = showNotification;
window.handleModals = handleModals;
