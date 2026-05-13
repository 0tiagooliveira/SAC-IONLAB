from __future__ import annotations

from datetime import timedelta
from typing import Iterable, Optional

from django.db.models import Q
from django.utils import timezone

from core.models import SAC, SACItem, SacHistorico


ACAO_HISTORICO_REINCIDENCIA = 'Aviso de SAC anterior do equipamento'


def _texto_limpo(valor) -> str:
    if valor in (None, ''):
        return ''
    return str(valor).strip()


def _data_br(valor) -> str:
    if not valor:
        return '-'
    return timezone.localtime(valor).strftime('%d/%m/%Y')


def _normalizar_serial(valor) -> str:
    return _texto_limpo(valor).upper()


def _ano_sac(sac: SAC) -> int:
    ano = getattr(sac, 'ano', None) or 0
    try:
        ano = int(ano)
    except (TypeError, ValueError):
        ano = 0
    if ano:
        return ano

    numero = _texto_limpo(getattr(sac, 'numero', None))
    if '/' in numero:
        parte = numero.rsplit('/', 1)[-1]
        try:
            return int(parte)
        except (TypeError, ValueError):
            return 0
    return 0


def _tipo_ocorrencia_item(item: SACItem) -> str:
    tipo = getattr(item, 'tipo_ocorrencia', None)
    return _texto_limpo(getattr(tipo, 'nome', None)) or 'Nao informado'


def _sac_eh_anterior(sac_item: SACItem, sac_referencia: Optional[SAC]) -> bool:
    if not sac_referencia:
        return True

    sac_anterior = sac_item.sac
    if sac_anterior.pk == sac_referencia.pk:
        return False

    data_anterior = getattr(sac_anterior, 'data_abertura', None)
    data_referencia = getattr(sac_referencia, 'data_abertura', None)
    if not data_anterior or not data_referencia:
        return sac_anterior.pk < sac_referencia.pk

    if data_anterior < data_referencia:
        return True
    if data_anterior == data_referencia:
        ano_anterior = _ano_sac(sac_anterior)
        ano_referencia = _ano_sac(sac_referencia)
        if ano_anterior and ano_referencia and ano_anterior != ano_referencia:
            return ano_anterior < ano_referencia
        return sac_anterior.pk < sac_referencia.pk
    return False


def listar_reincidencias_serial(
    *,
    item_nf,
    numero_rastreio: str,
    sac_referencia: Optional[SAC] = None,
    sac_excluir_id: Optional[int] = None,
) -> list[dict]:
    numero = _texto_limpo(numero_rastreio)
    referencia = _texto_limpo(getattr(item_nf, 'codigo_produto', None))
    nota = getattr(item_nf, 'nota_fiscal', None)
    empresa_id = getattr(nota, 'empresa_id', None)

    if not item_nf or not numero or not referencia:
        return []

    query = (
        SACItem.objects.filter(
            tipo_rastreio__iexact='SERIAL',
            numero_rastreio__iexact=numero,
            item_nota_fiscal__codigo_produto__iexact=referencia,
        )
        .select_related('sac', 'sac__empresa', 'tipo_ocorrencia', 'item_nota_fiscal')
        .order_by('sac__data_abertura', 'sac__id', 'id')
    )

    if empresa_id:
        query = query.filter(sac__empresa_id=empresa_id)
    if sac_excluir_id:
        query = query.exclude(sac_id=sac_excluir_id)

    resultados = []
    sac_vistos = set()
    for sac_item in query:
        if sac_item.sac_id in sac_vistos:
            continue
        if not _sac_eh_anterior(sac_item, sac_referencia):
            continue
        sac_vistos.add(sac_item.sac_id)
        data = _data_br(getattr(sac_item.sac, 'data_abertura', None))
        tipo_ocorrencia = _tipo_ocorrencia_item(sac_item)
        sac_numero = _texto_limpo(getattr(sac_item.sac, 'numero', None)) or f'SAC {sac_item.sac_id}'
        resultados.append(
            {
                'sac_id': sac_item.sac_id,
                'sac_numero': sac_numero,
                'data': data,
                'tipo_ocorrencia': tipo_ocorrencia,
                'referencia': referencia,
                'numero_rastreio': numero,
                'texto': (
                    f'Esse Equipamento ja teve um SAC aberto em {data}. '
                    f'N\u00ba do SAC {sac_numero}. Tipo de Ocorrencia: {tipo_ocorrencia}.'
                ),
            }
        )

    return resultados


def montar_texto_reincidencia_item(
    *,
    item_nf,
    numero_rastreio: str,
    sac_referencia: Optional[SAC] = None,
    sac_excluir_id: Optional[int] = None,
) -> str:
    reincidencias = listar_reincidencias_serial(
        item_nf=item_nf,
        numero_rastreio=numero_rastreio,
        sac_referencia=sac_referencia,
        sac_excluir_id=sac_excluir_id,
    )
    return '\n'.join(r['texto'] for r in reincidencias).strip()


def montar_texto_reincidencias_sac(sac: SAC) -> str:
    if not sac:
        return ''

    itens = (
        sac.itens_sac.select_related('item_nota_fiscal', 'tipo_ocorrencia')
        .filter(tipo_rastreio__iexact='SERIAL')
        .exclude(numero_rastreio__isnull=True)
        .exclude(numero_rastreio='')
        .order_by('id')
    )

    linhas = []
    vistos = set()
    for item in itens:
        item_nf = item.item_nota_fiscal
        referencia = _texto_limpo(getattr(item_nf, 'codigo_produto', None))
        numero = _texto_limpo(item.numero_rastreio)
        chave = (referencia.upper(), _normalizar_serial(numero))
        if chave in vistos:
            continue
        vistos.add(chave)

        reincidencias = listar_reincidencias_serial(
            item_nf=item_nf,
            numero_rastreio=numero,
            sac_referencia=sac,
            sac_excluir_id=sac.pk,
        )
        if not reincidencias:
            continue

        if linhas:
            linhas.append('')
        linhas.append(f'Equipamento {referencia} | Serial {numero}')
        linhas.extend(r['texto'] for r in reincidencias)

    if not linhas:
        return ''

    return 'HISTORICO DE SAC ANTERIOR DO EQUIPAMENTO\n' + '\n'.join(linhas)


def sincronizar_historicos_reincidencia_sac(
    *,
    sacs: Optional[Iterable[SAC]] = None,
    usuario=None,
    dry_run: bool = False,
) -> dict:
    if sacs is None:
        sacs = SAC.objects.all()

    if hasattr(sacs, 'select_related'):
        sacs = sacs.select_related('status_atual', 'setor_atual').prefetch_related(
            'itens_sac__item_nota_fiscal__nota_fiscal',
            'itens_sac__tipo_ocorrencia',
        )

    stats = {
        'avaliados': 0,
        'com_reincidencia': 0,
        'criados': 0,
        'atualizados': 0,
        'removidos': 0,
        'sem_usuario': 0,
    }

    for sac in sacs:
        stats['avaliados'] += 1
        texto = montar_texto_reincidencias_sac(sac)
        historicos = SacHistorico.objects.filter(
            sac=sac,
            acao_executada=ACAO_HISTORICO_REINCIDENCIA,
        ).order_by('id')
        historico = historicos.first()

        if texto:
            stats['com_reincidencia'] += 1
            if dry_run:
                if historico:
                    stats['atualizados'] += 1
                else:
                    stats['criados'] += 1
                continue

            usuario_historico = usuario or getattr(historico, 'usuario', None)
            if not usuario_historico:
                stats['sem_usuario'] += 1
                continue

            data_evento = getattr(sac, 'data_abertura', None) or timezone.now()
            data_evento = data_evento + timedelta(seconds=2)

            if historico:
                historico.usuario = usuario_historico
                historico.data_evento = data_evento
                historico.status_novo = sac.status_atual
                historico.setor_destino = sac.setor_atual
                historico.observacao = texto
                historico.save(
                    update_fields=[
                        'usuario',
                        'data_evento',
                        'status_novo',
                        'setor_destino',
                        'observacao',
                    ]
                )
                stats['atualizados'] += 1
                extras = historicos.exclude(pk=historico.pk)
                stats['removidos'] += extras.count()
                extras.delete()
            else:
                SacHistorico.objects.create(
                    sac=sac,
                    usuario=usuario_historico,
                    data_evento=data_evento,
                    status_novo=sac.status_atual,
                    setor_destino=sac.setor_atual,
                    acao_executada=ACAO_HISTORICO_REINCIDENCIA,
                    observacao=texto,
                )
                stats['criados'] += 1
            continue

        if historico:
            if dry_run:
                stats['removidos'] += historicos.count()
            else:
                stats['removidos'] += historicos.count()
                historicos.delete()

    return stats
