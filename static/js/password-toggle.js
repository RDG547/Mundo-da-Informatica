/**
 * Password Toggle Functionality
 * Solução simples e direta para alternar visibilidade de senhas
 */

(function () {
    'use strict';

    // Evitar múltiplas inicializações
    if (window.passwordToggleInitialized) {
        console.log('🔐 Password toggle script already initialized, skipping...');
        return;
    }
    window.passwordToggleInitialized = true;

    console.log('🔐 Password toggle script loading...');

    // Função para alternar a visibilidade da senha
    function togglePassword(passwordFieldId) {
        console.log('🔄 Toggle function called for:', passwordFieldId);

        const passwordField = document.getElementById(passwordFieldId);
        if (!passwordField) {
            console.error('❌ Campo não encontrado:', passwordFieldId);
            return;
        }

        const container = passwordField.parentElement;
        const toggleIcon = container.querySelector('.password-toggle i');

        if (!toggleIcon) {
            console.error('❌ Ícone não encontrado');
            return;
        }

        // Alternar tipo do campo
        if (passwordField.type === 'password') {
            passwordField.type = 'text';
            passwordField.classList.add('has-toggle');
            toggleIcon.classList.remove('fa-eye');
            toggleIcon.classList.add('fa-eye-slash');
            console.log('👁️ Senha visível');
        } else {
            passwordField.type = 'password';
            passwordField.classList.remove('has-toggle');
            toggleIcon.classList.remove('fa-eye-slash');
            toggleIcon.classList.add('fa-eye');
            console.log('🔒 Senha oculta');
        }
    }

    // Configurar eventos usando event delegation no documento
    function setupEvents() {
        console.log('⚙️ Configurando eventos...');

        // Event delegation - um único listener no documento
        document.addEventListener('click', function (e) {
            // Verificar se clicou no botão ou no ícone dentro dele
            const toggleBtn = e.target.closest('.password-toggle');

            if (toggleBtn) {
                e.preventDefault();
                e.stopPropagation();

                const targetId = toggleBtn.getAttribute('data-target');
                console.log('🖱️ Clique detectado! Target:', targetId);

                if (targetId) {
                    togglePassword(targetId);
                }
            }
        }, true); // Usar capture phase para garantir que pegamos o evento primeiro

        console.log('✅ Eventos configurados');
    }

    // Disponibilizar funções globalmente
    window.togglePassword = togglePassword;
    window.togglePasswordField = togglePassword;

    // Executar imediatamente ou aguardar DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            console.log('📄 DOM carregado');
            setupEvents();
        });
    } else {
        console.log('📄 DOM já pronto');
        setupEvents();
    }

    console.log('✅ Password toggle script loaded');
})();
