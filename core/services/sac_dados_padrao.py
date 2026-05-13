import unicodedata
from django.utils import timezone
from core.services.sac_visual import formatar_duracao_dd_hh_mm
from core.utils_log_seguro import registrar_erro


def _texto_normalizado(valor):
    return unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode('ascii').strip().lower()


def _formatar_tempo_espera(delta):
    return formatar_duracao_dd_hh_mm(delta)


def _nome_setor_contexto(setor_contexto):
    if not setor_contexto:
        return ''
    if isinstance(setor_contexto, str):
        return (setor_contexto or '').strip()
    return (getattr(setor_contexto, 'nome', '') or '').strip()


def _tipo_ocorrencia_sac_texto(sac):
    nomes = []
    try:
        itens = sac.itens_sac.select_related('tipo_ocorrencia').all()
        for item in itens:
            nome = (getattr(getattr(item, 'tipo_ocorrencia', None), 'nome', '') or '').strip()
            if nome and nome not in nomes:
                nomes.append(nome)
    except Exception as e:
        registrar_erro('core.services.sac_dados_padrao.py:except_1', e)
        pass
    return ' | '.join(nomes) if nomes else '-'


def _data_hora_entrada_no_setor(sac, setor_contexto=None):
    nome_contexto = _texto_normalizado(_nome_setor_contexto(setor_contexto) or getattr(getattr(sac, 'setor_atual', None), 'nome', ''))
    try:
        historicos = sac.historicos.select_related('setor_destino').order_by('-data_evento', '-id')
        for h in historicos:
            nome_destino = _texto_normalizado(getattr(getattr(h, 'setor_destino', None), 'nome', ''))
            if nome_contexto:
                if nome_destino == nome_contexto:
                    return h.data_evento
            elif h.data_evento:
                return h.data_evento
    except Exception as e:
        registrar_erro('core.services.sac_dados_padrao.py:except_2', e)
        pass
    return getattr(sac, 'data_abertura', None)


def montar_dados_padrao_sac(sac, setor_contexto=None, acao_atual_texto=None):
    if not sac:
        return None

    data_entrada = _data_hora_entrada_no_setor(sac, setor_contexto=setor_contexto)
    agora = timezone.now()
    tempo_setor = '-'
    if data_entrada:
        try:
            tempo_setor = _formatar_tempo_espera(agora - data_entrada)
        except Exception:
            tempo_setor = '-'

    empresa = getattr(sac, 'empresa', None)
    cliente = getattr(sac, 'cliente', None)
    nota = getattr(sac, 'nota_fiscal', None)
    status_obj = getattr(sac, 'status_atual', None) or getattr(sac, 'status', None)

    return {
        'numero_sac': getattr(sac, 'numero', None) or getattr(sac, 'numero_sac', None) or '-',
        'status_atual': getattr(status_obj, 'nome', None) or getattr(sac, 'status_inicial', None) or '-',
        'empresa': getattr(empresa, 'razao_social', None) or getattr(empresa, 'nome_fantasia', None) or getattr(empresa, 'nome', None) or '-',
        'setor_atual': getattr(getattr(sac, 'setor_atual', None), 'nome', None) or '-',
        'cliente': getattr(cliente, 'razao_social', None) or getattr(cliente, 'nome', None) or str(cliente or '-') or '-',
        'nota_fiscal': getattr(nota, 'numero_nf', None) or getattr(nota, 'numero', None) or '-',
        'titulo': getattr(sac, 'titulo', None) or '-',
        'acao_em_espera_atual': acao_atual_texto or getattr(getattr(sac, 'acao_em_espera', None), 'nome', None) or '-',
        'data_hora_setor': data_entrada.strftime('%d/%m/%Y %H:%M') if data_entrada else '-',
        'tempo_setor': tempo_setor,
        'tipo_ocorrencia': _tipo_ocorrencia_sac_texto(sac),
    }
