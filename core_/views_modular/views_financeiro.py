from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import SAC, SACAnexo, StatusSAC, AcaoEmEspera, Setor
from core.services.fila_setorial import queryset_fila_por_setor
from core.services.historico_padronizado import compor_observacao_padronizada, montar_historico_detalhado
from core.services.sac_dados_oficiais import montar_dados_sac_oficiais
from core.services.sac_transicao_unificada import aplicar_transicao_sac
from core.services.sac_visual import (
    acao_em_espera_card,
    empresa_sac,
    formatar_numero_sac,
    montar_contexto_itens_sac,
    nota_sac,
    resumo_tempo_setor,
    status_anterior_card,
)

ACAO_APROVAR_COBRANCA = 'Aprovar Cobrança do Valor do Serviço'


def _norm(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Z0-9]+', ' ', texto.upper()).strip()


def _nome(obj):
    return str(getattr(obj, 'nome', '') or obj or '').strip()


def _formatar_moeda(valor):
    try:
        valor = Decimal(str(valor or '0'))
    except (InvalidOperation, ValueError):
        valor = Decimal('0')
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _decimal_br(valor):
    texto = str(valor or '').strip()
    if not texto:
        return Decimal('0')
    texto = texto.replace('R$', '').replace(' ', '')
    if ',' in texto and '.' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    else:
        texto = texto.replace(',', '.')
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _eh_aprovar_cobranca(sac):
    return _norm(_nome(getattr(sac, 'acao_em_espera', None))) == _norm(ACAO_APROVAR_COBRANCA)


def _buscar(model, nome, codigos=()):
    qs = model.objects.all()
    alvo = _norm(nome)
    for codigo in codigos:
        obj = qs.filter(codigo__iexact=codigo).first()
        if obj:
            return obj
    for obj in qs:
        if _norm(getattr(obj, 'nome', '')) == alvo:
            return obj
    palavras = [p for p in alvo.split() if len(p) > 2]
    for obj in qs:
        nome_obj = _norm(getattr(obj, 'nome', ''))
        if palavras and all(p in nome_obj for p in palavras[:4]):
            return obj
    return None


def _resolver_destino_financeiro(decisao):
    if decisao == 'Sim':
        status_nome = 'Emissão de Pedido de Saída'
        acao_nome = 'Aguardando Emissão do Pedido (Saída)'
        setor_nome = 'SAC'
        setor_codigos = ('SAC',)
    else:
        status_nome = 'Em Análise'
        acao_nome = 'Aguardando Tratativa Interna'
        setor_nome = 'SAC'
        setor_codigos = ('SAC',)

    status = _buscar(StatusSAC, status_nome)
    acao = _buscar(AcaoEmEspera, acao_nome)
    setor = _buscar(Setor, setor_nome, codigos=setor_codigos)

    faltam = []
    if not status:
        faltam.append(f'Status: {status_nome}')
    if not acao:
        faltam.append(f'Ação em espera: {acao_nome}')
    if not setor:
        faltam.append(f'Setor: {setor_nome}')

    return status, acao, setor, faltam


def _buscar_valor_manutencao(sac):
    """Busca no histórico o último valor total de manutenção/orçamento técnico."""
    if not sac:
        return ''
    padroes = [
        r'Valor\s+total\s+da\s+Manuten[cç][aã]o\s*[:\-]\s*(R\$\s*[\d\.\,]+|[\d\.\,]+)',
        r'Valor\s+total\s+do\s+or[cç]amento\s*[:\-]\s*(R\$\s*[\d\.\,]+|[\d\.\,]+)',
        r'Total\s+geral\s+do\s+or[cç]amento\s*[:\-]\s*(R\$\s*[\d\.\,]+|[\d\.\,]+)',
        r'Valor\s+Total\s+das\s+pe[cç]as.*?R\$\s*[\d\.\,]+.*?Valor\s+total\s+das\s+Horas.*?R\$\s*[\d\.\,]+.*?Valor\s+total\s+do\s+or[cç]amento\s*[:\-]\s*(R\$\s*[\d\.\,]+|[\d\.\,]+)',
    ]
    try:
        historicos = sac.historicos.order_by('-data_evento', '-id')[:50]
    except Exception:
        historicos = []
    for historico in historicos:
        obs = str(getattr(historico, 'observacao', '') or '')
        for padrao in padroes:
            m = re.search(padrao, obs, re.IGNORECASE | re.DOTALL)
            if m:
                valor = (m.group(1) or '').strip()
                if valor:
                    return valor if valor.startswith('R$') else _formatar_moeda(_decimal_br(valor))
    return ''


def _montar_card_financeiro(sac, agora):
    tempo = resumo_tempo_setor(sac, agora=agora)
    cliente = getattr(sac, 'cliente', None)
    return {
        'id': sac.id,
        'numero': formatar_numero_sac(sac),
        'numero_sac': formatar_numero_sac(sac),
        'cliente_nome': getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None) or '-',
        'empresa_nome': empresa_sac(sac),
        'nota_fiscal_numero': nota_sac(sac),
        'status_atual_nome': status_anterior_card(sac),
        'acao_em_espera_nome': acao_em_espera_card(sac),
        'tempo_espera': tempo['tempo_espera'],
        'tempo_cor': tempo['tempo_cor'],
        'marco_tempo': tempo['marco_tempo'],
    }


@login_required
def gestao_financeira(request, sac_id=None):
    sac_id = sac_id or request.GET.get('sac')

    qs = queryset_fila_por_setor(nome_setor='Financeiro')
    try:
        if not qs.exists():
            qs = SAC.objects.filter(
                Q(setor_atual__nome__icontains='Finance')
                | Q(setor_atual__codigo__icontains='FINANC')
            ).select_related('empresa', 'cliente', 'nota_fiscal', 'status_atual', 'acao_em_espera', 'setor_atual')
    except Exception:
        qs = SAC.objects.filter(
            Q(setor_atual__nome__icontains='Finance')
            | Q(setor_atual__codigo__icontains='FINANC')
        ).select_related('empresa', 'cliente', 'nota_fiscal', 'status_atual', 'acao_em_espera', 'setor_atual')

    agora = timezone.now()
    sacs_disponiveis = sorted(
        [_montar_card_financeiro(sac, agora) for sac in qs],
        key=lambda item: (item['marco_tempo'], item['id'])
    )

    sac = None
    historicos_detalhados = []
    itens_contexto = None
    caso_aprovar_cobranca = False
    valor_manutencao = ''

    if sac_id:
        sac = get_object_or_404(
            SAC.objects.select_related('empresa', 'cliente', 'nota_fiscal', 'status_atual', 'acao_em_espera', 'setor_atual')
            .prefetch_related('itens_sac__item_nota_fiscal', 'itens_sac__tipo_ocorrencia', 'historicos'),
            id=sac_id
        )
        historicos_qs = sac.historicos.select_related(
            'usuario', 'status_novo', 'status_anterior', 'setor_destino', 'setor_origem'
        ).order_by('-data_evento', '-id')
        historicos_detalhados = montar_historico_detalhado(historicos_qs)
        itens_contexto = montar_contexto_itens_sac(sac, setor_contexto=getattr(sac, 'setor_atual', None))
        caso_aprovar_cobranca = _eh_aprovar_cobranca(sac)
        valor_manutencao = _buscar_valor_manutencao(sac)

        if request.method == 'POST' and request.POST.get('form_origem') == 'financeiro_aprovar_cobranca':
            decisao = (request.POST.get('cobranca_aprovada') or '').strip()
            motivo_reprovacao = (request.POST.get('motivo_reprovacao') or '').strip()
            observacao_financeira = (request.POST.get('observacao_financeira') or '').strip()

            if not caso_aprovar_cobranca:
                messages.error(request, 'Este SAC não está aguardando aprovação financeira de cobrança.')
                return redirect(f'/sac/gestao-financeira/?sac={sac.id}')

            if decisao not in {'Sim', 'Não'}:
                messages.error(request, 'Informe se a cobrança foi aprovada.')
                return redirect(f'/sac/gestao-financeira/?sac={sac.id}')

            if decisao == 'Não' and not motivo_reprovacao:
                messages.error(request, 'Informe o motivo da reprovação.')
                return redirect(f'/sac/gestao-financeira/?sac={sac.id}')

            status, acao, setor, faltam = _resolver_destino_financeiro(decisao)
            if faltam:
                messages.error(request, 'Fluxo financeiro não configurado: ' + '; '.join(faltam))
                return redirect(f'/sac/gestao-financeira/?sac={sac.id}')

            observacao = compor_observacao_padronizada(
                ('Ação financeira', ACAO_APROVAR_COBRANCA),
                ('Cobrança aprovada', decisao),
                ('Valor total da manutenção', valor_manutencao or '-'),
                ('Motivo da reprovação', motivo_reprovacao or '-'),
                ('Observação financeira', observacao_financeira or '-'),
                ('Próximo status', status.nome),
                ('Ação em Espera próximo Setor', acao.nome),
                ('Próximo setor', setor.nome),
                titulo='Histórico padronizado da Gestão Financeira',
            )

            try:
                aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    status_novo=status,
                    acao_em_espera=acao,
                    setor_destino=setor,
                    observacao=observacao,
                    acao_executada_texto='Gestão Financeira - aprovação de cobrança do serviço',
                )
            except Exception as exc:
                messages.error(request, f'Não foi possível aplicar a transição financeira: {exc}')
                return redirect(f'/sac/gestao-financeira/?sac={sac.id}')

            messages.success(request, 'Decisão financeira registrada com sucesso.')
            return redirect(f'/sac/gestao/?sac={sac.id}')

    return render(request, 'core/gestao_financeira.html', {
        'sac': sac,
        'sacs_disponiveis': sacs_disponiveis,
        'cards_pendentes': sacs_disponiveis,
        'total_sacs': len(sacs_disponiveis),
        'dados_sac_oficiais': montar_dados_sac_oficiais(sac),
        'historicos_detalhados': historicos_detalhados,
        'itens_contexto': itens_contexto,
        'caso_aprovar_cobranca': caso_aprovar_cobranca,
        'valor_manutencao': valor_manutencao,
    })
