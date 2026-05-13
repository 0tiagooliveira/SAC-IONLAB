from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import AcaoEmEspera, FluxoAcaoSetor, PecaTabelaPreco, SAC, SACAnexo, SacHistorico, Setor, StatusSAC
from core.services.fila_setorial import queryset_fila_por_setor
from core.services.historico_padronizado import compor_observacao_padronizada, montar_historico_detalhado
from core.services.sac_dados_padrao import montar_dados_padrao_sac
from core.services.sac_dados_oficiais import montar_dados_sac_oficiais
from core.services.sac_transicao_unificada import ErroTransicaoSAC, aplicar_transicao_sac
from core.services.sac_visual import (
    acao_em_espera_card, empresa_sac, formatar_numero_sac, nota_sac,
    resolver_setor_contexto_assistencia_tecnica, resumo_tempo_setor,
    status_anterior_card, montar_contexto_itens_sac,
)

TIPO_TECNICO = 'Técnico - Equipamento não funciona'
ACAO_INSPECAO = 'Aguardando Inspeção física e Funcional'
ACAO_MANUTENCAO_INTERNA = 'Aguardando Manutenção Interna'
TIPOS_PROBLEMA = ['Elétrico', 'Eletrônico', 'Mecânico', 'Motor', 'Ótico', 'Software', 'Térmicos']
TERMO_GARANTIA = (
    'materiais de uso e consumo bem como partes elétricas, eletrônicas e ótica possuem garantia de 3 meses conforme '
    'Prevista no termo de Garantia e CDC. Demais itens do equipamento possuí garantia até 12 meses contra defeito de fabricação. '
    'Qualquer Erro Operacional, ou dano elétrico causado por sobre carga, ou inobservância da voltagem do equipamento anulam qualquer tempo da garantia.'
)


def _norm(v):
    t = unicodedata.normalize('NFKD', str(v or '')).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Z0-9]+', ' ', t.upper()).strip()


def _nome(obj):
    return str(getattr(obj, 'nome', '') or obj or '').strip()


def _tempo_uso_dias_oficial(sac):
    """Retorna o tempo de uso oficial gravado no SAC, sem depender do histórico."""
    valor = getattr(sac, 'tempo_uso_dias', None)
    try:
        if valor is None or valor == '':
            return None
        valor = int(valor)
        return max(valor, 0)
    except (TypeError, ValueError):
        return None


def _formatar_tempo_uso_dias(dias):
    if dias is None:
        return ''
    meses = dias // 30
    resto = dias % 30
    if meses and resto:
        return f'{meses} meses e {resto} dias'
    if meses:
        return f'{meses} meses'
    return f'{resto} dias'


def _eh_caso_tecnico(sac):
    if not sac or _norm(_nome(sac.acao_em_espera)) != _norm(ACAO_INSPECAO):
        return False
    return any(_norm(_nome(i.tipo_ocorrencia)) == _norm(TIPO_TECNICO) for i in sac.itens_sac.all())


def _eh_manutencao_interna(sac):
    if not sac:
        return False
    return _norm(_nome(sac.acao_em_espera)) == _norm(ACAO_MANUTENCAO_INTERNA)


def _validar_hora_minuto(valor):
    texto = str(valor or '').strip()
    if not re.match(r'^\d{1,3}:[0-5]\d$', texto):
        return None
    horas, minutos = texto.split(':', 1)
    try:
        horas_i = int(horas)
        minutos_i = int(minutos)
    except ValueError:
        return None
    if horas_i < 0 or minutos_i < 0 or minutos_i > 59:
        return None
    return f'{horas_i:02d}:{minutos_i:02d}'


def _salvar_anexos_sac(sac, request):
    anexos_salvos = []
    for campo in ('fotos_manutencao[]', 'videos_manutencao[]'):
        for arquivo in request.FILES.getlist(campo):
            anexo = SACAnexo.objects.create(sac=sac, arquivo=arquivo)
            anexos_salvos.append(anexo)
    return anexos_salvos


def _anexos_sac_contexto(sac):
    if not sac:
        return []
    anexos = []
    try:
        qs = SACAnexo.objects.filter(sac=sac).order_by('-id')
    except Exception:
        return anexos
    for anexo in qs:
        arquivo = getattr(anexo, 'arquivo', None)
        if not arquivo:
            continue
        nome = str(getattr(arquivo, 'name', '') or '').split('/')[-1] or 'Anexo'
        url = ''
        try:
            url = arquivo.url
        except Exception:
            url = ''
        ext = nome.lower().rsplit('.', 1)[-1] if '.' in nome else ''
        anexos.append({
            'nome': nome,
            'url': url,
            'tipo': 'video' if ext in {'mp4', 'mov', 'avi', 'mkv', 'webm'} else ('imagem' if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'} else 'arquivo'),
        })
    return anexos


def _tempo_uso_historico(sac):
    """Lê o Tempo de uso gravado em históricos anteriores, tolerando variações de texto."""
    padroes = [
        r'tempo\s+de\s+uso(?:\s+do\s+equipamento)?\s*[:\-]\s*([^\n\r;]+)',
        r'tempo\s+uso\s*[:\-]\s*([^\n\r;]+)',
        r'uso\s+do\s+equipamento\s*[:\-]\s*([^\n\r;]+)',
    ]
    for h in sac.historicos.order_by('-data_evento', '-id')[:30]:
        obs = str(h.observacao or '')
        for padrao in padroes:
            m = re.search(padrao, obs, re.I)
            if m:
                valor = (m.group(1) or '').strip()
                # Remove restos comuns de histórico padronizado colado na mesma linha.
                valor = re.split(r'\s{2,}|\|', valor)[0].strip()
                if valor:
                    return valor
    return ''


def _meses(txt):
    s = _norm(txt).replace(',', '.')
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if not m:
        return None
    n = float(m.group(1))
    if 'ANO' in s:
        return n * 12
    if 'DIA' in s:
        return n / 30
    return n



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


def _moeda_br(valor):
    valor = _decimal_br(valor)
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _pecas_reposicao_json():
    dados = []
    try:
        qs = PecaTabelaPreco.objects.filter(ativo=True).order_by('referencia', 'descricao')
    except Exception:
        qs = PecaTabelaPreco.objects.all().order_by('referencia', 'descricao')
    for peca in qs[:1000]:
        dados.append({
            'referencia': str(peca.referencia or ''),
            'descricao': str(peca.descricao or ''),
            'valor_unitario': str(peca.valor_unitario or '0'),
        })
    return json.dumps(dados, ensure_ascii=False)


def _montar_orcamento_post(post):
    precisa = (post.get('precisa_peca_reposicao') or '').strip()
    refs = post.getlist('peca_referencia[]')
    descs = post.getlist('peca_descricao[]')
    qtds = post.getlist('peca_quantidade[]')
    valores = post.getlist('peca_valor_unitario[]')
    itens = []
    total_pecas = Decimal('0')
    if precisa == 'Sim':
        for i, ref in enumerate(refs):
            ref = (ref or '').strip()
            desc = (descs[i] if i < len(descs) else '').strip()
            qtd = _decimal_br(qtds[i] if i < len(qtds) else '0')
            valor = _decimal_br(valores[i] if i < len(valores) else '0')
            if not ref and not desc and qtd == 0 and valor == 0:
                continue
            total = qtd * valor
            total_pecas += total
            itens.append({
                'referencia': ref or '-',
                'descricao': desc or '-',
                'quantidade': qtd,
                'valor_unitario': valor,
                'total': total,
            })
    qtd_horas = _decimal_br(post.get('quantidade_horas'))
    valor_hora = _decimal_br(post.get('valor_unitario_hora'))
    total_horas = qtd_horas * valor_hora
    total_geral = total_pecas + total_horas
    return {
        'precisa': precisa or '-',
        'itens': itens,
        'qtd_horas': qtd_horas,
        'valor_hora': valor_hora,
        'total_horas': total_horas,
        'total_pecas': total_pecas,
        'total_geral': total_geral,
    }


def _resolver_fluxo_manutencao_interna(sac):
    """Resolve o próximo fluxo da manutenção interna a partir do cadastro FluxoAcaoSetor.

    Não usa hardcode de destino. Primeiro procura regra exata por ação atual + setor atual.
    Se não encontrar, aceita regra genérica da ação com setor_atual vazio.
    """
    if not sac or not getattr(sac, 'acao_em_espera_id', None):
        return None, ['Ação atual do SAC não encontrada.']

    qs = FluxoAcaoSetor.objects.filter(
        ativo=True,
        acao_atual=sac.acao_em_espera,
    ).select_related('proxima_acao', 'proximo_setor', 'status_destino', 'setor_atual')

    fluxo = None
    if getattr(sac, 'setor_atual_id', None):
        fluxo = qs.filter(setor_atual=sac.setor_atual).first()
    if fluxo is None:
        fluxo = qs.filter(setor_atual__isnull=True).first()

    if fluxo is None:
        return None, [
            'Fluxo não configurado para a combinação atual: '
            f'{_nome(sac.acao_em_espera)} / {_nome(sac.setor_atual)}.'
        ]

    faltam = []
    if not getattr(fluxo, 'status_destino_id', None):
        faltam.append('Status destino não configurado no FluxoAcaoSetor.')
    if not getattr(fluxo, 'proxima_acao_id', None):
        faltam.append('Próxima ação não configurada no FluxoAcaoSetor.')
    if not getattr(fluxo, 'proximo_setor_id', None):
        faltam.append('Próximo setor não configurado no FluxoAcaoSetor.')
    return fluxo, faltam

def _buscar(model, nome, codigos=()):
    alvo = _norm(nome)
    qs = model.objects.all()
    for c in codigos:
        obj = qs.filter(codigo__iexact=c).first()
        if obj:
            return obj
    for obj in qs:
        if _norm(getattr(obj, 'nome', '')) == alvo:
            return obj
    palavras = [p for p in alvo.split() if len(p) > 2]
    for obj in qs:
        n = _norm(getattr(obj, 'nome', ''))
        if all(p in n for p in palavras[:4]):
            return obj
    return None


def _calcular(tipo, erro, tempo_dias):
    tipo_norm = _norm(tipo)
    grupo_3_meses = {'ELETRICO', 'ELETRONICO', 'OTICO'}
    limite_dias = 90 if tipo_norm in grupo_3_meses else 365
    limite_texto = '3 meses' if limite_dias == 90 else '12 meses'

    if tempo_dias is None and erro != 'Sim':
        return {'erro': 'Tempo de uso oficial não encontrado nos Dados do SAC. Verifique se a abertura do SAC já foi atualizada com a data de emissão da NF ou NF de revenda.'}

    if erro == 'Sim' or (tempo_dias is not None and tempo_dias > limite_dias):
        return {
            'cobertura': 'Não', 'classe': 'negada', 'termo': TERMO_GARANTIA,
            'status': 'Aguardando Aprovação do Orçamento - Cliente',
            'acao': 'Aguardando Aprovação do Orçamento (cliente)', 'setor': 'SAC',
            'motivo': 'Erro operacional informado.' if erro == 'Sim' else f'Tempo de uso superior a {limite_texto}.',
            'limite_texto': limite_texto,
        }
    return {
        'cobertura': 'Dentro do período de garantia', 'classe': 'aprovada', 'termo': '',
        'status': 'Em Manutenção', 'acao': 'Aguardando Manutenção Interna', 'setor': 'Assistência Técnica',
        'motivo': f'Tempo de uso dentro do limite de {limite_texto}.',
        'limite_texto': limite_texto,
    }


def _codigos_setor_destino(nome_setor):
    alvo = _norm(nome_setor)
    if alvo == 'SAC':
        return ('SAC',)
    if 'ASSISTENCIA' in alvo or 'TECNICA' in alvo:
        return ('ASSISTENCIA_TECNICA', 'ASSISTENCIA', 'TECNICA')
    return ()


def _destinos(r):
    st = _buscar(StatusSAC, r['status'])
    ac = _buscar(AcaoEmEspera, r['acao'])
    se = _buscar(Setor, r['setor'], codigos=_codigos_setor_destino(r['setor']))
    faltam = []
    if not st: faltam.append('Status: ' + r['status'])
    if not ac: faltam.append('Ação em espera: ' + r['acao'])
    if not se: faltam.append('Setor: ' + r['setor'])
    return st, ac, se, faltam


@login_required
def gestao_assistencia_tecnica(request, sac_id=None):
    sac_id = sac_id or request.GET.get('sac')
    qs = queryset_fila_por_setor(nome_setor='Assistência Técnica')
    try:
        if not qs.exists():
            qs = SAC.objects.filter(Q(setor_atual__nome__icontains='Assist') | Q(setor_atual__codigo__icontains='ASSIST') | Q(setor_atual__codigo__icontains='TECN')).select_related('empresa','cliente','nota_fiscal','status_atual','acao_em_espera','setor_atual')
    except Exception:
        qs = SAC.objects.filter(Q(setor_atual__nome__icontains='Assist') | Q(setor_atual__codigo__icontains='ASSIST') | Q(setor_atual__codigo__icontains='TECN')).select_related('empresa','cliente','nota_fiscal','status_atual','acao_em_espera','setor_atual')

    agora = timezone.now()
    sacs_disponiveis = []
    for s in qs:
        tempo = resumo_tempo_setor(s, agora=agora)
        cliente = getattr(s, 'cliente', None)
        sacs_disponiveis.append({
            'id': s.id, 'numero': formatar_numero_sac(s), 'numero_sac': formatar_numero_sac(s),
            'cliente_nome': getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None) or '-',
            'empresa_nome': empresa_sac(s), 'nota_fiscal_numero': nota_sac(s),
            'status_atual_nome': status_anterior_card(s), 'acao_em_espera_nome': acao_em_espera_card(s),
            'tempo_espera': tempo['tempo_espera'], 'tempo_cor': tempo['tempo_cor'], 'marco_tempo': tempo['marco_tempo'],
        })
    sacs_disponiveis = sorted(sacs_disponiveis, key=lambda x: (x['marco_tempo'], x['id']))

    sac = None; historicos = []; historicos_detalhados = []; itens_contexto = None
    caso_inspecao_tecnica = False; caso_manutencao_interna = False; tempo_uso_dias_oficial = None; tempo_uso_formatado = ''; anexos_sac = []
    if sac_id:
        sac = get_object_or_404(SAC.objects.select_related('empresa','cliente','nota_fiscal','status_atual','acao_em_espera','setor_atual').prefetch_related('itens_sac__item_nota_fiscal','itens_sac__tipo_ocorrencia'), id=sac_id)
        historicos = sac.historicos.select_related('usuario','status_novo','status_anterior','setor_destino','setor_origem').order_by('-data_evento','-id')
        historicos_detalhados = montar_historico_detalhado(historicos)
        itens_contexto = montar_contexto_itens_sac(sac, setor_contexto=getattr(sac, 'setor_atual', None))
        caso_inspecao_tecnica = _eh_caso_tecnico(sac)
        caso_manutencao_interna = _eh_manutencao_interna(sac)
        anexos_sac = _anexos_sac_contexto(sac)
        tempo_uso_dias_oficial = _tempo_uso_dias_oficial(sac)
        tempo_uso_formatado = _formatar_tempo_uso_dias(tempo_uso_dias_oficial)
        if request.method == 'POST' and request.POST.get('form_origem') == 'assistencia_tecnica_manutencao_interna':
            equipamento_consertado = (request.POST.get('equipamento_consertado') or '').strip()
            tempo_efetivo = _validar_hora_minuto(request.POST.get('tempo_efetivo_manutencao'))
            informacoes_adicionais = (request.POST.get('informacoes_adicionais_manutencao') or '').strip()
            equipamento_inconsertavel = (request.POST.get('equipamento_inconsertavel') or '').strip()
            motivos_tecnicos = (request.POST.get('motivos_tecnicos_inconsertavel') or '').strip()

            if not caso_manutencao_interna:
                messages.error(request, 'Este SAC não está aguardando manutenção interna.')
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            if equipamento_consertado not in {'Sim', 'Não'}:
                messages.error(request, 'Informe se o equipamento foi consertado.')
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            if equipamento_consertado == 'Sim' and not tempo_efetivo:
                messages.error(request, 'Informe o tempo efetivo gasto da manutenção no formato hh:mm.')
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            if equipamento_consertado == 'Não':
                if equipamento_inconsertavel not in {'Sim', 'Não'}:
                    messages.error(request, 'Informe se o equipamento é inconsertável.')
                    return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
                if equipamento_inconsertavel == 'Não':
                    messages.error(request, 'Retornar e dar continuidade quando o equipamento estiver consertado')
                    return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
                if equipamento_inconsertavel == 'Sim' and not motivos_tecnicos:
                    messages.error(request, 'Descreva os motivos técnicos para classificar o equipamento como inconsertável.')
                    return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')

            anexos_salvos = _salvar_anexos_sac(sac, request)
            hist = compor_observacao_padronizada(
                ('Tipo de ocorrência', TIPO_TECNICO),
                ('Ação analisada', ACAO_MANUTENCAO_INTERNA),
                ('Equipamento Consertado', equipamento_consertado),
                ('Tempo efetivo gasto da Manutenção', tempo_efetivo if equipamento_consertado == 'Sim' else '-'),
                ('Informações adicionais', informacoes_adicionais or '-'),
                ('Equipamento Inconsertável', equipamento_inconsertavel if equipamento_consertado == 'Não' else '-'),
                ('Motivos técnicos', motivos_tecnicos if equipamento_consertado == 'Não' and equipamento_inconsertavel == 'Sim' else '-'),
                ('Anexos incluídos', len(anexos_salvos)),
                titulo='Histórico padronizado da Manutenção Interna - Assistência Técnica',
            )
            fluxo, faltam_fluxo = _resolver_fluxo_manutencao_interna(sac)
            if faltam_fluxo:
                messages.error(request, 'Fluxo da manutenção interna não configurado: ' + '; '.join(faltam_fluxo))
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')

            hist = hist + '\n\n' + compor_observacao_padronizada(
                ('Próximo status', fluxo.status_destino.nome),
                ('Ação em Espera próximo Setor', fluxo.proxima_acao.nome),
                ('Próximo setor', fluxo.proximo_setor.nome),
                titulo='Encaminhamento automático da Manutenção Interna',
            )

            try:
                aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    acao_em_espera=fluxo.proxima_acao,
                    setor_destino=fluxo.proximo_setor,
                    status_novo=fluxo.status_destino,
                    observacao=hist,
                    acao_executada_texto='Manutenção interna registrada e encaminhada',
                )
            except ErroTransicaoSAC as exc:
                messages.error(request, str(exc))
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')

            messages.success(request, f'Manutenção interna do SAC {sac.numero} registrada e encaminhada com sucesso.')
            return redirect('/sac/assistencia-tecnica/')

        if request.method == 'POST' and request.POST.get('form_origem') == 'assistencia_tecnica_inspecao':
            tipo = (request.POST.get('tipo_problema') or '').strip()
            erro = (request.POST.get('erro_operacional') or '').strip()
            obs = (request.POST.get('observacao_tecnica') or '').strip()
            if not caso_inspecao_tecnica or not tipo or not erro:
                messages.error(request, 'Preencha os campos obrigatórios da inspeção técnica.')
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            r = _calcular(tipo, erro, tempo_uso_dias_oficial)
            if r.get('erro'):
                messages.error(request, r['erro'])
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            orcamento = _montar_orcamento_post(request.POST) if r.get('cobertura') == 'Não' else None
            if orcamento and orcamento['precisa'] not in {'Sim', 'Não'}:
                messages.error(request, 'Informe se será necessário peça de reposição.')
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            if orcamento and orcamento['precisa'] == 'Sim' and not orcamento['itens']:
                messages.error(request, 'Informe ao menos uma peça de reposição ou selecione Necessário peças de reposição = Não.')
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            if orcamento and (orcamento['qtd_horas'] <= 0 or orcamento['valor_hora'] <= 0):
                messages.error(request, 'Informe quantidade de horas e valor unitário das horas para gerar o orçamento.')
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            st, ac, se, faltam = _destinos(r)
            if faltam:
                messages.error(request, 'Fluxo não configurado: ' + '; '.join(faltam))
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            hist = compor_observacao_padronizada(
                ('Tipo de ocorrência', TIPO_TECNICO), ('Ação analisada', ACAO_INSPECAO), ('Tempo de uso', tempo_uso_formatado or '-'),
                ('Tipo de problema', tipo), ('Indícios de Erros Operacionais - uso humano', erro), ('Coberto pela Garantia', r['cobertura']),
                ('Termo de Cobertura da Garantia', r.get('termo') or '-'), ('Motivo da decisão', r['motivo']),
                ('Necessário peças de reposição', orcamento['precisa'] if orcamento else '-'),
                ('Peças de reposição', '; '.join([f"{it['referencia']} - {it['descricao']} | Qtde {it['quantidade']} | Unit. {_moeda_br(it['valor_unitario'])} | Total {_moeda_br(it['total'])}" for it in (orcamento['itens'] if orcamento else [])]) or '-'),
                ('Valor total das peças', _moeda_br(orcamento['total_pecas']) if orcamento else '-'),
                ('Quantidade de horas', orcamento['qtd_horas'] if orcamento else '-'),
                ('Valor unitário das horas', _moeda_br(orcamento['valor_hora']) if orcamento else '-'),
                ('Valor total das horas', _moeda_br(orcamento['total_horas']) if orcamento else '-'),
                ('Valor total do orçamento', _moeda_br(orcamento['total_geral']) if orcamento else '-'),
                ('Próximo status', st.nome), ('Ação em Espera próximo Setor', ac.nome), ('Próximo setor', se.nome),
                ('Observações da Assistência Técnica', obs or '-'), titulo='Histórico padronizado da Assistência Técnica')
            try:
                aplicar_transicao_sac(sac=sac, usuario=request.user, acao_em_espera=ac, setor_destino=se, status_novo=st, observacao=hist, acao_executada_texto='Inspeção física e funcional registrada')
            except ErroTransicaoSAC as exc:
                messages.error(request, str(exc))
                return redirect(f'/sac/assistencia-tecnica/?sac={sac.id}')
            messages.success(request, f'Inspeção técnica do SAC {sac.numero} registrada com sucesso.')
            return redirect('/sac/assistencia-tecnica/')

    setor_contexto = resolver_setor_contexto_assistencia_tecnica(sac)
    return render(request, 'core/gestao_assistencia_tecnica.html', {
        'sac': sac, 'historicos': historicos, 'historicos_detalhados': historicos_detalhados,
        'dados_sac': montar_dados_padrao_sac(sac, setor_contexto=setor_contexto),
        'dados_sac_oficiais': montar_dados_sac_oficiais(sac),
        'itens_contexto': itens_contexto,
        'sacs_disponiveis': sacs_disponiveis, 'cards_pendentes': sacs_disponiveis, 'total_sacs': len(sacs_disponiveis),
        'caso_inspecao_tecnica': caso_inspecao_tecnica, 'caso_manutencao_interna': caso_manutencao_interna, 'tempo_uso_dias_oficial': tempo_uso_dias_oficial, 'tempo_uso_formatado': tempo_uso_formatado, 'anexos_sac': anexos_sac,
        'tipos_problema_assistencia': TIPOS_PROBLEMA, 'termo_garantia_negada': TERMO_GARANTIA,
        'pecas_reposicao_json': _pecas_reposicao_json(),
    })
