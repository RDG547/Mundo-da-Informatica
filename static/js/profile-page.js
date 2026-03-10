/* eslint-env browser */
/* global window, document, console, performance, requestAnimationFrame, IntersectionObserver, setTimeout */
// Profile Page Functions - Must be in global scope for onclick handlers

// Modal functions - GLOBAL
window.openEditModal = function () {
    console.log('openEditModal chamada');
    const modal = document.getElementById('editModal');
    console.log('Modal encontrado:', modal);
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        console.log('Modal aberto com sucesso');
    } else {
        console.error('Modal não encontrado!');
    }
};

window.closeEditModal = function () {
    console.log('closeEditModal chamada');
    const modal = document.getElementById('editModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        console.log('Modal fechado com sucesso');
    }
};

// Password Modal functions - GLOBAL
window.openPasswordModal = function () {
    console.log('openPasswordModal chamada');
    const modal = document.getElementById('passwordModal');
    console.log('Password Modal encontrado:', modal);
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        console.log('Password Modal aberto com sucesso');
    } else {
        console.error('Password Modal não encontrado!');
    }
};

window.closePasswordModal = function () {
    console.log('closePasswordModal chamada');
    const modal = document.getElementById('passwordModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        // Limpar campos do formulário
        const form = document.getElementById('changePasswordForm');
        if (form) form.reset();
        console.log('Password Modal fechado com sucesso');
    }
};

// Remove Image Modal functions - GLOBAL
window.openRemoveImageModal = function () {
    console.log('openRemoveImageModal chamada');
    const modal = document.getElementById('removeImageModal');
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        console.log('Remove Image Modal aberto com sucesso');
    }
};

window.closeRemoveImageModal = function (event) {
    console.log('closeRemoveImageModal chamada');
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    const modal = document.getElementById('removeImageModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        console.log('Remove Image Modal fechado com sucesso');
    }
};

window.confirmRemoveImage = async function(event) {
    event.preventDefault();
    event.stopPropagation();

    const button = event.target;
    const originalText = button.innerHTML;

    // Desabilitar botão e mostrar loading
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removendo...';

    try {
        const response = await fetch('/remove-profile-image', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            // Fechar modal
            window.closeRemoveImageModal();

            // Atualizar TODAS as imagens de perfil no DOM
            const defaultImage = '/static/images/profiles/default.jpg';

            // 1. Imagem grande do perfil
            const profileImg = document.querySelector('.profile-avatar-large img');
            const placeholder = document.querySelector('.avatar-placeholder-large');
            const removeButton = document.getElementById('remove-image');

            if (profileImg) {
                profileImg.style.display = 'none';
            }

            if (placeholder) {
                placeholder.style.display = 'flex';
            }

            // Remover botão de deletar da UI
            if (removeButton) {
                removeButton.remove();
            }

            // 2. Header dropdown
            const headerImg = document.querySelector('.profile-dropdown .user-avatar img');
            if (headerImg) {
                headerImg.src = defaultImage;
            }

            // 3. Navbar avatar (se existir)
            const navbarAvatar = document.querySelector('.navbar .user-avatar img');
            if (navbarAvatar) {
                navbarAvatar.src = defaultImage;
            }

            // 4. Todas as outras instâncias de imagem de perfil
            document.querySelectorAll('img[src*="uploads/profiles/"]').forEach(img => {
                if (!img.src.includes('default')) {
                    img.src = defaultImage;
                }
            });

            // 5. Atualizar sidebar se existir
            const sidebarImg = document.querySelector('.sidebar-profile-header img');
            if (sidebarImg) {
                sidebarImg.src = defaultImage;
            }

            // Mostrar mensagem de sucesso
            showToast(data.message || 'Imagem removida com sucesso!', 'success');

            // Recarregar página após 1 segundo (como ao adicionar foto)
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            throw new Error(data.message || 'Erro ao remover imagem');
        }
    } catch (error) {
        console.error('Erro ao remover imagem:', error);
        showToast(error.message || 'Erro ao remover imagem. Tente novamente.', 'error');

        // Restaurar botão
        button.disabled = false;
        button.innerHTML = originalText;
    }
};

// Favorite functions - GLOBAL
window.removeFavorite = async function (postId) {
    // Usa o modal de confirmação do FavoriteManager
    if (!window.favoriteManager) {
        alert('Sistema de favoritos não carregado');
        return;
    }

    const removed = await window.favoriteManager.remove(postId);

    if (removed) {
        // Recarrega apenas a seção de favoritos dinamicamente
        await reloadFavoritesSection();

        // Invalidar cache para garantir dados atualizados
        if (window.dynamicLoader && window.dynamicLoader.cache) {
            window.dynamicLoader.cache.clear();
            console.log('[DEBUG] Cache invalidado após remover favorito');
        }
    }
};

// Função para atualizar navbar dinamicamente
function updateNavbar(user) {
    console.log('[DEBUG] Atualizando navbar com:', user);

    // Atualizar foto de perfil na navbar
    const navbarImg = document.querySelector('.user-dropdown img');
    if (navbarImg && user.profile_image) {
        const imageUrl = `/static/uploads/profiles/${user.profile_image}`;
        navbarImg.src = imageUrl;
        console.log('[DEBUG] Navbar image atualizada:', imageUrl);
    }

    // Atualizar nome de usuário na navbar
    const navbarUsername = document.querySelector('.user-dropdown .dropdown-toggle');
    if (navbarUsername && user.username) {
        // Preservar a imagem e apenas atualizar o texto
        const imgElement = navbarUsername.querySelector('img');
        if (imgElement) {
            navbarUsername.innerHTML = '';
            navbarUsername.appendChild(imgElement.cloneNode(true));
            navbarUsername.appendChild(document.createTextNode(' ' + user.username));
        }
        console.log('[DEBUG] Navbar username atualizado:', user.username);
    }
}

// Função para atualizar sidebar dinamicamente
function updateSidebar(user) {
    console.log('[DEBUG] Atualizando sidebar com:', user);

    // Atualizar foto na sidebar
    const sidebarImg = document.querySelector('.sidebar-profile-header img, .admin-sidebar-profile img');
    if (sidebarImg && user.profile_image) {
        const imageUrl = `/static/uploads/profiles/${user.profile_image}`;
        sidebarImg.src = imageUrl;
        console.log('[DEBUG] Sidebar image atualizada:', imageUrl);
    }

    // Atualizar título (nome completo ou username) na sidebar
    const sidebarTitle = document.querySelector('.sidebar-profile-title');
    if (sidebarTitle) {
        // A API retorna 'name', mas podemos ter 'full_name' em outros contextos
        const displayName = user.name || user.full_name || user.username;
        const planBadge = sidebarTitle.querySelector('span');
        if (planBadge) {
            // Preservar o badge do plano
            sidebarTitle.childNodes[0].textContent = displayName + ' ';
        } else {
            sidebarTitle.textContent = displayName;
        }
        console.log('[DEBUG] Sidebar title atualizado:', displayName);
    }

    // Atualizar username (@username) na sidebar
    const sidebarSubtitle = document.querySelector('.sidebar-profile-subtitle');
    if (sidebarSubtitle && user.username) {
        sidebarSubtitle.textContent = '@' + user.username;
        console.log('[DEBUG] Sidebar username atualizado:', user.username);
    }

    // Atualizar bio na sidebar
    const sidebarBio = document.querySelector('.sidebar-profile-bio');
    if (user.bio) {
        if (sidebarBio) {
            sidebarBio.textContent = user.bio;
        } else {
            // Se não existe, criar o elemento
            const bioElement = document.createElement('p');
            bioElement.className = 'sidebar-profile-bio';
            bioElement.textContent = user.bio;
            const profileHeader = document.querySelector('.sidebar-profile-header');
            if (profileHeader) {
                profileHeader.appendChild(bioElement);
            }
        }
        console.log('[DEBUG] Sidebar bio atualizada:', user.bio);
    } else if (sidebarBio) {
        // Se a bio foi removida, remover o elemento
        sidebarBio.remove();
        console.log('[DEBUG] Sidebar bio removida');
    }
}

// Função para recarregar apenas a seção de favoritos
async function reloadFavoritesSection() {
    try {
        const response = await fetch('/api/user-favorites');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.message || 'Erro ao carregar favoritos');
        }

        const favoritesSection = document.getElementById('favorites-section');
        if (!favoritesSection) return;

        // Se não há mais favoritos, mostra a mensagem vazia
        if (data.posts.length === 0) {
            favoritesSection.innerHTML = `
                <div class="profile-card-header">
                    <div class="profile-card-icon">
                        <i class="fas fa-star"></i>
                    </div>
                    <div>
                        <h2 class="profile-card-title">Posts Favoritos</h2>
                        <p class="profile-card-subtitle">Posts que você salvou para ler depois</p>
                    </div>
                </div>
                <div class="empty-state">
                    <i class="fas fa-star" style="font-size: 3rem; color: #ddd; margin-bottom: 1rem;"></i>
                    <p>Você ainda não tem posts favoritos.</p>
                    <p class="text-muted">Clique no ícone de estrela nos posts para adicioná-los aos favoritos!</p>
                </div>
            `;
            return;
        }

        // Reconstrói o HTML dos favoritos
        let postsHTML = '';
        data.posts.forEach(post => {
            const fullText = post.content.replace(/<[^>]*>/g, '');

            function getImgUrl(path, folder) {
                if (!path || path === 'default.jpg') return `/static/images/${folder}/default.jpg`;
                if (path.startsWith('http://') || path.startsWith('https://')) return path;
                return `/static/uploads/${folder}/${path}`;
            }

            const postImgUrl = getImgUrl(post.image_url, 'posts');
            const dlFiles = post.download_files || [];
            const hasMultiDownload = dlFiles.length > 1;
            const badgeText = hasMultiDownload ? dlFiles.map(f => f.type).join('/') : (post.category_str || 'Geral');

            let downloadBtnHtml = '';
            if (post.download_link) {
                if (hasMultiDownload) {
                    downloadBtnHtml = `<button type="button" class="btn btn-download download-btn multi-download-trigger"
                        data-post-id="${post.id}"
                        data-post-title="${post.title}"
                        data-download-files='${JSON.stringify(dlFiles).replace(/'/g, "&#39;")}'
                        style="flex: 1; min-width: 120px;">
                        <i class="fas fa-download"></i> Download
                    </button>`;
                } else {
                    downloadBtnHtml = `<a href="/download/${post.id}" class="btn btn-download download-btn" data-action="download" style="flex: 1; min-width: 120px;">
                        <i class="fas fa-download"></i> Download
                    </a>`;
                }
            }

            const postUrl = post.category_slug ? `/${post.category_slug}/${post.slug}` : `/post/${post.id}`;

            postsHTML += `
                <div class="col-md-6 col-lg-4 mb-3 favorite-post-item" data-post-id="${post.id}" draggable="true">
                    <div class="post-card" style="position: relative;">
                        <button onclick="removeFavorite(${post.id})" class="favorite-remove-badge" title="Remover dos favoritos">
                            <i class="fas fa-times"></i>
                        </button>
                        <a href="/categoria/${encodeURIComponent(post.category_str)}" class="category-badge-left">
                            <i class="fas fa-tag"></i> ${badgeText}
                        </a>
                        <div class="post-image">
                            ${post.image_url ?
                    `<img src="${postImgUrl}" alt="${post.title}">` :
                    `<div class="post-placeholder"><i class="fas fa-file-alt"></i></div>`
                }
                            ${post.featured ? '<div class="featured-badge"><i class="fas fa-star"></i></div>' : ''}
                        </div>
                        <div class="post-content">
                            <h3><a href="${postUrl}" style="text-decoration: none; color: inherit;">${post.title}</a></h3>
                            <div class="post-meta">
                                <span><i class="far fa-calendar-alt"></i> ${post.date_posted}</span>
                                <span><i class="far fa-eye"></i> ${post.views}</span>
                            </div>
                            <div class="post-description-section">
                                <div class="post-description-title">Descrição</div>
                                <div class="post-description-text" style="max-height: 100px; overflow-y: auto;">${fullText}</div>
                            </div>
                            <div style="display: flex; gap: 10px; align-items: stretch; flex-wrap: wrap;">
                                ${downloadBtnHtml}
                                <a href="${postUrl}" class="btn" style="flex: 1; min-width: 120px; display: flex; align-items: center; justify-content: center; white-space: nowrap; gap: 6px;"><i class="fas fa-eye"></i> Ver Detalhes</a>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        // Atualiza o HTML da seção
        favoritesSection.innerHTML = `
            <div class="profile-card-header">
                <div class="profile-card-icon">
                    <i class="fas fa-star"></i>
                </div>
                <div style="flex: 1;">
                    <h2 class="profile-card-title">Posts Favoritos</h2>
                    <p class="profile-card-subtitle">Posts que você salvou para ler depois</p>
                </div>
                ${data.posts.length > 0 ? `
                    <button onclick="confirmClearFavorites()" class="btn btn-sm btn-danger" style="margin-left: auto;">
                        <i class="fas fa-trash"></i> Limpar Favoritos
                    </button>
                ` : ''}
            </div>
            <div class="posts-grid" style="margin-top: 1.5rem;">
                <div class="row" id="favorites-container">
                    ${postsHTML}
                </div>
            </div>
            ${data.total > 6 ? `
                <div class="profile-card-footer">
                    <p class="text-muted">E mais ${data.total - 6} favorito(s)</p>
                </div>
            ` : ''}
        `;

        // Animação suave
        favoritesSection.style.opacity = '0';
        setTimeout(() => {
            favoritesSection.style.transition = 'opacity 0.3s ease';
            favoritesSection.style.opacity = '1';

            // Reinicializar botões de download após atualizar o HTML
            if (typeof window.setupDownloadButtons === 'function') {
                window.setupDownloadButtons();
            }
            // Reinicializar drag-and-drop
            if (typeof window.setupFavoritesDragDrop === 'function') {
                window.setupFavoritesDragDrop();
            }
        }, 10);

    } catch (error) {
        console.error('Erro ao recarregar favoritos:', error);
        if (window.favoriteManager) {
            window.favoriteManager.showToast('Erro ao atualizar favoritos', 'error');
        }
    }
}

// Expor função globalmente para uso em outros scripts
window.reloadFavoritesSection = reloadFavoritesSection;

// Update ALL profile images across the page
function updateAllProfileImages(userData) {
    if (!userData.profile_image) return;

    const timestamp = new Date().getTime();
    const imagePath = `/static/uploads/profiles/${userData.profile_image}?t=${timestamp}`;

    // Update main profile avatar
    const profileAvatar = document.querySelector('.profile-avatar-large img');
    if (profileAvatar) {
        profileAvatar.src = imagePath;
    }

    // Update navbar avatar
    const navbarAvatar = document.querySelector('.navbar .user-dropdown img');
    if (navbarAvatar) {
        navbarAvatar.src = imagePath;
    }

    // Update sidebar avatar if exists
    const sidebarAvatar = document.querySelector('.admin-sidebar img[alt*="Perfil"]');
    if (sidebarAvatar) {
        sidebarAvatar.src = imagePath;
    }

    console.log('Todas as imagens de perfil atualizadas');
}

// Update profile header with new data
function updateProfileHeader(userData) {
    console.log('Atualizando header do perfil com:', userData);

    // Update name in profile title
    const profileTitle = document.querySelector('.profile-title');
    if (profileTitle && userData.name) {
        profileTitle.textContent = userData.name;
    }

    // Update username in subtitle
    const profileSubtitle = document.querySelector('.profile-subtitle');
    if (profileSubtitle && userData.username) {
        profileSubtitle.textContent = '@' + userData.username;
    }

    // Update bio
    const profileBio = document.querySelector('.profile-bio');
    if (userData.bio) {
        if (profileBio) {
            profileBio.textContent = userData.bio;
            profileBio.style.display = 'block';
            profileBio.style.fontStyle = 'normal';
            profileBio.style.color = '';
        } else {
            // Create bio element if it doesn't exist
            const profileSubtitle = document.querySelector('.profile-subtitle');
            if (profileSubtitle) {
                const newBio = document.createElement('p');
                newBio.className = 'profile-bio';
                newBio.textContent = userData.bio;
                profileSubtitle.parentNode.insertBefore(newBio, profileSubtitle.nextSibling);
            }
        }
    } else if (profileBio) {
        // Hide bio if empty
        profileBio.style.display = 'none';
    }

    // Update location
    const locationElement = document.querySelector('.profile-location');
    if (locationElement && userData.location) {
        locationElement.innerHTML = `<i class="fas fa-map-marker-alt"></i> ${userData.location}`;
        locationElement.style.display = '';
    } else if (locationElement) {
        locationElement.style.display = 'none';
    }

    // Update website
    const websiteElement = document.querySelector('.profile-website');
    if (websiteElement && userData.website) {
        websiteElement.href = userData.website;
        websiteElement.textContent = userData.website.replace(/^https?:\/\//, '');
        websiteElement.style.display = '';
    } else if (websiteElement) {
        websiteElement.style.display = 'none';
    }

    // Update social links
    const socialLinks = {
        facebook: userData.facebook_url,
        twitter: userData.twitter_url,
        linkedin: userData.linkedin_url,
        github: userData.github_url
    };

    Object.keys(socialLinks).forEach(platform => {
        const link = document.querySelector(`.social-link[data-platform="${platform}"]`);
        if (link && socialLinks[platform]) {
            link.href = socialLinks[platform];
            link.style.display = '';
        } else if (link) {
            link.style.display = 'none';
        }
    });

    // Update all username references in the page
    document.querySelectorAll('[data-username]').forEach(el => {
        if (userData.username) {
            el.textContent = userData.username;
            el.setAttribute('data-username', userData.username);
        }
    });

    // Update all name references
    document.querySelectorAll('[data-name]').forEach(el => {
        if (userData.name) {
            el.textContent = userData.name;
            el.setAttribute('data-name', userData.name);
        }
    });

    console.log('Perfil atualizado com sucesso em tempo real');
}

// Show toast notification - GLOBAL
window.showToast = function(message, type = 'success') {
    // Check if favoriteManager toast exists
    if (window.favoriteManager && window.favoriteManager.showToast) {
        window.favoriteManager.showToast(message, type);
        return;
    }

    // Fallback: create simple toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#28a745' : type === 'warning' ? '#ffc107' : '#dc3545'};
        color: ${type === 'warning' ? '#000' : 'white'};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};

// Initialize profile page functionality
function initializeProfilePage() {
    console.log('Inicializando página de perfil...');

    // Image upload functionality
    const imageInput = document.getElementById('profile-image-input');
    const imageForm = document.getElementById('profile-image-form');
    const triggerUpload = document.getElementById('trigger-upload');
    const removeImageBtn = document.getElementById('remove-image');

    // Trigger file upload when camera button is clicked
    if (triggerUpload && imageInput) {
        triggerUpload.addEventListener('click', function () {
            imageInput.click();
        });
    }

    // Handle file selection
    if (imageInput && imageForm) {
        imageInput.addEventListener('change', function () {
            if (this.files && this.files[0]) {
                const file = this.files[0];

                // Validar tipo de arquivo
                if (!file.type.match('image/(jpeg|png|gif)')) {
                    showToast('Tipo de arquivo inválido. Use JPG, PNG ou GIF.', 'error');
                    this.value = '';
                    return;
                }

                // Validar tamanho (máximo 5MB)
                if (file.size > 5242880) {
                    showToast('Imagem muito grande. Máximo 5MB permitido.', 'error');
                    this.value = '';
                    return;
                }

                // Preview da imagem antes de enviar
                const reader = new FileReader();
                reader.onload = function (e) {
                    const profileImg = document.querySelector('.profile-avatar-large img');
                    if (profileImg) {
                        profileImg.src = e.target.result;
                        profileImg.style.display = 'block';
                        profileImg.onerror = null; // Remove handler de erro

                        // Ocultar placeholder se estiver visível
                        const placeholder = document.querySelector('.avatar-placeholder-large');
                        if (placeholder) {
                            placeholder.style.display = 'none';
                        }
                    }
                };
                reader.readAsDataURL(file);

                // Enviar formulário automaticamente
                showToast('Enviando imagem...', 'success');
                imageForm.submit();
            }
        });
    }

    // Open remove image modal
    if (removeImageBtn) {
        removeImageBtn.addEventListener('click', function () {
            window.openRemoveImageModal();
        });
    }

    // Biography character counter
    const bioInput = document.getElementById('bio');
    const bioCount = document.getElementById('bioCount');

    if (bioInput && bioCount) {
        bioInput.addEventListener('input', function () {
            const length = this.value.length;
            bioCount.textContent = length;

            // Mudar cor baseado no uso
            if (length > 300) {
                bioCount.style.color = '#ff006e';
                bioCount.style.fontWeight = '700';
            } else if (length > 250) {
                bioCount.style.color = '#ff8500';
                bioCount.style.fontWeight = '600';
            } else {
                bioCount.style.color = '#6c757d';
                bioCount.style.fontWeight = '500';
            }
        });
    }

    // Validação de senha em tempo real
    const newPasswordInput = document.getElementById('new_password');
    const confirmPasswordInput = document.getElementById('confirm_password');

    if (newPasswordInput && confirmPasswordInput) {
        confirmPasswordInput.addEventListener('input', function () {
            if (this.value !== newPasswordInput.value) {
                this.setCustomValidity('As senhas não coincidem');
                this.style.borderColor = '#dc3545';
            } else {
                this.setCustomValidity('');
                this.style.borderColor = '#28a745';
            }
        });

        newPasswordInput.addEventListener('input', function () {
            if (confirmPasswordInput.value && confirmPasswordInput.value !== this.value) {
                confirmPasswordInput.style.borderColor = '#dc3545';
            } else if (confirmPasswordInput.value) {
                confirmPasswordInput.style.borderColor = '#28a745';
            }
        });
    }

    // Validação de username em tempo real
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.addEventListener('input', function () {
            const pattern = /^[a-zA-Z0-9_]{3,20}$/;
            if (!pattern.test(this.value)) {
                this.setCustomValidity('Use apenas letras, números e _ (3-20 caracteres)');
                this.style.borderColor = '#dc3545';
            } else {
                this.setCustomValidity('');
                this.style.borderColor = '#28a745';
            }
        });
    }

    // Edit Profile Form Handler
    const editProfileForm = document.getElementById('editProfileForm');
    console.log('[DEBUG] Edit Profile Form:', editProfileForm ? 'encontrado' : 'NÃO encontrado');

    if (editProfileForm) {
        editProfileForm.addEventListener('submit', async function (e) {
            console.log('[DEBUG] Form submit interceptado');
            e.preventDefault();
            e.stopPropagation(); // Previne que o DynamicLoader intercepte

            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;

            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';

            try {
                const formData = new FormData(this);
                console.log('[DEBUG] Enviando requisição AJAX para:', this.action);

                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                console.log('[DEBUG] Response status:', response.status);
                const data = await response.json();
                console.log('[DEBUG] Response data:', data);

                if (data.success) {
                    console.log('[DEBUG] Sucesso! Fechando modal e atualizando interface');

                    // Close modal
                    window.closeEditModal();

                    // Update profile header with new data
                    updateProfileHeader(data.user);

                    // Update ALL profile images in the page (including navbar)
                    updateAllProfileImages(data.user);

                    // Atualizar navbar dinamicamente
                    updateNavbar(data.user);

                    // Atualizar sidebar se existir (página de perfil)
                    updateSidebar(data.user);

                    // Invalidar cache do Dynamic Loading para forçar recarga na próxima navegação
                    if (window.dynamicLoader && window.dynamicLoader.cache) {
                        window.dynamicLoader.cache.clear();
                        console.log('[DEBUG] Cache do Dynamic Loading invalidado');
                    }

                    // Show success message
                    showToast('Perfil atualizado com sucesso!', 'success');
                } else {
                    console.log('[DEBUG] Erro na resposta:', data.message);
                    showToast(data.message || 'Erro ao atualizar perfil', 'error');
                }
            } catch (error) {
                console.error('[DEBUG] Erro ao atualizar perfil:', error);
                showToast('Erro ao atualizar perfil. Tente novamente.', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        });
    } else {
        console.error('[DEBUG] Formulário editProfileForm não encontrado no DOM!');
    }

    // Stats animation
    const statNumbers = document.querySelectorAll('.count');

    // Função melhorada para animar números
    function animateNumber(element) {
        const target = parseInt(element.getAttribute('data-count'));
        if (isNaN(target)) return;

        const duration = 2000; // 2 segundos
        const start = 0;
        const startTime = performance.now();

        function updateNumber(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function para suavizar a animação
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            const current = Math.floor(start + (target - start) * easeOutQuart);

            element.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(updateNumber);
            } else {
                element.textContent = target; // Garantir valor final exato
            }
        }

        requestAnimationFrame(updateNumber);
    }

    // Observer para detectar quando os números entram na viewport
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Pequeno delay para melhor efeito visual
                setTimeout(() => {
                    animateNumber(entry.target);
                }, 100);
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    statNumbers.forEach(number => {
        observer.observe(number);
    });

    // Close modal on outside click
    const modal = document.getElementById('editModal');
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                window.closeEditModal();
            }
        });
    }

    // Close remove image modal on outside click
    const removeModal = document.getElementById('removeImageModal');
    if (removeModal) {
        removeModal.addEventListener('click', function (e) {
            if (e.target === removeModal) {
                window.closeRemoveImageModal();
            }
        });
    }

    // Close password modal on outside click
    const passwordModal = document.getElementById('passwordModal');
    if (passwordModal) {
        passwordModal.addEventListener('click', function (e) {
            if (e.target === passwordModal) {
                window.closePasswordModal();
            }
        });
    }

    console.log('Página de perfil inicializada com sucesso');
}

// Toggle para expandir/colapsar favoritos - GLOBAL
window.loadMoreFavorites = function(button) {
    const hiddenFavorites = document.querySelectorAll('.extra-favorites[style*="display: none"]');
    const batchSize = 8;
    const toShow = Array.from(hiddenFavorites).slice(0, batchSize);

    toShow.forEach(function(item, i) {
        setTimeout(function() {
            item.style.display = 'flex';
            item.style.opacity = '0';
            item.style.transform = 'translateY(20px)';
            // Force reflow
            void item.offsetWidth;
            item.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, i * 60);
    });

    // Check if there are still hidden items after this batch
    const remainingHidden = hiddenFavorites.length - toShow.length;
    if (remainingHidden <= 0) {
        var wrapper = document.getElementById('favorites-load-more-wrapper');
        if (wrapper) wrapper.style.display = 'none';
    }
};

// ============================================
// Sistema de Drag-and-Drop para Favoritos
// ============================================
(function initFavoritesDragDrop() {
    let draggedItem = null;
    let placeholder = null;

    function setupDragDrop() {
        const container = document.getElementById('favorites-container');
        if (!container) return;

        const items = container.querySelectorAll('.favorite-post-item[draggable="true"]');
        if (items.length < 2) return;

        // Adicionar cursor de arrasto e estilos
        items.forEach(item => {
            if (item.dataset.dragInitialized) return;
            item.dataset.dragInitialized = 'true';
            item.style.cursor = 'grab';

            item.addEventListener('dragstart', function(e) {
                draggedItem = this;
                this.style.opacity = '0.4';
                this.style.cursor = 'grabbing';
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', this.dataset.postId);
            });

            item.addEventListener('dragend', function() {
                this.style.opacity = '1';
                this.style.cursor = 'grab';
                draggedItem = null;
                if (placeholder && placeholder.parentNode) {
                    placeholder.parentNode.removeChild(placeholder);
                }
                placeholder = null;
                // Remover todos os indicadores visuais
                container.querySelectorAll('.favorite-post-item').forEach(el => {
                    el.style.borderLeft = '';
                    el.style.borderRight = '';
                });
            });

            item.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (!draggedItem || draggedItem === this) return;

                // Indicar posição de drop
                const rect = this.getBoundingClientRect();
                const midX = rect.left + rect.width / 2;
                container.querySelectorAll('.favorite-post-item').forEach(el => {
                    el.style.borderLeft = '';
                    el.style.borderRight = '';
                });

                if (e.clientX < midX) {
                    this.style.borderLeft = '3px solid var(--primary-color, #4a90e2)';
                } else {
                    this.style.borderRight = '3px solid var(--primary-color, #4a90e2)';
                }
            });

            item.addEventListener('dragleave', function() {
                this.style.borderLeft = '';
                this.style.borderRight = '';
            });

            item.addEventListener('drop', function(e) {
                e.preventDefault();
                if (!draggedItem || draggedItem === this) return;

                const rect = this.getBoundingClientRect();
                const midX = rect.left + rect.width / 2;

                if (e.clientX < midX) {
                    container.insertBefore(draggedItem, this);
                } else {
                    container.insertBefore(draggedItem, this.nextSibling);
                }

                this.style.borderLeft = '';
                this.style.borderRight = '';

                // Salvar nova ordem
                saveOrder();
            });
        });

        // Touch support para mobile
        let touchItem = null;
        let touchClone = null;
        let touchStartX, touchStartY;

        items.forEach(item => {
            if (item.dataset.touchInitialized) return;
            item.dataset.touchInitialized = 'true';

            item.addEventListener('touchstart', function(e) {
                if (e.target.closest('button, a, .btn')) return;
                touchItem = this;
                const touch = e.touches[0];
                touchStartX = touch.clientX;
                touchStartY = touch.clientY;
            }, { passive: true });

            item.addEventListener('touchmove', function(e) {
                if (!touchItem) return;
                const touch = e.touches[0];
                const dx = Math.abs(touch.clientX - touchStartX);
                const dy = Math.abs(touch.clientY - touchStartY);
                if (dx > 10 && dx > dy) {
                    e.preventDefault();
                    if (!touchClone) {
                        touchClone = touchItem.cloneNode(true);
                        touchClone.style.position = 'fixed';
                        touchClone.style.zIndex = '99999';
                        touchClone.style.opacity = '0.8';
                        touchClone.style.pointerEvents = 'none';
                        touchClone.style.width = touchItem.offsetWidth + 'px';
                        document.body.appendChild(touchClone);
                        touchItem.style.opacity = '0.3';
                    }
                    touchClone.style.left = (touch.clientX - touchItem.offsetWidth / 2) + 'px';
                    touchClone.style.top = (touch.clientY - 30) + 'px';
                }
            }, { passive: false });

            item.addEventListener('touchend', function(e) {
                if (!touchItem || !touchClone) {
                    touchItem = null;
                    return;
                }
                touchClone.remove();
                touchClone = null;
                touchItem.style.opacity = '1';

                const touch = e.changedTouches[0];
                const target = document.elementFromPoint(touch.clientX, touch.clientY);
                const dropTarget = target ? target.closest('.favorite-post-item') : null;

                if (dropTarget && dropTarget !== touchItem) {
                    const rect = dropTarget.getBoundingClientRect();
                    const midX = rect.left + rect.width / 2;
                    if (touch.clientX < midX) {
                        container.insertBefore(touchItem, dropTarget);
                    } else {
                        container.insertBefore(touchItem, dropTarget.nextSibling);
                    }
                    saveOrder();
                }
                touchItem = null;
            });
        });
    }

    function saveOrder() {
        const container = document.getElementById('favorites-container');
        if (!container) return;
        const items = container.querySelectorAll('.favorite-post-item[data-post-id]');
        const order = Array.from(items).map(item => parseInt(item.dataset.postId));

        fetch('/api/reorder-favorites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order: order })
        }).catch(function(err) {
            console.error('[FAVORITES] Erro ao salvar ordem:', err);
        });
    }

    // Inicializar
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupDragDrop);
    } else {
        setupDragDrop();
    }
    document.addEventListener('contentLoaded', setupDragDrop);
    window.setupFavoritesDragDrop = setupDragDrop;
})();

// Inicializar quando a página carregar
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeProfilePage);
} else {
    initializeProfilePage();
}

// Re-inicializar quando carregado dinamicamente
document.addEventListener('contentLoaded', initializeProfilePage);
