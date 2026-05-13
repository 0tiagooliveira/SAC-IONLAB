from django.core.management.base import BaseCommand
from django.db.models import Count

from core.models import SAC, FluxoAcaoSetor, AcaoEmEspera
from core.services.regras_sac import eh_status_concluido


def _setor_contexto_para_sac(sac):
    if getattr(sac, 'setor_atual', None):
        return sac.setor_atual
    acao = getattr(sac, 'acao_em_espera', None)
    setor_destino = getattr(acao, 'setor_destino', None) if acao else None
    if setor_destino is not None:
        return setor_destino
    return None


class Command(BaseCommand):
    help = 'Audita cadastros e identifica combinações de fluxo faltantes no SAC.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING('==== INICIANDO AUDITORIA SAC ===='))

        acoes_sem_setor = AcaoEmEspera.objects.filter(setor_destino__isnull=True, ativo=True)
        if acoes_sem_setor.exists():
            self.stdout.write(self.style.WARNING('Ações ativas sem setor destino padrão (avaliar se são realmente manuais):'))
            for acao in acoes_sem_setor.order_by('nome'):
                self.stdout.write(f'- {acao.nome}')
        else:
            self.stdout.write(self.style.SUCCESS('OK: Todas as ações ativas possuem setor destino padrão ou não exigem setor padrão.'))

        conflitos = (
            FluxoAcaoSetor.objects
            .filter(ativo=True)
            .values('acao_atual', 'setor_atual')
            .annotate(total=Count('id'))
            .filter(total__gt=1)
        )
        if conflitos.exists():
            self.stdout.write(self.style.ERROR('Fluxos duplicados ativos encontrados:'))
            for conflito in conflitos:
                self.stdout.write(
                    f"- acao_atual_id={conflito['acao_atual']} | setor_atual_id={conflito['setor_atual']} | total={conflito['total']}"
                )
        else:
            self.stdout.write(self.style.SUCCESS('OK: Nenhum fluxo duplicado ativo por combinação de ação/setor.'))

        sacs_invalidos = [s for s in SAC.objects.select_related('status_atual', 'acao_em_espera').all() if eh_status_concluido(getattr(s, 'status_atual', None)) and getattr(s, 'acao_em_espera', None)]
        if sacs_invalidos:
            self.stdout.write(self.style.WARNING('SACs concluídos com ação em espera pendente:'))
            for sac in sacs_invalidos[:20]:
                self.stdout.write(f'- SAC {sac.id} / {sac.numero} com ação {getattr(sac.acao_em_espera, "nome", "-")}')
        else:
            self.stdout.write(self.style.SUCCESS('OK: SACs concluídos consistentes.'))

        self.stdout.write(self.style.MIGRATE_HEADING('---- COMBINAÇÕES ATUAIS SEM REGRA DE FLUXO ----'))
        faltantes = []
        qs = SAC.objects.select_related('acao_em_espera', 'setor_atual', 'acao_em_espera__setor_destino', 'status_atual').all()
        for sac in qs:
            acao = getattr(sac, 'acao_em_espera', None)
            if not acao:
                continue
            setor = _setor_contexto_para_sac(sac)
            existe = FluxoAcaoSetor.objects.filter(acao_atual=acao, setor_atual=setor, ativo=True).exists()
            existe_generica = FluxoAcaoSetor.objects.filter(acao_atual=acao, setor_atual__isnull=True, ativo=True).exists()
            if not existe and not existe_generica:
                faltantes.append((sac.id, sac.numero, getattr(acao, 'nome', '-'), getattr(setor, 'nome', '-'), getattr(getattr(sac, 'status_atual', None), 'nome', '-')))

        if faltantes:
            for sac_id, numero, acao_nome, setor_nome, status_nome in faltantes:
                self.stdout.write(
                    self.style.WARNING(
                        f'- SAC {sac_id} / {numero} | status={status_nome} | ação atual={acao_nome} | setor contexto={setor_nome}'
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS('OK: Todas as combinações atuais de ação/setor possuem regra específica ou genérica.'))

        self.stdout.write(self.style.MIGRATE_HEADING('==== AUDITORIA FINALIZADA ===='))
