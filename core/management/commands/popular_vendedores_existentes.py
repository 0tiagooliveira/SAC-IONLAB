from django.core.management.base import BaseCommand

from core.models import NotaFiscal, Vendedor
from core.services.vendedor_service import atualizar_cadastro_vendedor


class Command(BaseCommand):
    help = 'Popula a tabela de vendedores com base nas notas fiscais já importadas.'

    def handle(self, *args, **options):
        criados = 0
        atualizados_ou_reaproveitados = 0
        lidas = 0

        for nf in NotaFiscal.objects.exclude(vendedor_codigo__isnull=True).exclude(vendedor_codigo=''):
            lidas += 1
            antes = Vendedor.objects.count()
            vendedor = atualizar_cadastro_vendedor(nf.vendedor_codigo, nf.vendedor_nome)
            depois = Vendedor.objects.count()
            if vendedor is None:
                continue
            if depois > antes:
                criados += 1
            else:
                atualizados_ou_reaproveitados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Notas lidas: {lidas} | Vendedores criados: {criados} | Vendedores reaproveitados/atualizados: {atualizados_ou_reaproveitados} | Total final: {Vendedor.objects.count()}'
        ))
