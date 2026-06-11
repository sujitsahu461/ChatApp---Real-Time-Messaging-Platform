// ============================================================
// ChatApp — WebSocket-powered chat + Browser Notifications
// ============================================================

let activeUserId = null;
let activeUserName = null;
let activeUserPic = null;
let chatSocket = null;
let notifSocket = null;
let notifToastTimeout = null;
let onlineUserIds = new Set();

// ============================================================
// ONLINE STATUS
// ============================================================

function updateOnlineStatus(userId, status) {
    const dot = document.getElementById('online-dot-' + userId);
    if (dot) {
        dot.classList.toggle('online', status === 'online');
    }

    // Update chat header if we're chatting with this user
    if (userId === activeUserId) {
        const headerStatus = document.getElementById('chatHeaderStatus');
        if (headerStatus) {
            headerStatus.textContent = status === 'online' ? 'online' : 'offline';
            headerStatus.style.color = status === 'online' ? '#00a884' : '#8696a0';
        }
    }
}

function setAllOnlineStatuses() {
    document.querySelectorAll('.online-dot').forEach(dot => {
        const uid = parseInt(dot.dataset.userid);
        dot.classList.toggle('online', onlineUserIds.has(uid));
    });
}

// ============================================================
// NOTIFICATION SYSTEM — connects on page load
// ============================================================

function connectNotifications() {
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    notifSocket = new WebSocket(`${wsScheme}://${window.location.host}/ws/notifications/`);

    notifSocket.onopen = () => {
        console.log('🔔 Notification WebSocket connected');
    };

    notifSocket.onmessage = (e) => {
        const data = JSON.parse(e.data);

        // Handle online users list (sent on connect)
        if (data.type === 'online_users') {
            onlineUserIds = new Set(data.users);
            setAllOnlineStatuses();
        }

        // Handle presence updates (user comes online/offline)
        if (data.type === 'presence') {
            if (data.status === 'online') {
                onlineUserIds.add(data.user_id);
            } else {
                onlineUserIds.delete(data.user_id);
            }
            updateOnlineStatus(data.user_id, data.status);
        }

        // Handle chat notifications
        if (data.type === 'notification') {
            const msg = data.message;
            // Don't notify if we're already chatting with this person
            if (msg.sender_id === activeUserId) return;

            // Show in-app toast
            showNotificationToast(msg);

            // Show browser notification
            showBrowserNotification(msg);

            // Update unread badge
            const badge = document.getElementById('unread-' + msg.sender_id);
            if (badge) {
                const current = parseInt(badge.textContent) || 0;
                badge.textContent = current + 1;
                badge.style.display = 'flex';
            }

            // Update sidebar preview
            const preview = document.getElementById('last-msg-' + msg.sender_id);
            const timeEl = document.getElementById('last-time-' + msg.sender_id);
            if (preview) preview.textContent = msg.content;
            if (timeEl) timeEl.textContent = msg.timestamp;
        }
    };

    notifSocket.onclose = () => {
        console.log('🔔 Notification WebSocket disconnected, reconnecting...');
        setTimeout(connectNotifications, 3000);
    };

    notifSocket.onerror = (err) => {
        console.error('Notification WS error:', err);
    };
}

// Request browser notification permission
function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// Show browser notification
function showBrowserNotification(msg) {
    if ('Notification' in window && Notification.permission === 'granted') {
        const notif = new Notification(`💬 ${msg.sender_username}`, {
            body: msg.content,
            icon: msg.sender_pic || undefined,
            tag: `chat-${msg.sender_id}`,
            silent: false,
        });
        notif.onclick = () => {
            window.focus();
            const contactEl = document.getElementById('contact-' + msg.sender_id);
            if (contactEl) {
                const pic = contactEl.dataset.pic || '';
                openChat(msg.sender_id, msg.sender_username, pic);
            }
            notif.close();
        };
        setTimeout(() => notif.close(), 5000);
    }
}

// Show in-app notification toast
function showNotificationToast(msg) {
    const toast = document.getElementById('notifToast');
    const avatarArea = document.getElementById('toastAvatarArea');
    const nameEl = document.getElementById('toastName');
    const msgEl = document.getElementById('toastMsg');

    if (msg.sender_pic) {
        avatarArea.innerHTML = `<img class="toast-avatar" src="${msg.sender_pic}" alt="${msg.sender_username}">`;
    } else {
        avatarArea.innerHTML = `<div class="toast-avatar-placeholder">${msg.sender_username[0].toUpperCase()}</div>`;
    }
    nameEl.textContent = msg.sender_username;
    msgEl.textContent = msg.content;

    toast.onclick = () => {
        hideNotificationToast();
        const contactEl = document.getElementById('contact-' + msg.sender_id);
        if (contactEl) {
            const pic = contactEl.dataset.pic || '';
            openChat(msg.sender_id, msg.sender_username, pic);
        }
    };

    toast.classList.add('show');

    if (notifToastTimeout) clearTimeout(notifToastTimeout);
    notifToastTimeout = setTimeout(hideNotificationToast, 4000);
}

function hideNotificationToast() {
    document.getElementById('notifToast').classList.remove('show');
}

// ============================================================
// CHAT WebSocket
// ============================================================

function openChat(userId, username, picUrl) {
    activeUserId = userId;
    activeUserName = username;
    activeUserPic = picUrl;

    // Mark contact as active
    document.querySelectorAll('.contact-item').forEach(el => el.classList.remove('active'));
    const contactEl = document.getElementById('contact-' + userId);
    if (contactEl) contactEl.classList.add('active');

    // Reset unread badge
    const badge = document.getElementById('unread-' + userId);
    if (badge) badge.style.display = 'none';

    // Show chat area
    document.getElementById('welcomeScreen').style.display = 'none';
    const chatArea = document.getElementById('chatArea');
    chatArea.style.display = 'flex';

    // Update header
    const headerAvatar = document.getElementById('chatHeaderAvatar');
    if (picUrl) {
        headerAvatar.innerHTML = `<img class="contact-avatar" src="${picUrl}" alt="${username}">`;
    } else {
        headerAvatar.innerHTML = `<div class="contact-avatar-placeholder">${username[0].toUpperCase()}</div>`;
    }
    document.getElementById('chatHeaderName').textContent = username;

    // Update online status in header
    const headerStatus = document.getElementById('chatHeaderStatus');
    const isOnline = onlineUserIds.has(userId);
    headerStatus.textContent = isOnline ? 'online' : 'offline';
    headerStatus.style.color = isOnline ? '#00a884' : '#8696a0';

    // Clear messages
    document.getElementById('messagesArea').innerHTML = '';

    // Close existing chat socket
    if (chatSocket) {
        chatSocket.close();
        chatSocket = null;
    }

    // Open WebSocket for this chat
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    chatSocket = new WebSocket(`${wsScheme}://${window.location.host}/ws/chat/${userId}/`);

    const connStatus = document.getElementById('connStatus');

    chatSocket.onopen = () => {
        console.log(`💬 Chat WebSocket connected with ${username}`);
        connStatus.classList.remove('disconnected');
    };

    chatSocket.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === 'history') {
            const area = document.getElementById('messagesArea');
            area.innerHTML = '';
            data.messages.forEach(msg => {
                const isSent = msg.sender_id === CURRENT_USER_ID;
                appendMessage(msg, isSent, area);
            });
            area.scrollTop = area.scrollHeight;

            if (data.messages.length > 0) {
                const lastMsg = data.messages[data.messages.length - 1];
                const preview = document.getElementById('last-msg-' + activeUserId);
                const timeEl = document.getElementById('last-time-' + activeUserId);
                if (preview) preview.textContent = lastMsg.content;
                if (timeEl) timeEl.textContent = lastMsg.timestamp;
            }
        }

        if (data.type === 'message') {
            const msg = data.message;
            const isSent = msg.sender_id === CURRENT_USER_ID;
            const area = document.getElementById('messagesArea');
            appendMessage(msg, isSent, area);
            area.scrollTop = area.scrollHeight;

            const preview = document.getElementById('last-msg-' + activeUserId);
            const timeEl = document.getElementById('last-time-' + activeUserId);
            if (preview) preview.textContent = msg.content;
            if (timeEl) timeEl.textContent = msg.timestamp;
        }
    };

    chatSocket.onclose = () => {
        console.log('💬 Chat WebSocket disconnected');
        connStatus.classList.add('disconnected');
        connStatus.textContent = '🔄 Reconnecting...';
        setTimeout(() => {
            if (activeUserId === userId) {
                openChat(userId, username, picUrl);
            }
        }, 3000);
    };

    chatSocket.onerror = (err) => {
        console.error('Chat WS error:', err);
    };

    // Focus input
    document.getElementById('messageInput').focus();
}

// ============================================================
// SEND MESSAGE
// ============================================================

function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    if (!content || !chatSocket || chatSocket.readyState !== WebSocket.OPEN) return;

    chatSocket.send(JSON.stringify({ message: content }));
    input.value = '';
    input.focus();
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// ============================================================
// MESSAGE RENDERING
// ============================================================

function appendMessage(msg, isSent, container) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper ' + (isSent ? 'sent' : 'received');

    let avatarHtml = '';
    if (!isSent) {
        if (msg.sender_pic) {
            avatarHtml = `<img class="msg-avatar" src="${msg.sender_pic}" alt="${msg.sender_username}">`;
        } else if (msg.sender_username) {
            avatarHtml = `<div class="msg-avatar-placeholder">${msg.sender_username[0].toUpperCase()}</div>`;
        }
    }

    wrapper.innerHTML = `
        ${avatarHtml}
        <div class="message-bubble ${isSent ? 'sent' : 'received'}">
            ${escapeHtml(msg.content)}
            <span class="msg-time">${msg.timestamp}</span>
        </div>
    `;
    container.appendChild(wrapper);
}

// ============================================================
// UI HELPERS
// ============================================================

function filterContacts() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    document.querySelectorAll('.contact-item').forEach(item => {
        const name = item.querySelector('.contact-name').textContent.toLowerCase();
        item.style.display = name.includes(query) ? 'flex' : 'none';
    });
}

// Profile modal
function openProfileModal() {
    document.getElementById('profileModal').classList.add('open');
}
function closeProfileModal() {
    document.getElementById('profileModal').classList.remove('open');
}
document.getElementById('profileModal').addEventListener('click', function(e) {
    if (e.target === this) closeProfileModal();
});

// Signout modal
function openSignoutModal() {
    document.getElementById('signoutModal').classList.add('open');
}
function closeSignoutModal() {
    document.getElementById('signoutModal').classList.remove('open');
}
document.getElementById('signoutModal').addEventListener('click', function(e) {
    if (e.target === this) closeSignoutModal();
});

// Profile picture preview
function previewImage(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('modalPreviewImg');
            const placeholder = document.getElementById('modalPreviewPlaceholder');
            if (preview) {
                preview.src = e.target.result;
            } else if (placeholder) {
                const img = document.createElement('img');
                img.className = 'modal-avatar-preview';
                img.id = 'modalPreviewImg';
                img.src = e.target.result;
                placeholder.replaceWith(img);
            }
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

// ============================================================
// INIT — runs on page load
// ============================================================

requestNotificationPermission();
connectNotifications();
