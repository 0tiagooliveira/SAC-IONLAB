from __future__ import annotations

from typing import Optional

from core.models import SAC, SacHistorico, Setor, StatusSAC
from core.services.texto_padrao import padronizar_caixa_texto


def registrar_historico_sac(
    *,
    sac: SAC,
    usuario,
    acao_executada: str,
    observacao: str = '',
    status_anterior: Optional[StatusSAC] = None,
    status_novo: Optional[StatusSAC] = None,
    setor_origem: Optional[Setor] = None,
    setor_destino: Optional[Setor] = None,
    arquivo=None,
) -> SacHistorico:
    """Centraliza a gravação de histórico do SAC em um único ponto."""
    if sac is None:
        raise ValueError('SAC é obrigatório para registrar histórico.')
    if usuario is None:
        raise ValueError('Usuário é obrigatório para registrar histórico.')
    if not (acao_executada or '').strip():
        raise ValueError('A ação executada deve ser informada no histórico do SAC.')

    return SacHistorico.objects.create(
        sac=sac,
        usuario=usuario,
        status_anterior=status_anterior,
        status_novo=status_novo,
        setor_origem=setor_origem,
        setor_destino=setor_destino,
        acao_executada=acao_executada.strip(),
        observacao=padronizar_caixa_texto((observacao or '').strip()) or None,
        arquivo=arquivo,
    )
