/* HOTFIX VISUAL - Abertura de SAC Premium
   Move campos existentes sem alterar name/id/value/eventos. */
(function(){
  function norm(t){return String(t||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toLowerCase();}
  function byLabel(txt){const alvo=norm(txt);let best=null;document.querySelectorAll('.field').forEach(f=>{const l=f.querySelector('label');if(!l)return;const n=norm(l.textContent);if(n===alvo || n.includes(alvo) || alvo.includes(n)){if(!best)best=f;}});return best;}
  function byAnyLabel(list){for(const x of list){const f=byLabel(x);if(f)return f;}return null;}
  function cardByTitle(txt){const alvo=norm(txt);let found=null;document.querySelectorAll('.card').forEach(c=>{const h=c.querySelector('h2');if(h && norm(h.textContent).includes(alvo) && !found)found=c;});return found;}
  function panel(title, subtitle){const p=document.createElement('section');p.className='sac-premium-panel';const c=document.createElement('div');c.className='sac-premium-card';const h=document.createElement('h2');h.textContent=title;c.appendChild(h);if(subtitle){const s=document.createElement('div');s.className='sac-premium-note';s.textContent=subtitle;c.appendChild(s);}p.appendChild(c);return [p,c];}
  function move(field,parent,cls){if(field&&parent){if(cls)field.classList.add(cls);parent.appendChild(field);}}
  function wrapGrid(parent,cls){const g=document.createElement('div');g.className=cls||'sac-premium-grid';parent.appendChild(g);return g;}
  function setupTabs(){
    const form=document.getElementById('formSac'); const layout=document.querySelector('.layout'); if(!form||!layout||document.querySelector('.sac-premium-tabs'))return;
    layout.classList.add('sac-premium-hidden-old');
    const tabs=document.createElement('div');tabs.className='sac-premium-tabs';
    const bar=document.createElement('div');bar.className='sac-premium-tabbar';tabs.appendChild(bar);
    const names=['Dados Cliente / Nota Fiscal','Dados do contato','Inclusão de item com problema','Outros Dados'];
    const panels={};
    names.forEach((n,i)=>{const b=document.createElement('button');b.type='button';b.className='sac-premium-tabbtn'+(i===0?' active':'');b.textContent=n;bar.appendChild(b);const pc=panel(n, i===0?'Campos reorganizados sem alterar regras, IDs ou validações do sistema.':'');pc[0].classList.toggle('active',i===0);tabs.appendChild(pc[0]);panels[n]=pc[1];b.addEventListener('click',()=>{document.querySelectorAll('.sac-premium-tabbtn').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.sac-premium-panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');pc[0].classList.add('active');});});
    form.insertBefore(tabs, layout);

    const empresa=byLabel('Empresa');
    const timeline=document.querySelector('.timeline-card');
    if(empresa&&timeline){const box=document.createElement('div');box.className='sac-premium-company';timeline.appendChild(box);move(empresa,box,'sac-premium-field-highlight');}

    const gCliente=wrapGrid(panels['Dados Cliente / Nota Fiscal']);
    ['Busca de cliente por palavra chave','Busca por Serial / Lote','Cliente selecionado','Nota Fiscal','Data de emissão da nota fiscal','Número da nota fiscal de Revenda','Data de emissão da nota fiscal Revenda','Vendedor','Setor que abriu o SAC','Usuário que abriu o SAC','Status inicial'].forEach(label=>{
      const f=byAnyLabel([label,label.replace('Revenda','revenda')]); if(f){ if(norm(label).includes('cliente selecionado')) f.classList.add('sac-premium-wide'); move(f,gCliente,'sac-premium-field-highlight'); }
    });

    const contato=cardByTitle('dados do contato'); if(contato){panels['Dados do contato'].appendChild(contato);}

    const itemCard=cardByTitle('inclusao de item')||cardByTitle('inclusão de item');
    if(itemCard){
      panels['Inclusão de item com problema'].appendChild(itemCard);
      const builder=itemCard.querySelector('.builder-card')||itemCard;
      const ordered=document.createElement('div');ordered.className='sac-premium-grid-3';
      const before=builder.firstChild; builder.insertBefore(ordered,before);
      const labels=['Item','Referência (SKU)','Identificador','Serial/Lote encontrado na base','Grupo','Quantidade total','Valor unitário','Quantidade com Problema','Número do serial ou lote','Tipo ocorrência','Relato do Cliente/usuário sobre o Problema'];
      labels.forEach(label=>{const f=byAnyLabel([label,label.replace('Referência','Referencia'),label.replace('usuário','usuario')]); if(f){ if(norm(label).includes('relato')||norm(label)==='item') f.classList.add('sac-premium-wide'); move(f,ordered,'sac-premium-field-highlight'); }});
      const conds=['Item Quebrado Inservível','Item de pequeno Valor','Ação em espera','Setor de destino'];
      conds.forEach(label=>{const f=byAnyLabel([label,label.replace('Inservível','Inservivel')]); if(f) move(f,ordered);});
    }

    const anexos=cardByTitle('anexos'); if(anexos){panels['Outros Dados'].appendChild(anexos);}
    // Move cards restantes da coluna esquerda para Outros Dados, sem esconder nada.
    const left=layout.querySelector(':scope > div:first-child');
    if(left){Array.from(left.children).forEach(el=>{if(el.classList&&el.classList.contains('card'))panels['Outros Dados'].appendChild(el);});}
    const right=layout.querySelector(':scope > div:last-child');
    if(right){right.classList.add('sac-premium-aside');Array.from(right.children).forEach(el=>{if(el.classList)el.classList.add('sac-premium-sticky');panels['Inclusão de item com problema'].appendChild(el);});}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setupTabs);else setupTabs();
})();
