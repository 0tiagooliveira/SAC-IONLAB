from __future__ import annotations

import unicodedata
from decimal import Decimal

from core.models import SAC, SacHistorico, Setor, StatusSAC, AcaoEmEspera
from core.services.fluxo_licitacao import (
    extrair_dados_analise_licitacao as _extrair_dados_analise_licitacao_service,
    montar_contexto_analise_licitacao as _montar_contexto_analise_licitacao_service,
    resolver_fluxo_fixo_licitacao as _resolver_fluxo_fixo_licitacao_service,
)
from core.services.fila_setorial import queryset_fila_por_setor
from core.services.regras_sac import (
    resolver_acao_por_codigo,
    resolver_setor_por_codigo,
    resolver_status_por_codigo,
)


def obter_setor_por_nome(nome):
    return Setor.objects.filter(nome__iexact=nome).first()


def obter_status_por_nome(nome):
    return StatusSAC.objects.filter(nome__iexact=nome, ativo=True).first()


def obter_acao_por_nome(nome):
    if not nome:
        return None
    nome_limpo = str(nome).strip()
    return (
        resolver_acao_por_codigo(nome_limpo)
        or AcaoEmEspera.objects.filter(codigo__iexact=nome_limpo).first()
        or AcaoEmEspera.objects.filter(nome__iexact=nome_limpo).first()
    )


def obter_acao_por_codigo(codigo):
    return resolver_acao_por_codigo(codigo)


def obter_setor_por_codigo(codigo):
    return resolver_setor_por_codigo(codigo)


def texto_normalizado(valor):
    return unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii').strip().lower()


def _setor_por_codigo_ou_nome(codigo: str, nome: str | None = None):
    return resolver_setor_por_codigo(codigo) or (Setor.objects.filter(nome__iexact=nome).first() if nome else None)


def _queryset_fila_setor_atual(setor):
    if not setor:
        return SAC.objects.none()
    return queryset_fila_por_setor(setor)


def sac_aguardando_acao_gestao_queryset():
    return _queryset_fila_setor_atual(_setor_por_codigo_ou_nome('SAC', 'SAC'))


def sac_aguardando_acao_comercial_queryset():
    return _queryset_fila_setor_atual(_setor_por_codigo_ou_nome('COMERCIAL', 'Comercial'))


def sac_aguardando_acao_assessoria_queryset():
    return _queryset_fila_setor_atual(
        _setor_por_codigo_ou_nome('ASSESSORIA', 'Assessoria Científica')
        or _setor_por_codigo_ou_nome('ASSESSORIA', 'Assessoria Cientifica')
    )


def sac_aguardando_acao_logistica_queryset():
    return _queryset_fila_setor_atual(
        _setor_por_codigo_ou_nome('LOGISTICA', 'Logística')
        or _setor_por_codigo_ou_nome('LOGISTICA', 'Logistica')
    )


def sac_aguardando_acao_diretoria_queryset():
    return _queryset_fila_setor_atual(_setor_por_codigo_ou_nome('DIRETORIA', 'Diretoria'))


def sac_aguarda_acao_licitacao_queryset():
    return _queryset_fila_setor_atual(
        _setor_por_codigo_ou_nome('LICITACAO', 'Licitação')
        or _setor_por_codigo_ou_nome('LICITACAO', 'Licitacao')
    )


def sac_aguardando_acao_assistencia_tecnica_queryset():
    return _queryset_fila_setor_atual(
        _setor_por_codigo_ou_nome('ASSISTENCIA_TECNICA', 'Assistência Técnica')
        or _setor_por_codigo_ou_nome('ASSISTENCIA_TECNICA', 'Assistencia Tecnica')
    )


def diretoria_campos_historico(observacoes='', acao_em_espera_setor='', valor_pleiteado='', decisao='', contraproposta='', proximo_status='', proxima_acao='', proximo_setor=''):
    linhas = []
    if acao_em_espera_setor:
        linhas.append(f"Ação em espera desse setor: {acao_em_espera_setor}")
    if valor_pleiteado not in (None, ''):
        linhas.append(f"Valor do desconto pleiteado: {valor_pleiteado}")
    if decisao:
        linhas.append(f"O valor do desconto será: {decisao}")
    if contraproposta not in (None, ''):
        linhas.append(f"Contra proposta de desconto: {contraproposta}")
    if proximo_status:
        linhas.append(f"Próximo status: {proximo_status}")
    if proxima_acao:
        linhas.append(f"Ação em espera: {proxima_acao}")
    if proximo_setor:
        linhas.append(f"Próximo setor: {proximo_setor}")
    linhas.append(f"Observações: {(observacoes or '').strip() or '-'}")
    return '\n'.join(linhas)


def extrair_primeiro_valor_do_historico(sac, rotulos):
    if sac is None:
        return ''
    if isinstance(rotulos, str):
        rotulos = [rotulos]
    historicos = (
        SacHistorico.objects.filter(sac=sac)
        .exclude(observacao__isnull=True)
        .exclude(observacao__exact='')
        .order_by('-data_evento', '-id')
    )
    rotulos_norm = [r.strip().lower() for r in rotulos]
    for hist in historicos:
        texto = (hist.observacao or '').strip()
        if not texto:
            continue
        for linha in texto.splitlines():
            if ':' not in linha:
                continue
            chave, valor = linha.split(':', 1)
            if chave.strip().lower() in rotulos_norm:
                return valor.strip()
    return ''


def normalizar_decimal_texto_ptbr(valor):
    bruto = (valor or '').strip()
    if not bruto:
        return ''
    bruto = bruto.replace('R$', '').replace(' ', '')
    if ',' in bruto and '.' in bruto:
        if bruto.rfind(',') > bruto.rfind('.'):
            bruto = bruto.replace('.', '').replace(',', '.')
        else:
            bruto = bruto.replace(',', '')
    elif ',' in bruto:
        bruto = bruto.replace('.', '').replace(',', '.')
    try:
        return Decimal(bruto)
    except Exception:
        return None


# Wrappers de compatibilidade: a fonte canônica de licitação agora é core.services.fluxo_licitacao

def _texto_normalizado_licitacao(valor):
    return texto_normalizado(valor)


def _resolver_status_em_analise():
    return resolver_status_por_codigo('EM_ANALISE') or obter_status_por_nome('Em Análise') or obter_status_por_nome('Em Analise')


def _resolver_setor_sac():
    return resolver_setor_por_codigo('SAC') or obter_setor_por_nome('SAC')


def _resolver_acao_sac_pedido_retorno():
    return resolver_acao_por_codigo('AGUARDANDO_PEDIDO_ENTRADA_RETORNO') or resolver_acao_por_codigo('EMISSAO_DO_PEDIDO_DE_ENTRADA_RETORNO')


def _resolver_acao_sac_analise_ocorrido():
    return resolver_acao_por_codigo('ANALISE_OCORRIDO_SAC')


def resolver_fluxo_fixo_licitacao(sac):
    return _resolver_fluxo_fixo_licitacao_service(sac)


def extrair_dados_analise_licitacao(sac):
    return _extrair_dados_analise_licitacao_service(sac)


def montar_contexto_analise_licitacao(sac, dados_base=None):
    return _montar_contexto_analise_licitacao_service(sac, dados_base=dados_base)
