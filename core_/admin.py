from django.contrib import admin
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

from .models import (
    AcaoEmEspera,
    Cliente,
    ClienteContato,
    Empresa,
    FluxoAcaoSetor,
    ItemNotaFiscal,
    NaturezaOperacao,
    NotaFiscal,
    OrcamentoTecnicoExterno,
    OrcamentoTecnicoExternoPeca,
    PecaTabelaPreco,
    RastreioNotaItem,
    SAC,
    SACAnexo,
    SACItem,
    SacAnaliseTecnica,
    SacHistorico,
    Setor,
    StatusSAC,
    TecnicoExterno,
    TipoOcorrencia,
    TipoProblema,
    TratativaProblema,
    UsuarioSistema,
    Vendedor,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "razao_social", "ativo")
    search_fields = ("codigo", "razao_social")
    list_filter = ("ativo",)


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "ativo")
    search_fields = ("nome",)
    list_filter = ("ativo",)
    ordering = ("nome",)


@admin.register(AcaoEmEspera)
class AcaoEmEsperaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "setor_destino", "ativo")
    search_fields = ("nome", "setor_destino__nome")
    list_filter = ("ativo", "setor_destino")


@admin.register(UsuarioSistema)
class UsuarioSistemaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome_completo", "user", "setor", "ativo")
    search_fields = ("nome_completo", "user__username", "setor__nome")
    list_filter = ("ativo", "setor")


@admin.register(StatusSAC)
class StatusSACAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "nome", "ativo")
    search_fields = ("nome", "codigo")
    list_filter = ("ativo",)


@admin.register(TipoOcorrencia)
class TipoOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "nome", "setor", "acao_em_espera", "ativo")
    search_fields = ("nome", "codigo")
    list_filter = ("ativo", "setor", "acao_em_espera")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("id", "empresa", "codigo_interno", "razao_social", "nome", "uf", "ativo")
    search_fields = ("codigo_interno", "razao_social", "nome")
    list_filter = ("ativo", "empresa", "uf")


@admin.register(ClienteContato)
class ClienteContatoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "nome_contato", "whatsapp", "telefone", "email_1", "ativo")
    search_fields = ("cliente__razao_social", "cliente__nome", "nome_contato", "whatsapp", "telefone", "email_1")
    list_filter = ("ativo",)


@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ("id", "empresa", "numero_nf", "numero", "serie_nf", "cliente", "data_emissao")
    search_fields = ("numero_nf", "numero", "cliente__razao_social", "cliente__nome")
    list_filter = ("empresa", "data_emissao")
    change_list_template = "admin/core/notafiscal/change_list.html"

    def _get_importar_notas_url(self):
        for nome in ("importar_notas_excel", "importar"):
            try:
                return reverse(nome)
            except NoReverseMatch:
                continue
        return "/importar/"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["botao_importar_url"] = self._get_importar_notas_url()
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(ItemNotaFiscal)
class ItemNotaFiscalAdmin(admin.ModelAdmin):
    list_display = ("id", "nota_fiscal", "codigo_produto", "descricao_item", "quantidade", "valor_total_item")
    search_fields = ("codigo_produto", "descricao_item", "item")


@admin.register(RastreioNotaItem)
class RastreioNotaItemAdmin(admin.ModelAdmin):
    list_display = ("id", "empresa", "numero_nf", "codigo_produto", "serial_lote", "tipo")
    search_fields = ("numero_nf", "codigo_produto", "serial_lote")
    change_list_template = "admin/core/rastreionotaitem/change_list.html"

    def _get_importar_rastreios_url(self):
        for nome in ("importar_rastreios_excel", "importar_rastreios"):
            try:
                return reverse(nome)
            except NoReverseMatch:
                continue
        return "/importar-rastreios/"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["botao_importar_url"] = self._get_importar_rastreios_url()
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(TratativaProblema)
class TratativaProblemaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "ativo", "criado_em")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(TipoProblema)
class TipoProblemaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "ativo", "criado_em")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(TecnicoExterno)
class TecnicoExternoAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "telefone", "whatsapp", "email", "cidade", "estado", "ativo")
    search_fields = ("nome", "telefone", "whatsapp", "email", "cidade")
    list_filter = ("ativo", "estado")


@admin.register(PecaTabelaPreco)
class PecaTabelaPrecoAdmin(admin.ModelAdmin):
    list_display = ("id", "referencia", "descricao", "valor_unitario", "grupo", "custo", "ativo")
    search_fields = ("referencia", "descricao", "grupo")
    list_filter = ("ativo",)
    change_list_template = "admin/core/pecatabelapreco/change_list.html"
    change_form_template = "admin/core/pecatabelapreco/change_form.html"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["botao_importar_url"] = reverse("importar_tabela_pecas")
        return super().changelist_view(request, extra_context=extra_context)


class SACItemInline(admin.TabularInline):
    model = SACItem
    extra = 0


class SACAnexoInline(admin.TabularInline):
    model = SACAnexo
    extra = 0


@admin.register(SAC)
class SACAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero",
        "empresa",
        "cliente",
        "nota_fiscal",
        "titulo",
        "status_atual",
        "setor_atual",
        "acao_em_espera",
        "status_inicial",
        "data_abertura",
    )
    list_filter = ("status_atual", "setor_atual", "empresa", "data_abertura")
    search_fields = ("numero", "titulo", "cliente__razao_social", "cliente__nome")
    inlines = [SACItemInline, SACAnexoInline]


@admin.register(SACItem)
class SACItemAdmin(admin.ModelAdmin):
    list_display = ("id", "sac", "item_nota_fiscal", "tipo_ocorrencia", "tipo_rastreio", "numero_rastreio", "quantidade_com_problema")


@admin.register(SACAnexo)
class SACAnexoAdmin(admin.ModelAdmin):
    list_display = ("id", "sac", "arquivo")


@admin.register(SacHistorico)
class SacHistoricoAdmin(admin.ModelAdmin):
    list_display = ("id", "sac", "data_evento", "usuario", "status_anterior", "status_novo", "setor_destino", "acao_executada")
    list_filter = ("status_novo", "setor_destino", "data_evento")
    search_fields = ("sac__numero", "acao_executada", "observacao")


@admin.register(SacAnaliseTecnica)
class SacAnaliseTecnicaAdmin(admin.ModelAdmin):
    list_display = ("id", "sac", "tratativa_problema", "tipo_problema", "proximo_status_sugerido", "usuario_responsavel", "data_analise")
    list_filter = ("tratativa_problema", "tipo_problema", "proximo_status_sugerido")
    search_fields = ("sac__numero", "observacao_tecnica")


class OrcamentoTecnicoExternoPecaInline(admin.TabularInline):
    model = OrcamentoTecnicoExternoPeca
    extra = 0


@admin.register(OrcamentoTecnicoExterno)
class OrcamentoTecnicoExternoAdmin(admin.ModelAdmin):
    list_display = ("id", "sac", "tecnico_externo", "precisa_peca_reposicao", "valor_total_pecas", "valor_total_horas", "valor_total_geral", "atualizado_em")
    search_fields = ("sac__numero", "tecnico_externo__nome")
    inlines = [OrcamentoTecnicoExternoPecaInline]


@admin.register(OrcamentoTecnicoExternoPeca)
class OrcamentoTecnicoExternoPecaAdmin(admin.ModelAdmin):
    list_display = ("id", "orcamento", "referencia", "descricao", "quantidade", "valor_unitario", "valor_total")
    search_fields = ("referencia", "descricao", "orcamento__sac__numero")


@admin.register(NaturezaOperacao)
class NaturezaOperacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(FluxoAcaoSetor)
class FluxoAcaoSetorAdmin(admin.ModelAdmin):
    list_display = ("id", "acao_atual", "setor_atual", "proxima_acao", "proximo_setor", "status_destino", "ativo")
    search_fields = ("acao_atual__nome", "setor_atual__nome", "proxima_acao__nome", "proximo_setor__nome", "status_destino__nome")
    list_filter = ("ativo", "acao_atual", "setor_atual", "proximo_setor", "status_destino")
    autocomplete_fields = ("acao_atual", "setor_atual", "proxima_acao", "proximo_setor", "status_destino")
    ordering = ("acao_atual__nome", "setor_atual__nome", "proxima_acao__nome", "status_destino__nome")

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "nome", "email", "ativo")
    search_fields = ("codigo", "nome", "email")
    list_filter = ("ativo",)
    ordering = ("nome",)
