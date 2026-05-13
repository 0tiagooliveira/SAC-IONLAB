from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import ItemNotaFiscal, PecaTabelaPreco, SACItem
from core.services.cadastro_itens import normalizar_referencia, normalizar_texto_cadastro, normalizar_voltagem


class Command(BaseCommand):
    help = 'Atualiza descrição, grupo, origem, modelo e voltagem das referências a partir de uma planilha.'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', type=str)
        parser.add_argument('--aba', default='Referencias')

    def handle(self, *args, **options):
        arquivo = Path(options['arquivo'])
        if not arquivo.exists():
            raise CommandError(f'Arquivo não encontrado: {arquivo}')

        df = pd.read_excel(arquivo, sheet_name=options['aba'], engine='openpyxl')
        df.columns = [str(col).strip().upper() for col in df.columns]

        colunas_obrigatorias = {'REFERENCIA', 'DESCRICAO', 'GRUPO', 'ORIGEM', 'MODELO', 'VOLTAGEM'}
        faltantes = sorted(colunas_obrigatorias - set(df.columns))
        if faltantes:
            raise CommandError(f'Colunas ausentes na planilha: {", ".join(faltantes)}')

        referencias = {}
        ignoradas = 0
        for _, row in df.iterrows():
            referencia = normalizar_referencia(row.get('REFERENCIA'))
            if not referencia:
                ignoradas += 1
                continue
            referencias[referencia] = {
                'referencia': referencia,
                'descricao': normalizar_texto_cadastro(row.get('DESCRICAO')) or referencia,
                'grupo': normalizar_texto_cadastro(row.get('GRUPO')) or None,
                'origem': normalizar_texto_cadastro(row.get('ORIGEM')) or None,
                'modelo': normalizar_texto_cadastro(row.get('MODELO')) or None,
                'voltagem': normalizar_voltagem(row.get('VOLTAGEM')) or None,
            }

        if not referencias:
            raise CommandError('Nenhuma referência válida encontrada na planilha.')

        pecas_criadas = 0
        pecas_atualizadas = 0
        itens_nf_atualizados = 0
        itens_sac_atualizados = 0
        descricoes_preservadas = 0

        with transaction.atomic():
            pecas_existentes = {
                peca.referencia.upper(): peca
                for peca in PecaTabelaPreco.objects.filter(referencia__in=referencias.keys())
            }
            pecas_para_criar = []
            pecas_para_atualizar = []
            for referencia, dados in referencias.items():
                peca = pecas_existentes.get(referencia)
                if peca:
                    mudou = False
                    for campo in ('descricao', 'grupo', 'origem', 'modelo', 'voltagem'):
                        if getattr(peca, campo) != dados[campo]:
                            setattr(peca, campo, dados[campo])
                            mudou = True
                    if not peca.ativo:
                        peca.ativo = True
                        mudou = True
                    if mudou:
                        pecas_para_atualizar.append(peca)
                else:
                    pecas_para_criar.append(PecaTabelaPreco(**dados, ativo=True))

            if pecas_para_criar:
                PecaTabelaPreco.objects.bulk_create(pecas_para_criar, batch_size=500)
                pecas_criadas = len(pecas_para_criar)
            if pecas_para_atualizar:
                PecaTabelaPreco.objects.bulk_update(
                    pecas_para_atualizar,
                    ['descricao', 'grupo', 'origem', 'modelo', 'voltagem', 'ativo'],
                    batch_size=500,
                )
                pecas_atualizadas = len(pecas_para_atualizar)

            itens = list(ItemNotaFiscal.objects.filter(codigo_produto__in=referencias.keys()).only(
                'id', 'nota_fiscal_id', 'codigo_produto', 'descricao_item', 'item', 'agrp', 'origem', 'modelo', 'voltagem'
            ))
            atuais_por_grupo = defaultdict(set)
            alvo_por_grupo = Counter()
            for item in itens:
                referencia = normalizar_referencia(item.codigo_produto)
                dados = referencias.get(referencia)
                if not dados:
                    continue
                grupo_chave = (item.nota_fiscal_id, referencia)
                atuais_por_grupo[grupo_chave].add((item.descricao_item or '', item.id))
                alvo_por_grupo[(item.nota_fiscal_id, referencia, dados['descricao'])] += 1

            itens_para_atualizar = []
            for item in itens:
                referencia = normalizar_referencia(item.codigo_produto)
                dados = referencias.get(referencia)
                if not dados:
                    continue
                mudou = False
                grupo_chave = (item.nota_fiscal_id, referencia)
                alvo_chave = (item.nota_fiscal_id, referencia, dados['descricao'])
                existe_outro_com_mesma_desc = any(
                    desc == dados['descricao'] and item_id != item.id
                    for desc, item_id in atuais_por_grupo[grupo_chave]
                )
                pode_mudar_descricao = (
                    item.descricao_item != dados['descricao']
                    and alvo_por_grupo[alvo_chave] == 1
                    and not existe_outro_com_mesma_desc
                )
                if pode_mudar_descricao:
                    item.descricao_item = dados['descricao']
                    item.item = dados['descricao']
                    mudou = True
                elif item.descricao_item != dados['descricao']:
                    descricoes_preservadas += 1
                elif item.item != dados['descricao']:
                    item.item = dados['descricao']
                    mudou = True

                for campo_item, campo_dados in (
                    ('agrp', 'grupo'),
                    ('origem', 'origem'),
                    ('modelo', 'modelo'),
                    ('voltagem', 'voltagem'),
                ):
                    valor = dados[campo_dados]
                    if valor and getattr(item, campo_item) != valor:
                        setattr(item, campo_item, valor)
                        mudou = True
                if mudou:
                    itens_para_atualizar.append(item)

            if itens_para_atualizar:
                ItemNotaFiscal.objects.bulk_update(
                    itens_para_atualizar,
                    ['descricao_item', 'item', 'agrp', 'origem', 'modelo', 'voltagem'],
                    batch_size=500,
                )
                itens_nf_atualizados = len(itens_para_atualizar)

            for referencia, dados in referencias.items():
                grupo = dados.get('grupo')
                if grupo:
                    itens_sac_atualizados += SACItem.objects.filter(
                        item_nota_fiscal__codigo_produto__iexact=referencia
                    ).exclude(grupo=grupo).update(grupo=grupo)

        self.stdout.write(self.style.SUCCESS(
            'Metadados atualizados em {:%d/%m/%Y %H:%M}. Linhas: {} | peças criadas: {} | peças atualizadas: {} | itens NF atualizados: {} | itens SAC atualizados: {} | descrições preservadas por duplicidade: {} | ignoradas: {}'.format(
                timezone.now(),
                len(referencias),
                pecas_criadas,
                pecas_atualizadas,
                itens_nf_atualizados,
                itens_sac_atualizados,
                descricoes_preservadas,
                ignoradas,
            )
        ))
