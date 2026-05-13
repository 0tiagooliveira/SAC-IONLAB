from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import SAC, SacAnaliseComercial
from core.services.empresa_filtro import aplicar_filtro_empresa, resolver_filtro_empresa
from core.services.fluxo_sac import diagnosticar_fluxo_inicial
from core.services.historico_padronizado import montar_historico_detalhado
from core.services.sac_dados_oficiais import montar_dados_sac_oficiais
from core.services.sac_transicao_unificada import aplicar_transicao_sac
from core.services.sac_bridge import (
    extrair_dados_analise_licitacao as _extrair_dados_analise_licitacao,
    montar_contexto_analise_licitacao as _montar_contexto_analise_licitacao,
    obter_setor_por_nome,
    resolver_fluxo_fixo_licitacao as _resolver_fluxo_fixo_licitacao,
    sac_aguarda_acao_licitacao_queryset,
)
from core.services.sac_visual import (
    acao_em_espera_card as _acao_em_espera_card,
    classe_tempo_espera as _classe_tempo_espera,
    empresa_sac as _empresa_sac,
    formatar_tempo_espera as _formatar_tempo_espera,
    montar_contexto_itens_sac,
    montar_grafico_tempo_status_sac,
    nota_sac as _nota_sac,
    resolver_setor_contexto_licitacao,
    status_anterior_card as _status_anterior_card,
)

def gestao_licitacao(request, sac_id=None):
    empresa_filtro, contexto_empresa = resolver_filtro_empresa(request)
    sacs_pendentes_qs = sac_aguarda_acao_licitacao_queryset()
    sacs_pendentes_qs = aplicar_filtro_empresa(sacs_pendentes_qs, empresa_filtro)
    sac_id_selecionado = sac_id or request.POST.get('sac_id') or request.GET.get('sac')
    sac = None

    cards_pendentes = []
    agora = timezone.now()
    for sac_item in sacs_pendentes_qs:
        ultimo_historico = sac_item.historicos.order_by('-data_evento', '-id').first()
        marco = ultimo_historico.data_evento if ultimo_historico else sac_item.data_abertura
        cliente_nome = (
            sac_item.cliente.razao_social if sac_item.cliente and getattr(sac_item.cliente, 'razao_social', None)
            else (sac_item.cliente.nome if sac_item.cliente and getattr(sac_item.cliente, 'nome', None) else '-')
        )
        cards_pendentes.append({
            'id': sac_item.id,
            'numero': sac_item.numero or f'SAC {sac_item.id}',
            'empresa_nome': _empresa_sac(sac_item),
            'cliente_nome': cliente_nome,
            'nota_fiscal_numero': _nota_sac(sac_item),
            'status_atual_nome': _status_anterior_card(sac_item),
            'acao_em_espera_nome': _acao_em_espera_card(sac_item),
            'tempo_espera': _formatar_tempo_espera(agora - marco),
            'tempo_cor': _classe_tempo_espera(agora - marco),
            'marco_tempo': marco,
            'selecionado': str(sac_item.id) == str(sac_id_selecionado),
        })
    cards_pendentes = sorted(cards_pendentes, key=lambda x: (x['marco_tempo'], x['id']))

    if sac_id_selecionado:
        sac = get_object_or_404(
            SAC.objects.select_related('empresa', 'cliente', 'nota_fiscal', 'status_atual', 'acao_em_espera', 'setor_atual')
            .prefetch_related('itens_sac__item_nota_fiscal', 'itens_sac__tipo_ocorrencia__setor', 'historicos'),
            id=sac_id_selecionado
        )

    historico = []
    itens_contexto = None
    itens_sac = []
    form = None
    grafico_tempo_status = []
    setor_contexto_licitacao = None
    acao_em_espera_atual = '-'
    usuario_anterior_nome = '-'
    licitacao_ctx = None

    if sac:
        historico = sac.historicos.select_related('usuario', 'status_anterior', 'status_novo', 'setor_destino', 'setor_origem').order_by('-data_evento', '-id')[:20]
        historicos_detalhados = montar_historico_detalhado(historico)
        grafico_tempo_status = montar_grafico_tempo_status_sac(sac)
        itens_sac = sac.itens_sac.select_related('item_nota_fiscal', 'tipo_ocorrencia').all()
        setor_contexto = sac.setor_atual or obter_setor_por_nome('Licitação') or obter_setor_por_nome('Licitacao')
        itens_contexto = montar_contexto_itens_sac(sac, setor_contexto=setor_contexto)
        setor_contexto_licitacao = resolver_setor_contexto_licitacao(sac)
        acao_em_espera_atual = sac.acao_em_espera.nome if getattr(sac, 'acao_em_espera', None) else '-'
        if historico:
            usuario_hist = getattr(historico[0], 'usuario', None)
            if usuario_hist:
                usuario_anterior_nome = usuario_hist.get_full_name() or usuario_hist.username or '-'

        dados_iniciais = _extrair_dados_analise_licitacao(sac)

        if request.method == 'POST':
            dados_post = {
                'tipo_produto': (request.POST.get('tipo_produto') or '').strip(),
                'usuario_classificou_edital': (request.POST.get('usuario_classificou_edital') or '').strip(),
                'qual_ponto_divergiu': (request.POST.get('qual_ponto_divergiu') or '').strip(),
                'teve_erro_classificacao': (request.POST.get('teve_erro_classificacao') or '').strip(),
                'edital_estava_claro': (request.POST.get('edital_estava_claro') or '').strip(),
                'justificativa': (request.POST.get('justificativa') or '').strip(),
                'tem_referencia_correta': (request.POST.get('tem_referencia_correta') or '').strip(),
                'referencia_correta': (request.POST.get('referencia_correta') or '').strip(),
                'valor_referencia_correta': (request.POST.get('valor_referencia_correta') or '').strip(),
                'marca_alternativa': (request.POST.get('marca_alternativa') or '').strip(),
                'valor_marca_alternativa': (request.POST.get('valor_marca_alternativa') or '').strip(),
                'nome_usuario_gerou_pedido': (request.POST.get('nome_usuario_gerou_pedido') or '').strip(),
                'nome_usuario_fez_conferencia': (request.POST.get('nome_usuario_fez_conferencia') or '').strip(),
                'justificativa_erro': (request.POST.get('justificativa_erro') or '').strip(),
            }
            licitacao_ctx = _montar_contexto_analise_licitacao(sac, dados_post)
            flow = _resolver_fluxo_fixo_licitacao(sac)

            erros = []
            if not dados_post['tipo_produto']:
                erros.append('Tipo de produto é obrigatório.')

            if not flow:
                erros.append('Não foi possível determinar o fluxo fixo da Licitação para este SAC.')

            if licitacao_ctx.get('flow_case') == 'desacordo_edital':
                if not dados_post['usuario_classificou_edital']:
                    erros.append('Usuário que Classificou o edital é obrigatório.')
                if not dados_post['teve_erro_classificacao']:
                    erros.append('Teve erro de classificação é obrigatório.')
                if not dados_post['edital_estava_claro']:
                    erros.append('Edital estava claro/objetivo é obrigatório.')
                if dados_post['edital_estava_claro'] == 'Não' and not dados_post['justificativa']:
                    erros.append('Justificativa é obrigatória quando o edital não estava claro/objetivo.')
                if not dados_post['tem_referencia_correta']:
                    erros.append('Temos uma Referência correta pra atender é obrigatório.')
                if dados_post['tem_referencia_correta'] == 'Sim':
                    if not dados_post['referencia_correta']:
                        erros.append('Referência Correta é obrigatória.')
                    if not dados_post['valor_referencia_correta']:
                        erros.append('Valor da Referência Correta é obrigatório.')
                elif dados_post['tem_referencia_correta'] == 'Não':
                    if not dados_post['marca_alternativa']:
                        erros.append('Marca Alternativa é obrigatória.')
                    if not dados_post['valor_marca_alternativa']:
                        erros.append('Valor Marca Alternativa é obrigatório.')
            elif licitacao_ctx.get('flow_case') == 'pedido_duplicidade':
                if not dados_post['nome_usuario_gerou_pedido']:
                    erros.append('Nome do Usuário que Gerou o Pedido é obrigatório.')
                if not dados_post['nome_usuario_fez_conferencia']:
                    erros.append('Nome do Usuário que fez a Conferência é obrigatório.')

            if erros:
                for erro in erros:
                    messages.error(request, erro)
            else:
                observacao_historico_linhas = [
                    f"Tipo de produto: {dados_post['tipo_produto']}",
                ]
                if licitacao_ctx.get('flow_case') == 'desacordo_edital':
                    observacao_historico_linhas.extend([
                        f"Usuário que Classificou o edital: {dados_post['usuario_classificou_edital'] or '-'}",
                        f"Qual ponto divergiu: {dados_post['qual_ponto_divergiu'] or '-'}",
                        f"Teve erro de classificação: {dados_post['teve_erro_classificacao'] or '-'}",
                        f"Edital estava claro/objetivo: {dados_post['edital_estava_claro'] or '-'}",
                        f"Justificativa: {dados_post['justificativa'] or '-'}",
                        f"Temos uma Referência correta pra atender: {dados_post['tem_referencia_correta'] or '-'}",
                        f"Referência Correta: {dados_post['referencia_correta'] or '-'}",
                        f"Valor da Referência Correta: {dados_post['valor_referencia_correta'] or '-'}",
                        f"Marca Alternativa: {dados_post['marca_alternativa'] or '-'}",
                        f"Valor Marca Alternativa: {dados_post['valor_marca_alternativa'] or '-'}",
                    ])
                elif licitacao_ctx.get('flow_case') == 'pedido_duplicidade':
                    observacao_historico_linhas.extend([
                        f"Nome do Usuário que Gerou o Pedido: {dados_post['nome_usuario_gerou_pedido'] or '-'}",
                        f"Nome do Usuário que fez a Conferência: {dados_post['nome_usuario_fez_conferencia'] or '-'}",
                        f"Justificativa do Erro: {dados_post['justificativa_erro'] or '-'}",
                    ])
                observacao_historico_linhas.extend([
                    f"Próximo status: {getattr(flow.get('status'), 'nome', '-')}",
                    f"Ação em espera: {getattr(flow.get('acao'), 'nome', '-')}",
                    f"Próximo setor: {getattr(flow.get('setor'), 'nome', '-')}",
                ])
                observacao_historico = '\n'.join(observacao_historico_linhas)

                SacAnaliseComercial.objects.update_or_create(
                    sac=sac,
                    defaults={
                        'cliente_confirmou_pedido': False,
                        'cliente_aceita_negociacao': False,
                        'proximo_status_sugerido': flow.get('status'),
                        'acao_em_espera': flow.get('acao'),
                        'valor_desconto_pleiteado': None,
                        'observacao_comercial': observacao_historico,
                        'usuario_responsavel': request.user,
                        'data_analise': timezone.now(),
                    }
                )

                aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    acao_em_espera=flow.get('acao'),
                    setor_destino=flow.get('setor'),
                    status_novo=flow.get('status') or sac.status_atual,
                    observacao=observacao_historico,
                    acao_executada_texto='Análise de licitação registrada',
                )

                messages.success(request, f'Análise de licitação do SAC {sac.numero} registrada com sucesso.')
                setor_fluxo = flow.get('setor')
                nome_setor_fluxo = (getattr(setor_fluxo, 'nome', '') or '').strip().lower()
                if nome_setor_fluxo == 'sac':
                    return redirect(f'/sac/gestao/?sac={sac.id}')
                return redirect('/sac/gestao-licitacao/')
        else:
            licitacao_ctx = _montar_contexto_analise_licitacao(sac, dados_iniciais)

    return render(request, 'core/gestao_licitacao.html', {
        'sac': sac,
        'historico': historico,
        'historicos_detalhados': locals().get('historicos_detalhados', []),
        'itens_sac': itens_sac,
        'itens_contexto': itens_contexto,
        'form': form,
        'licitacao_ctx': licitacao_ctx,
        'cards_pendentes': cards_pendentes,
        'sacs_disponiveis': cards_pendentes,
        'total_sacs': len(cards_pendentes),
        'setor_contexto_licitacao': setor_contexto_licitacao,
        'acao_em_espera_atual': acao_em_espera_atual,
        'usuario_anterior_nome': usuario_anterior_nome,
        'dados_sac_oficiais': montar_dados_sac_oficiais(sac) if sac else {},
        'fluxo_alertas': diagnosticar_fluxo_inicial(sac, setor_contexto=getattr(sac, 'setor_atual', None), nome_tela='Gestão Licitação') if sac else [],
        'grafico_tempo_status': grafico_tempo_status,
        **contexto_empresa,
    })


# === OVERRIDE MODULAR SEGURO ===
from core.views_modular.views_gestao import gestao_sac as gestao_sac


# === OVERRIDE MODULAR LOGISTICA ===
from core.views_modular.views_logistica import gestao_logistica as gestao_logistica
