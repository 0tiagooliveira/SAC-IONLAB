from django.core.management.base import BaseCommand
from core.models import Empresa


class Command(BaseCommand):
    help = 'Cadastra ou atualiza as empresas iniciais do grupo'

    def handle(self, *args, **options):
        empresas = [
            {
                'codigo': 'ION',
                'razao_social': 'IONLAB EQUIP LAB E HOSPITALARES LTDA - ME',
                'nome_fantasia': 'IONLAB',
                'cnpj': '11.916.966/0001-90',
                'cor_padrao': 'Vermelho claro',
                'cor_hex': '#e58d8d',
                'ativa': True,
                'observacao': '',
            },
            {
                'codigo': 'VIT',
                'razao_social': 'VITRALAB EQUIPAMENTOS E SUPRIMENTOS PARA LABORATORIOS E HOSPITAIS EIRELI',
                'nome_fantasia': 'VITRALAB',
                'cnpj': '13.440.815/0001-33',
                'cor_padrao': 'Verde',
                'cor_hex': '#49b649',
                'ativa': True,
                'observacao': '',
            },
            {
                'codigo': 'CIO',
                'razao_social': 'CIORBRASIL IMPORTACAO E COMERCIO LTDA',
                'nome_fantasia': 'CIORBRASIL',
                'cnpj': '33.192.986/0001-06',
                'cor_padrao': 'Lilás',
                'cor_hex': '#d96be8',
                'ativa': True,
                'observacao': '',
            },
            {
                'codigo': 'AMB',
                'razao_social': 'ÂMBARLAB PRODUTOS LABORATORIAIS LTDA',
                'nome_fantasia': 'ÂMBARLAB',
                'cnpj': '80.243.769/0001-70',
                'cor_padrao': 'Azul claro',
                'cor_hex': '#8fc6f5',
                'ativa': True,
                'observacao': '',
            },
            {
                'codigo': 'ONI',
                'razao_social': 'ONIX LAB EQUIPAMENTOS LABORATORIAIS LTDA',
                'nome_fantasia': 'ONIX LAB',
                'cnpj': '10.698.323/0001-54',
                'cor_padrao': 'Azul',
                'cor_hex': '#6f95e8',
                'ativa': True,
                'observacao': '',
            },
            {
                'codigo': 'NAT',
                'razao_social': 'NATIVA LAB PRODUTOS LABORATORIAIS LTDA',
                'nome_fantasia': 'NATIVA LAB',
                'cnpj': '17.930.162/0001-21',
                'cor_padrao': 'Rosa',
                'cor_hex': '#f06292',
                'ativa': True,
                'observacao': '',
            },
            {
                'codigo': 'EVE',
                'razao_social': 'EVEN COMERCIAL LTDA',
                'nome_fantasia': 'EVEN COMERCIAL',
                'cnpj': '53.568.001/0001-01',
                'cor_padrao': 'Laranja',
                'cor_hex': '#f28c28',
                'ativa': True,
                'observacao': '',
            },
        ]

        for dados in empresas:
            empresa, criada = Empresa.objects.update_or_create(
                codigo=dados['codigo'],
                defaults=dados
            )

            if criada:
                self.stdout.write(self.style.SUCCESS(f'Empresa criada: {empresa.codigo}'))
            else:
                self.stdout.write(self.style.WARNING(f'Empresa atualizada: {empresa.codigo}'))

        self.stdout.write(self.style.SUCCESS('Cadastro das empresas concluído com sucesso.'))