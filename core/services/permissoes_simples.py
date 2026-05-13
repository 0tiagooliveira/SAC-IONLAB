from core.access_config import (
    CADASTRO_MODEL_MAP,
    NIVEL_ALTERAR,
    NIVEL_RANK,
    NIVEL_SEM_ACESSO,
    NIVEL_VISUALIZAR,
    TELA_PERMISSOES_ANTIGAS,
)


def nivel_tela_usuario(user, tela):
    if not user or not user.is_authenticated:
        return NIVEL_SEM_ACESSO
    if user.is_superuser:
        return NIVEL_ALTERAR
    try:
        permissao = user.permissoes_telas_simples.filter(tela=tela).first()
    except Exception:
        permissao = None
    if permissao:
        return permissao.nivel
    perm_antiga = TELA_PERMISSOES_ANTIGAS.get(tela)
    if perm_antiga and user.has_perm(perm_antiga):
        return NIVEL_ALTERAR
    return NIVEL_SEM_ACESSO


def usuario_pode_tela(user, tela, nivel_minimo=NIVEL_VISUALIZAR):
    nivel = nivel_tela_usuario(user, tela)
    return NIVEL_RANK.get(nivel, 0) >= NIVEL_RANK.get(nivel_minimo, 1)


def nivel_cadastro_usuario(user, item):
    if not user or not user.is_authenticated:
        return NIVEL_SEM_ACESSO
    if user.is_superuser:
        return NIVEL_ALTERAR
    try:
        permissao = user.permissoes_cadastros_simples.filter(item=item).first()
    except Exception:
        permissao = None
    if permissao:
        return permissao.nivel
    if user.has_perm('core.acessar_admin_cadastros'):
        return NIVEL_ALTERAR
    return NIVEL_SEM_ACESSO


def usuario_pode_cadastro(user, item, nivel_minimo=NIVEL_VISUALIZAR):
    nivel = nivel_cadastro_usuario(user, item)
    return NIVEL_RANK.get(nivel, 0) >= NIVEL_RANK.get(nivel_minimo, 1)


def item_cadastro_por_model(model):
    return CADASTRO_MODEL_MAP.get(model._meta.model_name)


def usuario_tem_algum_cadastro(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.has_perm('core.acessar_admin_cadastros'):
        return True
    try:
        return user.permissoes_cadastros_simples.exclude(nivel=NIVEL_SEM_ACESSO).exists()
    except Exception:
        return False
