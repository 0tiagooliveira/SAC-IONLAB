/* Abertura SAC - apoio visual seguro.
   Mantem o select #itemNota como fonte oficial e nao altera backend, ids ou validacoes. */
(function () {
  function fieldOf(el) {
    return el ? el.closest('.field') : null;
  }

  function normalizar(texto) {
    return String(texto || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  function escapeHtml(texto) {
    return String(texto || '').replace(/[&<>'"]/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[c];
    });
  }

  function prepararAutocompleteItem() {
    const select = document.getElementById('itemNota');
    if (!select || select.dataset.autocompleteReady === '1') return;
    select.dataset.autocompleteReady = '1';

    const field = fieldOf(select);
    if (!field) return;

    field.classList.add('sac-item-principal-field');

    const wrap = document.createElement('div');
    wrap.className = 'sac-item-autocomplete-wrap';

    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'itemNotaBuscaPremium';
    input.autocomplete = 'off';
    input.placeholder = 'Digite SKU, referencia, descricao ou parte do item...';
    input.className = 'sac-item-autocomplete-input';

    const list = document.createElement('div');
    list.className = 'sac-item-autocomplete-list';

    wrap.appendChild(input);
    wrap.appendChild(list);
    select.parentNode.insertBefore(wrap, select.nextSibling);
    select.classList.add('sac-select-original-preservado');

    function opcoesValidas() {
      return Array.from(select.options).filter(function (option) {
        return option.value;
      });
    }

    function textoOpcao(option) {
      return (option.textContent || option.text || '').trim();
    }

    function sincronizarInput() {
      const option = select.options[select.selectedIndex];
      input.value = option && option.value ? textoOpcao(option) : '';
    }

    function renderizar(query) {
      const alvo = normalizar(query);
      list.innerHTML = '';

      const opcoes = opcoesValidas();
      if (!opcoes.length) {
        list.innerHTML = '<div class="sac-item-autocomplete-empty">Selecione primeiro a nota fiscal para carregar os itens.</div>';
        list.style.display = 'block';
        return;
      }

      const encontradas = opcoes.filter(function (option) {
        return !alvo || normalizar(textoOpcao(option)).includes(alvo);
      }).slice(0, 80);

      if (!encontradas.length) {
        list.innerHTML = '<div class="sac-item-autocomplete-empty">Nenhum item encontrado para essa busca.</div>';
        list.style.display = 'block';
        return;
      }

      encontradas.forEach(function (option) {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'sac-item-autocomplete-option';
        const texto = textoOpcao(option);
        const partes = texto.split(' - ');
        row.innerHTML = '<strong>' + escapeHtml(partes[0] || texto) + '</strong>' +
          (partes.length > 1 ? '<span>' + escapeHtml(partes.slice(1).join(' - ')) + '</span>' : '');
        row.addEventListener('mousedown', function (event) {
          event.preventDefault();
          select.value = option.value;
          sincronizarInput();
          list.style.display = 'none';
          select.dispatchEvent(new Event('change', {bubbles: true}));
        });
        list.appendChild(row);
      });

      list.style.display = 'block';
    }

    input.addEventListener('focus', function () { renderizar(input.value); });
    input.addEventListener('input', function () { renderizar(input.value); });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') list.style.display = 'none';
      if (event.key === 'Enter') {
        const first = list.querySelector('.sac-item-autocomplete-option');
        if (first) {
          event.preventDefault();
          first.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
        }
      }
    });
    document.addEventListener('click', function (event) {
      if (!wrap.contains(event.target)) list.style.display = 'none';
    });
    select.addEventListener('change', sincronizarInput);
    new MutationObserver(sincronizarInput).observe(select, {childList: true, subtree: true});
    sincronizarInput();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', prepararAutocompleteItem);
  } else {
    prepararAutocompleteItem();
  }
})();
