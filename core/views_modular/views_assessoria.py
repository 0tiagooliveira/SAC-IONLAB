from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from core.services.empresa_filtro import aplicar_filtro_empresa, resolver_filtro_empresa
from core.services.sac_bridge import sac_aguardando_acao_assessoria_queryset
from core.services.sac_dados_oficiais import montar_dados_sac_oficiais
from core.services.sac_visual import (
    acao_em_espera_card as _acao_em_espera_card,
    classe_tempo_espera as _classe_tempo_espera,
    empresa_sac as _empresa_sac,
    formatar_numero_sac as _formatar_numero_sac,
    nota_sac as _nota_sac,
    resumo_tempo_setor as _resumo_tempo_setor,
    status_anterior_card as _status_anterior_card,
)


@login_required
def assessoria_cientifica(request):
    empresa_filtro, contexto_empresa = resolver_filtro_empresa(request)
    sacs_qs = sac_aguardando_acao_assessoria_queryset()
    sacs_qs = aplicar_filtro_empresa(sacs_qs, empresa_filtro)
    agora = timezone.now()
    cards_pendentes = []

    for sac_item in sacs_qs:
        tempo = _resumo_tempo_setor(sac_item, agora=agora)
        marco = tempo['marco_tempo']
        cliente_nome = (
            sac_item.cliente.razao_social if sac_item.cliente and getattr(sac_item.cliente, 'razao_social', None)
            else (sac_item.cliente.nome if sac_item.cliente and getattr(sac_item.cliente, 'nome', None) else '-')
        )
        dados_oficiais = montar_dados_sac_oficiais(sac_item)
        cards_pendentes.append({
            'id': sac_item.id,
            'numero': _formatar_numero_sac(sac_item),
            'numero_sac': _formatar_numero_sac(sac_item),
            'empresa_nome': _empresa_sac(sac_item),
            'cliente_nome': cliente_nome,
            'nota_fiscal_numero': _nota_sac(sac_item),
            'data_nf': dados_oficiais.get('data_nf_formatada', '-'),
            'numero_nf_revenda': dados_oficiais.get('numero_nf_revenda') or '-',
            'data_nf_revenda': dados_oficiais.get('data_nf_revenda_formatada', '-'),
            'tempo_uso_oficial': dados_oficiais.get('tempo_uso_formatado') or 'Não calculado',
            'status_atual_nome': _status_anterior_card(sac_item),
            'acao_em_espera_nome': _acao_em_espera_card(sac_item),
            'tempo_espera': tempo['tempo_espera'],
            'tempo_cor': tempo['tempo_cor'],
            'marco_tempo': marco,
        })

    cards_pendentes = sorted(cards_pendentes, key=lambda x: (x['marco_tempo'], x['id']))

    return render(request, 'core/assessoria_cientifica.html', {
        'sacs_disponiveis': cards_pendentes,
        'cards_pendentes': cards_pendentes,
        'total_sacs': len(cards_pendentes),
        **contexto_empresa,
    })
