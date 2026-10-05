(function () {
    const config = document.getElementById('zelda-product-config');
    if (!config) return;
    const panels = Array.from(document.querySelectorAll('.zelda-product-panel'));
    let evidence = null;
    let selectedSubject = null;
    let pendingEvidence = 0;
    function csrf() {
        const field=document.querySelector('.zelda-product-panel [name="csrfmiddlewaretoken"]');
        const match=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return field ? field.value : match ? decodeURIComponent(match[1]) : '';
    }
    function status(panel, text, kind='pending', scope='product') {
        const box=panel.querySelector(`.zelda-${scope}-status`);
        box.hidden=false;box.replaceChildren();
        box.className=`zelda-${scope}-status small p-2 rounded border fw-semibold ${kind==='error'?'text-danger border-danger':kind==='success'?'text-success border-success':'text-dark'}`;
        box.setAttribute('aria-busy',kind==='pending'?'true':'false');
        if(kind==='pending') {
            const spinner=document.createElement('span');spinner.className='spinner-border spinner-border-sm me-2';spinner.setAttribute('aria-hidden','true');box.append(spinner);
        }
        const copy=document.createElement('span');copy.textContent=text;box.append(copy);
    }
    function sync() {
        panels.forEach(panel=>{
            panel.querySelector('.zelda-selected-evidence').textContent = evidence ?
                `${evidence.company} · ${evidence.evidence}. This evidence is selected across your product tabs.` :
                'Upload a document or select a company. Nothing is purchased by searching or uploading.';
            const packValid = panel.dataset.product !== 'three_pack' || panel.querySelectorAll('[name="pack-report"]:checked').length===3;
            panel.querySelector('.zelda-product-checkout').disabled = !evidence || !packValid || pendingEvidence>0;
        });
    }
    async function post(url, body, json=false) {
        const headers={'X-CSRFToken':csrf(),'Accept':'application/json'};if(json)headers['Content-Type']='application/json';
        const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),60000);
        try {
            const response=await fetch(url,{method:'POST',credentials:'same-origin',headers,signal:controller.signal,body:json?JSON.stringify(body):body});
            if(response.redirected)throw new Error('Your session may have expired. Refresh this page and sign in again, then retry.');
            let data;try { data=await response.json(); } catch(error) {
                const message=response.status===403?'Your session could not be verified. Refresh this page and try again.':
                    response.status===413?'That file is too large. Use a PDF, PPTX or TXT up to 25 MB.':
                    response.status>=500?'The server could not finish this request. Please try again shortly. Nothing was purchased.':
                    'The server returned an unexpected response. Refresh this page and try again.';
                throw new Error(message);
            }
            if(!response.ok)throw new Error(data.error||'The request could not finish. Please try again.');
            return data;
        } catch(error) {
            if(error.name==='AbortError')throw new Error('The request took too long. Please try again.');
            if(error instanceof TypeError)throw new Error('The connection was interrupted. Check your connection and try again.');
            throw error;
        } finally { clearTimeout(timer); }
    }
    panels.forEach(panel=>{
        panel.querySelectorAll('[name="pack-report"]').forEach(input=>input.addEventListener('change',sync));
        panel.querySelector('.zelda-product-upload').addEventListener('submit',async event=>{
            event.preventDefault();if(pendingEvidence)return;
            const form=event.currentTarget,button=form.querySelector('button');button.disabled=true;
            evidence=null;pendingEvidence++;sync();status(panel,'Reading your document…','pending','upload');
            try {
                const body=new FormData(form);
                if(selectedSubject && body.get('company')===selectedSubject.name)body.set('subject_token',selectedSubject.token);
                evidence=await post(config.dataset.intakeUrl,body);
                status(panel,`Document selected for ${evidence.company}. You can continue to Stripe Checkout.`,'success','upload');
            } catch(error){status(panel,error.message,'error','upload');}
            finally{pendingEvidence--;button.disabled=false;sync();}
        });
        panel.querySelector('.zelda-product-search').addEventListener('submit',async event=>{
            event.preventDefault();const form=event.currentTarget,button=form.querySelector('button');button.disabled=true;
            const list=panel.querySelector('.zelda-company-results');list.replaceChildren();status(panel,'Searching company names and stock tickers…','pending','search');
            try {
                const data=await post(config.dataset.searchUrl,new FormData(form));
                status(panel,data.message||(data.results?.length?'Company results found. Select the company your document is about.':'No company results found. Try its legal name or upload a pitch deck.'),data.results?.length?'success':'error','search');
                (data.results||[]).forEach(company=>{
                    const item=document.createElement('div'),name=document.createElement('p'),select=document.createElement('button');
                    item.className='p-3 bg-light rounded-3';name.className='small mb-2';name.textContent=`${company.name}${company.ticker?' · '+company.ticker:''} · SEC CIK ${company.cik}`;
                    select.type='button';select.className='btn btn-outline-primary btn-sm';select.textContent='Use this company';
                    select.addEventListener('click',async()=>{
                        if(pendingEvidence)return;
                        select.disabled=true;evidence=null;pendingEvidence++;sync();status(panel,'Loading the company record…','pending','search');
                        const body=new FormData();body.set('subject_token',company.token);
                        try {
                            evidence=await post(config.dataset.intakeUrl,body);selectedSubject=company;
                            panels.forEach(p=>p.querySelector('[name="company"]').value=evidence.company);
                            status(panel,`Company selected: ${evidence.company}. Upload company documents for better financial and claim analysis.`,'success','search');
                        } catch(error){status(panel,error.message,'error','search');}
                        finally{pendingEvidence--;select.disabled=false;sync();}
                    });item.append(name,select);list.append(item);
                });
            } catch(error){status(panel,error.message,'error','search');}finally{button.disabled=false;}
        });
        panel.querySelector('.zelda-product-checkout').addEventListener('click',async event=>{
            const button=event.currentTarget;if(!evidence||pendingEvidence)return;button.disabled=true;status(panel,'Opening Stripe Checkout…');
            try {
                const data=await post(config.dataset.checkoutUrl,{product:panel.dataset.product,document_id:evidence.document_id,
                    reports:Array.from(panel.querySelectorAll('[name="pack-report"]:checked')).map(input=>input.value)},true);
                window.location.assign(data.checkout_url||data.order_url);
            } catch(error){status(panel,error.message,'error');sync();}
        });
    });
    sync();
})();
