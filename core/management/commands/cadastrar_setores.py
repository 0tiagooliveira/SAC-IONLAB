from django.core.management.base import BaseCommand
from core.models import Setor


class Command(BaseCommand):
    help = 'Cadastra ou atualiza os setores iniciais do sistema'

    def handle(self, *args, **options):
        setores = [
            {
                'codigo': 'SAC',
                'nome': 'SAC',
                'descricao': 'Atendimento e gestão inicial dos chamados de SAC',
                'ativo': True,
            },
            {
                'codigo': 'AST',
                'nome': 'Assistência Técnica',
                'descricao': 'Análise e tratativa técnica dos equipamentos e ocorrências',
                'ativo': True,
            },
            {
                'codigo': 'LOG',
                'nome': 'Logística',
                'descricao': 'Movimentação, coleta, expedição, transporte e devoluções',
                'ativo': True,
            },
            {
                'codigo': 'QUA',
                'nome': 'Qualidade',
                'descricao': 'Avaliação de não conformidades, causa raiz e ações corretivas',
                'ativo': True,
            },
            {
                'codigo': 'PRO',
                'nome': 'Produção',
                'descricao': 'Tratativas ligadas ao processo produtivo e fabricação',
                'ativo': True,
            },
            {
                'codigo': 'COM',
                'nome': 'Comercial',
                'descricao': 'Tratativas com clientes, pedidos, vendas e pós-venda comercial',
                'ativo': True,
            },
            {
                'codigo': 'FIN',
                'nome': 'Financeiro',
                'descricao': 'Questões financeiras, faturamento, créditos e cobranças',
                'ativo': True,
            },
            {
                'codigo': 'COMPR',
                'nome': 'Compras',
                'descricao': 'Suprimentos, fornecedores e aquisição de materiais',
                'ativo': True,
            },
            {
                'codigo': 'DIR',
                'nome': 'Diretoria',
                'descricao': 'Aprovações estratégicas e decisões gerenciais',
                'ativo': True,
            },
        ]

        for dados in setores:
            setor, criado = Setor.objects.update_or_create(
                codigo=dados['codigo'],
                defaults=dados
            )

            if criado:
                self.stdout.write(self.style.SUCCESS(f'Setor criado: {setor.nome}'))
            else:
                self.stdout.write(self.style.WARNING(f'Setor atualizado: {setor.nome}'))

        self.stdout.write(self.style.SUCCESS('Cadastro dos setores concluído com sucesso.'))