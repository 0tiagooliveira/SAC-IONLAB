from core.services.motor_fluxo_sac import resolver_fluxo


def _mesmo_obj(a, b):
    """Compara objetos Django por PK quando possível; fallback para texto."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    a_pk = getattr(a, "pk", None)
    b_pk = getattr(b, "pk", None)
    if a_pk is not None and b_pk is not None:
        return str(a_pk) == str(b_pk)
    return str(a) == str(b)


def aplicar_motor_comercial_seguro(sac, proximo_status, acao_em_espera, proximo_setor):
    """
    Ativa o motor no Comercial com trava de equivalencia.

    Regra de seguranca:
    - Se o motor chegar ao MESMO resultado da regra atual, retorna os objetos do motor.
    - Se divergir ou falhar, preserva 100% a regra atual.
    - Assim o motor entra sem quebrar comportamento existente.
    """
    try:
        motor = resolver_fluxo(sac)
        if not motor:
            return proximo_status, acao_em_espera, proximo_setor

        motor_status = motor.get("proximo_status")
        motor_acao = motor.get("acao_espera")
        motor_setor = motor.get("proximo_setor")

        equivalente = (
            _mesmo_obj(motor_status, proximo_status)
            and _mesmo_obj(motor_acao, acao_em_espera)
            and _mesmo_obj(motor_setor, proximo_setor)
        )

        if equivalente:
            return (
                motor_status or proximo_status,
                motor_acao or acao_em_espera,
                motor_setor or proximo_setor,
            )

        try:
            from core.services.motor_log import registrar_divergencia
            registrar_divergencia(
                getattr(sac, "id", "-"),
                {
                    "status_regra_atual": str(proximo_status),
                    "acao_regra_atual": str(acao_em_espera),
                    "setor_regra_atual": str(proximo_setor),
                },
                {
                    "status_motor": str(motor_status),
                    "acao_motor": str(motor_acao),
                    "setor_motor": str(motor_setor),
                },
            )
        except Exception:
            pass

        return proximo_status, acao_em_espera, proximo_setor
    except Exception:
        return proximo_status, acao_em_espera, proximo_setor
