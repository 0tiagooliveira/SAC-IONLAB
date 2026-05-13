from core.models import FluxoAcaoSetor


def resolver_fluxo(sac, acao_codigo=None):
    """Motor central de fluxo do SAC.

    Nesta etapa ele fica seguro para uso em validacao paralela.
    Nao altera regras, nao salva banco e retorna None se nao encontrar fluxo.
    """
    try:
        setor = getattr(sac, "setor_atual", None)
        status = getattr(sac, "status_atual", None)
        acao = getattr(sac, "acao_em_espera_atual", None)

        filtros = {
            "setor_origem": setor,
            "status_origem": status,
        }
        if acao_codigo and hasattr(FluxoAcaoSetor, "acao_origem"):
            filtros["acao_origem__codigo"] = acao_codigo
        elif acao is not None:
            filtros["acao_origem"] = acao

        fluxo = FluxoAcaoSetor.objects.filter(**filtros).first()
        if not fluxo:
            return None

        return {
            "proximo_status": getattr(fluxo, "status_destino", None),
            "proximo_setor": getattr(fluxo, "setor_destino", None),
            "acao_espera": getattr(fluxo, "acao_destino", None),
            "fluxo": fluxo,
        }
    except Exception:
        return None
