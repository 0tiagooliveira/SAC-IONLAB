from __future__ import annotations

import re


ACRONIMOS = {
    "AC",
    "ANVISA",
    "CNPJ",
    "CPF",
    "EPP",
    "ID",
    "IONLAB",
    "LTDA",
    "ME",
    "NF",
    "NFE",
    "NR",
    "R$",
    "SAC",
    "SKU",
    "SLA",
}


def _deve_padronizar_caixa(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    if len(letras) < 6:
        return False
    maiusculas = sum(1 for c in letras if c.isupper())
    minusculas = sum(1 for c in letras if c.islower())
    return maiusculas >= max(6, minusculas * 3)


def _proteger_termos(texto: str):
    protegidos = []

    def guardar(match):
        protegidos.append(match.group(0))
        return f"¤{len(protegidos) - 1}¤"

    texto = re.sub(r"\b(?=[A-Z0-9/-]*\d)[A-Z0-9]+(?:[-/][A-Z0-9]+)+\b", guardar, texto)
    texto = re.sub(r"\b(?=[A-Z0-9.-]*\d)[A-Z0-9.-]{2,}\b", guardar, texto)
    for termo in sorted(ACRONIMOS, key=len, reverse=True):
        texto = re.sub(rf"\b{re.escape(termo)}\b", guardar, texto, flags=re.IGNORECASE)
    return texto, protegidos


def _restaurar_termos(texto: str, protegidos):
    for idx, valor in enumerate(protegidos):
        texto = texto.replace(f"¤{idx}¤", valor)
    return texto


def _capitalizar_frases(texto: str) -> str:
    texto = texto.lower()

    def capitalizar(match):
        return match.group(1) + match.group(2).upper()

    texto = re.sub(r"(^|[.!?]\s+|-\s+)([a-záàâãéêíóôõúç])", capitalizar, texto)
    texto = re.sub(r"(:\s*)([a-záàâãéêíóôõúç])", capitalizar, texto)
    texto = re.sub(r"\s+([,.;:!?])", r"\1", texto)
    return texto


def padronizar_caixa_texto(texto: str) -> str:
    if not texto:
        return ""
    linhas = []
    for linha in str(texto).splitlines():
        original = linha.strip()
        if not original or not _deve_padronizar_caixa(original):
            linhas.append(linha)
            continue
        prefixo = linha[: len(linha) - len(linha.lstrip())]
        sufixo = linha[len(linha.rstrip()) :]
        protegido, termos = _proteger_termos(original)
        ajustado = _capitalizar_frases(protegido)
        linhas.append(prefixo + _restaurar_termos(ajustado, termos) + sufixo)
    return "\n".join(linhas).strip()
