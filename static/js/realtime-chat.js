(function () {
    if (window.__realtimeChatInitialized) {
        return;
    }
    window.__realtimeChatInitialized = true;

    const CHAT_ROOMS = [
        { id: 'todos', label: 'Todos' },
        { id: 'suporte', label: 'Suporte' }
    ];

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
        input: document.getElementById('chat-message-input'),
        send: document.getElementById('chat-send-btn')
    };

    if (!elements.button || !elements.panel) {
        return;
    }

    const userMeta = {
        isAuthenticated: document.body.dataset.authenticated === 'true',
        isAdmin: document.body.dataset.isAdmin === 'true',
        userId: (document.body.dataset.userId || '').trim(),
        userName: (document.body.dataset.userName || '').trim() || 'Usuario',
        userAvatar: (document.body.dataset.userAvatar || '').trim()
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

    let supportTickets = [];
    let currentTab = 'todos';
    let currentRoomId = 'todos';
    let selectedTicketRoomId = '';
    let panelOpen = false;

    let firestore = null;
    let auth = null;

    const unsubscribers = {
        activeMessages: null,
        todosMeta: null,
        suporteMeta: null,
        chamadosList: null
    };

    function tsToMillis(value) {
        if (!value) return 0;
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

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatMessageTime(createdAt) {
        if (!createdAt || typeof createdAt.toDate !== 'function') {
            return 'agora';
        }

        try {
            return createdAt.toDate().toLocaleTimeString('pt-BR', {
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

    function readFirebaseConfig() {
        const configEl = document.getElementById('firebase-config');
        if (!configEl) return null;

        try {
            const parsed = JSON.parse(configEl.textContent || '{}');
            if (!parsed.apiKey || !parsed.authDomain || !parsed.projectId || !parsed.appId) {
                return null;
            }
            return parsed;
        } catch (error) {
            console.error('[CHAT] Config Firebase invalida:', error);
            return null;
        }
    }

    function getFirebaseApp() {
        if (typeof firebase === 'undefined' || !firebase.initializeApp) {
            return null;
        }

        if (firebase.apps && firebase.apps.length > 0) {
            return firebase.app();
        }

        const config = readFirebaseConfig();
        if (!config) {
            return null;
        }

        return firebase.initializeApp(config);
    }

    function getSupportRoomIdForUser(userId) {
        return `support_user_${userId}`;
    }

    function extractSupportUserId(roomId) {
        if (!roomId || !roomId.startsWith('support_user_')) return '';
        return roomId.replace('support_user_', '');
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

        const updatedAtMs = tsToMillis(meta.updatedAt);
        if (!updatedAtMs) return 0;

        const lastRead = getLastRead(roomId);
        if (updatedAtMs <= lastRead) return 0;

        const lastSenderId = String(meta.lastSenderSiteUserId || '');
        if (lastSenderId && lastSenderId === userMeta.userId) return 0;

        return 1;
    }

    function getUnreadFromTicket(ticket) {
        if (!ticket || !ticket.id || !ticket.data) return 0;

        const updatedAtMs = tsToMillis(ticket.data.updatedAt);
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

    function renderMessages(docs) {
        if (!elements.messages) return;

        if (!docs.length) {
            elements.messages.innerHTML = '<div class="chat-empty-state">Ainda nao ha mensagens nesta conversa.</div>';
            return;
        }

        const ordered = docs.slice().reverse();
        const currentAuthUid = auth && auth.currentUser ? auth.currentUser.uid : '';
        const html = ordered.map((doc) => {
            const data = doc.data() || {};
            const senderName = data.senderName || 'Usuario';
            const text = data.text || '';
            const senderSiteUserId = String(data.senderSiteUserId || '');
            const senderAuthUid = String(data.senderAuthUid || '');

            const mine = (
                (userMeta.userId && senderSiteUserId && userMeta.userId === senderSiteUserId) ||
                (currentAuthUid && senderAuthUid && currentAuthUid === senderAuthUid)
            );

            return `
                <article class="chat-message${mine ? ' mine' : ''}">
                    <div class="chat-message-header">
                        <span class="chat-message-sender">${escapeHtml(senderName)}</span>
                        <span class="chat-message-time">${escapeHtml(formatMessageTime(data.createdAt))}</span>
                    </div>
                    <div class="chat-message-body">${escapeHtml(text)}</div>
                </article>
            `;
        }).join('');

        elements.messages.innerHTML = html;
        elements.messages.scrollTop = elements.messages.scrollHeight;
    }

    function setActiveTab(tabId) {
        currentTab = tabId;
        if (!elements.roomTabs) return;
        elements.roomTabs.querySelectorAll('[data-chat-room]').forEach((button) => {
            button.classList.toggle('active', button.dataset.chatRoom === tabId);
        });
    }

    function updateInputState() {
        if (!elements.input || !elements.send) return;

        let enabled = true;
        if (currentTab === 'chamados' && userMeta.isAdmin) {
            enabled = !!selectedTicketRoomId;
        }

        elements.input.disabled = !enabled;
        elements.send.disabled = !enabled;
        elements.input.placeholder = enabled ? 'Digite sua mensagem...' : 'Selecione um chamado para responder.';
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
            const preview = (ticketData.lastMessage || 'Sem mensagens').slice(0, 70);
            const activeClass = selectedTicketRoomId === ticket.id ? ' active' : '';
            return `
                <button type="button" class="chat-ticket-item${activeClass}" data-ticket-room="${escapeHtml(ticket.id)}">
                    <div class="chat-ticket-main">
                        <strong>${escapeHtml(ownerName)}</strong>
                        <span>${escapeHtml(preview)}</span>
                    </div>
                    ${unread > 0 ? `<span class="chat-ticket-unread">${unread > 99 ? '99+' : unread}</span>` : ''}
                </button>
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
        if (currentTab === 'chamados') {
            switchToRoom(selectedTicketRoomId);
        }
    }

    async function ensureRoomDoc(roomId, extraData) {
        if (!firestore || !roomId) return false;
        const baseData = {
            id: roomId,
            updatedAt: firebase.firestore.FieldValue.serverTimestamp()
        };
        try {
            await firestore.collection('chat_rooms').doc(roomId).set({
                ...baseData,
                ...(extraData || {})
            }, { merge: true });
            return true;
        } catch (error) {
            console.warn(`[CHAT] Falha ao garantir sala ${roomId}:`, error);
            return false;
        }
    }

    async function ensureBaseRooms() {
        const supportRoomId = getSupportRoomIdForUser(userMeta.userId);

        await ensureRoomDoc('todos', {
            type: 'public',
            name: 'Todos'
        });

        await ensureRoomDoc(supportRoomId, {
            type: 'support',
            name: `Suporte - ${userMeta.userName}`,
            ownerSiteUserId: userMeta.userId,
            ownerName: userMeta.userName
        });
    }

    async function fetchChatFirebaseToken() {
        const response = await fetch('/api/chat/firebase-token', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success || !data.token) {
            throw new Error(data.message || 'Falha ao gerar token do chat.');
        }

        return data.token;
    }

    async function ensureFirebaseReady() {
        const app = getFirebaseApp();
        if (!app || !firebase.auth || !firebase.firestore) {
            return false;
        }

        auth = firebase.auth();
        firestore = firebase.firestore();

        const expectedUid = `site_user_${userMeta.userId}`;
        const mustRefreshUser = !auth.currentUser || auth.currentUser.uid !== expectedUid;

        if (mustRefreshUser) {
            try {
                const token = await fetchChatFirebaseToken();
                await auth.signInWithCustomToken(token);
            } catch (error) {
                console.error('[CHAT] Falha ao autenticar no Firebase com token customizado:', error);
                return false;
            }
        }

        return !!(auth.currentUser && auth.currentUser.uid === expectedUid);
    }

    function clearActiveMessagesSubscription() {
        if (typeof unsubscribers.activeMessages === 'function') {
            unsubscribers.activeMessages();
            unsubscribers.activeMessages = null;
        }
    }

    function subscribeActiveRoom(roomId) {
        clearActiveMessagesSubscription();

        if (!roomId || !firestore) {
            elements.messages.innerHTML = '<div class="chat-empty-state">Selecione uma conversa para comecar.</div>';
            return;
        }

        currentRoomId = roomId;
        setStatus(`Conectando na sala ${roomId}...`);

        const query = firestore
            .collection('chat_rooms')
            .doc(roomId)
            .collection('messages')
            .orderBy('createdAt', 'desc')
            .limit(80);

        unsubscribers.activeMessages = query.onSnapshot((snapshot) => {
            renderMessages(snapshot.docs);
            setStatus(`Sala: ${roomId}`, 'ok');
            if (panelOpen) {
                markRoomAsRead(roomId);
            }
        }, (error) => {
            console.error('[CHAT] Erro ao receber mensagens em tempo real:', error);
            setStatus('Erro ao conectar com o chat.', 'error');
        });
    }

    async function switchToRoom(roomId) {
        if (!roomId) {
            const fallbackRoomId = getDefaultRoomForCurrentTab();
            if (fallbackRoomId) {
                subscribeActiveRoom(fallbackRoomId);
                updateInputState();
                if (panelOpen) {
                    markRoomAsRead(fallbackRoomId);
                }
                return;
            }

            currentRoomId = '';
            if (currentTab === 'chamados') {
                elements.messages.innerHTML = '<div class="chat-empty-state">Selecione um chamado para comecar.</div>';
            } else {
                elements.messages.innerHTML = '<div class="chat-empty-state">Ainda nao ha mensagens nesta sala.</div>';
            }
            updateInputState();
            return;
        }

        subscribeActiveRoom(roomId);
        updateInputState();

        if (panelOpen) {
            markRoomAsRead(roomId);
        }
    }

    async function switchTab(tabId) {
        setActiveTab(tabId);

        if (tabId === 'todos') {
            renderTicketList();
            await switchToRoom('todos');
            return;
        }

        if (tabId === 'suporte') {
            renderTicketList();
            const supportRoomId = getSupportRoomIdForUser(userMeta.userId);
            await ensureRoomDoc(supportRoomId, {
                type: 'support',
                name: `Suporte - ${userMeta.userName}`,
                ownerSiteUserId: userMeta.userId,
                ownerName: userMeta.userName
            });
            await switchToRoom(supportRoomId);
            return;
        }

        if (tabId === 'chamados' && userMeta.isAdmin) {
            if (!selectedTicketRoomId && supportTickets.length) {
                selectedTicketRoomId = supportTickets[0].id;
            }
            renderTicketList();
            await switchToRoom(selectedTicketRoomId);
        }
    }

    function buildRoomMetadataForMessage(roomId, messageText) {
        const baseMeta = {
            updatedAt: firebase.firestore.FieldValue.serverTimestamp(),
            lastMessage: String(messageText || '').slice(0, 140),
            lastSender: userMeta.userName,
            lastSenderRole: userMeta.isAdmin ? 'admin' : 'user',
            lastSenderSiteUserId: userMeta.userId
        };

        if (roomId === 'todos') {
            return {
                ...baseMeta,
                type: 'public',
                name: 'Todos'
            };
        }

        if (roomId.startsWith('support_user_')) {
            const ownerId = extractSupportUserId(roomId) || userMeta.userId;
            const ticket = supportTickets.find((item) => item.id === roomId);
            const ownerName = ticket?.data?.ownerName || (ownerId === userMeta.userId ? userMeta.userName : `Usuario ${ownerId}`);
            return {
                ...baseMeta,
                type: 'support',
                name: `Suporte - ${ownerName}`,
                ownerSiteUserId: ownerId,
                ownerName: ownerName
            };
        }

        return baseMeta;
    }

    async function sendMessage(text) {
        if (!firestore || !auth || !auth.currentUser || !currentRoomId) {
            throw new Error('Chat ainda esta conectando.');
        }

        await firestore
            .collection('chat_rooms')
            .doc(currentRoomId)
            .collection('messages')
            .add({
                text,
                senderName: userMeta.userName,
                senderAvatar: userMeta.userAvatar,
                senderRole: userMeta.isAdmin ? 'admin' : 'user',
                senderSiteUserId: userMeta.userId || null,
                senderAuthUid: auth.currentUser.uid,
                createdAt: firebase.firestore.FieldValue.serverTimestamp()
            });

        await firestore.collection('chat_rooms').doc(currentRoomId).set(
            buildRoomMetadataForMessage(currentRoomId, text),
            { merge: true }
        );
    }

    function subscribeRoomMeta() {
        if (!firestore) return;

        const supportRoomId = getSupportRoomIdForUser(userMeta.userId);

        unsubscribers.todosMeta = firestore.collection('chat_rooms').doc('todos').onSnapshot((docSnap) => {
            roomMetaCache.todos = docSnap.exists ? (docSnap.data() || null) : null;
            refreshUnreadBadges();
        });

        unsubscribers.suporteMeta = firestore.collection('chat_rooms').doc(supportRoomId).onSnapshot((docSnap) => {
            roomMetaCache.suporte = docSnap.exists ? (docSnap.data() || null) : null;
            refreshUnreadBadges();
        });

        if (userMeta.isAdmin) {
            unsubscribers.chamadosList = firestore
                .collection('chat_rooms')
                .where('type', '==', 'support')
                .orderBy('updatedAt', 'desc')
                .limit(80)
                .onSnapshot((snapshot) => {
                    supportTickets = snapshot.docs.map((doc) => ({
                        id: doc.id,
                        data: doc.data() || {}
                    }));

                    if (currentTab === 'chamados') {
                        if (!selectedTicketRoomId || !supportTickets.some((item) => item.id === selectedTicketRoomId)) {
                            selectedTicketRoomId = supportTickets.length ? supportTickets[0].id : '';
                            switchToRoom(selectedTicketRoomId);
                        }
                    }

                    renderTicketList();
                    refreshUnreadBadges();
                }, (error) => {
                    console.error('[CHAT] Erro ao listar chamados:', error);
                });
        }
    }

    function openPanel() {
        panelOpen = true;
        elements.panel.classList.add('open');
        elements.panel.setAttribute('aria-hidden', 'false');
        elements.button.classList.add('active');

        if (currentRoomId) {
            markRoomAsRead(currentRoomId);
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
        const ready = await ensureFirebaseReady();
        if (!ready) {
            setStatus('Falha ao conectar com o chat.', 'error');
            return;
        }

        try {
            await ensureBaseRooms();
            subscribeRoomMeta();
            await switchTab('todos');
        } catch (error) {
            console.error('[CHAT] Erro ao inicializar chat em tempo real:', error);
            setStatus('Falha ao inicializar o chat.', 'error');
        }
    }

    function setupAccessControl() {
        if (!userMeta.isAuthenticated || !userMeta.userId) {
            elements.button.style.display = 'none';
            elements.panel.style.display = 'none';
            window.openLiveChat = redirectToLogin;
            return false;
        }

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
                const ticketButton = event.target.closest('[data-ticket-room]');
                if (!ticketButton) return;
                const roomId = ticketButton.dataset.ticketRoom;
                if (!roomId || roomId === selectedTicketRoomId) return;
                selectTicket(roomId);
            });
        }

        if (elements.form) {
            elements.form.addEventListener('submit', async (event) => {
                event.preventDefault();

                const text = (elements.input.value || '').trim();
                if (!text) return;

                elements.send.disabled = true;
                try {
                    await sendMessage(text);
                    elements.input.value = '';
                    markRoomAsRead(currentRoomId);
                } catch (error) {
                    console.error('[CHAT] Erro ao enviar mensagem:', error);
                    if (typeof window.showNotification === 'function') {
                        window.showNotification('Nao foi possivel enviar a mensagem. Tente novamente.', 'error');
                    } else {
                        alert('Nao foi possivel enviar a mensagem.');
                    }
                } finally {
                    updateInputState();
                }
            });
        }
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
