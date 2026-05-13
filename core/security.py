from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from core.access_config import NIVEL_ALTERAR, NIVEL_VISUALIZAR
from core.services.permissoes_simples import usuario_pode_tela


URL_TELA_MAP = {
    'painel_navegacao': 'painel',
    'dashboard_sla': 'dashboard_sla',
    'auditoria_visual_sac': 'dashboard_sla',
    'cancelar_sac': 'cancelar_sac',
    'pesquisa_sacs': 'pesquisa_sacs',
    'abrir_sac': 'abertura_sac',
    'retificar_sac': 'retificar_sac',
    'gestao_sac': 'gestao_sac',
    'analise_comercial_sac_lista': 'gestao_comercial',
    'analise_comercial_sac': 'gestao_comercial',
    'gestao_logistica_lista': 'gestao_logistica',
    'gestao_logistica': 'gestao_logistica',
    'assessoria_cientifica': 'assessoria_cientifica',
    'analise_tecnica_sac': 'assessoria_cientifica',
    'assistencia_tecnica_lista': 'assistencia_tecnica',
    'assistencia_tecnica': 'assistencia_tecnica',
    'analise_diretoria': 'diretoria',
    'gestao_financeira_lista': 'gestao_financeira',
    'gestao_financeira': 'gestao_financeira',
    'gestao_licitacao_lista': 'gestao_licitacao',
    'gestao_licitacao': 'gestao_licitacao',
    'importar': 'importacoes',
    'importar_rastreios': 'importacoes',
    'importar_tabela_pecas': 'importacoes',
    'executar_correcao_banco': 'importacoes',
}


class UsuarioSistemaPermissaoMiddleware:
    """
    Camada de acesso simples por pagina.
    - Superusuario sempre passa.
    - GET exige Visualizar.
    - POST/alteracoes exigem Incluir/Alterar.
    - Se nao houver permissao nova cadastrada, o sistema respeita permissoes antigas.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = getattr(request, 'resolver_match', None)
        url_name = getattr(match, 'url_name', None)
        path = request.path or ''

        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            return None

        if url_name in {'login_interno', 'logout_interno', 'raiz_para_intra'}:
            return None

        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None

        if user.is_superuser:
            return None

        if path.startswith('/admin/'):
            if not usuario_pode_tela(user, 'cadastros'):
                messages.error(request, 'Usuário sem acesso a essa pagina')
                return redirect('painel_navegacao')
            return None

        if path.startswith('/api/'):
            return None

        tela = URL_TELA_MAP.get(url_name)
        if not tela:
            return None

        perfil = getattr(user, 'usuario_sistema', None)
        if not perfil or not perfil.ativo:
            messages.error(request, 'Usuário sem perfil ativo no sistema. Solicite liberação ao administrador.')
            logout(request)
            return redirect('login_interno')

        nivel_minimo = NIVEL_ALTERAR if request.method not in {'GET', 'HEAD', 'OPTIONS'} else NIVEL_VISUALIZAR
        if not usuario_pode_tela(user, tela, nivel_minimo):
            messages.error(request, 'Usuário sem acesso a essa pagina')
            return redirect('painel_navegacao')

        return None
