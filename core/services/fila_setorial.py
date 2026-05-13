from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db.models import Q, QuerySet
from django.utils import timezone

from core.models import SAC, Setor
from core.services.regras_sac import (
    aliases_acao,
    aliases_setor,
    aliases_status,
    codigo_setor,
    eh_setor_assistencia_tecnica,
    eh_setor_assessoria,
    eh_setor_comercial,
    eh_setor_diretoria,
    eh_setor_licitacao,
    eh_setor_logistica,
    eh_setor_sac,
    rota_detalhe_por_codigo_setor,
    rota_lista_por_codigo_setor,
)
from core.services.sac_visual import formatar_duracao_dd_hh_mm


@dataclass(frozen=True)
class FilaSetorialResumo:
    nome: str
    rota_lista: str
    total: int
    primeiro_sac_id: Optional[int] = None
    criticos: int = 0
    tempo_mais_antigo: str = '-'


SETORES_PRIORITARIOS = (
    'SAC',
    'Gestão Comercial',
    'Assessoria Científica',
    'Gestão Logística',
    'Diretoria',
    'Licitação',
)


def _texto(valor) -> str:
    return str(valor or '').strip().lower()


def _q_por_nomes(field: str, nomes: set[str]) -> Q:
    q = Q()
    for nome in sorted({n for n in nomes if n}):
        q |= Q(**{f'{field}__iexact': nome})
    return q


def _q_por_codigo_ou_nome(field_base: str, codigo: str) -> Q:
    nomes = aliases_setor(codigo)
    q = _q_por_nomes(f'{field_base}__nome', nomes)
    q |= Q(**{f'{field_base}__codigo__iexact': codigo})
    return q


def _q_setor_unico(codigo: str) -> Q:
    return (
        _q_por_codigo_ou_nome('setor_atual', codigo) |
        (Q(setor_atual__isnull=True) & _q_por_codigo_ou_nome('acao_em_espera__setor_destino', codigo))
    )


def _q_status(codigo: str) -> Q:
    q = _q_por_nomes('status_atual__nome', aliases_status(codigo))
    q |= Q(status_atual__codigo__iexact=codigo)
    return q


def _q_acao(codigo: str) -> Q:
    q = _q_por_nomes('acao_em_espera__nome', aliases_acao(codigo))
    q |= Q(acao_em_espera__codigo__iexact=codigo)
    return q


def _base_qs() -> QuerySet:
    qs = (
        SAC.objects.select_related(
            'empresa', 'cliente', 'nota_fiscal',
            'acao_em_espera', 'acao_em_espera__setor_destino',
            'status_atual', 'setor_atual'
        )
        .prefetch_related('historicos')
    )
    return qs.exclude(_q_status('CONCLUIDO') | _q_status('CANCELADO')).distinct()


def base_sacs_em_aberto() -> QuerySet:
    return _base_qs()


def _q_gestao() -> Q:
    return _q_setor_unico('SAC')


def _q_comercial() -> Q:
    return _q_setor_unico('COMERCIAL')


def _q_assessoria() -> Q:
    return _q_setor_unico('ASSESSORIA')


def _q_logistica() -> Q:
    return _q_setor_unico('LOGISTICA')


def _q_diretoria() -> Q:
    return _q_setor_unico('DIRETORIA')


def _q_licitacao(setor: Optional[Setor] = None) -> Q:
    q = _q_setor_unico('LICITACAO')
    if setor is not None:
        q |= Q(setor_atual_id=setor.id) | (Q(setor_atual__isnull=True) & Q(acao_em_espera__setor_destino_id=setor.id))
    return q


def _marco_tempo_sac(sac: SAC):
    historico = None
    cache_prefetch = getattr(sac, '_prefetched_objects_cache', {})
    historicos_prefetch = cache_prefetch.get('historicos')
    if historicos_prefetch is not None:
        historico = historicos_prefetch[0] if historicos_prefetch else None
    elif hasattr(sac, 'historicos'):
        try:
            historico = sac.historicos.order_by('-data_evento', '-id').first()
        except Exception:
            historico = None
    return getattr(historico, 'data_evento', None) or getattr(sac, 'data_abertura', None) or timezone.now()


def _tempo_espera_humano(delta) -> str:
    return formatar_duracao_dd_hh_mm(delta)


def _critico(delta) -> bool:
    return delta >= timedelta(days=1)


def queryset_fila_por_setor(setor: Optional[Setor] = None, *, nome_setor: Optional[str] = None) -> QuerySet:
    referencia = nome_setor or getattr(setor, 'codigo', None) or getattr(setor, 'nome', None) or ''
    codigo = codigo_setor(referencia)
    qs = _base_qs()
    if eh_setor_sac(codigo):
        return qs.filter(_q_gestao()).order_by('data_abertura', 'id')
    if eh_setor_comercial(codigo):
        return qs.filter(_q_comercial()).order_by('data_abertura', 'id')
    if eh_setor_assessoria(codigo):
        filtro = _q_assessoria()
        if setor is not None:
            filtro |= Q(setor_atual_id=setor.id) | (Q(setor_atual__isnull=True) & Q(acao_em_espera__setor_destino_id=setor.id))
        return qs.filter(filtro).order_by('data_abertura', 'id')
    if eh_setor_logistica(codigo):
        filtro = _q_logistica()
        if setor is not None:
            filtro |= Q(setor_atual_id=setor.id) | (Q(setor_atual__isnull=True) & Q(acao_em_espera__setor_destino_id=setor.id))
        return qs.filter(filtro).order_by('data_abertura', 'id')
    if eh_setor_diretoria(codigo):
        filtro = _q_diretoria()
        if setor is not None:
            filtro |= Q(setor_atual_id=setor.id) | (Q(setor_atual__isnull=True) & Q(acao_em_espera__setor_destino_id=setor.id))
        return qs.filter(filtro).order_by('data_abertura', 'id')
    if eh_setor_licitacao(codigo):
        return qs.filter(_q_licitacao(setor)).order_by('data_abertura', 'id')
    if eh_setor_assistencia_tecnica(codigo):
        if setor is not None:
            return qs.filter(Q(setor_atual_id=setor.id) | (Q(setor_atual__isnull=True) & Q(acao_em_espera__setor_destino_id=setor.id))).order_by('data_abertura', 'id')
    if setor is not None:
        return qs.filter(Q(setor_atual_id=setor.id) | (Q(setor_atual__isnull=True) & Q(acao_em_espera__setor_destino_id=setor.id))).order_by('data_abertura', 'id')
    return qs.none()


def _resumo_setor(nome: str) -> FilaSetorialResumo:
    setor = Setor.objects.filter(nome__iexact=nome).first() or Setor.objects.filter(codigo__iexact=codigo_setor(nome)).first()
    qs = queryset_fila_por_setor(setor, nome_setor=nome)
    agora = timezone.now()
    sacs = list(qs[:50])
    criticos = 0
    tempo_mais_antigo = '-'
    primeiro = sacs[0] if sacs else None
    if sacs:
        deltas = []
        for sac in sacs:
            delta = agora - _marco_tempo_sac(sac)
            deltas.append(delta)
            if _critico(delta):
                criticos += 1
        if deltas:
            tempo_mais_antigo = _tempo_espera_humano(max(deltas))
    return FilaSetorialResumo(
        nome=nome,
        rota_lista=rota_lista_por_codigo_setor(nome),
        total=qs.count(),
        primeiro_sac_id=getattr(primeiro, 'id', None),
        criticos=criticos,
        tempo_mais_antigo=tempo_mais_antigo,
    )


def resumo_filas_por_setor() -> list[FilaSetorialResumo]:
    resumos = [_resumo_setor(nome) for nome in SETORES_PRIORITARIOS]
    nomes_base = {_texto(item.nome) for item in resumos}
    extras = []
    for setor in Setor.objects.filter(ativo=True).order_by('nome'):
        if _texto(setor.nome) in nomes_base:
            continue
        resumo = _resumo_setor(setor.nome)
        if resumo.total > 0:
            extras.append(resumo)
    return resumos + extras


def top_sacs_criticos(limit: int = 5):
    agora = timezone.now()
    sacs = list(_base_qs().select_related('cliente', 'status_atual', 'setor_atual', 'acao_em_espera__setor_destino'))
    sacs.sort(key=lambda sac: (_marco_tempo_sac(sac), getattr(sac, 'id', 0)))
    dados = []
    for sac in sacs[:limit]:
        cliente = getattr(sac, 'cliente', None)
        cliente_nome = getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None) or '-'
        setor = getattr(sac, 'setor_atual', None) or getattr(getattr(sac, 'acao_em_espera', None), 'setor_destino', None)
        codigo = codigo_setor(setor)
        delta = agora - _marco_tempo_sac(sac)
        dados.append({
            'numero': getattr(sac, 'numero', None) or f'SAC {sac.id}',
            'cliente': cliente_nome,
            'status': getattr(getattr(sac, 'status_atual', None), 'nome', None) or getattr(sac, 'status_inicial', '-') or '-',
            'setor': getattr(setor, 'nome', None) or '-',
            'tempo_espera': _tempo_espera_humano(delta),
            'critico': _critico(delta),
            'url': rota_detalhe_por_codigo_setor(codigo, getattr(sac, 'id', None)),
        })
    return dados


def rota_detalhe_sac_por_setor(sac: Optional[SAC]) -> str:
    if sac is None:
        return '/sac/gestao/'
    setor = getattr(sac, 'setor_atual', None) or getattr(getattr(sac, 'acao_em_espera', None), 'setor_destino', None)
    return rota_detalhe_por_codigo_setor(codigo_setor(setor), getattr(sac, 'id', None))
