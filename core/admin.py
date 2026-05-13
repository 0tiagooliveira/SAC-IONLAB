from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

from core.access_config import CADASTRO_ITENS, NIVEIS_ACESSO, TELAS_SISTEMA
from core.services.permissoes_simples import (
    item_cadastro_por_model,
    usuario_pode_cadastro,
    usuario_pode_tela,
)
from .models import (
    AcaoEmEspera,
    Cliente,
    ClienteContato,
    Empresa,
    FluxoAcaoSetor,
    ImportacaoLegadoSAC,
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
    PermissaoCadastroUsuario,
    PermissaoTelaUsuario,
    UsuarioSistema,
    Vendedor,
)


TELA_FIELD_NAMES = tuple(f"acesso_tela_{codigo}" for codigo, _label, _perm in TELAS_SISTEMA)
CADASTRO_FIELD_NAMES = tuple(f"acesso_cadastro_{codigo}" for codigo, _label in CADASTRO_ITENS)


class CadastroPermissaoAdminMixin:
    def _item_cadastro(self):
        return item_cadastro_por_model(self.model)

    def _pode_visualizar_item(self, request):
        item = self._item_cadastro()
        if not item:
            return True
        return usuario_pode_tela(request.user, 'cadastros') and usuario_pode_cadastro(request.user, item)

    def _pode_alterar_item(self, request):
        item = self._item_cadastro()
        if not item:
            return True
        return usuario_pode_tela(request.user, 'cadastros', 'alterar') and usuario_pode_cadastro(request.user, item, 'alterar')

    def _sem_acesso_response(self, request):
        messages.error(request, 'Usuário sem acesso a essa pagina')
        return redirect('admin:index')

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return self._pode_visualizar_item(request)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return self._pode_visualizar_item(request)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return self._pode_alterar_item(request)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return self._pode_alterar_item(request)

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return self._pode_alterar_item(request)

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            return self._sem_acesso_response(request)
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if not self.has_view_permission(request):
            return self._sem_acesso_response(request)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and not self.has_change_permission(request):
            return self._sem_acesso_response(request)
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        if not self.has_add_permission(request):
            return self._sem_acesso_response(request)
        return super().add_view(request, form_url, extra_context=extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        if not self.has_delete_permission(request):
            return self._sem_acesso_response(request)
        return super().delete_view(request, object_id, extra_context=extra_context)

    def history_view(self, request, object_id, extra_context=None):
        if not self.has_view_permission(request):
            return self._sem_acesso_response(request)
        return super().history_view(request, object_id, extra_context=extra_context)


class UsuarioPermissoesSimplesForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance if self.instance and self.instance.pk else None
        permissoes_telas = {}
        permissoes_cadastros = {}
        if user:
            permissoes_telas = {
                permissao.tela: permissao.nivel
                for permissao in PermissaoTelaUsuario.objects.filter(user=user)
            }
            permissoes_cadastros = {
                permissao.item: permissao.nivel
                for permissao in PermissaoCadastroUsuario.objects.filter(user=user)
            }
        for codigo, label, _perm_antiga in TELAS_SISTEMA:
            self.fields[f"acesso_tela_{codigo}"] = forms.ChoiceField(
                label=label,
                choices=NIVEIS_ACESSO,
                widget=forms.RadioSelect,
                initial=permissoes_telas.get(codigo, 'sem_acesso'),
                required=True,
            )
        for codigo, label in CADASTRO_ITENS:
            self.fields[f"acesso_cadastro_{codigo}"] = forms.ChoiceField(
                label=label,
                choices=NIVEIS_ACESSO,
                widget=forms.RadioSelect,
                initial=permissoes_cadastros.get(codigo, 'sem_acesso'),
                required=True,
            )

    def salvar_permissoes_simples(self, user):
        for codigo, _label, _perm_antiga in TELAS_SISTEMA:
            PermissaoTelaUsuario.objects.update_or_create(
                user=user,
                tela=codigo,
                defaults={'nivel': self.cleaned_data.get(f"acesso_tela_{codigo}", 'sem_acesso')},
            )
        for codigo, _label in CADASTRO_ITENS:
            PermissaoCadastroUsuario.objects.update_or_create(
                user=user,
                item=codigo,
                defaults={'nivel': self.cleaned_data.get(f"acesso_cadastro_{codigo}", 'sem_acesso')},
            )


@admin.register(Empresa)
class EmpresaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "codigo", "razao_social", "ativo")
    search_fields = ("codigo", "razao_social")
    list_filter = ("ativo",)


@admin.register(Setor)
class SetorAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "nome", "ativo")
    search_fields = ("nome",)
    list_filter = ("ativo",)
    ordering = ("nome",)


@admin.register(AcaoEmEspera)
class AcaoEmEsperaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "nome", "setor_destino", "ativo")
    search_fields = ("nome", "setor_destino__nome")
    list_filter = ("ativo", "setor_destino")


class UsuarioSistemaInline(admin.StackedInline):
    model = UsuarioSistema
    can_delete = False
    extra = 0
    max_num = 1
    verbose_name = "Dados internos do usuÃ¡rio"
    verbose_name_plural = "Dados internos do usuÃ¡rio"
    fields = ("nome_completo", "cpf", "setor", "ativo")
    autocomplete_fields = ("setor",)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UsuarioAuthAdmin(CadastroPermissaoAdminMixin, BaseUserAdmin):
    form = UsuarioPermissoesSimplesForm
    inlines = (UsuarioSistemaInline,)
    list_display = ("id", "username", "get_nome_completo", "get_cpf", "get_setor", "email", "is_active", "is_staff", "is_superuser")
    list_filter = ("is_active", "is_staff", "is_superuser", "groups", "usuario_sistema__setor")
    search_fields = ("username", "first_name", "last_name", "email", "usuario_sistema__nome_completo", "usuario_sistema__cpf")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        ("Login", {"fields": ("username", "password")}),
        ("Dados bÃ¡sicos", {"fields": ("first_name", "last_name", "email")}),
        ("Status", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Acessos simples por tela", {
            "fields": TELA_FIELD_NAMES,
            "description": "Selecione Incluir/Alterar, Visualizar ou Sem Acesso para cada tela do sistema.",
        }),
        ("Itens liberados na tela Cadastros", {
            "fields": CADASTRO_FIELD_NAMES,
            "description": "Defina exatamente quais itens da tela Cadastros este usuario pode visualizar ou alterar.",
        }),
        ("Acessos antigos por grupo", {"classes": ("collapse",), "fields": ("groups",), "description": "Mantido apenas para compatibilidade com acessos ja existentes."}),
        ("Acessos antigos individuais", {"classes": ("collapse",), "fields": ("user_permissions",), "description": "Mantido apenas para compatibilidade com acessos ja existentes."}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )

    def get_form(self, request, obj=None, **kwargs):
        fields = kwargs.get('fields')
        if fields:
            campos_dinamicos = set(TELA_FIELD_NAMES) | set(CADASTRO_FIELD_NAMES)
            kwargs['fields'] = tuple(campo for campo in fields if campo not in campos_dinamicos)
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if hasattr(form, 'salvar_permissoes_simples'):
            form.salvar_permissoes_simples(obj)

    def get_nome_completo(self, obj):
        perfil = getattr(obj, "usuario_sistema", None)
        return perfil.nome_completo if perfil else obj.get_full_name()
    get_nome_completo.short_description = "Nome completo"

    def get_cpf(self, obj):
        perfil = getattr(obj, "usuario_sistema", None)
        return perfil.cpf if perfil else ""
    get_cpf.short_description = "CPF"

    def get_setor(self, obj):
        perfil = getattr(obj, "usuario_sistema", None)
        return perfil.setor if perfil else ""
    get_setor.short_description = "Setor"


@admin.register(UsuarioSistema)
class UsuarioSistemaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "nome_completo", "cpf", "user", "setor", "ativo")
    search_fields = ("nome_completo", "cpf", "user__username", "user__email", "setor__nome")
    list_filter = ("ativo", "setor")
    autocomplete_fields = ("user", "setor")


@admin.register(StatusSAC)
class StatusSACAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "codigo", "nome", "ativo")
    search_fields = ("nome", "codigo")
    list_filter = ("ativo",)


@admin.register(TipoOcorrencia)
class TipoOcorrenciaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "codigo", "nome", "setor", "acao_em_espera", "ativo")
    search_fields = ("nome", "codigo")
    list_filter = ("ativo", "setor", "acao_em_espera")


@admin.register(Cliente)
class ClienteAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "empresa", "codigo_interno", "razao_social", "nome", "uf", "ativo")
    search_fields = ("codigo_interno", "razao_social", "nome")
    list_filter = ("ativo", "empresa", "uf")


@admin.register(ClienteContato)
class ClienteContatoAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "cliente", "nome_contato", "whatsapp", "telefone", "email_1", "ativo")
    search_fields = ("cliente__razao_social", "cliente__nome", "nome_contato", "whatsapp", "telefone", "email_1")
    list_filter = ("ativo",)


@admin.register(NotaFiscal)
class NotaFiscalAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
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
class ItemNotaFiscalAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "nota_fiscal", "codigo_produto", "descricao_item", "agrp", "origem", "modelo", "voltagem", "quantidade", "valor_total_item")
    search_fields = ("codigo_produto", "descricao_item", "item", "agrp", "origem", "modelo", "voltagem")


@admin.register(RastreioNotaItem)
class RastreioNotaItemAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
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
class TratativaProblemaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "nome", "ativo", "criado_em")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(TipoProblema)
class TipoProblemaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "nome", "ativo", "criado_em")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(TecnicoExterno)
class TecnicoExternoAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "nome", "telefone", "whatsapp", "email", "cidade", "estado", "ativo")
    search_fields = ("nome", "telefone", "whatsapp", "email", "cidade")
    list_filter = ("ativo", "estado")


@admin.register(PecaTabelaPreco)
class PecaTabelaPrecoAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "referencia", "descricao", "valor_unitario", "grupo", "origem", "modelo", "voltagem", "custo", "ativo")
    search_fields = ("referencia", "descricao", "grupo", "origem", "modelo", "voltagem")
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
class SACAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
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
class SACItemAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "sac", "item_nota_fiscal", "tipo_ocorrencia", "tipo_rastreio", "numero_rastreio", "quantidade_com_problema")


@admin.register(SACAnexo)
class SACAnexoAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "sac", "arquivo")


@admin.register(SacHistorico)
class SacHistoricoAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "sac", "data_evento", "usuario", "status_anterior", "status_novo", "setor_destino", "acao_executada")
    list_filter = ("status_novo", "setor_destino", "data_evento")
    search_fields = ("sac__numero", "acao_executada", "observacao")


@admin.register(ImportacaoLegadoSAC)
class ImportacaoLegadoSACAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "nome",
        "empresa",
        "status",
        "dry_run",
        "total_linhas",
        "total_sacs_planilha",
        "sacs_criados",
        "sacs_atualizados",
        "itens_criados",
        "itens_atualizados",
        "sacs_pulados",
        "criado_em",
    )
    list_filter = ("status", "dry_run", "empresa", "criado_em")
    search_fields = ("nome", "arquivo_origem")
    readonly_fields = ("criado_em", "atualizado_em", "detalhes")


@admin.register(SacAnaliseTecnica)
class SacAnaliseTecnicaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "sac", "tratativa_problema", "tipo_problema", "proximo_status_sugerido", "usuario_responsavel", "data_analise")
    list_filter = ("tratativa_problema", "tipo_problema", "proximo_status_sugerido")
    search_fields = ("sac__numero", "observacao_tecnica")


class OrcamentoTecnicoExternoPecaInline(admin.TabularInline):
    model = OrcamentoTecnicoExternoPeca
    extra = 0


@admin.register(OrcamentoTecnicoExterno)
class OrcamentoTecnicoExternoAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "sac", "tecnico_externo", "precisa_peca_reposicao", "valor_total_pecas", "valor_total_horas", "valor_total_geral", "atualizado_em")
    search_fields = ("sac__numero", "tecnico_externo__nome")
    inlines = [OrcamentoTecnicoExternoPecaInline]


@admin.register(OrcamentoTecnicoExternoPeca)
class OrcamentoTecnicoExternoPecaAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "orcamento", "referencia", "descricao", "quantidade", "valor_unitario", "valor_total")
    search_fields = ("referencia", "descricao", "orcamento__sac__numero")


@admin.register(NaturezaOperacao)
class NaturezaOperacaoAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "ativo")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(FluxoAcaoSetor)
class FluxoAcaoSetorAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "acao_atual", "setor_atual", "proxima_acao", "proximo_setor", "status_destino", "ativo")
    search_fields = ("acao_atual__nome", "setor_atual__nome", "proxima_acao__nome", "proximo_setor__nome", "status_destino__nome")
    list_filter = ("ativo", "acao_atual", "setor_atual", "proximo_setor", "status_destino")
    autocomplete_fields = ("acao_atual", "setor_atual", "proxima_acao", "proximo_setor", "status_destino")
    ordering = ("acao_atual__nome", "setor_atual__nome", "proxima_acao__nome", "status_destino__nome")

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Vendedor)
class VendedorAdmin(CadastroPermissaoAdminMixin, admin.ModelAdmin):
    list_display = ("id", "codigo", "nome", "email", "ativo")
    search_fields = ("codigo", "nome", "email")
    list_filter = ("ativo",)
    ordering = ("nome",)

