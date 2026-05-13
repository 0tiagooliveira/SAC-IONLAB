
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict

from django.conf import settings
from django.utils import timezone


@dataclass
class SLAInfo:
    horas_decorridas: float
    nivel: str
    cor: str
    vencido: bool
    faixa: str
    horas_limite: int
    horas_reincidencia: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "horas_decorridas": round(self.horas_decorridas, 2),
            "nivel": self.nivel,
            "cor": self.cor,
            "vencido": self.vencido,
            "faixa": self.faixa,
            "horas_limite": self.horas_limite,
            "horas_reincidencia": self.horas_reincidencia,
        }


def _marco_tempo_setor(sac) -> Any:
    for attr in ("data_hora_setor", "data_ultima_movimentacao", "data_abertura"):
        valor = getattr(sac, attr, None)
        if valor:
            return valor
    return timezone.now()


def calcular_sla_sac(sac, agora=None) -> SLAInfo:
    agora = agora or timezone.now()
    marco = _marco_tempo_setor(sac)
    delta = agora - marco if marco else timedelta(0)
    horas = max(delta.total_seconds(), 0) / 3600

    amarelo = int(getattr(settings, "SLA_ALERTA_AMARELO_HORAS", 12))
    vermelho = int(getattr(settings, "SLA_ALERTA_VERMELHO_HORAS", 24))
    reincidencia = int(getattr(settings, "SLA_ALERTA_REINCIDENCIA_HORAS", 48))

    if horas < amarelo:
        return SLAInfo(horas, "normal", "verde", False, "dentro_do_prazo", vermelho, reincidencia)
    if horas < vermelho:
        return SLAInfo(horas, "atencao", "amarelo", False, "proximo_do_vencimento", vermelho, reincidencia)
    if horas < reincidencia:
        return SLAInfo(horas, "vencido", "vermelho", True, "vencido", vermelho, reincidencia)
    return SLAInfo(horas, "critico", "vermelho", True, "reincidente", vermelho, reincidencia)
