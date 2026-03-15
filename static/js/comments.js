(function () {
    if (window.CommentSystem && typeof window.CommentSystem.init === 'function') {
        window.CommentSystem.init();
        return;
    }

    const state = {
        postId: '',
        pollTimer: null,
        isLoading: false,
        snapshot: '',
        comments: [],
        editId: null
    };

    function getElements() {
        return {
            post: document.querySelector('[data-post-id]'),
            form: document.getElementById('commentForm'),
            list: document.querySelector('.comments-list'),
            count: document.querySelector('.comments-count'),
            name: document.getElementById('commentName'),
            email: document.getElementById('commentEmail'),
            text: document.getElementById('commentText')
        };
    }

    function getCsrfHeaders(baseHeaders = {}) {
        const token = (window.csrfUtils && window.csrfUtils.getCsrfToken && window.csrfUtils.getCsrfToken())
            || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
            || '';
        return token ? { ...baseHeaders, 'X-CSRFToken': token } : baseHeaders;
    }

    function clearPolling() {
        if (state.pollTimer) {
            clearInterval(state.pollTimer);
            state.pollTimer = null;
        }
    }

    function getPostId() {
        return String(getElements().post?.dataset.postId || '').trim();
    }

    function getCommentsUrl(pathSuffix = '') {
        return `/post/${state.postId}/comments${pathSuffix}`;
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function isAdmin() {
        return document.body.dataset.isAdmin === 'true';
    }

    function currentUserId() {
        const raw = document.body.dataset.userId || '';
        return raw ? Number(raw) : null;
    }

    function isAuthenticated() {
        return document.body.dataset.authenticated === 'true';
    }

    function canEditComment(comment) {
        return !!comment.user_id && (isAdmin() || currentUserId() === Number(comment.user_id));
    }

    function canDeleteComment(_comment) {
        return isAdmin();
    }

    function renderAvatar(comment) {
        if (comment.profile_image) {
            return `<img src="${escapeHtml(comment.profile_image)}" alt="${escapeHtml(comment.author)}" class="comment-avatar-img">`;
        }
        return '<i class="far fa-user-circle"></i>';
    }

    function renderCommentActions(comment) {
        const actions = [];

        if (canEditComment(comment)) {
            actions.push(`
                <button type="button" class="btn-edit-comment" data-comment-edit="${comment.id}" title="Editar comentário">
                    <i class="fas fa-edit"></i>
                </button>
            `);
        }

        if (canDeleteComment(comment)) {
            actions.push(`
                <button type="button" class="btn-delete-comment" data-comment-delete="${comment.id}" title="Deletar comentário">
                    <i class="fas fa-trash-alt"></i>
                </button>
            `);
        }

        if (!actions.length) {
            return '';
        }

        return `<div class="comment-actions">${actions.join('')}</div>`;
    }

    function renderCommentItem(comment) {
        const editedBadge = comment.is_edited
            ? `<span class="comment-edited-badge" title="${escapeHtml(comment.date_edited || 'Editado')}">editado</span>`
            : '';

        return `
            <div class="comment-item animate-fade-in" data-comment-id="${comment.id}">
                <div class="comment-avatar">
                    ${renderAvatar(comment)}
                </div>
                <div class="comment-content">
                    <div class="comment-header">
                        <h4 class="comment-author">${escapeHtml(comment.author)}</h4>
                        <span class="comment-date">${escapeHtml(comment.date)} ${editedBadge}</span>
                        ${renderCommentActions(comment)}
                    </div>
                    <p class="comment-text">${escapeHtml(comment.content)}</p>
                </div>
            </div>
        `;
    }

    function renderComments(comments) {
        const { list, count } = getElements();
        if (!list) return;

        state.editId = null;
        state.comments = Array.isArray(comments) ? comments.slice() : [];
        state.snapshot = JSON.stringify(state.comments);

        if (!state.comments.length) {
            list.innerHTML = `
                <div class="no-comments">
                    <i class="far fa-comments"></i>
                    <p>Seja o primeiro a comentar!</p>
                </div>
            `;
        } else {
            list.innerHTML = state.comments.map(renderCommentItem).join('');
        }

        if (count) {
            count.textContent = `(${state.comments.length})`;
        }
    }

    function showMessage(message, type) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type || 'info', 7000);
            return;
        }

        const existingMessages = document.querySelectorAll('.comment-message');
        existingMessages.forEach((msg) => msg.remove());

        const messageDiv = document.createElement('div');
        messageDiv.className = `comment-message comment-message-${type}`;

        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        else if (type === 'error') icon = 'exclamation-circle';
        else if (type === 'warning') icon = 'exclamation-triangle';

        messageDiv.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${escapeHtml(message)}</span>
        `;

        const commentFormCard = document.querySelector('.comment-form-card');
        if (commentFormCard) {
            commentFormCard.insertBefore(messageDiv, commentFormCard.firstChild);
            setTimeout(() => {
                messageDiv.classList.add('fade-out');
                setTimeout(() => messageDiv.remove(), 300);
            }, 6000);
        }
    }

    async function fetchComments(forceRender = false) {
        if (!state.postId || state.isLoading) return;
        state.isLoading = true;

        try {
            const response = await fetch(getCommentsUrl(), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao carregar comentários.');
            }

            const nextSnapshot = JSON.stringify(data.comments || []);
            if (forceRender || nextSnapshot !== state.snapshot) {
                renderComments(data.comments || []);
            } else if (getElements().count) {
                getElements().count.textContent = `(${data.count || 0})`;
            }
        } catch (error) {
            console.error('Erro ao carregar comentários:', error);
        } finally {
            state.isLoading = false;
        }
    }

    async function submitComment() {
        const { form, name, email, text } = getElements();
        if (!form || !text) return;

        const content = (text.value || '').trim();
        const submitBtn = form.querySelector('button[type="submit"]');

        if (!content) {
            showMessage('Por favor, preencha o campo de comentário.', 'error');
            return;
        }

        if (!isAuthenticated()) {
            if (!(name?.value || '').trim() || !(email?.value || '').trim()) {
                showMessage('Por favor, preencha seu nome e email.', 'error');
                return;
            }
        }

        const payload = { content };
        if (name && name.type !== 'hidden') payload.name = (name.value || '').trim();
        if (email && email.type !== 'hidden') payload.email = (email.value || '').trim();

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
        }

        try {
            const response = await fetch(getCommentsUrl(), {
                method: 'POST',
                headers: getCsrfHeaders({
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }),
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao enviar comentário.');
            }

            if (data.comment && data.comment.is_approved) {
                renderComments([
                    data.comment,
                    ...state.comments.filter((comment) => Number(comment.id) !== Number(data.comment.id))
                ]);
                showMessage('Comentário publicado com sucesso!', 'success');
                fetchComments(true);
            } else {
                showMessage(data.message || 'Comentário enviado! Aguarde aprovação.', 'info');
            }

            form.reset();
        } catch (error) {
            console.error('Erro ao enviar comentário:', error);
            showMessage(error.message || 'Erro ao enviar comentário.', 'error');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Enviar';
            }
        }
    }

    function buildEditForm(comment) {
        return `
            <div class="edit-comment-form">
                <textarea class="edit-comment-textarea" maxlength="1000" rows="3">${escapeHtml(comment.content)}</textarea>
                <div class="edit-comment-actions">
                    <button type="button" class="btn-save-edit" data-comment-save="${comment.id}">
                        <i class="fas fa-check"></i> Salvar
                    </button>
                    <button type="button" class="btn-cancel-edit" data-comment-cancel="${comment.id}">
                        <i class="fas fa-times"></i> Cancelar
                    </button>
                </div>
            </div>
        `;
    }

    function startEditing(commentId) {
        const comment = state.comments.find((item) => Number(item.id) === Number(commentId));
        const target = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (!comment || !target || state.editId === Number(commentId)) return;

        cancelEditing();
        state.editId = Number(commentId);

        const textEl = target.querySelector('.comment-text');
        if (!textEl) return;
        textEl.style.display = 'none';
        textEl.insertAdjacentHTML('afterend', buildEditForm(comment));
        target.classList.add('editing');
        const textarea = target.querySelector('.edit-comment-textarea');
        if (textarea) textarea.focus();
    }

    function cancelEditing() {
        const activeEditing = document.querySelector('.comment-item.editing');
        if (!activeEditing) {
            state.editId = null;
            return;
        }

        activeEditing.classList.remove('editing');
        const textEl = activeEditing.querySelector('.comment-text');
        const formEl = activeEditing.querySelector('.edit-comment-form');
        if (formEl) formEl.remove();
        if (textEl) textEl.style.display = '';
        state.editId = null;
    }

    async function saveEdit(commentId) {
        const target = document.querySelector(`[data-comment-id="${commentId}"]`);
        const textarea = target?.querySelector('.edit-comment-textarea');
        if (!target || !textarea) return;

        const content = (textarea.value || '').trim();
        if (!content) {
            showMessage('O comentário não pode estar vazio.', 'error');
            return;
        }

        try {
            const response = await fetch(getCommentsUrl(`/${commentId}`), {
                method: 'PUT',
                headers: getCsrfHeaders({
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }),
                credentials: 'same-origin',
                body: JSON.stringify({ content })
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao editar comentário.');
            }

            const updatedComment = data.comment || {};
            state.comments = state.comments.map((comment) => (
                Number(comment.id) === Number(commentId)
                    ? { ...comment, ...updatedComment }
                    : comment
            ));
            renderComments(state.comments);
            cancelEditing();
            showMessage('Comentário editado com sucesso!', 'success');
        } catch (error) {
            console.error('Erro ao editar comentário:', error);
            showMessage(error.message || 'Erro ao editar comentário.', 'error');
        }
    }

    async function deleteComment(commentId) {
        if (!window.confirm('Tem certeza que deseja deletar este comentário?')) {
            return;
        }

        try {
            const response = await fetch(getCommentsUrl(`/${commentId}`), {
                method: 'DELETE',
                headers: getCsrfHeaders({
                    'X-Requested-With': 'XMLHttpRequest'
                }),
                credentials: 'same-origin'
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao deletar comentário.');
            }

            state.comments = state.comments.filter((comment) => Number(comment.id) !== Number(commentId));
            renderComments(state.comments);
            showMessage('Comentário deletado com sucesso!', 'success');
        } catch (error) {
            console.error('Erro ao deletar comentário:', error);
            showMessage(error.message || 'Erro ao deletar comentário.', 'error');
        }
    }

    function bindForm() {
        const { form } = getElements();
        if (!form || form.dataset.commentsBound === 'true') return;

        form.dataset.commentsBound = 'true';
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            event.stopPropagation();
            submitComment();
        });
    }

    function bindList() {
        const { list } = getElements();
        if (!list || list.dataset.commentsBound === 'true') return;

        list.dataset.commentsBound = 'true';
        list.addEventListener('click', (event) => {
            const editButton = event.target.closest('[data-comment-edit]');
            if (editButton) {
                startEditing(Number(editButton.dataset.commentEdit));
                return;
            }

            const deleteButton = event.target.closest('[data-comment-delete]');
            if (deleteButton) {
                deleteComment(Number(deleteButton.dataset.commentDelete));
                return;
            }

            const saveButton = event.target.closest('[data-comment-save]');
            if (saveButton) {
                saveEdit(Number(saveButton.dataset.commentSave));
                return;
            }

            const cancelButton = event.target.closest('[data-comment-cancel]');
            if (cancelButton) {
                cancelEditing();
            }
        });
    }

    function startPolling() {
        clearPolling();
        state.pollTimer = setInterval(() => {
            if (document.visibilityState === 'hidden') return;
            fetchComments(false);
        }, 3000);
    }

    function init() {
        const postId = getPostId();
        const { form, list } = getElements();

        if (!postId || !form || !list) {
            clearPolling();
            state.postId = '';
            state.snapshot = '';
            state.comments = [];
            return;
        }

        if (state.postId !== postId) {
            state.snapshot = '';
            state.comments = [];
            state.editId = null;
        }

        state.postId = postId;
        bindForm();
        bindList();
        fetchComments(true);
        startPolling();
    }

    window.CommentSystem = {
        init,
        refresh: () => fetchComments(true)
    };

    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('pageLoaded', init);
})();
