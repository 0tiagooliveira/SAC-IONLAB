import unicodedata
from collections import defaultdict

from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from core.models import SAC, SACItem, SacHistorico, Setor
from core.access_config import TELA_PERMISSOES_ANTIGAS
from core.services.fila_setorial import resumo_filas_por_setor
from core.services.empresa_filtro import resolver_filtro_empresa
from core.services.permissoes_simples import usuario_pode_tela
from core.services.sac_visual import formatar_horas_dd_hh_mm
from core.services.sla_inteligente import calcular_sla_sac


MENU_PRINCIPAL = [
    {'label': 'Painel principal', 'url': '/intra/', 'perm': 'core.acessar_painel', 'match': ['/intra/']},
    {'label': 'Abrir novo SAC', 'url': '/sac/abrir/', 'perm': 'core.acessar_abertura_sac', 'match': ['/sac/abrir/']},
    {'label': 'Consultar SACs', 'url': '/sac/pesquisa/', 'perm': 'core.acessar_pesquisa_sacs', 'match': ['/sac/pesquisa/']},
    {'label': 'Dashboard SLA', 'url': '/sac/dashboard/', 'perm': 'core.acessar_dashboard_sla', 'match': ['/sac/dashboard/']},
]

MENU_AREAS = [
    {'label': 'Gestão do SAC', 'url': '/sac/gestao/', 'perm': 'core.acessar_comercial', 'match': ['/sac/gestao/']},
    {'label': 'Gestão Comercial', 'url': '/sac/analise-comercial/', 'perm': 'core.acessar_comercial', 'match': ['/sac/analise-comercial/']},
    {'label': 'Gestão Logística', 'url': '/sac/gestao-logistica/', 'perm': 'core.acessar_logistica', 'match': ['/sac/gestao-logistica/']},
    {'label': 'Gestão Licitação', 'url': '/sac/gestao-licitacao/', 'perm': 'core.acessar_licitacao', 'match': ['/sac/gestao-licitacao/']},
    {'label': 'Assessoria Científica', 'url': '/sac/assessoria-cientifica/', 'perm': 'core.acessar_assessoria', 'match': ['/sac/assessoria-cientifica/', '/sac/analise-tecnica/']},
    {'label': 'Assistência Técnica', 'url': '/sac/assistencia-tecnica/', 'perm': 'core.acessar_assistencia_tecnica', 'match': ['/sac/assistencia-tecnica/']},
    {'label': 'Gestão Financeira', 'url': '/sac/gestao-financeira/', 'perm': 'core.acessar_financeiro', 'match': ['/sac/gestao-financeira/']},
    {'label': 'Diretoria', 'url': '/sac/diretoria/', 'perm': 'core.acessar_diretoria', 'match': ['/sac/diretoria/']},
]

MENU_ADMIN = [
    {'label': 'Cadastros', 'url': '/admin/', 'perm': 'core.acessar_admin_cadastros', 'match': ['/admin/']},
    {'label': 'Importar notas', 'url': '/importar/', 'perm': 'core.acessar_importacoes', 'match': ['/importar/']},
    {'label': 'Importar rastreios', 'url': '/importar-rastreios/', 'perm': 'core.acessar_importacoes', 'match': ['/importar-rastreios/']},
    {'label': 'Importar tabela de peças', 'url': '/importar-tabela-pecas/', 'perm': 'core.acessar_importacoes', 'match': ['/importar-tabela-pecas/']},
]

MENU_CARDS = [
    {'label': 'Cadastros', 'url': '/admin/', 'perm': 'core.acessar_admin_cadastros', 'accent': 'accent-purple', 'icon': 'ADM', 'tag': 'Area administrativa', 'description': 'Gerencie tabelas de apoio, parametros do sistema e registros administrativos.'},
    {'label': 'Gestao do SAC', 'url': '/sac/gestao/', 'perm': 'core.acessar_comercial', 'accent': 'accent-blue', 'icon': 'SAC', 'tag': 'Fluxo central', 'description': 'Acompanhe SACs aguardando acao e organize encaminhamentos da rotina operacional.'},
    {'label': 'Assessoria Cientifica', 'url': '/sac/assessoria-cientifica/', 'perm': 'core.acessar_assessoria', 'accent': 'accent-cyan', 'icon': 'AC', 'tag': 'Analise tecnica', 'description': 'Acesse a etapa tecnica e cientifica do processo com foco em analise e suporte especializado.'},
    {'label': 'Assistencia Tecnica', 'url': '/sac/assistencia-tecnica/', 'perm': 'core.acessar_assistencia_tecnica', 'accent': 'accent-cyan', 'icon': 'AT', 'tag': 'Assistencia tecnica', 'description': 'Acompanhe a fila da Assistencia Tecnica, itens incluidos e historico recente.'},
    {'label': 'Gestao Comercial', 'url': '/sac/analise-comercial/', 'perm': 'core.acessar_comercial', 'accent': 'accent-green', 'icon': 'COM', 'tag': 'Decisao comercial', 'description': 'Conduza negociacoes, valide encaminhamentos comerciais e registre decisoes do atendimento.'},
    {'label': 'Gestao Financeira', 'url': '/sac/gestao-financeira/', 'perm': 'core.acessar_financeiro', 'accent': 'accent-green', 'icon': 'FIN', 'tag': 'Decisao financeira', 'description': 'Gerencie aprovacoes de cobranca, valores de manutencao e decisoes financeiras.'},
    {'label': 'Gestao Licitacao', 'url': '/sac/gestao-licitacao/', 'perm': 'core.acessar_licitacao', 'accent': 'accent-green', 'icon': 'LIC', 'tag': 'Licitacao', 'description': 'Acompanhe os SACs destinados ao setor de Licitacao e registre analises da etapa.'},
    {'label': 'Abrir Novo SAC', 'url': '/sac/abrir/', 'perm': 'core.acessar_abertura_sac', 'accent': 'accent-gold', 'icon': '+', 'tag': 'Novo atendimento', 'description': 'Inicie um novo atendimento com acesso direto ao formulario de abertura.'},
    {'label': 'Diretoria', 'url': '/sac/diretoria/', 'perm': 'core.acessar_diretoria', 'accent': 'accent-red', 'icon': 'DIR', 'tag': 'Alcada diretoria', 'description': 'Acompanhe SACs direcionados para a Diretoria e visualize o historico completo.'},
    {'label': 'Consultar SACs', 'url': '/sac/pesquisa/', 'perm': 'core.acessar_pesquisa_sacs', 'accent': 'accent-purple', 'icon': 'BUS', 'tag': 'Consulta historica', 'description': 'Pesquise a base de SACs por cliente, numero, serial, produto e ocorrencia.'},
    {'label': 'Dashboard SLA', 'url': '/sac/dashboard/', 'perm': 'core.acessar_dashboard_sla', 'accent': 'accent-blue', 'icon': 'DASH', 'tag': 'Indicadores visuais', 'description': 'Acompanhe graficos por setor, SACs vencidos, tendencia mensal e itens campeoes.'},
    {'label': 'Gestao Logistica', 'url': '/sac/gestao-logistica/', 'perm': 'core.acessar_logistica', 'accent': 'accent-cyan', 'icon': 'LOG', 'tag': 'Fluxo logistico', 'description': 'Acompanhe a etapa logistica, recebimento, expedicao e registros do fluxo.'},
]


def _usuario_pode(user, perm):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if perm == 'core.acessar_admin_cadastros':
        return usuario_pode_tela(user, 'cadastros')
    tela_por_perm = {valor: chave for chave, valor in TELA_PERMISSOES_ANTIGAS.items()}
    tela = tela_por_perm.get(perm)
    if tela:
        return usuario_pode_tela(user, tela)
    return user.has_perm(perm)


def _menu_visivel(request, itens):
    path = request.path or ''
    menu = []
    for item in itens:
        if not _usuario_pode(request.user, item['perm']):
            continue
        menu.append({
            **item,
            'active': any(path.startswith(prefix) for prefix in item.get('match', [])),
        })
    return menu


def _normalizar_nome(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(texto.lower().split())


SETOR_POR_PAGINA = {
    '/sac/gestao/': 'SAC',
    '/sac/analise-comercial/': 'Comercial',
    '/sac/gestao-logistica/': 'Logística',
    '/sac/gestao-licitacao/': 'Licitação',
    '/sac/assessoria-cientifica/': 'Assessoria Cientifica',
    '/sac/assistencia-tecnica/': 'Assistência Técnica',
    '/sac/gestao-financeira/': 'Financeiro',
    '/sac/diretoria/': 'Diretoria',
}


def _setor_da_pagina(path):
    for prefixo, nome_setor in SETOR_POR_PAGINA.items():
        if path.startswith(prefixo):
            return nome_setor
    return ''


def _inicio_mes_atual():
    agora = timezone.now()
    return agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0), agora


def _sac_passou_pelo_setor_no_encerramento(sac, setor_chave):
    historicos = list(
        SacHistorico.objects.filter(sac=sac)
        .select_related('setor_origem', 'setor_destino')
        .order_by('-data_evento', '-id')
    )
    for historico in historicos:
        setor = getattr(historico, 'setor_destino', None) or getattr(historico, 'setor_origem', None)
        if setor and _normalizar_nome(setor.nome) == setor_chave:
            return True
    for setor in (getattr(sac, 'setor_atual', None), getattr(sac, 'setor_responsavel', None)):
        if setor and _normalizar_nome(setor.nome) == setor_chave:
            return True
    return False


def _concluidos_mes_setor(setor_nome, empresa):
    if not setor_nome:
        return 0
    inicio, fim = _inicio_mes_atual()
    setor_chave = _normalizar_nome(setor_nome)
    setor_ids = [
        setor.id
        for setor in Setor.objects.filter(ativo=True).only('id', 'nome')
        if _normalizar_nome(setor.nome) == setor_chave
    ]
    if not setor_ids:
        return 0

    qs = SAC.objects.filter(concluido_em__gte=inicio, concluido_em__lte=fim)
    if empresa is not None:
        qs = qs.filter(empresa_id=empresa.id)
    sac_ids = set(qs.values_list('id', flat=True))
    if not sac_ids:
        return 0
    historico_ids = set(
        SacHistorico.objects.filter(
            sac_id__in=sac_ids,
        ).filter(
            Q(setor_origem_id__in=setor_ids) | Q(setor_destino_id__in=setor_ids)
        ).values_list('sac_id', flat=True)
    )
    setor_atual_ids = set(
        qs.filter(Q(setor_atual_id__in=setor_ids) | Q(setor_responsavel_id__in=setor_ids))
        .values_list('id', flat=True)
    )
    return len(historico_ids | setor_atual_ids)


def _top_itens_mes_leve(inicio, fim, empresa):
    qs = (
        SACItem.objects
        .select_related('sac', 'item_nota_fiscal')
        .filter(sac__data_abertura__gte=inicio, sac__data_abertura__lte=fim)
    )
    if empresa is not None:
        qs = qs.filter(sac__empresa_id=empresa.id)

    equipamentos = {}
    consumiveis = {}
    for item_sac in qs:
        item_nf = item_sac.item_nota_fiscal
        codigo = getattr(item_nf, 'codigo_produto', None) or '-'
        descricao = getattr(item_nf, 'descricao_item', None) or getattr(item_nf, 'item', None) or '-'
        if item_sac.tipo_rastreio == 'SERIAL':
            bucket = equipamentos.setdefault(codigo, {'codigo': codigo, 'descricao': descricao, 'seriais': set(), 'total': 0})
            serial = (item_sac.numero_rastreio or '').strip()
            if serial:
                bucket['seriais'].add(serial)
            else:
                bucket['total'] += 1
        else:
            bucket = consumiveis.setdefault(codigo, {'codigo': codigo, 'descricao': descricao, 'sacs': set()})
            bucket['sacs'].add((item_sac.sac.empresa_id, item_sac.sac.numero or item_sac.sac_id))

    def montar_lista(dados, categoria):
        itens = []
        for item in dados.values():
            total = len(item.get('seriais', set())) + item.get('total', 0) if categoria == 'equipamentos' else len(item.get('sacs', set()))
            if total:
                itens.append({'codigo': item['codigo'], 'descricao': item['descricao'], 'total_sacs': total})
        return sorted(itens, key=lambda valor: (-valor['total_sacs'], valor['codigo']))[:3]

    return {
        'mes_corrente': {
            'equipamentos': montar_lista(equipamentos, 'equipamentos'),
            'consumiveis': montar_lista(consumiveis, 'consumiveis'),
        }
    }


def _montar_indicadores_globais_leves(empresa):
    agora = timezone.now()
    inicio_mes, fim_mes = _inicio_mes_atual()
    limite_sla_horas = 24

    abertos_qs = (
        SAC.objects
        .select_related('setor_atual', 'status_atual')
        .filter(concluido_em__isnull=True, cancelado_em__isnull=True)
        .exclude(status_atual__nome__iexact='Concluído')
    )
    if empresa is not None:
        abertos_qs = abertos_qs.filter(empresa_id=empresa.id)

    resumo = {
        'total_abertos': 0,
        'sla_verde': 0,
        'sla_amarelo': 0,
        'sla_vencidos': 0,
        'sla_proximos': 0,
        'concluidos_mes': 0,
        'tempo_medio_resolucao': 'Não calculado',
        'taxa_conclusao_prazo': 0,
    }
    setores = defaultdict(lambda: {'setor': 'Sem setor', 'total': 0, 'vencidos': 0, 'proximos': 0})

    for sac in abertos_qs:
        resumo['total_abertos'] += 1
        sla = calcular_sla_sac(sac, agora=agora)
        if sla.faixa == 'proximo_do_vencimento':
            resumo['sla_amarelo'] += 1
            resumo['sla_proximos'] += 1
        elif sla.faixa in {'vencido', 'reincidente'}:
            resumo['sla_vencidos'] += 1
        else:
            resumo['sla_verde'] += 1
        setor_nome = getattr(getattr(sac, 'setor_atual', None), 'nome', None) or 'Sem setor'
        setor = setores[setor_nome]
        setor['setor'] = setor_nome
        setor['total'] += 1
        if sla.faixa == 'proximo_do_vencimento':
            setor['proximos'] += 1
        elif sla.faixa in {'vencido', 'reincidente'}:
            setor['vencidos'] += 1

    concluidos_qs = SAC.objects.filter(concluido_em__gte=inicio_mes, concluido_em__lte=fim_mes)
    if empresa is not None:
        concluidos_qs = concluidos_qs.filter(empresa_id=empresa.id)
    tempos = []
    no_prazo = 0
    for sac in concluidos_qs.only('data_abertura', 'concluido_em'):
        if not sac.data_abertura or not sac.concluido_em:
            continue
        horas = max((sac.concluido_em - sac.data_abertura).total_seconds(), 0) / 3600
        tempos.append(horas)
        if horas <= limite_sla_horas:
            no_prazo += 1
    resumo['concluidos_mes'] = len(tempos)
    if tempos:
        resumo['tempo_medio_resolucao'] = formatar_horas_dd_hh_mm(sum(tempos) / len(tempos))
    resumo['taxa_conclusao_prazo'] = round((no_prazo / len(tempos)) * 100, 1) if tempos else 0

    setores_ordenados = sorted(setores.values(), key=lambda item: (-item['vencidos'], -item['proximos'], -item['total'], item['setor']))
    return {
        'resumo': resumo,
        'setores': setores_ordenados,
        'ranking_itens': _top_itens_mes_leve(inicio_mes, fim_mes, empresa),
    }


def menu_lateral_sac(request):
    if not request.user.is_authenticated:
        return {}
    menu_principal = _menu_visivel(request, MENU_PRINCIPAL)
    menu_areas = _menu_visivel(request, MENU_AREAS)
    menu_admin = _menu_visivel(request, MENU_ADMIN)
    return {
        'menu_principal_sac': menu_principal,
        'menu_areas_sac': menu_areas,
        'menu_admin_sac': menu_admin,
        'menu_cards_sac': _menu_visivel(request, MENU_CARDS),
        'pode_abrir_sac': any(item['url'] == '/sac/abrir/' for item in menu_principal),
        'pode_gestao_sac': any(item['url'] == '/sac/gestao/' for item in menu_areas),
    }


def indicadores_globais_sac(request):
    if not request.user.is_authenticated:
        return {}
    if request.path.startswith('/admin/') or request.path.startswith('/api/'):
        return {}
    if request.path in {'/login/', '/logout/'}:
        return {}
    if request.path == '/sac/dashboard/':
        return {'mostrar_indicadores_globais_sac': False}
    if not _usuario_pode(request.user, 'core.acessar_dashboard_sla'):
        return {}

    try:
        empresa, _ = resolver_filtro_empresa(request)
        setor_atual = _setor_da_pagina(request.path or '')
        setor_cache = (_normalizar_nome(setor_atual) or 'geral').replace(' ', '_')
        cache_key = f"indicadores_globais_sac:v3:{getattr(empresa, 'id', 'agrupado')}:{setor_cache}"
        dashboard = cache.get(cache_key)
        if dashboard is None:
            dashboard = _montar_indicadores_globais_leves(empresa)
            if setor_atual:
                setor_chave = _normalizar_nome(setor_atual)
                setor_resumo = next(
                    (item for item in dashboard.get('setores', []) if _normalizar_nome(item.get('setor')) == setor_chave),
                    None,
                )
                dashboard['setor_pagina_atual'] = setor_atual
                dashboard['resumo']['sla_vencidos_setor_atual'] = (setor_resumo or {}).get('vencidos', 0)
                dashboard['resumo']['sla_proximos_setor_atual'] = (setor_resumo or {}).get('proximos', 0)
                dashboard['resumo']['concluidos_mes_setor_atual'] = _concluidos_mes_setor(setor_atual, empresa)
            cache.set(cache_key, dashboard, 60)
    except Exception:
        return {}

    return {
        'indicadores_globais_sac': dashboard,
        'mostrar_indicadores_globais_sac': request.path != '/sac/dashboard/',
    }


def fila_inteligente(request):
    if not request.user.is_authenticated:
        return {}

    cache_key = 'fila_inteligente:v2'
    dados_cache = cache.get(cache_key)
    if dados_cache is not None:
        return {'fila_inteligente': dados_cache}

    resumos_validos = [resumo for resumo in resumo_filas_por_setor() if resumo.total > 0 and resumo.primeiro_sac_id]
    sac_ids = [resumo.primeiro_sac_id for resumo in resumos_validos]
    sacs_por_id = {
        sac.id: sac
        for sac in SAC.objects.select_related('cliente', 'status_atual').filter(id__in=sac_ids)
    }

    dados = []
    for resumo in resumos_validos:
        sac = sacs_por_id.get(resumo.primeiro_sac_id)
        if not sac:
            continue

        cliente = getattr(sac, 'cliente', None)
        cliente_texto = (
            getattr(cliente, 'razao_social', None)
            or getattr(cliente, 'nome', None)
            or '-'
        )
        status_obj = getattr(sac, 'status_atual', None) or getattr(sac, 'status', None)
        status_texto = getattr(status_obj, 'nome', '-') if status_obj else '-'

        dados.append({
            'setor': resumo.nome,
            'numero_sac': getattr(sac, 'numero', None) or getattr(sac, 'numero_sac', '-'),
            'cliente': cliente_texto,
            'status': status_texto,
            'total': resumo.total,
            'criticos': resumo.criticos,
            'tempo_mais_antigo': resumo.tempo_mais_antigo,
            'rota_lista': resumo.rota_lista,
        })

    cache.set(cache_key, dados, 45)
    return {'fila_inteligente': dados}


def menu_setores(request):
    if not request.user.is_authenticated:
        return {}

    setores = cache.get('menu_setores:v1')
    if setores is None:
        setores = list(Setor.objects.filter(ativo=True).order_by('nome'))
        cache.set('menu_setores:v1', setores, 300)
    return {'menu_setores': setores}
