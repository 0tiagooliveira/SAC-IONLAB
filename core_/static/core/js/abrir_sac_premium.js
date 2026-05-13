/* Abertura SAC Premium V3 - layout seguro + Item principal com autocomplete
   Não altera backend, name/id, validações ou regras. Mantém o select #itemNota como fonte oficial. */
(function(){
  function norm(t){return String(t||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toLowerCase();}
  function fieldOf(el){return el ? el.closest('.field') : null;}
  function byLabel(txt){
    const alvo=norm(txt); let best=null;
    document.querySelectorAll('.field').forEach(f=>{
      const l=f.querySelector('label'); if(!l) return;
      const n=norm(l.textContent);
      if((n===alvo || n.includes(alvo) || alvo.includes(n)) && !best) best=f;
    });
    return best;
  }
  function cardByTitle(txt){
    const alvo=norm(txt); let found=null;
    document.querySelectorAll('.card').forEach(c=>{
      const h=c.querySelector('h2');
      if(h && norm(h.textContent).includes(alvo) && !found) found=c;
    });
    return found;
  }
  function panel(title, subtitle){
    const p=document.createElement('section'); p.className='sac-premium-panel';
    const c=document.createElement('div'); c.className='sac-premium-card';
    const h=document.createElement('h2'); h.textContent=title; c.appendChild(h);
    if(subtitle){const s=document.createElement('div');s.className='sac-premium-note';s.textContent=subtitle;c.appendChild(s);}
    p.appendChild(c); return [p,c];
  }
  function move(field,parent,cls){ if(field&&parent){ if(cls) field.classList.add(cls); parent.appendChild(field); } }
  function wrapGrid(parent,cls){ const g=document.createElement('div'); g.className=cls||'sac-premium-grid'; parent.appendChild(g); return g; }

  function ensureItemAutocomplete(){
    const select=document.getElementById('itemNota');
    if(!select || select.dataset.autocompleteReady==='1') return;
    select.dataset.autocompleteReady='1';
    const f=fieldOf(select); if(!f) return;
    f.classList.add('sac-item-principal-field','sac-premium-wide');

    const wrap=document.createElement('div');
    wrap.className='sac-item-autocomplete-wrap';
    const input=document.createElement('input');
    input.type='text';
    input.id='itemNotaBuscaPremium';
    input.autocomplete='off';
    input.placeholder='Digite SKU, referência, descrição ou parte do nome do item...';
    input.className='sac-item-autocomplete-input';
    const list=document.createElement('div');
    list.className='sac-item-autocomplete-list';
    wrap.appendChild(input); wrap.appendChild(list);

    select.parentNode.insertBefore(wrap, select.nextSibling);
    select.classList.add('sac-select-original-preservado');

    function options(){return Array.from(select.options).filter(o=>o.value);}
    function textOf(o){return (o.textContent||o.text||'').trim();}
    function syncInput(){
      const o=select.options[select.selectedIndex];
      input.value = o && o.value ? textOf(o) : '';
    }
    function render(q){
      const query=norm(q);
      list.innerHTML='';
      const opts=options();
      if(!opts.length){
        list.innerHTML='<div class="sac-item-autocomplete-empty">Selecione primeiro a nota fiscal para carregar os itens.</div>';
        list.style.display='block'; return;
      }
      const found=opts.filter(o=>!query || norm(textOf(o)).includes(query)).slice(0,80);
      if(!found.length){
        list.innerHTML='<div class="sac-item-autocomplete-empty">Nenhum item encontrado para essa busca.</div>';
        list.style.display='block'; return;
      }
      found.forEach(o=>{
        const row=document.createElement('button'); row.type='button'; row.className='sac-item-autocomplete-option';
        const txt=textOf(o);
        const parts=txt.split(' - ');
        row.innerHTML='<strong>'+escapeHtml(parts[0]||txt)+'</strong>'+(parts.length>1?'<span>'+escapeHtml(parts.slice(1).join(' - '))+'</span>':'');
        row.addEventListener('mousedown',function(ev){
          ev.preventDefault();
          select.value=o.value;
          syncInput();
          list.style.display='none';
          select.dispatchEvent(new Event('change',{bubbles:true}));
        });
        list.appendChild(row);
      });
      list.style.display='block';
    }
    function escapeHtml(s){return String(s||'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}

    input.addEventListener('focus',()=>render(input.value));
    input.addEventListener('input',()=>render(input.value));
    input.addEventListener('keydown',function(e){
      if(e.key==='Escape') list.style.display='none';
      if(e.key==='Enter'){
        const first=list.querySelector('.sac-item-autocomplete-option');
        if(first){e.preventDefault(); first.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));}
      }
    });
    document.addEventListener('click',e=>{ if(!wrap.contains(e.target)) list.style.display='none'; });
    select.addEventListener('change',syncInput);
    new MutationObserver(syncInput).observe(select,{childList:true,subtree:true});
    syncInput();
  }

  function reorderItemFields(builder){
    if(!builder) return;
    const oldAuto=builder.querySelector('.sac-premium-grid-3');
    if(oldAuto && oldAuto.dataset.reordered==='1') return;

    let grid=builder.querySelector('.sac-item-grid-real');
    if(!grid){
      grid=document.createElement('div');
      grid.className='sac-item-grid-real';
      const badge=builder.querySelector('.badge');
      builder.insertBefore(grid, builder.firstElementChild || null);
    }

    const item=fieldOf(document.getElementById('itemNota'));
    const ref=fieldOf(document.getElementById('referenciaItem'));
    const identificador=fieldOf(document.getElementById('tipoRastreio'));
    const serialBase=fieldOf(document.getElementById('serialLoteBase'));
    const grupo=fieldOf(document.getElementById('grupoItem'));
    const qtdTotal=fieldOf(document.getElementById('quantidadeTotal'));
    const valor=fieldOf(document.getElementById('valorUnitario'));
    const qtdProb=fieldOf(document.getElementById('quantidadeProblema'));
    const numero=fieldOf(document.getElementById('numeroRastreio'));
    const tipo=fieldOf(document.getElementById('tipoOcorrencia'));
    const relato=fieldOf(document.getElementById('relatoProblema'));
    const quebrado=document.getElementById('campoItemQuebradoInservivel');
    const pequeno=document.getElementById('campoItemPequenoValor');
    const acao=fieldOf(document.getElementById('id_display_acao_em_espera'));
    const setor=fieldOf(document.getElementById('id_display_setor_destino'));

    [item,ref,identificador,serialBase,grupo,qtdTotal,valor,qtdProb,numero,tipo,relato,quebrado,pequeno,acao,setor].forEach(el=>{
      if(!el) return;
      if(el===item){ el.classList.add('sac-item-principal-field','sac-premium-wide'); }
      if(el===relato){ el.classList.add('sac-premium-wide'); }
      grid.appendChild(el);
    });
    ensureItemAutocomplete();
  }

  function setupTabs(){
    const form=document.getElementById('formSac'); const layout=document.querySelector('.layout');
    if(!form||!layout||document.querySelector('.sac-premium-tabs')){ ensureItemAutocomplete(); return; }
    layout.classList.add('sac-premium-hidden-old');

    const tabs=document.createElement('div'); tabs.className='sac-premium-tabs';
    const bar=document.createElement('div'); bar.className='sac-premium-tabbar'; tabs.appendChild(bar);
    const names=['Dados Cliente / Nota Fiscal','Dados do contato','Inclusão de item com problema','Outros Dados'];
    const panels={};
    names.forEach((n,i)=>{
      const b=document.createElement('button'); b.type='button'; b.className='sac-premium-tabbtn'+(i===0?' active':''); b.textContent=n; bar.appendChild(b);
      const pc=panel(n, i===0?'Campos reorganizados sem alterar regras, IDs ou validações do sistema.':'');
      pc[0].classList.toggle('active',i===0); tabs.appendChild(pc[0]); panels[n]=pc[1];
      b.addEventListener('click',()=>{document.querySelectorAll('.sac-premium-tabbtn').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.sac-premium-panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');pc[0].classList.add('active');});
    });
    form.insertBefore(tabs, layout);

    const empresa=byLabel('Empresa'); const timeline=document.querySelector('.timeline-card');
    if(empresa&&timeline){const box=document.createElement('div');box.className='sac-premium-company';timeline.appendChild(box);move(empresa,box,'sac-premium-field-highlight');}

    const gCliente=wrapGrid(panels['Dados Cliente / Nota Fiscal']);
    ['Busca de cliente por palavra chave','Busca por Serial / Lote','Cliente selecionado','Nota Fiscal','Data de emissão da nota fiscal','Número da nota fiscal de Revenda','Data de emissão da nota fiscal Revenda','Vendedor','Setor que abriu o SAC','Usuário que abriu o SAC','Status inicial'].forEach(label=>{
      const f=byLabel(label) || byLabel(label.replace('Revenda','revenda'));
      if(f){ if(norm(label).includes('cliente selecionado')) f.classList.add('sac-premium-wide'); move(f,gCliente,'sac-premium-field-highlight'); }
    });

    const contato=cardByTitle('dados do contato'); if(contato) panels['Dados do contato'].appendChild(contato);
    const itemCard=cardByTitle('inclusao de item')||cardByTitle('inclusão de item');
    if(itemCard){
      panels['Inclusão de item com problema'].appendChild(itemCard);
      reorderItemFields(itemCard.querySelector('.builder-card')||itemCard);
    }
    const anexos=cardByTitle('anexos'); if(anexos) panels['Outros Dados'].appendChild(anexos);

    const left=layout.querySelector(':scope > div:first-child');
    if(left){Array.from(left.children).forEach(el=>{if(el.classList&&el.classList.contains('card')) panels['Outros Dados'].appendChild(el);});}
    const right=layout.querySelector(':scope > div:last-child');
    if(right){right.classList.add('sac-premium-aside');Array.from(right.children).forEach(el=>{if(el.classList)el.classList.add('sac-premium-sticky');panels['Inclusão de item com problema'].appendChild(el);});}
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',setupTabs); else setupTabs();
})();
