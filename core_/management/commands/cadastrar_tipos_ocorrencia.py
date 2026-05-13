from django.core.management.base import BaseCommand
from core.models import TipoOcorrencia


class Command(BaseCommand):
    help = 'Cadastra os tipos iniciais de ocorrência'

    def handle(self, *args, **options):
        ocorrencias = [
            'Itens/Equipamentos faltantes na embalagem',
            'Itens/Equipamentos sobrando na embalagem',
            'Itens/Equipamentos em desacordo com pedido',
            'Tecnico - Equipamento não funciona',
            'Itens/Equipamentos avariados',
            'Comercial - Clientes não confirmou a compra',
            'Pedido enviado em duplicidade',
        ]

        for nome in ocorrencias:
            TipoOcorrencia.objects.get_or_create(nome=nome, defaults={'ativo': True})

        self.stdout.write(self.style.SUCCESS('Tipos de ocorrência cadastrados com sucesso.'))