from django.core.management.base import BaseCommand

from core.services.monitoramento_sac import auditar_fluxo_operacional


class Command(BaseCommand):
    help = 'Audita inconsistências básicas do fluxo do SAC.'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=30)

    def handle(self, *args, **options):
        itens = auditar_fluxo_operacional(limite=options['limite'])
        if not itens:
            self.stdout.write(self.style.SUCCESS('Nenhuma inconsistência encontrada na auditoria do fluxo.'))
            return
        self.stdout.write(self.style.WARNING(f'Total de inconsistências: {len(itens)}'))
        for item in itens:
            self.stdout.write(f"[{item.severidade.upper()}] {item.numero} | {item.tipo} | {item.setor} | {item.descricao}")
