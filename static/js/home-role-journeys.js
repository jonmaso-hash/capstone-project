(() => {
    const root = document.getElementById('home-role-journeys');
    if (!root) return;
    const buttons = [...root.querySelectorAll('[data-journey-role]')];
    const panels = [...root.querySelectorAll('[data-journey-panel]')];
    if (!buttons.length) return;
    function selectRole(role, expand) {
        buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.journeyRole === role)));
        panels.forEach(panel => {
            const selected = panel.dataset.journeyPanel === role;
            panel.hidden = !selected;
            panel.querySelector('.role-journey-details').open = selected && expand;
            const fundingInfo = panel.querySelector('.role-funding-info');
            if (fundingInfo) fundingInfo.open = false;
        });
    }
    selectRole(buttons[0].dataset.journeyRole, false);
    buttons.forEach(button => button.addEventListener('click', () => selectRole(button.dataset.journeyRole, true)));
})();
