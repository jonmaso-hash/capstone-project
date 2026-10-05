(function () {
    const config = document.getElementById('zelda-product-config');
    if (!config) return;
    const panels = Array.from(document.querySelectorAll('.zelda-product-panel'));
    let evidence = null;
    let selectedSubject = null;
    function csrf() { const match=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);return match?decodeURIComponent(match[1]):''; }
    function status(panel, text) { panel.querySelector('.zelda-product-status').textContent=text; }
    function sync() {
        panels.forEach(panel=>{
            panel.querySelector('.zelda-selected-evidence').textContent = evidence ?
                `${evidence.company} · ${evidence.evidence}. This evidence is selected across your product tabs.` :
                'Upload a document or select a company. Nothing is purchased by searching or uploading.';
            const packValid = panel.dataset.product !== 'three_pack' || panel.querySelectorAll('[name="pack-report"]:checked').length===3;
            panel.querySelector('.zelda-product-checkout').disabled = !evidence || !packValid;
        });
    }
    async function post(url, body, json=false) {
        const headers={'X-CSRFToken':csrf()};if(json)headers['Content-Type']='application/json';
        const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),60000);
        try {
            const response=await fetch(url,{method:'POST',credentials:'same-origin',headers,signal:controller.signal,body:json?JSON.stringify(body):body});
            let data;try { data=await response.json(); } catch(error) { throw new Error('The request could not finish. Please try again.'); }
            if(!response.ok)throw new Error(data.error||'The request could not finish. Please try again.');
            return data;
        } catch(error) {
            if(error.name==='AbortError')throw new Error('The request took too long. Please try again.');
            throw error;
        } finally { clearTimeout(timer); }
    }
    panels.forEach(panel=>{
        panel.querySelectorAll('[name="pack-report"]').forEach(input=>input.addEventListener('change',sync));
        panel.querySelector('.zelda-product-upload').addEventListener('submit',async event=>{
            event.preventDefault();const button=event.currentTarget.querySelector('button');button.disabled=true;
            status(panel,'Reading your document…');
            try { const body=new FormData(event.currentTarget);if(selectedSubject && body.get('company')===selectedSubject.name)body.set('subject_token',selectedSubject.token);evidence=await post(config.dataset.intakeUrl,body);sync();status(panel,'Document selected. Review the product and continue to Checkout when ready.'); }
            catch(error){status(panel,error.message);}finally{button.disabled=false;}
        });
        panel.querySelector('.zelda-product-search').addEventListener('submit',async event=>{
            event.preventDefault();const form=event.currentTarget,button=form.querySelector('button');button.disabled=true;
            const list=panel.querySelector('.zelda-company-results');list.replaceChildren();status(panel,'Searching public company records…');
            try {
                const data=await post(config.dataset.searchUrl,new FormData(form));
                status(panel,data.message||'Select a company to use its public registration snapshot, or upload a substantive document.');
                (data.results||[]).forEach(company=>{
                    const item=document.createElement('div'),name=document.createElement('p'),select=document.createElement('button');
                    item.className='p-3 bg-light rounded-3';name.className='small mb-2';name.textContent=`${company.name} · SEC CIK ${company.cik}`;
                    select.type='button';select.className='btn btn-outline-primary btn-sm';select.textContent='Use this company';
                    select.addEventListener('click',async()=>{
                        select.disabled=true;const body=new FormData();body.set('subject_token',company.token);
                        try { evidence=await post(config.dataset.intakeUrl,body);selectedSubject=company;sync();panels.forEach(p=>p.querySelector('[name="company"]').value=evidence.company);status(panel,'Company selected. Upload company documents to improve financial and claim analysis.'); }
                        catch(error){status(panel,error.message);select.disabled=false;}
                    });item.append(name,select);list.append(item);
                });
            }catch(error){status(panel,error.message);}finally{button.disabled=false;}
        });
        panel.querySelector('.zelda-product-checkout').addEventListener('click',async event=>{
            const button=event.currentTarget;if(!evidence)return;button.disabled=true;status(panel,'Opening Stripe Checkout…');
            try {
                const data=await post(config.dataset.checkoutUrl,{product:panel.dataset.product,document_id:evidence.document_id,
                    reports:Array.from(panel.querySelectorAll('[name="pack-report"]:checked')).map(input=>input.value)},true);
                window.location.assign(data.checkout_url||data.order_url);
            }catch(error){status(panel,error.message);sync();}
        });
    });
    sync();
})();
