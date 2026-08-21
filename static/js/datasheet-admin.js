(function(){
    function init(){
        const root=document.getElementById('datasheetAdmin');
        if(!root||root.dataset.initialized==='true')return;
        root.dataset.initialized='true';
        const jsonHeaders={'Content-Type':'application/json'};
        const toast=(message,error=false)=>{const el=document.createElement('div');el.className=`ds-toast${error?' error':''}`;el.textContent=message;document.body.appendChild(el);setTimeout(()=>el.remove(),4200)};
        const request=async(url,options={})=>{const response=await fetch(url,options);let data={};try{data=await response.json()}catch(e){data={message:'Resposta inválida do servidor.'}}if(!response.ok)throw new Error(data.message||`Erro HTTP ${response.status}`);return data};
        root.querySelectorAll('[data-ds-tab]').forEach(button=>button.addEventListener('click',()=>{root.querySelectorAll('[data-ds-tab]').forEach(item=>item.classList.toggle('active',item===button));root.querySelectorAll('[data-ds-panel]').forEach(panel=>panel.classList.toggle('active',panel.dataset.dsPanel===button.dataset.dsTab))}));
        const busy=async(button,callback)=>{const old=button.innerHTML;button.disabled=true;button.innerHTML='<i class="fas fa-spinner fa-spin"></i> Aguarde';try{return await callback()}finally{button.disabled=false;button.innerHTML=old}};
        root.querySelector('#dsSettingsForm')?.addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button[type=submit]');const data=Object.fromEntries(new FormData(form));form.querySelectorAll('input[type=checkbox]').forEach(input=>data[input.name]=input.checked);try{await busy(button,()=>request('/api/admin/datasheets/settings',{method:'PATCH',headers:jsonHeaders,body:JSON.stringify(data)}));toast('Controles globais salvos.');}catch(error){toast(error.message,true)}});
        root.querySelector('#dsQueueForm')?.addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button[type=submit]');try{const data=await busy(button,()=>request('/api/admin/datasheets/queue',{method:'POST',body:new FormData(form)}));toast(data.message||'Itens adicionados.');setTimeout(()=>location.reload(),500)}catch(error){toast(error.message,true)}});
        root.querySelectorAll('.ds-provider-form').forEach(form=>form.addEventListener('submit',async event=>{event.preventDefault();const card=form.closest('[data-provider-id]');const button=form.querySelector('button[type=submit]');const data=Object.fromEntries(new FormData(form));form.querySelectorAll('input[type=checkbox]').forEach(input=>data[input.name]=input.checked);try{await busy(button,()=>request(`/api/admin/datasheets/providers/${card.dataset.providerId}`,{method:'PATCH',headers:jsonHeaders,body:JSON.stringify(data)}));toast('Política da fonte atualizada.')}catch(error){toast(error.message,true)}}));
        root.querySelectorAll('[data-test-provider]').forEach(button=>button.addEventListener('click',async()=>{const card=button.closest('[data-provider-id]');const value=prompt('Part number para o teste isolado:','TPS51225');if(!value)return;try{const data=await busy(button,()=>request(`/api/admin/datasheets/providers/${card.dataset.providerId}/test`,{method:'POST',headers:jsonHeaders,body:JSON.stringify({part_number:value})}));toast(data.found?`Encontrado com ${Math.round(data.confidence*100)}% de confiança.`:'Nenhum candidato encontrado.')}catch(error){toast(error.message,true)}}));
        root.querySelectorAll('[data-kill-provider]').forEach(button=>button.addEventListener('click',async()=>{if(!confirm('Desativar esta fonte imediatamente?'))return;const card=button.closest('[data-provider-id]');try{const data=await busy(button,()=>request(`/api/admin/datasheets/providers/${card.dataset.providerId}/kill`,{method:'POST'}));toast(data.message);setTimeout(()=>location.reload(),500)}catch(error){toast(error.message,true)}}));
        root.querySelector('#dsProcessBatch')?.addEventListener('click',async event=>{const button=event.currentTarget;try{const data=await busy(button,()=>request('/api/admin/datasheets/queue/process',{method:'POST',headers:jsonHeaders,body:JSON.stringify({limit:10})}));toast(`${data.processed} item(ns) processado(s).`);setTimeout(()=>location.reload(),600)}catch(error){toast(error.message,true)}});
        root.querySelectorAll('[data-queue-action]').forEach(button=>button.addEventListener('click',async()=>{
            const item=button.closest('[data-item-id]');
            const action=button.dataset.queueAction;
            let url=`/api/admin/datasheets/queue/${item.dataset.itemId}/${action}`;
            let method='POST';
            let payload={};
            if(action==='process')url=`/api/admin/datasheets/queue/${item.dataset.itemId}/process`;
            if(action==='edit'){
                const current=item.querySelector('h3')?.childNodes[0]?.textContent.trim()||'';
                const partNumber=prompt('Part number normalizado:',current);
                if(partNumber===null)return;
                const manufacturer=prompt('Fabricante (opcional):','');
                if(manufacturer===null)return;
                const category=prompt('Categoria (opcional):','');
                if(category===null)return;
                const packageName=prompt('Package (opcional):','');
                if(packageName===null)return;
                url=`/api/admin/datasheets/queue/${item.dataset.itemId}`;
                method='PATCH';
                payload={part_number:partNumber,manufacturer,category,package:packageName};
            }
            if(action==='duplicate'){
                const componentId=prompt('ID do componente existente:','');
                if(!componentId)return;
                payload={component_id:componentId};
            }
            if(['publish','ignore'].includes(action)&&!confirm(`Confirmar ação: ${action}?`))return;
            try{
                await busy(button,()=>request(url,{method,headers:jsonHeaders,body:JSON.stringify(payload)}));
                toast('Item atualizado.');
                setTimeout(()=>location.reload(),500);
            }catch(error){toast(error.message,true)}
        }));
        root.querySelector('#dsBenchmarkForm')?.addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button');const values=new FormData(form).get('part_numbers');try{const data=await busy(button,()=>request('/api/admin/datasheets/benchmark',{method:'POST',headers:jsonHeaders,body:JSON.stringify({part_numbers:values})}));const rows=Object.entries(data.summary).map(([provider,value])=>`<tr><td>${provider}</td><td>${value.coverage}%</td><td>${value.exact_rate}%</td><td>${value.average_ms} ms</td><td>${value.hits}/${value.queries}</td></tr>`).join('');root.querySelector('#dsBenchmarkResult').innerHTML=`<div class="ds-benchmark-result"><table><thead><tr><th>Provider</th><th>Cobertura</th><th>Exatos</th><th>Tempo médio</th><th>Hits</th></tr></thead><tbody>${rows}</tbody></table></div>`}catch(error){toast(error.message,true)}});
    }
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
    document.addEventListener('adminPageLoaded',init);
})();
