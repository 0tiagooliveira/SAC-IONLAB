from __future__ import annotations

from datetime import date, datetime


def _valor_texto(valor, padrao='-'):
    if valor is None:
        return padrao
    texto = str(valor).strip()
    return texto if texto else padrao


def _formatar_data(valor):
    if not valor:
        return '-'
    try:
        if isinstance(valor, datetime):
            valor = valor.date()
        if isinstance(valor, date):
            return valor.strftime('%d/%m/%Y')
    except Exception:
        pass
    return _valor_texto(valor)


def _formatar_numero_sac(sac):
    numero = _valor_texto(getattr(sac, 'numero', None), '')
    if not numero:
        return '-'
    if '/' in numero:
        return numero
    ano = _valor_texto(getattr(sac, 'ano', None), '')
    try:
        numero = str(int(numero)).zfill(3)
    except Exception:
        pass
    return f'{numero}/{ano}' if ano else numero


def formatar_tempo_uso_oficial(dias):
    try:
        if dias is None or dias == '':
            return 'Não calculado'
        dias = int(dias)
    except (TypeError, ValueError):
        return 'Não calculado'
    if dias < 0:
        dias = 0
    meses = dias // 30
    resto = dias % 30
    partes = []
    if meses:
        partes.append(f'{meses} mês' + ('es' if meses != 1 else ''))
    if resto or not partes:
        partes.append(f'{resto} dia' + ('s' if resto != 1 else ''))
    return ' e '.join(partes)


def montar_dados_sac_oficiais(sac):
    """Monta o bloco oficial de Dados do SAC para uso padronizado nas telas.

    Não recalcula tempo de uso. Apenas exibe os campos oficiais já gravados no SAC.
    Usa getattr para ser compatível com bancos ainda em migração e evitar quebrar telas antigas.
    """
    if not sac:
        return {}
    nf = getattr(sac, 'nota_fiscal', None)
    empresa = getattr(sac, 'empresa', None)
    cliente = getattr(sac, 'cliente', None)
    status = getattr(sac, 'status_atual', None)
    setor = getattr(sac, 'setor_atual', None)
    acao = getattr(sac, 'acao_em_espera', None)
    numero_nf = getattr(nf, 'numero_nf', None) or getattr(nf, 'numero', None) or '-'
    data_nf = getattr(sac, 'data_emissao_nf', None) or getattr(nf, 'data_emissao', None)
    tempo_uso_dias = getattr(sac, 'tempo_uso_dias', None)
    return {
        'numero_sac': _formatar_numero_sac(sac),
        'status_atual': _valor_texto(getattr(status, 'nome', None)),
        'empresa': _valor_texto(getattr(empresa, 'razao_social', None) or getattr(empresa, 'nome', None)),
        'setor_atual': _valor_texto(getattr(setor, 'nome', None)),
        'cliente': _valor_texto(getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None)),
        'nota_fiscal': _valor_texto(numero_nf),
        'data_emissao_nf': _formatar_data(data_nf),
        'numero_nf_revenda': _valor_texto(getattr(sac, 'numero_nf_revenda', None)),
        'data_emissao_nf_revenda': _formatar_data(getattr(sac, 'data_emissao_nf_revenda', None)),
        'tempo_uso_dias': tempo_uso_dias,
        'tempo_uso_formatado': formatar_tempo_uso_oficial(tempo_uso_dias),
        'acao_em_espera_atual': _valor_texto(getattr(acao, 'nome', None)),
        'titulo': _valor_texto(getattr(sac, 'titulo', None)),
    }
