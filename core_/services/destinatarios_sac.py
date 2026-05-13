from __future__ import annotations

from typing import Iterable, List, Set
from django.conf import settings
from django.contrib.auth import get_user_model

from core.models import SacHistorico


def _normalizar_email(valor) -> str:
    valor = (valor or "").strip()
    return valor.lower()


def _emails_unicos(valores: Iterable[str]) -> List[str]:
    vistos: Set[str] = set()
    saida: List[str] = []
    for valor in valores:
        email = _normalizar_email(valor)
        if not email or email in vistos:
            continue
        vistos.add(email)
        saida.append(email)
    return saida


def _emails_fallback_config() -> List[str]:
    return _emails_unicos(getattr(settings, "ALERTAS_EMAILS_INTERNOS", []) or [])


def _setor_usuario(user):
    try:
        usuario_sistema = getattr(user, "usuario_sistema", None)
    except Exception:
        usuario_sistema = None
    if not usuario_sistema:
        return None
    return getattr(usuario_sistema, "setor", None)


def _usuarios_ativos_com_email():
    User = get_user_model()
    return User.objects.filter(is_active=True).exclude(email__isnull=True).exclude(email__exact="")


def emails_usuarios_do_setor(setor) -> List[str]:
    if not setor:
        return []
    emails = []
    for user in _usuarios_ativos_com_email():
        setor_user = _setor_usuario(user)
        if setor_user and getattr(setor_user, "id", None) == getattr(setor, "id", None):
            emails.append(user.email)
    return _emails_unicos(emails)


def emails_envolvidos_internos_sac(sac) -> List[str]:
    emails: List[str] = []

    usuario_abertura = getattr(sac, "usuario_abertura", None)
    if usuario_abertura and getattr(usuario_abertura, "email", None):
        emails.append(usuario_abertura.email)

    setor_atual = getattr(sac, "setor_atual", None)
    emails.extend(emails_usuarios_do_setor(setor_atual))

    historicos = (
        SacHistorico.objects.filter(sac=sac)
        .select_related("usuario", "setor_origem", "setor_destino")
        .order_by("data_evento", "id")
    )
    for hist in historicos:
        usuario = getattr(hist, "usuario", None)
        if usuario and getattr(usuario, "email", None):
            emails.append(usuario.email)

        emails.extend(emails_usuarios_do_setor(getattr(hist, "setor_origem", None)))
        emails.extend(emails_usuarios_do_setor(getattr(hist, "setor_destino", None)))

    emails = _emails_unicos(emails)
    if emails:
        return emails
    return _emails_fallback_config()


def emails_cliente_sac(sac) -> List[str]:
    emails: List[str] = []
    cliente = getattr(sac, "cliente", None)

    if cliente is not None:
        for attr in (
            "email",
            "email_principal",
            "contato_email",
            "email_1",
            "email_2",
        ):
            valor = getattr(cliente, attr, None)
            if valor:
                emails.append(valor)

    for attr in ("email_1", "email_2", "email_usuario_contato"):
        valor = getattr(sac, attr, None)
        if valor:
            emails.append(valor)

    return _emails_unicos(emails)
