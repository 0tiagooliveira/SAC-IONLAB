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
    retificar_sac,
    analise_tecnica_sac,
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
    buscar_serial_api,
    buscar_vendedor_por_nota,
)
from core.views_modular.views_gestao import gestao_sac
from core.views_modular.views_logistica import gestao_logistica
from core.views_modular.views_comercial import analise_comercial_sac
from core.views_modular.views_assessoria import assessoria_cientifica
from core.views_modular.views_diretoria import analise_diretoria
from core.views_modular.views_licitacao import gestao_licitacao
from core.views_modular.views_assistencia_tecnica import gestao_assistencia_tecnica
from core.views_modular.views_financeiro import gestao_financeira
from core.views_modular.views_dashboard_sla import dashboard_sla, auditoria_visual_sac, cancelar_sac

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_interno, name='login_interno'),
    path('logout/', logout_interno, name='logout_interno'),
    path('', RedirectView.as_view(url='/intra/', permanent=False), name='raiz_para_intra'),
    path('intra/', painel_navegacao, name='painel_navegacao'),
    path('sac/dashboard/', dashboard_sla, name='dashboard_sla'),
    path('sac/gestao/', gestao_sac, name='gestao_sac'),
    path('sac/pesquisa/', pesquisa_sacs, name='pesquisa_sacs'),
    path('sac/assessoria-cientifica/', assessoria_cientifica, name='assessoria_cientifica'),
    path('sac/diretoria/', analise_diretoria, name='analise_diretoria'),
    path('importar/', importar_notas_excel, name='importar'),
    path('importar-rastreios/', importar_rastreios_excel, name='importar_rastreios'),
    path('importar-tabela-pecas/', importar_tabela_pecas_excel, name='importar_tabela_pecas'),
    path('corrigir-banco/', executar_correcao_banco, name='executar_correcao_banco'),
    path('sac/abrir/', abrir_sac, name='abrir_sac'),
    path('sac/<int:sac_id>/retificar/', retificar_sac, name='retificar_sac'),
    path('sac/<int:sac_id>/analise-tecnica/', analise_tecnica_sac, name='analise_tecnica_sac'),
    path('sac/analise-comercial/', analise_comercial_sac, name='analise_comercial_sac_lista'),
    path('sac/<int:sac_id>/analise-comercial/', analise_comercial_sac, name='analise_comercial_sac'),
    path('sac/gestao-logistica/', gestao_logistica, name='gestao_logistica_lista'),
    path('sac/<int:sac_id>/gestao-logistica/', gestao_logistica, name='gestao_logistica'),
    path('sac/assistencia-tecnica/', gestao_assistencia_tecnica, name='assistencia_tecnica_lista'),
    path('sac/<int:sac_id>/assistencia-tecnica/', gestao_assistencia_tecnica, name='assistencia_tecnica'),
    path('sac/gestao-financeira/', gestao_financeira, name='gestao_financeira_lista'),
    path('sac/<int:sac_id>/gestao-financeira/', gestao_financeira, name='gestao_financeira'),
    path('sac/<int:sac_id>/auditoria/', auditoria_visual_sac, name='auditoria_visual_sac'),
    path('sac/<int:sac_id>/cancelar/', cancelar_sac, name='cancelar_sac'),
    path('api/clientes/', buscar_clientes, name='buscar_clientes'),
    path('api/contatos-cliente/', listar_contatos_cliente, name='listar_contatos_cliente'),
    path('api/notas-cliente/', listar_notas_cliente, name='listar_notas_cliente'),
    path('api/itens-nota/', listar_itens_nota, name='listar_itens_nota'),
    path('api/rastreios-item/', listar_rastreios_item, name='listar_rastreios_item'),
    path('api/tipo-ocorrencia/', buscar_tipo_ocorrencia, name='buscar_tipo_ocorrencia'),
    path('api/historico-item-rastreio/', historico_item_rastreio, name='historico_item_rastreio'),
    path('api/proximo-numero-sac/', proximo_numero_sac_api, name='proximo_numero_sac_api'),
    path('api/buscar-serial/', buscar_serial_api, name='buscar_serial_api'),
    path('api/buscar-vendedor-por-nota/', buscar_vendedor_por_nota, name='buscar_vendedor_por_nota'),
    path('api/buscar-vendedor/', buscar_vendedor_por_nota, name='buscar_vendedor_por_nota_alias'),
]

urlpatterns += [
    path('sac/gestao-licitacao/', gestao_licitacao, name='gestao_licitacao_lista'),
    path('sac/<int:sac_id>/gestao-licitacao/', gestao_licitacao, name='gestao_licitacao'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
