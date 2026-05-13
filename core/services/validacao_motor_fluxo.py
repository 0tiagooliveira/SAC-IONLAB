from core.services.motor_fluxo_sac import resolver_fluxo

try:
    from core.utils_log_seguro import registrar_erro
except Exception:  # fallback defensivo
    def registrar_erro(contexto, erro):
        return None


def validar_motor_em_paralelo(sac, esperado=None, contexto="motor_fluxo"):
    """Executa o motor em paralelo sem alterar o comportamento atual.

    Retorna um dicionario com o resultado do motor e eventual divergencia.
    Nao salva no banco, nao altera status, setor ou acao.
    """
    try:
        resultado = resolver_fluxo(sac)
        divergencias = []

        if esperado and resultado:
            for chave, valor_esperado in esperado.items():
                valor_motor = resultado.get(chave)
                if valor_esperado is not None and valor_motor != valor_esperado:
                    divergencias.append({
                        "campo": chave,
                        "esperado": valor_esperado,
                        "motor": valor_motor,
                    })

        if divergencias:
            registrar_erro(contexto, "Divergencia motor fluxo: {}".format(divergencias))

        return {
            "ok": True,
            "resultado": resultado,
            "divergencias": divergencias,
        }
    except Exception as exc:
        registrar_erro(contexto, exc)
        return {
            "ok": False,
            "resultado": None,
            "divergencias": [],
            "erro": str(exc),
        }
