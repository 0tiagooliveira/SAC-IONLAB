from __future__ import annotations

import logging
from typing import Dict, List

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.models import SAC
from core.services.comunicacao_cliente import numero_sac_seguro
from core.services.destinatarios_sac import emails_envolvidos_internos_sac
from core.services.sla_inteligente import calcular_sla_sac

logger = logging.getLogger(__name__)


def _emails_internos_sac(sac) -> List[str]:
    emails = emails_envolvidos_internos_sac(sac)
    return list(emails or [])


ASSUNTO_SLA_PROXIMO_VENCIMENTO = "Você tem uma ação pendente próximo do vencimento."
ASSUNTO_SLA_VENCIDO = "Você tem uma ação vencida. Regularize urgente. O cliente não pode esperar!"


def _janela_envio_sla(agora, faixa: str) -> bool:
    local = timezone.localtime(agora)
    if local.weekday() >= 5:
        return False
    if faixa == "proximo_do_vencimento":
        return local.hour == 10
    if faixa == "vencido":
        return local.hour in {10, 15}
    return False


def _assunto_sla(faixa: str) -> str:
    if faixa == "proximo_do_vencimento":
        return ASSUNTO_SLA_PROXIMO_VENCIMENTO
    if faixa == "vencido":
        return ASSUNTO_SLA_VENCIDO
    return ""


def processar_alertas_sla(*, enviar_cliente: bool = False, enviar_interno: bool = True, respeitar_janela: bool = True, agora=None) -> List[Dict]:
    agora = agora or timezone.now()
    resultados: List[Dict] = []

    sacs = (
        SAC.objects.select_related("status_atual", "setor_atual", "cliente", "usuario_abertura")
        .filter(concluido_em__isnull=True, cancelado_em__isnull=True)
        .order_by("id")
    )
    for sac in sacs:
        sla = calcular_sla_sac(sac, agora=agora)
        if sla.faixa == "dentro_do_prazo":
            continue
        if sla.faixa == "reincidente":
            resultados.append(
                {
                    "sac_id": sac.id,
                    "numero_sac": numero_sac_seguro(sac),
                    "faixa": sla.faixa,
                    "cliente_enviado": False,
                    "motivo_cliente": "sla_reincidente_suspenso",
                    "destinatario_cliente": "",
                    "envio_interno": "sla_reincidente_suspenso",
                    "destinatarios_internos": [],
                }
            )
            continue
        if respeitar_janela and not _janela_envio_sla(agora, sla.faixa):
            resultados.append(
                {
                    "sac_id": sac.id,
                    "numero_sac": numero_sac_seguro(sac),
                    "faixa": sla.faixa,
                    "cliente_enviado": False,
                    "motivo_cliente": "fora_da_janela_de_envio",
                    "destinatario_cliente": "",
                    "envio_interno": "fora_da_janela_de_envio",
                    "destinatarios_internos": [],
                }
            )
            continue

        numero = numero_sac_seguro(sac)
        setor = getattr(getattr(sac, "setor_atual", None), "nome", None) or "-"
        status = getattr(getattr(sac, "status_atual", None), "nome", None) or "-"
        destinatarios_internos = _emails_internos_sac(sac)

        envio_interno = "nao_solicitado"
        if enviar_interno and destinatarios_internos:
            assunto = _assunto_sla(sla.faixa)
            corpo = (
                f"SAC: {numero}\n"
                f"Setor atual: {setor}\n"
                f"Status atual: {status}\n"
                f"Horas decorridas: {sla.horas_decorridas:.2f}\n"
                f"Nível: {sla.nivel}\n"
                f"Destinatários internos: {', '.join(destinatarios_internos)}\n"
            )
            try:
                send_mail(
                    assunto,
                    corpo,
                    getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    destinatarios_internos,
                    fail_silently=False,
                )
                envio_interno = "enviado"
            except Exception as exc:
                envio_interno = f"erro_envio_interno: {exc.__class__.__name__}"
                logger.exception("Falha no envio interno do alerta de SLA do SAC %s", numero)
        elif enviar_interno:
            envio_interno = "sem_destinatarios_internos"

        cliente_enviado = False
        motivo_cliente = "envio_sla_cliente_desabilitado"
        destinatario_cliente = ""
        if enviar_cliente:
            motivo_cliente = "envio_sla_cliente_desabilitado_pela_regra_atual"

        resultados.append(
            {
                "sac_id": sac.id,
                "numero_sac": numero,
                "faixa": sla.faixa,
                "cliente_enviado": cliente_enviado,
                "motivo_cliente": motivo_cliente,
                "destinatario_cliente": destinatario_cliente,
                "envio_interno": envio_interno,
                "destinatarios_internos": destinatarios_internos,
            }
        )

    return resultados
