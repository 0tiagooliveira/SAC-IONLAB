from django.core.management.base import BaseCommand

try:
    from core.models import SAC
except Exception:
    SAC = None

try:
    from core.services.motor_fluxo_sac import resolver_fluxo
except Exception:
    resolver_fluxo = None


class Command(BaseCommand):
    help = "Valida o motor do fluxo Comercial sem alterar regras nem banco."

    def handle(self, *args, **options):
        if SAC is None:
            self.stdout.write(self.style.ERROR("Modelo SAC nao importado."))
            return
        if resolver_fluxo is None:
            self.stdout.write(self.style.ERROR("resolver_fluxo nao encontrado em core.services.motor_fluxo_sac."))
            return

        total = 0
        com_motor = 0
        sem_motor = 0
        erros = 0

        qs = SAC.objects.all().order_by("-id")[:200]
        for sac in qs:
            total += 1
            try:
                resultado = resolver_fluxo(sac)
                if resultado:
                    com_motor += 1
                else:
                    sem_motor += 1
            except Exception as exc:
                erros += 1
                self.stdout.write(self.style.WARNING(f"SAC {getattr(sac, 'id', '?')} falhou no motor: {exc}"))

        self.stdout.write("SACs analisados: %s" % total)
        self.stdout.write("Com retorno do motor: %s" % com_motor)
        self.stdout.write("Sem retorno do motor: %s" % sem_motor)
        self.stdout.write("Erros no motor: %s" % erros)

        if erros:
            self.stdout.write(self.style.ERROR("Validacao concluida com erros no motor."))
        else:
            self.stdout.write(self.style.SUCCESS("Validacao concluida sem erros no motor."))
