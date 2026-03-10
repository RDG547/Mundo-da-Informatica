/**
 * profile-images.js
 * Gerencia o comportamento das imagens de perfil em todo o site
 */

document.addEventListener('DOMContentLoaded', function() {
    // Inicializa todas as imagens de perfil na página
    initProfileImages();

    // Configura os manipuladores de upload de imagem
    setupProfileImageUpload();
});

// Listen for dynamic page loads
document.addEventListener('adminPageLoaded', function() {
    initProfileImages();
    setupProfileImageUpload();
});

// Export for global access
window.initializeProfileImages = function() {
    initProfileImages();
    setupProfileImageUpload();
};

/**
 * Inicializa o tratamento de todas as imagens de perfil na página
 */
function initProfileImages() {
    // Seleciona todos os contêineres de imagens de perfil
    const profileContainers = document.querySelectorAll('.profile-img, .user-avatar, .admin-profile-img');

    profileContainers.forEach(container => {
        // Adiciona classe de carregamento
        container.classList.add('loading');

        // Encontra a imagem dentro do contêiner
        const img = container.querySelector('img');

        if (img) {
            // Verifica se a imagem já foi carregada
            if (img.complete) {
                validateProfileImage(img);
            } else {
                // Adiciona evento para quando a imagem carregar
                img.addEventListener('load', function() {
                    validateProfileImage(this);
                });
            }

            // Trata erros de carregamento
            img.addEventListener('error', function() {
                handleImageError(this);
            });
        }
    });
}

/**
 * Valida uma imagem de perfil após o carregamento
 */
function validateProfileImage(img) {
    // Verifica se a imagem tem dimensões válidas
    if (img.naturalWidth === 0 || img.naturalHeight === 0 || !img.src || img.src === 'undefined' || img.src === '') {
        handleImageError(img);
    } else {
        // Imagem carregada com sucesso
        img.classList.remove('error');

        // Remove classe de carregamento do contêiner
        const container = img.closest('.profile-img, .user-avatar, .admin-profile-img');
        if (container) {
            container.classList.remove('loading');
        }
    }
}

/**
 * Lida com erros de carregamento de imagem
 */
function handleImageError(img) {
    // Marcar imagem como com erro
    img.classList.add('error');

    // Obter iniciais para o placeholder
    let initials = 'U';

    // Procurar por um elemento de nome de usuário próximo para extrair iniciais
    const container = img.closest('.profile-img, .user-avatar, .admin-profile-img');
    const parentContainer = container?.parentElement;

    if (parentContainer) {
        const nameElement = parentContainer.querySelector('.user-name, h4, .admin-profile-info h4');

        if (nameElement) {
            const name = nameElement.textContent.trim();
            const nameParts = name.split(' ');

            if (nameParts.length >= 2) {
                initials = (nameParts[0][0] + nameParts[nameParts.length - 1][0]).toUpperCase();
            } else if (nameParts.length === 1 && nameParts[0]) {
                initials = nameParts[0][0].toUpperCase();
            }
        }
    }

    // Buscar ou criar placeholder
    let placeholder = img.nextElementSibling;
    if (!placeholder || !placeholder.classList.contains('profile-placeholder')) {
        placeholder = document.createElement('div');
        placeholder.className = 'profile-placeholder';
        img.parentNode.appendChild(placeholder);
    }

    // Atualizar o texto do placeholder
    placeholder.textContent = initials;

    // Remover classe de carregamento
    if (container) {
        container.classList.remove('loading');
    }
}

/**
 * Configura o upload de imagem de perfil
 */
function setupProfileImageUpload() {
    const fileInput = document.getElementById('profile-image-input');
    const form = document.getElementById('profile-image-form');

    if (fileInput && form) {
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const file = this.files[0];

                // Verificar tipo e tamanho
                if (!file.type.match('image.*')) {
                    alert('Por favor, selecione uma imagem válida.');
                    return;
                }

                if (file.size > 5242880) { // 5MB
                    alert('A imagem é muito grande. O tamanho máximo é 5MB.');
                    return;
                }

                // Mostrar indicador de carregamento
                const profileImg = document.querySelector('.admin-profile-img, .profile-img');
                if (profileImg) {
                    profileImg.classList.add('loading');
                }

                // Enviar formulário automaticamente
                form.submit();
            }
        });
    }
}
