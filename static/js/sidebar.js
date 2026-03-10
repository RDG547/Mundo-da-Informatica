/**
 * Sidebar Functions
 * Funcionalidades para a barra lateral do painel administrativo
 */
document.addEventListener('DOMContentLoaded', function() {
    // Elementos da UI
    const sidebar = document.getElementById('adminSidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const adminContent = document.getElementById('adminContent');
    const navItems = document.querySelectorAll('.admin-nav-item');
    const themeToggle = document.getElementById('themeToggle');

    // Verificar se a sidebar está em modo recolhido no localStorage
    const isSidebarCollapsed = localStorage.getItem('admin_sidebar_collapsed') === 'true';
    if (isSidebarCollapsed) {
        sidebar.classList.add('collapsed');
    }

    // Toggle da sidebar
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');

            // Salvar estado no localStorage
            localStorage.setItem('admin_sidebar_collapsed', sidebar.classList.contains('collapsed'));

            // Adicionar data attributes para os tooltips
            if (sidebar.classList.contains('collapsed')) {
                navItems.forEach(item => {
                    const text = item.querySelector('.admin-nav-text');
                    if (text) {
                        item.setAttribute('data-title', text.textContent.trim());
                    }
                });
            } else {
                navItems.forEach(item => {
                    item.removeAttribute('data-title');
                });
            }
        });
    }

    // Ajustar o conteúdo principal quando a sidebar muda
    if (adminContent) {
        if (isSidebarCollapsed) {
            adminContent.classList.add('expanded');
        }

        sidebarToggle.addEventListener('click', function() {
            adminContent.classList.toggle('expanded');
        });
    }

    // Inicializar tooltips para sidebar colapsada
    if (isSidebarCollapsed) {
        navItems.forEach(item => {
            const text = item.querySelector('.admin-nav-text');
            if (text) {
                item.setAttribute('data-title', text.textContent.trim());
            }
        });
    }

    // Alternar tema claro/escuro
    if (themeToggle) {
        themeToggle.addEventListener('click', function(e) {
            e.preventDefault();

            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';

            // Atualizar tema
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('admin_theme', newTheme);

            // Mostrar notificação
            showNotification(`Tema ${newTheme === 'dark' ? 'escuro' : 'claro'} ativado`, 'success');
        });
    }

    // Mobile: Adicionar overlay e comportamento para fechar sidebar
    function setupMobileBehavior() {
        // Criar overlay se não existir
        let overlay = document.querySelector('.overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'overlay';
            document.body.appendChild(overlay);

            // Fechar sidebar ao clicar no overlay
            overlay.addEventListener('click', function() {
                sidebar.classList.remove('show');
                overlay.classList.remove('active');
            });
        }

        // Modificar comportamento do toggle em mobile
        if (window.innerWidth <= 991) {
            // Remover classe collapsed em mobile se estiver
            if (sidebar.classList.contains('collapsed')) {
                sidebar.classList.remove('collapsed');
            }

            if (sidebarToggle) {
                sidebarToggle.addEventListener('click', function(e) {
                    // Prevenir o comportamento padrão do toggle em mobile
                    e.stopPropagation();

                    if (!sidebar.classList.contains('show')) {
                        sidebar.classList.add('show');
                        overlay.classList.add('active');
                    } else {
                        sidebar.classList.remove('show');
                        overlay.classList.remove('active');
                    }
                });
            }

            // Fechar sidebar ao clicar em links (em mobile)
            navItems.forEach(item => {
                item.addEventListener('click', function(e) {
                    if (window.innerWidth <= 991 && sidebar.classList.contains('show')) {
                        sidebar.classList.remove('show');
                        overlay.classList.remove('active');
                    }
                });
            });
        } else {
            // Desktop: restaurar comportamento normal
            if (sidebarToggle && sidebarToggle.parentNode) {
                const newEvents = clone(sidebarToggle);
                sidebarToggle.parentNode.replaceChild(newEvents, sidebarToggle);

                // Re-adicionar evento de toggle para desktop
                newEvents.addEventListener('click', function() {
                    sidebar.classList.toggle('collapsed');
                    localStorage.setItem('admin_sidebar_collapsed', sidebar.classList.contains('collapsed'));

                    if (sidebar.classList.contains('collapsed')) {
                        navItems.forEach(item => {
                            const text = item.querySelector('.admin-nav-text');
                            if (text) {
                                item.setAttribute('data-title', text.textContent.trim());
                            }
                        });
                    } else {
                        navItems.forEach(item => {
                            item.removeAttribute('data-title');
                        });
                    }
                });
            }
        }
    }

    // Função auxiliar para clonar elemento
    function clone(el) {
        const newEl = el.cloneNode(true);
        return newEl;
    }

    // Configurar comportamento mobile inicialmente
    setupMobileBehavior();

    // Atualizar quando a janela for redimensionada
    window.addEventListener('resize', function() {
        setupMobileBehavior();
    });

    // Marcar item ativo baseado na URL atual
    function markActiveMenuItem() {
        const currentPath = window.location.pathname;

        navItems.forEach(item => {
            const itemPath = item.getAttribute('href');

            // Limpar classes ativas primeiro
            item.classList.remove('active');

            // Se for um link válido e a URL atual inclui o caminho do item
            if (itemPath && currentPath.includes(itemPath) && itemPath !== '/' && itemPath !== '#') {
                item.classList.add('active');

                // Expandir seção pai (se estiver em um dropdown/submenu)
                const parentSubmenu = item.closest('.nav-submenu');
                if (parentSubmenu) {
                    parentSubmenu.classList.add('expanded');

                    // Encontrar o botão toggle e marcá-lo como ativo
                    const toggleBtn = parentSubmenu.previousElementSibling.querySelector('.submenu-toggle');
                    if (toggleBtn) {
                        toggleBtn.classList.add('active');
                    }
                }
            }
        });
    }

    // Marcar o menu ativo na carga inicial
    markActiveMenuItem();

    // Animar ícones quando o mouse passar por cima dos itens
    navItems.forEach(item => {
        const icon = item.querySelector('.admin-icon');

        if (icon) {
            item.addEventListener('mouseenter', function() {
                icon.style.transform = 'scale(1.1) translateX(2px)';
                icon.style.filter = 'brightness(1.2)';
            });

            item.addEventListener('mouseleave', function() {
                icon.style.transform = '';
                icon.style.filter = '';
            });
        }
    });

    // Efeito ao clicar (feedback visual)
    navItems.forEach(item => {
        item.addEventListener('mousedown', function() {
            this.style.transform = 'scale(0.98)';
        });

        item.addEventListener('mouseup', function() {
            this.style.transform = '';
        });

        // Evitar que o efeito fique preso se o mouse sair durante o clique
        item.addEventListener('mouseleave', function() {
            this.style.transform = '';
        });
    });

    // Funcionalidade para o botão Limpar Cache
    const clearCacheBtn = document.getElementById('clearCacheBtn');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', function(e) {
            e.preventDefault();

            // Animação de carregamento
            const originalContent = this.innerHTML;
            this.innerHTML = `
                <svg class="admin-icon spin" viewBox="0 0 512 512">
                    <path fill="currentColor" d="M304 48a48 48 0 1 0 -96 0 48 48 0 1 0 96 0zm0 416a48 48 0 1 0 -96 0 48 48 0 1 0 96 0zM48 304a48 48 0 1 0 0-96 48 48 0 1 0 0 96zm464-48a48 48 0 1 0 -96 0 48 48 0 1 0 96 0zM142.9 437A48 48 0 1 0 75 369.1 48 48 0 1 0 142.9 437zm0-294.2A48 48 0 1 0 75 75a48 48 0 1 0 67.9 67.9zM369.1 437A48 48 0 1 0 437 369.1 48 48 0 1 0 369.1 437z"/>
                </svg>
                <span class="admin-nav-text">Limpando...</span>
            `;

            // Simular limpeza de cache (em produção, seria uma chamada AJAX real)
            setTimeout(() => {
                // Restaurar botão original
                this.innerHTML = originalContent;

                // Mostrar notificação de sucesso
                showNotification('Cache limpo com sucesso!', 'success');

                // Opcional: remover algumas preferências locais para simular limpeza real
                localStorage.removeItem('admin_recent_searches');

                // Simular atualização da página (opcional)
                // location.reload();
            }, 1500);
        });
    }

    // Adicionar classe para animação de giro
    if (!document.getElementById('spin-animation-style')) {
        const style = document.createElement('style');
        style.id = 'spin-animation-style';
        style.textContent = `
            .spin {
                animation: spin 1.5s linear infinite;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
});
