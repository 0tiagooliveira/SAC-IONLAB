from __future__ import annotations

import logging
from typing import Dict, List

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from core.services.destinatarios_sac import emails_cliente_sac
from core.services.sla_inteligente import calcular_sla_sac

logger = logging.getLogger(__name__)

STATUS_CLIENTE_MAP = {
    "EM ANÁLISE": "Em análise",
    "EM ANALISE": "Em análise",
    "AGUARDANDO APROVAÇÃO DE DESCONTO": "Em validação",
    "AGUARDANDO APROVACAO DE DESCONTO": "Em validação",
    "EMISSÃO DO PEDIDO DE ENTRADA/RETORNO": "Organizando coleta",
    "EMISSAO DO PEDIDO DE ENTRADA/RETORNO": "Organizando coleta",
    "CONCLUÍDO": "Finalizado",
    "CONCLUIDO": "Finalizado",
}


def traduzir_status_para_cliente(status_nome: str) -> str:
    status_nome = (status_nome or "").strip()
    if not status_nome:
        return "Em andamento"
    return STATUS_CLIENTE_MAP.get(status_nome.upper(), status_nome.title())


def obter_emails_cliente(sac) -> List[str]:
    return emails_cliente_sac(sac)


def obter_email_cliente(sac) -> str:
    emails = obter_emails_cliente(sac)
    return emails[0] if emails else ""


def numero_sac_seguro(sac) -> str:
    numero = getattr(sac, "numero", "") or ""
    if isinstance(numero, str) and "/" in numero:
        return numero
    ano = getattr(sac, "ano", "") or ""
    try:
        return f"{int(numero):03d}/{ano}" if ano else f"{int(numero):03d}"
    except Exception:
        return str(numero or "-")


def contexto_email_cliente(sac) -> Dict[str, str]:
    status_atual = getattr(getattr(sac, "status_atual", None), "nome", None) or ""
    cliente_nome = (
        getattr(getattr(sac, "cliente", None), "razao_social", None)
        or getattr(getattr(sac, "cliente", None), "nome", None)
        or "Cliente"
    )
    sla = calcular_sla_sac(sac).as_dict()
    return {
        "numero_sac": numero_sac_seguro(sac),
        "cliente_nome": cliente_nome,
        "status_cliente": traduzir_status_para_cliente(status_atual),
        "titulo": getattr(sac, "titulo", None) or "Solicitação em acompanhamento",
        "data_referencia": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        "sla_faixa": sla["faixa"],
    }


def diagnosticar_email_cliente(sac) -> Dict[str, str]:
    destinatarios = obter_emails_cliente(sac)
    if not destinatarios:
        return {"ok": False, "motivo": "sem_email_cliente", "destinatario": "", "destinatarios": []}
    if not getattr(settings, "DEFAULT_FROM_EMAIL", None):
        return {"ok": False, "motivo": "smtp_nao_configurado", "destinatario": ", ".join(destinatarios), "destinatarios": destinatarios}
    return {"ok": True, "motivo": "ok", "destinatario": ", ".join(destinatarios), "destinatarios": destinatarios}


def enviar_email_cliente_sac(sac, tipo_evento: str, mensagem_livre: str = "") -> Dict[str, str]:
    diagnostico = diagnosticar_email_cliente(sac)
    if not diagnostico["ok"]:
        return {
            "enviado": False,
            "motivo": diagnostico["motivo"],
            "destinatario": diagnostico["destinatario"],
            "destinatarios": diagnostico.get("destinatarios", []),
        }

    destinatarios = diagnostico["destinatarios"]
    contexto = contexto_email_cliente(sac)
    contexto["mensagem_livre"] = mensagem_livre

    assunto_map = {
        "abertura": f"[SAC] Atendimento aberto - Nº {contexto['numero_sac']}",
        "status": f"[SAC] Atualização do atendimento - Nº {contexto['numero_sac']}",
        "conclusao": f"[SAC] Atendimento finalizado - Nº {contexto['numero_sac']}",
    }
    template_map = {
        "abertura": "core/emails/cliente_abertura.html",
        "status": "core/emails/cliente_status.html",
        "conclusao": "core/emails/cliente_conclusao.html",
    }

    assunto = assunto_map.get(tipo_evento, assunto_map["status"])
    try:
        html = render_to_string(template_map.get(tipo_evento, template_map["status"]), contexto)
        texto = render_to_string("core/emails/cliente_status.txt", contexto)

        msg = EmailMultiAlternatives(
            subject=assunto,
            body=texto,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=destinatarios,
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        return {
            "enviado": True,
            "motivo": "enviado",
            "destinatario": ", ".join(destinatarios),
            "destinatarios": destinatarios,
        }
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail ao cliente do SAC %s", contexto["numero_sac"])
        return {
            "enviado": False,
            "motivo": f"erro_envio_cliente: {exc.__class__.__name__}",
            "destinatario": ", ".join(destinatarios),
            "destinatarios": destinatarios,
        }
