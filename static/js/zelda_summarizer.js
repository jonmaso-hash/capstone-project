async function runZeldaSummarizer() {
    const content = document.body.innerText.substring(0, 5000); // Scrape current page text
    const display = document.getElementById('zelda-content');
    display.innerHTML = '<div class="spinner-border spinner-border-sm text-primary"></div> Analyzing...';

    const response = await fetch('/api/v1/zelda/summarize/', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN 
        },
        body: JSON.stringify({ page_text: content })
    });

    const data = await response.json();
    
    // LLM output is untrusted text. Never interpret it as HTML.
    const list = document.createElement('ul');
    list.className = 'list-unstyled mb-0';

    [
        ['Traction:', data.traction, 'mb-2'],
        ['Tech:', data.tech, 'mb-2'],
        ['Ask:', data.ask, ''],
    ].forEach(([label, value, className]) => {
        const item = document.createElement('li');
        item.className = className;
        const strong = document.createElement('strong');
        strong.textContent = label;
        item.append(strong, document.createTextNode(' ' + (value || '')));
        list.appendChild(item);
    });

    display.replaceChildren(list);
}