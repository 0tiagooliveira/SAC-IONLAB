from django.core.management.base import BaseCommand

from core.models import StatusSAC, TratativaProblema, TipoProblema


class Command(BaseCommand):
    help = 'Cadastra a base de status, tratativas e tipos de problema do novo fluxo do SAC.'

    def handle(self, *args, **options):
        status_base = [
            'Aberto',
            'Análise Técnica',
            'Aguardando Cliente',
            'Importação de Peça de Reposição',
            'Coleta no Cliente',
            'Manutenção - Técnico Externo',
            'Manutenção - Técnico Interno',
            'Cancelado',
            'Concluído',
            'Trânsito para Ionlab',
            'Trânsito para o Cliente',
            'Gestão do SAC',
            'Orçamento Técnico Externo',
            'Aprovação de Orçamento - Diretoria',
            'Faturamento / Expedição',
            'Manutenção pelo Cliente',
            'Trâmite Documental',
            'Emissão de Pedido',
        ]

        tratativas = [
            'Problema Resolvido em Atendimento Remoto',
            'Problema Não Resolvido em Atendimento Remoto',
        ]

        tipos_problema = [
            'Problema Elétrico',
            'Problema Mecânico',
            'Problema Eletrônico',
        ]

        for nome in status_base:
            StatusSAC.objects.update_or_create(nome=nome, defaults={'ativo': True})

        for nome in tratativas:
            TratativaProblema.objects.update_or_create(nome=nome, defaults={'ativo': True})

        for nome in tipos_problema:
            TipoProblema.objects.update_or_create(nome=nome, defaults={'ativo': True})

        self.stdout.write(self.style.SUCCESS('Base do novo fluxo do SAC cadastrada com sucesso.'))
