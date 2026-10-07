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

    let evidence = null;
    let selectedSubject = null;
    let pendingEvidence = 0;

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

    function sync() {
        panels.forEach(panel => {
            const selected = panel.querySelector('.zelda-selected-evidence');
            if (selected) {
                selected.textContent = evidence
                    ? `${evidence.company} · ${evidence.evidence}. This evidence is selected across your product tabs.`
                    : 'Upload a document or select a company. Nothing is purchased by searching or uploading.';
            }

            const checkout = panel.querySelector('.zelda-product-checkout');
            if (checkout) {
                const packValid = panel.dataset.product !== 'three_pack'
                    || panel.querySelectorAll('[name="pack-report"]:checked').length === 3;
                checkout.disabled = !evidence || !packValid || pendingEvidence > 0;
            }

            const redeem = panel.querySelector('.zelda-credit-redeem');
            if (redeem) redeem.disabled = !evidence || pendingEvidence > 0;

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

                            const subjectName = document.getElementById('zelda-subject-name');
                            const subjectHelp = document.getElementById('zelda-subject-help');
                            if (subjectName) subjectName.textContent = evidence.company;
                            if (subjectHelp) subjectHelp.textContent = 'External company selected. Upload authorized materials for deeper analysis.';

                            panels.forEach(p => {
                                const companyInput = p.querySelector('[name="company"]');
                                if (companyInput) companyInput.value = evidence.company;
                            });
                            statusBox.className = 'small text-success';
                            statusBox.textContent = `Company selected: ${evidence.company}. Zelda products will use this subject.`;
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
            uploadForm.addEventListener('submit', async event => {
                event.preventDefault();
                if (pendingEvidence) return;
                const form = event.currentTarget;
                const button = form.querySelector('button');
                button.disabled = true;
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
                    status(panel, `Document selected for ${evidence.company}. Choose payment or use a credit.`, 'success', 'upload');
                } catch (error) {
                    status(panel, error.message, 'error', 'upload');
                } finally {
                    pendingEvidence--;
                    button.disabled = false;
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
                                status(panel, `Company selected: ${evidence.company}. Upload company documents for better financial and claim analysis.`, 'success', 'search');
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
                if (!evidence || pendingEvidence) return;
                button.disabled = true;
                status(panel, 'Opening Stripe Checkout…');
                try {
                    const data = await post(config.dataset.checkoutUrl, {
                        product: panel.dataset.product,
                        document_id: evidence.document_id,
                        reports: Array.from(panel.querySelectorAll('[name="pack-report"]:checked')).map(input => input.value),
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
                if (!evidence || pendingEvidence) return;
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
