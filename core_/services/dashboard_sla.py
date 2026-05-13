
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from core.models import SAC, SacHistorico
from core.services.sac_visual import formatar_numero_sac, resumo_tempo_setor


SLA_VERDE_HORAS = 12
SLA_AMARELO_HORAS = 24


def classificar_sla(delta):
    total_horas = max(delta.total_seconds(), 0) / 3600
    if total_horas < SLA_VERDE_HORAS:
        return 'verde', 'Dentro do SLA'
    if total_horas < SLA_AMARELO_HORAS:
        return 'amarelo', 'Atenção'
    return 'vermelho', 'Estourado'


def _nome_setor(sac):
    return getattr(getattr(sac, 'setor_atual', None), 'nome', None) or 'Sem setor'


def _nome_status(sac):
    return getattr(getattr(sac, 'status_atual', None), 'nome', None) or getattr(sac, 'status_inicial', None) or '-'


def _nome_cliente(sac):
    cliente = getattr(sac, 'cliente', None)
    return getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None) or '-'


def montar_dashboard_sla(limit=30):
    agora = timezone.now()
    sacs = list(SAC.objects.select_related('setor_atual', 'status_atual', 'cliente', 'empresa').all().order_by('-data_abertura', '-id'))

    resumo = {
        'total_sacs': len(sacs),
        'sla_verde': 0,
        'sla_amarelo': 0,
        'sla_vermelho': 0,
    }
    setores: dict[str, dict[str, Any]] = {}
    cards = []

    for sac in sacs:
        tempo = resumo_tempo_setor(sac, agora=agora)
        delta = tempo['tempo_delta']
        sla_classe, sla_rotulo = classificar_sla(delta)
        resumo[f'sla_{sla_classe}'] += 1
        setor_nome = _nome_setor(sac)
        bucket = setores.setdefault(setor_nome, {
            'setor': setor_nome,
            'total': 0,
            'verde': 0,
            'amarelo': 0,
            'vermelho': 0,
        })
        bucket['total'] += 1
        bucket[sla_classe] += 1
        cards.append({
            'id': sac.id,
            'numero_sac': formatar_numero_sac(sac),
            'cliente': _nome_cliente(sac),
            'setor': setor_nome,
            'status': _nome_status(sac),
            'tempo_setor': tempo['tempo_espera'],
            'tempo_cor': tempo['tempo_cor'],
            'sla_classe': sla_classe,
            'sla_rotulo': sla_rotulo,
        })

    cards = cards[:limit]
    setores_ordenados = sorted(setores.values(), key=lambda x: (-x['vermelho'], -x['amarelo'], x['setor']))
    return {
        'resumo': resumo,
        'setores': setores_ordenados,
        'cards': cards,
        'gerado_em': agora,
        'sla_verde_horas': SLA_VERDE_HORAS,
        'sla_amarelo_horas': SLA_AMARELO_HORAS,
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
    return {
        'sac': sac,
        'numero_sac': formatar_numero_sac(sac),
        'historicos': linhas,
        'logs_tecnicos': _carregar_logs_sac(sac.id),
    }
