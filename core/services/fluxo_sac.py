from __future__ import annotations

from typing import Optional

from core.models import SAC, AcaoEmEspera, Setor, StatusSAC, FluxoAcaoSetor
from core.services.regras_sac import (
    codigo_setor,
    eh_status_cancelado,
    eh_status_concluido,
    normalizar_nome,
)


class FluxoSACNaoConfigurado(ValueError):
    """Erro quando não existe regra ativa em FluxoAcaoSetor para a ação/setor atual."""


def is_setor(setor, codigo):
    if not setor:
        return False
    return codigo_setor(setor) == codigo_setor(codigo)


def acao_permite_selecao_manual_setor(acao_em_espera: Optional[AcaoEmEspera]) -> bool:
    if not acao_em_espera:
        return True
    return acao_em_espera.setor_destino_id is None


def obter_setor_destino_padrao(acao_em_espera: Optional[AcaoEmEspera]) -> Optional[Setor]:
    if acao_permite_selecao_manual_setor(acao_em_espera):
        return None
    return acao_em_espera.setor_destino


def validar_transicao_basica(
    sac: SAC,
    *,
    status_novo: Optional[StatusSAC] = None,
    acao_nova: Optional[AcaoEmEspera] = None,
    setor_destino: Optional[Setor] = None,
) -> None:
    if sac is None:
        raise ValueError('SAC inválido para validação de transição.')

    status_atual = getattr(sac, 'status_atual', None)

    if eh_status_concluido(status_atual):
        if acao_nova and normalizar_nome(getattr(acao_nova, 'nome', '')) not in {'reabrir'}:
            raise ValueError('SAC concluído só pode avançar mediante reabertura.')

    if eh_status_cancelado(status_atual) and acao_nova:
        raise ValueError('SAC cancelado não pode receber nova ação.')

    if acao_nova and not acao_permite_selecao_manual_setor(acao_nova):
        setor_padrao = obter_setor_destino_padrao(acao_nova)
        if setor_destino and setor_padrao and getattr(setor_destino, 'id', None) != getattr(setor_padrao, 'id', None):
            raise ValueError('Setor de destino divergente do padrão da ação.')


def obter_fluxo_dinamico(acao_atual, setor_atual=None):
    if not acao_atual:
        return None

    if setor_atual is not None:
        fluxo = (
            FluxoAcaoSetor.objects.filter(
                acao_atual=acao_atual,
                setor_atual=setor_atual,
                ativo=True,
            )
            .select_related('acao_atual', 'setor_atual', 'proxima_acao', 'proximo_setor', 'status_destino')
            .order_by('id')
            .first()
        )
        if fluxo:
            return fluxo

    return (
        FluxoAcaoSetor.objects.filter(
            acao_atual=acao_atual,
            setor_atual__isnull=True,
            ativo=True,
        )
        .select_related('acao_atual', 'setor_atual', 'proxima_acao', 'proximo_setor', 'status_destino')
        .first()
    )


def resolver_proximo_fluxo_por_codigo(acao_atual, setor_atual=None):
    fluxo = obter_fluxo_dinamico(acao_atual, setor_atual)
    if not fluxo:
        return None
    return {
        'fluxo': fluxo,
        'proxima_acao': getattr(fluxo, 'proxima_acao', None),
        'proximo_setor': getattr(fluxo, 'proximo_setor', None),
        'proximo_status': getattr(fluxo, 'status_destino', None),
    }


def resolver_proximo_setor_codigo(acao_atual, setor_atual=None):
    dados = resolver_proximo_fluxo_por_codigo(acao_atual, setor_atual)
    return (dados or {}).get('proximo_setor')


def resolver_proxima_acao_codigo(acao_atual, setor_atual=None):
    dados = resolver_proximo_fluxo_por_codigo(acao_atual, setor_atual)
    return (dados or {}).get('proxima_acao')


def resolver_proximo_status_codigo(acao_atual, setor_atual=None):
    dados = resolver_proximo_fluxo_por_codigo(acao_atual, setor_atual)
    return (dados or {}).get('proximo_status')


def transicao_exige_setor_manual(acao_em_espera: Optional[AcaoEmEspera]) -> bool:
    return acao_permite_selecao_manual_setor(acao_em_espera)


def mensagem_fluxo_nao_configurado(acao_atual, setor_atual=None):
    acao_nome = getattr(acao_atual, 'nome', None) or '-'
    setor_nome = getattr(setor_atual, 'nome', None) or '-'
    return (
        'Fluxo não configurado para:\n'
        f'Ação atual: {acao_nome}\n'
        f'Setor atual: {setor_nome}\n\n'
        'Cadastre a regra em FluxoAcaoSetor informando:\n'
        '- próxima ação\n'
        '- próximo setor'
    )


def diagnosticar_fluxo_inicial(sac: Optional[SAC], *, setor_contexto: Optional[Setor] = None, nome_tela: str = ''):
    if sac is None:
        return []

    alertas = []
    acao_atual = getattr(sac, 'acao_em_espera', None)
    setor_atual = setor_contexto or getattr(sac, 'setor_atual', None)

    if not acao_atual:
        alertas.append({
            'tipo': 'warning',
            'titulo': 'Ação atual não definida',
            'mensagem': (
                f'{nome_tela + ": " if nome_tela else ""}'
                'o SAC está sem ação em espera atual. '
                'Cadastre/ajuste a ação atual antes de tentar avançar o fluxo.'
            ),
        })
        return alertas

    if obter_fluxo_dinamico(acao_atual, setor_atual) is None:
        alertas.append({
            'tipo': 'warning',
            'titulo': 'Fluxo não configurado',
            'mensagem': mensagem_fluxo_nao_configurado(acao_atual, setor_atual),
        })

    return alertas


def buscar_fluxo_dinamico(acao_atual, setor_atual=None):
    fluxo = obter_fluxo_dinamico(acao_atual, setor_atual)
    if not fluxo:
        return None, None
    return fluxo.proxima_acao, fluxo.proximo_setor


def buscar_fluxo_obrigatorio(acao_atual, setor_atual=None):
    fluxo = obter_fluxo_dinamico(acao_atual, setor_atual)
    if fluxo:
        return fluxo
    raise FluxoSACNaoConfigurado(mensagem_fluxo_nao_configurado(acao_atual, setor_atual))


__all__ = [
    'FluxoSACNaoConfigurado',
    'is_setor',
    'normalizar_nome',
    'acao_permite_selecao_manual_setor',
    'obter_setor_destino_padrao',
    'validar_transicao_basica',
    'obter_fluxo_dinamico',
    'resolver_proximo_fluxo_por_codigo',
    'resolver_proximo_setor_codigo',
    'resolver_proxima_acao_codigo',
    'resolver_proximo_status_codigo',
    'transicao_exige_setor_manual',
    'mensagem_fluxo_nao_configurado',
    'diagnosticar_fluxo_inicial',
    'buscar_fluxo_dinamico',
    'buscar_fluxo_obrigatorio',
]
