from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from core.models import AcaoEmEspera, Setor, StatusSAC
from core.services.regras_sac import (
    resolver_acao_por_codigo,
    resolver_setor_por_codigo,
    resolver_status_por_codigo,
)


def normalizar_texto_fluxo(valor: object) -> str:
    texto = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('-', ' ').replace('/', ' ').replace('(', ' ').replace(')', ' ')
    return ' '.join(texto.strip().lower().split())


def eh_acao_analise_ocorrido_logistica(nome_acao: object) -> bool:
    return normalizar_texto_fluxo(nome_acao) in {
        'analise do ocorrido logistica',
        'analise do ocorrido logistica',
        'analise do ocorrido logistica',
    }


def eh_tipo_ocorrencia_cliente_nao_confirmou(nome_tipo: object) -> bool:
    texto = normalizar_texto_fluxo(nome_tipo)
    return 'cliente nao confirmou a compra' in texto or 'clientes nao confirmou a compra' in texto


def eh_tipo_ocorrencia_item_vencido(nome_tipo: object) -> bool:
    return 'item vencido' in normalizar_texto_fluxo(nome_tipo)


@dataclass(frozen=True)
class ResultadoFluxoFormulario:
    status: object = None
    acao: object = None
    setor: object = None


def _resolver_por_nome(modelo, *nomes: str):
    nomes = [str(n or '').strip() for n in nomes if str(n or '').strip()]
    for nome in nomes:
        instancia = modelo.objects.filter(nome__iexact=nome).first()
        if instancia is not None:
            return instancia
    return None


def resolver_fluxo_formulario(caso: str) -> ResultadoFluxoFormulario:
    caso_norm = normalizar_texto_fluxo(caso)

    if caso_norm == 'analise ocorrido logistica para sac':
        status = resolver_status_por_codigo('EM_ANALISE') or _resolver_por_nome(StatusSAC, 'Em Análise', 'Em Analise')
        acao = resolver_acao_por_codigo('ANALISE_OCORRIDO_SAC') or _resolver_por_nome(AcaoEmEspera, 'Analise do Ocorrido - SAC', 'Análise do Ocorrido - SAC')
        setor = resolver_setor_por_codigo('SAC') or _resolver_por_nome(Setor, 'SAC')
        return ResultadoFluxoFormulario(status=status, acao=acao, setor=setor)

    if caso_norm == 'cliente nao confirmou coleta logistica':
        status = _resolver_por_nome(StatusSAC, 'Aguardando Coleta no Cliente', 'Aguardando coleta no cliente')
        acao = resolver_acao_por_codigo('AGUARDANDO_COLETA_CLIENTE') or _resolver_por_nome(AcaoEmEspera, 'Aguardando Coleta no Cliente')
        setor = resolver_setor_por_codigo('LOGISTICA') or _resolver_por_nome(Setor, 'Logística', 'Logistica')
        return ResultadoFluxoFormulario(status=status, acao=acao, setor=setor)

    if caso_norm == 'item vencido assessoria':
        status = resolver_status_por_codigo('EM_ANALISE') or _resolver_por_nome(StatusSAC, 'Em Análise', 'Em Analise')
        acao = resolver_acao_por_codigo('ANALISE_DO_OCORRIDO_ASSESSORIA_CIENTIFICA') or _resolver_por_nome(AcaoEmEspera, 'Analise do Ocorrido - Assessoria Cientifica', 'Análise do Ocorrido - Assessoria Científica')
        setor = resolver_setor_por_codigo('ASSESSORIA_CIENTIFICA') or _resolver_por_nome(Setor, 'Assessoria Científica', 'Assessoria Cientifica')
        return ResultadoFluxoFormulario(status=status, acao=acao, setor=setor)

    return ResultadoFluxoFormulario()


def aplicar_fluxo_resolvido_no_form(form, cleaned_data: dict, *, status=None, acao=None, setor=None,
                                   nome_campo_status='proximo_status',
                                   nome_campo_acao='proxima_acao_em_espera',
                                   nome_campo_setor='proximo_setor'):
    if status is not None and nome_campo_status in form.fields:
        cleaned_data[nome_campo_status] = status
        form.fields[nome_campo_status].initial = status.id
        form.fields[nome_campo_status].queryset = StatusSAC.objects.filter(id=status.id)
        form.fields[nome_campo_status].widget.attrs['disabled'] = 'disabled'
    if acao is not None and nome_campo_acao in form.fields:
        cleaned_data[nome_campo_acao] = acao
        form.fields[nome_campo_acao].initial = acao.id
        form.fields[nome_campo_acao].queryset = AcaoEmEspera.objects.filter(id=acao.id)
        form.fields[nome_campo_acao].widget.attrs['disabled'] = 'disabled'
    if setor is not None and nome_campo_setor in form.fields:
        cleaned_data[nome_campo_setor] = setor
        form.fields[nome_campo_setor].initial = setor.id
        form.fields[nome_campo_setor].queryset = Setor.objects.filter(id=setor.id)
        form.fields[nome_campo_setor].widget.attrs['disabled'] = 'disabled'

    # mantém campos travados mesmo quando algum elemento vier faltando
    for nome in (nome_campo_status, nome_campo_acao, nome_campo_setor):
        if nome in form.fields:
            form.fields[nome].widget.attrs['disabled'] = 'disabled'

    return status, acao, setor
