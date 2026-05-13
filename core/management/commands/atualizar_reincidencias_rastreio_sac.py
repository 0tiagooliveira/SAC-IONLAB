from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Empresa, SAC
from core.services.reincidencia_rastreio import sincronizar_historicos_reincidencia_sac


class Command(BaseCommand):
    help = 'Atualiza o historico dos SACs que possuem equipamento serial com SAC anterior.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', dest='empresa', default='', help='Codigo ou nome da empresa.')
        parser.add_argument('--sac', dest='sac', default='', help='Numero do SAC para atualizar.')
        parser.add_argument('--dry-run', action='store_true', help='Apenas simula a atualizacao.')

    def handle(self, *args, **options):
        qs = SAC.objects.all().select_related('empresa')

        empresa_texto = (options.get('empresa') or '').strip()
        if empresa_texto:
            empresa = (
                Empresa.objects.filter(codigo__iexact=empresa_texto).first()
                or Empresa.objects.filter(nome__iexact=empresa_texto).first()
            )
            if not empresa:
                self.stdout.write(self.style.ERROR(f'Empresa nao encontrada: {empresa_texto}'))
                return
            qs = qs.filter(empresa=empresa)

        sac_numero = (options.get('sac') or '').strip()
        if sac_numero:
            qs = qs.filter(numero=sac_numero)

        usuario = self._obter_usuario_sistema()
        if not usuario and not options['dry_run']:
            self.stdout.write(self.style.ERROR('Nao ha usuario cadastrado para gravar historico.'))
            return

        stats = sincronizar_historicos_reincidencia_sac(
            sacs=qs,
            usuario=usuario,
            dry_run=options['dry_run'],
        )

        prefixo = 'SIMULACAO' if options['dry_run'] else 'ATUALIZADO'
        self.stdout.write(
            self.style.SUCCESS(
                f'{prefixo}: avaliados={stats["avaliados"]}; '
                f'com_reincidencia={stats["com_reincidencia"]}; '
                f'criados={stats["criados"]}; atualizados={stats["atualizados"]}; '
                f'removidos={stats["removidos"]}; sem_usuario={stats["sem_usuario"]}.'
            )
        )

    def _obter_usuario_sistema(self):
        User = get_user_model()
        return (
            User.objects.filter(is_superuser=True, is_active=True).order_by('id').first()
            or User.objects.filter(is_active=True).order_by('id').first()
            or User.objects.order_by('id').first()
        )
