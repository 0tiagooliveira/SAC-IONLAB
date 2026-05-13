from __future__ import annotations

import unicodedata
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.utils import timezone

from core.models import Setor
from core.services.regras_sac import codigo_setor, resolver_setor_por_codigo
from core.utils_log_seguro import registrar_erro


def texto_normalizado(valor) -> str:
    return unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii').strip().lower()


def obter_setor_por_nome(nome: str):
    return Setor.objects.filter(nome__iexact=nome).first()


def obter_setor_por_codigo(codigo: str):
    return resolver_setor_por_codigo(codigo)


def obter_setor_comercial_padrao():
    return obter_setor_por_codigo('COMERCIAL')


def obter_setor_licitacao_padrao():
    return obter_setor_por_codigo('LICITACAO')


def obter_setor_assistencia_tecnica_padrao():
    return obter_setor_por_codigo('ASSISTENCIA_TECNICA')


def resolver_setor_contexto_por_codigo(sac, codigo: str):
    codigo_norm = codigo_setor(codigo)
    padrao = obter_setor_por_codigo(codigo_norm)
    if sac is None:
        return padrao
    setor_atual = getattr(sac, 'setor_atual', None)
    if setor_atual and codigo_setor(setor_atual) == codigo_norm:
        return setor_atual
    acao_atual = getattr(sac, 'acao_em_espera', None)
    setor_destino_acao = getattr(acao_atual, 'setor_destino', None) if acao_atual else None
    if setor_destino_acao and codigo_setor(setor_destino_acao) == codigo_norm:
        return setor_destino_acao
    return padrao


def resolver_setor_contexto_comercial(sac):
    return resolver_setor_contexto_por_codigo(sac, 'COMERCIAL')


def resolver_setor_contexto_licitacao(sac):
    return resolver_setor_contexto_por_codigo(sac, 'LICITACAO')


def resolver_setor_contexto_assistencia_tecnica(sac):
    return resolver_setor_contexto_por_codigo(sac, 'ASSISTENCIA_TECNICA')



def formatar_numero_sac(sac):
    numero = str(getattr(sac, 'numero', '') or '').strip()
    if not numero:
        return f'SAC {getattr(sac, "id", "")}'.strip()
    if '/' in numero:
        return numero
    ano = getattr(sac, 'ano', None)
    try:
        numero = str(int(numero)).zfill(3)
    except Exception as e:
        registrar_erro('core.services.sac_visual.py:except_1', e)
        pass
    return f'{numero}/{ano}' if ano else numero


def marco_tempo_setor(sac, agora=None):
    agora = agora or timezone.now()
    historicos_rel = getattr(sac, 'historicos', None)
    if historicos_rel is not None:
        try:
            cache_prefetch = getattr(sac, '_prefetched_objects_cache', {})
            historicos_prefetch = cache_prefetch.get('historicos')
            if historicos_prefetch is not None:
                ultimo = historicos_prefetch[0] if historicos_prefetch else None
            else:
                ultimo = historicos_rel.order_by('-data_evento', '-id').first()
        except Exception:
            ultimo = None
        if ultimo and getattr(ultimo, 'data_evento', None):
            return ultimo.data_evento
    return getattr(sac, 'data_abertura', None) or agora


def resumo_tempo_setor(sac, agora=None):
    agora = agora or timezone.now()
    marco = marco_tempo_setor(sac, agora=agora)
    delta = agora - marco
    return {
        'marco_tempo': marco,
        'tempo_espera': formatar_tempo_espera(delta),
        'tempo_cor': classe_tempo_espera(delta),
        'tempo_delta': delta,
    }

def _parte_tempo(valor, singular, plural):
    if not valor:
        return None
    nome = singular if valor == 1 else plural
    return f'{valor} {nome}'


def formatar_duracao_dd_hh_mm(delta):
    total_horas = int(max(delta.total_seconds(), 0) // 3600)
    if total_horas < 1:
        return 'Menos de 1 hora'

    dias_total = total_horas // 24
    horas = total_horas % 24
    anos = dias_total // 365
    dias_restantes = dias_total % 365
    meses = dias_restantes // 30
    dias = dias_restantes % 30

    partes = [
        _parte_tempo(anos, 'ano', 'anos'),
        _parte_tempo(meses, 'mês', 'meses'),
        _parte_tempo(dias, 'dia', 'dias'),
        _parte_tempo(horas, 'hora', 'horas'),
    ]
    partes = [parte for parte in partes if parte]
    return ' - '.join(partes) if partes else 'Menos de 1 hora'


def formatar_horas_dd_hh_mm(horas):
    try:
        segundos = int(max(float(horas or 0), 0) * 3600)
    except (TypeError, ValueError):
        segundos = 0
    return formatar_duracao_dd_hh_mm(timedelta(seconds=segundos))


def formatar_tempo_espera(delta):
    return formatar_duracao_dd_hh_mm(delta)


def classe_tempo_espera(delta):
    total_horas = max(delta.total_seconds(), 0) / 3600
    if total_horas < 12:
        return 'tempo-verde'
    if total_horas < 24:
        return 'tempo-amarelo'
    return 'tempo-vermelho'


def montar_grafico_tempo_status_sac(sac, agora=None, limite=None):
    historicos_qs = getattr(sac, 'historicos', None)
    if historicos_qs is None:
        return []
    agora = agora or timezone.now()
    historicos_ordenados = list(historicos_qs.all().order_by('-data_evento', '-id'))
    if limite:
        historicos_ordenados = historicos_ordenados[:limite]
    grafico_tempo_status = []
    for i, h in enumerate(historicos_ordenados):
        data_evento = getattr(h, 'data_evento', None)
        proximo = historicos_ordenados[i + 1] if i + 1 < len(historicos_ordenados) else None
        data_proximo = getattr(proximo, 'data_evento', None) if proximo else agora
        delta = (data_proximo - data_evento) if data_evento and data_proximo else timedelta(0)
        tempo_txt = formatar_duracao_dd_hh_mm(delta)
        grafico_tempo_status.append({
            'status': getattr(getattr(h, 'status_novo', None), 'nome', '') or getattr(getattr(sac, 'status_atual', None), 'nome', '-') or '-',
            'setor': getattr(getattr(h, 'setor_destino', None), 'nome', '-') or '-',
            'data_evento_formatada': data_evento.strftime('%d/%m/%Y %H:%M') if data_evento else '-',
            'tempo_ate_proxima': tempo_txt,
            'tempo_label': 'Tempo até a próxima mudança' if proximo else 'Tempo em status atual',
        })
    return grafico_tempo_status


def empresa_sac(sac):
    if getattr(sac, 'empresa', None):
        return getattr(sac.empresa, 'nome_fantasia', None) or getattr(sac.empresa, 'razao_social', None) or str(sac.empresa)
    if getattr(sac, 'cliente', None):
        return getattr(sac.cliente, 'razao_social', None) or getattr(sac.cliente, 'nome', None) or '-'
    return '-'


def nota_sac(sac):
    if getattr(sac, 'nota_fiscal', None):
        return getattr(sac.nota_fiscal, 'numero_nf', None) or getattr(sac.nota_fiscal, 'numero', None) or '-'
    return '-'


def data_nota_sac(sac):
    if getattr(sac, 'nota_fiscal', None):
        return getattr(sac.nota_fiscal, 'data_emissao', None) or getattr(sac.nota_fiscal, 'data', None) or getattr(sac.nota_fiscal, 'data_nota', None)
    return None


def ultimo_historico_card(sac):
    historicos_rel = getattr(sac, 'historicos', None)
    if historicos_rel is None:
        return None
    try:
        return historicos_rel.order_by('-data_evento', '-id').first()
    except Exception:
        return None


def status_anterior_card(sac):
    return getattr(getattr(sac, 'status_atual', None), 'nome', None) or '-'


def acao_em_espera_card(sac):
    return getattr(getattr(sac, 'acao_em_espera', None), 'nome', None) or '-'


def valor_unitario_item(item_sac):
    item_nf = getattr(item_sac, 'item_nota_fiscal', None)
    if item_nf is None:
        return None
    for attr in ('valor_unitario', 'valor', 'preco_unitario', 'valor_total'):
        valor = getattr(item_nf, attr, None)
        if valor not in (None, ''):
            return valor
    valor_total_item = getattr(item_nf, 'valor_total_item', None)
    quantidade = getattr(item_nf, 'quantidade', None)
    try:
        if valor_total_item not in (None, '') and quantidade not in (None, '', 0):
            valor_total_dec = Decimal(valor_total_item)
            quantidade_dec = Decimal(quantidade)
            if quantidade_dec != 0:
                return (valor_total_dec / quantidade_dec).quantize(Decimal('0.01'))
    except (InvalidOperation, ZeroDivisionError, TypeError):
        pass
    return None


def descricao_item_sac(item_sac):
    item_nf = getattr(item_sac, 'item_nota_fiscal', None)
    for attr in ('descricao_produto', 'descricao_item', 'descricao'):
        valor = getattr(item_nf, attr, None)
        if valor:
            return valor
    return '-'


def montar_contexto_itens_sac(sac, setor_contexto=None):
    itens = list(sac.itens_sac.select_related('item_nota_fiscal', 'tipo_ocorrencia__setor').all().order_by('id'))
    itens_visiveis, itens_outros_setores = [], []
    for item in itens:
        valor_unitario = valor_unitario_item(item)
        try:
            quantidade_com_problema = Decimal(str(getattr(item, 'quantidade_com_problema', 0) or 0))
        except Exception:
            quantidade_com_problema = Decimal('0')
        try:
            valor_total_problema = (Decimal(str(valor_unitario or 0)) * quantidade_com_problema)
        except Exception:
            valor_total_problema = Decimal('0')
        tipo = getattr(item, 'tipo_ocorrencia', None)
        setor_item = getattr(tipo, 'setor', None)
        item_dict = {
            'obj': item,
            'codigo_produto': getattr(getattr(item, 'item_nota_fiscal', None), 'codigo_produto', None) or '-',
            'descricao_item': descricao_item_sac(item),
            'tipo_ocorrencia_nome': getattr(tipo, 'nome', None) or '-',
            'identificador': getattr(item, 'tipo_rastreio', None) or '-',
            'numero_rastreio': getattr(item, 'numero_rastreio', None) or '-',
            'quantidade_nf': getattr(getattr(item, 'item_nota_fiscal', None), 'quantidade', None),
            'quantidade_com_problema': quantidade_com_problema,
            'valor_unitario': valor_unitario,
            'valor_total_problema': valor_total_problema,
            'setor_item_nome': getattr(setor_item, 'nome', None) or '-',
            # PATCH_RELATO_CLIENTE_FINAL_REAL_20260501
            # itens_contexto.itens é um dict, então o relato precisa ser enviado explicitamente.
            'observacao': getattr(item, 'observacao_item', None) or '',
            'observacao_item': getattr(item, 'observacao_item', None) or '',
        }
        if setor_contexto is None or setor_item is None or setor_item.id == setor_contexto.id:
            itens_visiveis.append(item_dict)
        else:
            itens_outros_setores.append(item_dict)
    avisos = []
    if itens_outros_setores:
        avisos.append('Existem itens vinculados a outros setores e a conclusão total pode ser bloqueada.')
    return {
        'itens': itens_visiveis,
        'itens_outros_setores': itens_outros_setores,
        'avisos_outros_setores': avisos,
        'total_visivel': len(itens_visiveis),
        'total_geral': len(itens),
    }
