from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from core.views import (
    login_interno,
    logout_interno,
    importar_notas_excel,
    importar_rastreios_excel,
    importar_tabela_pecas_excel,
    executar_correcao_banco,
    abrir_sac,
    analise_tecnica_sac,
    analise_comercial_sac,
    gestao_licitacao,
    buscar_clientes,
    listar_contatos_cliente,
    listar_notas_cliente,
    listar_itens_nota,
    listar_rastreios_item,
    buscar_tipo_ocorrencia,
    historico_item_rastreio,
    proximo_numero_sac_api,
    painel_navegacao,
    pesquisa_sacs,
    gestao_sac,
    assessoria_cientifica,
    analise_diretoria,
    buscar_serial_api,
    gestao_logistica,
    buscar_vendedor_por_nota,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_interno, name='login_interno'),
    path('logout/', logout_interno, name='logout_interno'),

    # RAIZ → /intra/
    path('', RedirectView.as_view(url='/intra/', permanent=False), name='raiz_para_intra'),

    # PAINEL
    path('intra/', painel_navegacao, name='painel_navegacao'),

    # GESTÃO
    path('sac/gestao/', gestao_sac, name='gestao_sac'),
    path('sac/pesquisa/', pesquisa_sacs, name='pesquisa_sacs'),

    # ASSESSORIA
    path('sac/assessoria-cientifica/', assessoria_cientifica, name='assessoria_cientifica'),
    path('sac/diretoria/', analise_diretoria, name='analise_diretoria'),

    # IMPORTAÇÕES
    path('importar/', importar_notas_excel, name='importar'),
    path('importar-rastreios/', importar_rastreios_excel, name='importar_rastreios'),
    path('importar-tabela-pecas/', importar_tabela_pecas_excel, name='importar_tabela_pecas'),
    path('corrigir-banco/', executar_correcao_banco, name='executar_correcao_banco'),

    # SAC
    path('sac/abrir/', abrir_sac, name='abrir_sac'),
    path('sac/<int:sac_id>/analise-tecnica/', analise_tecnica_sac, name='analise_tecnica_sac'),
    path('sac/analise-comercial/', analise_comercial_sac, name='analise_comercial_sac_lista'),
    path('sac/<int:sac_id>/analise-comercial/', analise_comercial_sac, name='analise_comercial_sac'),
    # GESTÃO LOGÍSTICA (BASE E POR SAC)
    path('sac/gestao-logistica/', gestao_logistica, name='gestao_logistica_lista'),
    path('sac/<int:sac_id>/gestao-logistica/', gestao_logistica, name='gestao_logistica'),

    # APIs
    path('api/clientes/', buscar_clientes, name='buscar_clientes'),
    path('api/contatos-cliente/', listar_contatos_cliente, name='listar_contatos_cliente'),
    path('api/notas-cliente/', listar_notas_cliente, name='listar_notas_cliente'),
    path('api/itens-nota/', listar_itens_nota, name='listar_itens_nota'),
    path('api/rastreios-item/', listar_rastreios_item, name='listar_rastreios_item'),
    path('api/tipo-ocorrencia/', buscar_tipo_ocorrencia, name='buscar_tipo_ocorrencia'),
    path('api/historico-item-rastreio/', historico_item_rastreio, name='historico_item_rastreio'),
    path('api/proximo-numero-sac/', proximo_numero_sac_api, name='proximo_numero_sac_api'),
    path('api/buscar-serial/', buscar_serial_api, name='buscar_serial_api'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# Gestão Licitação
urlpatterns += [path('sac/gestao-licitacao/', gestao_licitacao, name='gestao_licitacao_lista'), path('sac/<int:sac_id>/gestao-licitacao/', gestao_licitacao, name='gestao_licitacao')]
