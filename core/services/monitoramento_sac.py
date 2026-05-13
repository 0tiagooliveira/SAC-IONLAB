from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import List

from django.db.models import QuerySet
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.models import SAC
from core.services.fila_setorial import base_sacs_em_aberto, queryset_fila_por_setor
from core.services.sac_visual import formatar_duracao_dd_hh_mm


@dataclass
class ItemAuditoriaFluxo:
    tipo: str
    severidade: str
    sac_id: int
    numero: str
    descricao: str
    setor: str
    url: str


def _nome(obj, fallback='-'):
    if not obj:
        return fallback
    return getattr(obj, 'nome', str(obj))


def _codigo(obj, fallback=''):
    if not obj:
        return fallback
    return getattr(obj, 'codigo', '') or fallback


def _cliente_nome(sac: SAC) -> str:
    cliente = getattr(sac, 'cliente', None)
    if not cliente:
        return '-'
    return getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None) or '-'


def _resolver_url_sac(sac: SAC, setor=None) -> str:
    """
    Resolve a detail URL safely without depending on helper functions that may
    not exist in every deployed base.
    """
    setor = setor or getattr(sac, 'setor_atual', None)
    setor_codigo = _codigo(setor).upper()

    candidates = []
    if setor_codigo == 'COMERCIAL':
        candidates.append(('analise_comercial_sac', {'sac_id': sac.id}))
    elif setor_codigo == 'LOGISTICA':
        candidates.append(('gestao_logistica', {'sac_id': sac.id}))
    elif setor_codigo == 'DIRETORIA':
        candidates.append(('analise_diretoria', {'sac_id': sac.id}))
    elif setor_codigo in {'ASSESSORIA_CIENTIFICA', 'ASSESSORIA'}:
        candidates.append(('assessoria_cientifica', {'sac_id': sac.id}))
    elif setor_codigo == 'LICITACAO':
        candidates.append(('gestao_licitacao', {'sac_id': sac.id}))
    elif setor_codigo == 'ASSISTENCIA_TECNICA':
        candidates.append(('assistencia_tecnica', {'sac_id': sac.id}))
    elif setor_codigo == 'GESTAO' or _nome(setor, '').upper() == 'GESTÃO DO SAC':
        candidates.append(('gestao_sac', {'sac_id': sac.id}))

    candidates.extend([
        ('gestao_sac', {'sac_id': sac.id}),
        ('analise_comercial_sac', {'sac_id': sac.id}),
        ('gestao_logistica', {'sac_id': sac.id}),
        ('analise_diretoria', {'sac_id': sac.id}),
        ('assessoria_cientifica', {'sac_id': sac.id}),
        ('gestao_licitacao', {'sac_id': sac.id}),
        ('assistencia_tecnica', {'sac_id': sac.id}),
    ])

    tried = set()
    for name, kwargs in candidates:
        key = (name, tuple(sorted(kwargs.items())))
        if key in tried:
            continue
        tried.add(key)
        try:
            return reverse(name, kwargs=kwargs)
        except NoReverseMatch:
            continue

    return f'/sac/{sac.id}/'


def _montar_item_sac_parado(sac: SAC, agora=None) -> dict:
    agora = agora or timezone.now()
    setor = getattr(sac, 'setor_atual', None)
    url = _resolver_url_sac(sac, setor)
    return {
        'id': sac.id,
        'sac_id': sac.id,
        'numero': getattr(sac, 'numero', '') or f'SAC {sac.id}',
        'titulo': getattr(sac, 'titulo', '') or getattr(sac, 'descricao', '') or '',
        'cliente': _cliente_nome(sac),
        'setor': _nome(setor),
        'setor_codigo': _codigo(setor),
        'acao': _nome(getattr(sac, 'acao_em_espera', None)),
        'status': _nome(getattr(sac, 'status_atual', None), getattr(sac, 'status_inicial', '-')),
        'url': url,
        'tempo_aguardando': '',
        'tempo_horas': 0,
        'agora': agora,
    }


def listar_sacs_parados(horas: int = 24, limite: int = 10) -> List[dict]:
    agora = timezone.now()
    corte = agora - timedelta(hours=max(horas, 1))
    itens = []
    qs: QuerySet[SAC] = base_sacs_em_aberto().select_related(
        'setor_atual',
        'acao_em_espera',
        'status_atual',
        'cliente',
    )

    for sac in qs:
        ultimo_historico = sac.historicos.order_by('-data_evento', '-id').first()
        referencia = getattr(ultimo_historico, 'data_evento', None) or sac.data_abertura
        if not referencia or referencia > corte:
            continue

        horas_parado = round((agora - referencia).total_seconds() / 3600, 1)
        item = _montar_item_sac_parado(sac, agora=agora)
        item.update({
            'horas_parado': horas_parado,
            'tempo_horas': horas_parado,
            'tempo_aguardando': formatar_duracao_dd_hh_mm(agora - referencia),
            'referencia': referencia,
        })
        itens.append(item)

    itens.sort(key=lambda x: (-x['horas_parado'], x.get('numero') or ''))
    return itens[:limite] if limite else itens


def auditar_fluxo_operacional(limite: int = 30) -> List[ItemAuditoriaFluxo]:
    resultados: List[ItemAuditoriaFluxo] = []
    qs = SAC.objects.select_related('setor_atual', 'acao_em_espera', 'status_atual').all().order_by('-id')

    for sac in qs:
        setor = getattr(sac, 'setor_atual', None)
        status = getattr(sac, 'status_atual', None)
        acao = getattr(sac, 'acao_em_espera', None)
        url = _resolver_url_sac(sac, setor)

        if not setor:
            resultados.append(
                ItemAuditoriaFluxo('SEM_SETOR', 'alta', sac.id, sac.numero, 'SAC sem setor atual definido.', '-', url)
            )
            continue

        if not status:
            resultados.append(
                ItemAuditoriaFluxo('SEM_STATUS', 'alta', sac.id, sac.numero, 'SAC sem status atual definido.', _nome(setor), url)
            )

        if not acao and not getattr(sac, 'concluido_em', None) and not getattr(sac, 'cancelado_em', None):
            resultados.append(
                ItemAuditoriaFluxo('SEM_ACAO', 'media', sac.id, sac.numero, 'SAC aberto sem ação em espera.', _nome(setor), url)
            )

        status_codigo = _codigo(status).upper()
        if status_codigo in {'CONCLUIDO', 'CANCELADO'} and acao:
            resultados.append(
                ItemAuditoriaFluxo(
                    'STATUS_FINAL_COM_ACAO',
                    'media',
                    sac.id,
                    sac.numero,
                    'SAC em status final ainda possui ação pendente.',
                    _nome(setor),
                    url,
                )
            )

        try:
            fila_setor = queryset_fila_por_setor(setor)
            ids_fila = set(fila_setor.values_list('id', flat=True)[:500])
            if status_codigo not in {'CONCLUIDO', 'CANCELADO'} and sac.id not in ids_fila:
                resultados.append(
                    ItemAuditoriaFluxo(
                        'FORA_DA_FILA',
                        'baixa',
                        sac.id,
                        sac.numero,
                        'SAC em aberto não apareceu na fila esperada do próprio setor.',
                        _nome(setor),
                        url,
                    )
                )
        except Exception:
            resultados.append(
                ItemAuditoriaFluxo('ERRO_FILA', 'media', sac.id, sac.numero, 'Erro ao validar fila do setor atual.', _nome(setor), url)
            )

    resultados.sort(key=lambda x: ({'alta': 0, 'media': 1, 'baixa': 2}.get(x.severidade, 9), x.numero or ''))
    return resultados[:limite] if limite else resultados
