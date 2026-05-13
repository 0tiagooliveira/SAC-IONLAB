from __future__ import annotations

import logging
from typing import Dict, List

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.models import SAC
from core.services.comunicacao_cliente import enviar_email_cliente_sac, numero_sac_seguro
from core.services.destinatarios_sac import emails_envolvidos_internos_sac
from core.services.sla_inteligente import calcular_sla_sac

logger = logging.getLogger(__name__)


def _emails_internos_sac(sac) -> List[str]:
    emails = emails_envolvidos_internos_sac(sac)
    return list(emails or [])


def processar_alertas_sla(*, enviar_cliente: bool = True, enviar_interno: bool = True) -> List[Dict]:
    agora = timezone.now()
    resultados: List[Dict] = []

    sacs = SAC.objects.select_related("status_atual", "setor_atual", "cliente", "usuario_abertura").all().order_by("id")
    for sac in sacs:
        sla = calcular_sla_sac(sac, agora=agora)
        if sla.faixa == "dentro_do_prazo":
            continue

        numero = numero_sac_seguro(sac)
        setor = getattr(getattr(sac, "setor_atual", None), "nome", None) or "-"
        status = getattr(getattr(sac, "status_atual", None), "nome", None) or "-"
        destinatarios_internos = _emails_internos_sac(sac)

        envio_interno = "nao_solicitado"
        if enviar_interno and destinatarios_internos:
            assunto = f"[SAC][ALERTA SLA] SAC {numero} - {sla.faixa.replace('_', ' ')}"
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
        motivo_cliente = "nao_elegivel_para_envio"
        destinatario_cliente = ""
        if enviar_cliente and sla.faixa in {"vencido", "reincidente"}:
            retorno = enviar_email_cliente_sac(
                sac,
                "status",
                mensagem_livre="Seu atendimento segue em acompanhamento pela nossa equipe.",
            )
            cliente_enviado = bool(retorno.get("enviado"))
            motivo_cliente = retorno.get("motivo") or "desconhecido"
            destinatario_cliente = retorno.get("destinatario") or ""
        elif enviar_cliente:
            motivo_cliente = "faixa_sem_envio_ao_cliente"

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
