from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import AcaoEmEspera, SAC, SacHistorico, Setor, StatusSAC
from core.services.historico_sac import registrar_historico_sac
from core.services.sac_auditoria import registrar_log_sac
from core.services.fluxo_sac import (
    acao_permite_selecao_manual_setor,
    obter_setor_destino_padrao,
    validar_transicao_basica,
)
from core.services.regras_sac import (
    codigo_acao,
    codigo_setor,
    codigo_status,
    eh_status_cancelado,
    eh_status_concluido,
    resolver_acao_por_codigo,
    resolver_setor_por_codigo,
    resolver_status_por_codigo,
)


@dataclass(frozen=True)
class ResultadoTransicaoSAC:
    sac: SAC
    historico: SacHistorico
    status_anterior: Optional[StatusSAC]
    status_novo: Optional[StatusSAC]
    setor_origem: Optional[Setor]
    setor_destino: Optional[Setor]
    acao_em_espera: Optional[AcaoEmEspera]


class ErroTransicaoSAC(ValidationError):
    """Erro de validação de transição do SAC."""


def _resolver_instancia(modelo, valor, nome_campo: str):
    if valor in (None, ''):
        return None
    if isinstance(valor, modelo):
        return valor
    if isinstance(valor, int):
        return modelo.objects.filter(pk=valor).first()
    if isinstance(valor, str):
        valor = valor.strip()
        if not valor:
            return None
        if valor.isdigit():
            return modelo.objects.filter(pk=int(valor)).first()
        instancia = None
        if modelo is AcaoEmEspera:
            instancia = resolver_acao_por_codigo(valor) or modelo.objects.filter(nome__iexact=valor).first()
        elif modelo is StatusSAC:
            instancia = resolver_status_por_codigo(valor) or modelo.objects.filter(nome__iexact=valor).first()
        elif modelo is Setor:
            instancia = resolver_setor_por_codigo(valor) or modelo.objects.filter(nome__iexact=valor).first()
        if instancia:
            return instancia
        if hasattr(modelo, 'codigo'):
            instancia = modelo.objects.filter(codigo__iexact=valor).first()
            if instancia:
                return instancia
    raise ErroTransicaoSAC(f'Valor inválido para {nome_campo}.')


def _coagir_setor_destino(valor: Any):
    if valor in (None, ''):
        return None
    if isinstance(valor, Setor):
        return valor
    if isinstance(valor, int):
        return _resolver_instancia(Setor, valor, 'setor destino')
    if isinstance(valor, str):
        valor = valor.strip()
        if not valor:
            return None
        if valor.isdigit():
            return _resolver_instancia(Setor, int(valor), 'setor destino')
        return _resolver_instancia(Setor, valor, 'setor destino')
    return _resolver_instancia(Setor, valor, 'setor destino')


def _acao_para_texto(acao: Optional[AcaoEmEspera]) -> str:
    if not acao:
        return 'Atualização do SAC'
    return (acao.nome or 'Atualização do SAC').strip()


def _nome_usuario_historico(usuario) -> str:
    if not usuario:
        return ''
    try:
        nome = (usuario.get_full_name() or '').strip()
    except Exception:
        nome = ''
    if nome:
        return nome
    try:
        username = (usuario.get_username() or '').strip()
    except Exception:
        username = ''
    return username or str(usuario)


def _observacao_com_usuario(usuario, observacao: Optional[str]) -> Optional[str]:
    nome_usuario = _nome_usuario_historico(usuario)
    base = (observacao or '').strip()
    if not nome_usuario:
        return base or None

    prefixo = f'Usuário responsável: {nome_usuario}'
    if base:
        primeira_linha = base.splitlines()[0].strip().lower()
        if primeira_linha.startswith('usuário responsável:') or primeira_linha.startswith('usuario responsável:') or primeira_linha.startswith('usuario responsavel:') or primeira_linha.startswith('usuário responsavel:'):
            return base
        return f'{prefixo}\n{base}'
    return prefixo


def _status_eh_concluido(status: Optional[StatusSAC]) -> bool:
    return eh_status_concluido(status)


def _status_eh_cancelado(status: Optional[StatusSAC]) -> bool:
    return eh_status_cancelado(status)




def _codigo_status(status: Optional[StatusSAC]) -> str:
    return codigo_status(status)


def _codigo_setor(setor: Optional[Setor]) -> str:
    return codigo_setor(setor)


def _codigo_acao(acao: Optional[AcaoEmEspera]) -> str:
    return codigo_acao(acao)

def _existe_outro_sac_mesma_nf_pendente(sac: SAC) -> bool:
    nota_fiscal_id = getattr(sac, 'nota_fiscal_id', None)
    if not nota_fiscal_id:
        return False
    outros = SAC.objects.filter(nota_fiscal_id=nota_fiscal_id).exclude(pk=sac.pk).select_related('status_atual')
    for outro in outros:
        if not _status_eh_concluido(outro.status_atual) and not _status_eh_cancelado(outro.status_atual):
            return True
    return False


def validar_parametros_transicao(*, acao_em_espera: Optional[AcaoEmEspera], setor_destino: Optional[Setor], status_novo: Optional[StatusSAC]):
    acao = _resolver_instancia(AcaoEmEspera, acao_em_espera, 'ação em espera')
    setor = _coagir_setor_destino(setor_destino)
    status = _resolver_instancia(StatusSAC, status_novo, 'status novo')

    if acao:
        setor_padrao = obter_setor_destino_padrao(acao)
        permite_manual = acao_permite_selecao_manual_setor(acao)
        if setor_padrao and not isinstance(setor_padrao, Setor):
            try:
                setor_padrao = _resolver_instancia(Setor, getattr(setor_padrao, 'pk', setor_padrao), 'setor padrão')
            except (TypeError, ValueError, ErroTransicaoSAC):
                setor_padrao = None
        if setor_padrao and not permite_manual:
            setor = setor_padrao
        elif permite_manual and not setor and setor_padrao:
            setor = setor_padrao

    return acao, setor, status


def aplicar_transicao_sac(*, sac: SAC, usuario, acao_em_espera: Any = None, setor_destino: Any = None, status_novo: Any = None, observacao: Optional[str] = None, acao_executada_texto: Optional[str] = None, data_evento=None, salvar_sac: bool = True, arquivo_historico=None) -> ResultadoTransicaoSAC:
    if not sac:
        raise ErroTransicaoSAC('SAC não informado.')
    if not usuario:
        raise ErroTransicaoSAC('Usuário responsável não informado.')

    acao, setor_resolvido, status_resolvido = validar_parametros_transicao(
        acao_em_espera=acao_em_espera,
        setor_destino=setor_destino,
        status_novo=status_novo,
    )

    status_anterior = sac.status_atual
    setor_origem = sac.setor_atual
    status_final = status_resolvido or sac.status_atual
    setor_final = setor_resolvido or sac.setor_atual
    momento = data_evento or timezone.now()

    try:
        validar_transicao_basica(sac, status_novo=status_final, acao_nova=acao, setor_destino=setor_final)
    except ValueError as exc:
        raise ErroTransicaoSAC(str(exc))

    if _status_eh_concluido(status_final) and _existe_outro_sac_mesma_nf_pendente(sac):
        raise ErroTransicaoSAC(
            'Não é permitido concluir este SAC. Existem outros SACs da mesma Nota Fiscal ainda pendentes em outros setores.'
        )

    with transaction.atomic():
        campos_alterados = []

        if acao and sac.acao_em_espera_id != acao.id:
            sac.acao_em_espera = acao
            campos_alterados.append('acao_em_espera')

        if status_final and getattr(sac, 'status_atual_id', None) != status_final.id:
            sac.status_atual = status_final
            campos_alterados.append('status_atual')

        if setor_final and getattr(sac, 'setor_atual_id', None) != setor_final.id:
            sac.setor_atual = setor_final
            campos_alterados.append('setor_atual')

        if _status_eh_concluido(status_final):
            if getattr(sac, 'concluido_em', None) is None:
                sac.concluido_em = momento
                campos_alterados.append('concluido_em')
            if getattr(sac, 'cancelado_em', None) is not None:
                sac.cancelado_em = None
                campos_alterados.append('cancelado_em')
        elif _status_eh_cancelado(status_final):
            if getattr(sac, 'cancelado_em', None) is None:
                sac.cancelado_em = momento
                campos_alterados.append('cancelado_em')
        else:
            if status_resolvido and getattr(sac, 'concluido_em', None) is not None:
                sac.concluido_em = None
                campos_alterados.append('concluido_em')
            if status_resolvido and getattr(sac, 'cancelado_em', None) is not None:
                sac.cancelado_em = None
                campos_alterados.append('cancelado_em')

        if salvar_sac and campos_alterados:
            sac.save(update_fields=campos_alterados)
        elif salvar_sac and not campos_alterados:
            sac.save()

        historico = registrar_historico_sac(
            sac=sac,
            usuario=usuario,
            acao_executada=(acao_executada_texto or _acao_para_texto(acao)).strip(),
            observacao=_observacao_com_usuario(usuario, observacao),
            status_anterior=status_anterior,
            status_novo=status_final,
            setor_origem=setor_origem,
            setor_destino=setor_final,
            arquivo=arquivo_historico,
        )
        if historico.data_evento != momento:
            historico.data_evento = momento
            historico.save(update_fields=['data_evento'])

        registrar_log_sac(
            'transicao_sac',
            sac_id=sac.id,
            numero_sac=getattr(sac, 'numero', None),
            usuario=_nome_usuario_historico(usuario),
            status_anterior=getattr(status_anterior, 'nome', None),
            status_novo=getattr(status_final, 'nome', None),
            setor_origem=getattr(setor_origem, 'nome', None),
            setor_destino=getattr(setor_final, 'nome', None),
            acao_em_espera=getattr(acao, 'nome', None),
            historico_id=historico.id,
            salvar_sac=salvar_sac,
        )

    return ResultadoTransicaoSAC(
        sac=sac,
        historico=historico,
        status_anterior=status_anterior,
        status_novo=status_final,
        setor_origem=setor_origem,
        setor_destino=setor_final,
        acao_em_espera=acao,
    )


registrar_transicao_sac = aplicar_transicao_sac
salvar_transicao_sac = aplicar_transicao_sac
