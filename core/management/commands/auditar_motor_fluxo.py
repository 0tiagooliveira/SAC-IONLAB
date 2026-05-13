from django.core.management.base import BaseCommand 
from core.models import SAC 
from core.services.motor_fluxo_sac import resolver_fluxo 
from core.services.motor_log import registrar_divergencia 
 
class Command(BaseCommand): 
    help = "Audita divergencias do motor de fluxo" 
 
    def handle(self, *args, **options): 
        total = 0 
        divergencias = 0 
 
        for sac in SAC.objects.all()[:200]: 
            total += 1 
            motor = resolver_fluxo(sac) 
 
            if not motor: 
                continue 
 
            atual = str(sac.status_atual) 
            esperado = str(motor.get("proximo_status")) 
 
            if atual != esperado: 
                registrar_divergencia(sac.id, atual, esperado) 
                divergencias += 1 
 
        print("SACs analisados:", total) 
        print("Divergencias encontradas:", divergencias) 
