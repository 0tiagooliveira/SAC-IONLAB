import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.forms import GestaoSACPedidoRetornoForm
from core.models import SAC, SACAnexo, StatusSAC, AcaoEmEspera, Setor
from core.services.fluxo_sac import validar_transicao_basica
from core.services.sac_transicao_unificada import aplicar_transicao_sac
from core.services.sac_dados_padrao import montar_dados_padrao_sac
from core.services.sac_dados_oficiais import montar_dados_sac_oficiais
from core.services.empresa_filtro import aplicar_filtro_empresa, resolver_filtro_empresa
from core.services.fila_setorial import queryset_fila_por_setor
from core.services.sac_visual import obter_setor_por_codigo, montar_contexto_itens_sac, formatar_duracao_dd_hh_mm, formatar_numero_sac, resumo_tempo_setor
from core.services.historico_padronizado import compor_observacao_padronizada, montar_historico_detalhado


def _formatar_tempo(delta):
    return formatar_duracao_dd_hh_mm(delta)


def _classe_tempo(delta):
    total_horas = max(delta.total_seconds(), 0) / 3600
    if total_horas < 12:
        return "tempo-verde"
    if total_horas < 24:
        return "tempo-amarelo"
    return "tempo-vermelho"


def _normalizar_texto_gestao(valor):
    import unicodedata
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    return texto.strip().lower()


def _obter_tipo_ocorrencia_gestao(sac):
    if not sac:
        return ''
    try:
        for item in sac.itens_sac.select_related('tipo_ocorrencia').all():
            nome = (getattr(getattr(item, 'tipo_ocorrencia', None), 'nome', '') or '').strip()
            if nome:
                return nome
    except Exception:
        return ''
    return ''


def _eh_tecnico_equipamento_gestao(tipo_nome):
    return _normalizar_texto_gestao(tipo_nome) == 'tecnico - equipamento nao funciona'


def _eh_acao_autorizar_manutencao_interna_gestao(acao_nome):
    texto = _normalizar_texto_gestao(acao_nome)
    return (
        'manutencao' in texto
        and 'interna' in texto
        and ('autorizar' in texto or 'autorizacao' in texto)
    )


def _eh_emissao_pedido_saida_gestao(acao_nome):
    texto = _normalizar_texto_gestao(acao_nome)
    return (
        'aguardando emissao do pedido' in texto
        and 'saida' in texto
    )


def _buscar_cobertura_garantia_gestao(sac):
    """Busca no histórico padronizado se o equipamento foi coberto pela garantia."""
    if not sac:
        return '-'
    try:
        historicos = sac.historicos.order_by('-data_evento', '-id')[:80]
    except Exception:
        return '-'

    for hist in historicos:
        obs = str(getattr(hist, 'observacao', '') or '')
        obs_norm = _normalizar_texto_gestao(obs)

        # Caso explícito de negativa.
        if 'coberto pela garantia' in obs_norm or 'cobertura da garantia' in obs_norm:
            linhas = [linha.strip() for linha in obs.splitlines() if linha.strip()]
            for linha in linhas:
                linha_norm = _normalizar_texto_gestao(linha)
                if 'garantia' not in linha_norm:
                    continue
                if ': nao' in linha_norm or ': não' in linha_norm or linha_norm.endswith(' nao') or linha_norm.endswith(' não'):
                    return 'Não'
                if 'dentro do periodo de garantia' in linha_norm or 'dentro do período de garantia' in linha_norm:
                    return 'Sim'
                if ': sim' in linha_norm or linha_norm.endswith(' sim'):
                    return 'Sim'

        # Fallback para textos gerados pela Assistência Técnica.
        if 'coberto pela garantia nao' in obs_norm or 'coberto pela garantia não' in obs_norm:
            return 'Não'
        if 'dentro do periodo de garantia' in obs_norm or 'dentro do período de garantia' in obs_norm:
            return 'Sim'

    return '-'


def _buscar_valor_total_manutencao_gestao(sac):
    """Busca o valor total do orçamento/manutenção no histórico mais recente."""
    if not sac:
        return '-'
    padroes = [
        r'Valor\s+total\s+da\s+Manuten[cç][aã]o\s*[:\-]\s*([^\n\r]+)',
        r'Valor\s+total\s+do\s+or[cç]amento\s*[:\-]\s*([^\n\r]+)',
        r'Total\s+geral\s+do\s+or[cç]amento\s*[:\-]\s*([^\n\r]+)',
        r'Valor\s+total\s+geral\s*[:\-]\s*([^\n\r]+)',
    ]
    try:
        historicos = sac.historicos.order_by('-data_evento', '-id')[:80]
    except Exception:
        return '-'
    for hist in historicos:
        obs = str(getattr(hist, 'observacao', '') or '')
        for padrao in padroes:
            m = re.search(padrao, obs, re.IGNORECASE)
            if m:
                valor = (m.group(1) or '').strip()
                valor = valor.split('|')[0].strip()
                return valor or '-'
    return '-'


def _resolver_por_nome_gestao(modelo, *nomes):
    for nome in nomes:
        obj = modelo.objects.filter(nome__iexact=nome).first()
        if obj:
            return obj
    nomes_norm = [_normalizar_texto_gestao(n) for n in nomes if n]
    for obj in modelo.objects.all():
        nome_norm = _normalizar_texto_gestao(getattr(obj, 'nome', '') or '')
        if nome_norm in nomes_norm:
            return obj
    for obj in modelo.objects.all():
        nome_norm = _normalizar_texto_gestao(getattr(obj, 'nome', '') or '')
        for alvo in nomes_norm:
            partes = [p for p in alvo.split() if len(p) > 2]
            if partes and all(p in nome_norm for p in partes[:5]):
                return obj
    return None


def _resolver_setor_gestao(*nomes_ou_codigos):
    for valor in nomes_ou_codigos:
        if not valor:
            continue
        obj = Setor.objects.filter(codigo__iexact=valor).first()
        if obj:
            return obj
        obj = Setor.objects.filter(nome__iexact=valor).first()
        if obj:
            return obj
    return _resolver_por_nome_gestao(Setor, *nomes_ou_codigos)


def _redirect_setor_gestao(sac, setor_destino, fallback='/sac/gestao/'):
    setor_nome = _normalizar_texto_gestao(getattr(setor_destino, "nome", ""))
    setor_codigo = _normalizar_texto_gestao(getattr(setor_destino, "codigo", ""))
    if "assistencia" in setor_nome or "assistencia" in setor_codigo or "tecnica" in setor_nome:
        return redirect(f"/sac/{sac.id}/assistencia-tecnica/")
    if "logistica" in setor_nome or "logistica" in setor_codigo:
        return redirect(f"/sac/{sac.id}/gestao-logistica/")
    if "licitacao" in setor_nome or "licitacao" in setor_codigo:
        return redirect(f"/sac/{sac.id}/gestao-licitacao/")
    if "comercial" in setor_nome or "comercial" in setor_codigo:
        return redirect(f"/sac/{sac.id}/analise-comercial/")
    if "assessoria" in setor_nome or "cientifica" in setor_nome or "assessoria" in setor_codigo:
        return redirect(f"/sac/{sac.id}/analise-tecnica/")
    if "diretoria" in setor_nome or "diretoria" in setor_codigo:
        return redirect(f"/sac/diretoria/?sac={sac.id}")
    if "financeiro" in setor_nome or "financeiro" in setor_codigo:
        return redirect(f"/sac/gestao/?sac={sac.id}")
    return redirect(fallback)


def _destino_emissao_pedido_saida_gestao(garantia):
    garantia_norm = _normalizar_texto_gestao(garantia)
    if garantia_norm == 'sim':
        status = _resolver_por_nome_gestao(StatusSAC, 'Emissão Nota Fiscal de Saída', 'Emissao Nota Fiscal de Saida', 'Emissão da Nota Fiscal de Saída')
        acao = _resolver_por_nome_gestao(AcaoEmEspera, 'Aguardando emissão da nota fiscal (Saída)', 'Aguardando Emissão da Nota fiscal (Saída)', 'Aguardando emissao da nota fiscal (Saida)')
        setor = _resolver_setor_gestao('LOGISTICA', 'Logística', 'Logistica')
        return status, acao, setor, 'Emissão Nota Fiscal de Saída', 'Aguardando emissão da nota fiscal (Saída)', 'Logística'

    status = _resolver_por_nome_gestao(StatusSAC, 'Em Análise Financeira', 'Em Analise Financeira')
    acao = _resolver_por_nome_gestao(AcaoEmEspera, 'Aprovar Cobrança do Valor do Serviço', 'Aprovar Cobranca do Valor do Servico')
    setor = _resolver_setor_gestao('FINANCEIRO', 'Financeiro')
    return status, acao, setor, 'Em Análise Financeira', 'Aprovar Cobrança do Valor do Serviço', 'Financeiro'


def _formatar_data_br_gestao(valor):
    if not valor:
        return '-'
    try:
        return valor.strftime('%d/%m/%Y')
    except Exception:
        return str(valor)


def _calcular_tempo_uso_gestao(data_inicio, data_fim):
    if not data_inicio or not data_fim:
        return '-'
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
    meses = (data_fim.year - data_inicio.year) * 12 + (data_fim.month - data_inicio.month)
    dias = data_fim.day - data_inicio.day
    if dias < 0:
        meses -= 1
        import calendar
        mes_anterior = data_fim.month - 1 or 12
        ano_mes_anterior = data_fim.year if data_fim.month > 1 else data_fim.year - 1
        dias += calendar.monthrange(ano_mes_anterior, mes_anterior)[1]
    partes = []
    if meses:
        partes.append(f'{meses} mês' + ('es' if meses != 1 else ''))
    partes.append(f'{dias} dia' + ('s' if dias != 1 else ''))
    return ' e '.join(partes)


def _dados_manutencao_interna_gestao(sac, data_venda_usuario=None):
    nota = getattr(sac, 'nota_fiscal', None) if sac else None
    numero_nf = getattr(nota, 'numero_nf', None) or getattr(nota, 'numero', None) or '-'
    data_nf = getattr(nota, 'data_emissao', None)
    data_base = data_venda_usuario or data_nf
    data_abertura = getattr(sac, 'data_abertura', None) if sac else None
    if hasattr(data_abertura, 'date'):
        data_abertura = data_abertura.date()
    return {
        'nota_fiscal_venda': numero_nf,
        'data_emissao_nf_venda': _formatar_data_br_gestao(data_nf),
        'data_emissao_nf_venda_iso': data_nf.strftime('%Y-%m-%d') if hasattr(data_nf, 'strftime') else '',
        'data_abertura_iso': data_abertura.strftime('%Y-%m-%d') if hasattr(data_abertura, 'strftime') else '',
        'tempo_uso': _calcular_tempo_uso_gestao(data_base, data_abertura),
    }


def _montar_card_gestao(s, agora):
    tempo = resumo_tempo_setor(s, agora=agora)
    data_agendamento = getattr(s, 'data_agendamento_gestao', None)
    return {
        "id": s.id,
        "numero": formatar_numero_sac(s),
        "numero_sac": formatar_numero_sac(s),
        "cliente_nome": getattr(getattr(s, "cliente", None), "razao_social", "") or getattr(getattr(s, "cliente", None), "nome", "") or "-",
        "empresa_nome": getattr(getattr(s, "empresa", None), "nome_fantasia", "") or getattr(getattr(s, "empresa", None), "razao_social", "") or getattr(getattr(s, "empresa", None), "nome", "") or "-",
        "nota_fiscal_numero": getattr(getattr(s, "nota_fiscal", None), "numero_nf", "") or getattr(getattr(s, "nota_fiscal", None), "numero", "") or "-",
        "status_atual_nome": getattr(getattr(s, "status_atual", None), "nome", "-") or getattr(getattr(s, "status", None), "nome", "-"),
        "acao_em_espera_nome": getattr(getattr(s, "acao_em_espera", None), "nome", "-"),
        "tipo_ocorrencia_nome": _obter_tipo_ocorrencia_gestao(s) or "-",
        "data_agendamento_gestao": data_agendamento.strftime('%d/%m/%Y') if data_agendamento else "-",
        "_data_agendamento_gestao_obj": data_agendamento,
        "tempo_espera": tempo["tempo_espera"],
        "tempo_cor": tempo["tempo_cor"],
        "marco_tempo": tempo["marco_tempo"],
    }


@login_required
def gestao_sac(request):
    sac_id = request.GET.get("sac")
    empresa_filtro, contexto_empresa = resolver_filtro_empresa(request)

    setor_gestao = obter_setor_por_codigo('SAC')
    qs = queryset_fila_por_setor(setor_gestao) if setor_gestao else SAC.objects.none()
    qs = aplicar_filtro_empresa(qs, empresa_filtro)

    agora = timezone.now()
    hoje = agora.date()
    sacs_disponiveis = []
    sacs_agendamentos = []
    for s in qs:
        card = _montar_card_gestao(s, agora)
        data_agendada = card.get("_data_agendamento_gestao_obj")
        if data_agendada and data_agendada > hoje:
            sacs_agendamentos.append(card)
        else:
            sacs_disponiveis.append(card)

    sac = None
    historicos = []
    form = None
    itens_contexto = None
    contexto_status = "-"
    contexto_acao = "-"

    if sac_id:
        sac = get_object_or_404(
            SAC.objects.select_related(
                "empresa",
                "cliente",
                "nota_fiscal",
                "status_atual",
                "acao_em_espera",
                "setor_atual",
            ),
            id=sac_id,
        )
        historicos = (
            sac.historicos
            .select_related("usuario", "status_novo", "status_anterior", "setor_origem", "setor_destino")
            .order_by("-data_evento", "-id")[:20]
        )
        historicos_detalhados = montar_historico_detalhado(historicos)
        contexto_status = getattr(getattr(sac, "status_atual", None), "nome", None) or getattr(getattr(sac, "status", None), "nome", None) or getattr(sac, "status_inicial", None) or "-"
        contexto_acao = getattr(getattr(sac, "acao_em_espera", None), "nome", None) or "-"
        tipo_ocorrencia_gestao = _obter_tipo_ocorrencia_gestao(sac)
        eh_tecnico_equipamento_gestao = _eh_tecnico_equipamento_gestao(tipo_ocorrencia_gestao)
        eh_fluxo_autorizar_manutencao_interna = eh_tecnico_equipamento_gestao and _eh_acao_autorizar_manutencao_interna_gestao(contexto_acao)
        eh_fluxo_emissao_pedido_saida = eh_tecnico_equipamento_gestao and _eh_emissao_pedido_saida_gestao(contexto_acao)
        garantia_sac = _buscar_cobertura_garantia_gestao(sac)
        valor_manutencao = _buscar_valor_total_manutencao_gestao(sac)
        dados_manutencao_interna = _dados_manutencao_interna_gestao(sac)

        if request.method == "POST":
            if request.POST.get("form_origem") == "gestao_emissao_pedido_saida" and eh_fluxo_emissao_pedido_saida:
                garantia_atual = _buscar_cobertura_garantia_gestao(sac)
                valor_manutencao = _buscar_valor_total_manutencao_gestao(sac)
                numero_pedido_devolucao = (request.POST.get("numero_pedido_devolucao") or "").strip()
                data_emissao_devolucao = (request.POST.get("data_emissao_devolucao") or "").strip()
                frete = (request.POST.get("frete") or "").strip()
                nf_servico = (request.POST.get("nf_servico") or "").strip()
                data_nf_servico = (request.POST.get("data_nf_servico") or "").strip()
                observacao_importante = (request.POST.get("observacao_importante") or "").strip()
                anexos = request.FILES.getlist("anexos_pdf")

                if garantia_atual not in {"Sim", "Não"}:
                    messages.error(request, "Não foi possível identificar se o equipamento foi coberto pela garantia no histórico deste SAC.")
                    return redirect(f"/sac/gestao/?sac={sac.id}")

                erros = []
                if not numero_pedido_devolucao:
                    erros.append("Número do Pedido de Devolução")
                if not data_emissao_devolucao:
                    erros.append("Data de Emissão")
                if garantia_atual == "Sim" and frete not in {"Pago", "A Pagar"}:
                    erros.append("Frete")
                if garantia_atual == "Não":
                    frete = "A pagar"

                if erros:
                    messages.error(request, "Preencha os campos obrigatórios: " + ", ".join(erros) + ".")
                    return redirect(f"/sac/gestao/?sac={sac.id}")

                proximo_status, proxima_acao, proximo_setor, status_txt, acao_txt, setor_txt = _destino_emissao_pedido_saida_gestao(garantia_atual)
                faltando = []
                if not proximo_status:
                    faltando.append("Status: " + status_txt)
                if not proxima_acao:
                    faltando.append("Ação em espera: " + acao_txt)
                if not proximo_setor:
                    faltando.append("Setor: " + setor_txt)
                if faltando:
                    messages.error(request, "Fluxo não configurado: " + "; ".join(faltando))
                    return redirect(f"/sac/gestao/?sac={sac.id}")

                linhas_historico = [
                    "Fluxo — Emissão do Pedido (Saída)",
                    f"Ação em espera atual: {contexto_acao or '-'}",
                    f"Tipo de ocorrência: {tipo_ocorrencia_gestao or '-'}",
                    f"Equipamento foi coberto pela garantia: {garantia_atual}",
                    f"Valor total da Manutenção: {valor_manutencao if garantia_atual == 'Não' else '-'}",
                    f"Número da Nota fiscal de Serviço: {nf_servico or '-'}",
                    f"Data de Emissão Nota de Serviço: {data_nf_servico or '-'}",
                    f"Número do Pedido de Devolução: {numero_pedido_devolucao or '-'}",
                    f"Data de Emissão: {data_emissao_devolucao or '-'}",
                    f"Frete: {frete or '-'}",
                    f"Próximo status: {proximo_status.nome}",
                    f"Ação em Espera próximo Setor: {proxima_acao.nome}",
                    f"Próximo setor: {proximo_setor.nome}",
                    f"Observação importante: {observacao_importante or '-'}",
                ]
                observacao_historico = "\n".join(linhas_historico)

                validar_transicao_basica(
                    sac,
                    status_novo=proximo_status,
                    acao_nova=proxima_acao,
                    setor_destino=proximo_setor,
                )

                resultado_transicao = aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    acao_em_espera=proxima_acao,
                    setor_destino=proximo_setor,
                    status_novo=proximo_status,
                    observacao=observacao_historico,
                    acao_executada_texto="Gestão do SAC — Emissão do Pedido (Saída)",
                    arquivo_historico=(anexos[0] if anexos else None),
                )

                for arquivo in anexos:
                    SACAnexo.objects.create(sac=sac, arquivo=arquivo)

                if getattr(sac, "data_agendamento_gestao", None):
                    sac.data_agendamento_gestao = None
                    sac.save(update_fields=["data_agendamento_gestao"])

                messages.success(request, "Emissão do Pedido (Saída) registrada e SAC encaminhado com sucesso.")
                setor_redirect = getattr(resultado_transicao, "setor_destino", None) or proximo_setor
                return _redirect_setor_gestao(sac, setor_redirect, fallback=f"/sac/gestao/?sac={sac.id}")

            form = GestaoSACPedidoRetornoForm(
                request.POST,
                request.FILES,
                sac=sac,
                acao_atual_nome=contexto_acao,
            )
            if form.is_valid():
                acao_em_espera = form.cleaned_data.get("proxima_acao_em_espera")
                proximo_status = form.cleaned_data.get("proximo_status")
                proximo_setor = form.cleaned_data.get("proximo_setor") or sac.setor_atual
                numero_pedido = (form.cleaned_data.get("numero_pedido") or "").strip()
                data_pedido = form.cleaned_data.get("data_pedido")
                cliente_emite_nf = (form.cleaned_data.get("cliente_emite_nf") or "").strip().upper()
                nf_solicitada = (form.cleaned_data.get("nf_solicitada") or "").strip().upper()
                data_emissao_nf = form.cleaned_data.get("data_emissao_nf")
                numero_nf_venda_usuario = (form.cleaned_data.get("numero_nf_venda_usuario") or "").strip()
                data_emissao_venda_usuario = form.cleaned_data.get("data_emissao_venda_usuario")
                dados_manutencao_interna = _dados_manutencao_interna_gestao(sac, data_emissao_venda_usuario)
                observacao_importante = (form.cleaned_data.get("observacao_importante") or "").strip()
                anexos = request.FILES.getlist("anexos_pdf")

                validar_transicao_basica(
                    sac,
                    status_novo=proximo_status or getattr(sac, "status_atual", None) or getattr(sac, "status", None),
                    acao_nova=acao_em_espera,
                    setor_destino=proximo_setor,
                )

                resultado_transicao = aplicar_transicao_sac(
                    sac=sac,
                    usuario=request.user,
                    acao_em_espera=acao_em_espera,
                    setor_destino=proximo_setor,
                    status_novo=proximo_status or getattr(sac, "status_atual", None) or getattr(sac, "status", None),
                    observacao="",
                    acao_executada_texto="Gestão do SAC registrada",
                    arquivo_historico=(anexos[0] if anexos else None),
                )

                anexos_salvos = 0
                for arquivo in anexos:
                    SACAnexo.objects.create(sac=sac, arquivo=arquivo)
                    anexos_salvos += 1

                if eh_tecnico_equipamento_gestao and cliente_emite_nf == "SIM" and nf_solicitada == "SIM" and data_emissao_nf:
                    sac.data_agendamento_gestao = data_emissao_nf
                    sac.save(update_fields=["data_agendamento_gestao"])
                elif getattr(sac, "data_agendamento_gestao", None):
                    sac.data_agendamento_gestao = None
                    sac.save(update_fields=["data_agendamento_gestao"])

                linhas_historico = [
                    f"Ação em espera atual: {contexto_acao or '-'}",
                ]
                if eh_tecnico_equipamento_gestao:
                    linhas_historico.extend([
                        f"Tipo de ocorrência: {tipo_ocorrencia_gestao or '-'}",
                    ])
                    if eh_fluxo_autorizar_manutencao_interna:
                        linhas_historico.extend([
                            f"Nota Fiscal de Venda: {dados_manutencao_interna.get('nota_fiscal_venda') or '-'}",
                            f"Data da Emissão da Nota fiscal: {dados_manutencao_interna.get('data_emissao_nf_venda') or '-'}",
                            f"Número da Nota fiscal de venda ao Usuário: {numero_nf_venda_usuario or '-'}",
                            f"Data de Emissão de venda ao usuário: {data_emissao_venda_usuario.strftime('%d/%m/%Y') if data_emissao_venda_usuario else '-'}",
                            f"Tempo de uso: {dados_manutencao_interna.get('tempo_uso') or '-'}",
                        ])
                    else:
                        linhas_historico.extend([
                            f"Cliente emite nota fiscal de Devolução/Remessa: {'Sim' if cliente_emite_nf == 'SIM' else 'Não' if cliente_emite_nf == 'NAO' else '-'}",
                        ])
                        if cliente_emite_nf == "SIM":
                            linhas_historico.extend([
                                f"Já foi solicitado a emissão da Nota fiscal: {'Sim' if nf_solicitada == 'SIM' else 'Não' if nf_solicitada == 'NAO' else '-'}",
                                f"Data que será emitida: {data_emissao_nf.strftime('%d/%m/%Y') if data_emissao_nf else '-'}",
                            ])
                        elif cliente_emite_nf == "NAO":
                            linhas_historico.extend([
                                f"Número do pedido: {numero_pedido or '-'}",
                                f"Data do pedido: {data_pedido.strftime('%d/%m/%Y') if data_pedido else '-'}",
                            ])
                else:
                    linhas_historico.extend([
                        f"Número do pedido: {numero_pedido or '-'}",
                        f"Data do pedido: {data_pedido.strftime('%d/%m/%Y') if data_pedido else '-'}",
                    ])
                linhas_historico.extend([
                    f"Próxima ação em espera: {acao_em_espera.nome if acao_em_espera else '-'}",
                    f"Próximo status: {proximo_status.nome if proximo_status else '-'}",
                    f"Próximo setor: {proximo_setor.nome if proximo_setor else '-'}",
                    f"Observação importante: {observacao_importante or '-'}",
                    f"Quantidade de anexos PDF: {anexos_salvos}",
                ])
                observacao_historico = "\n".join([linha for linha in linhas_historico if not linha.endswith(': -')])

                ultimo_historico = sac.historicos.order_by("-data_evento", "-id").first()
                if ultimo_historico and not (ultimo_historico.observacao or "").strip():
                    ultimo_historico.observacao = observacao_historico
                    ultimo_historico.save(update_fields=["observacao"])

                messages.success(request, "Gestão do SAC registrada com sucesso.")

                # Redirecionamento inteligente: depois de salvar, abre a tela do setor atual do SAC.
                setor_redirect = getattr(resultado_transicao, "setor_destino", None) or getattr(sac, "setor_atual", None) or proximo_setor
                setor_nome = _normalizar_texto_gestao(getattr(setor_redirect, "nome", ""))
                setor_codigo = _normalizar_texto_gestao(getattr(setor_redirect, "codigo", ""))

                if "assistencia" in setor_nome or "assistencia" in setor_codigo or "tecnica" in setor_nome:
                    return redirect(f"/sac/{sac.id}/assistencia-tecnica/")
                if "logistica" in setor_nome or "logistica" in setor_codigo:
                    return redirect(f"/sac/{sac.id}/gestao-logistica/")
                if "licitacao" in setor_nome or "licitacao" in setor_codigo:
                    return redirect(f"/sac/{sac.id}/gestao-licitacao/")
                if "comercial" in setor_nome or "comercial" in setor_codigo:
                    return redirect(f"/sac/{sac.id}/analise-comercial/")
                if "assessoria" in setor_nome or "cientifica" in setor_nome or "assessoria" in setor_codigo:
                    return redirect(f"/sac/{sac.id}/analise-tecnica/")
                if "diretoria" in setor_nome or "diretoria" in setor_codigo:
                    return redirect(f"/sac/diretoria/?sac={sac.id}")

                return redirect(f"/sac/gestao/?sac={sac.id}")
            else:
                messages.error(request, "Não foi possível salvar. Verifique os campos obrigatórios.")
        else:
            form = GestaoSACPedidoRetornoForm(sac=sac, acao_atual_nome=contexto_acao)

    historicos_detalhados = locals().get("historicos_detalhados", [])
    tipo_ocorrencia_gestao = locals().get("tipo_ocorrencia_gestao", "")
    eh_tecnico_equipamento_gestao = locals().get("eh_tecnico_equipamento_gestao", False)
    eh_fluxo_autorizar_manutencao_interna = locals().get("eh_fluxo_autorizar_manutencao_interna", False)
    eh_fluxo_emissao_pedido_saida = locals().get("eh_fluxo_emissao_pedido_saida", False)
    garantia_sac = locals().get("garantia_sac", "-")
    valor_manutencao = locals().get("valor_manutencao", "-")
    dados_manutencao_interna = locals().get("dados_manutencao_interna", {})
    sacs_disponiveis = sorted(sacs_disponiveis, key=lambda x: (x.get("marco_tempo"), x["id"]))
    sacs_agendamentos = sorted(sacs_agendamentos, key=lambda x: (x.get("_data_agendamento_gestao_obj") or timezone.now().date(), x["id"]))

    return render(request, "core/analise_gestao_sac.html", {
        "modo_lista": sac is None,
        "sac": sac,
        "form": form,
        "historicos": historicos,
        "historicos_detalhados": historicos_detalhados,
        "sacs_disponiveis": sacs_disponiveis,
        "sacs_agendamentos": sacs_agendamentos,
        "cards_pendentes": sacs_disponiveis,
        "total_sacs": len(sacs_disponiveis),
        "tipo_ocorrencia_gestao": tipo_ocorrencia_gestao,
        "eh_tecnico_equipamento_gestao": eh_tecnico_equipamento_gestao,
        "eh_fluxo_autorizar_manutencao_interna": eh_fluxo_autorizar_manutencao_interna,
        "eh_fluxo_emissao_pedido_saida": eh_fluxo_emissao_pedido_saida,
        "garantia_sac": garantia_sac,
        "valor_manutencao": valor_manutencao,
        "dados_manutencao_interna": dados_manutencao_interna,
        "contexto_status": contexto_status,
        "contexto_acao": contexto_acao,
        "dados_sac": montar_dados_padrao_sac(sac, setor_contexto=getattr(sac, "setor_atual", None), acao_atual_texto=contexto_acao),
        "dados_sac_oficiais": montar_dados_sac_oficiais(sac),
        "itens_contexto": itens_contexto,
        "fluxo_alertas": [],
        **contexto_empresa,
    })
