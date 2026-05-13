from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

VALORES_VAZIOS = {'', '-', '---', 'none', 'null', 'nan', 'não informado', 'nao informado', 'não se aplica', 'nao se aplica', 'n/a', 'sem informação', 'sem informacao', '[]', '{}'}
TITULOS_TECNICOS_IGNORADOS = {'histórico padronizado da gestão comercial', 'historico padronizado da gestao comercial'}


def _valor_texto(valor):
    if valor in (None, ''):
        return '-'
    return str(valor).strip() or '-'


def _normalizar(valor):
    return str(valor or '').strip().lower()


def _eh_valor_util(valor):
    texto = str(valor or '').strip()
    return bool(texto) and _normalizar(texto) not in VALORES_VAZIOS


def _nome_obj(obj):
    if obj is None:
        return '-'
    nome = getattr(obj, 'nome', None)
    return (str(nome).strip() if nome else str(obj).strip()) or '-'


def _nome_usuario(usuario):
    if usuario is None:
        return '-'
    try:
        return (usuario.get_full_name() or '').strip() or getattr(usuario, 'username', None) or str(usuario)
    except Exception:
        return getattr(usuario, 'username', None) or str(usuario)


def compor_observacao_padronizada(*pares, incluir_bloco_tecnico=True, titulo=None):
    linhas = []
    if titulo:
        linhas.append(str(titulo).strip())
    for chave, valor in pares:
        if chave:
            linhas.append(f'{str(chave).strip()}: {_valor_texto(valor)}')
    if incluir_bloco_tecnico:
        linhas.append('')
        linhas.append('[PADRAO_HISTORICO=1]')
    return '\n'.join(linhas).strip()


def quebrar_observacao_em_campos(observacao: str):
    campos = OrderedDict()
    linhas_livres = []
    for linha in str(observacao or '').splitlines():
        linha = (linha or '').strip()
        if not linha or (linha.startswith('[') and linha.endswith(']')):
            continue
        if _normalizar(linha) in TITULOS_TECNICOS_IGNORADOS:
            continue
        if ':' not in linha:
            if _eh_valor_util(linha):
                linhas_livres.append(linha)
            continue
        chave, valor = linha.split(':', 1)
        chave = (chave or '').strip()
        valor = (valor or '').strip()
        if chave and _eh_valor_util(valor) and chave not in campos:
            campos[chave] = valor
    return campos, linhas_livres


def montar_historico_detalhado(historicos: Iterable):
    itens = []
    for hist in historicos or []:
        campos, linhas_livres = quebrar_observacao_em_campos(getattr(hist, 'observacao', ''))
        setor_origem = getattr(hist, 'setor_origem', None)
        setor_destino = getattr(hist, 'setor_destino', None)
        setor_responsavel = _nome_obj(setor_origem)
        if setor_responsavel == '-':
            setor_responsavel = _nome_obj(setor_destino)
        if setor_responsavel == '-':
            setor_responsavel = 'Sistema / SAC'
        status_anterior = _nome_obj(getattr(hist, 'status_anterior', None))
        status_novo = _nome_obj(getattr(hist, 'status_novo', None))
        acao_executada = getattr(hist, 'acao_executada', None) or 'Registro'
        data_evento = getattr(hist, 'data_evento', None)
        resumo = []
        if status_anterior != '-' or status_novo != '-':
            resumo.append({'rotulo': 'Status', 'valor': f'{status_anterior} → {status_novo}'})
        if _nome_obj(setor_origem) != '-' or _nome_obj(setor_destino) != '-':
            resumo.append({'rotulo': 'Setor', 'valor': f'{_nome_obj(setor_origem)} → {_nome_obj(setor_destino)}'})
        if _eh_valor_util(acao_executada):
            resumo.append({'rotulo': 'Ação executada', 'valor': acao_executada})
        itens.append({
            'obj': hist,
            'setor_responsavel': setor_responsavel,
            'usuario_nome': _nome_usuario(getattr(hist, 'usuario', None)),
            'status_anterior_nome': status_anterior,
            'status_novo_nome': status_novo,
            'setor_origem_nome': _nome_obj(setor_origem),
            'setor_destino_nome': _nome_obj(setor_destino),
            'acao_executada': acao_executada,
            'data_evento_formatada': data_evento.strftime('%d/%m/%Y %H:%M') if data_evento else '-',
            'campos': campos,
            'linhas_livres': linhas_livres,
            'resumo_movimentacao': resumo,
            'tem_dados': bool(campos or linhas_livres),
            'arquivo': getattr(hist, 'arquivo', None),
            'observacao_texto': getattr(hist, 'observacao', '') or '',
        })
    return itens
