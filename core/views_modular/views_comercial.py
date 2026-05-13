from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.services.sac_dados_oficiais import montar_dados_sac_oficiais

from core.forms import AnaliseComercialSACForm
from core.models import SAC, AcaoEmEspera, SacAnaliseComercial, Setor
from core.services.empresa_filtro import aplicar_filtro_empresa, resolver_filtro_empresa
from core.services.fluxo_sac import diagnosticar_fluxo_inicial, validar_transicao_basica
from core.services.sac_transicao_unificada import aplicar_transicao_sac
from core.services.sac_bridge import (
    obter_setor_por_nome,
    sac_aguardando_acao_comercial_queryset,
    texto_normalizado as _texto_normalizado,
)
from core.services.historico_padronizado import compor_observacao_padronizada, montar_historico_detalhado
from core.services.sac_visual import (
    acao_em_espera_card as _acao_em_espera_card,
    classe_tempo_espera as _classe_tempo_espera,
    data_nota_sac as _data_nota_sac,
    empresa_sac as _empresa_sac,
    formatar_numero_sac,
    formatar_tempo_espera as _formatar_tempo_espera,
    montar_contexto_itens_sac,
    montar_grafico_tempo_status_sac,
    nota_sac as _nota_sac,
    resolver_setor_contexto_comercial,
    status_anterior_card as _status_anterior_card,
)

def analise_comercial_sac(request, sac_id=None):
    empresa_filtro, contexto_empresa = resolver_filtro_empresa(request)
    sacs_pendentes_qs = sac_aguardando_acao_comercial_queryset()
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
        data_referencia = _data_nota_sac(sac_item) or sac_item.data_abertura
        cards_pendentes.append({
            'id': sac_item.id,
            'numero': formatar_numero_sac(sac_item),
            'numero_sac': formatar_numero_sac(sac_item),
            'empresa_nome': _empresa_sac(sac_item),
            'cliente_nome': cliente_nome,
            'nota_fiscal_numero': _nota_sac(sac_item),
            'data_referencia': data_referencia,
            'status_atual_nome': _status_anterior_card(sac_item),
            'acao_em_espera_nome': _acao_em_espera_card(sac_item),
            'tempo_espera': _formatar_tempo_espera(agora - marco),
            'tempo_cor': _classe_tempo_espera(agora - marco),
            'marco_tempo': marco,
            'linha_resumo': ' / '.join([
                sac_item.numero or f'SAC {sac_item.id}',
                _empresa_sac(sac_item),
                cliente_nome,
                _nota_sac(sac_item),
                data_referencia.strftime('%d/%m/%Y') if data_referencia else '-',
            ]),
            'selecionado': str(sac_item.id) == str(sac_id_selecionado),
        })

    cards_pendentes = sorted(cards_pendentes, key=lambda x: (x['marco_tempo'], x['id']))

    if sac_id_selecionado:
        sac = sacs_pendentes_qs.filter(id=sac_id_selecionado).first()
        if sac is None:
            sac = get_object_or_404(
                SAC.objects.select_related('empresa', 'cliente', 'nota_fiscal', 'status_atual', 'acao_em_espera', 'setor_atual').prefetch_related('itens_sac__item_nota_fiscal', 'itens_sac__tipo_ocorrencia__setor'),
                id=sac_id_selecionado
            )

    historico = []
    itens_contexto = None
    itens_sac = []
    form = None
    setor_contexto_comercial = None
    acao_em_espera_atual = '-'
    usuario_anterior_nome = '-'

    setores_proximo = list(Setor.objects.all().order_by('nome'))
    mapa_acao_setor = {}
    for acao in AcaoEmEspera.objects.select_related('setor_destino').all():
        nome_acao = (acao.nome or '').strip()
        manual = _texto_normalizado(nome_acao) == 'analise do ocorrido'
        mapa_acao_setor[str(acao.id)] = {
            'manual': manual,
            'setor_id': str(acao.setor_destino.id) if getattr(acao, 'setor_destino', None) else '',
            'setor_nome': acao.setor_destino.nome if getattr(acao, 'setor_destino', None) else '',
        }

    proximo_setor_id = request.POST.get('proximo_setor') or request.POST.get('proximo_setor_id') or ''

    if sac:
        historico = sac.historicos.select_related('usuario', 'status_novo', 'setor_destino', 'setor_origem').order_by('-data_evento', '-id')[:20]
        historicos_detalhados = montar_historico_detalhado(historico)
        grafico_tempo_status = montar_grafico_tempo_status_sac(sac)
        itens_sac = sac.itens_sac.select_related('item_nota_fiscal', 'tipo_ocorrencia').all()
        setor_contexto = sac.setor_atual or obter_setor_por_nome('SAC')
        itens_contexto = montar_contexto_itens_sac(sac, setor_contexto=setor_contexto)
        setor_contexto_comercial = resolver_setor_contexto_comercial(sac)
        acao_em_espera_atual = sac.acao_em_espera.nome if getattr(sac, 'acao_em_espera', None) else '-'
        if historico:
            usuario_hist = getattr(historico[0], 'usuario', None)
            if usuario_hist:
                usuario_anterior_nome = usuario_hist.get_full_name() or usuario_hist.username or '-'

        if request.method == 'POST':
            form = AnaliseComercialSACForm(request.POST, sac=sac, setor_contexto=setor_contexto_comercial)
            if form.is_valid():
                cliente_confirmou = form.cleaned_data['cliente_confirmou_pedido'] == 'sim'
                cliente_aceita = (form.cleaned_data.get('cliente_aceita_negociacao') or 'nao') == 'sim'
                cliente_aceitou_contra = (form.cleaned_data.get('cliente_aceitou_contra_proposta') or '') == 'sim'
                valor_desconto = form.cleaned_data.get('valor_desconto_pleiteado')
                contra_proposta = (form.cleaned_data.get('contra_proposta_visual') or '').strip()
                proximo_status = form.cleaned_data.get('proximo_status_sugerido')
                acao_em_espera = form.cleaned_data.get('acao_em_espera')
                observacao = (form.cleaned_data.get('observacao_comercial') or '').strip()

                item_pequeno_valor = (form.cleaned_data.get('item_pequeno_valor') or 'nao') == 'sim'
                proximo_setor = form.cleaned_data.get('proximo_setor')
                modo_contra_proposta = getattr(form, 'modo_contra_proposta', False)

                nome_status = _texto_normalizado(proximo_status.nome if proximo_status else '')
                proximo_setor_id = str(proximo_setor.id) if proximo_setor else ''

                if nome_status == 'concluido' and itens_contexto and itens_contexto.get('itens_outros_setores'):
                    messages.error(request, 'Bloqueado: este SAC ainda possui item pendente de ação em outro setor e não pode ser concluído.')
                    return redirect(f'/sac/analise-comercial/?sac={sac.id}')

                observacao_salva = observacao
                if valor_desconto not in (None, ''):
                    valor_desconto_txt = f"{Decimal(valor_desconto):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    bloco_desconto = f"Valor do desconto pleiteado: R$ {valor_desconto_txt}"
                    observacao_salva = (observacao_salva + '\n' + bloco_desconto).strip() if observacao_salva else bloco_desconto

                SacAnaliseComercial.objects.update_or_create(
                    sac=sac,
                    defaults={
                        'cliente_confirmou_pedido': cliente_confirmou,
                        'cliente_aceita_negociacao': cliente_aceita,
                        'proximo_status_sugerido': proximo_status,
                        'acao_em_espera': acao_em_espera,
                        'valor_desconto_pleiteado': valor_desconto,
                        'observacao_comercial': observacao_salva,
                        'usuario_responsavel': request.user,
                        'data_analise': timezone.now(),
                    }
                )

                pares_historico = []
                if modo_contra_proposta:
                    pares_historico.extend([
                        ("Contra Proposta", contra_proposta or '-'),
                        ("Cliente aceitou a contra proposta", 'Sim' if cliente_aceitou_contra else 'Não'),
                    ])
                else:
                    pares_historico.extend([
                        ("Cliente confirmou o pedido", 'Sim' if cliente_confirmou else 'Não'),
                        ("Cliente aceita negociação", 'Sim' if cliente_aceita else 'Não'),
                        ("Item de pequeno valor", 'Sim' if item_pequeno_valor else 'Não'),
                    ])
                if valor_desconto not in (None, ''):
                    valor_desconto_txt = f"{Decimal(valor_desconto):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    pares_historico.append(("Valor do desconto pleiteado", f"R$ {valor_desconto_txt}"))
                pares_historico.extend([
                    ("Próximo status", proximo_status.nome if proximo_status else '-'),
                    ("Ação em espera", acao_em_espera.nome if acao_em_espera else '-'),
                    ("Próximo setor", proximo_setor.nome if proximo_setor else '-'),
                    ("Observações comerciais", observacao or '-'),
                ])
                observacao_historico = compor_observacao_padronizada(*pares_historico, titulo='Histórico padronizado da Gestão Comercial')

                setor_destino_validacao = None if nome_status == 'concluido' else (proximo_setor or sac.setor_atual)

                validar_transicao_basica(
                    sac,
                    status_novo=proximo_status or sac.status_atual,
                    acao_nova=acao_em_espera,
                    setor_destino=setor_destino_validacao if setor_destino_validacao is not None else sac.setor_atual,
                )

                aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    acao_em_espera=acao_em_espera if nome_status != 'concluido' else None,
                    setor_destino=proximo_setor if nome_status != 'concluido' else None,
                    status_novo=proximo_status or sac.status_atual,
                    observacao=observacao_historico,
                    acao_executada_texto='Análise comercial registrada',
                )

                messages.success(request, f'Análise comercial do SAC {sac.numero} registrada com sucesso.')
                return redirect('/sac/analise-comercial/')
        else:
            form = AnaliseComercialSACForm(sac=sac, setor_contexto=setor_contexto_comercial)
            if form and getattr(form, '_fluxo_resolvido', None):
                fluxo_setor = getattr(form._fluxo_resolvido, 'proximo_setor', None)
                proximo_setor_id = str(getattr(fluxo_setor, 'id', '') or '')

    return render(request, 'core/analise_comercial_sac.html', {
        'sac': sac,
        'dados_sac_oficiais': montar_dados_sac_oficiais(sac),
        'historico': historico,
        'historicos_detalhados': locals().get('historicos_detalhados', []),
        'itens_sac': itens_sac,
        'itens_contexto': itens_contexto,
        'form': form,
        'sacs_aguardando_acao_comercial': cards_pendentes,
        'sacs_disponiveis': cards_pendentes,
        'cards_pendentes': cards_pendentes,
        'total_sacs': len(cards_pendentes),
        'setores_proximo': setores_proximo,
        'proximo_setor_id': proximo_setor_id,
        'mapa_acao_setor_json': json.dumps(mapa_acao_setor),
        'setor_contexto_comercial': setor_contexto_comercial,
        'fluxo_comercial_padrao': getattr(form, '_preview_fluxo_padrao', {}),
        'fluxo_comercial_negociacao': getattr(form, '_preview_fluxo_negociacao', {}),
        'fluxo_comercial_confirmado': getattr(form, '_preview_fluxo_confirmado', {}),
        'fluxo_comercial_sem_negociacao': getattr(form, '_preview_fluxo_sem_negociacao', {}),
        'fluxo_comercial_doacao_brinde': getattr(form, '_preview_fluxo_doacao_brinde', {}),
        'fluxo_contra_aceita': getattr(form, '_preview_fluxo_contra_aceita', {}),
        'fluxo_contra_recusa': getattr(form, '_preview_fluxo_contra_recusa', {}),
        'acao_em_espera_atual': acao_em_espera_atual,
        'usuario_anterior_nome': usuario_anterior_nome,
        **contexto_empresa,
        'fluxo_alertas': diagnosticar_fluxo_inicial(sac, setor_contexto=getattr(sac, 'setor_atual', None), nome_tela='Gestão Comercial') if sac else [],
    })
