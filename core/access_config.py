NIVEL_SEM_ACESSO = 'sem_acesso'
NIVEL_VISUALIZAR = 'visualizar'
NIVEL_ALTERAR = 'alterar'

NIVEIS_ACESSO = (
    (NIVEL_ALTERAR, 'Incluir/Alterar'),
    (NIVEL_VISUALIZAR, 'Visualizar'),
    (NIVEL_SEM_ACESSO, 'Sem Acesso'),
)

NIVEL_RANK = {
    NIVEL_SEM_ACESSO: 0,
    NIVEL_VISUALIZAR: 1,
    NIVEL_ALTERAR: 2,
}

TELAS_SISTEMA = (
    ('painel', 'Painel principal', 'core.acessar_painel'),
    ('abertura_sac', 'Abrir novo SAC', 'core.acessar_abertura_sac'),
    ('pesquisa_sacs', 'Consultar SACs', 'core.acessar_pesquisa_sacs'),
    ('dashboard_sla', 'Dashboard SLA', 'core.acessar_dashboard_sla'),
    ('gestao_sac', 'Gestao do SAC', 'core.acessar_comercial'),
    ('gestao_comercial', 'Gestao Comercial', 'core.acessar_comercial'),
    ('gestao_logistica', 'Gestao Logistica', 'core.acessar_logistica'),
    ('gestao_licitacao', 'Gestao Licitacao', 'core.acessar_licitacao'),
    ('assessoria_cientifica', 'Assessoria Cientifica', 'core.acessar_assessoria'),
    ('assistencia_tecnica', 'Assistencia Tecnica', 'core.acessar_assistencia_tecnica'),
    ('gestao_financeira', 'Gestao Financeira', 'core.acessar_financeiro'),
    ('diretoria', 'Diretoria', 'core.acessar_diretoria'),
    ('importacoes', 'Importacoes', 'core.acessar_importacoes'),
    ('cadastros', 'Cadastros', 'core.acessar_admin_cadastros'),
    ('retificar_sac', 'Retificar SAC', 'core.retificar_sac'),
    ('cancelar_sac', 'Cancelar SAC', 'core.cancelar_sac'),
)

TELA_LABELS = {codigo: label for codigo, label, _perm in TELAS_SISTEMA}
TELA_PERMISSOES_ANTIGAS = {codigo: perm for codigo, _label, perm in TELAS_SISTEMA}

CADASTRO_ITENS = (
    ('empresas', 'Empresas'),
    ('setores', 'Setores'),
    ('acoes_em_espera', 'Acoes em espera'),
    ('usuarios', 'Usuarios'),
    ('status_sac', 'Status do SAC'),
    ('tipos_ocorrencia', 'Tipos de ocorrencia'),
    ('clientes', 'Clientes'),
    ('contatos_clientes', 'Contatos dos clientes'),
    ('notas_fiscais', 'Notas fiscais'),
    ('itens_notas_fiscais', 'Itens das notas fiscais'),
    ('rastreios', 'Rastreios / Seriais'),
    ('tratativas_problema', 'Tratativas do problema'),
    ('tipos_problema', 'Tipos de problema'),
    ('tecnicos_externos', 'Tecnicos externos'),
    ('tabela_pecas', 'Tabela de pecas'),
    ('sacs', 'SACs'),
    ('itens_sac', 'Itens do SAC'),
    ('anexos_sac', 'Anexos do SAC'),
    ('historicos_sac', 'Historicos do SAC'),
    ('importacoes_legado', 'Importacoes legado'),
    ('analises_tecnicas', 'Analises tecnicas'),
    ('orcamentos_tecnicos', 'Orcamentos tecnicos'),
    ('pecas_orcamento', 'Pecas do orcamento'),
    ('naturezas_operacao', 'Naturezas de operacao'),
    ('fluxo_acoes', 'Fluxo de acoes'),
    ('vendedores', 'Vendedores'),
)

CADASTRO_LABELS = dict(CADASTRO_ITENS)

CADASTRO_MODEL_MAP = {
    'empresa': 'empresas',
    'setor': 'setores',
    'acaoemespera': 'acoes_em_espera',
    'user': 'usuarios',
    'usuariosistema': 'usuarios',
    'statussac': 'status_sac',
    'tipoocorrencia': 'tipos_ocorrencia',
    'cliente': 'clientes',
    'clientecontato': 'contatos_clientes',
    'notafiscal': 'notas_fiscais',
    'itemnotafiscal': 'itens_notas_fiscais',
    'rastreionotaitem': 'rastreios',
    'tratativaproblema': 'tratativas_problema',
    'tipoproblema': 'tipos_problema',
    'tecnicoexterno': 'tecnicos_externos',
    'pecatabelapreco': 'tabela_pecas',
    'sac': 'sacs',
    'sacitem': 'itens_sac',
    'sacanexo': 'anexos_sac',
    'sachistorico': 'historicos_sac',
    'importacaolegadosac': 'importacoes_legado',
    'sacanalisetecnica': 'analises_tecnicas',
    'orcamentotecnicoexterno': 'orcamentos_tecnicos',
    'orcamentotecnicoexternopeca': 'pecas_orcamento',
    'naturezaoperacao': 'naturezas_operacao',
    'fluxoacaosetor': 'fluxo_acoes',
    'vendedor': 'vendedores',
}
