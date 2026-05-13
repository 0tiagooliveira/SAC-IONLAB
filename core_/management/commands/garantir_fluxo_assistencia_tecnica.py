from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from core.models import AcaoEmEspera, Setor, StatusSAC


class Command(BaseCommand):
    help = 'Garante os cadastros mínimos usados pelo fluxo da Assistência Técnica, sem duplicar nome/código.'

    def _garantir_setor(self, codigo, nome):
        obj, _ = Setor.objects.get_or_create(
            codigo=codigo,
            defaults={'nome': nome, 'ativo': True},
        )
        updates = []
        if obj.nome != nome:
            obj.nome = nome
            updates.append('nome')
        if not obj.ativo:
            obj.ativo = True
            updates.append('ativo')
        if updates:
            obj.save(update_fields=updates)
        return obj

    def _garantir_status(self, codigo, nome):
        obj, created = StatusSAC.objects.get_or_create(
            codigo=codigo,
            defaults={'nome': nome, 'ativo': True},
        )
        updates = []
        if obj.nome != nome:
            obj.nome = nome
            updates.append('nome')
        if not obj.ativo:
            obj.ativo = True
            updates.append('ativo')
        if updates:
            obj.save(update_fields=updates)
        return obj

    def _garantir_acao(self, codigo, nome, setor_destino):
        """
        AcaoEmEspera tem UNIQUE em nome e em codigo.
        Por isso NÃO pode usar get_or_create apenas por codigo.
        Primeiro reaproveita pelo nome, depois por codigo, e só cria se nenhum existir.
        """
        obj_nome = AcaoEmEspera.objects.filter(nome=nome).first()
        obj_codigo = AcaoEmEspera.objects.filter(codigo=codigo).first()

        if obj_nome and obj_codigo and obj_nome.pk != obj_codigo.pk:
            # Conflito raro: nome e código estão em registros diferentes.
            # Para não quebrar produção, preserva o registro pelo nome e ajusta o destino/ativo.
            obj = obj_nome
            self.stdout.write(self.style.WARNING(
                f'Aviso: codigo {codigo} já existe em outra ação. Mantido registro pelo nome: {nome}'
            ))
        else:
            obj = obj_nome or obj_codigo

        if not obj:
            obj = AcaoEmEspera(nome=nome, codigo=codigo, setor_destino=setor_destino, ativo=True)
            obj.save()
            return obj

        updates = []
        if obj.nome != nome:
            obj.nome = nome
            updates.append('nome')
        if obj.codigo != codigo and not AcaoEmEspera.objects.filter(codigo=codigo).exclude(pk=obj.pk).exists():
            obj.codigo = codigo
            updates.append('codigo')
        if obj.setor_destino_id != setor_destino.id:
            obj.setor_destino = setor_destino
            updates.append('setor_destino')
        if not obj.ativo:
            obj.ativo = True
            updates.append('ativo')
        if updates:
            obj.save(update_fields=updates)
        return obj

    @transaction.atomic
    def handle(self, *args, **options):
        setor_sac = self._garantir_setor('SAC', 'SAC')
        setor_at = self._garantir_setor('ASSISTENCIA_TECNICA', 'Assistência Técnica')

        self._garantir_status('AGUARDANDO_APROVACAO_ORCAMENTO_CLIENTE', 'Aguardando Aprovação do Orçamento - Cliente')
        self._garantir_status('EM_MANUTENCAO', 'Em Manutenção')

        self._garantir_acao(
            'AGUARDANDO_APROVACAO_ORCAMENTO_CLIENTE',
            'Aguardando Aprovação do Orçamento (cliente)',
            setor_sac,
        )
        self._garantir_acao(
            'AGUARDANDO_MANUTENCAO_INTERNA',
            'Aguardando Manutenção Interna',
            setor_at,
        )

        self.stdout.write(self.style.SUCCESS('Fluxo da Assistência Técnica garantido com sucesso.'))
