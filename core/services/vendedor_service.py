from __future__ import annotations

from core.models import Vendedor


def normalizar_texto(valor):
    return str(valor or '').strip()


def normalizar_codigo_excel(valor):
    texto = normalizar_texto(valor)
    if not texto:
        return None
    try:
        numero = float(texto.replace(',', '.'))
        if numero.is_integer():
            return str(int(numero))
    except (TypeError, ValueError):
        pass
    if texto.endswith('.0'):
        return texto[:-2]
    return texto


def atualizar_cadastro_vendedor(codigo, nome):
    codigo = normalizar_codigo_excel(codigo)
    nome = normalizar_texto(nome)

    if not codigo and not nome:
        return None

    nome_final = nome or codigo or ''
    codigo_final = codigo or nome_final

    vendedor = Vendedor.objects.filter(codigo=codigo_final).first() if codigo_final else None
    if vendedor:
        alterou = False
        if nome_final and vendedor.nome != nome_final:
            vendedor.nome = nome_final
            alterou = True
        if getattr(vendedor, 'email', None) is None:
            vendedor.email = ''
            alterou = True
        if not getattr(vendedor, 'ativo', True):
            vendedor.ativo = True
            alterou = True
        if alterou:
            vendedor.save()
        return vendedor

    vendedor = Vendedor.objects.filter(nome=nome_final).first() if nome_final else None
    if vendedor:
        alterou = False
        if codigo_final and vendedor.codigo != codigo_final:
            vendedor.codigo = codigo_final
            alterou = True
        if getattr(vendedor, 'email', None) is None:
            vendedor.email = ''
            alterou = True
        if not getattr(vendedor, 'ativo', True):
            vendedor.ativo = True
            alterou = True
        if alterou:
            vendedor.save()
        return vendedor

    vendedor = Vendedor(codigo=codigo_final, nome=nome_final, ativo=True)
    if hasattr(vendedor, 'email'):
        vendedor.email = ''
    vendedor.save()
    return vendedor
