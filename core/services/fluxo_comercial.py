from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from core.models import AcaoEmEspera, Setor, StatusSAC
from core.services.regras_sac import (
    resolver_acao_por_codigo,
    resolver_setor_por_codigo,
    resolver_status_por_codigo,
)


@dataclass(frozen=True)
class ResultadoFluxoComercial:
    confirmado_cliente: bool
    aceita_negociacao: bool
    item_pequeno_valor: bool
    status_nome: str
    status_codigo: str = ""
    acao_nome: str = ""
    acao_codigo: str = ""
    setor_nome: str = ""
    setor_codigo: str = ""
    exigir_desconto: bool = False
    ocultar_campos_abaixo: bool = False


LIMITE_ITEM_PEQUENO_VALOR = Decimal("200.00")


def calcular_item_pequeno_valor(valor_total_com_problema: Optional[Decimal]) -> bool:
    try:
        return Decimal(valor_total_com_problema or 0) <= LIMITE_ITEM_PEQUENO_VALOR
    except Exception:
        return False


def calcular_total_com_problema(itens) -> Decimal:
    total = Decimal('0')
    for item in itens:
        item_nf = getattr(item, 'item_nota_fiscal', None)
        valor_unitario = Decimal('0')
        if item_nf is not None:
            for attr in ('valor_unitario', 'preco_unitario', 'vlr_unitario', 'valor'):
                valor = getattr(item_nf, attr, None)
                if valor not in (None, ''):
                    try:
                        valor_unitario = Decimal(str(valor))
                        break
                    except (InvalidOperation, TypeError, ValueError):
                        pass
            if valor_unitario == 0:
                quantidade_nf = getattr(item_nf, 'quantidade', None) or getattr(item_nf, 'pr_qtd', None) or 0
                total_nf = getattr(item_nf, 'valor_total_item', None) or getattr(item_nf, 'pr_sbt', None) or 0
                try:
                    quantidade_nf = Decimal(str(quantidade_nf))
                    total_nf = Decimal(str(total_nf))
                    if quantidade_nf > 0:
                        valor_unitario = total_nf / quantidade_nf
                except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
                    valor_unitario = Decimal('0')
        try:
            qtd_problema = Decimal(str(getattr(item, 'quantidade_com_problema', 0) or 0))
        except (InvalidOperation, TypeError, ValueError):
            qtd_problema = Decimal('0')
        total += valor_unitario * qtd_problema
    return total


# Regra única oficial da Comercial.
def resolver_fluxo_comercial(*, confirmado_cliente: bool, aceita_negociacao: bool, item_pequeno_valor: bool) -> ResultadoFluxoComercial:
    if confirmado_cliente:
        return ResultadoFluxoComercial(
            confirmado_cliente=True,
            aceita_negociacao=False,
            item_pequeno_valor=item_pequeno_valor,
            status_nome="Concluído",
            status_codigo="CONCLUIDO",
            acao_nome="",
            acao_codigo="",
            setor_nome="",
            setor_codigo="",
            exigir_desconto=False,
            ocultar_campos_abaixo=True,
        )

    if aceita_negociacao:
        return ResultadoFluxoComercial(
            confirmado_cliente=False,
            aceita_negociacao=True,
            item_pequeno_valor=item_pequeno_valor,
            status_nome="Em Análise",
            status_codigo="EM_ANALISE",
            acao_nome="Aguardando Aprovação de Desconto",
            acao_codigo="APROVACAO_DESCONTO",
            setor_nome="Diretoria",
            setor_codigo="DIRETORIA",
            exigir_desconto=True,
            ocultar_campos_abaixo=False,
        )

    if item_pequeno_valor:
        return ResultadoFluxoComercial(
            confirmado_cliente=False,
            aceita_negociacao=False,
            item_pequeno_valor=True,
            status_nome="Em Análise",
            status_codigo="EM_ANALISE",
            acao_nome="Aguardando Autorização para Doação/Brinde",
            acao_codigo="AGUARDANDO_AUTORIZACAO_DOACAO_BRINDE",
            setor_nome="Diretoria",
            setor_codigo="DIRETORIA",
            exigir_desconto=False,
            ocultar_campos_abaixo=False,
        )

    return ResultadoFluxoComercial(
        confirmado_cliente=False,
        aceita_negociacao=False,
        item_pequeno_valor=False,
        status_nome="Emissão do Pedido de Entrada/Retorno",
        status_codigo="EMISSAO_PEDIDO_DE_ENTRADA_RETORNO",
        acao_nome="Emissão do Pedido de Entrada/Retorno",
        acao_codigo="EMISSAO_DO_PEDIDO_DE_ENTRADA_RETORNO",
        setor_nome="SAC",
        setor_codigo="SAC",
        exigir_desconto=False,
        ocultar_campos_abaixo=False,
    )


def _resolver_por_nome(modelo, nome: str):
    if not nome:
        return None
    return modelo.objects.filter(nome__iexact=nome).first()


def resolver_instancias_fluxo_comercial(*, confirmado_cliente: bool, aceita_negociacao: bool, item_pequeno_valor: bool):
    resultado = resolver_fluxo_comercial(
        confirmado_cliente=confirmado_cliente,
        aceita_negociacao=aceita_negociacao,
        item_pequeno_valor=item_pequeno_valor,
    )

    status = resolver_status_por_codigo(resultado.status_codigo) if resultado.status_codigo else None
    if status is None and resultado.status_nome:
        status = _resolver_por_nome(StatusSAC, resultado.status_nome)

    acao = resolver_acao_por_codigo(resultado.acao_codigo) if resultado.acao_codigo else None
    if acao is None and resultado.acao_nome:
        acao = _resolver_por_nome(AcaoEmEspera, resultado.acao_nome)

    setor = resolver_setor_por_codigo(resultado.setor_codigo) if resultado.setor_codigo else None
    if setor is None and resultado.setor_nome:
        setor = _resolver_por_nome(Setor, resultado.setor_nome)

    return {
        "resultado": resultado,
        "status": status,
        "acao": acao,
        "setor": setor,
    }
