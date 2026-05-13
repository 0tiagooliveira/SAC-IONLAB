from django.core.management.base import BaseCommand

from core.services.monitoramento_sac import listar_sacs_parados


class Command(BaseCommand):
    help = 'Lista SACs em aberto parados acima do limite informado.'

    def add_arguments(self, parser):
        parser.add_argument('--horas', type=int, default=24)
        parser.add_argument('--limite', type=int, default=20)

    def handle(self, *args, **options):
        itens = listar_sacs_parados(horas=options['horas'], limite=options['limite'])
        if not itens:
            self.stdout.write(self.style.SUCCESS('Nenhum SAC parado acima do limite informado.'))
            return
        self.stdout.write(self.style.WARNING(f'Total de SACs parados: {len(itens)}'))
        for item in itens:
            self.stdout.write(
                f"{item.get('numero')} | setor={item.get('setor')} | acao={item.get('acao')} | status={item.get('status')} | horas={item.get('horas_parado')}"
            )
