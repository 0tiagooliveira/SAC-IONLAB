from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from core.models import SAC
from core.services.empresa_filtro import aplicar_filtro_empresa, resolver_filtro_empresa
from core.services.sac_transicao_unificada import aplicar_transicao_sac
from core.services.regras_sac import resolver_acao_por_codigo
from core.utils_log_seguro import registrar_erro
from core.services.sac_bridge import (
    diretoria_campos_historico as _diretoria_campos_historico,
    extrair_primeiro_valor_do_historico as _extrair_primeiro_valor_do_historico,
    normalizar_decimal_texto_ptbr as _normalizar_decimal_texto_ptbr,
    obter_acao_por_nome,
    obter_setor_por_nome,
    obter_status_por_nome,
    sac_aguardando_acao_diretoria_queryset,
)
from core.services.historico_padronizado import montar_historico_detalhado
from core.services.sac_dados_oficiais import montar_dados_sac_oficiais
from core.services.sac_visual import (
    acao_em_espera_card as _acao_em_espera_card,
    classe_tempo_espera as _classe_tempo_espera,
    formatar_duracao_dd_hh_mm,
    montar_grafico_tempo_status_sac,
    montar_contexto_itens_sac,
    status_anterior_card as _status_anterior_card,
)



def _formatar_numero_sac(sac):
    numero = str(getattr(sac, 'numero', '') or '').strip()
    if not numero:
        return '-'
    if '/' in numero:
        return numero
    try:
        numero_formatado = str(int(numero)).zfill(3)
    except Exception:
        numero_formatado = numero
    ano = str(getattr(sac, 'ano', '') or '').strip()
    return f"{numero_formatado}/{ano}" if ano else numero_formatado


def _texto_tempo(delta):
    return formatar_duracao_dd_hh_mm(delta)


def _dados_sac_contexto(sac, agora):
    if not sac:
        return {}

    marco_tempo = getattr(sac, 'data_abertura', None) or agora
    tempo_delta = (agora - marco_tempo) if marco_tempo else timedelta(0)
    tipo_ocorrencia = '-'
    try:
        item = sac.itens_sac.select_related('tipo_ocorrencia').first()
        if item and getattr(item, 'tipo_ocorrencia', None):
            tipo_ocorrencia = item.tipo_ocorrencia.nome or '-'
    except Exception as e:
        registrar_erro('core.views_modular.views_diretoria.py:except_1', e)
        pass

    nf = getattr(sac, 'nota_fiscal', None)
    numero_nf = getattr(nf, 'numero_nf', None) or getattr(nf, 'numero', None) or '-'

    return {
        'numero_sac': _formatar_numero_sac(sac),
        'status_atual': getattr(getattr(sac, 'status_atual', None), 'nome', None) or '-',
        'empresa': getattr(getattr(sac, 'empresa', None), 'razao_social', None) or getattr(getattr(sac, 'empresa', None), 'nome', None) or '-',
        'setor_atual': getattr(getattr(sac, 'setor_atual', None), 'nome', None) or '-',
        'cliente': getattr(getattr(sac, 'cliente', None), 'razao_social', None) or getattr(getattr(sac, 'cliente', None), 'nome', None) or '-',
        'nota_fiscal': numero_nf,
        'titulo': getattr(sac, 'titulo', None) or '-',
        'acao_em_espera_atual': getattr(getattr(sac, 'acao_em_espera', None), 'nome', None) or '-',
        'data_hora_setor': marco_tempo.strftime('%d/%m/%Y %H:%M') if marco_tempo else '-',
        'tempo_setor': _texto_tempo(tempo_delta),
        'tipo_ocorrencia': tipo_ocorrencia,
    }


def _normalizar_acao(valor):
    return (valor or '').strip().lower()


def _fluxo_preview_aprovado():
    return {'status': 'Concluído', 'acao': '-', 'setor': '-'}


def _fluxo_preview_reprovado():
    return {'status': 'Em Análise', 'acao': 'Ligar para o Cliente - Comercial', 'setor': 'Gestão Comercial'}


@login_required
def analise_diretoria(request):
    sac_id = request.GET.get('sac')
    agora = timezone.now()
    empresa_filtro, contexto_empresa = resolver_filtro_empresa(request)

    sacs_qs = sac_aguardando_acao_diretoria_queryset()
    sacs_qs = aplicar_filtro_empresa(sacs_qs, empresa_filtro)

    sacs_disponiveis = []
    for s in sacs_qs:
        marco_tempo = getattr(s, 'data_abertura', None)
        tempo_espera_delta = (agora - marco_tempo) if marco_tempo else timedelta(0)

        tempo_espera = formatar_duracao_dd_hh_mm(tempo_espera_delta)

        sacs_disponiveis.append({
            'id': s.id,
            'numero': getattr(s, 'numero', ''),
            'numero_sac': _formatar_numero_sac(s),
            'empresa_nome': getattr(getattr(s, 'empresa', None), 'razao_social', '') or getattr(getattr(s, 'empresa', None), 'nome', ''),
            'cliente_nome': getattr(getattr(s, 'cliente', None), 'razao_social', '') or getattr(getattr(s, 'cliente', None), 'nome', ''),
            'nota_fiscal_numero': getattr(getattr(s, 'nota_fiscal', None), 'numero_nf', '') or getattr(getattr(s, 'nota_fiscal', None), 'numero', ''),
            'status_atual_nome': _status_anterior_card(s),
            'acao_em_espera_nome': _acao_em_espera_card(s),
            'tempo_espera': tempo_espera,
            'tempo_cor': _classe_tempo_espera(tempo_espera_delta),
        })

    sac = None
    historicos = []
    grafico_tempo_status = []
    itens_contexto = None

    if sac_id:
        try:
            sac = SAC.objects.select_related(
                'empresa', 'cliente', 'nota_fiscal', 'status_atual', 'setor_atual', 'acao_em_espera'
            ).get(id=sac_id)
        except SAC.DoesNotExist:
            sac = None

    dados_sac = _dados_sac_contexto(sac, agora)
    acao_setor_nome = (getattr(getattr(sac, 'acao_em_espera', None), 'nome', '') or '').strip() if sac else ''
    is_aprovacao_desconto = _normalizar_acao(acao_setor_nome) in {'aguardando aprovação de desconto', 'aguardando aprovacao de desconto'}
    decisao_desconto_inicial = ''
    contraproposta_inicial = ''
    observacoes_diretoria_inicial = ''
    fluxo_preview_aprovado = _fluxo_preview_aprovado()
    fluxo_preview_reprovado = _fluxo_preview_reprovado()
    fluxo_preview = {'status': '-', 'acao': '-', 'setor': '-'}
    if is_aprovacao_desconto:
        fluxo_preview = {'status': 'Selecione a decisão', 'acao': 'Selecione a decisão', 'setor': 'Selecione a decisão'}

    if sac and request.method == 'POST':
        acao_setor_nome = (getattr(getattr(sac, 'acao_em_espera', None), 'nome', '') or '').strip()
        valor_pleiteado_texto = (request.POST.get('valor_desconto_pleiteado') or '').strip()
        decisao_desconto = (request.POST.get('decisao_desconto') or '').strip().upper()
        contraproposta_texto = (request.POST.get('contra_proposta_desconto') or '').strip()
        observacoes_diretoria = (request.POST.get('observacoes_diretoria') or '').strip()

        decisao_desconto_inicial = decisao_desconto
        contraproposta_inicial = contraproposta_texto
        observacoes_diretoria_inicial = observacoes_diretoria
        if decisao_desconto == 'APROVADO':
            fluxo_preview = fluxo_preview_aprovado
        elif decisao_desconto == 'REPROVADO':
            fluxo_preview = fluxo_preview_reprovado

        valor_pleiteado = _normalizar_decimal_texto_ptbr(valor_pleiteado_texto)
        contraproposta = _normalizar_decimal_texto_ptbr(contraproposta_texto)

        if acao_setor_nome.lower() == 'aguardando aprovação de desconto' or acao_setor_nome.lower() == 'aguardando aprovacao de desconto':
            if valor_pleiteado in (None, ''):
                valor_hist = _extrair_primeiro_valor_do_historico(sac, 'Valor do desconto pleiteado')
                valor_pleiteado = _normalizar_decimal_texto_ptbr(valor_hist)

            if not decisao_desconto:
                messages.error(request, 'Selecione se o valor do desconto será Aprovado ou Reprovado.')
                return redirect(f'/sac/diretoria/?sac={sac.id}')

            if decisao_desconto == 'APROVADO':
                status_novo = obter_status_por_nome('Concluído') or obter_status_por_nome('Concluido')
                observacao = _diretoria_campos_historico(
                    observacoes=observacoes_diretoria,
                    acao_em_espera_setor=acao_setor_nome,
                    valor_pleiteado=valor_pleiteado,
                    decisao='Aprovado',
                    proximo_status=getattr(status_novo, 'nome', 'Concluído'),
                    proxima_acao='',
                    proximo_setor='',
                )
                aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    acao_em_espera=None,
                    setor_destino=None,
                    status_novo=status_novo,
                    observacao=observacao,
                    acao_executada_texto='Análise da Diretoria registrada',
                )
                messages.success(request, f'Análise da Diretoria do SAC {sac.numero} registrada com sucesso.')
                return redirect(f'/sac/analise-comercial/?sac={sac.id}')

            if decisao_desconto == 'REPROVADO':
                if contraproposta in (None, ''):
                    messages.error(request, 'Informe a Contra Proposta de desconto.')
                    return redirect(f'/sac/diretoria/?sac={sac.id}')

                acao_destino = resolver_acao_por_codigo('LIGAR_CLIENTE_COMERCIAL') or resolver_acao_por_codigo('LIGAR_PARA_O_CLIENTE_COMERCIAL') or resolver_acao_por_codigo('COMERCIAL_LIGAR_CLIENTE') or obter_acao_por_nome('Ligar para o Cliente - Comercial') or obter_acao_por_nome('Ligar para o Cliente')
                status_novo = obter_status_por_nome('Em Análise') or obter_status_por_nome('Em Analise')
                setor_destino = obter_setor_por_nome('Gestão Comercial') or obter_setor_por_nome('Gestao Comercial') or obter_setor_por_nome('Comercial')

                observacao = _diretoria_campos_historico(
                    observacoes=observacoes_diretoria,
                    acao_em_espera_setor=acao_setor_nome,
                    valor_pleiteado=valor_pleiteado,
                    decisao='Reprovado',
                    contraproposta=contraproposta,
                    proximo_status=getattr(status_novo, 'nome', 'Em Análise'),
                    proxima_acao=getattr(acao_destino, 'nome', 'Ligar para o Cliente'),
                    proximo_setor=getattr(setor_destino, 'nome', 'Comercial'),
                )
                aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    acao_em_espera=acao_destino,
                    setor_destino=setor_destino,
                    status_novo=status_novo,
                    observacao=observacao,
                    acao_executada_texto='Análise da Diretoria registrada',
                )
                messages.success(request, f'Análise da Diretoria do SAC {sac.numero} registrada com sucesso.')
                return redirect(f'/sac/diretoria/?sac={sac.id}')

        else:
            observacao = _diretoria_campos_historico(
                observacoes=observacoes_diretoria,
                acao_em_espera_setor=acao_setor_nome,
            )
            aplicar_transicao_sac(
                sac=sac,
                usuario=request.user,
                acao_em_espera=getattr(sac, 'acao_em_espera', None),
                setor_destino=getattr(sac, 'setor_atual', None),
                status_novo=getattr(sac, 'status_atual', None),
                observacao=observacao,
                acao_executada_texto='Análise da Diretoria registrada',
                salvar_sac=False,
            )
            messages.success(request, f'Observações da Diretoria do SAC {sac.numero} registradas com sucesso.')
            return redirect(f'/sac/diretoria/?sac={sac.id}')

    if sac:
        historicos_qs = getattr(sac, 'historicos', None)
        if historicos_qs is not None:
            historicos = historicos_qs.all().order_by('-data_evento', '-id')
            historicos_detalhados = montar_historico_detalhado(historicos)
            historicos_ordenados = list(historicos_qs.all().order_by('-data_evento', '-id'))
        else:
            historicos_ordenados = []

        grafico_tempo_status = montar_grafico_tempo_status_sac(sac, agora=agora)
        itens_contexto = montar_contexto_itens_sac(sac, setor_contexto=getattr(sac, "setor_atual", None))
    fluxo_alertas = []
    valor_desconto_pleiteado_inicial = _extrair_primeiro_valor_do_historico(sac, 'Valor do desconto pleiteado') if sac else ''
    total_itens = sac.itens_sac.count() if sac else 0

    return render(request, 'core/analise_diretoria.html', {
        'sacs_disponiveis': sacs_disponiveis,
        'cards_pendentes': sacs_disponiveis,
        'total_sacs': len(sacs_disponiveis),
        'sac': sac,
        'dados_sac': dados_sac,
        'dados_sac_oficiais': montar_dados_sac_oficiais(sac),
        'historicos': historicos,
        'historicos_detalhados': locals().get('historicos_detalhados', []),
        'grafico_tempo_status': grafico_tempo_status,
        'itens_contexto': itens_contexto,
        'fluxo_alertas': fluxo_alertas,
        'valor_desconto_pleiteado_inicial': valor_desconto_pleiteado_inicial,
        'total_itens': total_itens,
        'acao_setor_nome': acao_setor_nome,
        'is_aprovacao_desconto': is_aprovacao_desconto,
        'decisao_desconto_inicial': decisao_desconto_inicial,
        'contraproposta_inicial': contraproposta_inicial,
        'observacoes_diretoria_inicial': observacoes_diretoria_inicial,
        'fluxo_preview': fluxo_preview,
        'fluxo_preview_aprovado': fluxo_preview_aprovado,
        'fluxo_preview_reprovado': fluxo_preview_reprovado,
        'fila_setorial_atual': sacs_disponiveis,
        **contexto_empresa,
    })
