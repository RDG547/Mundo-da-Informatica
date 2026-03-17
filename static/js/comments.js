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
        editId: null,
        replyId: null,
        pendingReplyId: null
    };

    function getElements() {
        return {
            post: document.querySelector('[data-post-id]'),
            form: document.getElementById('commentForm'),
            list: document.querySelector('.comments-list'),
            count: document.querySelector('.comments-count'),
            name: document.getElementById('commentName'),
            email: document.getElementById('commentEmail'),
            text: document.getElementById('commentText'),
            parentId: document.getElementById('commentParentId'),
            replyState: document.getElementById('commentReplyState'),
            replyAuthor: document.getElementById('commentReplyAuthor'),
            replyPreview: document.getElementById('commentReplyPreview')
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

    function parseMultilineText(value) {
        return escapeHtml(value).replace(/\n/g, '<br>');
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

    function canReplyComment(_comment) {
        return true;
    }

    function renderAvatar(comment) {
        if (comment.profile_image) {
            return `<img src="${escapeHtml(comment.profile_image)}" alt="${escapeHtml(comment.author)}" class="comment-avatar-img">`;
        }
        return '<i class="far fa-user-circle"></i>';
    }

    function renderCommentActions(comment) {
        const actions = [];

        if (canReplyComment(comment)) {
            actions.push(`
                <button type="button" class="btn-reply-comment" data-comment-reply="${comment.id}" title="Responder comentário">
                    <i class="fas fa-reply"></i>
                </button>
            `);
        }

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

        return actions.length ? `<div class="comment-actions">${actions.join('')}</div>` : '';
    }

    function renderCommentItem(comment, depth = 0) {
        const editedBadge = comment.is_edited
            ? `<span class="comment-edited-badge" title="${escapeHtml(comment.date_edited || 'Editado')}">editado</span>`
            : '';

        const replies = Array.isArray(comment.replies) ? comment.replies : [];
        const replyClass = depth > 0 ? ' is-reply' : '';

        return `
            <div class="comment-thread" data-comment-thread="${comment.id}">
                <div class="comment-item animate-fade-in${replyClass}" data-comment-id="${comment.id}">
                    <div class="comment-avatar">
                        ${renderAvatar(comment)}
                    </div>
                    <div class="comment-content">
                        <div class="comment-header">
                            <h4 class="comment-author">${escapeHtml(comment.author)}</h4>
                            <span class="comment-date">${escapeHtml(comment.date)} ${editedBadge}</span>
                            ${renderCommentActions(comment)}
                        </div>
                        <p class="comment-text">${parseMultilineText(comment.content)}</p>
                    </div>
                </div>
                ${replies.length ? `<div class="comment-replies">${replies.map((reply) => renderCommentItem(reply, depth + 1)).join('')}</div>` : ''}
            </div>
        `;
    }

    function countComments(comments) {
        return (comments || []).reduce((total, comment) => total + 1 + countComments(comment.replies || []), 0);
    }

    function findCommentById(comments, commentId) {
        for (const comment of comments || []) {
            if (Number(comment.id) === Number(commentId)) {
                return comment;
            }

            const nested = findCommentById(comment.replies || [], commentId);
            if (nested) {
                return nested;
            }
        }

        return null;
    }

    function updateCommentTree(comments, commentId, updater) {
        return (comments || []).map((comment) => {
            if (Number(comment.id) === Number(commentId)) {
                return updater(comment);
            }

            const replies = updateCommentTree(comment.replies || [], commentId, updater);
            return replies !== comment.replies ? { ...comment, replies } : comment;
        });
    }

    function removeCommentFromTree(comments, commentId) {
        let changed = false;

        const nextComments = (comments || []).reduce((acc, comment) => {
            if (Number(comment.id) === Number(commentId)) {
                changed = true;
                return acc;
            }

            const nestedResult = removeCommentFromTree(comment.replies || [], commentId);
            if (nestedResult.changed) {
                changed = true;
                acc.push({ ...comment, replies: nestedResult.comments });
                return acc;
            }

            acc.push(comment);
            return acc;
        }, []);

        return {
            changed,
            comments: nextComments
        };
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
            list.innerHTML = state.comments.map((comment) => renderCommentItem(comment)).join('');
        }

        if (count) {
            count.textContent = `(${countComments(state.comments)})`;
        }

        if (state.replyId && !findCommentById(state.comments, state.replyId)) {
            clearReplyState();
        }

        applyPendingReplyIntent();
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

    async function parseJsonResponse(response) {
        const rawText = await response.text();

        try {
            return rawText ? JSON.parse(rawText) : {};
        } catch (_error) {
            throw new Error('O servidor retornou uma resposta invalida ao processar os comentarios.');
        }
    }

    function updateReplyState(comment) {
        const { parentId, replyState, replyAuthor, replyPreview, text } = getElements();
        if (!comment || !replyState || !parentId) return;

        state.replyId = Number(comment.id);
        parentId.value = String(comment.id);
        replyState.hidden = false;

        if (replyAuthor) {
            replyAuthor.textContent = comment.author || 'Usuario';
        }

        if (replyPreview) {
            replyPreview.textContent = (comment.content || '').trim().slice(0, 140);
        }

        if (text) {
            text.focus();
            text.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function clearReplyState() {
        const { parentId, replyState, replyAuthor, replyPreview } = getElements();

        state.replyId = null;
        if (parentId) parentId.value = '';
        if (replyState) replyState.hidden = true;
        if (replyAuthor) replyAuthor.textContent = '';
        if (replyPreview) replyPreview.textContent = '';
    }

    function applyPendingReplyIntent() {
        const params = new URLSearchParams(window.location.search);
        const requestedReplyId = state.pendingReplyId || params.get('reply_to');
        if (!requestedReplyId) return;

        const targetComment = findCommentById(state.comments, requestedReplyId);
        if (!targetComment) return;

        state.pendingReplyId = null;
        updateReplyState(targetComment);

        if (params.get('reply_to')) {
            params.delete('reply_to');
            const nextSearch = params.toString();
            const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ''}${window.location.hash || ''}`;
            window.history.replaceState({}, '', nextUrl);
        }
    }

    function startReply(commentId) {
        const comment = findCommentById(state.comments, commentId);
        if (!comment) return;

        cancelEditing();
        updateReplyState(comment);
    }

    async function fetchComments(forceRender = false) {
        if (!state.postId || state.isLoading) return;
        state.isLoading = true;

        try {
            const response = await fetch(getCommentsUrl(), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            });
            const data = await parseJsonResponse(response);
            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao carregar comentarios.');
            }

            const nextSnapshot = JSON.stringify(data.comments || []);
            if (forceRender || nextSnapshot !== state.snapshot) {
                renderComments(data.comments || []);
            } else if (getElements().count) {
                getElements().count.textContent = `(${data.count || countComments(state.comments)})`;
            }
        } catch (error) {
            console.error('Erro ao carregar comentarios:', error);
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
            showMessage('Por favor, preencha o campo de comentario.', 'error');
            return;
        }

        if (!isAuthenticated()) {
            if (!(name?.value || '').trim() || !(email?.value || '').trim()) {
                showMessage('Por favor, preencha seu nome e email.', 'error');
                return;
            }
        }

        const wasReply = Boolean(state.replyId);
        const payload = { content };
        if (name && name.type !== 'hidden') payload.name = (name.value || '').trim();
        if (email && email.type !== 'hidden') payload.email = (email.value || '').trim();
        if (state.replyId) payload.parent_id = state.replyId;

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
            const data = await parseJsonResponse(response);

            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao enviar comentario.');
            }

            form.reset();
            clearReplyState();
            await fetchComments(true);

            if (data.comment && data.comment.is_approved) {
                showMessage(wasReply ? 'Resposta publicada com sucesso!' : 'Comentario publicado com sucesso!', 'success');
            } else {
                showMessage(data.message || (wasReply ? 'Resposta enviada! Aguarde aprovacao.' : 'Comentario enviado! Aguarde aprovacao.'), 'info');
            }
        } catch (error) {
            console.error('Erro ao enviar comentario:', error);
            showMessage(error.message || 'Erro ao enviar comentario.', 'error');
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
        const comment = findCommentById(state.comments, commentId);
        const target = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (!comment || !target || state.editId === Number(commentId)) return;

        clearReplyState();
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
            showMessage('O comentario nao pode estar vazio.', 'error');
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
            const data = await parseJsonResponse(response);
            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao editar comentario.');
            }

            const updatedComment = data.comment || {};
            state.comments = updateCommentTree(state.comments, commentId, (comment) => ({
                ...comment,
                ...updatedComment
            }));
            renderComments(state.comments);
            cancelEditing();
            showMessage('Comentario editado com sucesso!', 'success');
        } catch (error) {
            console.error('Erro ao editar comentario:', error);
            showMessage(error.message || 'Erro ao editar comentario.', 'error');
        }
    }

    async function deleteComment(commentId) {
        if (!window.confirm('Tem certeza que deseja deletar este comentario?')) {
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
            const data = await parseJsonResponse(response);
            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Erro ao deletar comentario.');
            }

            const removal = removeCommentFromTree(state.comments, commentId);
            state.comments = removal.comments;
            renderComments(state.comments);
            showMessage('Comentario deletado com sucesso!', 'success');
        } catch (error) {
            console.error('Erro ao deletar comentario:', error);
            showMessage(error.message || 'Erro ao deletar comentario.', 'error');
        }
    }

    function bindForm() {
        const { form, replyState } = getElements();
        if (!form || form.dataset.commentsBound === 'true') return;

        form.dataset.commentsBound = 'true';
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            event.stopPropagation();
            submitComment();
        });

        replyState?.addEventListener('click', (event) => {
            const cancelButton = event.target.closest('[data-comment-cancel-reply]');
            if (!cancelButton) return;
            clearReplyState();
        });
    }

    function bindList() {
        const { list } = getElements();
        if (!list || list.dataset.commentsBound === 'true') return;

        list.dataset.commentsBound = 'true';
        list.addEventListener('click', (event) => {
            const replyButton = event.target.closest('[data-comment-reply]');
            if (replyButton) {
                startReply(Number(replyButton.dataset.commentReply));
                return;
            }

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
            state.editId = null;
            clearReplyState();
            return;
        }

        if (state.postId !== postId) {
            state.snapshot = '';
            state.comments = [];
            state.editId = null;
            clearReplyState();
            state.pendingReplyId = new URLSearchParams(window.location.search).get('reply_to');
        }

        state.postId = postId;
        bindForm();
        bindList();
        fetchComments(true);
        startPolling();
    }

    window.CommentSystem = {
        init,
        refresh: () => fetchComments(true),
        replyTo(commentId) {
            state.pendingReplyId = String(commentId || '');
            applyPendingReplyIntent();
        }
    };

    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('pageLoaded', init);
})();
