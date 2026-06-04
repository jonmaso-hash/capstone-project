const StreamChatController = {
    client: null,

    async getSDK() {
        // 1. Check if it's already there
        if (window.StreamChat) return window.StreamChat;

        // 2. If not, wait for it with a retry loop
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const interval = setInterval(() => {
                if (window.StreamChat) {
                    clearInterval(interval);
                    resolve(window.StreamChat);
                }
                attempts++;
                if (attempts > 50) { // 5 seconds
                    clearInterval(interval);
                    reject(new Error("StreamChat SDK failed to load."));
                }
            }, 100);
        });
    },

    async connect() {
        if (this.client) return this.client;
        const SDK = await this.getSDK();

        // Update this URL to hit the matchmaking app route
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
            
            // Try to create the channel
            await channel.create();
            await channel.watch();
            window.location.href = `/matchmaking/deal-room/?cid=${channel.cid}`;
            
        } catch (error) {
            console.error("Channel creation failed:", error);
            
            // Check if it's the missing user error
            if (error.message && error.message.includes("don't exist")) {
                alert(`Cannot open Deal Room yet. User ${targetUsername} has not initialized their chat profile. They must log in and view their dashboard first.`);
            } else {
                alert("Failed to create Deal Room. Please try again later.");
            }
        }
    }
}; // <-- StreamChatController object is cleanly closed here

/**
 * Updates connection status and initiates chat if accepted
 * Placed OUTSIDE the object so it can be called globally by HTML buttons
 */
async function updateConnection(connectionId, action, targetUserId, targetUsername) {
    try {
        console.log("DEBUG: Updating connection...");
        const response = await fetch('/matchmaking/action/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.CSRF_TOKEN 
            },
            body: JSON.stringify({ id: connectionId, action: action })
        });

        const data = await response.json(); // Capture server response
        console.log("DEBUG: Server response:", data);

        if (response.ok && action === 'ACCEPTED') {
            await StreamChatController.createDealRoom(targetUserId, targetUsername);
        } else {
            alert("Error: " + (data.error || "Action failed."));
            location.reload();
        }
    } catch (err) {
        console.error("Connection update failed:", err);
        alert("Network Error: Could not connect to server.");
    }
}

