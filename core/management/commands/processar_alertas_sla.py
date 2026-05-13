from __future__ import annotations

from django.core.management.base import BaseCommand

from core.services.alertas_sla import processar_alertas_sla


class Command(BaseCommand):
    help = "Processa alertas de SLA e envia e-mails internos e, opcionalmente, ao cliente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sem-cliente",
            action="store_true",
            help="Processa alertas sem enviar e-mail ao cliente.",
        )
        parser.add_argument(
            "--sem-interno",
            action="store_true",
            help="Processa alertas sem enviar e-mail interno.",
        )
        parser.add_argument(
            "--ignorar-janela",
            action="store_true",
            help="Ignora os horários configurados para envio dos alertas de SLA.",
        )

    def handle(self, *args, **options):
        resultados = processar_alertas_sla(
            enviar_cliente=not options["sem_cliente"],
            enviar_interno=not options["sem_interno"],
            respeitar_janela=not options["ignorar_janela"],
        )
        self.stdout.write(self.style.SUCCESS(f"Alertas processados: {len(resultados)}"))
        for item in resultados:
            self.stdout.write(
                f"SAC {item['numero_sac']} | faixa={item['faixa']} | "
                f"cliente_enviado={item['cliente_enviado']} | "
                f"motivo_cliente={item.get('motivo_cliente', '-')} | "
                f"destinatario_cliente={item.get('destinatario_cliente', '-')} | "
                f"envio_interno={item.get('envio_interno', '-')} | "
                f"destinatarios_internos={', '.join(item.get('destinatarios_internos', [])) or '-'}"
            )
