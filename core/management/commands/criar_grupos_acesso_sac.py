from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from core.models import UsuarioSistema


PAGINAS = [
    'acessar_painel',
    'acessar_dashboard_sla',
    'acessar_pesquisa_sacs',
    'acessar_abertura_sac',
    'acessar_comercial',
    'acessar_logistica',
    'acessar_assessoria',
    'acessar_assistencia_tecnica',
    'acessar_diretoria',
    'acessar_financeiro',
    'acessar_licitacao',
]

CADASTROS_BASICOS = [
    'view_empresa', 'add_empresa', 'change_empresa',
    'view_cliente', 'add_cliente', 'change_cliente',
    'view_clientecontato', 'add_clientecontato', 'change_clientecontato',
    'view_notafiscal', 'add_notafiscal', 'change_notafiscal',
    'view_itemnotafiscal', 'add_itemnotafiscal', 'change_itemnotafiscal',
    'view_rastreionotaitem', 'add_rastreionotaitem', 'change_rastreionotaitem',
]

CADASTROS_ADMIN = [
    'acessar_admin_cadastros',
    'acessar_importacoes',
    'retificar_sac',
    'view_setor', 'add_setor', 'change_setor',
    'view_statussac', 'add_statussac', 'change_statussac',
    'view_acaoemespera', 'add_acaoemespera', 'change_acaoemespera',
    'view_fluxoacaosetor', 'add_fluxoacaosetor', 'change_fluxoacaosetor',
    'view_tipoocorrencia', 'add_tipoocorrencia', 'change_tipoocorrencia',
    'view_tipoproblema', 'add_tipoproblema', 'change_tipoproblema',
    'view_tratativaproblema', 'add_tratativaproblema', 'change_tratativaproblema',
    'view_tecnicoexterno', 'add_tecnicoexterno', 'change_tecnicoexterno',
    'view_pecatabelapreco', 'add_pecatabelapreco', 'change_pecatabelapreco',
    'view_vendedor', 'add_vendedor', 'change_vendedor',
]

GRUPOS = {
    'SAC - Administrador do Sistema': PAGINAS + CADASTROS_BASICOS + CADASTROS_ADMIN,
    'SAC - GestÃ£o Geral': PAGINAS + ['acessar_admin_cadastros'] + CADASTROS_BASICOS,
    'SAC - Comercial': ['acessar_painel', 'acessar_dashboard_sla', 'acessar_pesquisa_sacs', 'acessar_comercial'],
    'SAC - LogÃ­stica': ['acessar_painel', 'acessar_dashboard_sla', 'acessar_pesquisa_sacs', 'acessar_logistica'],
    'SAC - Assessoria CientÃ­fica': ['acessar_painel', 'acessar_dashboard_sla', 'acessar_pesquisa_sacs', 'acessar_assessoria'],
    'SAC - AssistÃªncia TÃ©cnica': ['acessar_painel', 'acessar_dashboard_sla', 'acessar_pesquisa_sacs', 'acessar_assistencia_tecnica'],
    'SAC - Diretoria': ['acessar_painel', 'acessar_dashboard_sla', 'acessar_pesquisa_sacs', 'acessar_diretoria'],
    'SAC - Financeiro': ['acessar_painel', 'acessar_dashboard_sla', 'acessar_pesquisa_sacs', 'acessar_financeiro'],
    'SAC - LicitaÃ§Ã£o': ['acessar_painel', 'acessar_dashboard_sla', 'acessar_pesquisa_sacs', 'acessar_licitacao'],
}


class Command(BaseCommand):
    help = 'Cria/atualiza grupos padrÃ£o de acesso do SAC.'

    def handle(self, *args, **options):
        ct_usuario = ContentType.objects.get_for_model(UsuarioSistema)
        permissoes_por_codigo = {p.codename: p for p in Permission.objects.all()}

        for nome_grupo, codigos in GRUPOS.items():
            grupo, _ = Group.objects.get_or_create(name=nome_grupo)
            for codigo in codigos:
                if codigo.startswith('acessar_'):
                    perm = Permission.objects.filter(content_type=ct_usuario, codename=codigo).first()
                else:
                    perm = permissoes_por_codigo.get(codigo)
                if perm:
                    grupo.permissions.add(perm)
                else:
                    self.stdout.write(self.style.WARNING(f'PermissÃ£o nÃ£o encontrada: {codigo}'))
            self.stdout.write(self.style.SUCCESS(f'Grupo atualizado: {nome_grupo}'))

