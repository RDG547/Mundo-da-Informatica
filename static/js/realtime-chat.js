(function () {
    if (window.__realtimeChatInitialized) {
        return;
    }
    window.__realtimeChatInitialized = true;

    const EDIT_WINDOW_MS = 10 * 60 * 1000;
    const ROOM_STATE_POLL_MS = 5000;
    const ACTIVE_ROOM_POLL_MS = 3000;

    const elements = {
        button: document.getElementById('floating-chat-btn'),
        floatingUnread: document.getElementById('floating-chat-unread'),
        panel: document.getElementById('floating-chat-panel'),
        close: document.getElementById('chat-close-btn'),
        status: document.getElementById('chat-connection-status'),
        roomTabs: document.getElementById('chat-room-tabs'),
        ticketList: document.getElementById('chat-ticket-list'),
        messages: document.getElementById('chat-messages'),
        form: document.getElementById('chat-message-form'),
        composerState: document.getElementById('chat-composer-state'),
        input: document.getElementById('chat-message-input'),
        send: document.getElementById('chat-send-btn')
    };

    if (!elements.button || !elements.panel || !elements.messages || !elements.form || !elements.input || !elements.send) {
        return;
    }

    const userMeta = {
        isAuthenticated: document.body.dataset.authenticated === 'true',
        isAdmin: document.body.dataset.isAdmin === 'true',
        userId: String(document.body.dataset.userId || '').trim(),
        userName: String(document.body.dataset.userName || '').trim() || 'Usuario',
        userAvatar: String(document.body.dataset.userAvatar || '').trim(),
        userPlan: String(document.body.dataset.userPlan || 'free').trim().toLowerCase()
    };

    const tabBadges = {
        todos: document.querySelector('[data-chat-badge="todos"]'),
        suporte: document.querySelector('[data-chat-badge="suporte"]'),
        chamados: document.querySelector('[data-chat-badge="chamados"]')
    };

    const roomMetaCache = {
        todos: null,
        suporte: null
    };

    const pollers = {
        activeMessages: null,
        roomState: null
    };
    const chatPermissions = {
        publicWrite: userMeta.userPlan === 'vip',
        supportWrite: true,
        vipArea: userMeta.userPlan === 'vip'
    };

    let supportTickets = [];
    let activeMessageDocs = [];
    let currentTab = 'todos';
    let currentRoomId = 'todos';
    let selectedTicketRoomId = '';
    let panelOpen = false;
    let bootstrapCompleted = false;
    let draftReply = null;
    let draftEdit = null;
    let chatConfirmState = null;
    let chatConfirmElements = null;

    function getCsrfToken() {
        if (window.csrfUtils && typeof window.csrfUtils.getCsrfToken === 'function') {
            return window.csrfUtils.getCsrfToken();
        }
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }

    async function apiJson(url, options = {}) {
        const requestOptions = {
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                ...(options.headers || {})
            },
            ...options
        };

        if (requestOptions.body && typeof requestOptions.body !== 'string' && !(requestOptions.body instanceof FormData)) {
            requestOptions.headers['Content-Type'] = 'application/json';
            requestOptions.body = JSON.stringify(requestOptions.body);
        }

        const method = String(requestOptions.method || 'GET').toUpperCase();
        if (method !== 'GET' && method !== 'HEAD') {
            const csrfToken = getCsrfToken();
            if (csrfToken) {
                requestOptions.headers['X-CSRFToken'] = csrfToken;
            }
        }

        const response = await fetch(url, requestOptions);
        const payload = await response.json().catch(() => ({}));

        if (!response.ok || payload.success === false) {
            throw new Error(payload.message || payload.error || 'Falha ao processar a solicitacao.');
        }

        return payload;
    }

    function tsToMillis(value) {
        if (!value) return 0;
        if (typeof value === 'number') return value;
        if (typeof value === 'string') {
            const parsed = Date.parse(value);
            return Number.isNaN(parsed) ? 0 : parsed;
        }
        if (typeof value.updatedAtMs === 'number') return value.updatedAtMs;
        if (typeof value.createdAtMs === 'number') return value.createdAtMs;
        if (typeof value.editedAtMs === 'number') return value.editedAtMs;
        if (typeof value.toMillis === 'function') return value.toMillis();
        if (typeof value.toDate === 'function') return value.toDate().getTime();
        return 0;
    }

    function setStatus(message, type) {
        if (!elements.status) return;
        elements.status.textContent = message;
        elements.status.classList.remove('is-error', 'is-ok');
        if (type === 'error') elements.status.classList.add('is-error');
        if (type === 'ok') elements.status.classList.add('is-ok');
    }

    function notifyUser(message, type) {
        if (typeof window.showSiteToast === 'function') {
            window.showSiteToast(message, type || 'info');
            return;
        }
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type || 'info');
            return;
        }
        window.alert(message);
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function normalizePlan(value) {
        const normalized = String(value || 'free').trim().toLowerCase();
        return ['free', 'premium', 'vip', 'admin'].includes(normalized) ? normalized : 'free';
    }

    function getPlanBadgeData(plan, role) {
        if (String(role || '').trim().toLowerCase() === 'admin') {
            return {
                key: 'admin',
                label: 'Admin',
                icon: 'fas fa-shield-halved'
            };
        }

        const normalizedPlan = normalizePlan(plan);
        if (normalizedPlan === 'vip') {
            return {
                key: 'vip',
                label: 'VIP',
                icon: 'fas fa-crown'
            };
        }

        if (normalizedPlan === 'premium') {
            return {
                key: 'premium',
                label: 'Premium',
                icon: 'fas fa-star'
            };
        }

        return {
            key: 'free',
            label: 'Gratis',
            icon: 'fas fa-user'
        };
    }

    function renderPlanBadge(plan, role, options = {}) {
        const badge = getPlanBadgeData(plan, role);
        const compactClass = options.compact ? ' is-compact' : '';
        return `
            <span class="chat-plan-badge is-${badge.key}${compactClass}">
                <i class="${badge.icon}"></i>
                ${escapeHtml(badge.label)}
            </span>
        `;
    }

    function resolveMessagePlan(data) {
        const senderRole = String(data.senderRole || '').trim().toLowerCase();
        if (senderRole === 'admin') {
            return 'admin';
        }

        if (Object.prototype.hasOwnProperty.call(data, 'senderPlan')) {
            return normalizePlan(data.senderPlan);
        }

        if (isMessageMine(data)) {
            return normalizePlan(userMeta.userPlan);
        }

        const senderSiteUserId = String(data.senderSiteUserId || '');
        const roomMeta = getRoomMeta(currentRoomId) || {};
        const ownerSiteUserId = String(roomMeta.ownerSiteUserId || '');
        if (senderSiteUserId && ownerSiteUserId && senderSiteUserId === ownerSiteUserId) {
            return normalizePlan(roomMeta.ownerPlan);
        }

        return 'free';
    }

    function ensureChatConfirmDialog() {
        if (chatConfirmElements) {
            return chatConfirmElements;
        }

        const overlay = document.createElement('div');
        overlay.className = 'chat-confirm-overlay';
        overlay.hidden = true;
        overlay.innerHTML = `
            <div class="chat-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="chat-confirm-title">
                <div class="chat-confirm-icon">
                    <i class="fas fa-trash-alt"></i>
                </div>
                <div class="chat-confirm-copy">
                    <h5 id="chat-confirm-title">Confirmar exclusão</h5>
                    <p id="chat-confirm-message">Deseja continuar com esta ação?</p>
                </div>
                <div class="chat-confirm-actions">
                    <button type="button" class="chat-confirm-btn is-secondary" data-chat-confirm-cancel>Cancelar</button>
                    <button type="button" class="chat-confirm-btn is-danger" data-chat-confirm-accept>Excluir</button>
                </div>
            </div>
        `;

        elements.panel.appendChild(overlay);

        const title = overlay.querySelector('#chat-confirm-title');
        const message = overlay.querySelector('#chat-confirm-message');
        const cancel = overlay.querySelector('[data-chat-confirm-cancel]');
        const accept = overlay.querySelector('[data-chat-confirm-accept]');

        const closeConfirm = (confirmed) => {
            if (!chatConfirmState) {
                return;
            }

            const resolver = chatConfirmState.resolve;
            chatConfirmState = null;
            overlay.classList.remove('visible');
            overlay.hidden = true;
            if (resolver) {
                resolver(Boolean(confirmed));
            }
        };

        cancel.addEventListener('click', () => closeConfirm(false));
        accept.addEventListener('click', () => closeConfirm(true));
        overlay.addEventListener('click', (event) => {
            if (event.target === overlay) {
                closeConfirm(false);
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && chatConfirmState) {
                closeConfirm(false);
            }
        });

        chatConfirmElements = { overlay, title, message, cancel, accept };
        return chatConfirmElements;
    }

    function showChatConfirm(options = {}) {
        const confirmElements = ensureChatConfirmDialog();
        confirmElements.title.textContent = options.title || 'Confirmar ação';
        confirmElements.message.textContent = options.message || 'Deseja continuar com esta ação?';
        confirmElements.accept.textContent = options.confirmLabel || 'Confirmar';
        confirmElements.accept.classList.toggle('is-danger', options.intent !== 'primary');
        confirmElements.accept.classList.toggle('is-primary', options.intent === 'primary');
        confirmElements.overlay.hidden = false;

        requestAnimationFrame(() => {
            confirmElements.overlay.classList.add('visible');
        });

        return new Promise((resolve) => {
            chatConfirmState = { resolve };
        });
    }

    function truncateText(value, limit) {
        const normalized = String(value || '').trim();
        if (!normalized) return '';
        if (normalized.length <= limit) return normalized;
        return `${normalized.slice(0, Math.max(0, limit - 1))}...`;
    }

    function formatMessageTime(createdAt) {
        const millis = tsToMillis(createdAt);
        if (!millis) {
            return 'agora';
        }

        try {
            return new Date(millis).toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (_error) {
            return 'agora';
        }
    }

    function getLoginRedirectUrl() {
        const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        return `/login?next=${encodeURIComponent(next || '/')}`;
    }

    function redirectToLogin() {
        window.location.href = getLoginRedirectUrl();
    }

    function getSupportRoomIdForUser(userId) {
        return `support_user_${userId}`;
    }

    function getPlansUrl() {
        return document.querySelector('[data-vip-link]')?.dataset.plansUrl || '/planos';
    }

    function applyServerPermissions(permissions) {
        if (!permissions || typeof permissions !== 'object') {
            return;
        }

        if (typeof permissions.public_write === 'boolean') {
            chatPermissions.publicWrite = permissions.public_write;
        }

        if (typeof permissions.support_write === 'boolean') {
            chatPermissions.supportWrite = permissions.support_write;
        }

        if (typeof permissions.vip_area === 'boolean') {
            chatPermissions.vipArea = permissions.vip_area;
        }
    }

    function extractSupportUserId(roomId) {
        if (!roomId || !roomId.startsWith('support_user_')) return '';
        return roomId.replace('support_user_', '');
    }

    function getRoomMeta(roomId) {
        if (!roomId) return null;
        if (roomId === 'todos') return roomMetaCache.todos;
        if (roomId === getSupportRoomIdForUser(userMeta.userId)) return roomMetaCache.suporte;
        const ticket = supportTickets.find((item) => item.id === roomId);
        return ticket ? (ticket.data || null) : null;
    }

    function getRoomLabel(roomId) {
        if (roomId === 'todos') {
            return 'Todos';
        }

        if (roomId && roomId.startsWith('support_user_')) {
            if (currentTab === 'chamados' && userMeta.isAdmin) {
                const roomMeta = getRoomMeta(roomId) || {};
                const ownerName = roomMeta.ownerName || `Usuario ${extractSupportUserId(roomId)}`;
                return `chamado de ${ownerName}`;
            }
            return 'Suporte';
        }

        return 'chat';
    }

    function getConnectingMessage(roomId) {
        if (roomId === 'todos') return 'Conectando a sala Todos...';
        if (roomId && roomId.startsWith('support_user_')) {
            return currentTab === 'chamados' && userMeta.isAdmin
                ? `Conectando ao ${getRoomLabel(roomId)}...`
                : 'Conectando ao suporte...';
        }
        return 'Conectando ao chat...';
    }

    function getConnectedMessage(roomId) {
        if (roomId === 'todos') return 'Conectado a sala Todos.';
        if (roomId && roomId.startsWith('support_user_')) {
            return currentTab === 'chamados' && userMeta.isAdmin
                ? `Conectado ao ${getRoomLabel(roomId)}.`
                : 'Conectado ao suporte.';
        }
        return 'Conectado ao chat.';
    }

    function getConnectionErrorMessage(roomId) {
        if (roomId === 'todos') return 'Erro ao conectar-se a sala Todos.';
        if (roomId && roomId.startsWith('support_user_')) {
            return currentTab === 'chamados' && userMeta.isAdmin
                ? `Erro ao conectar-se ao ${getRoomLabel(roomId)}.`
                : 'Erro ao conectar-se ao suporte.';
        }
        return 'Erro ao conectar com o chat.';
    }

    function getReadKey(roomId) {
        return `chat_last_read_${userMeta.userId}_${roomId}`;
    }

    function getLastRead(roomId) {
        try {
            const raw = localStorage.getItem(getReadKey(roomId));
            return raw ? Number(raw) || 0 : 0;
        } catch (_error) {
            return 0;
        }
    }

    function setLastRead(roomId, millis) {
        if (!roomId) return;
        try {
            localStorage.setItem(getReadKey(roomId), String(millis || Date.now()));
        } catch (_error) {
            // ignore
        }
    }

    function setBadge(element, count) {
        if (!element) return;
        const safeCount = Math.max(0, Number(count) || 0);
        if (safeCount <= 0) {
            element.hidden = true;
            element.textContent = '0';
            return;
        }
        element.hidden = false;
        element.textContent = safeCount > 99 ? '99+' : String(safeCount);
    }

    function getUnreadFromRoomMeta(meta, roomId) {
        if (!meta || !roomId) return 0;

        const updatedAtMs = tsToMillis(meta.updatedAt || meta.updatedAtMs);
        if (!updatedAtMs) return 0;

        const lastRead = getLastRead(roomId);
        if (updatedAtMs <= lastRead) return 0;

        const lastSenderId = String(meta.lastSenderSiteUserId || '');
        if (lastSenderId && lastSenderId === userMeta.userId) return 0;

        return 1;
    }

    function getUnreadFromTicket(ticket) {
        if (!ticket || !ticket.id || !ticket.data) return 0;

        const updatedAtMs = tsToMillis(ticket.data.updatedAt || ticket.data.updatedAtMs);
        if (!updatedAtMs) return 0;

        const lastRead = getLastRead(ticket.id);
        if (updatedAtMs <= lastRead) return 0;

        const lastSenderRole = String(ticket.data.lastSenderRole || '').toLowerCase();
        const lastSenderId = String(ticket.data.lastSenderSiteUserId || '');

        if (lastSenderId && lastSenderId === userMeta.userId) return 0;
        if (userMeta.isAdmin && lastSenderRole === 'admin') return 0;

        return 1;
    }

    function refreshUnreadBadges() {
        const supportRoomId = getSupportRoomIdForUser(userMeta.userId);
        const unreadTodos = getUnreadFromRoomMeta(roomMetaCache.todos, 'todos');
        const unreadSuporte = getUnreadFromRoomMeta(roomMetaCache.suporte, supportRoomId);

        let unreadChamados = 0;
        if (userMeta.isAdmin) {
            unreadChamados = supportTickets.reduce((acc, ticket) => acc + getUnreadFromTicket(ticket), 0);
        }

        setBadge(tabBadges.todos, unreadTodos);
        setBadge(tabBadges.suporte, unreadSuporte);
        setBadge(tabBadges.chamados, unreadChamados);
        setBadge(elements.floatingUnread, unreadTodos + unreadSuporte + unreadChamados);
    }

    function markRoomAsRead(roomId) {
        if (!roomId) return;
        setLastRead(roomId, Date.now());
        refreshUnreadBadges();
    }

    function isMessageMine(data) {
        const senderSiteUserId = String(data.senderSiteUserId || '');
        return userMeta.userId && senderSiteUserId && userMeta.userId === senderSiteUserId;
    }

    function findMessageDocById(messageId) {
        return activeMessageDocs.find((doc) => doc.id === messageId) || null;
    }

    function canEditMessageDoc(doc) {
        if (!doc) return false;
        const data = doc.data() || {};
        if (!isMessageMine(data)) return false;
        const createdAtMs = tsToMillis(data.createdAt || data.createdAtMs);
        if (!createdAtMs) return false;
        return (Date.now() - createdAtMs) <= EDIT_WINDOW_MS;
    }

    function canDeleteMessageDoc(doc) {
        if (!doc) return false;

        if (currentRoomId.startsWith('support_user_') && userMeta.isAdmin) {
            return true;
        }

        const data = doc.data() || {};
        if (!isMessageMine(data)) return false;
        const createdAtMs = tsToMillis(data.createdAt || data.createdAtMs);
        if (!createdAtMs) return false;
        return (Date.now() - createdAtMs) <= EDIT_WINDOW_MS;
    }

    function canWriteRoom(roomId) {
        if (!roomId) return false;
        if (roomId === 'todos') return chatPermissions.publicWrite;
        if (roomId.startsWith('support_user_')) {
            return userMeta.isAdmin || (chatPermissions.supportWrite && extractSupportUserId(roomId) === userMeta.userId);
        }
        return false;
    }

    function getRoomRestriction(roomId) {
        if (!roomId || canWriteRoom(roomId)) {
            return null;
        }

        if (roomId === 'todos') {
            return {
                title: 'Sala Todos exclusiva para VIP',
                message: 'Assine o plano VIP para participar do chat ao vivo com a comunidade. A aba Suporte continua liberada para todos os usuarios.',
                ctaLabel: 'Assinar plano VIP',
                ctaKind: 'plans',
                secondaryLabel: 'Ir para suporte',
                secondaryKind: 'support'
            };
        }

        return {
            title: 'Envio indisponivel',
            message: 'Voce nao tem permissao para enviar mensagens nesta conversa.',
            secondaryLabel: 'Ir para suporte',
            secondaryKind: 'support'
        };
    }

    async function promptVipUpgrade(reason) {
        const message = reason
            || 'Este recurso é exclusivo de assinantes do plano VIP. Deseja assinar o plano VIP agora?';

        if (typeof window.showSiteConfirm === 'function') {
            const confirmed = await window.showSiteConfirm({
                title: 'Recurso exclusivo do plano VIP',
                message,
                confirmLabel: 'Quero assinar VIP',
                cancelLabel: 'Cancelar',
                confirmIcon: 'fa-crown',
                cancelIcon: 'fa-circle-xmark',
                intent: 'warning',
                icon: 'fa-crown'
            });

            if (confirmed) {
                window.location.href = getPlansUrl();
            }
            return;
        }

        notifyUser(message, 'warning');
    }

    async function handleRoomRestrictionAttempt(restriction) {
        if (!restriction) {
            return;
        }

        if (restriction.ctaKind === 'plans') {
            await promptVipUpgrade('O envio de mensagens na sala Todos é exclusivo para assinantes VIP. Deseja assinar o plano VIP agora?');
            return;
        }

        notifyUser(restriction.message || 'Voce nao tem permissao para enviar mensagens nesta sala.', 'warning');
    }

    function clearComposerAction(shouldClearInput) {
        draftReply = null;
        draftEdit = null;
        if (shouldClearInput) {
            elements.input.value = '';
        }
        renderComposerState();
    }

    function renderComposerState() {
        if (!elements.composerState) {
            updateInputState();
            return;
        }

        const restriction = currentTab === 'todos' && currentRoomId === 'todos'
            ? getRoomRestriction(currentRoomId)
            : null;
        if (restriction) {
            elements.composerState.hidden = false;
            elements.composerState.innerHTML = `
                <div class="chat-composer-pill is-locked">
                    <div class="chat-composer-copy">
                        <strong>${escapeHtml(restriction.title)}</strong>
                        <span>${escapeHtml(restriction.message)}</span>
                    </div>
                    <div class="chat-composer-actions">
                        ${restriction.secondaryLabel ? `<button type="button" class="chat-composer-action-btn is-secondary" data-chat-cta="${escapeHtml(restriction.secondaryKind)}">${escapeHtml(restriction.secondaryLabel)}</button>` : ''}
                        ${restriction.ctaLabel ? `<button type="button" class="chat-composer-action-btn" data-chat-cta="${escapeHtml(restriction.ctaKind)}">${escapeHtml(restriction.ctaLabel)}</button>` : ''}
                    </div>
                </div>
            `;
            updateInputState();
            return;
        }

        if (draftEdit) {
            elements.composerState.hidden = false;
            elements.composerState.innerHTML = `
                <div class="chat-composer-pill is-editing">
                    <div class="chat-composer-copy">
                        <strong>Editando mensagem</strong>
                        <span>${escapeHtml(truncateText(draftEdit.originalText, 90))}</span>
                    </div>
                    <button type="button" class="chat-composer-cancel" data-chat-cancel-composer aria-label="Cancelar edicao">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            updateInputState();
            return;
        }

        if (draftReply) {
            elements.composerState.hidden = false;
            elements.composerState.innerHTML = `
                <div class="chat-composer-pill is-replying">
                    <div class="chat-composer-copy">
                        <strong>Respondendo a ${escapeHtml(draftReply.senderName || 'Usuario')}</strong>
                        <span>${escapeHtml(truncateText(draftReply.text, 90))}</span>
                    </div>
                    <button type="button" class="chat-composer-cancel" data-chat-cancel-composer aria-label="Cancelar resposta">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            updateInputState();
            return;
        }

        elements.composerState.hidden = true;
        elements.composerState.innerHTML = '';
        updateInputState();
    }

    function startReply(messageId) {
        if (!canWriteRoom(currentRoomId)) {
            renderComposerState();
            handleRoomRestrictionAttempt(getRoomRestriction(currentRoomId)).catch((error) => {
                console.error('[CHAT] Erro ao tratar restricao de resposta:', error);
            });
            return;
        }

        const doc = findMessageDocById(messageId);
        if (!doc) return;
        const data = doc.data() || {};
        draftReply = {
            messageId,
            roomId: currentRoomId,
            senderName: data.senderName || 'Usuario',
            text: data.text || ''
        };
        draftEdit = null;
        renderComposerState();
        elements.input.focus();
    }

    function startEdit(messageId) {
        const doc = findMessageDocById(messageId);
        if (!doc || !canEditMessageDoc(doc)) {
            notifyUser('Voce so pode editar mensagens proprias enviadas ha menos de 10 minutos.', 'warning');
            return;
        }

        const data = doc.data() || {};
        draftEdit = {
            messageId,
            roomId: currentRoomId,
            originalText: data.text || ''
        };
        draftReply = null;
        elements.input.value = data.text || '';
        renderComposerState();
        elements.input.focus();
    }

    function makeMessageDoc(message) {
        const normalizedMessage = {
            ...message,
            createdAt: message.createdAtMs || message.createdAt || 0,
            editedAt: message.editedAtMs || message.editedAt || 0
        };

        return {
            id: String(message.id || ''),
            data() {
                return normalizedMessage;
            }
        };
    }

    function renderMessages(docs) {
        if (!elements.messages) return;

        activeMessageDocs = docs.slice();

        if (!docs.length) {
            elements.messages.innerHTML = '<div class="chat-empty-state">Ainda nao ha mensagens nesta conversa.</div>';
            return;
        }

        const canReplyInRoom = canWriteRoom(currentRoomId);
        const ordered = docs.slice().reverse();
        const html = ordered.map((doc) => {
            const data = doc.data() || {};
            const senderName = data.senderName || 'Usuario';
            const text = data.text || '';
            const mine = isMessageMine(data);
            const canEdit = canEditMessageDoc(doc);
            const planBadge = renderPlanBadge(resolveMessagePlan(data), data.senderRole);
            const replyBlock = data.replyToMessageId || data.replyToText
                ? `
                    <div class="chat-message-reply-preview">
                        <span class="chat-message-reply-name">${escapeHtml(data.replyToSenderName || 'Mensagem respondida')}</span>
                        <span class="chat-message-reply-text">${escapeHtml(truncateText(data.replyToText || '', 110))}</span>
                    </div>
                `
                : '';
            const editedBadge = data.isEdited
                ? '<span class="chat-message-edited">editada</span>'
                : '';
            const replyButton = canReplyInRoom
                ? `
                    <button type="button" class="chat-message-action" data-chat-reply="${escapeHtml(doc.id)}">
                        <i class="fas fa-reply"></i>
                        Responder
                    </button>
                `
                : '';
            const editButton = canEdit
                ? `
                    <button type="button" class="chat-message-action" data-chat-edit="${escapeHtml(doc.id)}">
                        <i class="fas fa-pen"></i>
                        Editar
                    </button>
                `
                : '';
            const deleteButton = canDeleteMessageDoc(doc)
                ? `
                    <button type="button" class="chat-message-action is-danger" data-chat-delete="${escapeHtml(doc.id)}">
                        <i class="fas fa-trash"></i>
                        Excluir
                    </button>
                `
                : '';

            return `
                <article class="chat-message${mine ? ' mine' : ''}" data-message-id="${escapeHtml(doc.id)}">
                    <div class="chat-message-header">
                        <div class="chat-message-sender-wrap">
                            <span class="chat-message-sender">${escapeHtml(senderName)}</span>
                            ${planBadge}
                        </div>
                        <span class="chat-message-time">${escapeHtml(formatMessageTime(data.createdAt || data.createdAtMs))}</span>
                    </div>
                    <div class="chat-message-body">
                        ${replyBlock}
                        <div class="chat-message-text">${escapeHtml(text)}</div>
                    </div>
                    <div class="chat-message-footer">
                        <div class="chat-message-meta">${editedBadge}</div>
                        <div class="chat-message-actions">
                            ${replyButton}
                            ${editButton}
                            ${deleteButton}
                        </div>
                    </div>
                </article>
            `;
        }).join('');

        elements.messages.innerHTML = html;
        elements.messages.scrollTop = elements.messages.scrollHeight;

        if (draftReply && (draftReply.roomId !== currentRoomId || !findMessageDocById(draftReply.messageId))) {
            draftReply = null;
        }

        if (draftEdit && (draftEdit.roomId !== currentRoomId || !findMessageDocById(draftEdit.messageId) || !canEditMessageDoc(findMessageDocById(draftEdit.messageId)))) {
            draftEdit = null;
            elements.input.value = '';
        }

        renderComposerState();
    }

    function setActiveTab(tabId) {
        currentTab = tabId;
        if (!elements.roomTabs) return;
        elements.roomTabs.querySelectorAll('[data-chat-room]').forEach((button) => {
            button.classList.toggle('active', button.dataset.chatRoom === tabId);
        });
    }

    function updateTodosTabState() {
        const todosTab = elements.roomTabs?.querySelector('[data-chat-room="todos"]');
        if (!todosTab) return;
        const isLocked = !canWriteRoom('todos');
        todosTab.classList.toggle('is-locked', isLocked);
        todosTab.setAttribute(
            'title',
            isLocked
                ? 'Sala Todos exclusiva para assinantes VIP'
                : 'Sala publica da comunidade'
        );
    }

    function updateInputState() {
        let enabled = true;
        let placeholder = 'Digite sua mensagem...';

        if (currentTab === 'chamados' && userMeta.isAdmin && !selectedTicketRoomId) {
            enabled = false;
            placeholder = supportTickets.length
                ? 'Selecione um chamado para responder.'
                : 'Nenhum chamado aberto no momento.';
        } else if (draftEdit) {
            placeholder = 'Edite sua mensagem...';
        } else if (draftReply) {
            placeholder = 'Digite sua resposta...';
        }

        const restriction = getRoomRestriction(currentRoomId);
        if (restriction) {
            enabled = false;
            placeholder = restriction.title;
        }

        elements.input.disabled = !enabled;
        elements.send.disabled = !enabled;
        elements.input.placeholder = placeholder;
    }

    function renderTicketList() {
        if (!elements.ticketList) return;

        if (!userMeta.isAdmin || currentTab !== 'chamados') {
            elements.ticketList.hidden = true;
            elements.ticketList.innerHTML = '';
            return;
        }

        elements.ticketList.hidden = false;

        if (!supportTickets.length) {
            elements.ticketList.innerHTML = '<div class="chat-ticket-empty">Nenhum chamado aberto ainda.</div>';
            return;
        }

        const html = supportTickets.map((ticket) => {
            const ticketData = ticket.data || {};
            const unread = getUnreadFromTicket(ticket);
            const ownerName = ticketData.ownerName || `Usuario ${ticketData.ownerSiteUserId || ''}`;
            const preview = truncateText(ticketData.lastMessage || 'Sem mensagens', 70);
            const activeClass = selectedTicketRoomId === ticket.id ? ' active' : '';
            const planBadge = renderPlanBadge(ticketData.ownerPlan, 'user', { compact: true });
            return `
                <div class="chat-ticket-row${activeClass}">
                    <button type="button" class="chat-ticket-item${activeClass}" data-ticket-room="${escapeHtml(ticket.id)}">
                        <div class="chat-ticket-main">
                            <div class="chat-ticket-heading">
                                <strong>${escapeHtml(ownerName)}</strong>
                                ${planBadge}
                            </div>
                            <span>${escapeHtml(preview)}</span>
                        </div>
                        ${unread > 0 ? `<span class="chat-ticket-unread">${unread > 99 ? '99+' : unread}</span>` : ''}
                    </button>
                    <button type="button" class="chat-ticket-delete" data-ticket-delete="${escapeHtml(ticket.id)}" title="Excluir chamado">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;
        }).join('');

        elements.ticketList.innerHTML = html;
    }

    function getDefaultRoomForCurrentTab() {
        if (currentTab === 'todos') {
            return 'todos';
        }

        if (currentTab === 'suporte') {
            return getSupportRoomIdForUser(userMeta.userId);
        }

        if (currentTab === 'chamados' && userMeta.isAdmin) {
            return selectedTicketRoomId || '';
        }

        return '';
    }

    function selectTicket(roomId) {
        selectedTicketRoomId = roomId || '';
        renderTicketList();
        clearComposerAction(true);
        if (currentTab === 'chamados') {
            switchToRoom(selectedTicketRoomId);
        }
    }

    async function bootstrapRoomsFromServer() {
        const data = await apiJson('/api/chat/bootstrap');
        applyServerPermissions(data.permissions);
        bootstrapCompleted = !!data.success;
        return data;
    }

    async function fetchChatState() {
        return apiJson('/api/chat/state');
    }

    async function refreshChatState() {
        const state = await fetchChatState();
        applyServerPermissions(state.permissions);
        roomMetaCache.todos = state.rooms?.todos || null;
        roomMetaCache.suporte = state.rooms?.support || null;

        if (Array.isArray(state.tickets)) {
            hydrateSupportTickets(state.tickets);
        } else if (currentTab === 'chamados' && userMeta.isAdmin) {
            hydrateSupportTickets([]);
        }

        updateTodosTabState();
        refreshUnreadBadges();
        updateInputState();
        return state;
    }

    function hydrateSupportTickets(tickets) {
        supportTickets = (tickets || [])
            .map((ticket) => ({
                id: String(ticket.id || ''),
                data: ticket.data || {}
            }))
            .filter((ticket) => ticket.id.startsWith('support_user_'))
            .sort((a, b) => tsToMillis(b.data.updatedAt || b.data.updatedAtMs) - tsToMillis(a.data.updatedAt || a.data.updatedAtMs));

        if (currentTab === 'chamados') {
            if (!selectedTicketRoomId || !supportTickets.some((item) => item.id === selectedTicketRoomId)) {
                selectedTicketRoomId = supportTickets.length ? supportTickets[0].id : '';
            }
        }

        renderTicketList();
        refreshUnreadBadges();
        updateInputState();
    }

    function showCurrentEmptyState() {
        if (currentTab === 'chamados' && userMeta.isAdmin) {
            if (!supportTickets.length) {
                elements.messages.innerHTML = '<div class="chat-empty-state">Nenhum chamado aberto ainda.</div>';
            } else {
                elements.messages.innerHTML = '<div class="chat-empty-state">Selecione um chamado para comecar.</div>';
            }
            renderComposerState();
            return;
        }

        const restriction = currentTab === 'todos' && currentRoomId === 'todos'
            ? getRoomRestriction(currentRoomId)
            : null;
        if (restriction) {
            elements.messages.innerHTML = `<div class="chat-empty-state">${escapeHtml(restriction.message)}</div>`;
            renderComposerState();
            return;
        }

        elements.messages.innerHTML = '<div class="chat-empty-state">Ainda nao ha mensagens nesta sala.</div>';
        renderComposerState();
    }

    function clearPoller(pollerName) {
        const activePoller = pollers[pollerName];
        if (typeof activePoller === 'function') {
            activePoller();
        }
        pollers[pollerName] = null;
    }

    function startPoller(pollerName, handler, intervalMs) {
        clearPoller(pollerName);
        let isActive = true;

        const run = async () => {
            if (!isActive) {
                return;
            }
            try {
                await handler();
            } catch (error) {
                console.error(`[CHAT] Erro no poller ${pollerName}:`, error);
            }
        };

        run();
        const intervalId = window.setInterval(run, intervalMs);
        pollers[pollerName] = () => {
            isActive = false;
            window.clearInterval(intervalId);
        };
    }

    function clearActiveMessagesSubscription() {
        clearPoller('activeMessages');
    }

    async function loadRoomMessages(roomId) {
        if (!roomId) {
            currentRoomId = '';
            showCurrentEmptyState();
            updateInputState();
            return;
        }

        const data = await apiJson(`/api/chat/rooms/${encodeURIComponent(roomId)}/messages?limit=80`);
        if (roomId !== currentRoomId) {
            return;
        }

        const docs = Array.isArray(data.messages)
            ? data.messages.map(makeMessageDoc)
            : [];

        renderMessages(docs);
        setStatus(getConnectedMessage(roomId), 'ok');
        if (panelOpen) {
            markRoomAsRead(roomId);
        }
    }

    function subscribeActiveRoom(roomId) {
        clearActiveMessagesSubscription();
        clearComposerAction(true);
        activeMessageDocs = [];

        if (!roomId) {
            currentRoomId = '';
            showCurrentEmptyState();
            updateInputState();
            return;
        }

        currentRoomId = roomId;
        setStatus(getConnectingMessage(roomId));
        showCurrentEmptyState();
        updateInputState();

        startPoller('activeMessages', async () => {
            try {
                await loadRoomMessages(roomId);
            } catch (error) {
                if (roomId === currentRoomId) {
                    activeMessageDocs = [];
                    showCurrentEmptyState();
                    setStatus(error.message || getConnectionErrorMessage(roomId), 'error');
                    if (currentTab === 'chamados' && userMeta.isAdmin) {
                        await refreshChatState();
                    }
                }
            }
        }, ACTIVE_ROOM_POLL_MS);
    }

    async function switchToRoom(roomId) {
        if (!roomId) {
            const fallbackRoomId = getDefaultRoomForCurrentTab();
            if (fallbackRoomId) {
                subscribeActiveRoom(fallbackRoomId);
                if (panelOpen) {
                    markRoomAsRead(fallbackRoomId);
                }
                return;
            }

            currentRoomId = '';
            showCurrentEmptyState();
            updateInputState();
            return;
        }

        subscribeActiveRoom(roomId);

        if (panelOpen) {
            markRoomAsRead(roomId);
        }
    }

    async function switchTab(tabId) {
        setActiveTab(tabId);
        currentRoomId = getDefaultRoomForCurrentTab();
        clearComposerAction(true);

        if (tabId === 'todos') {
            renderTicketList();
            await switchToRoom('todos');
            return;
        }

        if (tabId === 'suporte') {
            renderTicketList();
            await switchToRoom(getSupportRoomIdForUser(userMeta.userId));
            return;
        }

        if (tabId === 'chamados' && userMeta.isAdmin) {
            await refreshChatState();
            renderTicketList();
            if (!selectedTicketRoomId && supportTickets.length) {
                selectedTicketRoomId = supportTickets[0].id;
            }
            await switchToRoom(selectedTicketRoomId);
        }
    }

    function buildReplyPayload() {
        if (!draftReply) {
            return {};
        }

        return {
            replyToMessageId: draftReply.messageId,
            replyToSenderName: draftReply.senderName || 'Usuario',
            replyToText: truncateText(draftReply.text || '', 180)
        };
    }

    async function createMessage(text) {
        await apiJson(`/api/chat/rooms/${encodeURIComponent(currentRoomId)}/messages`, {
            method: 'POST',
            body: {
                text,
                ...buildReplyPayload()
            }
        });
        await refreshChatState();
        await loadRoomMessages(currentRoomId);
    }

    async function editMessage(text) {
        if (!draftEdit) {
            throw new Error('Nenhuma mensagem selecionada para edicao.');
        }

        const targetDoc = findMessageDocById(draftEdit.messageId);
        if (!targetDoc || !canEditMessageDoc(targetDoc)) {
            throw new Error('A janela de edicao desta mensagem expirou.');
        }

        await apiJson(`/api/chat/rooms/${encodeURIComponent(currentRoomId)}/messages/${encodeURIComponent(draftEdit.messageId)}`, {
            method: 'PATCH',
            body: { text }
        });
        await refreshChatState();
        await loadRoomMessages(currentRoomId);
    }

    async function deleteMessage(messageId) {
        const targetDoc = findMessageDocById(messageId);
        if (!targetDoc || !canDeleteMessageDoc(targetDoc)) {
            throw new Error('Você não pode excluir esta mensagem.');
        }

        const confirmed = await showChatConfirm({
            title: 'Excluir mensagem?',
            message: 'Deseja excluir esta mensagem do chat?',
            confirmLabel: 'Excluir'
        });
        if (!confirmed) {
            return;
        }

        await apiJson(`/api/chat/rooms/${encodeURIComponent(currentRoomId)}/messages/${encodeURIComponent(messageId)}`, {
            method: 'DELETE'
        });

        if (draftReply && draftReply.messageId === messageId) {
            draftReply = null;
        }

        if (draftEdit && draftEdit.messageId === messageId) {
            draftEdit = null;
            elements.input.value = '';
        }

        await refreshChatState();
        await loadRoomMessages(currentRoomId);
        renderComposerState();
    }

    async function deleteTicket(roomId) {
        if (!userMeta.isAdmin || !roomId) {
            throw new Error('Você não pode excluir este chamado.');
        }

        const confirmed = await showChatConfirm({
            title: 'Excluir chamado?',
            message: 'Deseja excluir este chamado inteiro? Todas as mensagens serão removidas.',
            confirmLabel: 'Excluir chamado'
        });
        if (!confirmed) {
            return;
        }

        const data = await apiJson(`/api/chat/admin/tickets/${encodeURIComponent(roomId)}`, {
            method: 'DELETE'
        });

        supportTickets = supportTickets.filter((ticket) => ticket.id !== roomId);
        renderTicketList();
        refreshUnreadBadges();

        if (selectedTicketRoomId === roomId) {
            selectedTicketRoomId = supportTickets.length ? supportTickets[0].id : '';
            await switchToRoom(selectedTicketRoomId);
        } else {
            updateInputState();
        }

        notifyUser(data.message || 'Chamado excluído com sucesso.', 'success');
    }

    async function sendMessage(text) {
        if (!currentRoomId) {
            throw new Error('Chat ainda esta conectando.');
        }

        const restriction = getRoomRestriction(currentRoomId);
        if (restriction) {
            renderComposerState();
            await handleRoomRestrictionAttempt(restriction);
            return false;
        }

        if (draftEdit) {
            await editMessage(text);
        } else {
            await createMessage(text);
        }

        clearComposerAction(false);
        return true;
    }

    function openPlansForVip() {
        window.location.href = getPlansUrl();
    }

    async function goToSupportTab() {
        await switchTab('suporte');
        openPanel();
    }

    function openPanel() {
        panelOpen = true;
        elements.panel.classList.add('open');
        elements.panel.setAttribute('aria-hidden', 'false');
        elements.button.classList.add('active');

        if (currentRoomId) {
            markRoomAsRead(currentRoomId);
            loadRoomMessages(currentRoomId).catch((error) => {
                console.error('[CHAT] Erro ao carregar mensagens ao abrir painel:', error);
            });
        }

        setTimeout(() => {
            if (elements.input && !elements.input.disabled) {
                elements.input.focus();
            }
        }, 120);
    }

    function closePanel() {
        panelOpen = false;
        elements.panel.classList.remove('open');
        elements.panel.setAttribute('aria-hidden', 'true');
        elements.button.classList.remove('active');
    }

    async function initializeChatConnection() {
        setStatus('Preparando salas do chat...');

        try {
            await bootstrapRoomsFromServer();
            await refreshChatState();
            await switchTab('todos');
            startPoller('roomState', refreshChatState, ROOM_STATE_POLL_MS);
        } catch (error) {
            console.error('[CHAT] Erro ao inicializar chat em tempo real:', error);
            setStatus(error.message || 'Falha ao inicializar o chat.', 'error');
        }
    }

    function setupAccessControl() {
        if (!userMeta.isAuthenticated || !userMeta.userId) {
            elements.button.style.display = 'none';
            elements.panel.style.display = 'none';
            window.openLiveChat = redirectToLogin;
            return false;
        }

        updateTodosTabState();
        updateInputState();
        return true;
    }

    function bindEvents() {
        elements.button.addEventListener('click', () => {
            if (elements.panel.classList.contains('open')) {
                closePanel();
            } else {
                openPanel();
            }
        });

        if (elements.close) {
            elements.close.addEventListener('click', closePanel);
        }

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && elements.panel.classList.contains('open')) {
                closePanel();
            }
        });

        if (elements.roomTabs) {
            elements.roomTabs.addEventListener('click', (event) => {
                const tabButton = event.target.closest('[data-chat-room]');
                if (!tabButton) return;
                const tabId = tabButton.dataset.chatRoom;
                if (!tabId || tabId === currentTab) return;
                switchTab(tabId);
            });
        }

        if (elements.ticketList) {
            elements.ticketList.addEventListener('click', (event) => {
                const deleteButton = event.target.closest('[data-ticket-delete]');
                if (deleteButton) {
                    event.preventDefault();
                    event.stopPropagation();
                    deleteTicket(deleteButton.dataset.ticketDelete).catch((error) => {
                        console.error('[CHAT] Erro ao excluir chamado:', error);
                        notifyUser(error.message || 'Não foi possível excluir o chamado.', 'error');
                    });
                    return;
                }

                const ticketButton = event.target.closest('[data-ticket-room]');
                if (!ticketButton) return;
                const roomId = ticketButton.dataset.ticketRoom;
                if (!roomId || roomId === selectedTicketRoomId) return;
                selectTicket(roomId);
            });
        }

        if (elements.messages) {
            elements.messages.addEventListener('click', (event) => {
                const replyButton = event.target.closest('[data-chat-reply]');
                if (replyButton) {
                    startReply(replyButton.dataset.chatReply);
                    return;
                }

                const editButton = event.target.closest('[data-chat-edit]');
                if (editButton) {
                    startEdit(editButton.dataset.chatEdit);
                    return;
                }

                const deleteButton = event.target.closest('[data-chat-delete]');
                if (deleteButton) {
                    deleteMessage(deleteButton.dataset.chatDelete).catch((error) => {
                        console.error('[CHAT] Erro ao excluir mensagem:', error);
                        notifyUser(error.message || 'Não foi possível excluir a mensagem.', 'error');
                    });
                }
            });
        }

        if (elements.composerState) {
            elements.composerState.addEventListener('click', (event) => {
                const cancelButton = event.target.closest('[data-chat-cancel-composer]');
                if (cancelButton) {
                    clearComposerAction(!!draftEdit);
                    return;
                }

                const ctaButton = event.target.closest('[data-chat-cta]');
                if (!ctaButton) return;

                const ctaType = ctaButton.dataset.chatCta;
                if (ctaType === 'plans') {
                    promptVipUpgrade('O envio de mensagens na sala Todos é exclusivo para assinantes VIP. Deseja assinar o plano VIP agora?').catch((error) => {
                        console.error('[CHAT] Erro ao abrir convite VIP:', error);
                    });
                    return;
                }

                if (ctaType === 'support') {
                    goToSupportTab();
                }
            });
        }

        elements.form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const text = (elements.input.value || '').trim();
            if (!text) return;

            elements.send.disabled = true;
            try {
                const wasSent = await sendMessage(text);
                if (wasSent) {
                    elements.input.value = '';
                    markRoomAsRead(currentRoomId);
                }
            } catch (error) {
                console.error('[CHAT] Erro ao enviar mensagem:', error);
                notifyUser(error.message || 'Não foi possível enviar a mensagem. Tente novamente.', 'error');
            } finally {
                renderComposerState();
                updateInputState();
            }
        });
    }

    function init() {
        if (!setupAccessControl()) {
            return;
        }

        bindEvents();
        initializeChatConnection();
        window.openLiveChat = openPanel;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
