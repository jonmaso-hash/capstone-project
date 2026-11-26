(function () {
    const config = document.getElementById('zelda-product-config');
    if (!config) return;

    const panels = Array.from(document.querySelectorAll('.zelda-product-panel'));

    document.querySelectorAll('[data-zelda-product], [data-zelda-tab]').forEach(shortcut => {
        shortcut.addEventListener('click', () => {
            const tabName = shortcut.dataset.zeldaProduct
                ? `product-${shortcut.dataset.zeldaProduct}`
                : shortcut.dataset.zeldaTab;
            const sidebar = document.getElementById('aiAgentSidebar');
            const tab = sidebar && Array.from(sidebar.querySelectorAll('.zelda-tab'))
                .find(button => button.dataset.tab === tabName);
            if (tab) tab.click();
        });
    });

    // The one accepted selection, shared by every product tab. Switching tabs
    // never changes it; only a new upload or company selection replaces it.
    let evidence = null;
    let selectedSubject = null;
    let pendingEvidence = 0;

    const uploadForms = panels.map(panel => panel.querySelector('.zelda-product-upload')).filter(Boolean);
    uploadForms.forEach(form => {
        const label = form.querySelector('label[for^="product-file-"]');
        const button = form.querySelector('button[type="submit"]');
        form.dataset.fileLabel = label ? label.textContent.trim() : '';
        form.dataset.submitLabel = button.textContent.trim();
    });

    // The panel's "Current subject" card. Every way of choosing evidence (the
    // card's own company search, a product tab's company search, or an upload)
    // ends in sync(), so the card is updated there and nowhere else. Before
    // this, only the card's own search updated it: after an upload the product
    // tab said the evidence was "selected across your product tabs" while the
    // card still said "No company selected".
    const subjectName = document.getElementById('zelda-subject-name');
    const subjectHelp = document.getElementById('zelda-subject-help');
    const defaultSubject = subjectName ? {
        name: subjectName.textContent.trim(),
        help: subjectHelp ? subjectHelp.textContent.trim() : '',
    } : null;

    function syncSubject() {
        if (!subjectName) return;
        if (evidence && evidence.company) {
            subjectName.textContent = evidence.company;
            if (subjectHelp) {
                subjectHelp.textContent = evidence.filename
                    ? 'Your uploaded document is selected for this company. Nothing is purchased until you pay or use a credit.'
                    : 'External company selected. Upload authorized materials for deeper analysis.';
            }
        } else if (!pendingEvidence) {
            subjectName.textContent = defaultSubject.name;
            if (subjectHelp) subjectHelp.textContent = defaultSubject.help;
        }
    }

    function csrf() {
        const field = document.querySelector('.zelda-product-panel [name="csrfmiddlewaretoken"]');
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return field ? field.value : match ? decodeURIComponent(match[1]) : '';
    }

    function status(panel, text, kind='pending', scope='product') {
        const box = panel.querySelector(`.zelda-${scope}-status`);
        if (!box) return;
        box.hidden = false;
        box.replaceChildren();
        box.className = `zelda-${scope}-status small p-2 rounded border fw-semibold ${
            kind === 'error' ? 'text-danger border-danger'
                : kind === 'success' ? 'text-success border-success'
                : 'text-dark'
        }`;
        box.setAttribute('aria-busy', kind === 'pending' ? 'true' : 'false');
        if (kind === 'pending') {
            const spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm me-2';
            spinner.setAttribute('aria-hidden', 'true');
            box.append(spinner);
        }
        const copy = document.createElement('span');
        copy.textContent = text;
        box.append(copy);
        box.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    }

    function sentencePunctuation(text) {
        return /[.!?]$/.test(text) ? '' : '.';
    }

    function selectedReports(panel) {
        return Array.from(panel.querySelectorAll('[name="pack-report"]:checked')).map(input => input.value);
    }

    function valuationBlockReason(panel, reports) {
        const product = panel.dataset.product;
        if (product === 'valuation' || product === 'complete_bundle'
            || (product === 'three_pack' && reports.includes('valuation'))) {
            return evidence?.valuation_block_reason || '';
        }
        return '';
    }

    function unsubmittedUpload(form) {
        if (!form) return null;
        const company = form.elements.company.value.trim();
        const file = form.elements.file.files[0];
        // File inputs are cleared once a document is accepted, so a chosen
        // file here is always one that has not been submitted yet.
        if (!company || !file) return null;
        return {form, company, file};
    }

    // The accepted document, shown on every product tab from the shared
    // selection. textContent only: the filename and company are user input.
    function syncSharedDocument(panel) {
        const box = panel.querySelector('.zelda-shared-document');
        if (!box) return;
        const name = box.querySelector('.zelda-shared-document-name');
        const company = box.querySelector('.zelda-shared-document-company');
        const replace = box.querySelector('.zelda-shared-document-replace');
        if (!evidence || !evidence.document_id) {
            box.hidden = true;
            box.dataset.documentId = '';
            name.textContent = company.textContent = replace.textContent = '';
            return;
        }
        box.hidden = false;
        box.dataset.documentId = String(evidence.document_id);
        name.textContent = evidence.filename
            ? `Selected document: ${evidence.filename} — used across intelligence tabs.`
            : `Selected evidence: ${evidence.evidence} — used across intelligence tabs.`;
        company.textContent = `Company: ${evidence.company}`;
        replace.textContent = evidence.filename
            ? 'To use a different file, choose it below and select Replace selected document. The new file replaces this one on every tab.'
            : 'To use a document instead, choose it below. It replaces this evidence on every tab.';
    }

    // While a document is selected, the upload form reads as a replacement.
    function syncUploadLabels(form) {
        const label = form.querySelector('label[for^="product-file-"]');
        const button = form.querySelector('button[type="submit"]');
        const replacing = Boolean(evidence && evidence.document_id);
        if (label) label.textContent = replacing ? 'Replace the selected document with another file' : form.dataset.fileLabel;
        button.textContent = replacing
            ? (evidence.filename ? 'Replace selected document' : 'Use this document instead')
            : form.dataset.submitLabel;
    }

    function sync() {
        syncSubject();
        panels.forEach(panel => {
            const uploadForm = panel.querySelector('.zelda-product-upload');
            const upload = unsubmittedUpload(uploadForm);
            if (uploadForm) {
                const button = uploadForm.querySelector('button[type="submit"]');
                const ready = Boolean(upload) && pendingEvidence === 0;
                button.disabled = !ready;
                button.classList.toggle('btn-primary', ready);
                button.classList.toggle('btn-outline-dark', !ready);
                syncUploadLabels(uploadForm);
            }

            syncSharedDocument(panel);

            const awaitingEvidence = !evidence || Boolean(upload) || pendingEvidence > 0;
            const checkout = panel.querySelector('.zelda-product-checkout');
            if (checkout) {
                const reports = selectedReports(panel);
                const packValid = panel.dataset.product !== 'three_pack' || reports.length === 3;
                const blockReason = valuationBlockReason(panel, reports);
                checkout.disabled = awaitingEvidence || !packValid || Boolean(blockReason);
                const evidenceStatus = panel.querySelector('.zelda-valuation-evidence-status');
                if (evidenceStatus) evidenceStatus.textContent = blockReason;
            }

            const redeem = panel.querySelector('.zelda-credit-redeem');
            if (redeem) redeem.disabled = awaitingEvidence;

            const creditPack = panel.querySelector('.zelda-credit-pack-checkout');
            if (creditPack) creditPack.disabled = pendingEvidence > 0;
        });
    }

    async function post(url, body, json=false) {
        const headers = {'X-CSRFToken': csrf(), 'Accept': 'application/json'};
        if (json) headers['Content-Type'] = 'application/json';
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 60000);
        try {
            const response = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers,
                signal: controller.signal,
                body: json ? JSON.stringify(body) : body,
            });
            if (response.redirected) {
                throw new Error('Your session may have expired. Refresh this page and sign in again, then retry.');
            }
            let data;
            try {
                data = await response.json();
            } catch (error) {
                const message = response.status === 403
                    ? 'Your session could not be verified. Refresh this page and try again.'
                    : response.status === 413
                        ? 'That file is too large. Use a PDF, PPTX or TXT up to 25 MB.'
                        : response.status >= 500
                            ? 'The server could not finish this request. Please try again shortly. Nothing was purchased.'
                            : 'The server returned an unexpected response. Refresh this page and try again.';
                throw new Error(message);
            }
            if (!response.ok) {
                throw new Error((data.error || 'The request could not finish. Please try again.')
                    + (data.reference ? ` Error reference: ${data.reference}` : ''));
            }
            return data;
        } catch (error) {
            if (error.name === 'AbortError') throw new Error('The request took too long. Please try again.');
            if (error instanceof TypeError) throw new Error('The connection was interrupted. Check your connection and try again.');
            throw error;
        } finally {
            clearTimeout(timer);
        }
    }

    const hubExternalForm = document.getElementById('zelda-hub-external-search');
    if (hubExternalForm) {
        hubExternalForm.addEventListener('submit', async event => {
            event.preventDefault();
            const form = event.currentTarget;
            const button = form.querySelector('button[type="submit"]');
            const statusBox = document.getElementById('zelda-hub-external-status');
            const results = document.getElementById('zelda-hub-external-results');
            button.disabled = true;
            results.replaceChildren();
            statusBox.hidden = false;
            statusBox.className = 'small text-muted';
            statusBox.textContent = 'Searching company names and stock tickers…';
            try {
                const data = await post(config.dataset.searchUrl, new FormData(form));
                const companies = data.results || [];
                statusBox.className = companies.length ? 'small text-success' : 'small text-muted';
                statusBox.textContent = data.message || (companies.length
                    ? 'Company results found. Select the company you want Zelda to use.'
                    : 'No company results found. Try its legal name or upload company materials.');

                companies.forEach(company => {
                    const item = document.createElement('div');
                    const title = document.createElement('div');
                    const select = document.createElement('button');
                    item.className = 'p-3 bg-light rounded-3 border';
                    title.className = 'small mb-2';
                    title.textContent = `${company.name}${company.ticker ? ' · ' + company.ticker : ''} · SEC CIK ${company.cik}`;
                    select.type = 'button';
                    select.className = 'btn btn-outline-primary btn-sm';
                    select.textContent = 'Use this company';
                    select.addEventListener('click', async () => {
                        if (pendingEvidence) return;
                        select.disabled = true;
                        evidence = null;
                        pendingEvidence++;
                        sync();
                        statusBox.className = 'small text-muted';
                        statusBox.textContent = 'Loading the company record…';
                        const body = new FormData();
                        body.set('subject_token', company.token);
                        try {
                            evidence = await post(config.dataset.intakeUrl, body);
                            selectedSubject = company;

                            panels.forEach(p => {
                                const companyInput = p.querySelector('[name="company"]');
                                if (companyInput) companyInput.value = evidence.company;
                            });
                            statusBox.className = 'small text-success';
                            select.textContent = 'Company selected';
                            statusBox.textContent = `Found: ${evidence.company}${sentencePunctuation(evidence.company)} Review the evidence and any upload requirements below.`;
                        } catch (error) {
                            statusBox.className = 'small text-danger';
                            statusBox.textContent = error.message;
                        } finally {
                            pendingEvidence--;
                            select.disabled = false;
                            sync();
                        }
                    });
                    item.append(title, select);
                    results.append(item);
                });
            } catch (error) {
                statusBox.className = 'small text-danger';
                statusBox.textContent = error.message;
            } finally {
                button.disabled = false;
            }
        });
    }

    panels.forEach(panel => {
        panel.querySelectorAll('[name="pack-report"]').forEach(input => input.addEventListener('change', sync));

        const uploadForm = panel.querySelector('.zelda-product-upload');
        if (uploadForm) {
            uploadForm.elements.company.addEventListener('input', sync);
            uploadForm.elements.file.addEventListener('change', sync);
            uploadForm.addEventListener('submit', async event => {
                event.preventDefault();
                const form = event.currentTarget;
                const upload = unsubmittedUpload(form);
                if (!upload || pendingEvidence) return;
                // A replacement that fails leaves the previous document selected.
                const previous = evidence;
                evidence = null;
                pendingEvidence++;
                sync();
                status(panel, 'Reading your document…', 'pending', 'upload');
                try {
                    const body = new FormData(form);
                    if (selectedSubject && body.get('company') === selectedSubject.name) {
                        body.set('subject_token', selectedSubject.token);
                    }
                    evidence = await post(config.dataset.intakeUrl, body);
                    // Every tab now uses this document. Clear the file inputs
                    // (never fill them) so no tab holds a stale, unsubmitted
                    // file, and carry the accepted company into each form.
                    uploadForms.forEach(other => {
                        other.elements.file.value = '';
                        other.elements.company.value = evidence.company;
                        const otherStatus = other.querySelector('.zelda-upload-status');
                        if (other !== form && otherStatus) otherStatus.hidden = true;
                    });
                    status(panel, `Document selected for ${evidence.company}${sentencePunctuation(evidence.company)} Choose payment or use a credit.`, 'success', 'upload');
                } catch (error) {
                    evidence = previous;
                    status(panel, error.message + (previous && previous.document_id
                        ? ' Your previously selected document is still selected.' : ''), 'error', 'upload');
                } finally {
                    pendingEvidence--;
                    sync();
                }
            });
        }

        const searchForm = panel.querySelector('.zelda-product-search');
        if (searchForm) {
            searchForm.addEventListener('submit', async event => {
                event.preventDefault();
                const form = event.currentTarget;
                const button = form.querySelector('button');
                button.disabled = true;
                const list = panel.querySelector('.zelda-company-results');
                list.replaceChildren();
                status(panel, 'Searching company names and stock tickers…', 'pending', 'search');
                try {
                    const data = await post(config.dataset.searchUrl, new FormData(form));
                    status(
                        panel,
                        data.message || (data.results?.length
                            ? 'Company results found. Select the company your document is about.'
                            : 'No company results found. Try its legal name or upload a pitch deck.'),
                        data.results?.length ? 'success' : 'error',
                        'search'
                    );
                    (data.results || []).forEach(company => {
                        const item = document.createElement('div');
                        const name = document.createElement('p');
                        const select = document.createElement('button');
                        item.className = 'p-3 bg-light rounded-3';
                        name.className = 'small mb-2';
                        name.textContent = `${company.name}${company.ticker ? ' · ' + company.ticker : ''} · SEC CIK ${company.cik}`;
                        select.type = 'button';
                        select.className = 'btn btn-outline-primary btn-sm';
                        select.textContent = 'Use this company';
                        select.addEventListener('click', async () => {
                            if (pendingEvidence) return;
                            select.disabled = true;
                            evidence = null;
                            pendingEvidence++;
                            sync();
                            status(panel, 'Loading the company record…', 'pending', 'search');
                            const body = new FormData();
                            body.set('subject_token', company.token);
                            try {
                                evidence = await post(config.dataset.intakeUrl, body);
                                selectedSubject = company;
                                panels.forEach(p => {
                                    const companyInput = p.querySelector('[name="company"]');
                                    if (companyInput) companyInput.value = evidence.company;
                                });
                                select.textContent = 'Company selected';
                                status(panel, `Found: ${evidence.company}${sentencePunctuation(evidence.company)} Review the evidence and any upload requirements below.`, 'success', 'search');
                            } catch (error) {
                                status(panel, error.message, 'error', 'search');
                            } finally {
                                pendingEvidence--;
                                select.disabled = false;
                                sync();
                            }
                        });
                        item.append(name, select);
                        list.append(item);
                    });
                } catch (error) {
                    status(panel, error.message, 'error', 'search');
                } finally {
                    button.disabled = false;
                }
            });
        }

        const checkout = panel.querySelector('.zelda-product-checkout');
        if (checkout) {
            checkout.addEventListener('click', async event => {
                const button = event.currentTarget;
                const reports = selectedReports(panel);
                if (button.disabled || !evidence || pendingEvidence || valuationBlockReason(panel, reports)) return;
                button.disabled = true;
                status(panel, 'Opening Stripe Checkout…');
                try {
                    const data = await post(config.dataset.checkoutUrl, {
                        product: panel.dataset.product,
                        document_id: evidence.document_id,
                        reports,
                    }, true);
                    window.location.assign(data.checkout_url || data.order_url);
                } catch (error) {
                    status(panel, error.message, 'error');
                    sync();
                }
            });
        }

        const creditPack = panel.querySelector('.zelda-credit-pack-checkout');
        if (creditPack) {
            creditPack.addEventListener('click', async event => {
                const button = event.currentTarget;
                button.disabled = true;
                status(panel, 'Opening Stripe Checkout…');
                try {
                    const data = await post(config.dataset.creditPackCheckoutUrl, {}, true);
                    if (data.checkout_url) {
                        window.location.assign(data.checkout_url);
                    } else {
                        status(panel, `Credits available: ${data.credit_balance || 0}`, 'success');
                        window.location.reload();
                    }
                } catch (error) {
                    status(panel, error.message, 'error');
                    button.disabled = false;
                }
            });
        }

        const redeem = panel.querySelector('.zelda-credit-redeem');
        if (redeem) {
            redeem.addEventListener('click', async event => {
                const button = event.currentTarget;
                if (button.disabled || !evidence || pendingEvidence) return;
                button.disabled = true;
                status(panel, 'Applying one Truth Delta credit…');
                try {
                    const data = await post(config.dataset.creditRedeemUrl, {
                        document_id: evidence.document_id,
                    }, true);
                    window.location.assign(data.order_url);
                } catch (error) {
                    status(panel, error.message, 'error');
                    sync();
                }
            });
        }
    });

    sync();
})();
