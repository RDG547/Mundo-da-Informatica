/**
 * Sistema de Comentários - Post Page
 * Gerencia envio e exibição de comentários com atualização em tempo real
 */

document.addEventListener('DOMContentLoaded', function() {
    const commentForm = document.getElementById('commentForm');
    const commentsList = document.querySelector('.comments-list');
    const commentsCount = document.querySelector('.comments-count');
    const noComments = document.querySelector('.no-comments');

    // Obter o ID do post da URL
    const postId = getPostIdFromUrl();

    // Armazenar IDs dos comentários já exibidos para evitar re-renderização
    let currentCommentIds = new Set();

    // Verificar se é admin
    const isAdmin = document.body.dataset.isAdmin === 'true';

    // Obter ID do usuário atual (se estiver logado)
    const currentUserId = document.body.dataset.userId ? parseInt(document.body.dataset.userId) : null;

    if (!postId) {
        console.error('ID do post não encontrado');
        return;
    }

    // Carregar comentários ao iniciar
    loadComments();

    // Atualizar comentários automaticamente a cada 10 segundos
    setInterval(loadComments, 10000);

    // Enviar comentário - Event listener único e simples
    if (commentForm) {
        commentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();
            submitComment();
            return false;
        }, false);
    }

    /**
     * Extrai o ID do post da URL ou do atributo data
     */
    function getPostIdFromUrl() {
        // Tentar obter do atributo data-post-id
        const postElement = document.querySelector('[data-post-id]');
        if (postElement) {
            return postElement.getAttribute('data-post-id');
        }

        // Se não encontrar, tentar extrair da URL
        const pathParts = window.location.pathname.split('/');
        // Para URLs no formato /post/123
        if (pathParts[1] === 'post' && pathParts[2]) {
            return pathParts[2];
        }

        return null;
    }

    /**
     * Carrega os comentários do servidor
     */
    function loadComments() {
        // Obter categoria e slug dos atributos data
        const postElement = document.querySelector('[data-post-id]');
        if (!postElement) {
            console.error('Elemento do post não encontrado');
            return;
        }

        const category = postElement.getAttribute('data-category');
        const slug = postElement.getAttribute('data-slug');

        if (!category || !slug) {
            console.error('Categoria ou slug não encontrados');
            return;
        }

        fetch(`/${category}/${slug}/comments`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayComments(data.comments);
                    updateCommentsCount(data.count);
                }
            })
            .catch(error => {
                console.error('Erro ao carregar comentários:', error);
            });
    }

    /**
     * Exibe os comentários na lista (sem piscar)
     */
    function displayComments(comments) {
        if (!commentsList) return;

        // Criar Set com IDs dos novos comentários
        const newCommentIds = new Set(comments.map(c => c.id));

        // Remover comentários que não existem mais
        const existingComments = commentsList.querySelectorAll('.comment-item:not([data-comment-template])');
        existingComments.forEach(commentEl => {
            const commentId = parseInt(commentEl.dataset.commentId);
            if (!newCommentIds.has(commentId)) {
                commentEl.remove();
                currentCommentIds.delete(commentId);
            }
        });

        // Remover mensagem "sem comentários" se houver comentários
        const noCommentsMsg = commentsList.querySelector('.no-comments');
        if (comments.length > 0 && noCommentsMsg) {
            noCommentsMsg.remove();
        }

        if (comments.length === 0) {
            // Adicionar mensagem apenas se não existir
            if (!noCommentsMsg) {
                const noCommentsDiv = document.createElement('div');
                noCommentsDiv.className = 'no-comments';
                noCommentsDiv.innerHTML = `
                    <i class="far fa-comments"></i>
                    <p>Seja o primeiro a comentar!</p>
                `;
                commentsList.appendChild(noCommentsDiv);
            }
            currentCommentIds.clear();
            return;
        }

        // Adicionar apenas comentários novos (evita piscar)
        comments.forEach(comment => {
            if (!currentCommentIds.has(comment.id)) {
                const commentElement = createCommentElement(comment);
                // Inserir no início da lista
                const firstComment = commentsList.querySelector('.comment-item:not([data-comment-template])');
                if (firstComment) {
                    commentsList.insertBefore(commentElement, firstComment);
                } else {
                    commentsList.appendChild(commentElement);
                }
                currentCommentIds.add(comment.id);
            }
        });
    }    /**
     * Cria o elemento HTML de um comentário
     */
    function createCommentElement(comment) {
        const div = document.createElement('div');
        div.className = 'comment-item animate-fade-in';
        div.dataset.commentId = comment.id;

        // Avatar: foto de perfil se existir, ícone caso contrário
        let avatarHTML;
        if (comment.profile_image) {
            avatarHTML = `<img src="/static/uploads/profiles/${escapeHtml(comment.profile_image)}" alt="${escapeHtml(comment.author)}" class="comment-avatar-img">`;
        } else {
            avatarHTML = `<i class="far fa-user-circle"></i>`;
        }

        // Botão de deletar apenas para admins
        let deleteButton = '';
        if (isAdmin) {
            deleteButton = `
                <button class="btn-delete-comment" onclick="deleteComment(${comment.id})" title="Deletar comentário">
                    <i class="fas fa-trash-alt"></i>
                </button>
            `;
        }

        // Botão de editar para autor ou admin
        let editButton = '';
        if (comment.user_id && (currentUserId == comment.user_id || isAdmin)) {
            editButton = `
                <button class="btn-edit-comment" onclick="editComment(${comment.id})" title="Editar comentário">
                    <i class="fas fa-edit"></i>
                </button>
            `;
        }

        // Badge de editado
        let editedBadge = '';
        if (comment.is_edited) {
            const editedTitle = comment.date_edited ? `Editado em ${comment.date_edited}` : 'Editado';
            editedBadge = `<span class="comment-edited-badge" title="${editedTitle}">editado</span>`;
        }

        div.innerHTML = `
            <div class="comment-avatar">
                ${avatarHTML}
            </div>
            <div class="comment-content">
                <div class="comment-header">
                    <h4 class="comment-author">${escapeHtml(comment.author)}</h4>
                    <span class="comment-date">${comment.date} ${editedBadge}</span>
                    <div class="comment-actions">
                        ${editButton}
                        ${deleteButton}
                    </div>
                </div>
                <p class="comment-text" data-original-content="${escapeHtml(comment.content)}">${escapeHtml(comment.content)}</p>
            </div>
        `;

        return div;
    }

    /**
     * Envia um novo comentário
     */
    function submitComment() {
        const name = document.getElementById('commentName')?.value.trim();
        const email = document.getElementById('commentEmail')?.value.trim();
        const content = document.getElementById('commentText').value.trim();
        const submitBtn = commentForm.querySelector('button[type="submit"]');

        // Validações básicas
        if (!content) {
            showMessage('Por favor, preencha o campo de comentário.', 'error');
            return false;
        }

        // Para usuários não logados, validar nome e email
        const isLoggedIn = document.getElementById('commentName')?.type === 'hidden';
        if (!isLoggedIn && (!name || !email)) {
            showMessage('Por favor, preencha seu nome e email.', 'error');
            return;
        }

        // Desabilitar botão durante envio
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';

        // Preparar dados
        const commentData = { content: content };
        if (name) commentData.name = name;
        if (email) commentData.email = email;

        // Obter categoria e slug dos atributos data
        const postElement = document.querySelector('[data-post-id]');
        if (!postElement) {
            showMessage('❌ Erro: informações do post não encontradas.', 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Enviar Comentário';
            return;
        }

        const category = postElement.getAttribute('data-category');
        const slug = postElement.getAttribute('data-slug');

        if (!category || !slug) {
            showMessage('❌ Erro: categoria ou slug não encontrados.', 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Enviar Comentário';
            return;
        }

        // Enviar para o servidor
        fetch(`/${category}/${slug}/comments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(commentData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Mensagem diferente dependendo se foi aprovado ou não
                if (data.comment && data.comment.is_approved) {
                    showMessage('✅ Comentário publicado com sucesso!', 'success');
                    // Recarregar comentários imediatamente para mostrar o novo
                    setTimeout(() => {
                        loadComments();
                    }, 300);
                } else {
                    showMessage('📝 Comentário enviado! Aguardando aprovação do administrador.', 'info');
                }

                // Limpar formulário
                commentForm.reset();
            } else {
                showMessage(data.message || 'Erro ao enviar comentário.', 'error');
            }
        })
        .catch(error => {
            console.error('Erro ao enviar comentário:', error);
            showMessage('❌ Erro ao enviar comentário. Tente novamente.', 'error');
        })
        .finally(() => {
            // Reabilitar botão
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Enviar';
        });

        // Prevenir qualquer ação padrão do formulário
        return false;
    }

    /**
     * Atualiza o contador de comentários
     */
    function updateCommentsCount(count) {
        if (commentsCount) {
            commentsCount.textContent = `(${count})`;
        }
    }

    /**
     * Exibe mensagem de feedback
     * Usa a função global showNotification se disponível
     */
    function showMessage(message, type) {
        // Tenta usar a função global showNotification se disponível (de admin.js)
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type, 7000);
            return;
        }

        // Fallback: implementação local para páginas sem admin.js
        const existingMessages = document.querySelectorAll('.comment-message');
        existingMessages.forEach(msg => msg.remove());

        const messageDiv = document.createElement('div');
        messageDiv.className = `comment-message comment-message-${type}`;

        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        else if (type === 'error') icon = 'exclamation-circle';
        else if (type === 'info') icon = 'info-circle';

        messageDiv.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
        `;

        const commentFormCard = document.querySelector('.comment-form-card');
        if (commentFormCard) {
            commentFormCard.insertBefore(messageDiv, commentFormCard.firstChild);

            setTimeout(() => {
                messageDiv.classList.add('fade-out');
                setTimeout(() => messageDiv.remove(), 300);
            }, 7000);
        }
    }

    /**
     * Escapa HTML para prevenir XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Deleta um comentário (apenas para admins)
     */
    window.deleteComment = function(commentId) {
        if (!confirm('Tem certeza que deseja deletar este comentário?')) {
            return;
        }

        const postElement = document.querySelector('[data-post-id]');
        if (!postElement) {
            alert('Erro: informações do post não encontradas.');
            return;
        }

        const category = postElement.getAttribute('data-category');
        const slug = postElement.getAttribute('data-slug');

        if (!category || !slug) {
            alert('Erro: categoria ou slug não encontrados.');
            return;
        }

        fetch(`/${category}/${slug}/comments/${commentId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('✅ Comentário deletado com sucesso!', 'success');
                // Remover do DOM imediatamente
                const commentEl = document.querySelector(`[data-comment-id="${commentId}"]`);
                if (commentEl) {
                    commentEl.remove();
                    currentCommentIds.delete(commentId);
                }
                // Recarregar para atualizar contador
                setTimeout(() => loadComments(), 500);
            } else {
                showMessage('❌ Erro ao deletar comentário.', 'error');
            }
        })
        .catch(error => {
            console.error('Erro ao deletar comentário:', error);
            showMessage('❌ Erro ao deletar comentário.', 'error');
        });
    };

    /**
     * Edita um comentário (apenas para autor ou admin)
     */
    window.editComment = function(commentId) {
        const commentEl = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (!commentEl) return;

        const textEl = commentEl.querySelector('.comment-text');
        const originalContent = textEl.dataset.originalContent || textEl.textContent;

        // Verificar se já está em modo de edição
        if (commentEl.classList.contains('editing')) {
            return;
        }

        // Marcar como editando
        commentEl.classList.add('editing');

        // Criar formulário de edição inline
        const editForm = document.createElement('div');
        editForm.className = 'edit-comment-form';
        editForm.innerHTML = `
            <textarea class="edit-comment-textarea" maxlength="1000" rows="3">${originalContent}</textarea>
            <div class="edit-comment-actions">
                <button type="button" class="btn-save-edit">
                    <i class="fas fa-check"></i> Salvar
                </button>
                <button type="button" class="btn-cancel-edit">
                    <i class="fas fa-times"></i> Cancelar
                </button>
            </div>
        `;

        // Substituir texto pelo formulário
        textEl.style.display = 'none';
        textEl.parentElement.insertBefore(editForm, textEl.nextSibling);

        const textarea = editForm.querySelector('.edit-comment-textarea');
        const btnSave = editForm.querySelector('.btn-save-edit');
        const btnCancel = editForm.querySelector('.btn-cancel-edit');

        // Focar no textarea
        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);

        // Cancelar edição
        btnCancel.addEventListener('click', function() {
            editForm.remove();
            textEl.style.display = '';
            commentEl.classList.remove('editing');
        });

        // Salvar edição
        btnSave.addEventListener('click', function() {
            const newContent = textarea.value.trim();

            if (!newContent) {
                showMessage('❌ O comentário não pode estar vazio.', 'error');
                return;
            }

            if (newContent.length < 3) {
                showMessage('❌ O comentário deve ter pelo menos 3 caracteres.', 'error');
                return;
            }

            if (newContent === originalContent) {
                // Nenhuma mudança
                editForm.remove();
                textEl.style.display = '';
                commentEl.classList.remove('editing');
                return;
            }

            // Desabilitar botões durante o envio
            btnSave.disabled = true;
            btnCancel.disabled = true;
            textarea.disabled = true;

            const postElement = document.querySelector('[data-post-id]');
            if (!postElement) {
                showMessage('❌ Erro: informações do post não encontradas.', 'error');
                btnSave.disabled = false;
                btnCancel.disabled = false;
                textarea.disabled = false;
                return;
            }

            const category = postElement.getAttribute('data-category');
            const slug = postElement.getAttribute('data-slug');

            if (!category || !slug) {
                showMessage('❌ Erro: categoria ou slug não encontrados.', 'error');
                btnSave.disabled = false;
                btnCancel.disabled = false;
                textarea.disabled = false;
                return;
            }

            fetch(`/${category}/${slug}/comments/${commentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content: newContent })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => Promise.reject(err));
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showMessage('✅ Comentário editado com sucesso!', 'success');

                    // Atualizar o conteúdo no DOM
                    textEl.textContent = newContent;
                    textEl.dataset.originalContent = newContent;

                    // Adicionar/atualizar badge de editado
                    const commentHeader = commentEl.querySelector('.comment-header');
                    const dateSpan = commentHeader.querySelector('.comment-date');
                    let editedBadge = dateSpan.querySelector('.comment-edited-badge');

                    if (!editedBadge) {
                        editedBadge = document.createElement('span');
                        editedBadge.className = 'comment-edited-badge';
                        dateSpan.appendChild(document.createTextNode(' '));
                        dateSpan.appendChild(editedBadge);
                    }

                    editedBadge.textContent = 'editado';
                    if (data.comment && data.comment.date_edited) {
                        editedBadge.title = `Editado em ${data.comment.date_edited}`;
                    }

                    // Remover formulário e mostrar texto
                    editForm.remove();
                    textEl.style.display = '';
                    commentEl.classList.remove('editing');
                } else {
                    showMessage('❌ Erro ao editar comentário.', 'error');
                    // Re-habilitar botões
                    btnSave.disabled = false;
                    btnCancel.disabled = false;
                    textarea.disabled = false;
                }
            })
            .catch(error => {
                console.error('Erro ao editar comentário:', error);
                showMessage(error.error || '❌ Erro ao editar comentário.', 'error');
                // Re-habilitar botões
                btnSave.disabled = false;
                btnCancel.disabled = false;
                textarea.disabled = false;
            });
        });

        // Permitir salvar com Ctrl+Enter
        textarea.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                btnSave.click();
            }
        });
    };

});
