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