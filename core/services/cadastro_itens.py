from __future__ import annotations

import re
import unicodedata
from typing import Any


PALAVRAS_MINUSCULAS = {
    'a', 'as', 'ao', 'aos', 'da', 'das', 'de', 'do', 'dos', 'e', 'em',
    'na', 'nas', 'no', 'nos', 'para', 'por', 'sem', 'sob', 'sobre', 'com',
}


def texto_planilha(valor: Any) -> str:
    if valor is None:
        return ''
    try:
        import pandas as pd
        if pd.isna(valor):
            return ''
    except Exception:
        pass
    texto = str(valor).strip()
    if texto.endswith('.0'):
        try:
            numero = float(texto.replace(',', '.'))
            if numero.is_integer():
                return str(int(numero))
        except (TypeError, ValueError):
            pass
    return ' '.join(texto.split())


def _capitalizar_parte(parte: str) -> str:
    if not parte:
        return parte
    if re.search(r'\d', parte):
        return parte.upper().replace('VCC', 'VCC')
    if len(parte) <= 3 and parte.isalpha() and parte.upper() == parte:
        return parte
    return parte[:1].upper() + parte[1:].lower()


def normalizar_texto_cadastro(valor: Any) -> str:
    texto = texto_planilha(valor)
    if not texto:
        return ''

    texto = texto.replace('–', '-').replace('—', '-')
    tokens = re.split(r'(\s+|-|/)', texto)
    resultado = []
    indice_palavra = 0
    for token in tokens:
        if not token or token.isspace() or token in {'-', '/'}:
            resultado.append(token)
            continue
        palavra_base = unicodedata.normalize('NFKD', token).encode('ascii', 'ignore').decode('ascii').lower()
        if indice_palavra > 0 and palavra_base in PALAVRAS_MINUSCULAS:
            resultado.append(token.lower())
        else:
            resultado.append(_capitalizar_parte(token))
        indice_palavra += 1
    return ''.join(resultado).strip()


def normalizar_voltagem(valor: Any) -> str:
    texto = texto_planilha(valor)
    if not texto:
        return ''
    texto = texto.upper().replace('VOLTS', 'V').replace('VOLT', 'V')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def normalizar_referencia(valor: Any) -> str:
    return texto_planilha(valor).upper()


def valor_por_coluna(row, *nomes: str) -> Any:
    for nome in nomes:
        if nome in row:
            return row.get(nome)
    return None
