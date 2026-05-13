from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

from core.models import AcaoEmEspera, Setor, StatusSAC


def normalizar_nome(valor: object) -> str:
    texto = str(valor or '').strip().lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('&', ' e ')
    texto = re.sub(r'[^a-z0-9]+', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def normalizar_codigo(valor: object) -> str:
    texto = normalizar_nome(valor)
    return texto.replace(' ', '_').upper()


SETOR_ALIASES = {
    'SAC': {'sac', 'gestao do sac'},
    'COMERCIAL': {'comercial', 'gestao comercial'},
    'ASSESSORIA': {'assessoria cientifica'},
    'LOGISTICA': {'logistica', 'gestao logistica'},
    'DIRETORIA': {'diretoria'},
    'LICITACAO': {'licitacao'},
    'ASSISTENCIA_TECNICA': {'assistencia tecnica'},
    'ARQUIVO': {'arquivo'},
}

STATUS_ALIASES = {
    'CONCLUIDO': {'concluido', 'encerrado', 'finalizado'},
    'CANCELADO': {'cancelado', 'cancelada', 'cancelado definitivamente'},
    'EM_ANALISE': {'em analise'},
    'GESTAO_SAC': {'gestao do sac'},
    'GESTAO_COMERCIAL': {'gestao comercial'},
    'EMISSAO_PEDIDO_DE_ENTRADA_RETORNO': {
        'emissao pedido de entrada retorno',
        'emissao do pedido de entrada retorno',
        'emissao pedido entrada retorno',
        'emissao do pedido entrada retorno',
        'emitindo pedido de entrada retorno',
        'emitindo pedido entrada retorno',
    },
}

ACAO_ALIASES = {
    'ANALISE_OCORRIDO_SAC': {'analise do ocorrido sac'},
    'ANALISE_OCORRIDO': {'analise do ocorrido'},
    'AGUARDANDO_PEDIDO_ENTRADA_RETORNO': {
        'aguardando emissao do pedido entrada retorno',
        'aguardando emissao do pedido de entrada retorno',
        'aguardando emissao do pedido entrada retorno',
        'aguardando emissao do pedido de entrada retorno',
    },
    'EMISSAO_DO_PEDIDO_DE_ENTRADA_RETORNO': {
        'emissao do pedido de entrada retorno',
        'emissao pedido de entrada retorno',
        'emissao do pedido entrada retorno',
        'emissao pedido entrada retorno',
    },
    'AGUARDANDO_EMISSAO_NF': {'aguardando emissao da nota fiscal'},
    'AGUARDANDO_COLETA_CLIENTE': {'aguardando coleta no cliente'},
    'TRANSITO_IONLAB': {'em transito com destino a ionlab', 'transito para ionlab'},
    'AGUARDANDO_DEVOLUCAO_CLIENTE': {'aguardando devolucao ao cliente'},
    'TRANSITO_CLIENTE': {'em transito com destino ao cliente', 'transito para o cliente'},
    'APROVACAO_DESCONTO': {'aguardando aprovacao de desconto'},
}

ROTA_LISTA_POR_SETOR = {
    'SAC': '/sac/gestao/',
    'COMERCIAL': '/sac/analise-comercial/',
    'ASSESSORIA': '/sac/assessoria-cientifica/',
    'LOGISTICA': '/sac/gestao-logistica/',
    'DIRETORIA': '/sac/diretoria/',
    'LICITACAO': '/sac/gestao-licitacao/',
    'ASSISTENCIA_TECNICA': '/sac/assistencia-tecnica/',
    'ARQUIVO': '/sac/gestao/',
}


def _extrair_nome_codigo(obj: object) -> tuple[str, str]:
    if obj is None:
        return '', ''
    if isinstance(obj, str):
        return obj, obj
    nome = getattr(obj, 'nome', '') or getattr(obj, 'descricao', '') or str(obj)
    codigo = getattr(obj, 'codigo', '') or ''
    return str(nome or ''), str(codigo or '')


def _codigo_por_alias(obj: object, mapa: dict[str, set[str]]) -> str:
    nome, codigo = _extrair_nome_codigo(obj)
    codigo_norm = normalizar_codigo(codigo)
    if codigo_norm in mapa:
        return codigo_norm
    nome_norm = normalizar_nome(nome)
    for codigo_mapa, aliases in mapa.items():
        if nome_norm in aliases:
            return codigo_mapa
    return codigo_norm or normalizar_codigo(nome)


def codigo_setor(setor_ou_nome: object) -> str:
    return _codigo_por_alias(setor_ou_nome, SETOR_ALIASES)


def codigo_status(status_ou_nome: object) -> str:
    return _codigo_por_alias(status_ou_nome, STATUS_ALIASES)


def codigo_acao(acao_ou_nome: object) -> str:
    return _codigo_por_alias(acao_ou_nome, ACAO_ALIASES)


def _eh_codigo(obj: object, codigo: str, func) -> bool:
    return func(obj) == codigo


def eh_setor_sac(obj: object) -> bool:
    return _eh_codigo(obj, 'SAC', codigo_setor)


def eh_setor_comercial(obj: object) -> bool:
    return _eh_codigo(obj, 'COMERCIAL', codigo_setor)


def eh_setor_assessoria(obj: object) -> bool:
    return _eh_codigo(obj, 'ASSESSORIA', codigo_setor)


def eh_setor_logistica(obj: object) -> bool:
    return _eh_codigo(obj, 'LOGISTICA', codigo_setor)


def eh_setor_diretoria(obj: object) -> bool:
    return _eh_codigo(obj, 'DIRETORIA', codigo_setor)


def eh_setor_licitacao(obj: object) -> bool:
    return _eh_codigo(obj, 'LICITACAO', codigo_setor)


def eh_setor_assistencia_tecnica(obj: object) -> bool:
    return _eh_codigo(obj, 'ASSISTENCIA_TECNICA', codigo_setor)


def eh_setor_arquivo(obj: object) -> bool:
    return _eh_codigo(obj, 'ARQUIVO', codigo_setor)



def eh_status_concluido(obj: object) -> bool:
    return _eh_codigo(obj, 'CONCLUIDO', codigo_status)


def eh_status_cancelado(obj: object) -> bool:
    return _eh_codigo(obj, 'CANCELADO', codigo_status)


def eh_status_em_analise(obj: object) -> bool:
    return _eh_codigo(obj, 'EM_ANALISE', codigo_status)


def eh_acao_analise_ocorrido(obj: object) -> bool:
    return codigo_acao(obj) in {'ANALISE_OCORRIDO', 'ANALISE_OCORRIDO_SAC'}


def eh_acao_emissao_pedido_retorno(obj: object) -> bool:
    return codigo_acao(obj) in {'EMISSAO_DO_PEDIDO_DE_ENTRADA_RETORNO', 'AGUARDANDO_PEDIDO_ENTRADA_RETORNO'}


def eh_acao_aguardando_emissao_nf(obj: object) -> bool:
    return _eh_codigo(obj, 'AGUARDANDO_EMISSAO_NF', codigo_acao)


def eh_acao_aguardando_coleta_cliente(obj: object) -> bool:
    return _eh_codigo(obj, 'AGUARDANDO_COLETA_CLIENTE', codigo_acao)


def eh_acao_transito_ionlab(obj: object) -> bool:
    return _eh_codigo(obj, 'TRANSITO_IONLAB', codigo_acao)


def eh_acao_aguardando_devolucao_cliente(obj: object) -> bool:
    return _eh_codigo(obj, 'AGUARDANDO_DEVOLUCAO_CLIENTE', codigo_acao)


def eh_acao_transito_cliente(obj: object) -> bool:
    return _eh_codigo(obj, 'TRANSITO_CLIENTE', codigo_acao)


def aliases_setor(codigo: str) -> set[str]:
    return set(SETOR_ALIASES.get(normalizar_codigo(codigo), set()))


def aliases_status(codigo: str) -> set[str]:
    return set(STATUS_ALIASES.get(normalizar_codigo(codigo), set()))


def aliases_acao(codigo: str) -> set[str]:
    return set(ACAO_ALIASES.get(normalizar_codigo(codigo), set()))


def _resolver_por_codigo(modelo, codigo: str, aliases: Iterable[str]):
    codigo_norm = normalizar_codigo(codigo)
    alias_norms = {normalizar_codigo(alias) for alias in aliases if alias}
    if codigo_norm:
        alias_norms.add(codigo_norm)

    if hasattr(modelo, 'codigo') and codigo_norm:
        instancia = modelo.objects.filter(codigo__iexact=codigo_norm).first()
        if instancia:
            return instancia

    candidatos = list(modelo.objects.all())
    mapa = {}
    for obj in candidatos:
        nome = getattr(obj, 'nome', '') or getattr(obj, 'descricao', '') or ''
        codigo_obj = getattr(obj, 'codigo', '') or ''
        for chave in {normalizar_codigo(nome), normalizar_codigo(codigo_obj)}:
            if chave:
                mapa.setdefault(chave, obj)

    for chave in alias_norms:
        if chave in mapa:
            return mapa[chave]

    # fallback por proximidade normalizada para pequenas variações como "do/de"
    for chave in alias_norms:
        chave_simples = chave.replace('_DO_', '_').replace('_DE_', '_')
        for base, obj in mapa.items():
            base_simples = base.replace('_DO_', '_').replace('_DE_', '_')
            if chave_simples == base_simples or chave_simples in base_simples or base_simples in chave_simples:
                return obj
    return None


def resolver_setor_por_codigo(codigo: str) -> Optional[Setor]:
    return _resolver_por_codigo(Setor, codigo, aliases_setor(codigo))


def resolver_status_por_codigo(codigo: str) -> Optional[StatusSAC]:
    return _resolver_por_codigo(StatusSAC, codigo, aliases_status(codigo))


def resolver_acao_por_codigo(codigo: str) -> Optional[AcaoEmEspera]:
    return _resolver_por_codigo(AcaoEmEspera, codigo, aliases_acao(codigo))


def rota_lista_por_codigo_setor(codigo: object) -> str:
    codigo_norm = codigo_setor(codigo)
    return ROTA_LISTA_POR_SETOR.get(codigo_norm, '/sac/gestao/')


def rota_detalhe_por_codigo_setor(codigo: object, sac_id: Optional[int]) -> str:
    rota_lista = rota_lista_por_codigo_setor(codigo)
    if not sac_id:
        return rota_lista
    codigo_norm = codigo_setor(codigo)
    if codigo_norm == 'ASSESSORIA':
        return f'/sac/{sac_id}/analise-tecnica/'
    return f'{rota_lista}?sac={sac_id}'


__all__ = [name for name in globals() if name.startswith(('normalizar_', 'codigo_', 'eh_', 'aliases_', 'resolver_', 'rota_')) or name.endswith('_ALIASES')]
