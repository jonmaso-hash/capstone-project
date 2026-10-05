(function () {
    const section = document.querySelector('[data-section="entity-integrity"]');
    const status = document.getElementById('identityCheckStatus');
    const button = document.getElementById('identityCheckButton');
    if (!section || !status) return;

    let timer;
    let generation = 0;
    function stop(message) {
        clearTimeout(timer);
        generation += 1;
        if (button) button.disabled = false;
        status.textContent = message;
    }
    function terminal(data) {
        return data.status === 'complete' || data.status === 'failed';
    }
    function poll(url, attempt, current) {
        if (current !== generation) return;
        if (attempt >= 40) {
            stop('This check is taking longer than expected. Refresh this page for its latest status.');
            return;
        }
        timer = setTimeout(async function () {
            if (current !== generation) return;
            try {
                const response = await fetch(url, {credentials: 'same-origin'});
                if (!response.ok) {
                    stop('This check could not be loaded. Refresh this page to try again.');
                    return;
                }
                const data = await response.json();
                if (current !== generation) return;
                if (terminal(data)) { window.location.reload(); return; }
                if (data.status !== 'pending') {
                    stop('This check could not be loaded. Refresh this page to try again.');
                    return;
                }
                poll(url, attempt + 1, current);
            } catch (error) {
                if (current === generation) {
                    stop('The check status could not be retrieved. Refresh this page to try again.');
                }
            }
        }, 3000);
    }

    if (button) button.addEventListener('click', async function () {
        clearTimeout(timer);
        const current = ++generation;
        button.disabled = true;
        status.textContent = 'Checking public sources…';
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        try {
            const response = await fetch(button.dataset.url, {
                method: 'POST', credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': match ? decodeURIComponent(match[1]) : '',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            const data = await response.json();
            if (current !== generation) return;
            if (!response.ok) {
                stop(data.error || 'The check could not be started. Please try again.');
                return;
            }
            if (terminal(data)) { window.location.reload(); return; }
            if (data.status !== 'pending' || !data.status_url) {
                stop('The check could not be started. Please try again.');
                return;
            }
            poll(data.status_url, 0, current);
        } catch (error) {
            if (current === generation) stop('The check could not be started. Please try again.');
        }
    });

    // Owners have no request button; refreshes and reopened reports still poll.
    if (section.dataset.identityStatus === 'pending' && section.dataset.identityStatusUrl) {
        if (button) button.disabled = true;
        poll(section.dataset.identityStatusUrl, 0, generation);
    }
    window.addEventListener('pagehide', () => {
        clearTimeout(timer);
        generation += 1;
    });
})();
