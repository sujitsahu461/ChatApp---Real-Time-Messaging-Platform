// ============================================================
// ChatApp — WhatsApp-style chat JS
// ============================================================

let activeUserId = null;
let activeUserName = null;
let activeUserPic = null;
let pollingInterval = null;
let lastMessageId = 0;

// ---- Open a chat with a user ----
function openChat(userId, username, picUrl) {
    activeUserId = userId;
    activeUserName = username;
    activeUserPic = picUrl;
    lastMessageId = 0;

    // Mark contact as active in sidebar
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

    // Clear messages
    document.getElementById('messagesArea').innerHTML = '';

    // Load messages immediately
    fetchMessages();

    // Start polling every 2 seconds
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(fetchMessages, 2000);

    // Focus input
    document.getElementById('messageInput').focus();
}

// ---- Fetch messages from server ----
function fetchMessages() {
    if (!activeUserId) return;

    fetch(`/get_messages/${activeUserId}/`)
        .then(res => res.json())
        .then(data => {
            if (!data.messages) return;

            const area = document.getElementById('messagesArea');
            const isAtBottom = area.scrollHeight - area.scrollTop <= area.clientHeight + 60;

            // Only render new messages
            const newMessages = data.messages.filter(m => m.id > lastMessageId);
            if (newMessages.length === 0) return;

            newMessages.forEach(msg => {
                lastMessageId = Math.max(lastMessageId, msg.id);
                const isSent = msg.sender_id === CURRENT_USER_ID;
                appendMessage(msg, isSent, area);
            });

            // Update sidebar preview
            const lastMsg = data.messages[data.messages.length - 1];
            if (lastMsg) {
                const preview = document.getElementById('last-msg-' + activeUserId);
                const timeEl = document.getElementById('last-time-' + activeUserId);
                if (preview) preview.textContent = lastMsg.content;
                if (timeEl) timeEl.textContent = lastMsg.timestamp;
            }

            // Auto-scroll if user was near bottom
            if (isAtBottom) {
                area.scrollTop = area.scrollHeight;
            }
        })
        .catch(err => console.error('Fetch messages error:', err));
}

// ---- Append a single message bubble ----
function appendMessage(msg, isSent, container) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper ' + (isSent ? 'sent' : 'received');
    wrapper.id = 'msg-' + msg.id;

    // Avatar
    let avatarHtml = '';
    if (!isSent) {
        if (msg.sender_pic) {
            avatarHtml = `<img class="msg-avatar" src="${msg.sender_pic}" alt="${msg.sender_username}">`;
        } else {
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

// ---- Send a message ----
function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    if (!content || !activeUserId) return;

    input.value = '';

    fetch('/send_message/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN,
        },
        body: JSON.stringify({
            receiver_id: activeUserId,
            content: content,
        }),
    })
    .then(res => res.json())
    .then(msg => {
        if (msg.error) {
            console.error('Send error:', msg.error);
            return;
        }
        const area = document.getElementById('messagesArea');
        lastMessageId = Math.max(lastMessageId, msg.id);
        appendMessage({
            id: msg.id,
            content: msg.content,
            timestamp: msg.timestamp,
            sender_id: CURRENT_USER_ID,
            sender_username: '',
            sender_pic: '',
        }, true, area);
        area.scrollTop = area.scrollHeight;

        // Update sidebar preview
        const preview = document.getElementById('last-msg-' + activeUserId);
        const timeEl = document.getElementById('last-time-' + activeUserId);
        if (preview) preview.textContent = msg.content;
        if (timeEl) timeEl.textContent = msg.timestamp;
    })
    .catch(err => console.error('Send message error:', err));
}

// ---- Enter key to send ----
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// ---- Filter contacts by search ----
function filterContacts() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    document.querySelectorAll('.contact-item').forEach(item => {
        const name = item.querySelector('.contact-name').textContent.toLowerCase();
        item.style.display = name.includes(query) ? 'flex' : 'none';
    });
}

// ---- Profile modal ----
function openProfileModal() {
    document.getElementById('profileModal').classList.add('open');
}

function closeProfileModal() {
    document.getElementById('profileModal').classList.remove('open');
}

// Close modal if clicking outside
document.getElementById('profileModal').addEventListener('click', function(e) {
    if (e.target === this) closeProfileModal();
});

// ---- Profile picture preview ----
function previewImage(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('modalPreviewImg');
            const placeholder = document.getElementById('modalPreviewPlaceholder');
            if (preview) {
                preview.src = e.target.result;
            } else if (placeholder) {
                // Replace placeholder with img
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

// ---- Poll unread counts for sidebar badges ----
function pollUnreadCounts() {
    if (!activeUserId) return; // Only check if in a chat
    fetch('/get_unread_counts/')
        .then(res => res.json())
        .then(data => {
            if (!data.counts) return;
            for (const [uid, count] of Object.entries(data.counts)) {
                if (parseInt(uid) === activeUserId) continue; // Don't badge active chat
                const badge = document.getElementById('unread-' + uid);
                if (!badge) continue;
                if (count > 0) {
                    badge.style.display = 'flex';
                    badge.textContent = count;
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(() => {});
}

// Poll for unread badges every 5 seconds
setInterval(pollUnreadCounts, 5000);

// ---- Escape HTML to prevent XSS ----
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}
