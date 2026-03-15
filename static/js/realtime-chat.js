(function () {
    if (window.__realtimeChatInitialized) {
        return;
    }
    window.__realtimeChatInitialized = true;

    const CHAT_ROOMS = [
        { id: 'todos', label: 'Todos' },
        { id: 'suporte', label: 'Suporte' },
        { id: 'bios', label: 'BIOS' },
        { id: 'drivers', label: 'Drivers' }
    ];

    const elements = {
        button: document.getElementById('floating-chat-btn'),
        panel: document.getElementById('floating-chat-panel'),
        close: document.getElementById('chat-close-btn'),
        status: document.getElementById('chat-connection-status'),
        roomTabs: document.getElementById('chat-room-tabs'),
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
        userId: (document.body.dataset.userId || '').trim(),
        userName: (document.body.dataset.userName || '').trim() || 'Visitante',
        userAvatar: (document.body.dataset.userAvatar || '').trim()
    };

    let currentRoom = 'todos';
    let unsubscribeMessages = null;
    let firestore = null;
    let auth = null;

    function setStatus(message, type) {
        if (!elements.status) return;
        elements.status.textContent = message;
        elements.status.classList.remove('is-error', 'is-ok');
        if (type === 'error') {
            elements.status.classList.add('is-error');
        }
        if (type === 'ok') {
            elements.status.classList.add('is-ok');
        }
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
        } catch (error) {
            return 'agora';
        }
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
            console.error('[CHAT] Config Firebase inválida:', error);
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

    async function ensureFirebaseReady() {
        const app = getFirebaseApp();
        if (!app || !firebase.auth || !firebase.firestore) {
            return false;
        }

        auth = firebase.auth();
        firestore = firebase.firestore();

        if (!auth.currentUser) {
            try {
                await auth.signInAnonymously();
            } catch (error) {
                console.error('[CHAT] Falha ao autenticar anonimamente no Firebase:', error);
                return false;
            }
        }

        return true;
    }

    async function ensureRoomDoc(roomId) {
        if (!firestore) return;
        const roomMeta = CHAT_ROOMS.find((room) => room.id === roomId);
        await firestore.collection('chat_rooms').doc(roomId).set({
            id: roomId,
            name: roomMeta ? roomMeta.label : roomId,
            updatedAt: firebase.firestore.FieldValue.serverTimestamp()
        }, { merge: true });
    }

    function setActiveRoomTab(roomId) {
        if (!elements.roomTabs) return;
        elements.roomTabs.querySelectorAll('[data-chat-room]').forEach((button) => {
            button.classList.toggle('active', button.dataset.chatRoom === roomId);
        });
    }

    function renderMessages(docs) {
        if (!elements.messages) return;

        if (!docs.length) {
            elements.messages.innerHTML = '<div class="chat-empty-state">Ainda não há mensagens nesta sala. Seja o primeiro a falar.</div>';
            return;
        }

        const ordered = docs.slice().reverse();
        const currentAuthUid = auth && auth.currentUser ? auth.currentUser.uid : '';
        const html = ordered.map((doc) => {
            const data = doc.data() || {};
            const senderName = data.senderName || 'Usuário';
            const text = data.text || '';
            const senderSiteUserId = (data.senderSiteUserId || '').toString();
            const senderAuthUid = (data.senderAuthUid || '').toString();

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

    async function subscribeRoom(roomId) {
        if (!firestore) {
            return;
        }

        if (unsubscribeMessages) {
            unsubscribeMessages();
            unsubscribeMessages = null;
        }

        setActiveRoomTab(roomId);
        setStatus(`Conectando na sala ${roomId}...`);

        try {
            await ensureRoomDoc(roomId);
        } catch (error) {
            console.warn('[CHAT] Não foi possível garantir metadados da sala:', error);
        }

        const query = firestore
            .collection('chat_rooms')
            .doc(roomId)
            .collection('messages')
            .orderBy('createdAt', 'desc')
            .limit(60);

        unsubscribeMessages = query.onSnapshot((snapshot) => {
            renderMessages(snapshot.docs);
            setStatus(`Sala: ${roomId}`, 'ok');
        }, (error) => {
            console.error('[CHAT] Erro ao receber mensagens em tempo real:', error);
            setStatus('Erro ao conectar com o chat.', 'error');
        });
    }

    async function switchRoom(roomId) {
        currentRoom = roomId;
        if (!firestore) {
            const ready = await ensureFirebaseReady();
            if (!ready) {
                setStatus('Chat indisponível no momento.', 'error');
                return;
            }
        }

        await subscribeRoom(roomId);
    }

    async function sendMessage(text) {
        if (!firestore || !auth || !auth.currentUser) {
            throw new Error('Chat ainda está conectando.');
        }

        await firestore
            .collection('chat_rooms')
            .doc(currentRoom)
            .collection('messages')
            .add({
                text,
                senderName: userMeta.userName,
                senderAvatar: userMeta.userAvatar,
                senderSiteUserId: userMeta.userId || null,
                senderAuthUid: auth.currentUser.uid,
                createdAt: firebase.firestore.FieldValue.serverTimestamp()
            });

        await firestore.collection('chat_rooms').doc(currentRoom).set({
            updatedAt: firebase.firestore.FieldValue.serverTimestamp(),
            lastMessage: text.slice(0, 140),
            lastSender: userMeta.userName
        }, { merge: true });
    }

    function openPanel() {
        elements.panel.classList.add('open');
        elements.panel.setAttribute('aria-hidden', 'false');
        elements.button.classList.add('active');
        setTimeout(() => {
            if (elements.input && !elements.input.disabled) {
                elements.input.focus();
            }
        }, 120);
    }

    function closePanel() {
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

        await switchRoom(currentRoom);
    }

    function setupAccessControl() {
        if (!elements.input || !elements.send) {
            return;
        }

        if (userMeta.isAuthenticated) {
            elements.input.disabled = false;
            elements.send.disabled = false;
            elements.input.placeholder = 'Digite sua mensagem...';
            return;
        }

        elements.input.disabled = true;
        elements.send.disabled = true;
        elements.input.placeholder = 'Faça login para enviar mensagens.';
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
                const tab = event.target.closest('[data-chat-room]');
                if (!tab) return;

                const roomId = tab.dataset.chatRoom;
                if (!roomId || roomId === currentRoom) return;

                switchRoom(roomId);
            });
        }

        if (elements.form) {
            elements.form.addEventListener('submit', async (event) => {
                event.preventDefault();

                if (!userMeta.isAuthenticated) {
                    if (typeof window.showNotification === 'function') {
                        window.showNotification('Faça login para enviar mensagens no chat.', 'warning');
                    } else {
                        alert('Faça login para enviar mensagens no chat.');
                    }
                    return;
                }

                const text = (elements.input.value || '').trim();
                if (!text) {
                    return;
                }

                elements.send.disabled = true;
                try {
                    await sendMessage(text);
                    elements.input.value = '';
                } catch (error) {
                    console.error('[CHAT] Erro ao enviar mensagem:', error);
                    if (typeof window.showNotification === 'function') {
                        window.showNotification('Não foi possível enviar a mensagem. Tente novamente.', 'error');
                    } else {
                        alert('Não foi possível enviar a mensagem.');
                    }
                } finally {
                    elements.send.disabled = !userMeta.isAuthenticated;
                }
            });
        }
    }

    function init() {
        setupAccessControl();
        bindEvents();
        initializeChatConnection();

        // Compatibilidade com botão de chat em FAQ/outros pontos
        window.openLiveChat = openPanel;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
