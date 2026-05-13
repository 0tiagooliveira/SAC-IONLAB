from core.models import SAC, Setor
from core.services.fila_setorial import resumo_filas_por_setor


def fila_inteligente(request):
    if not request.user.is_authenticated:
        return {}

    resumos_validos = [resumo for resumo in resumo_filas_por_setor() if resumo.total > 0 and resumo.primeiro_sac_id]
    sac_ids = [resumo.primeiro_sac_id for resumo in resumos_validos]
    sacs_por_id = {
        sac.id: sac
        for sac in SAC.objects.select_related('cliente', 'status_atual').filter(id__in=sac_ids)
    }

    dados = []
    for resumo in resumos_validos:
        sac = sacs_por_id.get(resumo.primeiro_sac_id)
        if not sac:
            continue

        cliente = getattr(sac, 'cliente', None)
        cliente_texto = (
            getattr(cliente, 'razao_social', None)
            or getattr(cliente, 'nome', None)
            or '-'
        )
        status_obj = getattr(sac, 'status_atual', None) or getattr(sac, 'status', None)
        status_texto = getattr(status_obj, 'nome', '-') if status_obj else '-'

        dados.append({
            'setor': resumo.nome,
            'numero_sac': getattr(sac, 'numero', None) or getattr(sac, 'numero_sac', '-'),
            'cliente': cliente_texto,
            'status': status_texto,
            'total': resumo.total,
            'criticos': resumo.criticos,
            'tempo_mais_antigo': resumo.tempo_mais_antigo,
            'rota_lista': resumo.rota_lista,
        })

    return {'fila_inteligente': dados}


def menu_setores(request):
    if not request.user.is_authenticated:
        return {}

    setores = Setor.objects.filter(ativo=True).order_by('nome')
    return {'menu_setores': setores}
