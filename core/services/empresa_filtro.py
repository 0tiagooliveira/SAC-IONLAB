from __future__ import annotations

from core.models import Empresa


def resolver_filtro_empresa(request):
    empresas = list(Empresa.objects.filter(ativo=True).order_by('razao_social', 'codigo'))
    codigo = (request.GET.get('empresa') or '').strip()
    empresa = None

    if codigo and codigo.lower() != 'agrupado':
        empresa = Empresa.objects.filter(ativo=True, codigo__iexact=codigo).first()

    codigo_selecionado = getattr(empresa, 'codigo', '') or 'agrupado'
    return empresa, {
        'empresas_filtro': empresas,
        'empresa_selecionada': empresa,
        'empresa_codigo_selecionado': codigo_selecionado,
        'empresa_agrupada': empresa is None,
        'empresa_query_param': '' if empresa is None else f'?empresa={codigo_selecionado}',
        'empresa_query_suffix': '' if empresa is None else f'&empresa={codigo_selecionado}',
    }


def aplicar_filtro_empresa(qs, empresa):
    if empresa is None:
        return qs
    return qs.filter(empresa_id=empresa.id)
