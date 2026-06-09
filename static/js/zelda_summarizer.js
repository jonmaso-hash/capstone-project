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
    
    // Render the structured 3-bullet breakdown
    display.innerHTML = `
        <ul class="list-unstyled mb-0">
            <li class="mb-2"><strong>Traction:</strong> ${data.traction}</li>
            <li class="mb-2"><strong>Tech:</strong> ${data.tech}</li>
            <li><strong>Ask:</strong> ${data.ask}</li>
        </ul>
    `;
}