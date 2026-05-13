from django.core.management.base import BaseCommand
from core.models import StatusSAC


class Command(BaseCommand):
    help = 'Cadastra ou atualiza os status iniciais do SAC'

    def handle(self, *args, **options):
        status_lista = [
            {
                'codigo': 'ABERTO',
                'nome': 'Aberto',
                'descricao': 'SAC aberto e aguardando início da tratativa',
                'cor_hex': '#3498db',
                'ordem': 1,
                'status_inicial': True,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'TRIAGEM',
                'nome': 'Em Triagem',
                'descricao': 'SAC em análise inicial para direcionamento',
                'cor_hex': '#9b59b6',
                'ordem': 2,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'AG_TEC',
                'nome': 'Aguardando Análise Técnica',
                'descricao': 'SAC aguardando avaliação do setor técnico',
                'cor_hex': '#f1c40f',
                'ordem': 3,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'AG_LOG',
                'nome': 'Aguardando Logística',
                'descricao': 'SAC aguardando movimentação, coleta, envio ou devolução',
                'cor_hex': '#e67e22',
                'ordem': 4,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'TRANS_CLIENTE',
                'nome': 'Em Trânsito para o Cliente',
                'descricao': 'Produto, peça ou equipamento em transporte para o cliente',
                'cor_hex': '#16a085',
                'ordem': 5,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'TRANS_IONLAB',
                'nome': 'Em Trânsito para Ionlab',
                'descricao': 'Produto, peça ou equipamento em transporte para a Ionlab',
                'cor_hex': '#2980b9',
                'ordem': 6,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'AG_CLIENTE',
                'nome': 'Aguardando Cliente',
                'descricao': 'SAC aguardando retorno ou ação do cliente',
                'cor_hex': '#95a5a6',
                'ordem': 7,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'AG_IMPORT',
                'nome': 'Aguardando Importação de Peça de Reposição',
                'descricao': 'SAC aguardando chegada de peça importada para continuidade da tratativa',
                'cor_hex': '#8e44ad',
                'ordem': 8,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'AG_MAN_EXT',
                'nome': 'Aguardando Manutenção - Técnico Externo',
                'descricao': 'SAC aguardando manutenção ou atendimento por técnico externo',
                'cor_hex': '#d35400',
                'ordem': 9,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'AG_MAN_INT',
                'nome': 'Aguardando Manutenção - Técnico Interno',
                'descricao': 'SAC aguardando manutenção ou atendimento por técnico interno',
                'cor_hex': '#27ae60',
                'ordem': 10,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'TRATATIVA',
                'nome': 'Em Tratativa',
                'descricao': 'SAC em andamento com ações internas em execução',
                'cor_hex': '#1abc9c',
                'ordem': 11,
                'status_inicial': False,
                'status_final': False,
                'ativo': True,
            },
            {
                'codigo': 'CONCLUIDO',
                'nome': 'Concluído',
                'descricao': 'SAC finalizado com tratativa concluída',
                'cor_hex': '#2ecc71',
                'ordem': 12,
                'status_inicial': False,
                'status_final': True,
                'ativo': True,
            },
            {
                'codigo': 'CANCELADO',
                'nome': 'Cancelado',
                'descricao': 'SAC cancelado e encerrado sem continuidade',
                'cor_hex': '#e74c3c',
                'ordem': 13,
                'status_inicial': False,
                'status_final': True,
                'ativo': True,
            },
        ]

        for dados in status_lista:
            status, criado = StatusSAC.objects.update_or_create(
                codigo=dados['codigo'],
                defaults=dados
            )

            if criado:
                self.stdout.write(self.style.SUCCESS(f'Status criado: {status.nome}'))
            else:
                self.stdout.write(self.style.WARNING(f'Status atualizado: {status.nome}'))

        self.stdout.write(self.style.SUCCESS('Cadastro dos status do SAC concluído com sucesso.'))