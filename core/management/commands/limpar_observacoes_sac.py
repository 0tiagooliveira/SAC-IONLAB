from django.core.management.base import BaseCommand
from core.models import SACItem

class Command(BaseCommand):
    help = 'Remove observações de item contaminadas por logs/comandos de patch.'
    MARCADORES = [
        'APLICAR PATCH', 'Expand-Archive', 'powershell', 'taskkill',
        'python manage.py', 'C:\\Users\\', 'C:/Users/', 'BKP_',
        'No linha:', 'CategoryInfo', 'FullyQualifiedErrorId',
        'ExecutionPolicy', 'runserver', 'Arquivo não encontrado',
    ]
    def handle(self, *args, **options):
        limpos = 0
        for item in SACItem.objects.exclude(observacao_item__isnull=True).exclude(observacao_item=''):
            texto = item.observacao_item or ''
            if any(m.lower() in texto.lower() for m in self.MARCADORES):
                item.observacao_item = ''
                item.save(update_fields=['observacao_item'])
                limpos += 1
        self.stdout.write(self.style.SUCCESS(f'Observações contaminadas removidas: {limpos}'))
