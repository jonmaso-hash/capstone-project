/**
 * Custom analytics events — only the ones GA4 Enhanced Measurement cannot infer.
 *
 * Enhanced Measurement already reports outbound clicks, scroll depth, file
 * downloads, video engagement and form interactions, so nothing here duplicates
 * those. This covers the marketplace-specific moments: discovery views and the
 * clicks that lead into the funnel.
 *
 * Loaded only on pages where the tag itself was rendered, which means consent
 * has already been given.
 *
 * The boundary, enforced below rather than trusted: an event carries its name
 * and nothing else. No company names, usernames, document titles, deal values
 * or report contents ever reach Google. What people do inside the marketplace
 * is the database's business.
 */
(function () {
    'use strict';

    function send(name) {
        if (typeof window.gtag !== 'function') return;
        if (typeof name !== 'string' || !/^[a-z0-9_]{1,40}$/.test(name)) return;
        // Deliberately no parameters: the name is the whole payload.
        window.gtag('event', name);
    }

    window.ifAnalytics = { event: send };

    document.addEventListener('DOMContentLoaded', function () {
        var marker = document.querySelector('[data-ga-page]');
        if (marker) send(marker.dataset.gaPage);

        document.addEventListener('click', function (event) {
            var target = event.target.closest('[data-ga-event]');
            if (target) send(target.dataset.gaEvent);
        });
    });
})();
