from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from core.models import ItemNotaFiscal, NotaFiscal, PecaTabelaPreco, SAC, SACItem, SacHistorico
from core.services.sac_visual import formatar_horas_dd_hh_mm, formatar_numero_sac, resumo_tempo_setor
from core.services.sla_inteligente import calcular_sla_sac


SLA_VERDE_HORAS = int(getattr(settings, "SLA_ALERTA_AMARELO_HORAS", 12))
SLA_AMARELO_HORAS = int(getattr(settings, "SLA_ALERTA_VERMELHO_HORAS", 24))
CLIENTES_EXCLUIDOS_VENDAS_EQUIPAMENTOS = {
    'IONLAB': {'791', '14490', '34822', '24351', '14498', '792'},
    'CIORBRASIL': {'918', '9482', '16842', '887', '10784', '34854'},
}


def classificar_sla(delta):
    total_horas = max(delta.total_seconds(), 0) / 3600
    if total_horas < SLA_VERDE_HORAS:
        return 'verde', 'Dentro do SLA'
    if total_horas < SLA_AMARELO_HORAS:
        return 'amarelo', 'Próximo do vencimento'
    return 'vermelho', 'Vencido'


def _nome_setor(sac):
    return getattr(getattr(sac, 'setor_atual', None), 'nome', None) or 'Sem setor'


def _nome_status(sac):
    return getattr(getattr(sac, 'status_atual', None), 'nome', None) or getattr(sac, 'status_inicial', None) or '-'


def _nome_cliente(sac):
    cliente = getattr(sac, 'cliente', None)
    return getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None) or '-'


def _formatar_horas(horas):
    return formatar_horas_dd_hh_mm(horas)


def _percentual(parte, total):
    if not total:
        return 0
    return round((parte / total) * 100, 1)


def _normalizar_texto_filtro(valor):
    return str(valor or '').strip().upper()


def _origem_equipamento_compativel(origem, filtro):
    filtro = _normalizar_texto_filtro(filtro)
    origem = _normalizar_texto_filtro(origem)
    if not filtro or filtro == 'GERAL':
        return True
    if filtro == 'IMPORTADOS':
        return origem == 'IMPORTADO'
    if filtro == 'FABRICADOS':
        return origem in {'FABRICADO BR', 'FABRICADO', 'NACIONAL'}
    return True


def _voltagem_equipamento_compativel(voltagem, filtro):
    filtro = _normalizar_texto_filtro(filtro)
    voltagem = _normalizar_texto_filtro(voltagem)
    if not filtro or filtro == 'TODAS':
        return True
    if filtro == '110V':
        return '110' in voltagem
    if filtro == '220V':
        return '220' in voltagem
    if filtro == 'BI':
        return voltagem in {'BI', 'BIV', 'BIVOLT', '110/220V', '110V/220V', '127/220V', '127V/220V'}
    return True


def _item_nf_compativel_com_filtros(item_nf, origem_filtro=None, voltagem_filtro=None):
    return (
        _origem_equipamento_compativel(getattr(item_nf, 'origem', ''), origem_filtro)
        and _voltagem_equipamento_compativel(getattr(item_nf, 'voltagem', ''), voltagem_filtro)
    )


def _aplicar_filtros_equipamento_qs(qs, prefixo='', origem_filtro=None, voltagem_filtro=None):
    origem_filtro = _normalizar_texto_filtro(origem_filtro)
    voltagem_filtro = _normalizar_texto_filtro(voltagem_filtro)
    origem_campo = f'{prefixo}origem'
    voltagem_campo = f'{prefixo}voltagem'
    if origem_filtro == 'IMPORTADOS':
        qs = qs.filter(**{f'{origem_campo}__iexact': 'Importado'})
    elif origem_filtro == 'FABRICADOS':
        qs = qs.filter(**{f'{origem_campo}__iexact': 'Fabricado BR'})
    if voltagem_filtro == '110V':
        qs = qs.filter(**{f'{voltagem_campo}__icontains': '110'})
    elif voltagem_filtro == '220V':
        qs = qs.filter(**{f'{voltagem_campo}__icontains': '220'})
    elif voltagem_filtro == 'BI':
        qs = qs.filter(**{f'{voltagem_campo}__in': ['BI', 'BIV', 'Biv', 'Bivolt', 'BIVOLT']})
    return qs


def _periodo_mes_atual(agora):
    inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return inicio, agora


def _inicio_ano(agora):
    return agora.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _periodo_ano_anterior(agora):
    inicio = agora.replace(year=agora.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    fim = agora.replace(year=agora.year - 1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
    return inicio, fim


def _contar_sacs_unicos_por_cliente(inicio, fim, empresa_id=None):
    qs = (
        SAC.objects
        .select_related('cliente')
        .filter(data_abertura__gte=inicio, data_abertura__lte=fim)
        .exclude(cliente__isnull=True)
    )
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    contador = defaultdict(set)
    nomes = {}
    for sac in qs:
        if not sac.cliente_id:
            continue
        contador[sac.cliente_id].add((sac.empresa_id, sac.numero or sac.id))
        nomes[sac.cliente_id] = _nome_cliente(sac)
    return {cliente_id: len(chaves) for cliente_id, chaves in contador.items()}, nomes


def _chart_clientes_sacs(inicio, fim, empresa_id=None, limite=10):
    totais, nomes = _contar_sacs_unicos_por_cliente(inicio, fim, empresa_id=empresa_id)
    top = sorted(totais.items(), key=lambda item: (-item[1], nomes.get(item[0], '')))[:limite]
    return _chart(
        [nomes.get(cliente_id, '-') for cliente_id, _ in top],
        [total for _, total in top],
        ['#149b7e'] * len(top),
    )


def _contar_notas_unicas_por_cliente(cliente_ids, inicio, fim, empresa_id=None):
    notas_qs = NotaFiscal.objects.filter(
        cliente_id__in=cliente_ids,
        data_emissao__gte=inicio.date(),
        data_emissao__lte=fim.date(),
    )
    if empresa_id:
        notas_qs = notas_qs.filter(empresa_id=empresa_id)

    contador = defaultdict(set)
    for nota in notas_qs:
        contador[nota.cliente_id].add((nota.empresa_id, nota.numero_nf or nota.numero or nota.id))
    return {cliente_id: len(chaves) for cliente_id, chaves in contador.items()}


def _chart_vendas_x_sacs(inicio, fim, empresa_id=None, limite=10):
    notas_qs = (
        NotaFiscal.objects
        .select_related('cliente')
        .filter(data_emissao__gte=inicio.date(), data_emissao__lte=fim.date())
        .exclude(cliente__isnull=True)
    )
    if empresa_id:
        notas_qs = notas_qs.filter(empresa_id=empresa_id)

    notas_por_cliente = defaultdict(set)
    nota_ids = []
    notas_por_id = {}
    nomes = {}
    for nota in notas_qs:
        if not nota.cliente_id:
            continue
        chave_nf = (nota.empresa_id, nota.numero_nf or nota.numero or nota.id)
        notas_por_cliente[nota.cliente_id].add(chave_nf)
        nota_ids.append(nota.id)
        notas_por_id[nota.id] = nota
        nomes[nota.cliente_id] = getattr(nota.cliente, 'razao_social', None) or getattr(nota.cliente, 'nome', None) or '-'

    if not nota_ids:
        return _chart([], [], [])

    notas_com_sac_por_cliente = defaultdict(set)
    sacs_por_cliente = defaultdict(set)
    sacs_qs = SAC.objects.filter(nota_fiscal_id__in=nota_ids).exclude(nota_fiscal__cliente__isnull=True)
    for sac in sacs_qs:
        nota = notas_por_id.get(sac.nota_fiscal_id)
        if not nota or not nota.cliente_id:
            continue
        chave_nf = (nota.empresa_id, nota.numero_nf or nota.numero or nota.id)
        chave_sac = (sac.empresa_id, sac.numero or sac.id)
        notas_com_sac_por_cliente[nota.cliente_id].add(chave_nf)
        sacs_por_cliente[nota.cliente_id].add(chave_sac)

    candidatos = []
    for cliente_id in sacs_por_cliente.keys():
        total_notas = len(notas_por_cliente.get(cliente_id, set()))
        total_notas_com_sac = len(notas_com_sac_por_cliente.get(cliente_id, set()))
        total_sacs = len(sacs_por_cliente.get(cliente_id, set()))
        candidatos.append({
            'cliente_id': cliente_id,
            'notas': total_notas,
            'notas_com_sac': total_notas_com_sac,
            'sacs': total_sacs,
            'percentual': _percentual(total_notas_com_sac, total_notas),
            'nome': nomes.get(cliente_id, ''),
        })
    top_clientes = sorted(
        candidatos,
        key=lambda item: (-item['sacs'], -item['notas_com_sac'], -item['percentual'], item['nome']),
    )[:limite]

    labels = []
    values = []
    details = []
    for item in top_clientes:
        cliente_id = item['cliente_id']
        total_notas = item['notas']
        total_notas_com_sac = item['notas_com_sac']
        total_sacs = item['sacs']
        percentual = item['percentual']
        labels.append(nomes.get(cliente_id, '-'))
        values.append(percentual)
        details.append({
            'cliente': nomes.get(cliente_id, '-'),
            'sacs': total_sacs,
            'notas_com_sac': total_notas_com_sac,
            'notas': total_notas,
            'percentual': percentual,
        })
    chart = _chart(labels, values, ['#0d7f9b'] * len(labels))
    chart['details'] = details
    chart['suffix'] = '%'
    chart['value_labels'] = [
        f"{item['percentual']}% | {item['notas_com_sac']}/{item['notas']} NFs"
        for item in details
    ]
    return chart


def _rank_itens_campeoes(inicio, fim, limite=8, categoria='todos', empresa_id=None, origem_filtro=None, voltagem_filtro=None):
    qs_base = (
        SACItem.objects
        .select_related('item_nota_fiscal')
        .filter(sac__data_abertura__gte=inicio, sac__data_abertura__lte=fim)
        .exclude(item_nota_fiscal__codigo_produto__isnull=True)
        .exclude(item_nota_fiscal__codigo_produto__exact='')
    )
    if categoria == 'equipamentos':
        qs_base = qs_base.filter(tipo_rastreio='SERIAL')
        qs_base = _aplicar_filtros_equipamento_qs(
            qs_base,
            prefixo='item_nota_fiscal__',
            origem_filtro=origem_filtro,
            voltagem_filtro=voltagem_filtro,
        )
    elif categoria == 'consumiveis':
        qs_base = qs_base.exclude(tipo_rastreio='SERIAL')
    if empresa_id:
        qs_base = qs_base.filter(sac__empresa_id=empresa_id)

    acumulado = {}
    for item_sac in qs_base:
        item_nf = item_sac.item_nota_fiscal
        codigo = item_nf.codigo_produto or '-'
        descricao = item_nf.descricao_item or item_nf.item or '-'
        bucket = acumulado.setdefault(codigo, {
            'codigo': codigo,
            'descricao': descricao,
            'origem': item_nf.origem or '',
            'voltagem': item_nf.voltagem or '',
            'total': 0,
            'seriais': set(),
            'sacs': set(),
        })
        if categoria == 'equipamentos':
            serial = (item_sac.numero_rastreio or '').strip()
            if serial:
                bucket['seriais'].add(serial)
            else:
                bucket['total'] += 1
        elif categoria == 'consumiveis':
            bucket['sacs'].add((item_sac.sac.empresa_id, item_sac.sac.numero or item_sac.sac_id))
        else:
            bucket['total'] += 1

    ranking_base = []
    for item in acumulado.values():
        if categoria == 'equipamentos':
            total = len(item['seriais']) + item['total']
        elif categoria == 'consumiveis':
            total = len(item['sacs'])
        else:
            total = item['total']
        if total <= 0:
            continue
        ranking_base.append({
            'codigo': item['codigo'],
            'descricao': item['descricao'],
            'total_sacs': total,
        })
    ranking_base = sorted(ranking_base, key=lambda x: (-x['total_sacs'], x['codigo']))[:limite]

    ranking = []
    total_periodo = sum(item['total_sacs'] for item in ranking_base)
    for posicao, item in enumerate(ranking_base, start=1):
        total = item['total_sacs']
        ranking.append({
            'posicao': posicao,
            'codigo': item['codigo'],
            'descricao': item['descricao'],
            'origem': item.get('origem', ''),
            'voltagem': item.get('voltagem', ''),
            'total_sacs': total,
            'percentual': _percentual(total, total_periodo),
        })
    return ranking


def _limpar_nome_grupo_equipamento(grupo):
    nome = str(grupo or '').strip()
    nome = re.sub(r'^\s*equipamentos?\s*[-–—:/]*\s*', '', nome, flags=re.I)
    return nome.strip() or 'Sem grupo'


def _chart_grupos_equipamentos_campeoes(inicio, fim, empresa_id=None, limite=10, origem_filtro=None, voltagem_filtro=None):
    metas_por_ref = _metadados_equipamentos_por_referencia()
    if not metas_por_ref:
        return _chart([], [], [])

    itens_vendidos_ids = set()
    itens_qs = (
        ItemNotaFiscal.objects
        .select_related('nota_fiscal', 'nota_fiscal__empresa', 'nota_fiscal__cliente')
        .filter(nota_fiscal__data_emissao__gte=inicio.date(), nota_fiscal__data_emissao__lte=fim.date())
        .exclude(codigo_produto__isnull=True)
        .exclude(codigo_produto__exact='')
    )
    if empresa_id:
        itens_qs = itens_qs.filter(nota_fiscal__empresa_id=empresa_id)
    itens_qs = _aplicar_filtros_equipamento_qs(
        itens_qs,
        origem_filtro=origem_filtro,
        voltagem_filtro=voltagem_filtro,
    )

    for item_nf in itens_qs.iterator():
        meta = metas_por_ref.get(str(item_nf.codigo_produto or '').strip())
        if not meta:
            continue
        if _venda_deve_ser_desconsiderada(item_nf.nota_fiscal):
            continue
        itens_vendidos_ids.add(item_nf.id)

    if not itens_vendidos_ids:
        return _chart([], [], [])

    acumulado = defaultdict(set)
    qs_base = (
        SACItem.objects
        .select_related('sac', 'item_nota_fiscal')
        .filter(item_nota_fiscal_id__in=itens_vendidos_ids)
    )
    for item_sac in qs_base:
        meta = metas_por_ref.get(str(item_sac.item_nota_fiscal.codigo_produto or '').strip())
        if not meta:
            continue
        grupo = meta['grupo']
        acumulado[grupo].add((item_sac.sac.empresa_id, item_sac.sac.numero or item_sac.sac_id))

    top = sorted(
        ((grupo, len(sacs)) for grupo, sacs in acumulado.items()),
        key=lambda item: (-item[1], item[0]),
    )[:limite]
    return _chart(
        [grupo for grupo, _ in top],
        [total for _, total in top],
        ['#0d7f9b'] * len(top),
    )


def _venda_deve_ser_desconsiderada(nota):
    empresa_codigo = str(getattr(getattr(nota, 'empresa', None), 'codigo', '') or '').strip().upper()
    cliente_codigo = str(getattr(getattr(nota, 'cliente', None), 'codigo_interno', '') or '').strip()
    return cliente_codigo in CLIENTES_EXCLUIDOS_VENDAS_EQUIPAMENTOS.get(empresa_codigo, set())


def _metadados_equipamentos_por_referencia():
    grupos = {}
    pecas = PecaTabelaPreco.objects.exclude(referencia__isnull=True).exclude(referencia__exact='')
    for peca in pecas.iterator():
        grupo = str(peca.grupo or '').strip()
        if not grupo.upper().startswith('EQUIPAMENTO'):
            continue
        grupos[str(peca.referencia or '').strip()] = {
            'grupo': _limpar_nome_grupo_equipamento(grupo),
            'origem': peca.origem or '',
            'voltagem': peca.voltagem or '',
        }
    return grupos


def _grupos_equipamentos_por_referencia():
    return {
        referencia: meta['grupo']
        for referencia, meta in _metadados_equipamentos_por_referencia().items()
    }


def _chart_percentual_sac_por_grupo_equipamento(inicio, fim, empresa_id=None, limite=10, origem_filtro=None, voltagem_filtro=None):
    metas_por_ref = _metadados_equipamentos_por_referencia()
    if not metas_por_ref:
        return _chart([], [], [])

    vendidos = defaultdict(float)
    notas_validas = set()
    itens_vendidos_ids = set()
    itens_qs = (
        ItemNotaFiscal.objects
        .select_related('nota_fiscal', 'nota_fiscal__empresa', 'nota_fiscal__cliente')
        .filter(nota_fiscal__data_emissao__gte=inicio.date(), nota_fiscal__data_emissao__lte=fim.date())
        .exclude(codigo_produto__isnull=True)
        .exclude(codigo_produto__exact='')
    )
    if empresa_id:
        itens_qs = itens_qs.filter(nota_fiscal__empresa_id=empresa_id)
    itens_qs = _aplicar_filtros_equipamento_qs(
        itens_qs,
        origem_filtro=origem_filtro,
        voltagem_filtro=voltagem_filtro,
    )

    for item_nf in itens_qs.iterator():
        meta = metas_por_ref.get(str(item_nf.codigo_produto or '').strip())
        if not meta:
            continue
        grupo = meta['grupo']
        nota = item_nf.nota_fiscal
        if _venda_deve_ser_desconsiderada(nota):
            continue
        quantidade = float(item_nf.quantidade or 0)
        if quantidade <= 0:
            continue
        vendidos[grupo] += quantidade
        notas_validas.add(nota.id)
        itens_vendidos_ids.add(item_nf.id)

    if not itens_vendidos_ids:
        return _chart([], [], [])

    sacs_com_sac = defaultdict(set)
    sac_itens_qs = (
        SACItem.objects
        .select_related('item_nota_fiscal', 'sac')
        .filter(item_nota_fiscal_id__in=itens_vendidos_ids)
    )
    for item_sac in sac_itens_qs.iterator():
        item_nf = item_sac.item_nota_fiscal
        meta = metas_por_ref.get(str(item_nf.codigo_produto or '').strip())
        if not meta:
            continue
        grupo = meta['grupo']
        sacs_com_sac[grupo].add((item_sac.sac.empresa_id, item_sac.sac.numero or item_sac.sac_id))

    candidatos = []
    for grupo, total_vendido in vendidos.items():
        total_com_sac = len(sacs_com_sac.get(grupo, set()))
        percentual = _percentual(total_com_sac, total_vendido)
        candidatos.append({
            'grupo': grupo,
            'vendidos': round(total_vendido, 1),
            'com_sac': round(total_com_sac, 1),
            'percentual': percentual,
        })

    top = sorted(candidatos, key=lambda item: item['grupo'])
    if limite:
        top = top[:limite]
    chart = _chart(
        [item['grupo'] for item in top],
        [item['percentual'] for item in top],
        ['#0d7f9b'] * len(top),
    )
    chart['details'] = top
    chart['suffix'] = '%'
    return chart


def _alinhar_charts_percentual_grupos_equipamentos(charts):
    detalhes_por_periodo = {
        periodo: {item['grupo']: item for item in chart.get('details', [])}
        for periodo, chart in charts.items()
    }
    grupos = sorted({
        grupo
        for detalhes in detalhes_por_periodo.values()
        for grupo in detalhes.keys()
    })
    alinhados = {}
    for periodo, detalhes in detalhes_por_periodo.items():
        detalhes_alinhados = []
        for grupo in grupos:
            item = detalhes.get(grupo, {
                'grupo': grupo,
                'vendidos': 0,
                'com_sac': 0,
                'percentual': 0,
            })
            detalhes_alinhados.append(item)
        alinhados[periodo] = _chart(
            grupos,
            [item['percentual'] for item in detalhes_alinhados],
            ['#0d7f9b'] * len(grupos),
        )
        alinhados[periodo]['details'] = detalhes_alinhados
        alinhados[periodo]['suffix'] = '%'
    return alinhados


def _formatar_dias_uso(dias):
    dias = int(round(float(dias or 0)))
    if dias < 30:
        return f'{dias} dia' if dias == 1 else f'{dias} dias'
    meses = dias // 30
    resto = dias % 30
    if meses < 12:
        texto = f'{meses} mês' if meses == 1 else f'{meses} meses'
        if resto:
            texto += f' - {resto} dia' if resto == 1 else f' - {resto} dias'
        return texto
    anos = meses // 12
    meses_restantes = meses % 12
    texto = f'{anos} ano' if anos == 1 else f'{anos} anos'
    if meses_restantes:
        texto += f' - {meses_restantes} mês' if meses_restantes == 1 else f' - {meses_restantes} meses'
    if resto:
        texto += f' - {resto} dia' if resto == 1 else f' - {resto} dias'
    return texto


def _data_para_date(valor):
    if not valor:
        return None
    if hasattr(valor, 'date'):
        return valor.date()
    return valor


def _charts_tempo_uso_equipamentos(empresa_id=None, origem_filtro=None, voltagem_filtro=None):
    metas_por_ref = _metadados_equipamentos_por_referencia()
    acumulado = defaultdict(list)
    qs = (
        SACItem.objects
        .select_related('sac', 'item_nota_fiscal', 'item_nota_fiscal__nota_fiscal')
        .filter(tipo_rastreio='SERIAL')
        .exclude(sac__data_abertura__isnull=True)
        .exclude(item_nota_fiscal__nota_fiscal__data_emissao__isnull=True)
    )
    if empresa_id:
        qs = qs.filter(sac__empresa_id=empresa_id)
    qs = _aplicar_filtros_equipamento_qs(
        qs,
        prefixo='item_nota_fiscal__',
        origem_filtro=origem_filtro,
        voltagem_filtro=voltagem_filtro,
    )

    for item_sac in qs.iterator():
        item_nf = item_sac.item_nota_fiscal
        referencia = str(getattr(item_nf, 'codigo_produto', '') or getattr(item_nf, 'item', '') or '').strip()
        meta = metas_por_ref.get(referencia)
        if not meta:
            continue
        data_nf = _data_para_date(getattr(getattr(item_nf, 'nota_fiscal', None), 'data_emissao', None))
        data_abertura = _data_para_date(getattr(item_sac.sac, 'data_abertura', None))
        if not data_nf or not data_abertura:
            continue
        dias = max((data_abertura - data_nf).days, 0)
        acumulado[meta['grupo']].append(dias)

    grupos = sorted(acumulado.keys())
    medias = []
    menores = []
    media_labels = []
    menor_labels = []
    details = []
    for grupo in grupos:
        valores = acumulado[grupo]
        media = round(sum(valores) / len(valores), 1) if valores else 0
        menor = min(valores) if valores else 0
        medias.append(media)
        menores.append(menor)
        media_labels.append(_formatar_dias_uso(media))
        menor_labels.append(_formatar_dias_uso(menor))
        details.append({
            'grupo': grupo,
            'media_dias': media,
            'menor_dias': menor,
            'total_sacs': len(valores),
        })

    media_chart = _chart(grupos, medias, ['#0d7f9b'] * len(grupos))
    media_chart['value_labels'] = media_labels
    media_chart['details'] = details
    menor_chart = _chart(grupos, menores, ['#145a8f'] * len(grupos))
    menor_chart['value_labels'] = menor_labels
    menor_chart['details'] = details
    return {'media': media_chart, 'menor': menor_chart}


def _filtros_equipamentos_dashboard():
    return {
        'origens': [
            {'key': 'geral', 'label': 'Geral', 'valor': 'GERAL'},
            {'key': 'importados', 'label': 'Importados', 'valor': 'IMPORTADOS'},
            {'key': 'fabricados', 'label': 'Fabricados', 'valor': 'FABRICADOS'},
        ],
        'voltagens': [
            {'key': 'todas', 'label': 'Todas as Voltagens', 'valor': 'TODAS'},
            {'key': '110v', 'label': 'Voltagem 110V', 'valor': '110V'},
            {'key': '220v', 'label': 'Voltagem 220V', 'valor': '220V'},
            {'key': 'bi', 'label': 'Voltagem BI', 'valor': 'BI'},
        ],
    }


def _montar_variantes_equipamentos(inicio_anterior, fim_anterior, inicio_corrente, fim_corrente, empresa_id=None):
    filtros = _filtros_equipamentos_dashboard()
    ranking = {}
    grupos = {}
    percentual = {}
    for origem in filtros['origens']:
        origem_key = origem['key']
        ranking[origem_key] = {}
        grupos[origem_key] = {}
        percentual[origem_key] = {}
        for voltagem in filtros['voltagens']:
            voltagem_key = voltagem['key']
            kwargs = {
                'empresa_id': empresa_id,
                'origem_filtro': origem['valor'],
                'voltagem_filtro': voltagem['valor'],
            }
            ranking[origem_key][voltagem_key] = {
                'ano_anterior': _rank_itens_campeoes(inicio_anterior, fim_anterior, categoria='equipamentos', **kwargs),
                'ano_corrente': _rank_itens_campeoes(inicio_corrente, fim_corrente, categoria='equipamentos', **kwargs),
            }
            grupos[origem_key][voltagem_key] = {
                'ano_anterior': _chart_grupos_equipamentos_campeoes(inicio_anterior, fim_anterior, **kwargs),
                'ano_corrente': _chart_grupos_equipamentos_campeoes(inicio_corrente, fim_corrente, **kwargs),
            }
            percentual[origem_key][voltagem_key] = _alinhar_charts_percentual_grupos_equipamentos({
                'ano_anterior': _chart_percentual_sac_por_grupo_equipamento(inicio_anterior, fim_anterior, limite=999, **kwargs),
                'ano_corrente': _chart_percentual_sac_por_grupo_equipamento(inicio_corrente, fim_corrente, limite=999, **kwargs),
            })
    return {
        'filtros': filtros,
        'ranking': ranking,
        'grupos': grupos,
        'percentual': percentual,
    }


def _chart_ocorrencias_periodo(inicio, fim, empresa_id=None, limite=10):
    qs = (
        SACItem.objects
        .select_related('tipo_ocorrencia')
        .filter(sac__data_abertura__gte=inicio, sac__data_abertura__lte=fim)
        .exclude(tipo_ocorrencia__isnull=True)
    )
    if empresa_id:
        qs = qs.filter(sac__empresa_id=empresa_id)

    contador = defaultdict(int)
    for item_sac in qs:
        contador[item_sac.tipo_ocorrencia.nome] += 1
    top = sorted(contador.items(), key=lambda item: (-item[1], item[0]))[:limite]
    return _chart(
        [nome for nome, _ in top],
        [total for _, total in top],
        ['#145a8f'] * len(top),
    )


def _chart(labels, values, colors=None):
    return {
        'labels': labels,
        'values': values,
        'colors': colors or [],
    }


def _status_por_ano(sacs, agora):
    anos = sorted({sac.data_abertura.year for sac in sacs if sac.data_abertura})
    if not anos:
        return {'labels': [], 'series': []}

    contagem = defaultdict(lambda: defaultdict(int))
    totais_status = defaultdict(int)
    for sac in sacs:
        if not sac.data_abertura:
            continue
        if sac.data_abertura.year == agora.year and sac.data_abertura > agora:
            continue
        status = _nome_status(sac)
        ano = sac.data_abertura.year
        contagem[ano][status] += 1
        totais_status[status] += 1

    status_labels = [item[0] for item in sorted(totais_status.items(), key=lambda x: (-x[1], x[0]))[:6]]
    cores = ['#0d3b66', '#00b4c7', '#149b7e', '#d7a11b', '#8d5cf6', '#d62839']
    return {
        'labels': [str(ano) for ano in anos],
        'series': [
            {
                'name': status,
                'values': [contagem[ano].get(status, 0) for ano in anos],
                'color': cores[idx % len(cores)],
            }
            for idx, status in enumerate(status_labels)
        ],
    }


def _linha_mensal_sacs(agora, empresa_id=None):
    meses = []
    abertos = []
    concluidos = []
    base = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for i in range(11, -1, -1):
        ano = base.year
        mes = base.month - i
        while mes <= 0:
            mes += 12
            ano -= 1
        inicio = base.replace(year=ano, month=mes)
        if mes == 12:
            fim = inicio.replace(year=ano + 1, month=1)
        else:
            fim = inicio.replace(month=mes + 1)
        qs_abertos = SAC.objects.filter(data_abertura__gte=inicio, data_abertura__lt=fim)
        qs_concluidos = SAC.objects.filter(concluido_em__gte=inicio, concluido_em__lt=fim)
        if empresa_id:
            qs_abertos = qs_abertos.filter(empresa_id=empresa_id)
            qs_concluidos = qs_concluidos.filter(empresa_id=empresa_id)
        meses.append(inicio.strftime('%m/%Y'))
        abertos.append(qs_abertos.count())
        concluidos.append(qs_concluidos.count())
    return {'labels': meses, 'abertos': abertos, 'concluidos': concluidos}


def _chart_abertos_ano(ano, ultimo_mes=12, empresa_id=None):
    meses_nome = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    labels = []
    values = []
    agora = timezone.now()
    for mes in range(1, ultimo_mes + 1):
        inicio = agora.replace(year=ano, month=mes, day=1, hour=0, minute=0, second=0, microsecond=0)
        if mes == 12:
            fim = inicio.replace(year=inicio.year + 1, month=1)
        else:
            fim = inicio.replace(month=mes + 1)
        qs = SAC.objects.filter(data_abertura__gte=inicio, data_abertura__lt=fim)
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        labels.append(meses_nome[mes - 1])
        values.append(qs.count())
    return _chart(labels, values, ['#0d7f9b'] * len(labels))


def _chart_abertos_ano_corrente(agora, empresa_id=None):
    return _chart_abertos_ano(agora.year, ultimo_mes=agora.month, empresa_id=empresa_id)


def _chart_abertos_ano_anterior(agora, empresa_id=None):
    return _chart_abertos_ano(agora.year - 1, ultimo_mes=12, empresa_id=empresa_id)


def _chart_abertos_comparativo_anos(agora, empresa_id=None):
    ano_corrente = agora.year
    ano_anterior = agora.year - 1
    atual = _chart_abertos_ano(ano_corrente, ultimo_mes=agora.month, empresa_id=empresa_id)
    anterior = _chart_abertos_ano(ano_anterior, ultimo_mes=12, empresa_id=empresa_id)
    valores_atual = list(atual['values']) + [None] * (12 - len(atual['values']))
    return {
        'labels': anterior['labels'],
        'series': [
            {'name': str(ano_corrente), 'values': valores_atual, 'color': '#145a8f'},
            {'name': str(ano_anterior), 'values': anterior['values'], 'color': '#d62839'},
        ],
    }


def _tempo_medio_resolucao_por_ano(agora, quantidade_anos=2, empresa_id=None):
    meses_nome = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    anos_qs = SAC.objects.exclude(ano__isnull=True).exclude(ano=0)
    if empresa_id:
        anos_qs = anos_qs.filter(empresa_id=empresa_id)
    anos = list(anos_qs.values_list('ano', flat=True).distinct().order_by('-ano')[:quantidade_anos])
    blocos = []
    for ano in anos:
        ultimo_mes = agora.month if ano == agora.year else 12
        labels = []
        values = []
        counts = []
        for mes in range(1, ultimo_mes + 1):
            inicio = agora.replace(year=ano, month=mes, day=1, hour=0, minute=0, second=0, microsecond=0)
            if mes == 12:
                fim = inicio.replace(year=ano + 1, month=1)
            else:
                fim = inicio.replace(month=mes + 1)
            concluidos = SAC.objects.filter(
                ano=ano,
                data_abertura__gte=inicio,
                data_abertura__lt=fim,
                concluido_em__isnull=False,
                data_abertura__isnull=False,
            )
            if empresa_id:
                concluidos = concluidos.filter(empresa_id=empresa_id)
            duracoes = [
                max((sac.concluido_em - sac.data_abertura).total_seconds(), 0) / 86400
                for sac in concluidos
                if sac.concluido_em and sac.data_abertura and sac.concluido_em >= sac.data_abertura
            ]
            labels.append(meses_nome[mes - 1])
            counts.append(len(duracoes))
            values.append(round(sum(duracoes) / len(duracoes), 1) if duracoes else 0)
        blocos.append({
            'ano': ano,
            'labels': labels,
            'values': values,
            'counts': counts,
        })
    return blocos


def montar_dashboard_sla(limit=30, empresa=None):
    agora = timezone.now()
    empresa_id = getattr(empresa, 'id', None)
    mes_inicio, mes_fim = _periodo_mes_atual(agora)
    ano_inicio = _inicio_ano(agora)
    ano_ant_inicio, ano_ant_fim = _periodo_ano_anterior(agora)
    limite_sla_horas = int(getattr(settings, "SLA_ALERTA_VERMELHO_HORAS", 24))

    sacs_qs = (
        SAC.objects
        .select_related('setor_atual', 'status_atual', 'cliente', 'empresa', 'acao_em_espera')
        .prefetch_related('itens_sac__item_nota_fiscal', 'itens_sac__tipo_ocorrencia')
        .order_by('-data_abertura', '-id')
    )
    if empresa_id:
        sacs_qs = sacs_qs.filter(empresa_id=empresa_id)
    sacs = list(sacs_qs)
    sacs_abertos = [s for s in sacs if not s.concluido_em and not s.cancelado_em]
    sacs_concluidos_mes = [s for s in sacs if s.concluido_em and mes_inicio <= s.concluido_em <= mes_fim]

    resumo = {
        'total_sacs': len(sacs),
        'total_abertos': len(sacs_abertos),
        'sla_verde': 0,
        'sla_amarelo': 0,
        'sla_vermelho': 0,
        'sla_vencidos': 0,
        'sla_proximos': 0,
        'concluidos_mes': len(sacs_concluidos_mes),
        'tempo_medio_resolucao': 'Não calculado',
        'taxa_conclusao_prazo': 0,
    }

    tempos_resolucao_horas = []
    concluidos_no_prazo = 0
    for sac in sacs_concluidos_mes:
        if not sac.data_abertura or not sac.concluido_em:
            continue
        horas = max((sac.concluido_em - sac.data_abertura).total_seconds(), 0) / 3600
        tempos_resolucao_horas.append(horas)
        if horas <= limite_sla_horas:
            concluidos_no_prazo += 1
    if tempos_resolucao_horas:
        resumo['tempo_medio_resolucao'] = _formatar_horas(sum(tempos_resolucao_horas) / len(tempos_resolucao_horas))
    resumo['taxa_conclusao_prazo'] = _percentual(concluidos_no_prazo, len(sacs_concluidos_mes))

    setores: dict[str, dict[str, Any]] = {}
    cards = []
    status_counter = defaultdict(int)
    ocorrencias_counter = defaultdict(int)
    clientes_counter = defaultdict(int)

    for sac in sacs:
        status_counter[_nome_status(sac)] += 1
        cliente_nome = _nome_cliente(sac)
        if cliente_nome != '-':
            clientes_counter[cliente_nome] += 1
        for item in sac.itens_sac.all():
            if item.tipo_ocorrencia:
                ocorrencias_counter[item.tipo_ocorrencia.nome] += 1

    for sac in sacs_abertos:
        tempo = resumo_tempo_setor(sac, agora=agora)
        delta = tempo['tempo_delta']
        sla_classe, sla_rotulo = classificar_sla(delta)
        sla_info = calcular_sla_sac(sac, agora=agora)
        cliente_nome = _nome_cliente(sac)
        resumo[f'sla_{sla_classe}'] += 1
        if sla_info.faixa == 'proximo_do_vencimento':
            resumo['sla_proximos'] += 1
        if sla_info.faixa in {'vencido', 'reincidente'}:
            resumo['sla_vencidos'] += 1

        setor_nome = _nome_setor(sac)
        bucket = setores.setdefault(setor_nome, {
            'setor': setor_nome,
            'total': 0,
            'verde': 0,
            'amarelo': 0,
            'vermelho': 0,
            'proximos': 0,
            'vencidos': 0,
            'horas_total': 0,
            'mais_antigo_horas': -1,
            'mais_antigo_numero': '-',
            'acoes_counter': defaultdict(int),
            'sacs': [],
        })
        horas = max(delta.total_seconds(), 0) / 3600
        acao_nome = getattr(getattr(sac, 'acao_em_espera', None), 'nome', None) or 'Sem ação definida'
        bucket['total'] += 1
        bucket[sla_classe] += 1
        bucket['horas_total'] += horas
        bucket['acoes_counter'][acao_nome] += 1
        bucket['sacs'].append({
            'numero': formatar_numero_sac(sac),
            'tempo': tempo['tempo_espera'],
            'acao': acao_nome,
            'horas': horas,
        })
        if sla_info.faixa == 'proximo_do_vencimento':
            bucket['proximos'] += 1
        if sla_info.faixa in {'vencido', 'reincidente'}:
            bucket['vencidos'] += 1
        if horas > bucket['mais_antigo_horas']:
            bucket['mais_antigo_horas'] = horas
            bucket['mais_antigo_numero'] = formatar_numero_sac(sac)

        cards.append({
            'id': sac.id,
            'numero_sac': formatar_numero_sac(sac),
            'cliente': cliente_nome,
            'setor': setor_nome,
            'status': _nome_status(sac),
            'acao': getattr(getattr(sac, 'acao_em_espera', None), 'nome', None) or '-',
            'tempo_setor': tempo['tempo_espera'],
            'tempo_horas': horas,
            'tempo_cor': tempo['tempo_cor'],
            'sla_classe': sla_classe,
            'sla_rotulo': sla_rotulo,
        })

    for item in setores.values():
        item['tempo_medio'] = _formatar_horas(item['horas_total'] / item['total']) if item['total'] else 'Menos de 1 hora'
        item['mais_antigo_tempo'] = _formatar_horas(item['mais_antigo_horas']) if item['mais_antigo_horas'] >= 0 else '-'
        item['taxa_prazo'] = _percentual(item['verde'], item['total'])
        acoes = sorted(item['acoes_counter'].items(), key=lambda x: (-x[1], x[0]))
        item['acoes'] = [{'nome': nome, 'total': total} for nome, total in acoes]
        item['sacs'] = sorted(item['sacs'], key=lambda x: -x.get('horas', 0))
        item['acao_principal'] = item['acoes'][0]['nome'] if item['acoes'] else 'Sem ação definida'
        item.pop('acoes_counter', None)

    cards = sorted(cards, key=lambda x: -x.get('tempo_horas', 0))[:limit]
    setores_ordenados = sorted(setores.values(), key=lambda x: (-x['vencidos'], -x['proximos'], -x['total'], x['setor']))

    top_setores = setores_ordenados[:10]
    ocorrencias_top = sorted(ocorrencias_counter.items(), key=lambda x: (-x[1], x[0]))[:10]
    linha_mensal = _linha_mensal_sacs(agora, empresa_id=empresa_id)
    tempo_resolucao_anos = _tempo_medio_resolucao_por_ano(agora, empresa_id=empresa_id)
    clientes_periodos = {
        'ano_anterior': _chart_clientes_sacs(ano_ant_inicio, ano_ant_fim, empresa_id=empresa_id),
        'ano_corrente': _chart_clientes_sacs(ano_inicio, agora, empresa_id=empresa_id),
    }
    vendas_x_sacs = {
        'ano_anterior': _chart_vendas_x_sacs(ano_ant_inicio, ano_ant_fim, empresa_id=empresa_id),
        'ano_corrente': _chart_vendas_x_sacs(ano_inicio, agora, empresa_id=empresa_id),
    }
    variantes_equipamentos = _montar_variantes_equipamentos(
        ano_ant_inicio,
        ano_ant_fim,
        ano_inicio,
        agora,
        empresa_id=empresa_id,
    )
    grupos_campeoes_sac = {
        'ano_anterior': _chart_grupos_equipamentos_campeoes(ano_ant_inicio, ano_ant_fim, empresa_id=empresa_id),
        'ano_corrente': _chart_grupos_equipamentos_campeoes(ano_inicio, agora, empresa_id=empresa_id),
    }
    percentual_sac_grupos_equipamentos = _alinhar_charts_percentual_grupos_equipamentos({
        'ano_anterior': _chart_percentual_sac_por_grupo_equipamento(ano_ant_inicio, ano_ant_fim, empresa_id=empresa_id, limite=999),
        'ano_corrente': _chart_percentual_sac_por_grupo_equipamento(ano_inicio, agora, empresa_id=empresa_id, limite=999),
    })
    tempo_uso_equipamentos = _charts_tempo_uso_equipamentos(empresa_id=empresa_id)
    ocorrencias_periodos = {
        'ano_anterior': _chart_ocorrencias_periodo(ano_ant_inicio, ano_ant_fim, empresa_id=empresa_id),
        'ano_corrente': _chart_ocorrencias_periodo(ano_inicio, agora, empresa_id=empresa_id),
    }

    charts = {
        'sla': _chart(
            ['Dentro do prazo', 'Próximo', 'Vencido'],
            [resumo['sla_verde'], resumo['sla_proximos'], resumo['sla_vencidos']],
            ['#149b7e', '#d7a11b', '#d62839'],
        ),
        'setores': _chart(
            [item['setor'] for item in top_setores],
            [item['total'] for item in top_setores],
            ['#0d3b66'] * len(top_setores),
        ),
        'vencidos_setor': _chart(
            [item['setor'] for item in top_setores],
            [item['vencidos'] for item in top_setores],
            ['#d62839'] * len(top_setores),
        ),
        'status_anos': _status_por_ano(sacs, agora),
        'ocorrencias_periodos': ocorrencias_periodos,
        'clientes_periodos': clientes_periodos,
        'vendas_x_sacs': vendas_x_sacs,
        'grupos_campeoes_sac': grupos_campeoes_sac,
        'percentual_sac_grupos_equipamentos': percentual_sac_grupos_equipamentos,
        'tempo_uso_equipamentos': tempo_uso_equipamentos,
        'equipamentos_filtrados': variantes_equipamentos,
        'abertos_ano_corrente': _chart_abertos_ano_corrente(agora, empresa_id=empresa_id),
        'abertos_ano_anterior': _chart_abertos_ano_anterior(agora, empresa_id=empresa_id),
        'abertos_comparativo_anos': _chart_abertos_comparativo_anos(agora, empresa_id=empresa_id),
        'mensal': linha_mensal,
        'tempo_resolucao_anos': tempo_resolucao_anos,
    }

    ranking_itens = {
        'ano_anterior': {
            'titulo': f'Ano anterior ({ano_ant_inicio.year})',
            'periodo': f'{ano_ant_inicio:%d/%m/%Y} a {ano_ant_fim:%d/%m/%Y}',
            'equipamentos': _rank_itens_campeoes(ano_ant_inicio, ano_ant_fim, categoria='equipamentos', empresa_id=empresa_id),
            'consumiveis': _rank_itens_campeoes(ano_ant_inicio, ano_ant_fim, categoria='consumiveis', empresa_id=empresa_id),
        },
        'ano_corrente': {
            'titulo': f'Ano corrente ({agora.year})',
            'periodo': f'{ano_inicio:%d/%m/%Y} a {agora:%d/%m/%Y}',
            'equipamentos': _rank_itens_campeoes(ano_inicio, agora, categoria='equipamentos', empresa_id=empresa_id),
            'consumiveis': _rank_itens_campeoes(ano_inicio, agora, categoria='consumiveis', empresa_id=empresa_id),
        },
        'mes_corrente': {
            'titulo': f'Mês corrente ({agora:%m/%Y})',
            'periodo': f'{mes_inicio:%d/%m/%Y} a {agora:%d/%m/%Y}',
            'equipamentos': _rank_itens_campeoes(mes_inicio, agora, categoria='equipamentos', empresa_id=empresa_id),
            'consumiveis': _rank_itens_campeoes(mes_inicio, agora, categoria='consumiveis', empresa_id=empresa_id),
        },
    }

    return {
        'resumo': resumo,
        'setores': setores_ordenados,
        'cards': cards,
        'gerado_em': agora,
        'sla_verde_horas': SLA_VERDE_HORAS,
        'sla_amarelo_horas': SLA_AMARELO_HORAS,
        'charts_json': json.dumps(charts, ensure_ascii=False),
        'tempo_resolucao_anos': tempo_resolucao_anos,
        'ranking_itens': ranking_itens,
        'filtros_equipamentos': variantes_equipamentos['filtros'],
        'ranking_equipamentos_json': json.dumps(variantes_equipamentos['ranking'], ensure_ascii=False),
        'top_ocorrencias': [{'nome': k, 'total': v} for k, v in ocorrencias_top],
        'top_clientes': [],
        'empresa_selecionada': empresa,
        'ano_anterior': ano_ant_inicio.year,
        'ano_corrente': agora.year,
    }


def _carregar_logs_sac(sac_id: int, limite=100):
    log_path = Path(getattr(settings, 'BASE_DIR', '.')) / 'logs' / 'sac_auditoria.log'
    if not log_path.exists():
        return []
    eventos = []
    try:
        with log_path.open('r', encoding='utf-8') as fh:
            for linha in fh:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    payload = json.loads(linha)
                except Exception:
                    continue
                if str(payload.get('sac_id')) == str(sac_id):
                    eventos.append(payload)
    except Exception:
        return []
    return list(reversed(eventos[-limite:]))


def _extrair_secao_descricao(descricao, titulo):
    texto = str(descricao or '')
    if not texto:
        return ''
    padrao = re.compile(
        rf'{re.escape(titulo)}:\s*(.*?)(?=\n\n[A-ZÁÉÍÓÚÂÊÔÃÕÇA-Za-z0-9 /()_-]+:\s*|\Z)',
        re.S,
    )
    match = padrao.search(texto)
    if not match:
        return ''
    return match.group(1).strip()


def montar_auditoria_visual_sac(sac):
    historicos = list(
        SacHistorico.objects.filter(sac=sac)
        .select_related('usuario', 'setor_origem', 'setor_destino', 'status_anterior', 'status_novo')
        .order_by('-data_evento', '-id')
    )
    linhas = []
    for hist in historicos:
        linhas.append({
            'data_evento': hist.data_evento,
            'data_evento_fmt': hist.data_evento.strftime('%d/%m/%Y %H:%M') if hist.data_evento else '-',
            'usuario': getattr(hist.usuario, 'username', None) or str(hist.usuario),
            'acao_executada': hist.acao_executada,
            'status_anterior': getattr(getattr(hist, 'status_anterior', None), 'nome', None) or '-',
            'status_novo': getattr(getattr(hist, 'status_novo', None), 'nome', None) or '-',
            'setor_origem': getattr(getattr(hist, 'setor_origem', None), 'nome', None) or '-',
            'setor_destino': getattr(getattr(hist, 'setor_destino', None), 'nome', None) or '-',
            'observacao': hist.observacao or '-',
            'arquivo_url': hist.arquivo.url if getattr(hist, 'arquivo', None) else '',
        })
    itens = []
    itens_qs = (
        sac.itens_sac
        .select_related('item_nota_fiscal', 'tipo_ocorrencia')
        .order_by('item_nota_fiscal__codigo_produto', 'id')
    )
    for item in itens_qs:
        item_nf = getattr(item, 'item_nota_fiscal', None)
        tipo = getattr(item, 'tipo_ocorrencia', None)
        itens.append({
            'referencia': getattr(item_nf, 'codigo_produto', None) or '-',
            'descricao': getattr(item_nf, 'descricao_item', None) or getattr(item_nf, 'item', None) or '-',
            'quantidade': item.quantidade_com_problema or 0,
            'tipo_ocorrencia': getattr(tipo, 'nome', None) or '-',
            'tipo_rastreio': item.tipo_rastreio or '-',
            'numero_rastreio': item.numero_rastreio or '-',
            'grupo': item.grupo or '-',
            'observacao': item.observacao_item or '',
        })
    return {
        'sac': sac,
        'numero_sac': formatar_numero_sac(sac),
        'itens_sac': itens,
        'historico_legado': _extrair_secao_descricao(sac.descricao, 'Historico legado'),
        'historicos': linhas,
        'logs_tecnicos': _carregar_logs_sac(sac.id),
    }
