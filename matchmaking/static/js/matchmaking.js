const StreamChatController = {
    client: null,

    async getSDK() {
        if (window.StreamChat) return window.StreamChat;

        return new Promise((resolve, reject) => {
            let attempts = 0;
            const interval = setInterval(() => {
                if (window.StreamChat) {
                    clearInterval(interval);
                    resolve(window.StreamChat);
                }
                attempts++;
                if (attempts > 50) { 
                    clearInterval(interval);
                    reject(new Error("StreamChat SDK failed to load."));
                }
            }, 100);
        });
    },

    async connect() {
        if (this.client) return this.client;
        const SDK = await this.getSDK();

        const res = await fetch("/matchmaking/stream-token/");
        
        if (!res.ok) {
            console.error("Server refused token request:", await res.text());
            throw new Error("Failed to fetch Stream auth token.");
        }
        
        const data = await res.json();
        
        this.client = SDK.getInstance ? SDK.getInstance(data.api_key) : new SDK(data.api_key);
        await this.client.connectUser({ id: String(data.user_id), name: data.username }, data.token);
        
        return this.client;
    },

    async createDealRoom(targetUserId, targetUsername) {
        await this.connect();
        const members = [this.client.userID, String(targetUserId)].sort();
        
        try {
            const channel = this.client.channel('messaging', `deal_${members[0]}_${members[1]}`, {
                name: `Deal Room: ${targetUsername}`,
                members: members,
            });
            
            await channel.create();
            await channel.watch();
            window.location.href = `/matchmaking/deal-room/?cid=${channel.cid}`;
            
        } catch (error) {
            console.error("Channel creation failed:", error);
            if (error.message && error.message.includes("don't exist")) {
                alert(`Cannot open Deal Room yet. User ${targetUsername} has not initialized their chat profile.`);
            } else {
                alert("Failed to create Deal Room. Please try again later.");
            }
        }
    }
};

// ──────────────────────────────────────────────────────────────────────────
// CONTENT SHARE — one shared "Share" modal reused across pitch videos, blog
// articles, and job postings (see sharing/views.py + templates/matchmaking/
// chat.html's resolveShareCard). "Share with Foundry" delivers a structured
// {content_type, content_id} message into the existing Stream DM system —
// no new messaging infrastructure, no new persisted model. "Share
// externally" is just the real page URL, which already self-enforces its
// own access rules on every request.
// ──────────────────────────────────────────────────────────────────────────
const ContentShare = {
    modal: null,
    bsModal: null,
    contentType: null,
    contentId: null,
    externalUrl: null,
    selectedUser: null,
    searchTimer: null,

    _escape(str) {
        const div = document.createElement('div');
        div.textContent = str == null ? '' : str;
        return div.innerHTML;
    },

    ensureModal() {
        if (this.modal) return;
        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
        <div class="modal fade" id="contentShareModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content rounded-4">
              <div class="modal-header border-0 pb-0">
                <h5 class="modal-title fw-bold" id="contentShareTitle">Share</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body pt-2">
                <label class="form-label small fw-semibold text-uppercase text-muted">Share with Foundry</label>
                <input type="text" id="contentShareUserSearch" class="form-control" placeholder="Search Foundry members…" autocomplete="off">
                <div id="contentShareUserResults" class="list-group mt-1" style="max-height: 160px; overflow-y: auto;"></div>
                <div id="contentShareSelectedUser" class="d-none alert alert-light border d-flex justify-content-between align-items-center mt-2 py-2 px-3 mb-0">
                    <span id="contentShareSelectedUserLabel" class="small"></span>
                    <button type="button" class="btn-close" id="contentShareClearUser" aria-label="Clear selected member"></button>
                </div>
                <textarea id="contentShareMessage" class="form-control mt-2" rows="2" placeholder="Add a message (optional)"></textarea>
                <button type="button" class="btn btn-dark w-100 mt-2" id="contentShareSendBtn" disabled>
                    <i class="bi bi-send me-1"></i> Send
                </button>

                <div class="d-flex align-items-center gap-2 my-3">
                    <hr class="flex-grow-1 my-0"><span class="text-muted small">or</span><hr class="flex-grow-1 my-0">
                </div>

                <label class="form-label small fw-semibold text-uppercase text-muted">Share externally</label>
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-outline-secondary flex-grow-1" id="contentShareCopyBtn">
                        <i class="bi bi-link-45deg me-1"></i> Copy Link
                    </button>
                    <button type="button" class="btn btn-outline-secondary flex-grow-1 d-none" id="contentShareNativeBtn">
                        <i class="bi bi-share me-1"></i> Share
                    </button>
                </div>
              </div>
            </div>
          </div>
        </div>`;
        document.body.appendChild(wrapper.firstElementChild);
        this.modal = document.getElementById('contentShareModal');
        this._wireEvents();
    },

    _wireEvents() {
        const searchInput = document.getElementById('contentShareUserSearch');
        const resultsBox = document.getElementById('contentShareUserResults');
        const selectedBox = document.getElementById('contentShareSelectedUser');
        const selectedLabel = document.getElementById('contentShareSelectedUserLabel');
        const clearBtn = document.getElementById('contentShareClearUser');
        const sendBtn = document.getElementById('contentShareSendBtn');
        const copyBtn = document.getElementById('contentShareCopyBtn');
        const nativeBtn = document.getElementById('contentShareNativeBtn');
        const messageInput = document.getElementById('contentShareMessage');

        if (navigator.share) nativeBtn.classList.remove('d-none');

        searchInput.addEventListener('input', () => {
            clearTimeout(this.searchTimer);
            const q = searchInput.value.trim();
            if (q.length < 2) {
                resultsBox.innerHTML = '';
                return;
            }
            this.searchTimer = setTimeout(async () => {
                try {
                    const res = await fetch(`/sharing/user-search/?q=${encodeURIComponent(q)}`, { credentials: 'same-origin' });
                    const data = await res.json();
                    resultsBox.innerHTML = (data.results || []).map(u => `
                        <button type="button" class="list-group-item list-group-item-action py-2"
                                data-user-id="${u.id}" data-username="${this._escape(u.username)}" data-display-name="${this._escape(u.display_name)}">
                            <span class="fw-semibold">${this._escape(u.display_name)}</span>
                            <span class="text-muted small ms-1">@${this._escape(u.username)} · ${this._escape(u.role_label)}</span>
                        </button>`).join('') || '<div class="text-muted small p-2">No members found.</div>';
                } catch (err) {
                    resultsBox.innerHTML = '<div class="text-danger small p-2">Search failed.</div>';
                }
            }, 300);
        });

        resultsBox.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-user-id]');
            if (!btn) return;
            this.selectedUser = { id: btn.dataset.userId, username: btn.dataset.username, displayName: btn.dataset.displayName };
            selectedLabel.textContent = `${btn.dataset.displayName} (@${btn.dataset.username})`;
            selectedBox.classList.remove('d-none');
            searchInput.value = '';
            resultsBox.innerHTML = '';
            sendBtn.disabled = false;
        });

        clearBtn.addEventListener('click', () => {
            this.selectedUser = null;
            selectedBox.classList.add('d-none');
            sendBtn.disabled = true;
        });

        sendBtn.addEventListener('click', async () => {
            if (!this.selectedUser) return;
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Sending…';
            try {
                await this._send(messageInput.value.trim());
                sendBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Sent!';
                setTimeout(() => this._hide(), 900);
            } catch (err) {
                alert(err.message || 'Failed to send. Please try again.');
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="bi bi-send me-1"></i> Send';
            }
        });

        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(this.externalUrl);
                copyBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Copied!';
                setTimeout(() => { copyBtn.innerHTML = '<i class="bi bi-link-45deg me-1"></i> Copy Link'; }, 1500);
            } catch (err) {
                alert('Could not copy link.');
            }
        });

        nativeBtn.addEventListener('click', () => {
            navigator.share({ url: this.externalUrl, title: document.getElementById('contentShareTitle').textContent }).catch(() => {});
        });
    },

    async _send(message) {
        await StreamChatController.connect();

        const res = await fetch(`/matchmaking/chat/initiate/${this.selectedUser.id}/`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        });
        const data = await res.json();
        if (data.status !== 'success') throw new Error(data.message || 'Could not start conversation.');

        const channel = StreamChatController.client.channel('messaging', data.channel_id);
        await channel.watch();
        await channel.sendMessage({
            text: message || '',
            content_type: this.contentType,
            content_id: String(this.contentId),
        });
    },

    _hide() {
        if (this.bsModal) this.bsModal.hide();
    },

    open({ contentType, contentId, title, externalUrl }) {
        this.ensureModal();
        this.contentType = contentType;
        this.contentId = contentId;
        this.externalUrl = externalUrl;
        this.selectedUser = null;

        document.getElementById('contentShareTitle').textContent = title ? `Share “${title}”` : 'Share';
        document.getElementById('contentShareUserSearch').value = '';
        document.getElementById('contentShareUserResults').innerHTML = '';
        document.getElementById('contentShareSelectedUser').classList.add('d-none');
        document.getElementById('contentShareMessage').value = '';
        const sendBtn = document.getElementById('contentShareSendBtn');
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="bi bi-send me-1"></i> Send';

        this.bsModal = bootstrap.Modal.getOrCreateInstance(this.modal);
        this.bsModal.show();
    },
};

function openContentShare(contentType, contentId, title, externalUrl) {
    ContentShare.open({ contentType, contentId, title, externalUrl });
}

// FIX: Updated function signature to match your HTML buttons
async function updateConnection(requestId, actionStatus, targetUserId, targetUsername) {
    const csrftoken = getCookie('csrftoken'); 
    
    // Safely package the data
    const requestData = {
        id: requestId,
        action: actionStatus,
        targetUserId: targetUserId || null,
        targetUsername: targetUsername || "User"
    };
    
    try {
        // FIX: Hardcoded the correct Django endpoint here
        const response = await fetch('/matchmaking/action/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken, 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData) 
        });

        const responseData = await response.json(); 
        console.log("DEBUG: Server response:", responseData);

        if (response.ok && actionStatus === 'ACCEPTED') {
            if (targetUserId) {
                await StreamChatController.createDealRoom(targetUserId, targetUsername);
            } else {
                window.location.reload();
            }
        } else if (response.ok) {
            window.location.reload();
        } else {
            alert("Error: " + (responseData.error || "Action failed."));
            window.location.reload();
        }
    } catch (err) {
        console.error("Connection update failed:", err);
        alert("Network Error: Could not connect to server.");
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}