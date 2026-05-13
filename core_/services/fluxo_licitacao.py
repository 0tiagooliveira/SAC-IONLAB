from __future__ import annotations

from decimal import Decimal, InvalidOperation
import unicodedata

from core.models import AcaoEmEspera, Setor, StatusSAC
from core.services.regras_sac import resolver_acao_por_codigo, resolver_setor_por_codigo, resolver_status_por_codigo


def _texto_normalizado_licitacao(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(texto.strip().lower().split())


def _resolver_status_em_analise():
    return (
        resolver_status_por_codigo('EM_ANALISE')
        or resolver_status_por_codigo('EM ANALISE')
        or resolver_status_por_codigo('ANALISE')
        or StatusSAC.objects.filter(nome__iexact='Em Análise', ativo=True).first()
        or StatusSAC.objects.filter(nome__iexact='Em Analise', ativo=True).first()
    )


def _resolver_setor_sac():
    return resolver_setor_por_codigo('SAC') or Setor.objects.filter(nome__iexact='SAC', ativo=True).first()


def _resolver_acao_sac_analise_ocorrido():
    return (
        resolver_acao_por_codigo('ANALISE_OCORRIDO_SAC')
        or AcaoEmEspera.objects.filter(nome__iexact='Análise do Ocorrido – SAC', ativo=True).select_related('setor_destino').first()
        or AcaoEmEspera.objects.filter(nome__iexact='Análise do Ocorrido - SAC', ativo=True).select_related('setor_destino').first()
        or AcaoEmEspera.objects.filter(nome__iexact='Analise do Ocorrido – SAC', ativo=True).select_related('setor_destino').first()
        or AcaoEmEspera.objects.filter(nome__iexact='Analise do Ocorrido - SAC', ativo=True).select_related('setor_destino').first()
        or next((
            obj for obj in AcaoEmEspera.objects.filter(ativo=True).select_related('setor_destino')
            if 'analise do ocorrido' in _texto_normalizado_licitacao(obj.nome) and 'sac' in _texto_normalizado_licitacao(obj.nome)
        ), None)
    )


def _resolver_acao_sac_pedido_retorno():
    return (
        resolver_acao_por_codigo('AGUARDANDO_PEDIDO_ENTRADA_RETORNO')
        or resolver_acao_por_codigo('EMISSAO_DO_PEDIDO_DE_ENTRADA_RETORNO')
        or AcaoEmEspera.objects.filter(nome__iexact='Aguardando Emissão do Pedido (Entrada/Retorno)', ativo=True).select_related('setor_destino').first()
        or AcaoEmEspera.objects.filter(nome__iexact='Aguardando Emissao do Pedido (Entrada/Retorno)', ativo=True).select_related('setor_destino').first()
        or AcaoEmEspera.objects.filter(nome__iexact='Aguardando Emissão do Pedido de Entrada/Retorno', ativo=True).select_related('setor_destino').first()
        or AcaoEmEspera.objects.filter(nome__iexact='Aguardando Emissao do Pedido de Entrada/Retorno', ativo=True).select_related('setor_destino').first()
        or next((
            obj for obj in AcaoEmEspera.objects.filter(ativo=True).select_related('setor_destino')
            if 'aguardando emissao' in _texto_normalizado_licitacao(obj.nome)
            and 'pedido' in _texto_normalizado_licitacao(obj.nome)
            and 'entrada retorno' in _texto_normalizado_licitacao(obj.nome)
        ), None)
    )


def _itens_tipo_ocorrencia_licitacao(sac):
    itens = list(sac.itens_sac.select_related('tipo_ocorrencia').all()) if sac else []
    nomes = [_texto_normalizado_licitacao(getattr(getattr(i, 'tipo_ocorrencia', None), 'nome', '')) for i in itens]
    return itens, nomes


def _valor_unitario_item_nf(item_nf):
    if not item_nf:
        return Decimal('0')
    for attr in ('valor_unitario', 'preco_unitario', 'vlr_unitario', 'valor'):
        valor = getattr(item_nf, attr, None)
        if valor not in (None, ''):
            try:
                return Decimal(str(valor))
            except (InvalidOperation, TypeError, ValueError):
                continue
    quantidade = getattr(item_nf, 'quantidade', None) or 0
    total = getattr(item_nf, 'valor_total', None) or getattr(item_nf, 'valor_total_item', None) or 0
    try:
        quantidade = Decimal(str(quantidade))
        total = Decimal(str(total))
    except Exception:
        return Decimal('0')
    if quantidade and quantidade > 0:
        return total / quantidade
    return Decimal('0')


def _formatar_decimal_sem_zeros(valor):
    if valor in (None, ''):
        return ''
    try:
        decimal_valor = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return str(valor)
    texto = format(decimal_valor.normalize(), 'f')
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return texto


def _parse_decimal_licitacao(valor):
    texto = str(valor or '').strip()
    if not texto:
        return Decimal('0')
    texto = texto.replace('R$', '').replace(' ', '')
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'):
            texto = texto.replace('.', '').replace(',', '.')
        else:
            texto = texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _formatar_decimal_licitacao(valor):
    try:
        decimal_valor = Decimal(str(valor or 0)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        decimal_valor = Decimal('0.00')
    texto = f"{decimal_valor:,.2f}"
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def resolver_fluxo_fixo_licitacao(sac):
    _, nomes_ocorrencia = _itens_tipo_ocorrencia_licitacao(sac)
    status_em_analise = _resolver_status_em_analise()
    setor_sac = _resolver_setor_sac()
    if any(nome in {'pedido enviado em duplicidade licitacao', 'pedido enviado em duplicidade (licitacao)'} or ('pedido enviado em duplicidade' in nome and 'licitacao' in nome) for nome in nomes_ocorrencia):
        return {'status': status_em_analise, 'acao': _resolver_acao_sac_pedido_retorno(), 'setor': setor_sac, 'motivo': 'duplicidade_licitacao'}
    if any(nome in {'itens equipamentos em desacordo com edital empenho', 'itens/equipamentos em desacordo com edital/empenho'} or ('desacordo' in nome and 'edital' in nome and 'empenho' in nome) for nome in nomes_ocorrencia):
        return {'status': status_em_analise, 'acao': _resolver_acao_sac_analise_ocorrido(), 'setor': setor_sac, 'motivo': 'desacordo_edital'}
    return None


def extrair_dados_analise_licitacao(sac):
    dados = {}
    if not sac:
        return dados
    historico = sac.historicos.filter(acao_executada='Análise de licitação registrada').order_by('-data_evento', '-id').first()
    if not historico or not historico.observacao:
        return dados
    mapa = {
        'tipo de produto:': 'tipo_produto',
        'usuário que classificou o edital:': 'usuario_classificou_edital',
        'usuario que classificou o edital:': 'usuario_classificou_edital',
        'qual ponto divergiu:': 'qual_ponto_divergiu',
        'teve erro de classificação:': 'teve_erro_classificacao',
        'teve erro de classificacao:': 'teve_erro_classificacao',
        'edital estava claro/objetivo:': 'edital_estava_claro',
        'justificativa:': 'justificativa',
        'temos uma referência correta pra atender:': 'tem_referencia_correta',
        'temos uma referencia correta pra atender:': 'tem_referencia_correta',
        'referência correta:': 'referencia_correta',
        'referencia correta:': 'referencia_correta',
        'valor da referência correta:': 'valor_referencia_correta',
        'valor da referencia correta:': 'valor_referencia_correta',
        'marca alternativa:': 'marca_alternativa',
        'valor marca alternativa:': 'valor_marca_alternativa',
        'nome do usuário que gerou o pedido:': 'nome_usuario_gerou_pedido',
        'nome do usuario que gerou o pedido:': 'nome_usuario_gerou_pedido',
        'nome do usuário que fez a conferência:': 'nome_usuario_fez_conferencia',
        'nome do usuario que fez a conferencia:': 'nome_usuario_fez_conferencia',
        'justificativa do erro:': 'justificativa_erro',
    }
    for linha in str(historico.observacao).splitlines():
        linha_limpa = linha.strip()
        if not linha_limpa:
            continue
        chave = _texto_normalizado_licitacao(linha_limpa.split(':', 1)[0] + ':')
        for prefixo, destino in mapa.items():
            if chave == _texto_normalizado_licitacao(prefixo):
                dados[destino] = linha_limpa.split(':', 1)[1].strip() if ':' in linha_limpa else ''
                break
    return dados


def montar_contexto_analise_licitacao(sac, dados_base=None):
    dados_base = dict(dados_base or {})
    itens, _ = _itens_tipo_ocorrencia_licitacao(sac)
    item_relevante = itens[0] if itens else None
    flow = resolver_fluxo_fixo_licitacao(sac) or {}
    valor_unitario = _valor_unitario_item_nf(getattr(item_relevante, 'item_nota_fiscal', None))
    quantidade = sum(Decimal(str(getattr(i, 'quantidade_com_problema', 0) or 0)) for i in itens) if itens else Decimal('0')
    valor_total = valor_unitario * quantidade
    flow_case = ''
    if flow.get('motivo') == 'duplicidade_licitacao':
        flow_case = 'pedido_duplicidade'
    elif flow.get('motivo') == 'desacordo_edital':
        flow_case = 'desacordo_edital'
    ctx = {
        'flow_case': flow_case,
        'tipo_produto': dados_base.get('tipo_produto', ''),
        'valor_unitario_vendido': _formatar_decimal_licitacao(valor_unitario),
        'quantidade_com_problema': _formatar_decimal_sem_zeros(quantidade),
        'valor_total_com_problema': _formatar_decimal_licitacao(valor_total),
        'proximo_status_nome': getattr(flow.get('status'), 'nome', 'Em Análise') if flow else 'Em Análise',
        'proximo_setor_nome': getattr(flow.get('setor'), 'nome', 'SAC') if flow else 'SAC',
        'proxima_acao_nome': getattr(flow.get('acao'), 'nome', '-') if flow else '-',
    }
    for key in ['usuario_classificou_edital', 'qual_ponto_divergiu', 'teve_erro_classificacao', 'edital_estava_claro', 'justificativa', 'tem_referencia_correta', 'referencia_correta', 'valor_referencia_correta', 'marca_alternativa', 'valor_marca_alternativa', 'nome_usuario_gerou_pedido', 'nome_usuario_fez_conferencia', 'justificativa_erro']:
        ctx[key] = dados_base.get(key, '')
    base_valor = _parse_decimal_licitacao(ctx['valor_unitario_vendido'])
    valor_ref = _parse_decimal_licitacao(ctx.get('valor_referencia_correta'))
    diff_ref = valor_ref - base_valor
    ctx['diferenca_referencia'] = _formatar_decimal_licitacao(diff_ref) if ctx.get('valor_referencia_correta') else ''
    ctx['diferenca_referencia_positiva'] = diff_ref > 0
    valor_alt = _parse_decimal_licitacao(ctx.get('valor_marca_alternativa'))
    diff_alt = valor_alt - base_valor
    ctx['diferenca_marca_alternativa'] = _formatar_decimal_licitacao(diff_alt) if ctx.get('valor_marca_alternativa') else ''
    ctx['diferenca_marca_alternativa_positiva'] = diff_alt > 0
    return ctx


__all__ = [
    'resolver_fluxo_fixo_licitacao',
    'extrair_dados_analise_licitacao',
    'montar_contexto_analise_licitacao',
]
