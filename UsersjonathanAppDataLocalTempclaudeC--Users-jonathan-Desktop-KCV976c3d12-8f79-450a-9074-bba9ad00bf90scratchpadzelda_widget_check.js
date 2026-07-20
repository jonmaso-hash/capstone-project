
    const ZELDA_API = '/api/v1/zelda';

    // ──────────────────────────────────────────────────────────────────────────
    // UTILITY FUNCTIONS
    // ──────────────────────────────────────────────────────────────────────────

    function getCookie(name) {
        const cookies = document.cookie.split(';');
        for (let c of cookies) {
            c = c.trim();
            if (c.startsWith(name + '=')) return decodeURIComponent(c.slice(name.length + 1));
        }
        return null;
    }

    function addLogEntry(message, type = 'info') {
        const log = document.getElementById('agent-response-log');
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        const timestamp = new Date().toLocaleTimeString();
        entry.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    // ──────────────────────────────────────────────────────────────────────────
    // TAB NAVIGATION
    // ──────────────────────────────────────────────────────────────────────────

    document.querySelectorAll('.zelda-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(content => {
                content.style.display = 'none';
            });
            
            // Deactivate all tabs
            document.querySelectorAll('.zelda-tab').forEach(t => {
                t.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(`tab-${tabName}`).style.display = 'flex';
            this.classList.add('active');

            if (tabName === 'notifications') {
                loadNotifications();
            }
        });
    });

    // ──────────────────────────────────────────────────────────────────────────
    // NOTIFICATIONS — the red badge on the Zelda icon reflects unread
    // Notification rows (intro requests, matches, etc). Viewing this tab is
    // what actually tells the user what they were notified about; the list
    // endpoint marks everything read as a side effect of fetching it
    // (notifications/views.py::notification_list_api), so the badge clears
    // the moment they look, instead of persisting forever.
    // ──────────────────────────────────────────────────────────────────────────

    function updateUnreadBadge(count) {
        const iconBadge = document.getElementById('zelda-unread-badge');
        const tabBadge = document.getElementById('zelda-tab-notif-badge');
        const display = count > 0 ? (count > 9 ? '9+' : String(count)) : '';
        [iconBadge, tabBadge].forEach(el => {
            if (!el) return;
            el.textContent = display;
            el.style.display = count > 0 ? 'flex' : 'none';
        });
    }

    // Tells the user why the Zelda icon just changed color — a 1s-visible,
    // fading message anchored to the icon. Reuses a single DOM node across
    // calls rather than creating a new one each time, in case this ever
    // fires twice in quick succession.
    let zeldaStageToastTimer = null;
    function showStageChangeToast(color, message) {
        let toast = document.getElementById('zelda-stage-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'zelda-stage-toast';
            document.body.appendChild(toast);
        }

        clearTimeout(zeldaStageToastTimer);
        toast.classList.remove('zelda-stage-red', 'zelda-stage-yellow', 'zelda-stage-green', 'show');
        toast.textContent = message;
        toast.classList.add(`zelda-stage-${color}`);

        // Force a reflow so the browser registers the "no .show" state
        // before re-adding it — otherwise the opacity transition doesn't
        // replay on back-to-back calls.
        void toast.offsetWidth;
        toast.classList.add('show');

        zeldaStageToastTimer = setTimeout(() => {
            toast.classList.remove('show');
        }, 1000);
    }

    async function loadNotifications() {
        const loading = document.getElementById('notifications-loading');
        const empty = document.getElementById('notifications-empty');
        const list = document.getElementById('notifications-list');

        loading.style.display = 'block';
        empty.style.display = 'none';
        list.innerHTML = '';

        try {
            const response = await fetch('/notifications/api/list/', { credentials: 'same-origin' });
            const items = await response.json();

            loading.style.display = 'none';

            if (!items.length) {
                empty.style.display = 'block';
            } else {
                list.innerHTML = items.map(item => {
                    const body = `
                        <div class="d-flex align-items-start gap-2">
                            <i class="bi bi-info-circle-fill text-primary mt-1"></i>
                            <span class="small text-dark flex-grow-1">${item.message}</span>
                            <button type="button" class="btn-close ms-2 flex-shrink-0 zelda-notif-delete"
                                    data-id="${item.id}" aria-label="Delete notification"
                                    title="Delete notification" style="font-size:0.65rem;"></button>
                        </div>`;
                    return item.target_url
                        ? `<a href="${item.target_url}" class="zelda-card p-3 text-decoration-none" style="display:block;">${body}</a>`
                        : `<div class="zelda-card p-3">${body}</div>`;
                }).join('');
            }

            // The list endpoint already marked these rows read server-side —
            // reflect that immediately instead of waiting for the next
            // full-page loadJourneyStatus() call.
            updateUnreadBadge(0);
        } catch (err) {
            loading.style.display = 'none';
            addLogEntry(`Notifications load error: ${err.message}`, 'error');
        }
    }

    // Deletes a notification the user has already read but doesn't want to
    // keep seeing in the list. Card is scoped via .closest('.zelda-card')
    // since a card may render as either an <a> (has target_url) or a <div>.
    document.getElementById('notifications-list').addEventListener('click', async (e) => {
        const delBtn = e.target.closest('.zelda-notif-delete');
        if (!delBtn) return;
        e.preventDefault();
        e.stopPropagation();

        const cardEl = delBtn.closest('.zelda-card');
        delBtn.disabled = true;

        try {
            const response = await fetch(`/notifications/api/${delBtn.dataset.id}/delete/`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            if (cardEl) cardEl.remove();
            const list = document.getElementById('notifications-list');
            if (list && !list.children.length) {
                document.getElementById('notifications-empty').style.display = 'block';
            }
        } catch (err) {
            delBtn.disabled = false;
            addLogEntry(`Notification delete error: ${err.message}`, 'error');
        }
    });

    // ──────────────────────────────────────────────────────────────────────────
    // GLOBAL SEARCH
    // ──────────────────────────────────────────────────────────────────────────

    document.getElementById('global-agent-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = document.getElementById('globalAgentQuery').value.trim();
        if (!query) return;

        addLogEntry(`Searching for: "${query}"`, 'info');

        try {
            const response = await fetch(`${ZELDA_API}/search/`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ q: query })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            if (data.response) {
                addLogEntry(data.response, 'success');
            }

            renderSearchResults(data.results || []);

            if (data.results && data.results.length > 0) {
                addLogEntry(`Found ${data.results.length} results`, 'success');
            } else {
                addLogEntry('No results found', 'warning');
            }

        } catch (err) {
            addLogEntry(`Error: ${err.message}`, 'error');
        }

        document.getElementById('globalAgentQuery').value = '';
    });

    // ──────────────────────────────────────────────────────────────────────────
    // ASK ZELDA — natural-language founder search. Claude only extracts
    // filters server-side; the response text and results are always real
    // query results, so unlike globalAgentQuery's handler we read the JSON
    // body even on a non-2xx response (429 rate limit, 503 circuit open)
    // instead of throwing, so the server's actual message reaches the user.
    // ──────────────────────────────────────────────────────────────────────────

    document.getElementById('zelda-ask-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = document.getElementById('zeldaAskQuery').value.trim();
        if (!question) return;

        addLogEntry(`Asking Zelda: "${question}"`, 'info');

        try {
            const response = await fetch(`${ZELDA_API}/ask/`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ q: question })
            });

            const data = await response.json();

            if (data.status === 'error') {
                addLogEntry(data.message || `Error: HTTP ${response.status}`, 'error');
                renderSearchResults([]);
            } else {
                if (data.response) {
                    addLogEntry(data.response, 'success');
                }
                renderSearchResults(data.results || []);
            }

        } catch (err) {
            addLogEntry(`Error: ${err.message}`, 'error');
        }

        document.getElementById('zeldaAskQuery').value = '';
    });

    // ──────────────────────────────────────────────────────────────────────────
    // SEARCH RESULT CARDS — founders get a one-click "Analyze with Zelda" button
    // instead of forcing a trip to their profile page first.
    // ──────────────────────────────────────────────────────────────────────────

    function renderSearchResults(results) {
        const card = document.getElementById('search-results-card');
        const list = document.getElementById('search-results-list');

        if (!results.length) {
            card.style.display = 'none';
            list.innerHTML = '';
            return;
        }

        list.innerHTML = results.slice(0, 8).map((result, i) => {
            const title = result.title || result.company_name || 'Result';
            const desc = result.executive_summary || result.description || '';
            const statusId = `search-result-status-${i}`;

            let analyzeBtn = '';
            if (result.type === 'Founder Profile' && result.username) {
                if (result.has_pitch_deck) {
                    analyzeBtn = `
                        <button class="zelda-button" style="padding: 0.4rem 0.9rem; font-size: 0.8rem;"
                                onclick="analyzeFounderWithZelda(this, '${result.username}', '${(result.startup_name || title).replace(/'/g, "\\'")}', {statusElementId: '${statusId}', preferredTab: 'intelligence'})">
                            <i class="bi bi-cpu me-1"></i>Analyze with Zelda
                        </button>`;
                } else {
                    analyzeBtn = `<span class="text-muted small"><i class="bi bi-file-earmark-x me-1"></i>No pitch deck uploaded yet</span>`;
                }
            }

            return `
                <div class="zelda-card p-3">
                    <div class="d-flex justify-content-between align-items-start gap-2">
                        <div>
                            <a href="${result.url}" class="fw-bold text-dark text-decoration-none small d-block mb-1">${title}</a>
                            <p class="text-muted small mb-0">${desc}</p>
                        </div>
                    </div>
                    ${analyzeBtn ? `<div class="mt-2">${analyzeBtn}</div>` : ''}
                    <div id="${statusId}" class="small text-muted mt-1"></div>
                </div>
            `;
        }).join('');

        card.style.display = 'block';
    }

    // ──────────────────────────────────────────────────────────────────────────
    // DOCUMENT UPLOAD
    // ──────────────────────────────────────────────────────────────────────────

    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('document-file');

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        fileInput.files = e.dataTransfer.files;
        updateFileInfo();
    });

    fileInput.addEventListener('change', updateFileInfo);

    function updateFileInfo() {
        const file = fileInput.files[0];
        if (file) {
            document.getElementById('file-info').style.display = 'block';
            document.getElementById('file-name').textContent = file.name;
            document.getElementById('file-size').textContent = formatBytes(file.size);
        }
    }

    document.getElementById('document-upload-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        const file = fileInput.files[0];
        const sourceEntity = document.getElementById('source-entity').value.trim();
        const documentType = document.getElementById('document-type').value;

        if (!file || !sourceEntity || !documentType) {
            addLogEntry('Please fill all fields and select a file', 'error');
            return;
        }

        // Show upload status
        document.getElementById('upload-status-card').style.display = 'block';
        document.getElementById('upload-progress-bar').style.width = '0%';
        document.getElementById('status-text').textContent = 'Uploading file...';

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('source_entity', sourceEntity);
            formData.append('document_type', documentType);

            const response = await fetch(`${ZELDA_API}/documents/ingest/`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: formData
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            document.getElementById('upload-progress-bar').style.width = '100%';
            document.getElementById('status-text').textContent = 'Upload complete! Processing...';
            document.getElementById('upload-message').innerHTML = `
                <strong>Document Ingested!</strong><br>
                ID: <strong>${data.document_id}</strong><br>
                <a href="javascript:loadMemoById(${data.document_id})" style="color: var(--zelda-accent); text-decoration: none;">View progress →</a>
            `;

            addLogEntry(`Document uploaded: ${file.name} (ID: ${data.document_id})`, 'success');

            // Reset form
            setTimeout(() => {
                document.getElementById('document-upload-form').reset();
                document.getElementById('file-info').style.display = 'none';
            }, 2000);

        } catch (err) {
            addLogEntry(`Upload error: ${err.message}`, 'error');
            document.getElementById('upload-message').innerHTML = `<span style="color: var(--zelda-danger);">Error: ${err.message}</span>`;
        }
    });

    // ──────────────────────────────────────────────────────────────────────────
    // VECTOR SEARCH
    // ──────────────────────────────────────────────────────────────────────────

    document.getElementById('vector-search-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const docId = document.getElementById('searchDocId').value;
        const query = document.getElementById('vectorQuery').value.trim();

        if (!docId || !query) {
            addLogEntry('Please enter document ID and search query', 'error');
            return;
        }

        addLogEntry(`Vector searching document ${docId}: "${query}"`, 'info');

        try {
            const response = await fetch(`${ZELDA_API}/documents/${docId}/search/`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ query: query })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            addLogEntry(`Found ${data.results_count} relevant chunks`, 'success');
            data.results.slice(0, 3).forEach((result, i) => {
                const text = result.text.substring(0, 80) + '...';
                addLogEntry(`${i+1}. [${result.section}] ${text}`, 'info');
            });

        } catch (err) {
            addLogEntry(`Search error: ${err.message}`, 'error');
        }

        document.getElementById('vectorQuery').value = '';
    });

    // ──────────────────────────────────────────────────────────────────────────
    // CONFIDENCE GAUGE — shared by memo, intelligence brief, and the standalone
    // valuation report page. Scores from the API are 0.0-1.0; this renders them
    // as a filled bar, an "N/10" label, and a one-line explanation.
    // ──────────────────────────────────────────────────────────────────────────

    function renderConfidenceGauge(containerEl, score0to1, label) {
        if (!containerEl) return;
        const pct = Math.max(0, Math.min(100, Math.round((score0to1 || 0) * 100)));
        const tenScale = (Math.round(pct / 10 * 10) / 10).toFixed(1).replace(/\.0$/, '');

        let color, explanation;
        if (pct >= 70) {
            color = '#198754';
            explanation = 'Strong evidence base — most claims are well-supported by the source documents.';
        } else if (pct >= 40) {
            color = '#ffc107';
            explanation = 'Partial evidence base — some claims are inferred or missing supporting detail.';
        } else {
            color = '#dc3545';
            explanation = 'Limited evidence base — treat this output as a starting point, not a final answer.';
        }

        containerEl.innerHTML = `
            <div class="d-flex justify-content-between align-items-baseline mb-1">
                <span class="small fw-bold text-dark">${label || 'Confidence'}</span>
                <span class="fw-bold small" style="color: ${color};">${tenScale}/10</span>
            </div>
            <div style="height: 8px; background: #e9ecef; border-radius: 999px; overflow: hidden;">
                <div class="zelda-gauge-fill" style="height: 100%; width: 0%; background: ${color}; border-radius: 999px; transition: width 0.6s ease;"></div>
            </div>
            <p class="text-muted mb-0 mt-1" style="font-size: 0.75rem;">${explanation}</p>
        `;

        // setTimeout (not requestAnimationFrame) so the fill still animates in
        // backgrounded/unfocused tabs, where rAF callbacks can be paused indefinitely.
        setTimeout(() => {
            const fill = containerEl.querySelector('.zelda-gauge-fill');
            if (fill) fill.style.width = pct + '%';
        }, 20);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // MEMO VIEWER
    // ──────────────────────────────────────────────────────────────────────────

    // Shared locked-state card for the Memo tab and Intelligence brief —
    // the Intelligence Memo itself is Premium (founder/seller-controlled
    // asset, same model as the IC Memo and Truth Delta): free for any
    // investor to view once the founder unlocks it.
    function renderLockedMemoCard(documentName, isOwner) {
        const message = isOwner
            ? `Generate an AI Intelligence Memo &mdash; executive summary, strengths, weaknesses, and improvement
               recommendations &mdash; from your uploaded materials.`
            : `${documentName || 'This founder'} hasn't unlocked their Intelligence Memo yet. Once they upgrade to
               Premium, you'll be able to view it here &mdash; no extra cost to you.`;
        const cta = isOwner
            ? `<a href="/billing/" class="btn btn-sm btn-warning rounded-pill px-3 fw-semibold">View Membership Plans</a>`
            : '';
        return `
            <div class="card border-0 shadow-sm rounded-4 p-3" style="background: linear-gradient(135deg, #fff8e1, #ffffff);">
                <h6 class="fw-bold mb-2"><i class="bi bi-lock-fill me-1" style="color: var(--zelda-accent);"></i>
                    ${isOwner ? 'Unlock Your Intelligence Memo' : 'Premium Feature'}
                </h6>
                <p class="text-muted small mb-3">${message}</p>
                ${cta}
            </div>
        `;
    }

    function loadMemoById(docId) {
        document.getElementById('memo-doc-id').value = docId;
        loadMemo();
    }

    async function loadMemo() {
        const docId = document.getElementById('memo-doc-id').value;
        if (!docId) {
            addLogEntry('Please enter a document ID', 'error');
            return;
        }

        addLogEntry(`Loading memo for document ${docId}...`, 'info');

        try {
            const response = await fetch(`${ZELDA_API}/documents/${docId}/memo/`, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                }
            });

            if (!response.ok) {
                if (response.status === 202) {
                    addLogEntry('Memo still being generated. Please wait...', 'warning');
                    return;
                }
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            document.getElementById('memo-display').style.display = 'flex';

            console.log('[Zelda] Memo data received:', JSON.stringify(data, null, 2));

            if (data.locked) {
                document.getElementById('memo-content').innerHTML = renderLockedMemoCard(data.document_name, data.is_owner);
                addLogEntry(`Memo is Premium-locked for document ${docId}`, 'info');
                return;
            }

        let memoHTML = `
    <div class="mb-4">
        <h5 class="fw-bold text-dark mb-3">${data.document_name || 'Untitled'}</h5>
        <div style="display: flex; gap: 1rem; margin-bottom: 1rem;">
            <div>
                <div class="small text-muted">Recommendation</div>
                <strong style="color: var(--zelda-accent);">${(data.recommendation || 'pending').replace('_', ' ').toUpperCase()}</strong>
            </div>
            <div>
                <div class="small text-muted">Citations</div>
                <strong>${data.citations_count ?? '—'}</strong>
            </div>
        </div>
        <div id="memo-confidence-gauge" class="mb-3"></div>
    </div>
`;
            // Sections
            const sections = [
                { key: 'executive_summary', label: 'Executive Summary' },
                { key: 'problem_solution', label: 'Problem & Solution' },
                { key: 'market_analysis', label: 'Market Analysis' },
                { key: 'team_assessment', label: 'Team Assessment' },
                { key: 'financial_analysis', label: 'Financial Analysis' },
                { key: 'risk_assessment', label: 'Risk Assessment' },
                { key: 'investment_thesis', label: 'Investment Thesis' },
                { key: 'investment_readiness', label: 'Investment Readiness' },
                { key: 'questions_for_management', label: 'Questions for Management' },
            ];

            sections.forEach(section => {
                if (data.sections[section.key]) {
                    memoHTML += `
                        <div class="mb-3">
                            <h6 class="fw-bold text-dark">${section.label}</h6>
                            <p class="text-secondary small" style="white-space: pre-line;">${data.sections[section.key]}</p>
                        </div>
                    `;
                }
            });

            // Insights
            if (data.insights_cited && data.insights_cited.length > 0) {
                memoHTML += '<h6 class="fw-bold text-dark mt-4 mb-3">Key Insights</h6>';
                data.insights_cited.forEach(insight => {
                    memoHTML += `
                        <div class="small mb-2 p-2 bg-light rounded">
                            <strong>${insight.category}</strong>: ${insight.text}
                            <br><span class="text-muted" style="font-size: 0.75rem;">Confidence: ${Math.round(insight.confidence)}%</span>
                        </div>
                    `;
                });
            }

            document.getElementById('memo-content').innerHTML = memoHTML;
            renderConfidenceGauge(document.getElementById('memo-confidence-gauge'), data.completeness_score, 'Memo Completeness');
            addLogEntry(`Memo loaded successfully for document ${docId}`, 'success');

        } catch (err) {
            addLogEntry(`Memo load error: ${err.message}`, 'error');
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // JOURNEY STATUS — colors the Zelda icon by onboarding/engagement stage,
    // shows an unread-notification badge, and fills the "My Progress" tab.
    // ──────────────────────────────────────────────────────────────────────────

    async function loadJourneyStatus() {
        try {
            const response = await fetch(`${ZELDA_API}/journey-status/`, {
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            });
            if (!response.ok) return;
            const data = await response.json();

            const toggleBtn = document.getElementById('ai-agent-toggle');
            if (toggleBtn) {
                toggleBtn.classList.remove('zelda-stage-red', 'zelda-stage-yellow', 'zelda-stage-green');
                toggleBtn.classList.add(`zelda-stage-${data.stage_color}`);
            }

            // Explain *why* the icon just changed color — headline is the
            // same "what this stage means" text already shown in the My
            // Progress tab, so there's one source of truth for the copy.
            // Only fires on an actual color change (tracked in
            // localStorage, not per-page-load) so it doesn't nag on every
            // navigation once the user has already seen it for this stage.
            const lastSeenColor = localStorage.getItem('zeldaLastSeenStageColor');
            if (data.stage_color !== lastSeenColor) {
                showStageChangeToast(data.stage_color, data.headline);
                localStorage.setItem('zeldaLastSeenStageColor', data.stage_color);
            }

            // AI-analyses soft cap (zelda_api/quotas.py::usage_nearing_limit)
            // — a warning, not a block, so it only nags once per day rather
            // than on every page load once the user has seen it today.
            if (data.ai_usage_warning) {
                const today = new Date().toISOString().slice(0, 10);
                if (localStorage.getItem('zeldaLastSeenUsageWarningDate') !== today) {
                    showStageChangeToast('yellow', data.ai_usage_warning);
                    localStorage.setItem('zeldaLastSeenUsageWarningDate', today);
                }
            }

            updateUnreadBadge(data.unread_notifications);

            document.getElementById('progress-loading').style.display = 'none';
            const content = document.getElementById('progress-content');
            document.getElementById('progress-headline').textContent = data.headline;

            const checklist = document.getElementById('progress-checklist');
            checklist.innerHTML = data.checklist.map(item => `
                <div class="d-flex align-items-center gap-2 small">
                    <i class="bi ${item.done ? 'bi-check-circle-fill text-success' : 'bi-circle text-muted'}"></i>
                    <span class="${item.done ? 'text-muted text-decoration-line-through' : 'text-dark'}">${item.label}</span>
                </div>
            `).join('');

            // Profile Strength — a labeled bar, never a raw percentage (see
            // matchmaking/journey_actions.py::compute_profile_strength). The
            // ratio only drives the bar's fill width.
            const strengthColors = { 'Strong': '#198754', 'Good': '#ffc107', 'Building': '#fd7e14', 'Just Started': '#dc3545' };
            const strength = data.profile_strength || { ratio: 0, label: 'Just Started' };
            const strengthColor = strengthColors[strength.label] || 'var(--zelda-accent)';
            const strengthLabelEl = document.getElementById('progress-strength-label');
            strengthLabelEl.textContent = strength.label;
            strengthLabelEl.style.color = strengthColor;
            const strengthFill = document.getElementById('progress-strength-fill');
            strengthFill.style.background = strengthColor;
            setTimeout(() => { strengthFill.style.width = Math.round(strength.ratio * 100) + '%'; }, 20);

            // "Next best improvement" card — Zelda's own recommendation for
            // the first unfinished checklist item, with an honest reason
            // (never an invented match-quality percentage) and a direct
            // action button instead of a generic "Continue" link.
            const nextBestCard = document.getElementById('progress-next-best-action');
            if (data.next_best_action) {
                document.getElementById('progress-action-why').textContent = `Zelda recommendation: ${data.next_best_action.why_it_matters}`;
                document.getElementById('progress-action-time').textContent = `~${data.next_best_action.estimated_minutes} min`;
                document.getElementById('progress-action-label').textContent = data.next_best_action.action_label;

                const nextAction = document.getElementById('progress-next-action');
                if (data.next_best_action.action_url) {
                    nextAction.href = data.next_best_action.action_url;
                    nextAction.style.display = 'inline-block';
                } else {
                    nextAction.style.display = 'none';
                }
                nextBestCard.style.display = 'block';
            } else {
                nextBestCard.style.display = 'none';
            }

            content.style.display = 'block';
        } catch (err) {
            // Non-fatal — the icon just keeps its default look if this fails.
            console.warn('[Zelda] journey status load failed:', err.message);
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // INITIALIZE SIDEBAR
    // ──────────────────────────────────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', () => {
        const toggleBtn = document.getElementById('ai-agent-toggle');
        const sidebarEl = document.getElementById('aiAgentSidebar');

        if (sidebarEl && window.bootstrap) {
            const offcanvasInstance = new bootstrap.Offcanvas(sidebarEl);
            if (toggleBtn) {
                toggleBtn.addEventListener('click', () => offcanvasInstance.show());
            }
        }

        true
        loadJourneyStatus();
        true

        addLogEntry('Zelda Intelligence initialized', 'success');
    });

// ── Zelda Fullscreen Toggle ──
    function toggleZeldaFullscreen() {
        const sidebar = document.getElementById('aiAgentSidebar');
        const btn = document.getElementById('zelda-expand-btn');
        const icon = btn.querySelector('i');

        if (sidebar.classList.contains('zelda-fullscreen')) {
            sidebar.classList.remove('zelda-fullscreen');
            icon.className = 'bi bi-fullscreen';
            icon.style.fontSize = '0.85rem';
            btn.title = 'Expand Zelda';
        } else {
            sidebar.classList.add('zelda-fullscreen');
            icon.className = 'bi bi-fullscreen-exit';
            icon.style.fontSize = '0.85rem';
            btn.title = 'Collapse Zelda';
        }
    }

    // Reset fullscreen when sidebar is closed
    document.getElementById('aiAgentSidebar')?.addEventListener('hide.bs.offcanvas', function() {
        this.classList.remove('zelda-fullscreen');
        const btn = document.getElementById('zelda-expand-btn');
        if (btn) {
            btn.querySelector('i').className = 'bi bi-fullscreen';
            btn.title = 'Expand Zelda';
        }
    });
// ── Open Zelda to a specific tab with founder context ──
    function openZeldaIntelligence(founderId, tab) {
        // Open the sidebar
        const sidebarEl = document.getElementById('aiAgentSidebar');
        if (sidebarEl && window.bootstrap) {
            const offcanvas = bootstrap.Offcanvas.getOrCreateInstance(sidebarEl);
            offcanvas.show();
        }

        // Switch to the requested tab
        const tabName = tab === 'truth-delta' ? 'truth-delta' : 'intelligence';
        document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
        document.querySelectorAll('.zelda-tab').forEach(t => t.classList.remove('active'));
        const targetTab = document.getElementById(`tab-${tabName}`);
        const targetBtn = document.querySelector(`[data-tab="${tabName}"]`);
        if (targetTab) targetTab.style.display = 'flex';
        if (targetBtn) targetBtn.classList.add('active');

        addLogEntry(`Loading ${tab} for founder ID ${founderId}...`, 'info');

        if (tab === 'intelligence') {
            loadIntelligenceBrief(founderId);
        } else if (tab === 'truth-delta') {
            loadTruthDelta(founderId);
        } else if (tab === 'analyze') {
            // Switch to memo tab and load
            document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
            document.querySelectorAll('.zelda-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-memo').style.display = 'flex';
            document.querySelector('[data-tab="memo"]').classList.add('active');
            document.getElementById('memo-doc-id').value = founderId;
            loadMemo();
        }
    }

    // ── Resolve a founder's DocumentSource and open Zelda to the right tab ──
    // Shared by profile.html (single button) and investor_dashboard.html
    // (per-match-card buttons) — takes the button element itself so it works
    // regardless of how many instances are on the page at once.
    //
    // Never generates on a bare click anymore: if no memo exists yet, the
    // backend returns 'confirm_required' with the cached match score,
    // plain-language reasons, and the analysis cost, and this shows the
    // confirm modal instead — see confirmGenerateZeldaAnalysis for the
    // actual generation step, which is charged to the investor's own
    // monthly AI analyses, never the founder's.
    let _zeldaPendingConfirm = null;

    async function analyzeFounderWithZelda(buttonElement, founderUsername, companyName, options = {}) {
        const statusEl = options.statusElementId ? document.getElementById(options.statusElementId) : null;
        const preferredTab = options.preferredTab || 'intelligence';
        const originalHTML = buttonElement.innerHTML;

        buttonElement.disabled = true;
        buttonElement.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Analyzing...';
        if (statusEl) statusEl.textContent = 'Connecting to Zelda...';

        try {
            const response = await fetch(`/api/v1/zelda/analyze/founder/${founderUsername}/`, {
                credentials: 'include',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });

            const data = await response.json();

            if (data.status === 'ready') {
                if (statusEl) statusEl.textContent = `✓ Loading ${companyName} brief...`;
                openZeldaIntelligence(data.document_id, preferredTab);
            } else if (data.status === 'confirm_required') {
                if (statusEl) statusEl.textContent = '';
                showZeldaConfirmGenerateModal(founderUsername, companyName, preferredTab, statusEl, data);
            } else if (data.status === 'no_deck') {
                if (statusEl) statusEl.textContent = '⚠ No pitch deck uploaded yet.';
            } else {
                if (statusEl) statusEl.textContent = `✗ ${data.message}`;
            }
        } catch (err) {
            if (statusEl) statusEl.textContent = `✗ Error: ${err.message}`;
        } finally {
            buttonElement.innerHTML = originalHTML;
            buttonElement.disabled = false;
        }
    }

    function showZeldaConfirmGenerateModal(founderUsername, companyName, preferredTab, statusEl, data) {
        _zeldaPendingConfirm = { founderUsername, companyName, preferredTab, statusEl };

        let matchHtml = `<p class="mb-1">Analyzing <strong>${companyName}</strong></p>`;
        if (data.score !== null && data.score !== undefined) {
            matchHtml += `<p class="mb-2"><span class="badge bg-warning text-dark fs-6">${data.score}% Match</span></p>`;
        }
        if (data.reasons && data.reasons.length) {
            matchHtml += '<ul class="list-unstyled mb-0 small text-muted">' +
                data.reasons.map(r => `<li><i class="bi bi-check2 me-1"></i>${r}</li>`).join('') +
                '</ul>';
        }
        document.getElementById('zelda-confirm-match').innerHTML = matchHtml;

        const cost = data.analysis_cost || 1;
        document.getElementById('zelda-confirm-cost-line').textContent =
            `Uses ${cost} of your monthly AI analyses.`;

        document.getElementById('zelda-confirm-error').classList.add('d-none');
        const generateBtn = document.getElementById('zelda-confirm-generate-btn');
        generateBtn.disabled = false;
        generateBtn.innerHTML = 'Generate Report';

        bootstrap.Modal.getOrCreateInstance(document.getElementById('zeldaConfirmGenerateModal')).show();
    }

    async function confirmGenerateZeldaAnalysis() {
        if (!_zeldaPendingConfirm) return;
        const { founderUsername, companyName, preferredTab, statusEl } = _zeldaPendingConfirm;
        const generateBtn = document.getElementById('zelda-confirm-generate-btn');
        const errorEl = document.getElementById('zelda-confirm-error');

        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generating...';
        errorEl.classList.add('d-none');

        try {
            const response = await fetch(`/api/v1/zelda/analyze/founder/${founderUsername}/confirm/`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });
            const data = await response.json();

            if (data.status === 'ready' || data.status === 'processing') {
                bootstrap.Modal.getOrCreateInstance(document.getElementById('zeldaConfirmGenerateModal')).hide();
                if (statusEl) {
                    statusEl.textContent = data.status === 'ready'
                        ? `✓ Loading ${companyName} brief...`
                        : '⚙ Analysis queued — opening Zelda...';
                }
                openZeldaIntelligence(data.document_id, data.status === 'ready' ? preferredTab : 'analyze');
            } else {
                errorEl.textContent = data.message || 'Something went wrong.';
                errorEl.classList.remove('d-none');
                generateBtn.disabled = false;
                generateBtn.innerHTML = 'Generate Report';
            }
        } catch (err) {
            errorEl.textContent = `Error: ${err.message}`;
            errorEl.classList.remove('d-none');
            generateBtn.disabled = false;
            generateBtn.innerHTML = 'Generate Report';
        }
    }

    async function loadIntelligenceBrief(founderId) {
        const loading = document.getElementById('intelligence-loading');
        const empty = document.getElementById('intelligence-empty');
        const content = document.getElementById('intelligence-content');

        loading.style.display = 'block';
        empty.style.display = 'none';
        content.style.display = 'none';

        try {
            const response = await fetch(`${ZELDA_API}/documents/${founderId}/memo/`, {
                credentials: 'include',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            if (data.locked) {
                content.innerHTML = renderLockedMemoCard(data.document_name, data.is_owner);
                content.style.display = 'block';
                return;
            }

            let html = `<div class="mb-3">
                <span class="badge bg-primary-subtle text-primary px-3 py-2 rounded-pill mb-3">
                    ${data.document_name || 'Intelligence Brief'}
                </span>
                <div id="brief-confidence-gauge" class="mt-2 mb-1"></div>`;

            if (data.sections) {
                const sections = [
                    { key: 'executive_summary', label: 'Executive Summary' },
                    { key: 'problem_solution', label: 'Problem & Solution' },
                    { key: 'market_analysis', label: 'Market Opportunity' },
                    { key: 'team_assessment', label: 'Team Assessment' },
                    { key: 'financial_analysis', label: 'Financial Overview' },
                    { key: 'risk_assessment', label: 'Risk Factors' },
                    { key: 'investment_thesis', label: 'Investment Thesis' },
                    { key: 'investment_readiness', label: 'Investment Readiness' },
                    { key: 'questions_for_management', label: 'Questions for Management' },
                ];
                sections.forEach(s => {
                    if (data.sections[s.key]) {
                        html += `<div class="mb-3 p-3 bg-light rounded-3">
                            <h6 class="fw-bold text-dark mb-1" style="font-size:0.82rem;">${s.label}</h6>
                            <p class="text-secondary small mb-0" style="line-height:1.6; white-space: pre-line;">${data.sections[s.key]}</p>
                        </div>`;
                    }
                });
            }

            html += '</div>';
            content.innerHTML = html;
            renderConfidenceGauge(document.getElementById('brief-confidence-gauge'), data.completeness_score, 'Analysis Completeness');
            content.style.display = 'block';
            addLogEntry(`Intelligence brief loaded for document ${founderId}`, 'success');

        } catch (err) {
            content.innerHTML = `<div class="text-danger small p-3">
                <i class="bi bi-exclamation-triangle me-2"></i>
                Could not load brief: ${err.message}
            </div>`;
            content.style.display = 'block';
            addLogEntry(`Intelligence brief error: ${err.message}`, 'error');
        } finally {
            loading.style.display = 'none';
        }
    }

    async function loadTruthDelta(founderId) {
        const loading = document.getElementById('truth-delta-loading');
        const empty = document.getElementById('truth-delta-empty');
        const content = document.getElementById('truth-delta-content');

        loading.style.display = 'block';
        empty.style.display = 'none';
        content.style.display = 'none';

        try {
            const response = await fetch(`${ZELDA_API}/documents/${founderId}/verification/`, {
                credentials: 'include',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const html = await response.text();

            // Extract just the truth delta container from the full page response
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const container = doc.getElementById('truthDeltaContainer');

            if (container) {
                content.innerHTML = container.outerHTML;
            } else {
                content.innerHTML = `<div class="text-center py-4 text-muted small">
                    <i class="bi bi-shield fs-2 d-block mb-2 opacity-25"></i>
                    No Truth Delta report found for this founder.
                    <br><small>Upload a pitch deck to generate verification.</small>
                </div>`;
            }

            content.style.display = 'block';
            addLogEntry(`Truth Delta loaded for document ${founderId}`, 'success');

        } catch (err) {
            content.innerHTML = `<div class="text-danger small p-3">
                <i class="bi bi-exclamation-triangle me-2"></i>
                Could not load Truth Delta: ${err.message}
            </div>`;
            content.style.display = 'block';
            addLogEntry(`Truth Delta error: ${err.message}`, 'error');
        } finally {
            loading.style.display = 'none';
        }
    }
